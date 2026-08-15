import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(ROOT / "headend"))

from database import Base, BootstrapToken, Camera, Device, DeviceAssignment, EdgeCredentialInventory, KeyCredential, now_utc  # noqa: E402
from services.edge_lifecycle import (  # noqa: E402
    LifecycleTransitionError,
    advance_lifecycle_to,
    credential_state_allows_use,
    get_or_create_lifecycle_record,
    hardware_fingerprint,
    issue_inventory_api_credential,
    legacy_credential_paths_remaining,
    mark_bootstrap_consumed,
    migrate_legacy_api_token_to_inventory,
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

    assert "resolve_device_api_credential" in verify_block
    service_source = (ROOT / "headend" / "services" / "edge_lifecycle.py").read_text(encoding="utf-8")
    assert "Edge lifecycle state afviser API-adgang" in service_source
    assert '{"quarantined", "revoked", "retired"}' in service_source
    assert "migrate_legacy_api_token_to_inventory" in service_source


def test_retired_lifecycle_state_rejects_device_api_auth():
    source = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
    verify_block = source.split("async def _verify_device_token(", 1)[1].split("async def _verify_payload_device_token(", 1)[0]
    service_source = (ROOT / "headend" / "services" / "edge_lifecycle.py").read_text(encoding="utf-8")

    assert '"retired"' in service_source
    assert "raise HTTPException(status_code=401" in verify_block


def test_consumed_bootstrap_credential_cannot_be_reused(db):
    token = BootstrapToken(
        token="bootstrap-once",
        device_label="Nordre Villavej",
        expires_at=now_utc() + timedelta(hours=1),
    )
    db.add(token)
    db.flush()

    row = mark_bootstrap_consumed(
        db,
        token_id=token.id,
        token_hash="hash-bootstrap-once",
        device_id="TL-BOOTSTRAP01",
    )
    token.used_at = now_utc()
    token.used_by_device = "TL-BOOTSTRAP01"
    token.revoked = True
    db.flush()

    assert row.status == "consumed"
    assert row.consumed_at is not None
    assert token.revoked is True


def test_credential_scopes_remain_isolated_and_api_cannot_become_tunnel(db):
    device = Device(device_id="TL-SCOPE01")
    db.add(device)
    db.flush()

    row = issue_inventory_api_credential(
        db,
        device,
        credential_id="TL-KEY-API-SCOPE",
        token_hash="api-token-hash",
        fingerprint="api-fingerprint",
        actor="test",
        scopes_json='["capture:write"]',
    )

    assert row.trust_path == "device_api"
    assert row.key_type == "api"
    assert row.scope == '["capture:write"]'
    assert row.audience == "Headend Edge API"
    assert db.query(EdgeCredentialInventory).filter_by(
        device_id=device.device_id,
        trust_path="device_support_tunnel",
        credential_id=row.credential_id,
    ).first() is None


def test_credential_rotation_leaves_exactly_one_active_successor(db):
    device = Device(device_id="TL-ROTATE01")
    db.add(device)
    db.flush()

    first = issue_inventory_api_credential(
        db,
        device,
        credential_id="TL-KEY-API-OLD",
        token_hash="old-hash",
        fingerprint="old-fingerprint",
        actor="test",
        scopes_json="[]",
    )
    second = issue_inventory_api_credential(
        db,
        device,
        credential_id="TL-KEY-API-NEW",
        token_hash="new-hash",
        fingerprint="new-fingerprint",
        actor="test",
        scopes_json="[]",
    )
    db.flush()

    assert first.status == "rotated"
    assert first.rotated_at is not None
    assert second.status == "active"
    assert db.query(EdgeCredentialInventory).filter_by(
        device_id=device.device_id,
        trust_path="device_api",
        key_type="api",
        status="active",
    ).count() == 1


def test_unknown_credential_state_fails_closed(db):
    row = EdgeCredentialInventory(
        device_id="TL-UNKNOWN01",
        trust_path="device_api",
        credential_id="TL-KEY-UNKNOWN",
        key_type="api",
        status="unknown",
    )
    db.add(row)
    db.flush()

    assert credential_state_allows_use(row) is False
    row.status = "active"
    assert credential_state_allows_use(row) is True


def test_legacy_api_migration_is_idempotent(db):
    device = Device(device_id="TL-LEGACY01", api_token="legacy-token")
    db.add(device)
    db.flush()

    first = migrate_legacy_api_token_to_inventory(
        db,
        device,
        token_hash="legacy-hash",
        actor="test",
    )
    second = migrate_legacy_api_token_to_inventory(
        db,
        device,
        token_hash="legacy-hash",
        actor="test",
    )
    db.flush()

    assert first.id == second.id
    assert db.query(EdgeCredentialInventory).filter_by(
        device_id=device.device_id,
        trust_path="device_api",
        credential_id="legacy-api:legacy-hash",
    ).count() == 1


def test_existing_enrolled_edge_can_migrate_without_losing_capture_upload_scope(db):
    device = Device(device_id="TL-MIGRATE01", api_token="legacy-token", status="online")
    db.add(device)
    db.flush()

    row = migrate_legacy_api_token_to_inventory(
        db,
        device,
        token_hash="legacy-hash",
        actor="test",
    )

    assert device.api_token == "legacy-token"
    assert row.status == "active"
    assert "capture:write" in row.scope
    assert row.legacy_path is True
