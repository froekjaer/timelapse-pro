"""approve_update() can correct a mistaken approval by re-approving.

Found 2026-09-08, live: Edge 2's os_security update (#273) was approved to
the wrong environment (see test_approve_environment_derivation.py), leaving
it stuck at status="approved" with zero authorized targets. There was no
way to fix this short of a fresh PendingUpdate row — reject_update() only
accepts status="pending", and force_rollback() just moves the stalemate to
"rollback_requested" (Edge, never an authorized target, would never see it
either). approve_update() already fully re-derives environment/scope/
targets each call, so allowing it to run again from "approved" is a safe,
minimal fix — an admin correcting a mistake before anything's actually
moved should not need a workaround.
"""
import json

import pytest
from fastapi import HTTPException

import main
from database import (
    Base, ChangeTicket, DeviceInventory, PendingUpdate, SessionLocal,
    UpdateArtifact, UpdateTarget, engine,
)


DEVICE_ID = "TL-TESTDEVICE-REAPPROVE"


class _FakeUser:
    def __init__(self, username="admin", role="admin", customer_id=None):
        self.username = username
        self.role = role
        self.customer_id = customer_id


def _clean(session):
    session.query(UpdateTarget).filter(UpdateTarget.device_id == DEVICE_ID).delete()
    session.query(ChangeTicket).filter(ChangeTicket.pending_update_id.in_(
        session.query(PendingUpdate.id).filter_by(scope_id=DEVICE_ID)
    )).delete(synchronize_session=False)
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.query(UpdateArtifact).filter_by(artifact_id="art-reapprove-test").delete()
    session.query(DeviceInventory).filter_by(device_id=DEVICE_ID).delete()
    session.commit()


def _make_artifact(session):
    artifact = UpdateArtifact(
        artifact_id="art-reapprove-test",
        artifact_type="app",
        version="reapprove-v1",
        source_commit="deadbeef",
        source_ref="ci-run-1",
        sha256="a" * 64,
        signature="-----BEGIN PGP SIGNATURE-----\nci-test-signature\n-----END PGP SIGNATURE-----",
        signed_by="ci-signer",
        manifest_json=json.dumps({
            "schema": "timelapse.update_artifact.v1",
            "source": {"commit": "deadbeef", "dirty_worktree": False},
        }),
    )
    session.add(artifact)
    session.commit()
    return artifact


def _make_update(session, status="approved", environment="test"):
    update = PendingUpdate(
        update_type="app_updates",
        version="reapprove-v1",
        description="test",
        severity="low",
        scope="device",
        scope_id=DEVICE_ID,
        status=status,
        environment=environment,
    )
    session.add(update)
    session.commit()
    return update


def test_reapproving_an_approved_update_succeeds_and_corrects_environment():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production"))
        _make_artifact(session)
        update = _make_update(session, status="approved", environment="test")

        from main import ApprovePayload
        result = main.approve_update(
            update.id,
            ApprovePayload(environment="test", scope="device", scope_id=DEVICE_ID),
            _FakeUser(),
            session,
        )
        assert result["ok"] is True

        session.refresh(update)
        assert update.status == "approved"
        assert update.environment == "production"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_reapproving_is_blocked_while_a_target_is_mid_install():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production"))
        _make_artifact(session)
        update = _make_update(session, status="approved", environment="test")
        session.add(UpdateTarget(
            pending_update_id=update.id, device_id=DEVICE_ID, status="downloading",
        ))
        session.commit()

        from main import ApprovePayload
        with pytest.raises(HTTPException) as exc_info:
            main.approve_update(
                update.id,
                ApprovePayload(environment="production", scope="device", scope_id=DEVICE_ID),
                _FakeUser(),
                session,
            )
        assert exc_info.value.status_code == 409
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_reapproving_a_pending_status_update_still_works_unchanged():
    # Guard the pre-existing behavior wasn't disturbed for the normal,
    # first-time approval path.
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production"))
        _make_artifact(session)
        update = _make_update(session, status="pending", environment="production")

        from main import ApprovePayload
        result = main.approve_update(
            update.id,
            ApprovePayload(environment="production", scope="device", scope_id=DEVICE_ID),
            _FakeUser(),
            session,
        )
        assert result["ok"] is True
        session.refresh(update)
        assert update.status == "approved"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_cannot_approve_a_deployed_update():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production"))
        _make_artifact(session)
        update = _make_update(session, status="deployed", environment="production")

        from main import ApprovePayload
        with pytest.raises(HTTPException) as exc_info:
            main.approve_update(
                update.id,
                ApprovePayload(environment="production", scope="device", scope_id=DEVICE_ID),
                _FakeUser(),
                session,
            )
        assert exc_info.value.status_code == 400
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
