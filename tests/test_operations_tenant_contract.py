from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_cmdb_routes_apply_visible_device_scope():
    code = source("headend/cmdb.py")
    assert "def _visible_device_ids" in code
    assert "_ensure_device_access(db, _user, device_id)" in code
    assert "DeviceInventory.device_id.in_(visible)" in code


def test_siem_queries_start_from_tenant_scoped_query():
    code = source("headend/siem.py")
    assert "def _visible_event_query" in code
    assert "q = _visible_event_query(db, _user)" in code
    assert "visible = _visible_event_query(db, _user)" in code


def test_itim_health_metrics_and_alerts_are_tenant_scoped():
    code = source("headend/itim.py")
    assert "def _visible_target_query" in code
    assert "_ensure_target_access(db, _user" in code
    assert "ItimAlertEvent.target_id.in_(visible_ids)" in code
