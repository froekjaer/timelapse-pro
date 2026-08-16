"""Contract test for the CMDB baseline-drift reconciliation admin endpoint."""
from pathlib import Path


def _source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / relative_path).read_text(encoding="utf-8")


def test_reconcile_baseline_endpoint_requires_admin_and_delegates_to_service():
    source = _source("headend/main.py")
    pre, _, rest = source.partition("def reconcile_device_cmdb_baseline")
    block = rest.split("\n\n", 1)[0]
    decorator_line = pre.splitlines()[-1]

    assert decorator_line == '@app.post("/api/admin/devices/{device_id}/cmdb/reconcile-baseline")'
    assert 'require_role("admin", "super_admin")' in ("def reconcile_device_cmdb_baseline" + block)
    assert "from services.cmdb_baseline_drift import reconcile_device_baseline" in block
    assert "reconcile_device_baseline(db, device_id, current_user.username)" in block
