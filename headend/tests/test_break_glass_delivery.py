"""
Contract tests for the break-glass password delivery fix (2026-08-25).

Peter's design decision: keep the password-based BreakGlassAccount design
(not the abandoned pubkey-only PR #9), accepting that a password can only be
delivered to a device on its own next successful sync — not an instant
out-of-band push to a possibly-unreachable device. This fixes the checkout
rotation-race that made the whole feature structurally unusable (rotating
password_enc BEFORE the previous value was ever confirmed applied), and
wires actual delivery through the consolidated sync poll.

Kør (fra headend/):
    python3 -m pytest tests/test_break_glass_delivery.py -v
"""
import hashlib
import os
import sys
import tempfile
import pathlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")
os.environ.setdefault("BREAK_GLASS_ENC_KEY", "KY5Px2eBK4oPk41uP6-wjodRcUhmg8NdC2Xj6R5V0mM=")

import database  # noqa: E402
import cmdb  # noqa: E402
import main  # noqa: E402
import edge_sync  # noqa: E402
from edge_sync import EdgeSyncRequest, edge_sync as edge_sync_endpoint  # noqa: E402


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


def _admin_user(username="admin1"):
    return SimpleNamespace(username=username, role="super_admin", customer_id=None)


def test_checkout_returns_current_password_and_flags_unapplied_on_first_checkout(db_session):
    _make_device(db_session, "TL-BG0001")
    user = _admin_user()

    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        created = cmdb.create_break_glass("TL-BG0001", {}, _user=user, db=db_session)
        result = cmdb.checkout_break_glass(
            "TL-BG0001", {"reason": "test"}, request=None, _user=user, db=db_session,
        )

    assert result["applied"] is False
    assert "ADVARSEL" in result["warning"]
    assert result["password"]

    account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
    # 2026-08-25 (second live incident, same night): a plain checkout must
    # NOT rotate — it did originally, which silently invalidated the shown
    # password within one sync interval (Peter hit this exact race live).
    # The returned password must be exactly what's stored, unchanged.
    assert cmdb._decrypt(account.password_enc) == result["password"]
    assert account.applied_at is None


def test_checkout_without_rotate_is_idempotent_across_repeated_calls(db_session):
    """The core regression this fixes: checkout must be safe to call
    repeatedly (e.g. an admin re-opening the page) without ever changing
    the password that's actually live on the device."""
    _make_device(db_session, "TL-BG0001b")
    user = _admin_user()

    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        created = cmdb.create_break_glass("TL-BG0001b", {}, _user=user, db=db_session)
        account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
        account.applied_at = datetime.now(timezone.utc)
        db_session.commit()

        first = cmdb.checkout_break_glass(
            "TL-BG0001b", {"reason": "test"}, request=None, _user=user, db=db_session,
        )
        second = cmdb.checkout_break_glass(
            "TL-BG0001b", {"reason": "test again"}, request=None, _user=user, db=db_session,
        )

    assert first["password"] == second["password"]
    assert first["rotated"] is False
    assert second["rotated"] is False


def test_checkout_with_rotate_generates_a_fresh_password_and_flags_unapplied(db_session):
    _make_device(db_session, "TL-BG0001c")
    user = _admin_user()

    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        created = cmdb.create_break_glass("TL-BG0001c", {}, _user=user, db=db_session)
        account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
        account.applied_at = datetime.now(timezone.utc)
        db_session.commit()
        previous_password = cmdb._decrypt(account.password_enc)

        result = cmdb.checkout_break_glass(
            "TL-BG0001c", {"reason": "test", "rotate": True}, request=None, _user=user, db=db_session,
        )

    assert result["rotated"] is True
    assert result["applied"] is False
    assert result["password"] != previous_password

    db_session.expire_all()
    account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
    # The returned password must always be exactly what got persisted —
    # never a stale value from before the rotation.
    assert cmdb._decrypt(account.password_enc) == result["password"]
    assert account.applied_at is None


def test_checkout_does_not_warn_once_previous_password_was_confirmed_applied(db_session):
    _make_device(db_session, "TL-BG0002")
    user = _admin_user()

    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        created = cmdb.create_break_glass("TL-BG0002", {}, _user=user, db=db_session)

    account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
    account.applied_at = datetime.now(timezone.utc)
    db_session.commit()

    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        result = cmdb.checkout_break_glass(
            "TL-BG0002", {"reason": "test"}, request=None, _user=user, db=db_session,
        )

    assert result["applied"] is True
    assert "ADVARSEL" not in result["warning"]


