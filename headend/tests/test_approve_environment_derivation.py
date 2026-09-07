"""_resolve_approval_environment() — the fix for Peter's 2026-09-08 finding
that Edge 2's os_security update (#273) got approved to environment "test"
even though the device itself reports "production", so it silently
authorized zero targets (update_applies_to_device() correctly refuses a
mismatched device) and sat forever at "Afventer Edge poll" with no error
shown anywhere. The approve dialog's environment dropdown had defaulted from
the update's *current* environment field, not the target device's actual
one — an easy, silent trap for exactly this "first real approval" scenario.

A device-scoped approval already names one specific device; the environment
must come from that device's own reported environment, not a second,
disconnected free-choice field.
"""
import main
from database import Base, Device, DeviceInventory, SessionLocal, engine


DEVICE_ID = "TL-TESTDEVICE-APPROVEENV"


def _clean(session):
    session.query(DeviceInventory).filter_by(device_id=DEVICE_ID).delete()
    session.query(Device).filter_by(device_id=DEVICE_ID).delete()
    session.commit()


def test_device_scope_overrides_requested_environment_with_devices_own():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production"))
        session.commit()

        resolved = main._resolve_approval_environment(session, "test", "device", DEVICE_ID)
        assert resolved == "production"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_device_scope_falls_back_to_requested_when_device_has_no_reported_environment():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        # "" not None: the environment column has a Python-side default of
        # "production", which SQLAlchemy applies for a genuinely-unset (None)
        # value at flush time — "" is an explicit value that bypasses it, so
        # this actually exercises the "no real environment reported" case.
        session.add(DeviceInventory(device_id=DEVICE_ID, environment=""))
        session.commit()

        resolved = main._resolve_approval_environment(session, "test", "device", DEVICE_ID)
        assert resolved == "test"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_device_scope_falls_back_to_requested_when_device_unknown():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        resolved = main._resolve_approval_environment(session, "test", "device", "TL-DOES-NOT-EXIST")
        assert resolved == "test"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_non_device_scope_keeps_requested_environment():
    # Customer/site/global rollouts genuinely span multiple devices with
    # potentially different environments — there's no single device to defer
    # to, so the explicit choice must still work.
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    resolved = main._resolve_approval_environment(session, "test", "customer", "some-customer-id")
    assert resolved == "test"


def test_device_scope_without_scope_id_keeps_requested_environment():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    resolved = main._resolve_approval_environment(session, "production", "device", None)
    assert resolved == "production"
