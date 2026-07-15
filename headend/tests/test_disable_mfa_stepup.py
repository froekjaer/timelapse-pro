from types import SimpleNamespace

import pyotp
import pytest

import main


class _Query:
    def __init__(self, target):
        self.target = target

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.target


class _DB:
    def __init__(self, target=None):
        self.target = target
        self.commits = 0

    def query(self, _model):
        return _Query(self.target)

    def commit(self):
        self.commits += 1


def _user(*, user_id=1, role="viewer", mfa=True):
    return SimpleNamespace(
        id=user_id,
        username=f"user-{user_id}",
        role=role,
        password_hash="valid-hash",
        mfa_enabled=mfa,
        totp_secret=pyotp.random_base32() if mfa else None,
    )


def test_disable_mfa_requires_fresh_password(monkeypatch):
    user = _user()
    monkeypatch.setattr(main, "_verify_password", lambda *_args: False)
    with pytest.raises(main.HTTPException) as exc:
        main.disable_mfa({}, current_user=user, db=_DB())
    assert exc.value.status_code == 403


def test_disable_mfa_requires_current_totp(monkeypatch):
    user = _user()
    monkeypatch.setattr(main, "_verify_password", lambda *_args: True)
    with pytest.raises(main.HTTPException) as exc:
        main.disable_mfa({"current_password": "correct", "totp_code": "000000"}, current_user=user, db=_DB())
    assert exc.value.status_code == 403


def test_admin_cannot_disable_another_users_mfa(monkeypatch):
    admin = _user(role="admin")
    monkeypatch.setattr(main, "_verify_password", lambda *_args: True)
    with pytest.raises(main.HTTPException) as exc:
        main.disable_mfa({"user_id": 2}, current_user=admin, db=_DB(_user(user_id=2)))
    assert exc.value.status_code == 403


def test_successful_stepup_disables_mfa_and_records_siem(monkeypatch):
    user = _user()
    events = []
    monkeypatch.setattr(main, "_verify_password", lambda *_args: True)
    monkeypatch.setattr(main, "_siem_record_events", lambda db, device_id, payload: events.extend(payload))
    code = pyotp.TOTP(user.totp_secret).now()
    db = _DB()

    result = main.disable_mfa(
        {"current_password": "correct", "totp_code": code},
        current_user=user,
        db=db,
    )

    assert result == {"ok": True}
    assert user.mfa_enabled is False
    assert user.totp_secret is None
    assert events[0]["event_type"] == "mfa_disabled"
    assert events[0]["username"] == user.username


def test_admin_mfa_reset_requires_fresh_password(monkeypatch):
    admin = _user(role="super_admin")
    monkeypatch.setattr(main, "_verify_password", lambda *_args: False)

    with pytest.raises(main.HTTPException) as exc:
        main.reset_user_mfa(2, {}, current_user=admin, db=_DB(_user(user_id=2)))

    assert exc.value.status_code == 403


def test_successful_admin_mfa_reset_records_siem(monkeypatch):
    admin = _user(role="super_admin")
    target = _user(user_id=2)
    events = []
    monkeypatch.setattr(main, "_verify_password", lambda *_args: True)
    monkeypatch.setattr(main, "_siem_record_events", lambda db, device_id, payload: events.extend(payload))
    monkeypatch.setattr(main, "_mfa_required_for_user", lambda db, user: False)
    code = pyotp.TOTP(admin.totp_secret).now()
    db = _DB(target)

    result = main.reset_user_mfa(
        target.id,
        {"current_password": "correct", "totp_code": code},
        current_user=admin,
        db=db,
    )

    assert result["ok"] is True
    assert result["user_id"] == target.id
    assert target.mfa_enabled is False
    assert target.totp_secret is None
    assert events[0]["event_type"] == "mfa_reset"
    assert events[0]["username"] == admin.username
