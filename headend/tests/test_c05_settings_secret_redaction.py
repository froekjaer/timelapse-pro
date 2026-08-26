"""Regression tests for C-05 (MASTER_REVIEW_CLOSURE_2026-08-15.md): GET
/api/admin/settings returned every row of the flat `settings` table verbatim,
including secret-shaped values like sftp_password and bt_totp_secret, to any
caller with role=admin (not even super_admin). Any tenant admin could read
system-wide credentials in plaintext.

Fix: secret-shaped keys (password/secret/token/api_key/apikey/private_key
substring match) are masked to '••••••••' on readback. PUT skips writing a
secret key back if the submitted value is exactly that mask — so the admin
settings form can round-trip other fields without blanking/overwriting an
existing secret with the placeholder.
"""
import pytest

# get_settings/update_settings moved to api/admin_settings_api.py (2026-08-26,
# Phase 1 of the main.py modularization plan).
from api.admin_settings_api import get_settings, update_settings
from database import Base, Settings, SessionLocal, engine

_KEYS = ["sftp_password", "bt_totp_secret", "sftp_host", "bt_totp_sid"]


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.query(Settings).filter(Settings.key.in_(_KEYS)).delete(synchronize_session=False)
    session.commit()
    session.add_all([
        Settings(key="sftp_password", value="hunter2-real-password"),
        Settings(key="bt_totp_secret", value="JBSWY3DPEHPK3PXPREAL"),
        Settings(key="sftp_host", value="sftp.example.com"),
        Settings(key="bt_totp_sid", value="cam-abcd1234"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.query(Settings).filter(Settings.key.in_(_KEYS)).delete(synchronize_session=False)
        session.commit()
        session.close()


def test_get_settings_masks_secret_shaped_keys(db_session):
    result = get_settings(_user=None, db=db_session)
    assert result["sftp_password"] == "••••••••"
    assert result["bt_totp_secret"] == "••••••••"


def test_get_settings_leaves_non_secret_keys_untouched(db_session):
    result = get_settings(_user=None, db=db_session)
    assert result["sftp_host"] == "sftp.example.com"
    assert result["bt_totp_sid"] == "cam-abcd1234"


def test_put_settings_skips_masked_placeholder_for_secret_key(db_session):
    update_settings({"sftp_password": "••••••••", "sftp_host": "new.example.com"}, _user=None, db=db_session)
    row = db_session.query(Settings).filter_by(key="sftp_password").first()
    assert row.value == "hunter2-real-password"
    row2 = db_session.query(Settings).filter_by(key="sftp_host").first()
    assert row2.value == "new.example.com"


def test_put_settings_still_allows_a_real_new_secret_value(db_session):
    update_settings({"sftp_password": "a-genuinely-new-password"}, _user=None, db=db_session)
    row = db_session.query(Settings).filter_by(key="sftp_password").first()
    assert row.value == "a-genuinely-new-password"
