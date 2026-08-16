"""Regression contracts for update authority target and environment isolation."""
import json
import os
import pathlib
import sys
import tempfile

import pytest
from fastapi import HTTPException

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import database  # noqa: E402
import main  # noqa: E402


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


def _device(session, device_id, *, customer_id="cust-a", site_id="site-a", environment="production"):
    device = database.Device(device_id=device_id, customer_id=customer_id, site_id=site_id, app_version="1.0.0")
    inventory = database.DeviceInventory(device_id=device_id, environment=environment, app_version="1.0.0")
    session.add_all([device, inventory])
    session.commit()
    return device


def _update(session, **kwargs):
    values = dict(
        update_type="config_metadata",
        version="v-next",
        scope="device",
        scope_id="dev-a",
        status="approved",
        environment="production",
    )
    values.update(kwargs)
    update = database.PendingUpdate(**values)
    session.add(update)
    session.commit()
    return update


def _policy(session, device_id):
    return main.get_update_policy(device_id=device_id, _auth=None, db=session)


def test_customer_scoped_update_reaches_matching_device(db_session):
    _device(db_session, "dev-a", customer_id="cust-a", site_id="site-a")
    _device(db_session, "dev-b", customer_id="cust-b", site_id="site-b")
    update = _update(db_session, scope="customer", scope_id="cust-a")
    assert [item["id"] for item in _policy(db_session, "dev-a")["pending_updates"]] == [update.id]
    assert _policy(db_session, "dev-b")["pending_updates"] == []


def test_site_scoped_update_reaches_matching_device(db_session):
    _device(db_session, "dev-a", site_id="site-a")
    _device(db_session, "dev-b", site_id="site-b")
    update = _update(db_session, scope="site", scope_id="site-a")
    assert [item["id"] for item in _policy(db_session, "dev-a")["pending_updates"]] == [update.id]
    assert _policy(db_session, "dev-b")["pending_updates"] == []


def test_environment_is_fail_closed_and_test_alias_maps_to_lab(db_session):
    _device(db_session, "dev-prod", environment="production")
    _device(db_session, "dev-lab", environment="lab")
    update = _update(db_session, scope="global", scope_id=None, environment="test")
    assert _policy(db_session, "dev-prod")["pending_updates"] == []
    assert [item["id"] for item in _policy(db_session, "dev-lab")["pending_updates"]] == [update.id]


def test_resolve_targets_excludes_wrong_environment(db_session):
    _device(db_session, "dev-prod", environment="production")
    _device(db_session, "dev-lab", environment="lab")
    update = _update(db_session, scope="global", scope_id=None, environment="lab")
    resolved = main._resolve_update_targets(db_session, update)
    assert [device.device_id for device in resolved] == ["dev-lab"]


def test_non_target_authenticated_edge_cannot_report_status(db_session):
    _device(db_session, "dev-a", site_id="site-a")
    _device(db_session, "dev-b", site_id="site-b")
    update = _update(db_session, scope="site", scope_id="site-a")
    with pytest.raises(HTTPException) as excinfo:
        main.report_update(
            {"update_id": update.id, "status": "deployed", "device_id": "dev-b"},
            authenticated_device_id="dev-b",
            db=db_session,
        )
    assert excinfo.value.status_code == 403
    db_session.refresh(update)
    assert update.status == "approved"
    assert db_session.query(database.UpdateTarget).filter_by(
        pending_update_id=update.id,
        device_id="dev-b",
    ).count() == 0


def test_wrong_environment_edge_cannot_report_status(db_session):
    _device(db_session, "dev-a", environment="production")
    update = _update(db_session, scope="device", scope_id="dev-a", environment="lab")
    with pytest.raises(HTTPException) as excinfo:
        main.report_update(
            {"update_id": update.id, "status": "deployed", "device_id": "dev-a"},
            authenticated_device_id="dev-a",
            db=db_session,
        )
    assert excinfo.value.status_code == 403
    db_session.refresh(update)
    assert update.status == "approved"


def test_explicit_target_list_remains_authoritative(db_session):
    _device(db_session, "dev-a", site_id="site-a")
    _device(db_session, "dev-b", site_id="site-a")
    update = _update(
        db_session,
        scope="site",
        scope_id="site-a",
        target_device_ids=json.dumps(["dev-a"]),
    )
    assert [item["id"] for item in _policy(db_session, "dev-a")["pending_updates"]] == [update.id]
    assert _policy(db_session, "dev-b")["pending_updates"] == []
