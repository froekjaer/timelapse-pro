from __future__ import annotations

import os
import sys
from datetime import timedelta, timezone, datetime
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(ROOT / "headend"))
sys.path.insert(0, str(ROOT))

from database import Base, BootstrapToken, Device, EdgeCredentialInventory, EdgeLifecycleRecord, now_utc  # noqa: E402
from edge.provisioning_first_boot import (  # noqa: E402
    build_first_boot_enrollment_payload,
    generate_ssh_identity,
    generate_tls_key_and_csr,
)
from trust.provisioning import (  # noqa: E402
    ProvisioningError,
    allow_reenrollment_recovery_transition,
    build_generic_release_artifact_manifest,
    consume_bootstrap_envelope,
    complete_edge_credentialing,
    create_provisioning_envelope,
    create_reenrollment_recovery_intent,
    create_replacement_edge_assignment,
    create_signing_key,
    issue_tls_certificate_from_csr,
    legacy_edge_migration_plan,
    legacy_image_provisioning_adapter_plan,
    public_key_pem,
    register_edge_ssh_public_key,
    revoke_edge_credential,
    rotate_out_legacy_private_key_authority,
    verify_generic_release_artifact_manifest,
    verify_provisioning_envelope,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _bootstrap(db, *, token="bootstrap-once"):
    row = BootstrapToken(
        token=token,
        device_label="WP4 test Edge",
        expires_at=now_utc() + timedelta(hours=1),
        max_uses=1,
        token_type="single",
    )
    db.add(row)
    db.flush()
    return row


def _hardware(mac="04:3E:B9:E7:2E:FD"):
    return {"mac_address": mac, "board": "orangepi4pro", "serial": "wp4-test-board"}


def _envelope(db, *, device_id="TL-WP4FRESH01", hardware=None):
    key = create_signing_key()
    token = _bootstrap(db)
    evidence = hardware or _hardware()
    envelope = create_provisioning_envelope(
        private_key=key,
        device_id=device_id,
        hardware_evidence=evidence,
        bootstrap_token_id=token.id,
        bootstrap_token_hash="hash-bootstrap-once",
        image_artifact_id="edge-generic-rc1",
        hardware_target="orangepi4pro",
        assignment={"customer_id": "froekjaer", "site_id": "nordre-villavej-17c", "camera_id": "cam-1"},
    )
    return key.public_key(), envelope, evidence, token


def _ca_pair():
    ca_key = ec.generate_private_key(ec.SECP256R1())
    now = now_utc()
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.COMMON_NAME, "TimeLapse Pro WP4 Test CA"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii"),
    )


def test_generic_release_artifact_has_no_device_private_material():
    manifest = build_generic_release_artifact_manifest(
        artifact_id="edge-generic-rc1",
        hardware_target="orangepi4pro",
        rootfs_sha256="a" * 64,
        build_commit="abc123",
    )

    assert manifest["device_specific"] is False
    assert manifest["contains_operational_private_keys"] is False
    assert "device_id" not in manifest
    assert "BEGIN" not in str(manifest)
    assert "ssh_private_key" not in str(manifest)
    assert "tls_private_key" not in str(manifest)


def test_generic_image_verification_is_device_neutral():
    manifest = build_generic_release_artifact_manifest(
        artifact_id="edge-generic-rc1",
        hardware_target="orangepi4pro",
        rootfs_sha256="b" * 64,
        build_commit="abc123",
    )

    verified = verify_generic_release_artifact_manifest(
        manifest,
        expected_hardware_target="orangepi4pro",
        expected_rootfs_sha256="b" * 64,
    )

    assert verified["ok"] is True
    assert "device_id" not in verified


def test_cloned_or_replayed_envelope_is_rejected_after_bootstrap_consumption(db):
    public_key, envelope, evidence, token = _envelope(db)

    consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)
    db.flush()

    assert token.used_at is not None
    assert token.revoked is True
    with pytest.raises(ProvisioningError, match="already consumed"):
        consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)


def test_consumed_bootstrap_cannot_be_reused(db):
    public_key, envelope, evidence, _token = _envelope(db)
    consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)

    with pytest.raises(ProvisioningError, match="already consumed"):
        consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)


def test_wrong_hardware_or_device_binding_is_rejected(db):
    public_key, envelope, _evidence, _token = _envelope(db)

    with pytest.raises(ProvisioningError, match="hardware binding rejected"):
        verify_provisioning_envelope(
            envelope,
            public_key=public_key,
            actual_hardware_evidence=_hardware(mac="04:3E:B9:FF:FF:FF"),
        )


