"""Tests for the formal "help a colleague who can't reach the central system"
break-glass procedure (Peter, 2026-08-20, following C-06's audit-actor fix in
PR #82): an admin can still only check out THEIR OWN break-glass account
(unchanged from C-06 — no impersonation), but can now record an optional,
purely informational on_behalf_of note, and every checkout is now permanently
recorded in BreakGlassCheckoutAudit rather than only the latest one being
visible on the account row.
"""
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

import cmdb
from cmdb import checkout_break_glass, list_break_glass_checkout_history
from database import Base, BreakGlassAccount, BreakGlassCheckoutAudit, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-BGDELEGATION"


@pytest.fixture(autouse=True)
def _break_glass_enc_key(monkeypatch):
    monkeypatch.setenv("BREAK_GLASS_ENC_KEY", Fernet.generate_key().decode())


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.query(BreakGlassCheckoutAudit).filter_by(device_id=DEVICE_ID).delete()
    session.query(BreakGlassAccount).filter_by(device_id=DEVICE_ID).delete()
    session.commit()
    try:
        yield session
    finally:
        session.query(BreakGlassCheckoutAudit).filter_by(device_id=DEVICE_ID).delete()
        session.query(BreakGlassAccount).filter_by(device_id=DEVICE_ID).delete()
        session.commit()
        session.close()


def _platform_admin(username: str) -> MagicMock:
    return MagicMock(username=username, role="super_admin", customer_id=None)


def _seed_account(db_session, admin_username: str) -> BreakGlassAccount:
    account = BreakGlassAccount(
        device_id=DEVICE_ID,
        admin_username=admin_username,
        ssh_username="emergency",
        password_enc=cmdb._encrypt("initial-password"),
        rotation_reason="initial",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def test_checkout_records_on_behalf_of_in_permanent_history(db_session):
    _seed_account(db_session, "colleague-admin")
    caller = _platform_admin("colleague-admin")

    checkout_break_glass(
        DEVICE_ID,
        {"reason": "Site-teknikeren kan ikke nå centralt system", "on_behalf_of": "Peter (on-site, ingen VPN)"},
        request=None,
        _user=caller,
        db=db_session,
    )

    history = list_break_glass_checkout_history(DEVICE_ID, _user=caller, db=db_session)
    assert len(history) == 1
    assert history[0]["checked_out_by"] == "colleague-admin"
    assert history[0]["on_behalf_of"] == "Peter (on-site, ingen VPN)"
    assert "kan ikke nå centralt system" in history[0]["reason"]


def test_on_behalf_of_is_optional_and_defaults_to_none(db_session):
    _seed_account(db_session, "colleague-admin")
    caller = _platform_admin("colleague-admin")

    checkout_break_glass(
        DEVICE_ID,
        {"reason": "Rutine-adgang"},
        request=None,
        _user=caller,
        db=db_session,
    )

    history = list_break_glass_checkout_history(DEVICE_ID, _user=caller, db=db_session)
    assert history[0]["on_behalf_of"] is None


def test_history_survives_password_rotation_across_multiple_checkouts(db_session):
    """BreakGlassAccount.last_used_by/rotation_reason only ever hold the LATEST
    checkout — this is exactly the gap the audit table closes."""
    _seed_account(db_session, "colleague-admin")
    caller = _platform_admin("colleague-admin")

    checkout_break_glass(DEVICE_ID, {"reason": "Første besøg", "on_behalf_of": "A"}, request=None, _user=caller, db=db_session)
    checkout_break_glass(DEVICE_ID, {"reason": "Andet besøg", "on_behalf_of": "B"}, request=None, _user=caller, db=db_session)

    history = list_break_glass_checkout_history(DEVICE_ID, _user=caller, db=db_session)
    assert len(history) == 2
    # Most recent first.
    assert history[0]["on_behalf_of"] == "B"
    assert history[1]["on_behalf_of"] == "A"


def test_checkout_still_only_resolves_callers_own_account_when_helping_a_colleague(db_session):
    """Even when explicitly helping a named colleague, the account looked up
    and checked out is still the CALLER's own — on_behalf_of never changes
    which credential is retrieved. This is the C-06 guarantee, preserved."""
    _seed_account(db_session, "colleague-admin")
    caller = _platform_admin("someone-else")

    with pytest.raises(Exception) as exc_info:
        checkout_break_glass(
            DEVICE_ID,
            {"reason": "test", "on_behalf_of": "colleague-admin"},
            request=None,
            _user=caller,
            db=db_session,
        )

    assert getattr(exc_info.value, "status_code", None) == 404
