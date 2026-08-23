"""Regression tests for C-06 (MASTER_REVIEW_CLOSURE_2026-08-15.md): the
break-glass audit actor must be bound to the authenticated session, never to
a client-supplied `admin_username` field in the request body.

Before the fix, both create_break_glass() and checkout_break_glass() trusted
payload["admin_username"] outright — any admin could create or check out a
break-glass account under another admin's name, and that false identity was
written into the ownership/audit fields (admin_username, last_used_by,
rotation_reason). This directly contradicts the documented ownership model
on BreakGlassAccount ("Én konto pr. device pr. admin" / "Ejerskab: hvilken
admin-konto der har adgang til denne instans" — see headend/database.py).
"""
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

import cmdb
from cmdb import create_break_glass, checkout_break_glass
from database import BreakGlassAccount


@pytest.fixture(autouse=True)
def _break_glass_enc_key(monkeypatch):
    monkeypatch.setenv("BREAK_GLASS_ENC_KEY", Fernet.generate_key().decode())


def _platform_admin(username: str) -> MagicMock:
    return MagicMock(username=username, role="super_admin", customer_id=None)


def test_create_break_glass_ignores_client_supplied_admin_username():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None  # no existing account
    caller = _platform_admin("real-admin")

    result = create_break_glass(
        "TL-TESTDEVICE0001",
        {"admin_username": "impostor-admin", "expires_days": 0},
        _user=caller,
        db=db,
    )

    assert result["admin_username"] == "real-admin"
    created_account = db.add.call_args.args[0]
    assert created_account.admin_username == "real-admin"


def test_checkout_break_glass_records_authenticated_caller_not_payload_claim():
    account = BreakGlassAccount(
        device_id="TL-TESTDEVICE0001",
        admin_username="real-admin",
        ssh_username="emergency",
        password_enc=cmdb._encrypt("initial-password"),
        rotation_reason="initial",
    )
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = account
    caller = _platform_admin("real-admin")

    checkout_break_glass(
        "TL-TESTDEVICE0001",
        {"admin_username": "impostor-admin", "reason": "incident-123"},
        request=None,
        _user=caller,
        db=db,
    )

    assert account.last_used_by == "real-admin"
    assert "real-admin" in account.rotation_reason
    assert "impostor-admin" not in account.rotation_reason


def test_checkout_break_glass_looks_up_the_callers_own_account():
    """A caller can only ever check out the account matching their own
    username — payload["admin_username"] is no longer consulted."""
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    caller = _platform_admin("real-admin")

    with pytest.raises(Exception) as exc_info:
        checkout_break_glass(
            "TL-TESTDEVICE0001",
            {"admin_username": "someone-elses-account", "reason": "test"},
            request=None,
            _user=caller,
            db=db,
        )

    assert getattr(exc_info.value, "status_code", None) == 404
    # The lookup was performed for the caller's own identity, not the payload claim.
    filter_kwargs = db.query.return_value.filter_by.call_args.kwargs
    assert filter_kwargs["admin_username"] == "real-admin"
