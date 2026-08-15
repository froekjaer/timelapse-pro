"""F-001: Headend config merge must never emit a shared factory TOTP secret."""

import json
import os
import pathlib
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture()
def db_session():
    database.create_tables()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


def _make_device(session, device_id: str):
    device = database.Device(
        device_id=device_id,
        customer_id="cust-f001",
        site_id="site-f001",
        app_version="test",
    )
    session.add(device)
    session.commit()
    return device


def test_unprovisioned_config_has_no_shared_factory_totp_and_disables_service(db_session):
    _make_device(db_session, "TL-F001-UNPROVISIONED")
    cfg = main.get_config("TL-F001-UNPROVISIONED", _auth=None, db=db_session)
    payload = json.dumps(cfg, sort_keys=True)

    assert cfg["bt_totp"] == {"secret": "", "sid": "unprovisioned"}
    assert "JBSWY3DPEHPK3PXP" not in payload
    assert "factory-default" not in payload
    assert cfg["service_access"]["enabled"] is False
    assert cfg["service_access"]["live_view_enabled"] is False
    assert cfg["service_access"]["allow_continuous_live_view"] is False
    assert cfg["service_access"]["disabled_reason"] == "local_totp_unprovisioned"


def test_explicit_camera_totp_recovery_adapter_remains_available(db_session):
    _make_device(db_session, "TL-F001-PROVISIONED")
    camera = database.Camera(
        id="cam-f001",
        customer_id="cust-f001",
        site_id="site-f001",
        camera_name="F001 Camera",
        bt_totp_secret="JBSWY3DPEHPK3PXP2",
        bt_totp_sid="camera-f001",
    )
    assignment = database.DeviceAssignment(
        device_id="TL-F001-PROVISIONED",
        camera_id="cam-f001",
        assigned_by="test",
    )
    db_session.add_all([camera, assignment])
    db_session.commit()

    cfg = main.get_config("TL-F001-PROVISIONED", _auth=None, db=db_session)
    assert cfg["bt_totp"] == {"secret": "JBSWY3DPEHPK3PXP2", "sid": "camera-f001"}
    assert cfg["service_access"]["enabled"] is True
    assert "disabled_reason" not in cfg["service_access"]