def test_revoked_envelope_fails_closed(db):
    public_key, envelope, evidence, _token = _envelope(db)
    envelope["revoked"] = True

    with pytest.raises(ProvisioningError, match="revoked"):
        verify_provisioning_envelope(envelope, public_key=public_key, actual_hardware_evidence=evidence)


def test_power_loss_after_envelope_validation_before_bootstrap_consume_can_retry(db):
    public_key, envelope, evidence, token = _envelope(db)

    payload = verify_provisioning_envelope(envelope, public_key=public_key, actual_hardware_evidence=evidence)
    assert payload["device_id"] == "TL-WP4FRESH01"
    assert token.used_at is None

    consumed = consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)

    assert consumed.status == "consumed"
    assert token.used_at is not None


def test_private_ssh_and_tls_keys_never_leave_edge(tmp_path):
    ssh = generate_ssh_identity(tmp_path / "id_ed25519")
    tls = generate_tls_key_and_csr(
        device_id="TL-WP4FRESH01",
        hostname="tl-wp4fresh01.local",
        private_key_path=tmp_path / "mgmt.key",
    )
    payload = build_first_boot_enrollment_payload(
        device_id="TL-WP4FRESH01",
        envelope_id="env-test",
        ssh_public_key=ssh["public_key"],
        tls_csr_pem=tls["csr_pem"],
        hardware_evidence=_hardware(),
    )

    assert (tmp_path / "id_ed25519").exists()
    assert (tmp_path / "mgmt.key").exists()
    assert "PRIVATE KEY" not in str(payload)
    assert payload["private_keys_included"] is False


def test_power_loss_after_key_generation_before_enrollment_can_retry(db, tmp_path):
    db.add(Device(device_id="TL-WP4FRESH01"))
    db.add(EdgeLifecycleRecord(device_id="TL-WP4FRESH01", state="bootstrap_authenticated"))
    db.flush()
    ssh = generate_ssh_identity(tmp_path / "id_ed25519")
    tls = generate_tls_key_and_csr(
        device_id="TL-WP4FRESH01",
        hostname="tl-wp4fresh01.local",
        private_key_path=tmp_path / "mgmt.key",
    )

    ssh_inventory = register_edge_ssh_public_key(db, device_id="TL-WP4FRESH01", public_key=ssh["public_key"])
    ca_cert, ca_key = _ca_pair()
    _cert_pem, tls_inventory = issue_tls_certificate_from_csr(
        db,
        device_id="TL-WP4FRESH01",
        csr_pem=tls["csr_pem"],
        ca_cert_pem=ca_cert,
        ca_key_pem=ca_key,
    )

    assert ssh_inventory.status == "active"
    assert tls_inventory.status == "active"


def test_valid_csr_receives_certificate_and_inventory(db, tmp_path):
    db.add(Device(device_id="TL-WP4FRESH01"))
    db.add(EdgeLifecycleRecord(device_id="TL-WP4FRESH01", state="credentialed"))
    db.flush()
    tls = generate_tls_key_and_csr(
        device_id="TL-WP4FRESH01",
        hostname="tl-wp4fresh01.local",
        private_key_path=tmp_path / "mgmt.key",
    )
    ca_cert, ca_key = _ca_pair()

    cert_pem, inventory = issue_tls_certificate_from_csr(
        db,
        device_id="TL-WP4FRESH01",
        csr_pem=tls["csr_pem"],
        ca_cert_pem=ca_cert,
        ca_key_pem=ca_key,
    )

    assert "BEGIN CERTIFICATE" in cert_pem
    assert inventory.trust_path == "local_tls"
    assert inventory.legacy_path is False
    assert inventory.private_key_location == "edge:/etc/timelapse/certs/mgmt.key"


def test_duplicate_csr_is_rejected(db, tmp_path):
    db.add(Device(device_id="TL-WP4FRESH01"))
    db.add(EdgeLifecycleRecord(device_id="TL-WP4FRESH01", state="credentialed"))
    db.flush()
    tls = generate_tls_key_and_csr(
        device_id="TL-WP4FRESH01",
        hostname="tl-wp4fresh01.local",
        private_key_path=tmp_path / "mgmt.key",
    )
    ca_cert, ca_key = _ca_pair()
    issue_tls_certificate_from_csr(
        db,
        device_id="TL-WP4FRESH01",
        csr_pem=tls["csr_pem"],
        ca_cert_pem=ca_cert,
        ca_key_pem=ca_key,
    )

    with pytest.raises(ProvisioningError, match="duplicate CSR"):
        issue_tls_certificate_from_csr(
            db,
            device_id="TL-WP4FRESH01",
            csr_pem=tls["csr_pem"],
            ca_cert_pem=ca_cert,
            ca_key_pem=ca_key,
        )


