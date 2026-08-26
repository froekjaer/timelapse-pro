"""
Contract tests for the commissioning-key disable lifecycle
(headend/commissioning_key.py, 2026-08-24).

Verify-before-disable, MFA-enrollment style: disabling the shared headend
commissioning key for a device must be refused until
Device.servicetekniker_verified_at proves a personal RBAC key actually
authenticated on that device. See Dokumentation/HANDOVER_LOG.md.

Kør (fra headend/):
    python3 -m pytest tests/test_commissioning_key.py -v
"""
import os
import sys
import tempfile
import pathlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import database  # noqa: E402
import commissioning_key  # noqa: E402


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


def _make_device(session, device_id, **overrides):
    device = database.Device(device_id=device_id, app_version="1.0.0", **overrides)
    session.add(device)
    session.commit()
    return device


def test_status_reports_not_yet_verifiable(db_session):
    _make_device(db_session, "TL-TEST0001")
    user = SimpleNamespace(username="admin1", role="admin")

    status = commissioning_key.get_commissioning_key_status("TL-TEST0001", _user=user, db=db_session)

    assert status["disabled"] is False
    assert status["servicetekniker_verified_at"] is None
    assert status["can_disable"] is False


def test_status_can_disable_once_verified(db_session):
    from datetime import datetime, timezone
    _make_device(db_session, "TL-TEST0002", servicetekniker_verified_at=datetime.now(timezone.utc))
    user = SimpleNamespace(username="admin1", role="admin")

    status = commissioning_key.get_commissioning_key_status("TL-TEST0002", _user=user, db=db_session)

    assert status["can_disable"] is True


def test_disable_refused_without_verification_evidence(db_session):
    _make_device(db_session, "TL-TEST0003")
    user = SimpleNamespace(username="admin1", role="admin")

    with pytest.raises(HTTPException) as exc_info:
        commissioning_key.disable_commissioning_key("TL-TEST0003", user=user, db=db_session)

    assert exc_info.value.status_code == 409
    db_session.expire_all()
    device = db_session.query(database.Device).filter_by(device_id="TL-TEST0003").first()
    assert device.commissioning_key_disabled in (None, False)


def test_disable_succeeds_once_verified_and_is_recorded(db_session):
    from datetime import datetime, timezone
    _make_device(db_session, "TL-TEST0004", servicetekniker_verified_at=datetime.now(timezone.utc))
    user = SimpleNamespace(username="admin1", role="admin")

    result = commissioning_key.disable_commissioning_key("TL-TEST0004", user=user, db=db_session)

    assert result["disabled"] is True
    assert result["disabled_by"] == "admin1"
    db_session.expire_all()
    device = db_session.query(database.Device).filter_by(device_id="TL-TEST0004").first()
    assert device.commissioning_key_disabled is True
    assert device.commissioning_key_disabled_by == "admin1"
    assert device.commissioning_key_disabled_at is not None


def test_disable_is_idempotent_once_already_disabled(db_session):
    from datetime import datetime, timezone
    device = _make_device(
        db_session, "TL-TEST0005",
        servicetekniker_verified_at=datetime.now(timezone.utc),
        commissioning_key_disabled=True,
        commissioning_key_disabled_by="admin1",
    )
    user = SimpleNamespace(username="admin2", role="admin")

    result = commissioning_key.disable_commissioning_key("TL-TEST0005", user=user, db=db_session)

    # Re-disabling must not overwrite who originally disabled it.
    assert result["disabled_by"] == "admin1"


def test_status_404_for_unknown_device(db_session):
    user = SimpleNamespace(username="admin1", role="admin")
    with pytest.raises(HTTPException) as exc_info:
        commissioning_key.get_commissioning_key_status("TL-DOES-NOT-EXIST", _user=user, db=db_session)
    assert exc_info.value.status_code == 404
