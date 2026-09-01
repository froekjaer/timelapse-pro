"""Edge communication debug logger (headend/api/edge_communication_debug_api.py)
used to write a row to edge_api_communication_logs for EVERY Edge API call,
for every device, forever — unconditional, unbounded DB writes as the fleet
grows. Peter (2026-08-31): only log while an explicit, time- and/or
count-bounded "capture session" is active; everything outside a session must
cost nothing (no DB write, ideally no body-parsing either).
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

import database
from api.edge_communication_debug_api import (
    _any_capture_session_might_be_active,
    _match_active_capture_session,
    capture_status,
    clear_communications,
    install_edge_communication_logger,
    start_capture,
    stop_capture,
)


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


def _admin():
    return SimpleNamespace(username="admin1", role="admin")


def test_start_requires_a_bound(db_session):
    with pytest.raises(HTTPException) as exc:
        start_capture(device_id=None, duration_minutes=None, max_packets=None, _user=_admin(), db=db_session)
    assert exc.value.status_code == 400


def test_start_then_conflict_on_second_global_session(db_session):
    start_capture(device_id=None, duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    with pytest.raises(HTTPException) as exc:
        start_capture(device_id="TL-X", duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    assert exc.value.status_code == 409


def test_idle_headend_has_no_active_session(db_session):
    assert _any_capture_session_might_be_active(db_session) is False


def test_starting_a_session_makes_it_active(db_session):
    start_capture(device_id="TL-X", duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    assert _any_capture_session_might_be_active(db_session) is True


def test_session_matches_only_its_own_device(db_session):
    start_capture(device_id="TL-X", duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    assert _match_active_capture_session(db_session, "TL-X") is not None
    assert _match_active_capture_session(db_session, "TL-OTHER") is None


def test_global_session_matches_every_device(db_session):
    start_capture(device_id=None, duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    assert _match_active_capture_session(db_session, "TL-ANY") is not None


def test_manual_stop_deactivates_session(db_session):
    session = start_capture(device_id=None, duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    stop_capture(session["id"], _user=_admin(), db=db_session)
    assert _any_capture_session_might_be_active(db_session) is False


def test_max_packets_bound_expires_after_limit(db_session):
    session_row = start_capture(device_id="TL-X", duration_minutes=None, max_packets=2, _user=_admin(), db=db_session)
    row = db_session.get(database.EdgeCommunicationCaptureSession, session_row["id"])
    row.packet_count = 2
    db_session.commit()
    assert _match_active_capture_session(db_session, "TL-X") is None


def test_capture_status_lists_recent_sessions(db_session):
    start_capture(device_id="TL-X", duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    rows = capture_status(_user=_admin(), db=db_session)
    assert len(rows) == 1
    assert rows[0]["device_id"] == "TL-X"
    assert rows[0]["active"] is True


def _make_log_row(db, device_id="TL-X", transport_security="encrypted"):
    row = database.EdgeApiCommunicationLog(
        device_id=device_id,
        method="GET",
        path="/api/config/" + device_id,
        transport_security=transport_security,
    )
    db.add(row)
    db.commit()
    return row


def test_clear_with_no_filter_removes_everything(db_session):
    _make_log_row(db_session, device_id="TL-X")
    _make_log_row(db_session, device_id="TL-Y")
    result = clear_communications(device_id=None, transport_security=None, _user=_admin(), db=db_session)
    assert result["deleted"] == 2
    assert db_session.query(database.EdgeApiCommunicationLog).count() == 0


def test_clear_respects_device_filter(db_session):
    _make_log_row(db_session, device_id="TL-X")
    _make_log_row(db_session, device_id="TL-Y")
    result = clear_communications(device_id="TL-X", transport_security=None, _user=_admin(), db=db_session)
    assert result["deleted"] == 1
    remaining = db_session.query(database.EdgeApiCommunicationLog).all()
    assert len(remaining) == 1
    assert remaining[0].device_id == "TL-Y"


def test_clear_respects_transport_filter(db_session):
    _make_log_row(db_session, device_id="TL-X", transport_security="encrypted")
    _make_log_row(db_session, device_id="TL-X", transport_security="unencrypted")
    result = clear_communications(device_id=None, transport_security="unencrypted", _user=_admin(), db=db_session)
    assert result["deleted"] == 1
    remaining = db_session.query(database.EdgeApiCommunicationLog).all()
    assert len(remaining) == 1
    assert remaining[0].transport_security == "encrypted"


def test_clear_does_not_touch_capture_sessions(db_session):
    _make_log_row(db_session, device_id="TL-X")
    start_capture(device_id="TL-X", duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)
    clear_communications(device_id=None, transport_security=None, _user=_admin(), db=db_session)
    assert _any_capture_session_might_be_active(db_session) is True


def _fake_request(path: str, method: str = "GET") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": Headers({}).raw,
        "client": ("192.168.1.50", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "app": None,
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_middleware_skips_db_write_with_no_active_session(db_session, monkeypatch):
    monkeypatch.setattr("api.edge_communication_debug_api.SessionLocal", database.SessionLocal)
    captured = {}

    class _App:
        def middleware(self, _kind):
            def _decorator(fn):
                captured["handler"] = fn
                return fn
            return _decorator

    install_edge_communication_logger(_App())
    handler = captured["handler"]

    async def call_next(_request):
        return SimpleNamespace(status_code=200)

    request = _fake_request("/api/config/TL-X")
    asyncio.run(handler(request, call_next))

    count = db_session.query(database.EdgeApiCommunicationLog).count()
    assert count == 0


def test_middleware_logs_and_increments_packet_count_during_active_session(db_session, monkeypatch):
    monkeypatch.setattr("api.edge_communication_debug_api.SessionLocal", database.SessionLocal)
    session_row = start_capture(device_id="TL-X", duration_minutes=None, max_packets=5, _user=_admin(), db=db_session)

    captured = {}

    class _App:
        def middleware(self, _kind):
            def _decorator(fn):
                captured["handler"] = fn
                return fn
            return _decorator

    install_edge_communication_logger(_App())
    handler = captured["handler"]

    async def call_next(_request):
        return SimpleNamespace(status_code=200)

    request = _fake_request("/api/config/TL-X")
    asyncio.run(handler(request, call_next))

    count = db_session.query(database.EdgeApiCommunicationLog).count()
    assert count == 1
    row = db_session.get(database.EdgeCommunicationCaptureSession, session_row["id"])
    assert row.packet_count == 1


def test_middleware_does_not_log_unrelated_device_under_scoped_session(db_session, monkeypatch):
    monkeypatch.setattr("api.edge_communication_debug_api.SessionLocal", database.SessionLocal)
    start_capture(device_id="TL-X", duration_minutes=5, max_packets=None, _user=_admin(), db=db_session)

    captured = {}

    class _App:
        def middleware(self, _kind):
            def _decorator(fn):
                captured["handler"] = fn
                return fn
            return _decorator

    install_edge_communication_logger(_App())
    handler = captured["handler"]

    async def call_next(_request):
        return SimpleNamespace(status_code=200)

    request = _fake_request("/api/config/TL-OTHER")
    asyncio.run(handler(request, call_next))

    count = db_session.query(database.EdgeApiCommunicationLog).count()
    assert count == 0
