"""stop_update_approval() — a dedicated way to stop an approved update
without immediately deciding on new approve-dialog settings.

Peter, 2026-09-08: asked for a "stop" action after #273 got stuck approved
to the wrong environment, while noting the real fix is preventing the
mistake in the first place (see test_approve_environment_derivation.py and
_resolve_approval_environment()). approve_update() already allows
re-approving an "approved" update to correct a mistake in one step (see
test_reapprove_from_approved.py) — this is the complementary action for
when an admin wants to halt and investigate first, without committing to
new settings immediately. Moves status back to "blocked", the same state a
fresh, not-yet-approved candidate sits in, and resets any non-in-flight
targets via reset_stale_targets_on_block() (the same cascade every other
"parent went back to blocked" path in this codebase already uses).
"""
import pytest
from fastapi import HTTPException

import main
from database import Base, PendingUpdate, SessionLocal, UpdateTarget, engine


DEVICE_ID = "TL-TESTDEVICE-STOPAPPROVAL"


class _FakeUser:
    def __init__(self, username="admin", role="admin"):
        self.username = username
        self.role = role


def _clean(session):
    session.query(UpdateTarget).filter(UpdateTarget.device_id == DEVICE_ID).delete()
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.commit()


def _make_update(session, status="approved"):
    update = PendingUpdate(
        update_type="app_updates",
        version="stop-v1",
        description="test",
        severity="low",
        scope="device",
        scope_id=DEVICE_ID,
        status=status,
        environment="test",
    )
    session.add(update)
    session.commit()
    return update


def test_stop_moves_an_approved_update_back_to_blocked():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        update = _make_update(session, status="approved")
        session.add(UpdateTarget(pending_update_id=update.id, device_id=DEVICE_ID, status="queued"))
        session.commit()

        result = main.stop_update_approval(update.id, _FakeUser(), session)
        assert result["ok"] is True

        session.refresh(update)
        assert update.status == "blocked"
        assert "stoppet" in (update.resolution_reason or "").lower()

        target = session.query(UpdateTarget).filter_by(pending_update_id=update.id).first()
        assert target.status == "failed"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_stop_is_blocked_while_a_target_is_mid_install():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        update = _make_update(session, status="approved")
        session.add(UpdateTarget(pending_update_id=update.id, device_id=DEVICE_ID, status="installing"))
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            main.stop_update_approval(update.id, _FakeUser(), session)
        assert exc_info.value.status_code == 409

        session.refresh(update)
        assert update.status == "approved"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_stop_rejects_non_approved_status():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        update = _make_update(session, status="pending")

        with pytest.raises(HTTPException) as exc_info:
            main.stop_update_approval(update.id, _FakeUser(), session)
        assert exc_info.value.status_code == 400
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_stop_404s_for_unknown_update():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    with pytest.raises(HTTPException) as exc_info:
        main.stop_update_approval(999999999, _FakeUser(), session)
    assert exc_info.value.status_code == 404
