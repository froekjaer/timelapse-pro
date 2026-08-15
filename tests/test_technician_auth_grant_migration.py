import sqlite3
import time

from edge.technician_auth import TechnicianAuth


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