def test_revoked_device_cannot_reenroll_without_explicit_recovery(db):
    public_key, envelope, evidence, _token = _envelope(db, device_id="TL-REVOKED01")
    db.add(Device(device_id="TL-REVOKED01"))
    db.add(EdgeLifecycleRecord(device_id="TL-REVOKED01", state="revoked", revoked_at=now_utc()))
    db.flush()

    with pytest.raises(ProvisioningError, match="cannot re-enroll"):
        consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)


def test_revoked_device_can_receive_cert_after_explicit_recovery_transition(db, tmp_path):
    db.add(Device(device_id="TL-RECOVERYCERT01"))
    db.add(EdgeLifecycleRecord(device_id="TL-RECOVERYCERT01", state="revoked", revoked_at=now_utc()))
    db.flush()
    allow_reenrollment_recovery_transition(
        db,
        device_id="TL-RECOVERYCERT01",
        recovery_ticket="RECOVERY-789",
        actor="operator",
        reason="approved hardware recovery",
    )
    tls = generate_tls_key_and_csr(
        device_id="TL-RECOVERYCERT01",
        hostname="tl-recoverycert01.local",
        private_key_path=tmp_path / "mgmt.key",
    )
    ca_cert, ca_key = _ca_pair()

    cert_pem, inventory = issue_tls_certificate_from_csr(
        db,
        device_id="TL-RECOVERYCERT01",
        csr_pem=tls["csr_pem"],
        ca_cert_pem=ca_cert,
        ca_key_pem=ca_key,
    )

    assert "BEGIN CERTIFICATE" in cert_pem
    assert inventory.status == "active"


def test_replacement_edge_inherits_assignment_without_old_private_keys():
    replacement = create_replacement_edge_assignment(
        old_device_id="TL-OLD01",
        new_device_id="TL-NEW01",
        assignment={"customer_id": "froekjaer", "site_id": "nordre-villavej-17c", "camera_id": "cam-1"},
        recovery_ticket="RECOVERY-123",
    )

    assert replacement["inherits_logical_assignment"]["site_id"] == "nordre-villavej-17c"
    assert replacement["inherits_private_keys"] is False
    assert replacement["requires_new_edge_generated_keys"] is True


def test_revocation_and_reenrollment_recovery_are_explicit(db):
    public_key, envelope, evidence, _token = _envelope(db, device_id="TL-RECOVER01")
    consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)
    register_edge_ssh_public_key(db, device_id="TL-RECOVER01", public_key="ssh-ed25519 public")
    db.flush()

    rows = revoke_edge_credential(
        db,
        device_id="TL-RECOVER01",
        trust_path="device_support_tunnel",
        actor="test",
        reason="key compromise drill",
    )
    recovery = create_reenrollment_recovery_intent(
        device_id="TL-RECOVER01",
        recovery_ticket="RECOVERY-456",
        reason="replace compromised tunnel key",
    )

    assert [row.status for row in rows] == ["revoked"]
    assert recovery["requires_explicit_operator_approval"] is True
    assert recovery["old_private_keys_reused"] is False


def test_old_image_provisioning_path_remains_migration_compatible():
    plan = legacy_image_provisioning_adapter_plan(device_id="TL-LEGACY01", image_artifact_id="flashable-legacy")

    assert plan["compatible"] is True
    assert plan["mode"] == "legacy-per-device-image-adapter"
    assert plan["target_mode"] == "generic-image-plus-envelope"
    assert plan["may_create_new_credentials"] is False


def test_legacy_edge_migration_preserves_capture_upload_without_new_legacy_credentials():
    plan = legacy_edge_migration_plan(device_id="TL-LEGACY01")

    assert plan["legacy_paths_read_only"] is True
    assert plan["may_create_new_credentials_via_legacy_path"] is False
    assert "capture:write" in plan["scope_preserved"]


