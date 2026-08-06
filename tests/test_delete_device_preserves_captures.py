"""Regression test (2026-08-06): DELETE /api/admin/devices/{device_id} used to
cascade-delete every Capture row for the device (`db.query(Capture)
.filter_by(device_id=device_id).delete()`) before deleting the Device row
itself. CameraPage.tsx's "Slet kamera" button called this with only a generic
"cannot be undone" confirmation — no mention that images would be destroyed.
This directly contradicted the same-day camera_id architecture work (see
HANDOVER_LOG.md 2026-08-06): a camera location's image history is supposed to
survive its device being replaced/unassigned/removed, not be wiped out the
moment someone tidies up the device list. It is plausible this exact
mechanism (or one just like it) caused the original Travbyen incident this
session investigated and fixed.

Device deletion must now leave Capture rows alone (they survive via the
frozen camera_id/customer_id) and must refuse to delete a device if doing so
would orphan captures that have no camera_id to fall back on.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = MAIN.index(f"def {name}(")
    end = MAIN.index("\n@app.", start + 1)
    return MAIN[start:end]


def test_delete_device_does_not_cascade_delete_captures() -> None:
    section = _function_source("delete_device")
    assert "db.query(Capture).filter_by(device_id=device_id).delete()" not in section, (
        "delete_device must never bulk-delete Capture rows — captures are durably "
        "bound to camera_id/customer_id and must survive their device being removed."
    )


def test_delete_device_blocks_when_it_would_orphan_captures() -> None:
    section = _function_source("delete_device")
    assert "Capture.camera_id.is_(None)" in section
    assert "status_code=409" in section


def test_delete_device_still_purges_operational_telemetry() -> None:
    section = _function_source("delete_device")
    assert "db.query(Diagnostic).filter_by(device_id=device_id).delete()" in section
    assert "db.query(Event).filter_by(device_id=device_id).delete()" in section
