"""Tenant-isolation regression tests (security remediation P0, 2026-10-10).

Customer-bound admins (role=admin with customer_id) must only reach Edge
diagnostics, capture sessions, backup requests, tunnel logs and lifecycle
transitions for devices in their own tenant. Platform admins (super_admin, or
admin without customer_id) keep full access. Platform-wide snapshots are
platform-admin only.

Same pattern as test_c04_device_admin_tenant_isolation.py: route functions are
called directly against a real sqlite session so the actual tenant-resolution
SQL runs.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import main
from api import edge_communication_debug_api as diag
from api.edge_lifecycle_api import EdgeLifecycleTransitionPayload, create_edge_lifecycle_router
from database import (
    Base,
    Device,
    EdgeApiCommunicationLog,
    EdgeCommunicationCaptureSession,
    SessionLocal,
    Site,
    engine,
)

OWN_DEVICE = "TL-TESTDEVICE-P0-OWN"
FOREIGN_DEVICE = "TL-TESTDEVICE-P0-FOREIGN"
OWN_CUSTOMER = "cust-own-p0"
FOREIGN_CUSTOMER = "cust-foreign-p0"
DEVICES = (OWN_DEVICE, FOREIGN_DEVICE)


def _cleanup(session):
    session.query(EdgeApiCommunicationLog).filter(EdgeApiCommunicationLog.device_id.in_(DEVICES)).delete(
        synchronize_session=False)
    session.query(EdgeCommunicationCaptureSession).delete(synchronize_session=False)
    session.query(Device).filter(Device.device_id.in_(DEVICES)).delete(synchronize_session=False)
    session.query(Site).filter(Site.customer_id.in_((OWN_CUSTOMER, FOREIGN_CUSTOMER))).delete(
        synchronize_session=False)
    session.commit()


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _cleanup(session)
    session.add(Device(device_id=OWN_DEVICE, customer_id=OWN_CUSTOMER))
    session.add(Device(device_id=FOREIGN_DEVICE, customer_id=FOREIGN_CUSTOMER))
    for device_id in DEVICES:
        session.add(EdgeApiCommunicationLog(device_id=device_id, method="POST", path="/api/sync"))
    session.commit()
    try:
        yield session
    finally:
        _cleanup(session)
        session.close()


def _tenant_admin(customer_id=OWN_CUSTOMER):
    return MagicMock(username="tenant-admin", role="admin", customer_id=customer_id)


def _platform_admin():
    return MagicMock(username="platform-admin", role="admin", customer_id=None)


def _super_admin():
    return MagicMock(username="super", role="super_admin", customer_id=None)


def _status(fn, *args, **kwargs):
    with pytest.raises(HTTPException) as exc:
        fn(*args, **kwargs)
    return exc.value.status_code


def _log_devices(db):
    return {row.device_id for row in db.query(EdgeApiCommunicationLog)
            .filter(EdgeApiCommunicationLog.device_id.in_(DEVICES)).all()}


# --- Edge communication diagnostics -------------------------------------------------

def test_diag_device_list_is_tenant_scoped(db):
    ids = {d["device_id"] for d in diag.list_devices(_user=_tenant_admin(), db=db)}
    assert OWN_DEVICE in ids and FOREIGN_DEVICE not in ids
    ids = {d["device_id"] for d in diag.list_devices(_user=_super_admin(), db=db)}
    assert {OWN_DEVICE, FOREIGN_DEVICE} <= ids


def test_diag_list_unfiltered_shows_only_own_tenant(db):
    rows = diag.list_communications(device_id=None, transport_security=None, limit=200,
                                    _user=_tenant_admin(), db=db)
    assert {r["device_id"] for r in rows} & set(DEVICES) == {OWN_DEVICE}


def test_diag_list_other_tenant_device_is_rejected(db):
    assert _status(diag.list_communications, device_id=FOREIGN_DEVICE, transport_security=None,
                   limit=200, _user=_tenant_admin(), db=db) == 403


def test_diag_list_platform_admin_sees_all(db):
    rows = diag.list_communications(device_id=None, transport_security=None, limit=1000,
                                    _user=_platform_admin(), db=db)
    assert {OWN_DEVICE, FOREIGN_DEVICE} <= {r["device_id"] for r in rows}


def test_diag_export_is_tenant_scoped(db, monkeypatch):
    assert _status(diag.export_communications, device_id=FOREIGN_DEVICE, transport_security=None,
                   limit=1000, _user=_tenant_admin(), db=db) == 403
    exported = []
    monkeypatch.setattr(diag, "_xlsx_response", lambda rows: exported.extend(rows) or "xlsx")
    diag.export_communications(device_id=None, transport_security=None, limit=1000,
                               _user=_tenant_admin(), db=db)
    assert {r["device_id"] for r in exported} & set(DEVICES) == {OWN_DEVICE}


def test_diag_delete_other_tenant_device_is_rejected(db):
    assert _status(diag.clear_communications, device_id=FOREIGN_DEVICE, transport_security=None,
                   _user=_tenant_admin(), db=db) == 403
    assert _log_devices(db) == set(DEVICES)


def test_diag_delete_unfiltered_only_clears_own_tenant(db):
    result = diag.clear_communications(device_id=None, transport_security=None,
                                       _user=_tenant_admin(), db=db)
    assert result["deleted"] == 1
    assert _log_devices(db) == {FOREIGN_DEVICE}


def test_diag_delete_platform_admin_clears_all(db):
    diag.clear_communications(device_id=None, transport_security=None, _user=_super_admin(), db=db)
    assert _log_devices(db) == set()


# --- Capture sessions -------------------------------------------------------------

def test_capture_start_own_device_allowed(db):
    session = diag.start_capture(device_id=OWN_DEVICE, duration_minutes=5, max_packets=None,
                                 _user=_tenant_admin(), db=db)
    assert session["device_id"] == OWN_DEVICE


def test_capture_start_other_tenant_device_rejected(db):
    assert _status(diag.start_capture, device_id=FOREIGN_DEVICE, duration_minutes=5, max_packets=None,
                   _user=_tenant_admin(), db=db) == 403


def test_capture_start_global_session_is_platform_only(db):
    assert _status(diag.start_capture, device_id=None, duration_minutes=5, max_packets=None,
                   _user=_tenant_admin(), db=db) == 403
    session = diag.start_capture(device_id=None, duration_minutes=5, max_packets=None,
                                 _user=_platform_admin(), db=db)
    assert session["device_id"] is None


def test_capture_stop_other_tenant_session_rejected(db):
    foreign = diag.start_capture(device_id=FOREIGN_DEVICE, duration_minutes=5, max_packets=None,
                                 _user=_super_admin(), db=db)
    assert _status(diag.stop_capture, foreign["id"], _user=_tenant_admin(), db=db) == 403
    stopped = diag.stop_capture(foreign["id"], _user=_super_admin(), db=db)
    assert stopped["stopped_at"] is not None


def test_capture_stop_global_session_rejected_for_tenant_admin(db):
    global_session = diag.start_capture(device_id=None, duration_minutes=5, max_packets=None,
                                        _user=_super_admin(), db=db)
    assert _status(diag.stop_capture, global_session["id"], _user=_tenant_admin(), db=db) == 403


def test_capture_stop_own_session_allowed(db):
    own = diag.start_capture(device_id=OWN_DEVICE, duration_minutes=5, max_packets=None,
                             _user=_tenant_admin(), db=db)
    assert diag.stop_capture(own["id"], _user=_tenant_admin(), db=db)["stopped_at"] is not None


def test_capture_status_hides_other_tenants_and_global_sessions(db):
    diag.start_capture(device_id=FOREIGN_DEVICE, duration_minutes=5, max_packets=None,
                       _user=_super_admin(), db=db)
    diag.start_capture(device_id=OWN_DEVICE, duration_minutes=5, max_packets=None,
                       _user=_tenant_admin(), db=db)
    tenant_view = {s["device_id"] for s in diag.capture_status(_user=_tenant_admin(), db=db)}
    assert tenant_view == {OWN_DEVICE}
    platform_view = {s["device_id"] for s in diag.capture_status(_user=_super_admin(), db=db)}
    assert {OWN_DEVICE, FOREIGN_DEVICE} <= platform_view


# --- Resilience and backup ----------------------------------------------------------

def test_resilience_assessment_is_platform_admin_only(db):
    assert _status(main.resilience_assessment, _user=_tenant_admin(), db=db) == 403
    assert isinstance(main.resilience_assessment(_user=_super_admin(), db=db), dict)
    assert isinstance(main.resilience_assessment(_user=_platform_admin(), db=db), dict)


def test_trigger_edge_backup_other_tenant_rejected(db):
    assert _status(main.trigger_edge_backup, FOREIGN_DEVICE, _user=_tenant_admin(), db=db) == 403
    device = db.query(Device).filter_by(device_id=FOREIGN_DEVICE).first()
    assert "backup_requested" not in (device.device_config or "")


def test_trigger_edge_backup_own_tenant_and_platform_allowed(db):
    assert main.trigger_edge_backup(OWN_DEVICE, _user=_tenant_admin(), db=db)["status"] == "ok"
    assert main.trigger_edge_backup(FOREIGN_DEVICE, _user=_super_admin(), db=db)["status"] == "ok"


def test_edge_backup_complete_other_tenant_rejected(db):
    assert _status(main.edge_backup_complete, FOREIGN_DEVICE, {"filename": "x.tar.gz"},
                   _user=_tenant_admin(), db=db) == 403


def test_ssh_tunnel_log_is_tenant_scoped(db):
    assert _status(main.ssh_tunnel_log, FOREIGN_DEVICE, limit=10, _user=_tenant_admin(), db=db) == 403
    assert isinstance(main.ssh_tunnel_log(OWN_DEVICE, limit=10, _user=_tenant_admin(), db=db), list)
    assert isinstance(main.ssh_tunnel_log(FOREIGN_DEVICE, limit=10, _user=_super_admin(), db=db), list)


# --- Edge lifecycle -----------------------------------------------------------------

def _lifecycle_endpoints():
    router = create_edge_lifecycle_router(
        require_role=lambda *roles: None,
        sanitize_device_id=lambda value: value,
        audit_key_event=lambda *a, **k: None,
        reconcile_edge_lifecycle=lambda *a, **k: None,
    )
    return {route.path: route.endpoint for route in router.routes}


def test_lifecycle_transition_other_tenant_rejected(db):
    transition = _lifecycle_endpoints()["/api/admin/edge-lifecycle/{device_id}/transition"]
    payload = EdgeLifecycleTransitionPayload(state="quarantined", reason="test")
    assert _status(transition, FOREIGN_DEVICE, payload, current_user=_tenant_admin(), db=db) == 403


def test_lifecycle_transition_own_tenant_not_tenant_blocked(db):
    transition = _lifecycle_endpoints()["/api/admin/edge-lifecycle/{device_id}/transition"]
    payload = EdgeLifecycleTransitionPayload(state="quarantined", reason="test")
    try:
        transition(OWN_DEVICE, payload, current_user=_tenant_admin(), db=db)
    except HTTPException as exc:   # an invalid state transition is fine; a tenant denial is not
        assert exc.status_code != 403


def test_lifecycle_reconcile_is_platform_admin_only(db):
    reconcile = _lifecycle_endpoints()["/api/admin/edge-lifecycle/reconcile"]
    assert _status(reconcile, current_user=_tenant_admin(), db=db) == 403


# --- Fleet overviews: super_admin sees all, admin/operator/viewer per tenant ---------

@pytest.fixture()
def fleet(db):
    from database import CaptureAccessLog, DeviceInventory, SshTunnelLog
    for device_id, customer in ((OWN_DEVICE, OWN_CUSTOMER), (FOREIGN_DEVICE, FOREIGN_CUSTOMER)):
        db.add(DeviceInventory(device_id=device_id, hostname=device_id.lower()))
        db.add(SshTunnelLog(device_id=device_id, event="connected", remote_port=40000))
        db.add(CaptureAccessLog(device_id=device_id, filename="x.jpg", customer_id=customer))
    db.commit()
    yield db
    for model in (DeviceInventory, SshTunnelLog, CaptureAccessLog):
        db.query(model).filter(model.device_id.in_(DEVICES)).delete(synchronize_session=False)
    db.commit()


def _ids(rows, key="device_id"):
    return {row[key] for row in rows} & set(DEVICES)


def test_update_device_matrix_is_tenant_scoped(fleet):
    assert _ids(main.list_update_device_matrix(_user=_tenant_admin(), db=fleet)["devices"]) == {OWN_DEVICE}
    assert _ids(main.list_update_device_matrix(_user=_super_admin(), db=fleet)["devices"]) == set(DEVICES)


def test_grc_dashboard_is_tenant_scoped(fleet):
    assert _ids(main.grc_dashboard(_user=_tenant_admin(), db=fleet)["devices"]) == {OWN_DEVICE}
    assert _ids(main.grc_dashboard(_user=_super_admin(), db=fleet)["devices"]) == set(DEVICES)


def test_ssh_tunnel_active_is_tenant_scoped(fleet, monkeypatch):
    monkeypatch.setattr(main, "_localhost_tcp_reachable", lambda port: True)
    assert _ids(main.ssh_tunnel_active(_user=_tenant_admin(), db=fleet)) == {OWN_DEVICE}
    operator = MagicMock(username="op", role="operator", customer_id=OWN_CUSTOMER)
    assert _ids(main.ssh_tunnel_active(_user=operator, db=fleet)) == {OWN_DEVICE}
    assert _ids(main.ssh_tunnel_active(_user=_super_admin(), db=fleet)) == set(DEVICES)


def test_update_flow_status_only_lists_own_tenant_targets(fleet, monkeypatch):
    from database import PendingUpdate
    update = PendingUpdate(update_type="agent", version="p0-test", status="approved", scope="global")
    fleet.add(update)
    fleet.commit()
    devices = fleet.query(Device).filter(Device.device_id.in_(DEVICES)).all()
    monkeypatch.setattr(main, "_resolve_update_targets", lambda db, u: list(devices))
    try:
        own = main.get_update_flow_status(update.id, _user=_tenant_admin(), db=fleet)
        everyone = main.get_update_flow_status(update.id, _user=_super_admin(), db=fleet)
    finally:
        fleet.delete(update)
        fleet.commit()
    assert _ids(own["targets"]) == {OWN_DEVICE}
    assert _ids(everyone["targets"]) == set(DEVICES)


def test_capture_access_log_is_tenant_scoped_for_admins(fleet):
    from api.capture_access_api import search_capture_access

    def search(user):
        return search_capture_access(username=None, device_id=None, filename=None, action=None,
                                     hours=24, limit=500, user=user, db=fleet)
    assert _ids(search(_tenant_admin())) == {OWN_DEVICE}
    assert _ids(search(_super_admin())) == set(DEVICES)


def _route_role_check(path: str, method: str):
    for route in main.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return next(dep.call for dep in route.dependant.dependencies if dep.call.__name__ == "_check")
    raise AssertionError(f"route not found: {method} {path}")


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/key-management"),
    ("POST", "/api/admin/key-management/migrate-legacy-device-tokens"),
    ("POST", "/api/admin/key-management/credentials"),
    ("POST", "/api/admin/key-management/credentials/{credential_id}/revoke"),
    ("POST", "/api/admin/key-management/credentials/{credential_id}/request-signature"),
    ("POST", "/api/admin/key-management/cleanup-stale-credentials"),
    ("GET", "/api/ai/ops/snapshot"),
    ("POST", "/api/ai/ops/analyze"),
    ("POST", "/api/ai/ops/query"),
])
def test_platform_surfaces_are_super_admin_only(db, method, path):
    check = _route_role_check(path, method)
    for user in (_tenant_admin(), _platform_admin()):
        with pytest.raises(HTTPException) as exc:
            check(request=None, user=user, db=db)
        assert exc.value.status_code == 403
