"""Regression/behaviour test (2026-08-08): physical camera hardware CMDB.

`cameras.model`/`serial_number` existed but were never populated — Peter:
"det fysiske kamera mangler i vores CMDB". These tests exercise the real
report/read functions in api/camera_hardware_api.py against the test
database (not the source-string-assertion style used for wiring checks
elsewhere — this module has real branching logic worth running).
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))
os.environ.setdefault("DATABASE_URL", os.getenv("TIMELAPSE_TEST_DATABASE_URL", "postgresql://timelapse@localhost/timelapse_test"))
os.environ.setdefault("TIMELAPSE_ENV", "test")

from database import Camera, CameraFirmwareReference, Device, DeviceAssignment, SessionLocal  # noqa: E402
from api.camera_hardware_api import _firmware_status, report_camera_hardware_inventory  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def device_and_camera(db):
    """A Device with an active DeviceAssignment to a fresh Camera — cleaned
    up unconditionally, even if the test itself fails."""
    device_id = f"TEST-HW-{uuid.uuid4().hex[:8]}"
    camera_id = str(uuid.uuid4())
    device = Device(device_id=device_id)
    camera = Camera(id=camera_id, camera_name="Test kamera")
    assignment = DeviceAssignment(device_id=device_id, camera_id=camera_id, assigned_by="test")
    db.add_all([device, camera, assignment])
    db.commit()
    try:
        yield device_id, camera_id
    finally:
        db.query(DeviceAssignment).filter_by(device_id=device_id).delete()
        db.query(Camera).filter_by(id=camera_id).delete()
        db.query(Device).filter_by(device_id=device_id).delete()
        db.commit()


def test_report_populates_previously_empty_model_and_serial(db, device_and_camera):
    device_id, camera_id = device_and_camera
    result = report_camera_hardware_inventory(db, device_id, {
        "model": "NIKON Z30", "serial_number": "ABC12345",
        "firmware_version": "C1.10", "battery_level_pct": 75,
    })
    assert result["ok"] is True
    camera = db.query(Camera).filter_by(id=camera_id).first()
    assert camera.model == "NIKON Z30"
    assert camera.serial_number == "ABC12345"
    assert camera.battery_level_pct == 75
    assert camera.hardware_inventory_at is not None


def test_report_raises_404_when_device_has_no_active_camera(db):
    with pytest.raises(HTTPException) as exc_info:
        report_camera_hardware_inventory(db, "NO-SUCH-DEVICE-EVER", {"model": "x"})
    assert exc_info.value.status_code == 404


def test_report_stores_observed_settings_as_json(db, device_and_camera):
    device_id, camera_id = device_and_camera
    observed = {"iso": "400", "aperture": "f/8", "shutter_speed": "1/250"}
    report_camera_hardware_inventory(db, device_id, {"observed_settings": observed})
    camera = db.query(Camera).filter_by(id=camera_id).first()
    assert camera.observed_settings_at is not None
    import json
    assert json.loads(camera.observed_settings) == observed


def test_firmware_status_unknown_when_no_reference_row(db, device_and_camera):
    _device_id, camera_id = device_and_camera
    camera = db.query(Camera).filter_by(id=camera_id).first()
    camera.model = "Some Camera Nobody Has Catalogued"
    camera.firmware_version = "9.9.9"
    db.commit()
    status = _firmware_status(camera, db)
    assert status == {"known": False, "update_available": None, "latest_version": None}


def test_firmware_status_flags_outdated_version(db, device_and_camera):
    _device_id, camera_id = device_and_camera
    model_name = f"Test Model {uuid.uuid4().hex[:6]}"
    ref = CameraFirmwareReference(
        manufacturer="Nikon", model=model_name, latest_version="C1.20", updated_by="test",
    )
    db.add(ref)
    db.commit()
    try:
        camera = db.query(Camera).filter_by(id=camera_id).first()
        camera.model = model_name
        camera.firmware_version = "C1.10"
        db.commit()
        status = _firmware_status(camera, db)
        assert status["known"] is True
        assert status["update_available"] is True
        assert status["latest_version"] == "C1.20"
    finally:
        db.query(CameraFirmwareReference).filter_by(model=model_name).delete()
        db.commit()


def test_firmware_status_reports_up_to_date(db, device_and_camera):
    _device_id, camera_id = device_and_camera
    model_name = f"Test Model {uuid.uuid4().hex[:6]}"
    ref = CameraFirmwareReference(
        manufacturer="Canon", model=model_name, latest_version="1.2.0", updated_by="test",
    )
    db.add(ref)
    db.commit()
    try:
        camera = db.query(Camera).filter_by(id=camera_id).first()
        camera.model = model_name
        camera.firmware_version = "1.2.0"
        db.commit()
        status = _firmware_status(camera, db)
        assert status["update_available"] is False
    finally:
        db.query(CameraFirmwareReference).filter_by(model=model_name).delete()
        db.commit()
