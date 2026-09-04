"""
Behavioral tests for the Python dependency ("venv_packages") update-governance
chain, built 2026-09-04 mirroring the OS-package chain fixed the same day:

    Edge venv_packages -> PyPI reconciliation -> blocked dependency_updates
    candidate with Plan -> auto-poller builds+signs offline wheel bundle ->
    admin approves -> Edge installs offline via pip --no-index.

See test_fetch_python_bundle.py for the fetch/wheel-selection layer, and
tests/test_edge_venv_packages_reporting.py for why venv_packages needed fixing
before this chain had anything real to reconcile against.
"""
import json

import main
from database import Base, DeviceInventory, PendingUpdate, SessionLocal, UpdateTarget, engine


class _FakeUser:
    def __init__(self, username="tester", role="admin"):
        self.username = username
        self.role = role


DEVICE_ID = "TL-TESTDEVICE-PYDEPS"


def _clean(session):
    session.query(UpdateTarget).filter(
        UpdateTarget.pending_update_id.in_(
            session.query(PendingUpdate.id).filter_by(scope_id=DEVICE_ID)
        )
    ).delete(synchronize_session=False)
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.query(DeviceInventory).filter_by(device_id=DEVICE_ID).delete()
    session.commit()


# ── _reconcile_python_packages_from_pypi() ──────────────────────────────────

def test_reconcile_finds_outdated_package(monkeypatch):
    def fake_urlopen(req, timeout=15):
        class _Resp:
            def read(self_inner):
                return json.dumps({"info": {"version": "2.31.0"}}).encode()
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    decisions = main._reconcile_python_packages_from_pypi({"requests": "2.28.0"})
    assert decisions["dependency_updates"]["package_count"] == 1
    pkg = decisions["dependency_updates"]["packages"][0]
    assert pkg == {
        "name": "requests",
        "installed_version": "2.28.0",
        "available_version": "2.31.0",
        "source_repo": "pypi",
    }


def test_reconcile_skips_package_already_current(monkeypatch):
    def fake_urlopen(req, timeout=15):
        class _Resp:
            def read(self_inner):
                return json.dumps({"info": {"version": "2.28.0"}}).encode()
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert main._reconcile_python_packages_from_pypi({"requests": "2.28.0"}) == {}


def test_reconcile_tolerates_lookup_failure(monkeypatch):
    def raising_urlopen(req, timeout=15):
        raise OSError("network unreachable")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", raising_urlopen)

    # Must not raise — one package's lookup failure shouldn't kill the whole reconcile.
    assert main._reconcile_python_packages_from_pypi({"requests": "2.28.0"}) == {}


# ── _upsert_blocked_python_updates_from_plan() ──────────────────────────────

def test_upsert_creates_blocked_candidate_with_resolution_reason():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        decisions = {
            "dependency_updates": {
                "package_count": 1,
                "severity": "medium",
                "packages": [{"name": "requests", "installed_version": "2.28.0", "available_version": "2.31.0", "source_repo": "pypi"}],
            }
        }
        changes = main._upsert_blocked_python_updates_from_plan(
            session, DEVICE_ID, "lab", decisions, "test-source", "/tmp/fake-python-plan.json",
        )
        session.commit()
        assert changes[0]["status"] == "created"
        update = session.query(PendingUpdate).filter_by(id=changes[0]["id"]).first()
        assert update.update_type == "dependency_updates"
        assert update.status == "blocked"
        assert update.resolution_reason == "Awaiting Headend-signed offline Python wheel bundle."
        assert "Plan: /tmp/fake-python-plan.json" in update.description
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_upsert_resets_stale_target_on_already_blocked_row():
    """Same regression class as the OS-side fix: resolution_reason and target
    reset must apply even when the row is ALREADY blocked, not only on the
    pending/approved -> blocked transition (2026-09-03 finding)."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        update = PendingUpdate(
            update_type="dependency_updates", status="blocked", scope="device",
            scope_id=DEVICE_ID, version="1 pakker",
            description="Plan: /tmp/old-plan.json",
        )
        session.add(update)
        session.commit()
        target = UpdateTarget(pending_update_id=update.id, device_id=DEVICE_ID, status="queued")
        session.add(target)
        session.commit()

        decisions = {
            "dependency_updates": {
                "package_count": 1, "severity": "medium",
                "packages": [{"name": "requests", "installed_version": "2.28.0", "available_version": "2.31.0", "source_repo": "pypi"}],
            }
        }
        main._upsert_blocked_python_updates_from_plan(
            session, DEVICE_ID, "lab", decisions, "test-source", "/tmp/new-plan.json",
        )
        session.commit()

        session.refresh(update)
        session.refresh(target)
        assert update.resolution_reason == "Awaiting Headend-signed offline Python wheel bundle."
        assert target.status == "failed"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


# ── _packages_from_python_plan() ────────────────────────────────────────────

def test_packages_from_python_plan_reads_dependency_updates_key(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "decisions": {
            "dependency_updates": {
                "packages": [{"name": "requests", "available_version": "2.31.0"}],
            }
        }
    }))
    packages = main._packages_from_python_plan(str(plan_path))
    assert packages == [{"name": "requests", "available_version": "2.31.0"}]


def test_packages_from_python_plan_missing_file_returns_empty_list(tmp_path):
    assert main._packages_from_python_plan(str(tmp_path / "missing.json")) == []


# ── _python_catalog_refresh_pending_devices() ───────────────────────────────

def test_catalog_refresh_only_processes_devices_with_venv_packages(monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="lab", venv_packages=json.dumps({"requests": "2.28.0"})))
        session.commit()
        session.close()

        monkeypatch.setattr(
            main, "_reconcile_python_packages_from_pypi",
            lambda installed: {"dependency_updates": {"package_count": 1, "severity": "medium",
                                                        "packages": [{"name": "requests", "installed_version": "2.28.0", "available_version": "2.31.0", "source_repo": "pypi"}]}},
        )
        monkeypatch.setattr(main, "_write_update_json", lambda folder, filename, payload: "/tmp/fake-plan.json")

        main._python_catalog_refresh_pending_devices()

        verify = SessionLocal()
        try:
            update = verify.query(PendingUpdate).filter_by(scope_id=DEVICE_ID, update_type="dependency_updates").first()
            assert update is not None
            assert update.status == "blocked"
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


# ── _os_bundle_auto_build_pending() dispatch ────────────────────────────────

def test_auto_poller_dispatches_dependency_updates_to_python_builder(monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    session.add(PendingUpdate(
        update_type="dependency_updates", status="blocked", scope="device",
        scope_id=DEVICE_ID, version="1 pakker",
        description="Plan: /tmp/fake-plan.json",
    ))
    session.commit()
    session.close()

    captured = {}
    monkeypatch.setattr(main, "_auto_build_and_bind_python_bundle", lambda db, update, device_id, user: captured.setdefault("called", update.update_type))
    monkeypatch.setattr(main, "_auto_build_and_bind_os_bundle", lambda *a: captured.setdefault("wrong_builder", True))
    monkeypatch.setattr(main, "_find_artifact_for_update", lambda db, u: None)

    try:
        main._os_bundle_auto_build_pending()
        assert captured.get("called") == "dependency_updates"
        assert "wrong_builder" not in captured
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
