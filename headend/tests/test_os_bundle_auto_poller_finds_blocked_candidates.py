"""Regression test found live in production 2026-09-03 (HANDOVER_LOG): no code
path anywhere ever sets a os_security/os_updates PendingUpdate to status
"pending" — cmdb.py's inventory-sync and the lab-catalog import both create
them directly as "blocked" (deliberate: "observation, not deployable work").
_os_bundle_auto_build_pending()'s filter only matched "pending", so the
10-minute auto-poller thread ran continuously for weeks without ever finding
a single candidate to build — a silent no-op, not a crash, so nothing ever
surfaced the bug.

Verified live: the last os_security/os_updates PendingUpdate ever created was
2026-08-12; the automatic CMDB-catalog-refresh loop that should feed this
poller (see test_os_catalog_refresh_pending_devices.py) had also never run in
the actually-deployed codebase — only on an unmerged branch.
"""
import main
from database import Base, PendingUpdate, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-BLOCKED-POLLER"


def _clean(session):
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.commit()


def test_auto_poller_finds_blocked_os_candidates_with_plan(monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    session.add(PendingUpdate(
        update_type="os_security",
        status="blocked",
        scope="device",
        scope_id=DEVICE_ID,
        version="1.0",
        description="3 sikkerhedsopdatering(er) klar via Headend lab-katalog.\nPlan: /tmp/fake-plan.md",
    ))
    session.commit()
    session.close()

    captured = {}

    def fake_build(db, update, device_id, system_user):
        captured["called"] = True

    monkeypatch.setattr(main, "_auto_build_and_bind_os_bundle", fake_build)
    monkeypatch.setattr(main, "_find_artifact_for_update", lambda db, u: None)

    try:
        main._os_bundle_auto_build_pending()
        assert captured.get("called"), (
            "a blocked os_security row with a Plan reference was not picked up — "
            "the poller's status filter regressed back to pending-only"
        )
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_auto_poller_skips_blocked_os_candidate_without_plan(monkeypatch):
    """The plan_path requirement is a deliberate governance gate
    (OS_UPDATE_GOVERNANCE_CLOSURE_2026-08.md) — must survive alongside the
    status-filter fix, not be accidentally loosened at the same time."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    session.add(PendingUpdate(
        update_type="os_security",
        status="blocked",
        scope="device",
        scope_id=DEVICE_ID,
        version="1.0",
        description="Edge TL-X: 3 sikkerhedsopdateringer tilgængelige via apt. CMDB observation.",
    ))
    session.commit()
    session.close()

    captured = {}
    monkeypatch.setattr(main, "_auto_build_and_bind_os_bundle", lambda *a: captured.setdefault("called", True))
    monkeypatch.setattr(main, "_find_artifact_for_update", lambda db, u: None)

    try:
        main._os_bundle_auto_build_pending()
        assert "called" not in captured
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
