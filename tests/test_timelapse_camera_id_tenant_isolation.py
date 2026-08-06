"""Regression test (2026-08-06): Peter flagged a real tenant-isolation gap while
this session was adding camera_id support to timelapse generation — a Capture
row's device_id alone is NOT proof the current user's customer owns that image.
An Edge device can be unassigned from one customer and later reassigned to a
different one; captures taken under the FIRST customer keep that same
device_id row forever. A query that filters only `Capture.device_id ==
device_id` would let the new customer's admin render a timelapse containing
the previous customer's images, because device_id is a live/reusable
identifier while capture.customer_id is frozen at capture time (see
_resolve_capture_camera_customer() / _capture_tenant_clause()).

Both /api/timelapse/frames and /api/timelapse/create must apply the same
customer_id-first tenant clause (_capture_tenant_clause) that already protects
/api/admin/captures and /api/admin/captures/timeline — for the device_id path
AND the new camera_id path (defense in depth, even though Camera.customer_id
is itself stable).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = MAIN.index(f"def {name}(")
    end = MAIN.index("\n@app.", start + 1)
    return MAIN[start:end]


def test_get_timelapse_frames_enforces_capture_tenant_clause() -> None:
    section = _function_source("get_timelapse_frames")
    assert "_allowed_capture_device_ids(db, _user)" in section
    assert "_capture_tenant_clause(_user, allowed_ids)" in section, (
        "get_timelapse_frames must scope results with _capture_tenant_clause() so a "
        "reused/reassigned device_id cannot surface a previous customer's captures — "
        "device_id alone is not sufficient tenant isolation."
    )


def test_create_timelapse_enforces_capture_tenant_clause() -> None:
    section = _function_source("create_timelapse")
    assert "_allowed_capture_device_ids(db, _user)" in section
    assert "_capture_tenant_clause(_user, allowed_ids)" in section, (
        "create_timelapse must scope the frame lookup with _capture_tenant_clause() so "
        "a reused/reassigned device_id cannot let a video be rendered from a previous "
        "customer's captures."
    )


def test_ensure_capture_camera_access_checks_camera_customer_id() -> None:
    section = _function_source("_ensure_capture_camera_access")
    assert "camera.customer_id != user.customer_id" in section
    assert "_is_platform_admin(user)" in section
