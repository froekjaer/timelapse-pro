import sqlite3
import time

from edge.technician_auth import TechnicianAuth
from edge.service_platform import ServicePlatform, TECHNICIAN_CAPABILITIES


def test_technician_auth_purges_legacy_headend_session_tokens(tmp_path):
    db_path = tmp_path / "technician_auth.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE technician_sessions (
            session_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            challenge TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            status TEXT NOT NULL,
            technician_user_id TEXT,
            technician_username TEXT,
            headend_session_token TEXT,
            confirmed_at REAL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO technician_sessions
        (session_id, device_id, challenge, created_at, expires_at, status, headend_session_token)
        VALUES ('s1', 'TL-EDGE-A', 'c1', ?, ?, 'confirmed', 'legacy-headend-session')
        """,
        (time.time(), time.time() + 600),
    )
    conn.commit()
    conn.close()

    TechnicianAuth(db_path, "TL-EDGE-A", "https://headend.example")

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT headend_session_token, edge_service_grant, edge_service_grant_id FROM technician_sessions WHERE session_id='s1'"
    ).fetchone()
    conn.close()
    assert row == (None, None, None)


def test_confirmed_technician_session_uses_edge_service_grant(tmp_path):
    auth = TechnicianAuth(tmp_path / "technician_auth.db", "TL-EDGE-A", "https://headend.example")
    session = auth.create_auth_session(ttl_minutes=15)

    ok = auth.confirm_session(
        session.session_id,
        session.challenge,
        technician_user_id="42",
        technician_username="tech",
        edge_service_grant="grant-token",
        edge_service_grant_id="grant-1",
        edge_service_grant_expires_at=time.time() + 300,
    )

    active = auth.get_active_session(session.session_id)
    assert ok is True
    assert active is not None
    assert active.edge_service_grant == "grant-token"
    assert active.edge_service_grant_id == "grant-1"


def test_expired_edge_service_grant_fails_closed(tmp_path):
    auth = TechnicianAuth(tmp_path / "technician_auth.db", "TL-EDGE-A", "https://headend.example")
    session = auth.create_auth_session(ttl_minutes=15)
    assert auth.confirm_session(
        session.session_id,
        session.challenge,
        technician_user_id="42",
        technician_username="tech",
        edge_service_grant="grant-token",
        edge_service_grant_id="grant-1",
        edge_service_grant_expires_at=time.time() - 1,
    )

    assert auth.get_active_session(session.session_id) is None


def test_grant_status_snapshot_revokes_active_local_session(tmp_path):
    auth = TechnicianAuth(tmp_path / "technician_auth.db", "TL-EDGE-A", "https://headend.example")
    session = auth.create_auth_session(ttl_minutes=15)
    assert auth.confirm_session(
        session.session_id,
        session.challenge,
        technician_user_id="42",
        technician_username="tech",
        edge_service_grant="grant-token",
        edge_service_grant_id="grant-1",
        edge_service_grant_expires_at=time.time() + 300,
    )

    changed = auth.apply_grant_status_snapshot([{"grant_id": "grant-1", "status": "revoked"}])

    assert changed == 1
    assert auth.get_active_session(session.session_id).status == "revoked"


def _active_grant_backed_live_session(tmp_path, grant_id="grant-1"):
    platform = ServicePlatform(state_dir=tmp_path / "service-state")
    cleanup = []
    platform.register_cleanup_handler(
        "LiveViewLease",
        lambda _platform, _session, reason: cleanup.append(("live", reason)),
    )
    platform.register_cleanup_handler(
        "CameraPowerLease",
        lambda _platform, _session, reason: cleanup.append(("camera", reason)),
    )
    service_session = platform.start_session_from_edge_service_grant(
        username="tech",
        role="technician",
        grant_id=grant_id,
        expires_at=time.time() + 300,
        capabilities=TECHNICIAN_CAPABILITIES,
    )
    platform.call("camera.live.start", session=service_session)
    assert platform.status()["live_view"] == "ON"
    assert platform.status()["camera_relay_on"] is True
    return platform, cleanup


def test_central_grant_revoke_invalidates_service_platform_and_physical_leases(tmp_path):
    platform, cleanup = _active_grant_backed_live_session(tmp_path)
    auth = TechnicianAuth(
        tmp_path / "technician_auth.db",
        "TL-EDGE-A",
        "https://headend.example",
        service_platform=platform,
    )
    session = auth.create_auth_session(ttl_minutes=15)
    assert auth.confirm_session(
        session.session_id,
        session.challenge,
        technician_user_id="42",
        technician_username="tech",
        edge_service_grant="grant-token",
        edge_service_grant_id="grant-1",
        edge_service_grant_expires_at=time.time() + 300,
    )

    changed = auth.apply_grant_status_snapshot([{"grant_id": "grant-1", "status": "revoked"}])

    status = platform.status()
    assert changed == 1
    assert cleanup == [("live", "grant_revoked"), ("camera", "grant_revoked")]
    assert status["logged_in"] is False
    assert status["live_view"] == "OFF"
    assert status["camera_relay_on"] is False


def test_central_grant_expiry_invalidates_service_platform_and_physical_leases(tmp_path):
    platform, cleanup = _active_grant_backed_live_session(tmp_path)
    auth = TechnicianAuth(
        tmp_path / "technician_auth.db",
        "TL-EDGE-A",
        "https://headend.example",
        service_platform=platform,
    )
    session = auth.create_auth_session(ttl_minutes=15)
    assert auth.confirm_session(
        session.session_id,
        session.challenge,
        technician_user_id="42",
        technician_username="tech",
        edge_service_grant="grant-token",
        edge_service_grant_id="grant-1",
        edge_service_grant_expires_at=time.time() - 1,
    )

    assert auth.get_active_session(session.session_id) is None

    status = platform.status()
    assert cleanup == [("live", "grant_expired"), ("camera", "grant_expired")]
    assert status["logged_in"] is False
    assert status["live_view"] == "OFF"
    assert status["camera_relay_on"] is False
