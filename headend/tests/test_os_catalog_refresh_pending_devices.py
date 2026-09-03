"""_os_catalog_refresh_pending_devices() — the periodic CMDB->OS-catalog step
that feeds _os_bundle_auto_build_pending() its Plan-evidence.

Found missing entirely from the deployed codebase 2026-09-03 (HANDOVER_LOG):
the only version of this loop ever written lived on an unmerged branch
(codex/os-catalog-refresh, commit fe5fe6c7), so the daily CMDB->catalog->plan
refresh that used to run (dozens of "deployed" os_security/os_updates rows
through 2026-08-12, source "headend-scheduled-cmdb-refresh") had never
actually executed in production main — it only ever ran manually via the
"Refresh fra CMDB/Mac-builder" UI button, or from that stale branch.
"""
import main
from database import Base, Device, DeviceInventory, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-CATALOG-REFRESH"
NON_APT_DEVICE_ID = "TL-TESTDEVICE-CATALOG-REFRESH-MACOS"


def _clean(session):
    session.query(DeviceInventory).filter(
        DeviceInventory.device_id.in_([DEVICE_ID, NON_APT_DEVICE_ID])
    ).delete(synchronize_session=False)
    session.query(Device).filter(
        Device.device_id.in_([DEVICE_ID, NON_APT_DEVICE_ID])
    ).delete(synchronize_session=False)
    session.commit()


def test_refresh_reconciles_only_apt_devices_with_system_principal(monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    session.add(Device(device_id=DEVICE_ID, status="online"))
    session.add(DeviceInventory(
        device_id=DEVICE_ID,
        package_manager="apt/dpkg",
        os_packages='{"nginx": "1.24.0"}',
        environment="lab",
    ))
    session.add(Device(device_id=NON_APT_DEVICE_ID, status="online"))
    session.add(DeviceInventory(
        device_id=NON_APT_DEVICE_ID,
        package_manager="homebrew",
        os_packages='{"ollama": "0.1.0"}',
        environment="lab",
    ))
    session.commit()
    session.close()

    calls = []

    def fake_generate(*, installed, device_id, architecture, image):
        calls.append(("generate", device_id))
        return {"apt_list_text": "fake-list"}

    def fake_import(payload, current_user, db):
        calls.append(("import", payload.device_id, current_user.username, current_user.role))
        return {"ok": True}

    monkeypatch.setattr(main, "_generate_os_update_catalog_candidates", fake_generate)
    monkeypatch.setattr(main, "import_os_catalog_from_lab_apt_list", fake_import)

    try:
        main._os_catalog_refresh_pending_devices()

        device_ids_processed = {c[1] for c in calls if c[0] == "generate"}
        assert device_ids_processed == {DEVICE_ID}, (
            "should only reconcile apt-based devices, not homebrew/macOS ones"
        )
        import_call = next(c for c in calls if c[0] == "import")
        assert import_call[1] == DEVICE_ID
        assert import_call[2] == "system:os-catalog-refresh"
        assert import_call[3] == "system"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_refresh_continues_past_a_failing_device(monkeypatch):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    session.add(Device(device_id=DEVICE_ID, status="online"))
    session.add(DeviceInventory(
        device_id=DEVICE_ID,
        package_manager="apt/dpkg",
        os_packages='{"nginx": "1.24.0"}',
        environment="lab",
    ))
    session.commit()
    session.close()

    def raising_generate(**kwargs):
        raise RuntimeError("builder unavailable")

    monkeypatch.setattr(main, "_generate_os_update_catalog_candidates", raising_generate)

    try:
        # Must not raise — one device's failure shouldn't kill the whole poll cycle.
        main._os_catalog_refresh_pending_devices()
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
