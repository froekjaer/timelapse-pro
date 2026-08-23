"""Regression tests for C-04 (MASTER_REVIEW_CLOSURE_2026-08-15.md): several
/api/admin/devices/{device_id}/* routes checked ROLE but not TENANT — a
customer-scoped admin (role=admin, customer_id set) could read or mutate
another customer's device by guessing/enumerating device_id, because these
routes never called _ensure_capture_device_access() the way sibling routes
(e.g. assign_device, /info, /debug) already did.

Verified-open routes fixed here:
  - GET/PUT /api/admin/devices/{device_id}/config
  - GET     /api/admin/devices/{device_id}/camera-location
  - POST    /api/admin/devices/{device_id}/cmdb/reconcile-baseline

Calls the route functions directly (same pattern as
test_break_glass_audit_actor_binding.py) against a real sqlite session so the
actual tenant-resolution SQL (_allowed_capture_device_ids) runs for real,
rather than mocking a query chain that's easy to get subtly wrong.
"""
from unittest.mock import MagicMock

import pytest

import main
from database import Base, Device, Site, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-C04"
OWNER_CUSTOMER = "cust-owner-c04"
OTHER_CUSTOMER = "cust-other-c04"


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.query(Device).filter_by(device_id=DEVICE_ID).delete()
    session.query(Site).filter_by(customer_id=OWNER_CUSTOMER).delete()
    session.commit()
    session.add(Device(device_id=DEVICE_ID, customer_id=OWNER_CUSTOMER))
    session.commit()
    try:
        yield session
    finally:
        session.query(Device).filter_by(device_id=DEVICE_ID).delete()
        session.query(Site).filter_by(customer_id=OWNER_CUSTOMER).delete()
        session.commit()
        session.close()


def _tenant_admin(customer_id: str) -> MagicMock:
    return MagicMock(username="tenant-admin", role="admin", customer_id=customer_id)


def _platform_admin() -> MagicMock:
    return MagicMock(username="platform-admin", role="super_admin", customer_id=None)


def test_get_device_config_admin_rejects_other_tenant(db_session):
    with pytest.raises(Exception) as exc_info:
        main.get_device_config_admin(DEVICE_ID, _user=_tenant_admin(OTHER_CUSTOMER), db=db_session)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_update_device_config_rejects_other_tenant(db_session):
    with pytest.raises(Exception) as exc_info:
        main.update_device_config(DEVICE_ID, {"schedule": {"interval_minutes": 5}}, _user=_tenant_admin(OTHER_CUSTOMER), db=db_session)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_get_device_camera_location_rejects_other_tenant(db_session):
    with pytest.raises(Exception) as exc_info:
        main.get_device_camera_location(DEVICE_ID, _user=_tenant_admin(OTHER_CUSTOMER), db=db_session)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_reconcile_device_cmdb_baseline_rejects_other_tenant(db_session):
    with pytest.raises(Exception) as exc_info:
        main.reconcile_device_cmdb_baseline(DEVICE_ID, current_user=_tenant_admin(OTHER_CUSTOMER), db=db_session)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_get_device_config_admin_allows_owning_tenant(db_session):
    # Must not raise 403 for the device's own customer — reaching further into
    # get_config() is out of scope here, just prove the tenant gate passes.
    try:
        main.get_device_config_admin(DEVICE_ID, _user=_tenant_admin(OWNER_CUSTOMER), db=db_session)
    except Exception as exc:
        assert getattr(exc, "status_code", None) != 403


def test_get_device_camera_location_allows_platform_admin(db_session):
    result = main.get_device_camera_location(DEVICE_ID, _user=_platform_admin(), db=db_session)
    assert result == {"assignment": None, "camera": None}