def test_existing_image_tls_and_headend_ssh_rotate_out_without_parallel_authority(db):
    db.add_all([
        EdgeCredentialInventory(
            device_id="TL-LEGACY01",
            trust_path="device_support_tunnel_legacy_headend_private_key",
            credential_id="legacy-ssh",
            key_type="ssh",
            status="active",
            legacy_path=True,
        ),
        EdgeCredentialInventory(
            device_id="TL-LEGACY01",
            trust_path="local_tls",
            credential_id="legacy-tls",
            key_type="mtls_device_cert",
            status="active",
            legacy_path=True,
        ),
        EdgeCredentialInventory(
            device_id="TL-LEGACY01",
            trust_path="device_support_tunnel",
            credential_id="ssh-new",
            key_type="ssh",
            status="active",
            legacy_path=False,
        ),
    ])
    db.flush()

    rotated = rotate_out_legacy_private_key_authority(
        db,
        device_id="TL-LEGACY01",
        actor="test",
        reason="WP-4 successor active",
    )

    assert {row.credential_id for row in rotated} == {"legacy-ssh", "legacy-tls"}
    assert {row.status for row in rotated} == {"rotated"}
    assert db.query(EdgeCredentialInventory).filter_by(
        device_id="TL-LEGACY01",
        legacy_path=True,
        status="active",
    ).count() == 0


def test_fresh_edge_integration_contract_from_generic_image_to_reboot_auth(db, tmp_path):
    manifest = build_generic_release_artifact_manifest(
        artifact_id="edge-generic-rc1",
        hardware_target="orangepi4pro",
        rootfs_sha256="c" * 64,
        build_commit="abc123",
    )
    verify_generic_release_artifact_manifest(
        manifest,
        expected_hardware_target="orangepi4pro",
        expected_rootfs_sha256="c" * 64,
    )
    public_key, envelope, evidence, _token = _envelope(db)
    verify_provisioning_envelope(envelope, public_key=public_key, actual_hardware_evidence=evidence)
    payload = consume_bootstrap_envelope(db, envelope, public_key=public_key, actual_hardware_evidence=evidence)
    ssh = generate_ssh_identity(tmp_path / "id_ed25519")
    ssh_inventory = register_edge_ssh_public_key(db, device_id="TL-WP4FRESH01", public_key=ssh["public_key"])
    tls = generate_tls_key_and_csr(
        device_id="TL-WP4FRESH01",
        hostname="tl-wp4fresh01.local",
        private_key_path=tmp_path / "mgmt.key",
    )
    ca_cert, ca_key = _ca_pair()
    _cert_pem, tls_inventory = issue_tls_certificate_from_csr(
        db,
        device_id="TL-WP4FRESH01",
        csr_pem=tls["csr_pem"],
        ca_cert_pem=ca_cert,
        ca_key_pem=ca_key,
    )
    lifecycle = complete_edge_credentialing(db, device_id="TL-WP4FRESH01")

    assert payload.status == "consumed"
    assert lifecycle.state == "credentialed"
    assert db.query(Device).filter_by(device_id="TL-WP4FRESH01").first().site_id == "nordre-villavej-17c"
    assert ssh_inventory.trust_path == "device_support_tunnel"
    assert tls_inventory.trust_path == "local_tls"
    assert db.query(EdgeCredentialInventory).filter_by(device_id="TL-WP4FRESH01").count() >= 3
    after_reboot = register_edge_ssh_public_key(db, device_id="TL-WP4FRESH01", public_key=ssh["public_key"])
    assert after_reboot.id == ssh_inventory.id


def test_signed_envelope_can_be_verified_from_public_key_pem(db):
    key = create_signing_key()
    token = _bootstrap(db)
    evidence = _hardware()
    envelope = create_provisioning_envelope(
        private_key=key,
        device_id="TL-PUBLICPEM01",
        hardware_evidence=evidence,
        bootstrap_token_id=token.id,
        bootstrap_token_hash="hash-bootstrap-once",
        image_artifact_id="edge-generic-rc1",
        hardware_target="orangepi4pro",
    )
    loaded = serialization.load_pem_public_key(public_key_pem(key).encode("ascii"))

    assert verify_provisioning_envelope(envelope, public_key=loaded, actual_hardware_evidence=evidence)["device_id"] == "TL-PUBLICPEM01"


def test_expired_envelope_fails_closed(db):
    key = create_signing_key()
    token = _bootstrap(db)
    evidence = _hardware()
    envelope = create_provisioning_envelope(
        private_key=key,
        device_id="TL-EXPIRED01",
        hardware_evidence=evidence,
        bootstrap_token_id=token.id,
        bootstrap_token_hash="hash-bootstrap-once",
        image_artifact_id="edge-generic-rc1",
        hardware_target="orangepi4pro",
        ttl=timedelta(seconds=1),
    )

    with pytest.raises(ProvisioningError, match="expired"):
        verify_provisioning_envelope(
            envelope,
            public_key=key.public_key(),
            actual_hardware_evidence=evidence,
            now=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
