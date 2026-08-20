"""Regression test for U-12 (MASTER_REVIEW_CLOSURE_2026-08-15.md): the
auto OS-bundle-builder picked the FIRST super_admin row in the database and
used its username as the artifact manifest's "created.by" field — falsely
attributing an automated, unattended build to a real human account. If that
super_admin later reviewed the audit trail, it would look like they had
personally approved/signed a bundle they never saw.

Fixed by using a transient, non-persisted system principal
(User(username="system:auto-os-bundle-builder", role="system")) — the same
pattern _auto_approve_update_for_target() already uses correctly for policy
auto-approvals (requested_by="system:auto-policy").
"""
import main
from database import Base, PendingUpdate, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-U12"


def _clean(session):
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.commit()


def test_os_bundle_auto_poller_uses_system_principal_not_real_super_admin(monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    session.add(PendingUpdate(
        update_type="os_security",
        status="pending",
        scope="device",
        scope_id=DEVICE_ID,
        version="1.0",
        description="Plan: /tmp/fake-plan.md",
    ))
    session.commit()
    session.close()

    captured = {}

    def fake_build(db, update, device_id, system_user):
        captured["system_user"] = system_user

    monkeypatch.setattr(main, "_auto_build_and_bind_os_bundle", fake_build)
    monkeypatch.setattr(main, "_find_artifact_for_update", lambda db, u: None)

    try:
        main._os_bundle_auto_build_pending()

        assert "system_user" in captured, "auto-build was never invoked — test setup didn't reach the build path"
        system_user = captured["system_user"]
        assert system_user.username == "system:auto-os-bundle-builder"
        assert system_user.role == "system"
        # Must not be a real, persisted account (no primary key assigned).
        assert system_user.id is None
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