def test_checkout_never_returns_a_password_that_was_never_shown(db_session):
    """Regression guard, rewritten 2026-08-25 (second incident): the
    original bug was rotating password_enc BEFORE the previous value was
    confirmed applied. The second bug was rotating password_enc on EVERY
    checkout regardless of request, which — because edge_sync delivers any
    unapplied row on the device's very next sync — silently invalidated the
    password an admin was just shown within about a minute. Both bugs share
    one invariant this test checks directly rather than via source-text
    matching: whatever password_enc holds right after checkout returns is
    always exactly what was returned, never a value the caller never saw."""
    _make_device(db_session, "TL-BG0001d")
    user = _admin_user()

    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        created = cmdb.create_break_glass("TL-BG0001d", {}, _user=user, db=db_session)
        account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
        account.applied_at = datetime.now(timezone.utc)
        db_session.commit()

        for payload in ({"reason": "plain"}, {"reason": "rotate", "rotate": True}):
            result = cmdb.checkout_break_glass(
                "TL-BG0001d", payload, request=None, _user=user, db=db_session,
            )
            db_session.expire_all()
            account = db_session.query(database.BreakGlassAccount).filter_by(id=created["id"]).first()
            assert cmdb._decrypt(account.password_enc) == result["password"]


@pytest.mark.asyncio
async def test_edge_sync_includes_pending_break_glass_password(db_session):
    device = _make_device(db_session, "TL-BG0003")
    user = _admin_user()
    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        cmdb.create_break_glass("TL-BG0003", {}, _user=user, db=db_session)

    req = EdgeSyncRequest(timestamp="t", diagnostics={}, capture_stats={}, siem_events=[], inventory=None)
    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        result = await edge_sync_endpoint("TL-BG0003", req, _auth=None, db=db_session)

    assert len(result["break_glass"]) == 1
    assert result["break_glass"][0]["username"] == "emergency"
    assert result["break_glass"][0]["password"]


@pytest.mark.asyncio
async def test_edge_sync_marks_applied_when_hash_matches(db_session):
    _make_device(db_session, "TL-BG0004")
    user = _admin_user()
    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        cmdb.create_break_glass("TL-BG0004", {}, _user=user, db=db_session)

    account = db_session.query(database.BreakGlassAccount).filter_by(device_id="TL-BG0004").first()
    plaintext = cmdb._decrypt(account.password_enc)
    correct_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    req = EdgeSyncRequest(
        timestamp="t",
        diagnostics={"security": {"break_glass_applied": [{"username": "emergency", "password_sha256": correct_hash}]}},
        capture_stats={}, siem_events=[], inventory=None,
    )
    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        await edge_sync_endpoint("TL-BG0004", req, _auth=None, db=db_session)

    db_session.expire_all()
    account = db_session.query(database.BreakGlassAccount).filter_by(device_id="TL-BG0004").first()
    assert account.applied_at is not None


@pytest.mark.asyncio
async def test_edge_sync_does_not_mark_applied_when_hash_is_wrong(db_session):
    """Safety: a bogus/stale confirmation must never falsely mark a
    password as applied — that would make checkout show a password that
    silently doesn't work."""
    _make_device(db_session, "TL-BG0005")
    user = _admin_user()
    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        cmdb.create_break_glass("TL-BG0005", {}, _user=user, db=db_session)

    req = EdgeSyncRequest(
        timestamp="t",
        diagnostics={"security": {"break_glass_applied": [{"username": "emergency", "password_sha256": "deadbeef"}]}},
        capture_stats={}, siem_events=[], inventory=None,
    )
    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        await edge_sync_endpoint("TL-BG0005", req, _auth=None, db=db_session)

    db_session.expire_all()
    account = db_session.query(database.BreakGlassAccount).filter_by(device_id="TL-BG0005").first()
    assert account.applied_at is None


@pytest.mark.asyncio
async def test_edge_sync_survives_an_undecryptable_break_glass_row(db_session):
    """2026-08-25 incident: a pre-existing account.password_enc that can't
    be decrypted with the currently-configured BREAK_GLASS_ENC_KEY (e.g.
    from before a key rotation) took down sync for EVERY device for ~10
    minutes — one bad row, no error handling, crashed the whole endpoint.
    Must never happen again: a broken row is skipped, sync still succeeds
    with whatever remains."""
    _make_device(db_session, "TL-BG0007")
    user = _admin_user()
    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        cmdb.create_break_glass("TL-BG0007", {}, _user=user, db=db_session)
    account = db_session.query(database.BreakGlassAccount).filter_by(device_id="TL-BG0007").first()
    account.password_enc = "not-a-valid-fernet-token"
    db_session.commit()

    req = EdgeSyncRequest(timestamp="t", diagnostics={}, capture_stats={}, siem_events=[], inventory=None)
    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        result = await edge_sync_endpoint("TL-BG0007", req, _auth=None, db=db_session)

    assert result["server_time"] == "t"
    assert result["break_glass"] == []


@pytest.mark.asyncio
async def test_edge_sync_omits_break_glass_once_applied(db_session):
    _make_device(db_session, "TL-BG0006")
    user = _admin_user()
    with patch.object(cmdb, "_enforce_break_glass_policy", MagicMock()):
        cmdb.create_break_glass("TL-BG0006", {}, _user=user, db=db_session)
    account = db_session.query(database.BreakGlassAccount).filter_by(device_id="TL-BG0006").first()
    account.applied_at = datetime.now(timezone.utc)
    db_session.commit()

    req = EdgeSyncRequest(timestamp="t", diagnostics={}, capture_stats={}, siem_events=[], inventory=None)
    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        result = await edge_sync_endpoint("TL-BG0006", req, _auth=None, db=db_session)

    assert result["break_glass"] == []
