"""heartbeat() (headend/main.py) must persist camera_hardware (manufacturer/
model/serial_number/firmware_version, read via gphoto2 on the edge — see
edge/diagnostics/camera_diagnostics.py) onto the Camera row currently
assigned to the reporting device. Added 2026-09-01 per Peter: get the
physical camera's own hardware/firmware into CMDB — previously nothing about
the attached camera reached Headend at all, only the Orange Pi's own
OS/hardware inventory.
"""
import uuid

import pytest

import database
import main


@pytest.fixture()
def db_session():
    database.create_tables()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


def _seed_device_with_camera(db, device_id="TL-TEST0001"):
    db.add(database.Device(device_id=device_id))
    camera_id = str(uuid.uuid4())
    db.add(database.Camera(id=camera_id, camera_name="Test kamera"))
    db.add(database.DeviceAssignment(device_id=device_id, camera_id=camera_id, assigned_by="test"))
    db.commit()
    return camera_id


def _heartbeat_request(device_id, camera_hardware=None):
    return main.HeartbeatRequest(
        device_id=device_id,
        timestamp="2026-09-01T00:00:00Z",
        diagnostics={"camera": {"camera_hardware": camera_hardware or {}}},
        capture_stats={},
    )


def test_camera_hardware_is_written_to_the_assigned_camera(db_session):
    camera_id = _seed_device_with_camera(db_session)
    req = _heartbeat_request("TL-TEST0001", {
        "manufacturer": "Nikon Corporation",
        "model": "Nikon Z30",
        "serial_number": "4008675309",
        "firmware_version": "1.20",
    })

    main.heartbeat("TL-TEST0001", req, _auth=None, db=db_session)

    camera = db_session.query(database.Camera).filter_by(id=camera_id).first()
    assert camera.reported_manufacturer == "Nikon Corporation"
    assert camera.reported_model == "Nikon Z30"
    assert camera.reported_serial_number == "4008675309"
    assert camera.reported_firmware_version == "1.20"
    assert camera.reported_at is not None


def test_missing_camera_hardware_does_not_touch_the_camera_row(db_session):
    camera_id = _seed_device_with_camera(db_session)
    req = _heartbeat_request("TL-TEST0001", camera_hardware={})

    main.heartbeat("TL-TEST0001", req, _auth=None, db=db_session)

    camera = db_session.query(database.Camera).filter_by(id=camera_id).first()
    assert camera.reported_at is None
    assert camera.reported_model is None


def test_partial_read_does_not_blank_previously_known_fields(db_session):
    camera_id = _seed_device_with_camera(db_session)
    full = {
        "manufacturer": "Nikon Corporation",
        "model": "Nikon Z30",
        "serial_number": "4008675309",
        "firmware_version": "1.20",
    }
    main.heartbeat("TL-TEST0001", _heartbeat_request("TL-TEST0001", full), _auth=None, db=db_session)

    # Next sync only managed to read the model (e.g. camera briefly busy for
    # the other gphoto2 reads) — the rest must survive, not go blank.
    main.heartbeat("TL-TEST0001", _heartbeat_request("TL-TEST0001", {"model": "Nikon Z30"}), _auth=None, db=db_session)

    camera = db_session.query(database.Camera).filter_by(id=camera_id).first()
    assert camera.reported_serial_number == "4008675309"
    assert camera.reported_firmware_version == "1.20"


def test_device_with_no_camera_assignment_is_a_no_op(db_session):
    db_session.add(database.Device(device_id="TL-UNASSIGNED"))
    db_session.commit()
    req = _heartbeat_request("TL-UNASSIGNED", {"model": "Nikon Z30"})

    main.heartbeat("TL-UNASSIGNED", req, _auth=None, db=db_session)  # must not raise
