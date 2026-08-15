"""WP-4 provisioning envelope and Edge credential issuance contracts.

This module is the Trust Service boundary for the target model:

Generic signed image + signed device provisioning envelope.

The functions are intentionally small and side-effect explicit so existing
image builders can call them as compatibility adapters while the old
per-device image path is migrated.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import ExtensionOID, NameOID
from sqlalchemy.orm import Session

from database import BootstrapToken, Device, EdgeCredentialInventory, EdgeLifecycleRecord, now_utc
from services.edge_lifecycle import (
    LifecycleTransitionError,
    advance_lifecycle_to,
    get_or_create_lifecycle_record,
    hardware_fingerprint,
    mark_bootstrap_consumed,
    transition_lifecycle,
)


ENVELOPE_SCHEMA = "timelapse.edge.provisioning_envelope.v1"
GENERIC_IMAGE_SCHEMA = "timelapse.edge.generic_release_image.v1"

PRIVATE_KEY_MARKERS = (
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "private_key_pem",
    "ssh_private_key",
    "tls_private_key",
)


class ProvisioningError(ValueError):
    """Raised when a WP-4 provisioning contract fails closed."""


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_generic_release_artifact_manifest(
    *,
    artifact_id: str,
    hardware_target: str,
    rootfs_sha256: str,
    build_commit: str,
) -> dict[str, Any]:
    """Return a device-neutral release artifact manifest.

    Device identity, site assignment, bootstrap credentials and operational
    private keys are deliberately excluded and enforced by contract tests.
    """
    manifest = {
        "schema": GENERIC_IMAGE_SCHEMA,
        "artifact_id": artifact_id,
        "hardware_target": hardware_target,
        "rootfs_sha256": rootfs_sha256,
        "build_commit": build_commit,
        "device_specific": False,
        "contains_operational_private_keys": False,
        "credential_policy": "no permanent device-private credentials in generic image",
    }
    assert_no_private_key_material(manifest)
    return manifest


def verify_generic_release_artifact_manifest(
    manifest: dict[str, Any],
    *,
    expected_hardware_target: str,
    expected_rootfs_sha256: str,
) -> dict[str, Any]:
    if manifest.get("schema") != GENERIC_IMAGE_SCHEMA:
        raise ProvisioningError("invalid generic image manifest schema")
    assert_no_private_key_material(manifest)
    if manifest.get("device_specific") is not False:
        raise ProvisioningError("generic image manifest is device-specific")
    if manifest.get("contains_operational_private_keys") is not False:
        raise ProvisioningError("generic image manifest contains operational private keys")
    if manifest.get("hardware_target") != expected_hardware_target:
        raise ProvisioningError("generic image hardware target mismatch")
    if manifest.get("rootfs_sha256") != expected_rootfs_sha256:
        raise ProvisioningError("generic image digest mismatch")
    return {"ok": True, "artifact_id": manifest.get("artifact_id"), "verified_at": now_utc().isoformat()}


def create_signing_key() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


def public_key_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def create_provisioning_envelope(
    *,
    private_key: ed25519.Ed25519PrivateKey,
    device_id: str,
    hardware_evidence: dict[str, Any],
    bootstrap_token_id: int | str,
    bootstrap_token_hash: str,
    image_artifact_id: str,
    hardware_target: str,
    assignment: dict[str, Any] | None = None,
    ttl: timedelta = timedelta(hours=24),
    envelope_id: str | None = None,
) -> dict[str, Any]:
    now = now_utc()
    payload = {
        "schema": ENVELOPE_SCHEMA,
        "envelope_id": envelope_id or f"env-{uuid.uuid4()}",
        "device_id": device_id,
        "hardware_fingerprint": hardware_fingerprint(device_id, hardware_evidence),
        "hardware_evidence": hardware_evidence,
        "bootstrap": {
            "token_id": str(bootstrap_token_id),
            "token_hash": bootstrap_token_hash,
            "scope": ["edge:bootstrap:enroll-once"],
            "purpose": "enroll-one-edge",
        },
        "image_artifact_id": image_artifact_id,
        "hardware_target": hardware_target,
        "assignment": assignment or {},
        "issued_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
        "private_key_policy": "edge-generates-ssh-and-tls-private-keys",
    }
    assert_no_private_key_material(payload)
    signature = private_key.sign(canonical_json(payload))
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
        "signature_algorithm": "Ed25519",
        "signed_by": "timelapse-trust-service",
    }


def verify_provisioning_envelope(
    envelope: dict[str, Any],
    *,
    public_key: ed25519.Ed25519PublicKey,
    actual_hardware_evidence: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    if not isinstance(payload, dict) or payload.get("schema") != ENVELOPE_SCHEMA:
        raise ProvisioningError("invalid provisioning envelope schema")
    if envelope.get("revoked") or payload.get("revoked"):
        raise ProvisioningError("provisioning envelope revoked")
    assert_no_private_key_material(payload)
    try:
        public_key.verify(base64.b64decode(envelope.get("signature", "")), canonical_json(payload))
    except (InvalidSignature, ValueError) as exc:
        raise ProvisioningError("provisioning envelope signature rejected") from exc

    current = now or now_utc()
    expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= current:
        raise ProvisioningError("provisioning envelope expired")

    expected = payload.get("hardware_fingerprint")
    actual = hardware_fingerprint(str(payload.get("device_id")), actual_hardware_evidence)
    if expected != actual:
        raise ProvisioningError("hardware binding rejected")
    return payload


def consume_bootstrap_envelope(
    db: Session,
    envelope: dict[str, Any],
    *,
    public_key: ed25519.Ed25519PublicKey,
    actual_hardware_evidence: dict[str, Any],
    actor: str = "edge-first-boot",
) -> EdgeCredentialInventory:
    payload = verify_provisioning_envelope(
        envelope,
        public_key=public_key,
        actual_hardware_evidence=actual_hardware_evidence,
    )
    device_id = str(payload["device_id"])
    lifecycle = db.query(EdgeLifecycleRecord).filter_by(device_id=device_id).first()
    if lifecycle and lifecycle.state in {"revoked", "retired"}:
        raise ProvisioningError("revoked or retired device cannot re-enroll without explicit recovery")

    bootstrap = payload["bootstrap"]
    token = db.query(BootstrapToken).filter_by(id=int(bootstrap["token_id"])).first()
    if token is None or token.revoked or token.used_at is not None:
        raise ProvisioningError("bootstrap credential already consumed or revoked")
    if token.expires_at and _ensure_utc(token.expires_at) <= now_utc():
        raise ProvisioningError("bootstrap credential expired")

    device = db.query(Device).filter_by(device_id=device_id).first()
    if device is None:
        device = Device(device_id=device_id, status="provisioning")
        db.add(device)
        db.flush()
    _apply_assignment(device, payload.get("assignment") or {})
    record = get_or_create_lifecycle_record(db, device, actor=actor, hardware_evidence=actual_hardware_evidence)
    for target in ("prepared", "media_written", "bootstrap_pending", "bootstrap_authenticated"):
        if record.state != target:
            try:
                transition_lifecycle(
                    db,
                    record,
                    target,
                    actor=actor,
                    reason="WP-4 provisioning envelope consumed",
                    hardware_evidence=actual_hardware_evidence,
                )
            except LifecycleTransitionError:
                if record.state != target:
                    raise

    token.used_at = now_utc()
    token.used_by_device = device_id
    token.revoked = True
    token.use_count = (token.use_count or 0) + 1
    db.flush()
    return mark_bootstrap_consumed(
        db,
        token_id=token.id,
        token_hash=str(bootstrap["token_hash"]),
        device_id=device_id,
    )


def register_edge_ssh_public_key(
    db: Session,
    *,
    device_id: str,
    public_key: str,
    actor: str = "edge-first-boot",
) -> EdgeCredentialInventory:
    fingerprint = sha256_text(public_key)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device is not None:
        device.ssh_pubkey = public_key
    existing = db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path="device_support_tunnel",
        credential_id=f"ssh:{fingerprint[:16]}",
    ).first()
    if existing and existing.status == "active":
        return existing
    return _upsert_inventory(
        db,
        device_id=device_id,
        trust_path="device_support_tunnel",
        credential_id=f"ssh:{fingerprint[:16]}",
        key_type="ssh",
        subject=f"edge:{device_id}",
        issuer="edge-generated",
        owner="physical edge",
        private_key_location="edge:/etc/timelapse/device_keys/id_ed25519",
        public_key_location="edge_credential_inventory.public_key_metadata",
        storage="Edge filesystem private key; Headend stores public metadata only",
        fingerprint=fingerprint,
        scope='["ssh:reverse-tunnel"]',
        audience="Headend controlled support conduit",
        status="active",
        legacy_path=False,
        metadata={"public_key": public_key, "actor": actor, "private_key_exported": False},
    )


def complete_edge_credentialing(
    db: Session,
    *,
    device_id: str,
    actor: str = "trust-service-provisioning",
) -> EdgeLifecycleRecord:
    ssh = db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path="device_support_tunnel",
        key_type="ssh",
        status="active",
    ).first()
    tls = db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path="local_tls",
        key_type="mtls_device_cert",
        status="active",
    ).first()
    if not ssh or not tls:
        raise ProvisioningError("credentialing requires active Edge-owned SSH identity and local TLS certificate")
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device is None:
        raise ProvisioningError("device not found")
    record = get_or_create_lifecycle_record(db, device, actor=actor)
    if record.state in {"revoked", "retired"}:
        raise ProvisioningError("revoked or retired device cannot become credentialed")
    advance_lifecycle_to(db, record, "credentialed", actor=actor, reason="WP-4 SSH/TLS credentialing complete")
    return record


def issue_tls_certificate_from_csr(
    db: Session,
    *,
    device_id: str,
    csr_pem: str,
    ca_cert_pem: str,
    ca_key_pem: str,
    actor: str = "trust-service-pki",
    days: int = 825,
) -> tuple[str, EdgeCredentialInventory]:
    lifecycle = db.query(EdgeLifecycleRecord).filter_by(device_id=device_id).first()
    if lifecycle and lifecycle.state in {"revoked", "retired"}:
        raise ProvisioningError("revoked or retired device cannot receive certificate")
    csr = x509.load_pem_x509_csr(csr_pem.encode("ascii"))
    if not csr.is_signature_valid:
        raise ProvisioningError("CSR signature invalid")
    names = _csr_names(csr)
    normalized = "".join(ch for ch in device_id.lower() if ch.isalnum())
    if not any(normalized in item.replace("-", "").replace(".", "").lower() for item in names):
        raise ProvisioningError("CSR device binding rejected")
    csr_hash = sha256_text(csr_pem)
    duplicate = _active_credential_by_metadata(
        db,
        device_id=device_id,
        trust_path="local_tls",
        metadata_key="csr_sha256",
        metadata_value=csr_hash,
    )
    if duplicate:
        raise ProvisioningError("duplicate CSR rejected")

    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode("ascii"))
    ca_key = serialization.load_pem_private_key(ca_key_pem.encode("ascii"), password=None)
    now = now_utc()
    builder = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    )
    try:
        san = csr.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        builder = builder.add_extension(san, critical=False)
    except x509.ExtensionNotFound:
        pass
    certificate = builder.sign(private_key=ca_key, algorithm=hashes.SHA256())
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
    inventory = _upsert_inventory(
        db,
        device_id=device_id,
        trust_path="local_tls",
        credential_id=f"local-tls:{format(certificate.serial_number, 'x')}",
        key_type="mtls_device_cert",
        subject=certificate.subject.rfc4514_string(),
        issuer=certificate.issuer.rfc4514_string(),
        owner="physical edge",
        private_key_location="edge:/etc/timelapse/certs/mgmt.key",
        public_key_location="edge:/etc/timelapse/certs/mgmt.crt",
        storage="CSR-signed certificate; Headend stores certificate metadata only",
        fingerprint=certificate.fingerprint(hashes.SHA256()).hex(),
        scope='["local-service:tls"]',
        audience="Edge local technician HTTPS endpoint",
        status="active",
        legacy_path=False,
        expires_at=certificate.not_valid_after_utc,
        metadata={"actor": actor, "csr_sha256": csr_hash, "private_key_exported": False},
    )
    return certificate_pem, inventory


def allow_reenrollment_recovery_transition(
    db: Session,
    *,
    device_id: str,
    recovery_ticket: str,
    actor: str,
    reason: str,
) -> EdgeLifecycleRecord:
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device is None:
        raise ProvisioningError("device not found")
    record = get_or_create_lifecycle_record(db, device, actor=actor)
    if record.state not in {"revoked", "retired", "quarantined"}:
        raise ProvisioningError("recovery transition only applies to revoked, retired or quarantined devices")
    record.state = "prepared"
    record.transition_reason = reason
    record.metadata_json = json.dumps({
        **_record_metadata(record),
        "recovery_ticket": recovery_ticket,
        "recovery_actor": actor,
        "requires_new_edge_generated_keys": True,
    }, sort_keys=True, ensure_ascii=False)
    record.updated_at = now_utc()
    return record


def revoke_edge_credential(
    db: Session,
    *,
    device_id: str,
    trust_path: str,
    actor: str,
    reason: str,
) -> list[EdgeCredentialInventory]:
    now = now_utc()
    rows = db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path=trust_path,
        status="active",
    ).all()
    for row in rows:
        row.status = "revoked"
        row.revoked_at = now
        metadata = _metadata(row)
        metadata.update({"revoked_by": actor, "revocation_reason": reason})
        row.metadata_json = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
    return rows


def create_reenrollment_recovery_intent(
    *,
    device_id: str,
    recovery_ticket: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "recovery_ticket": recovery_ticket,
        "reason": reason,
        "requires_explicit_operator_approval": True,
        "requires_new_bootstrap_credential": True,
        "requires_new_edge_generated_keys": True,
        "old_private_keys_reused": False,
    }


def create_replacement_edge_assignment(
    *,
    old_device_id: str,
    new_device_id: str,
    assignment: dict[str, Any],
    recovery_ticket: str,
) -> dict[str, Any]:
    return {
        "old_device_id": old_device_id,
        "new_device_id": new_device_id,
        "recovery_ticket": recovery_ticket,
        "inherits_logical_assignment": {
            "customer_id": assignment.get("customer_id"),
            "site_id": assignment.get("site_id"),
            "camera_id": assignment.get("camera_id"),
        },
        "inherits_private_keys": False,
        "requires_new_edge_generated_keys": True,
    }


def legacy_image_provisioning_adapter_plan(*, device_id: str, image_artifact_id: str) -> dict[str, Any]:
    """Declare the old per-device image path as migration compatibility."""
    return {
        "device_id": device_id,
        "image_artifact_id": image_artifact_id,
        "mode": "legacy-per-device-image-adapter",
        "target_mode": "generic-image-plus-envelope",
        "compatible": True,
        "read_existing_state_only": True,
        "may_create_new_credentials": False,
        "must_not_create_new_operational_private_keys_on_headend": True,
    }


def legacy_edge_migration_plan(
    *,
    device_id: str,
    capture_upload_scope: str = '["capture:write","upload:sftp:site"]',
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "mode": "legacy-edge-single-device-migration",
        "capture_upload_continuity": "preserve existing API/SFTP credentials until WP-4 successor credentials are active",
        "legacy_paths_read_only": True,
        "may_create_new_credentials_via_legacy_path": False,
        "successor_paths": ["device_support_tunnel", "local_tls", "bootstrap"],
        "scope_preserved": capture_upload_scope,
    }


def rotate_out_legacy_private_key_authority(
    db: Session,
    *,
    device_id: str,
    actor: str,
    reason: str,
) -> list[EdgeCredentialInventory]:
    now = now_utc()
    rows = (
        db.query(EdgeCredentialInventory)
        .filter(
            EdgeCredentialInventory.device_id == device_id,
            EdgeCredentialInventory.legacy_path.is_(True),
            EdgeCredentialInventory.trust_path.in_([
                "device_support_tunnel_legacy_headend_private_key",
                "local_tls_legacy_image_injected",
                "local_tls",
            ]),
        )
        .all()
    )
    for row in rows:
        if row.trust_path == "local_tls" and row.legacy_path is not True:
            continue
        row.status = "rotated"
        row.rotated_at = now
        metadata = _metadata(row)
        metadata.update({
            "rotated_out_by": actor,
            "rotation_reason": reason,
            "parallel_authority": False,
            "legacy_path_read_only": True,
        })
        row.metadata_json = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
    return rows


def assert_no_private_key_material(data: dict[str, Any]) -> None:
    text = json.dumps(data, sort_keys=True, default=str)
    if any(marker in text for marker in PRIVATE_KEY_MARKERS):
        raise ProvisioningError("private operational key material is not allowed in image/envelope")


def _csr_names(csr: x509.CertificateSigningRequest) -> set[str]:
    names = {csr.subject.rfc4514_string()}
    for attr in csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME):
        names.add(attr.value)
    try:
        san = csr.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        names.update(san.get_values_for_type(x509.DNSName))
        names.update(str(ip) for ip in san.get_values_for_type(x509.IPAddress))
    except x509.ExtensionNotFound:
        pass
    return names


def _upsert_inventory(
    db: Session,
    *,
    device_id: str,
    trust_path: str,
    credential_id: str,
    key_type: str,
    subject: str,
    issuer: str,
    owner: str,
    private_key_location: str,
    public_key_location: str,
    storage: str,
    fingerprint: str,
    scope: str,
    audience: str,
    status: str,
    legacy_path: bool,
    metadata: dict[str, Any],
    expires_at: datetime | None = None,
) -> EdgeCredentialInventory:
    now = now_utc()
    for old in db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path=trust_path,
        key_type=key_type,
        status="active",
    ):
        if old.credential_id != credential_id:
            old.status = "rotated"
            old.rotated_at = now
    row = db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path=trust_path,
        credential_id=credential_id,
    ).first()
    if row is None:
        row = EdgeCredentialInventory(device_id=device_id, trust_path=trust_path, credential_id=credential_id)
        db.add(row)
    row.key_type = key_type
    row.subject = subject
    row.issuer = issuer
    row.owner = owner
    row.private_key_location = private_key_location
    row.public_key_location = public_key_location
    row.storage = storage
    row.fingerprint = fingerprint
    row.scope = scope
    row.audience = audience
    row.rotation = "rotate/re-enroll through WP-4 provisioning flow"
    row.revocation = "edge_credential_inventory.status=revoked and Trust Service revocation metadata"
    row.status = status
    row.legacy_path = legacy_path
    row.compromise_procedure = "revoke credential, quarantine device if provenance is uncertain, re-enroll with new Edge-generated keys"
    row.lifecycle_state_created = "credentialed"
    row.issued_at = row.issued_at or now
    row.activated_at = now if status == "active" else row.activated_at
    row.expires_at = expires_at
    row.metadata_json = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
    return row


def _metadata(row: EdgeCredentialInventory) -> dict[str, Any]:
    try:
        data = json.loads(row.metadata_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _record_metadata(row: EdgeLifecycleRecord) -> dict[str, Any]:
    try:
        data = json.loads(row.metadata_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _active_credential_by_metadata(
    db: Session,
    *,
    device_id: str,
    trust_path: str,
    metadata_key: str,
    metadata_value: str,
) -> EdgeCredentialInventory | None:
    for row in db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path=trust_path,
        status="active",
    ):
        if _metadata(row).get(metadata_key) == metadata_value:
            return row
    return None


def _apply_assignment(device: Device, assignment: dict[str, Any]) -> None:
    if not assignment:
        return
    if assignment.get("customer_id"):
        device.customer_id = str(assignment["customer_id"])
    if assignment.get("site_id"):
        device.site_id = str(assignment["site_id"])
    if assignment.get("camera_id"):
        device.camera_name = str(assignment["camera_id"])
    device.enrollment_state = "active"


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
