"""WP-1 Edge identity, enrollment and credential lifecycle contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from database import (
    Camera,
    Device,
    DeviceAssignment,
    EdgeCredentialInventory,
    EdgeLifecycleRecord,
    KeyCredential,
    Settings,
    Site,
    now_utc,
)


STATES: tuple[str, ...] = (
    "manufactured",
    "prepared",
    "media_written",
    "bootstrap_pending",
    "bootstrap_authenticated",
    "hardware_verified",
    "enrolled",
    "credentialed",
    "assigned",
    "commissioned",
    "active",
    "degraded",
    "quarantined",
    "revoked",
    "retired",
)

TERMINAL_STATES = {"revoked", "retired"}
USABLE_CREDENTIAL_STATES = {"active"}
BLOCKED_CREDENTIAL_STATES = {"unknown", "not_present", "rotated", "revoked", "retired", "expired", "consumed"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "manufactured": {"prepared", "quarantined", "retired"},
    "prepared": {"media_written", "bootstrap_pending", "quarantined", "retired"},
    "media_written": {"bootstrap_pending", "quarantined", "retired"},
    "bootstrap_pending": {"bootstrap_authenticated", "quarantined", "retired"},
    "bootstrap_authenticated": {"hardware_verified", "quarantined", "retired"},
    "hardware_verified": {"enrolled", "quarantined", "retired"},
    "enrolled": {"credentialed", "quarantined", "revoked", "retired"},
    "credentialed": {"assigned", "quarantined", "revoked", "retired"},
    "assigned": {"commissioned", "active", "degraded", "quarantined", "revoked", "retired"},
    "commissioned": {"active", "degraded", "quarantined", "revoked", "retired"},
    "active": {"degraded", "quarantined", "revoked", "retired"},
    "degraded": {"active", "quarantined", "revoked", "retired"},
    "quarantined": {"prepared", "revoked", "retired"},
    "revoked": {"retired"},
    "retired": set(),
}

MONOTONIC_FORWARD_ORDER = {state: index for index, state in enumerate(STATES)}
NORMAL_CONVERGENCE_PATH: tuple[str, ...] = (
    "manufactured",
    "prepared",
    "media_written",
    "bootstrap_pending",
    "bootstrap_authenticated",
    "hardware_verified",
    "enrolled",
    "credentialed",
    "assigned",
    "commissioned",
    "active",
)


class LifecycleTransitionError(ValueError):
    """Raised when a requested transition violates the canonical state machine."""


@dataclass(frozen=True)
class LifecycleTransition:
    device_id: str
    from_state: str
    to_state: str
    actor: str
    reason: str


def canonical_state_for_device(device: Device) -> str:
    """Infer a compatibility state from current legacy Device fields."""
    status = (device.status or "").lower()
    if status in {"retired", "deleted"}:
        return "retired"
    if status in {"revoked", "disabled"}:
        return "revoked"
    if status == "provisioning":
        return "prepared"
    if device.api_token:
        if device.site_id or device.customer_id or device.camera_name:
            return "assigned"
        return "credentialed"
    if device.enrollment_state == "active" and (device.site_id or device.customer_id or device.camera_name):
        return "assigned"
    if device.enrollment_state == "unassigned":
        return "enrolled"
    return "manufactured"


def hardware_fingerprint(device_id: str, evidence: dict[str, Any] | None = None) -> str:
    # Hardware evidence must stand apart from the logical device_id so a cloned
    # or mistyped logical identity bound to the same board is detected.
    material = evidence or {"device_id": device_id}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(Settings).filter_by(key=key).first()
    return row.value if row and row.value is not None else default


def credential_state_allows_use(row: EdgeCredentialInventory | None) -> bool:
    """Fail closed unless a credential inventory row is explicitly active."""
    return bool(row and (row.status or "unknown") in USABLE_CREDENTIAL_STATES)


def find_active_api_credential(
    db: Session,
    *,
    device_id: str,
    token_hash: str,
) -> EdgeCredentialInventory | None:
    row = (
        db.query(EdgeCredentialInventory)
        .filter_by(
            device_id=device_id,
            trust_path="device_api",
            key_type="api",
            secret_hash=token_hash,
        )
        .order_by(EdgeCredentialInventory.activated_at.desc(), EdgeCredentialInventory.created_at.desc())
        .first()
    )
    return row if credential_state_allows_use(row) else None


def mark_bootstrap_consumed(
    db: Session,
    *,
    token_id: Any,
    token_hash: str,
    device_id: str,
    status: str = "consumed",
) -> EdgeCredentialInventory:
    now = now_utc()
    return _upsert_inventory(
        db,
        device_id=device_id,
        trust_path="bootstrap",
        credential_id=f"bootstrap:{token_id}",
        key_type="bootstrap",
        subject=f"edge:{device_id}",
        issuer="headend",
        owner="headend provisioning",
        private_key_location="not stored",
        public_key_location="",
        storage="bootstrap_tokens.token plus inventory hash",
        secret_hash=token_hash,
        fingerprint=hashlib.sha256(token_hash.encode()).hexdigest(),
        source_table="bootstrap_tokens",
        source_id=str(token_id),
        lifetime="short-lived one-purpose enrollment credential",
        scope='["edge:bootstrap:enroll-once"]',
        audience="Headend enrollment/bootstrap endpoints",
        rotation="create a new bootstrap token; never reuse consumed token",
        revocation="bootstrap_tokens.revoked=true and edge_credential_inventory.status=revoked",
        status=status,
        legacy_path=False,
        compromise_procedure="revoke token, retire any device enrolled with uncertain provenance, issue a new envelope",
        lifecycle_state_created="bootstrap_authenticated",
        issued_at=now,
        activated_at=now if status == "active" else None,
        consumed_at=now if status == "consumed" else None,
        metadata={"purpose": "one-purpose bootstrap/enrollment", "consumed_by_device": device_id},
    )


def migrate_legacy_api_token_to_inventory(
    db: Session,
    device: Device,
    *,
    token_hash: str,
    actor: str,
) -> EdgeCredentialInventory:
    now = now_utc()
    return _upsert_inventory(
        db,
        device_id=device.device_id,
        trust_path="device_api",
        credential_id=f"legacy-api:{token_hash[:16]}",
        key_type="api",
        subject=f"edge:{device.device_id}",
        issuer="legacy devices.api_token adapter",
        owner="headend-governed edge",
        private_key_location="/opt/timelapse/edge/api_token.txt",
        public_key_location="",
        storage="edge_credential_inventory.secret_hash; migrated from devices.api_token",
        secret_hash=token_hash,
        fingerprint=hashlib.sha256(token_hash.encode()).hexdigest(),
        source_table="devices",
        source_id=device.device_id,
        lifetime="legacy compatibility until explicit rotation",
        scope='["config:read","heartbeat:write","capture:write","updates:poll"]',
        audience="Headend Edge API",
        rotation="issue managed inventory API credential and clear devices.api_token after Edge confirms",
        revocation="edge_credential_inventory.status=revoked and clear devices.api_token",
        status="active",
        legacy_path=True,
        compromise_procedure="revoke inventory row, clear devices.api_token, re-enroll or rotate device",
        lifecycle_state_created=canonical_state_for_device(device),
        issued_at=device.created_at or now,
        activated_at=now,
        metadata={"source": "devices.api_token", "actor": actor, "migration_adapter": True},
    )


def issue_inventory_api_credential(
    db: Session,
    device: Device,
    *,
    credential_id: str,
    token_hash: str,
    fingerprint: str,
    actor: str,
    scopes_json: str,
    source_table: str = "key_credentials",
) -> EdgeCredentialInventory:
    """Install a single active canonical API credential in inventory."""
    now = now_utc()
    for row in (
        db.query(EdgeCredentialInventory)
        .filter_by(device_id=device.device_id, trust_path="device_api", key_type="api", status="active")
        .all()
    ):
        if row.credential_id == credential_id:
            continue
        row.status = "rotated"
        row.rotated_at = now
        row.updated_at = now
    return _upsert_inventory(
        db,
        device_id=device.device_id,
        trust_path="device_api",
        credential_id=credential_id,
        key_type="api",
        subject=f"edge:{device.device_id}",
        issuer=actor,
        owner="headend-governed edge",
        private_key_location="edge local token file only; headend stores hash in inventory",
        public_key_location="",
        storage="edge_credential_inventory.secret_hash",
        secret_hash=token_hash,
        fingerprint=fingerprint,
        source_table=source_table,
        source_id=credential_id,
        lifetime="until rotation/revocation/retirement",
        scope=scopes_json,
        audience="Headend Edge API",
        rotation="edge_credential_inventory successor row; previous active row becomes rotated",
        revocation="edge_credential_inventory.status=revoked",
        status="active",
        legacy_path=False,
        compromise_procedure="revoke inventory row, quarantine lifecycle if identity integrity is uncertain",
        lifecycle_state_created=canonical_state_for_device(device),
        issued_at=now,
        activated_at=now,
        metadata={"actor": actor, "canonical_authority": True},
    )


def get_or_create_lifecycle_record(
    db: Session,
    device: Device,
    *,
    actor: str = "wp1-reconcile",
    hardware_evidence: dict[str, Any] | None = None,
) -> EdgeLifecycleRecord:
    record = db.query(EdgeLifecycleRecord).filter_by(device_id=device.device_id).first()
    if record:
        return record
    state = canonical_state_for_device(device)
    now = now_utc()
    record = EdgeLifecycleRecord(
        device_id=device.device_id,
        state=state,
        hardware_fingerprint=hardware_fingerprint(device.device_id, hardware_evidence),
        hardware_evidence_json=_json(hardware_evidence or {}),
        transition_reason=f"Initial WP-1 reconciliation by {actor}",
        metadata_json=_json({"source": "legacy_device_fields", "actor": actor}),
        created_at=now,
        updated_at=now,
    )
    _stamp_state_timestamp(record, state, now)
    db.add(record)
    return record


def _stamp_state_timestamp(record: EdgeLifecycleRecord, state: str, timestamp) -> None:
    field_by_state = {
        "prepared": "prepared_at",
        "bootstrap_authenticated": "bootstrapped_at",
        "hardware_verified": "hardware_verified_at",
        "enrolled": "enrolled_at",
        "credentialed": "credentialed_at",
        "assigned": "assigned_at",
        "commissioned": "commissioned_at",
        "active": "commissioned_at",
        "revoked": "revoked_at",
        "retired": "retired_at",
    }
    field = field_by_state.get(state)
    if field and getattr(record, field) is None:
        setattr(record, field, timestamp)


def assert_no_duplicate_hardware_identity(
    db: Session,
    *,
    device_id: str,
    fingerprint: str,
) -> None:
    duplicate = (
        db.query(EdgeLifecycleRecord)
        .filter(
            EdgeLifecycleRecord.hardware_fingerprint == fingerprint,
            EdgeLifecycleRecord.device_id != device_id,
            EdgeLifecycleRecord.state.notin_(["retired"]),
        )
        .first()
    )
    if duplicate:
        raise LifecycleTransitionError(
            f"Duplicate Edge hardware identity: {fingerprint} is already bound to {duplicate.device_id}"
        )


def transition_lifecycle(
    db: Session,
    record: EdgeLifecycleRecord,
    to_state: str,
    *,
    actor: str,
    reason: str,
    hardware_evidence: dict[str, Any] | None = None,
) -> LifecycleTransition:
    from_state = record.state or "manufactured"
    if to_state not in STATES:
        raise LifecycleTransitionError(f"Unknown lifecycle state: {to_state}")
    if from_state in TERMINAL_STATES and to_state not in ALLOWED_TRANSITIONS[from_state]:
        raise LifecycleTransitionError(f"Cannot transition {record.device_id} from terminal state {from_state} to {to_state}")
    if to_state == from_state:
        return LifecycleTransition(record.device_id, from_state, to_state, actor, reason)
    if to_state not in ALLOWED_TRANSITIONS.get(from_state, set()):
        raise LifecycleTransitionError(f"Forbidden lifecycle transition for {record.device_id}: {from_state} -> {to_state}")
    if to_state in {"hardware_verified", "enrolled", "credentialed", "assigned", "commissioned", "active"}:
        if from_state == "manufactured":
            raise LifecycleTransitionError(f"{record.device_id} cannot skip preparation before {to_state}")
    if hardware_evidence is not None:
        fingerprint = hardware_fingerprint(record.device_id, hardware_evidence)
        assert_no_duplicate_hardware_identity(db, device_id=record.device_id, fingerprint=fingerprint)
        record.hardware_fingerprint = fingerprint
        record.hardware_evidence_json = _json(hardware_evidence)
    now = now_utc()
    record.state = to_state
    record.transition_reason = reason
    record.updated_at = now
    _stamp_state_timestamp(record, to_state, now)
    return LifecycleTransition(record.device_id, from_state, to_state, actor, reason)


def advance_lifecycle_to(
    db: Session,
    record: EdgeLifecycleRecord,
    target_state: str,
    *,
    actor: str,
    reason: str,
    hardware_evidence: dict[str, Any] | None = None,
) -> list[LifecycleTransition]:
    """Advance a compatibility record along the canonical happy path.

    Legacy endpoints historically performed several lifecycle steps at once.
    WP-1 keeps those endpoints compatible while recording each canonical state
    transition instead of jumping over the contract.
    """
    if target_state not in NORMAL_CONVERGENCE_PATH:
        return [transition_lifecycle(
            db, record, target_state, actor=actor, reason=reason, hardware_evidence=hardware_evidence
        )]
    if record.state not in NORMAL_CONVERGENCE_PATH:
        return [transition_lifecycle(
            db, record, target_state, actor=actor, reason=reason, hardware_evidence=hardware_evidence
        )]
    current_index = NORMAL_CONVERGENCE_PATH.index(record.state)
    target_index = NORMAL_CONVERGENCE_PATH.index(target_state)
    if target_index <= current_index:
        return []
    transitions = []
    for next_state in NORMAL_CONVERGENCE_PATH[current_index + 1: target_index + 1]:
        transitions.append(transition_lifecycle(
            db,
            record,
            next_state,
            actor=actor,
            reason=reason,
            hardware_evidence=hardware_evidence if next_state == "hardware_verified" else None,
        ))
    return transitions


def _upsert_inventory(
    db: Session,
    *,
    device_id: str,
    trust_path: str,
    credential_id: str | None,
    key_type: str,
    subject: str,
    issuer: str,
    owner: str,
    private_key_location: str,
    public_key_location: str,
    storage: str,
    secret_hash: str | None = None,
    fingerprint: str | None = None,
    source_table: str = "",
    source_id: str = "",
    lifetime: str = "",
    scope: str = "",
    audience: str = "",
    rotation: str = "",
    revocation: str = "",
    status: str = "active",
    legacy_path: bool = False,
    compromise_procedure: str = "",
    lifecycle_state_created: str = "",
    issued_at: Any = None,
    activated_at: Any = None,
    rotated_at: Any = None,
    revoked_at: Any = None,
    retired_at: Any = None,
    expires_at: Any = None,
    consumed_at: Any = None,
    metadata: dict[str, Any] | None = None,
) -> EdgeCredentialInventory:
    lookup_id = credential_id or f"legacy:{trust_path}"
    row = (
        db.query(EdgeCredentialInventory)
        .filter_by(device_id=device_id, trust_path=trust_path, credential_id=lookup_id)
        .first()
    )
    if not row:
        row = EdgeCredentialInventory(device_id=device_id, trust_path=trust_path, credential_id=lookup_id)
        db.add(row)
    row.key_type = key_type
    row.subject = subject
    row.issuer = issuer
    row.owner = owner
    row.private_key_location = private_key_location
    row.public_key_location = public_key_location
    row.storage = storage
    row.secret_hash = secret_hash
    row.fingerprint = fingerprint
    row.source_table = source_table
    row.source_id = source_id
    row.lifetime = lifetime
    row.scope = scope
    row.audience = audience
    row.rotation = rotation
    row.revocation = revocation
    row.status = status
    row.legacy_path = bool(legacy_path)
    row.compromise_procedure = compromise_procedure
    row.lifecycle_state_created = lifecycle_state_created
    row.issued_at = issued_at
    row.activated_at = activated_at
    row.rotated_at = rotated_at
    row.revoked_at = revoked_at
    row.retired_at = retired_at
    row.expires_at = expires_at
    row.consumed_at = consumed_at
    row.metadata_json = _json(metadata or {})
    row.updated_at = now_utc()
    return row


def reconcile_device_credentials(
    db: Session,
    device: Device,
    *,
    actor: str = "wp1-reconcile",
) -> list[EdgeCredentialInventory]:
    record = get_or_create_lifecycle_record(db, device, actor=actor)
    assignment = (
        db.query(DeviceAssignment)
        .filter_by(device_id=device.device_id, unassigned_at=None)
        .order_by(DeviceAssignment.assigned_at.desc())
        .first()
    )
    camera = db.query(Camera).filter_by(id=assignment.camera_id).first() if assignment else None
    site = db.query(Site).filter_by(id=device.site_id).first() if device.site_id else None
    if not site and camera and camera.site_id:
        site = db.query(Site).filter_by(id=camera.site_id).first()
    for stale in db.query(EdgeCredentialInventory).filter_by(device_id=device.device_id).all():
        stale.status = "not_present"
        stale.updated_at = now_utc()
    rows: list[EdgeCredentialInventory] = []
    for credential in (
        db.query(KeyCredential)
        .filter_by(entity_type="edge", entity_id=device.device_id)
        .order_by(KeyCredential.created_at.desc())
        .all()
    ):
        try:
            credential_metadata = json.loads(credential.metadata_json or "{}")
        except Exception:
            credential_metadata = {}
        trust_path = {
            "api": "device_api",
            "ssh": "device_support_tunnel",
            "bootstrap": "bootstrap",
            "mtls_device_cert": "local_tls",
            "signing": "update_release_trust",
        }.get(credential.key_type, f"key:{credential.key_type}")
        rows.append(_upsert_inventory(
            db,
            device_id=device.device_id,
            trust_path=trust_path,
            credential_id=credential.credential_id,
            key_type=credential.key_type,
            subject=f"edge:{device.device_id}",
            issuer=credential.created_by or "headend",
            owner="edge" if credential.key_type != "api" else "headend-governed edge",
            private_key_location="not stored in key_credentials" if not credential.secret_hash else "edge local secret; hash in headend",
            public_key_location="key_credentials.public_key" if credential.public_key else "",
            storage="key_credentials",
            secret_hash=credential.secret_hash,
            fingerprint=credential.fingerprint,
            source_table="key_credentials",
            source_id=credential.credential_id,
            lifetime=credential.expires_at.isoformat() if credential.expires_at else "not-explicit",
            scope=credential.scopes_json or "[]",
            audience=f"timelapse:{trust_path}",
            rotation="KeyCredential rotation/revocation endpoint",
            revocation="key_credentials.status=revoked",
            status=credential.status or "active",
            legacy_path='"migrated_from_legacy_device_api_token":true' in (credential.metadata_json or ""),
            compromise_procedure="revoke credential, rotate trust path, quarantine device if identity integrity is uncertain",
            lifecycle_state_created=record.state,
            issued_at=credential.created_at,
            activated_at=credential.created_at if credential.status == "active" else None,
            rotated_at=credential.revoked_at if credential.status == "rotated" else None,
            revoked_at=credential.revoked_at if credential.status == "revoked" else None,
            retired_at=credential.revoked_at if credential.status == "retired" else None,
            expires_at=credential.expires_at,
            metadata={
                **credential_metadata,
                "source": "key_credentials",
                "actor": actor,
                "canonical_authority": credential.key_type == "api",
            },
        ))

    if device.api_token:
        rows.append(_upsert_inventory(
            db,
            device_id=device.device_id,
            trust_path="device_api_legacy",
            credential_id=None,
            key_type="api",
            subject=f"edge:{device.device_id}",
            issuer="headend",
            owner="legacy compatibility",
            private_key_location="/opt/timelapse/edge/api_token.txt",
            public_key_location="",
            storage="devices.api_token plus Edge file",
            secret_hash=hashlib.sha256(device.api_token.encode()).hexdigest(),
            fingerprint=hashlib.sha256(hashlib.sha256(device.api_token.encode()).hexdigest().encode()).hexdigest(),
            source_table="devices",
            source_id=device.device_id,
            lifetime="not-explicit",
            scope='["config:read","heartbeat:write","capture:write","updates:poll"]',
            audience="Headend Edge API",
            rotation="rotate to managed key_credentials API credential",
            revocation="clear devices.api_token and revoke matching KeyCredential",
            status="active",
            legacy_path=True,
            compromise_procedure="revoke matching KeyCredential, clear devices.api_token, re-enroll or rotate device",
            lifecycle_state_created=record.state,
            issued_at=device.created_at,
            activated_at=now_utc(),
            metadata={"source": "devices.api_token", "actor": actor},
        ))
    ssh_private_key = getattr(camera, "ssh_private_key", None) if camera else None
    ssh_public_key = getattr(camera, "ssh_public_key", None) if camera else None
    reverse_tunnel_port = getattr(camera, "reverse_tunnel_port", None) if camera else None
    if ssh_private_key:
        rows.append(_upsert_inventory(
            db,
            device_id=device.device_id,
            trust_path="device_support_tunnel_legacy_headend_private_key",
            credential_id=None,
            key_type="ssh",
            subject=f"edge:{device.device_id}",
            issuer="headend",
            owner="physical edge, generated/stored by headend compatibility path",
            private_key_location=f"cameras.ssh_private_key:{camera.id}; injected to /etc/timelapse/device_keys/id_ed25519",
            public_key_location=f"cameras.ssh_public_key:{camera.id}" if ssh_public_key else "",
            storage="Headend Camera DB + Edge filesystem",
            fingerprint=hashlib.sha256((ssh_public_key or ssh_private_key).encode()).hexdigest(),
            source_table="cameras",
            source_id=camera.id,
            lifetime="not-explicit",
            scope='["ssh:reverse-tunnel"]',
            audience=f"Headend reverse tunnel:{reverse_tunnel_port or 'unassigned-port'}",
            rotation="generate replacement tunnel identity and distribute via provisioning/update",
            revocation="remove authorized key/tunnel account mapping and rotate device key",
            status="active",
            legacy_path=True,
            compromise_procedure="quarantine device, revoke tunnel access, rotate Headend and Edge SSH identities",
            lifecycle_state_created=record.state,
            issued_at=getattr(camera, "created_at", None),
            activated_at=getattr(assignment, "assigned_at", None),
            metadata={"source": "cameras.ssh_private_key", "actor": actor, "camera_id": camera.id},
        ))
    bt_totp_secret = getattr(camera, "bt_totp_secret", None) if camera else None
    bt_totp_sid = getattr(camera, "bt_totp_sid", None) if camera else None
    if bt_totp_secret:
        rows.append(_upsert_inventory(
            db,
            device_id=device.device_id,
            trust_path="local_technician_totp_legacy",
            credential_id=None,
            key_type="totp",
            subject=f"edge:{device.device_id}",
            issuer="headend",
            owner="local service compatibility path",
            private_key_location=f"cameras.bt_totp_secret:{camera.id}; injected to /etc/timelapse/bt-config.yaml",
            public_key_location="technician authenticator seed/QR",
            storage="Headend Camera DB + Edge filesystem",
            secret_hash=hashlib.sha256(bt_totp_secret.encode()).hexdigest(),
            fingerprint=hashlib.sha256(hashlib.sha256(bt_totp_secret.encode()).hexdigest().encode()).hexdigest(),
            source_table="cameras",
            source_id=camera.id,
            lifetime="not-explicit",
            scope='["local-service:offline-compat"]',
            audience="Edge local management portal",
            rotation="issue new EdgeServiceGrant/TOTP compatibility secret and invalidate old seed",
            revocation="clear secret/disable local TOTP or push new service policy",
            status="active",
            legacy_path=True,
            compromise_procedure="disable local service, rotate TOTP seed, review service audit",
            lifecycle_state_created=record.state,
            issued_at=getattr(camera, "created_at", None),
            activated_at=getattr(assignment, "assigned_at", None),
            metadata={"source": "cameras.bt_totp_secret", "actor": actor, "camera_id": camera.id, "sid": bt_totp_sid},
        ))
    try:
        device_config = json.loads(device.device_config or "{}")
    except Exception:
        device_config = {}
    local_tls = (
        device_config.get("provisioning", {}).get("local_tls")
        or device_config.get("provisioning", {}).get("identity", {}).get("local_tls")
        or {}
    )
    local_tls_fingerprint = (
        local_tls.get("fingerprint")
        or local_tls.get("certificate_fingerprint")
        or local_tls.get("cert_sha256")
        or ""
    )
    if local_tls or local_tls_fingerprint:
        expires_at = None
        rows.append(_upsert_inventory(
            db,
            device_id=device.device_id,
            trust_path="local_tls",
            credential_id=local_tls.get("credential_id") or f"local-tls:{device.device_id}",
            key_type="mtls_device_cert",
            subject=local_tls.get("subject") or local_tls.get("hostname") or f"edge:{device.device_id}",
            issuer=local_tls.get("issuer") or "TimeLapse Pro Edge Local CA",
            owner="physical edge local service",
            private_key_location=local_tls.get("private_key_location") or "/opt/timelapse/edge/tls/local-mgmt.key",
            public_key_location=local_tls.get("certificate_location") or "/opt/timelapse/edge/tls/local-mgmt.crt",
            storage="Edge filesystem; Headend inventory metadata only",
            fingerprint=local_tls_fingerprint or hashlib.sha256(_json(local_tls).encode()).hexdigest(),
            source_table="devices.device_config",
            source_id=device.device_id,
            lifetime=local_tls.get("expires_at") or "not-visible",
            scope='["local-service:tls"]',
            audience="Edge local technician HTTPS endpoint",
            rotation="WP-2/WP-4 CSR/PKI lifecycle",
            revocation="not fully automated until CSR/PKI lifecycle",
            status=local_tls.get("status") or "active",
            legacy_path=True,
            compromise_procedure="reissue local leaf certificate/key via signed update or reflash",
            lifecycle_state_created=record.state,
            issued_at=None,
            expires_at=expires_at,
            metadata={"source": "device_config.local_tls", "actor": actor, "remaining_gap": "CSR/PKI lifecycle is WP-2/WP-4"},
        ))
    sftp_enabled = (_setting(db, "sftp_enabled", "false") or "").lower() == "true"
    sftp_password = _setting(db, "sftp_password", "")
    if sftp_enabled and site and getattr(site, "sftp_user", None):
        rows.append(_upsert_inventory(
            db,
            device_id=device.device_id,
            trust_path="site_sftp_upload",
            credential_id=f"site-sftp:{site.id}:{site.sftp_user}",
            key_type="sftp_password",
            subject=f"site:{site.id}:edge:{device.device_id}",
            issuer="site RBAC compatibility",
            owner=f"site:{site.id}",
            private_key_location="not a private key; password delivered in Edge config",
            public_key_location="/opt/timelapse/edge/ssh/known_hosts",
            storage="settings.sftp_password + sites.sftp_user + Edge config",
            secret_hash=hashlib.sha256(sftp_password.encode()).hexdigest() if sftp_password else None,
            fingerprint=hashlib.sha256(f"{site.id}:{site.sftp_user}".encode()).hexdigest(),
            source_table="sites/settings",
            source_id=str(site.id),
            lifetime="site RBAC compatibility credential",
            scope='["upload:sftp:site"]',
            audience=f"SFTP site chroot for {site.sftp_user}",
            rotation="site RBAC SFTP password/user rotation",
            revocation="disable site SFTP user or rotate site SFTP credential",
            status="active" if sftp_password else "unknown",
            legacy_path=True,
            compromise_procedure="rotate site SFTP credential, verify chroot, reconcile assigned Edge configs",
            lifecycle_state_created=record.state,
            activated_at=now_utc(),
            metadata={
                "source": "site_sftp_compatibility",
                "actor": actor,
                "site_id": site.id,
                "site_rbac_owned": True,
                "edge_lifecycle_owned": False,
            },
        ))
    return rows


def reconcile_all_devices(db: Session, *, actor: str = "wp1-reconcile") -> dict[str, Any]:
    rows = []
    for device in db.query(Device).order_by(Device.device_id).all():
        record = get_or_create_lifecycle_record(db, device, actor=actor)
        credentials = reconcile_device_credentials(db, device, actor=actor)
        rows.append({
            "device_id": device.device_id,
            "state": record.state,
            "credentials": len(credentials),
            "legacy_paths": sum(1 for item in credentials if item.legacy_path),
        })
    return {
        "devices": rows,
        "legacy_paths_remaining": sum(item["legacy_paths"] for item in rows),
    }


def legacy_credential_paths_remaining(db: Session, device_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    query = db.query(EdgeCredentialInventory).filter(
        EdgeCredentialInventory.legacy_path.is_(True),
        EdgeCredentialInventory.status != "not_present",
    )
    if device_ids:
        query = query.filter(EdgeCredentialInventory.device_id.in_(list(device_ids)))
    return [
        {
            "device_id": row.device_id,
            "trust_path": row.trust_path,
            "credential_id": row.credential_id,
            "private_key_location": row.private_key_location,
            "storage": row.storage,
            "revocation": row.revocation,
            "status": row.status,
        }
        for row in query.order_by(EdgeCredentialInventory.device_id, EdgeCredentialInventory.trust_path).all()
    ]
