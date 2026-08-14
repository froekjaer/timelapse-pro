import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(ROOT / "headend"))

from database import Base, Camera, Device, DeviceAssignment, EdgeCredentialInventory, KeyCredential  # noqa: E402
from services.edge_lifecycle import (  # noqa: E402
    LifecycleTransitionError,
    advance_lifecycle_to,
    get_or_create_lifecycle_record,
    hardware_fingerprint,
    legacy_credential_paths_remaining,
    reconcile_device_credentials,
    transition_lifecycle,
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


def test_canonical_lifecycle_rejects_forbidden_transition(db):
    device = Device(device_id="TL-ABCDEF123456")
    db.add(device)
    db.flush()

    record = get_or_create_lifecycle_record(db, device, actor="test")
    transition_lifecycle(db, record, "prepared", actor="test", reason="prepare")

    with pytest.raises(LifecycleTransitionError, match="prepared -> active"):
        transition_lifecycle(db, record, "active", actor="test", reason="skip commissioning")


def test_legacy_endpoint_can_advance_along_canonical_path(db):
    device = Device(device_id="TL-111111111111")
    db.add(device)
    db.flush()

    record = get_or_create_lifecycle_record(db, device, actor="test")
    transitions = advance_lifecycle_to(db, record, "credentialed", actor="test", reason="compat enroll")

    assert record.state == "credentialed"
    assert [item.to_state for item in transitions] == [
        "prepared",
        "media_written",
        "bootstrap_pending",
        "bootstrap_authenticated",
        "hardware_verified",
        "enrolled",
        "credentialed",
    ]


def test_duplicate_hardware_identity_is_rejected(db):
    evidence = {"mac_address": "04:3E:B9:E7:2E:FD", "board": "orangepi4pro"}
    first = Device(device_id="TL-043EB9E72EFD")
    second = Device(device_id="TL-OTHERDEVICE01")
    db.add_all([first, second])
    db.flush()

    first_record = get_or_create_lifecycle_record(db, first, actor="test")
    transition_lifecycle(
        db,
        first_record,
        "prepared",
        actor="test",
        reason="prepare first",
        hardware_evidence=evidence,
    )
    assert first_record.hardware_fingerprint == hardware_fingerprint(first.device_id, evidence)

    second_record = get_or_create_lifecycle_record(db, second, actor="test")
    with pytest.raises(LifecycleTransitionError, match="Duplicate Edge hardware identity"):
        transition_lifecycle(
            db,
            second_record,
            "prepared",
            actor="test",
            reason="prepare duplicate",
            hardware_evidence=evidence,
        )


def test_credential_inventory_marks_legacy_paths(db):
    device = Device(device_id="TL-CREDENTIALS01", api_token="tk-legacy")
    camera = Camera(
        id="camera-credentials-01",
        customer_id="customer-1",
        site_id="site-1",
        camera_name="Nordre Villavej test",
        ssh_private_key="PRIVATE",
        ssh_public_key="ssh-ed25519 pub",
        reverse_tunnel_port=2201,
        bt_totp_secret="ABCDEF",
        bt_totp_sid="edge-TL-CREDENTIALS01",
    )
    assignment = DeviceAssignment(device_id=device.device_id, camera_id=camera.id)
    managed = KeyCredential(
        credential_id="TL-KEY-TEST",
        entity_type="edge",
        entity_id=device.device_id,
        key_type="api",
        status="active",
        secret_hash="hash",
        metadata_json='{"migrated_from_legacy_device_api_token":true}',
    )
    db.add_all([device, camera, assignment, managed])
    db.flush()

    rows = reconcile_device_credentials(db, device, actor="test")
    legacy_paths = {row.trust_path for row in rows if row.legacy_path}

    assert "device_api_legacy" in legacy_paths
    assert "device_support_tunnel_legacy_headend_private_key" in legacy_paths
    assert "local_technician_totp_legacy" in legacy_paths
    assert db.query(EdgeCredentialInventory).filter_by(device_id=device.device_id).count() >= 4
    assert {item["trust_path"] for item in legacy_credential_paths_remaining(db)} >= legacy_paths


def test_device_auth_fails_closed_for_revoked_lifecycle_state():
    source = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
    verify_block = source.split("async def _verify_device_token(", 1)[1].split("async def _verify_payload_device_token(", 1)[0]

    assert "EdgeLifecycleRecord" in verify_block
    assert '{"quarantined", "revoked", "retired"}' in verify_block
    assert "Edge lifecycle state afviser API-adgang" in verify_block
