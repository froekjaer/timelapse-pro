"""Regression test (2026-08-06): Peter asked how to clean up a mistakenly
created camera location that already has captures attached (retire_empty_
camera_location() only handles the zero-capture case). He chose "both" when
offered a choice: a safe move-captures-to-the-correct-location path as the
default, plus a rarer, strongly-guarded permanent delete-with-data path for
when the images themselves were also a mistake.

move_camera_captures() must never move captures across customers (that would
be a tenant leak, not cleanup) and must keep customer_id/site_id consistent
with the destination camera.

force_delete_camera_location() must require super_admin (a higher bar than
the other camera-location endpoints, since it is irreversible), must require
the caller to type the location's exact current name as confirmation, and
must still refuse to delete a location with a live device assignment.

Both live in headend/api/camera_locations_api.py — extracted same day from
headend/main.py (see that module's docstring and Peter's reminder that the
architecture-ratchet baseline exists to force extraction, not to be raised
indefinitely instead of it).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "headend" / "api" / "camera_locations_api.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = SOURCE.index(f"def {name}(")
    end = SOURCE.index("\n@router.", start + 1)
    return SOURCE[start:end]


def test_move_captures_enforces_same_customer() -> None:
    section = _function_source("move_camera_captures")
    assert 'source.customer_id != target.customer_id' in section
    assert 'status_code=400' in section


def test_move_captures_updates_customer_and_site_to_target() -> None:
    section = _function_source("move_camera_captures")
    assert "Capture.customer_id: target.customer_id" in section
    assert "Capture.site_id: target.site_id" in section


def test_force_delete_requires_super_admin() -> None:
    start = SOURCE.index('def force_delete_camera_location(')
    header = SOURCE[start:start + 300]
    assert '_require_role("super_admin")' in header, (
        "force_delete_camera_location must require super_admin only — the other "
        "camera-location endpoints allow admin, but this one is irreversible."
    )


def test_force_delete_requires_exact_name_confirmation() -> None:
    section = _function_source("force_delete_camera_location")
    assert "confirm_name != expected_name" in section


def test_force_delete_still_blocks_on_active_device_assignment() -> None:
    section = _function_source("force_delete_camera_location")
    assert "DeviceAssignment.unassigned_at.is_(None)" in section
    assert "status_code=409" in section


def test_camera_locations_router_is_included_from_main() -> None:
    main_source = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
    assert "from api.camera_locations_api import router as _camera_locations_router" in main_source
    assert "app.include_router(_camera_locations_router)" in main_source


def test_all_events_in_this_module_set_device_id() -> None:
    """Regression test (2026-08-06): force_delete_camera_location() returned
    HTTP 500 on first live use — Event.device_id is NOT NULL in the schema,
    but none of the three Event(...) calls in this module (retire, move,
    force-delete) set it, since none of these actions are about a specific
    physical device. The failed commit rolled the whole transaction back
    cleanly (get_db()'s finally: db.rollback()), so no data was lost, but the
    request still 500'd. Fixed by using the same "HEADEND" sentinel
    device_id already used elsewhere in main.py for headend-originated
    events not tied to a device (see main.py's device_id="HEADEND" usage and
    siem.py's "HEADEND-LOCAL" convention)."""
    import re
    for match in re.finditer(r"Event\(\s*\n", SOURCE):
        block_start = match.end()
        block_end = SOURCE.index("))", block_start)
        block = SOURCE[block_start:block_end]
        assert "device_id=" in block, (
            f"Event(...) call near offset {match.start()} is missing device_id "
            "(NOT NULL column) — will 500 on commit"
        )
