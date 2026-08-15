"""
TimeLapse Pro — Technician Authentication

Provides technician login flow via QR code when edge has network connectivity.
Technician scans QR code → redirected to headend login → auth token sent to edge.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import qrcode
except ImportError:  # pragma: no cover - QR rendering is optional for session-store tests.
    qrcode = None

log = logging.getLogger(__name__)


@dataclass
class AuthSession:
    """Pending technician auth session waiting for headend confirmation."""
    session_id: str
    device_id: str
    challenge: str
    created_at: float
    expires_at: float
    status: str  # pending, confirmed, expired
    technician_user_id: Optional[str] = None
    technician_username: Optional[str] = None
    edge_service_grant: Optional[str] = None
    edge_service_grant_id: Optional[str] = None
    edge_service_grant_expires_at: Optional[float] = None


class TechnicianAuth:
    """
    Manages technician authentication sessions on edge.

    Flow:
      1. Edge generates auth challenge with QR code
      2. Technician scans QR → headend login
      3. Headend confirms auth → edge receives session
      4. Technician gains local access
    """

    def __init__(self, db_path: Path | str, device_id: str, headend_url: str):
        self._db_path = Path(db_path)
        self._device_id = device_id
        self._headend_url = headend_url.rstrip("/")
        self._lock = threading.Lock()
        self._sessions: dict[str, AuthSession] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database for auth sessions."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS technician_sessions (
                session_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                challenge TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                status TEXT NOT NULL,
                technician_user_id TEXT,
                technician_username TEXT,
                headend_session_token TEXT,
                edge_service_grant TEXT,
                edge_service_grant_id TEXT,
                edge_service_grant_expires_at REAL,
                confirmed_at REAL
            )
        """)
        for ddl in (
            "ALTER TABLE technician_sessions ADD COLUMN edge_service_grant TEXT",
            "ALTER TABLE technician_sessions ADD COLUMN edge_service_grant_id TEXT",
            "ALTER TABLE technician_sessions ADD COLUMN edge_service_grant_expires_at REAL",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        conn.execute("UPDATE technician_sessions SET headend_session_token = NULL WHERE headend_session_token IS NOT NULL")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_expires
            ON technician_sessions(status, expires_at)
        """)
        conn.commit()
        conn.close()

    def _generate_challenge(self) -> str:
        """Generate secure random challenge token."""
        return secrets.token_urlsafe(32)

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return uuid.uuid4().hex

    def create_auth_session(self, ttl_minutes: int = 15) -> AuthSession:
        """
        Create a new authentication session for technician login.

        Args:
            ttl_minutes: Session time-to-live in minutes

        Returns:
            AuthSession with QR code data
        """
        session_id = self._generate_session_id()
        challenge = self._generate_challenge()
        now = time.time()
        expires_at = now + (ttl_minutes * 60)

        session = AuthSession(
            session_id=session_id,
            device_id=self._device_id,
            challenge=challenge,
            created_at=now,
            expires_at=expires_at,
            status="pending",
        )

        with self._lock:
            self._sessions[session_id] = session
            # Persist to DB
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            conn.execute(
                """
                INSERT INTO technician_sessions
                (session_id, device_id, challenge, created_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, self._device_id, challenge, now, expires_at, "pending"),
            )
            conn.commit()
            conn.close()

        log.info("Created technician auth session: %s (expires: %.0f min)", session_id[:8], ttl_minutes)
        return session

    def get_auth_url(self, session: AuthSession) -> str:
        """
        Generate headend auth URL for QR code.

        URL format: {headend_url}/technician/auth/{session_id}?challenge={challenge}
        """
        return f"{self._headend_url}/technician/auth/{session.session_id}?challenge={session.challenge}"

    def generate_qr_code(self, session: AuthSession) -> tuple[str, str]:
        """
        Generate QR code for technician auth.

        Returns:
            (qr_code_data_uri, auth_url)
        """
        import io

        if qrcode is None:
            raise RuntimeError("qrcode package is required to render technician auth QR codes")
        auth_url = self.get_auth_url(session)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(auth_url)
        qr.make(fit=True)

        # Create PNG
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        # Convert to base64 data URI
        import base64
        data_uri = f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"

        return data_uri, auth_url

    def confirm_session(
        self,
        session_id: str,
        expected_challenge: str,
        technician_user_id: str,
        technician_username: str,
        edge_service_grant: str,
        edge_service_grant_id: str | None = None,
        edge_service_grant_expires_at: float | None = None,
    ) -> bool:
        """
        Confirm an auth session from headend callback.

        Returns True if session confirmed successfully.
        """
        with self._lock:
            session = self._sessions.get(session_id)

            if not session:
                # Try loading from DB
                conn = sqlite3.connect(str(self._db_path), timeout=30.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM technician_sessions
                    WHERE session_id = ? AND status = 'pending' AND expires_at > ?
                    """,
                    (session_id, time.time()),
                )
                row = cursor.fetchone()
                conn.close()

                if not row:
                    log.warning("Auth session not found or expired: %s", session_id[:8])
                    return False

                session = AuthSession(
                    session_id=row["session_id"],
                    device_id=row["device_id"],
                    challenge=row["challenge"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    status=row["status"],
                )
                self._sessions[session_id] = session

            # Verify challenge
            if not hmac.compare_digest(session.challenge, expected_challenge):
                log.warning("Auth challenge mismatch for session: %s", session_id[:8])
                return False

            if session.status != "pending":
                log.warning("Auth session not in pending state: %s (%s)", session_id[:8], session.status)
                return False

            if time.time() > session.expires_at:
                log.warning("Auth session expired: %s", session_id[:8])
                return False

            # Update session
            session.status = "confirmed"
            session.technician_user_id = technician_user_id
            session.technician_username = technician_username
            session.edge_service_grant = edge_service_grant
            session.edge_service_grant_id = edge_service_grant_id
            session.edge_service_grant_expires_at = edge_service_grant_expires_at

            # Persist to DB
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            conn.execute(
                """
                UPDATE technician_sessions
                SET status = 'confirmed',
                    technician_user_id = ?,
                    technician_username = ?,
                    headend_session_token = NULL,
                    edge_service_grant = ?,
                    edge_service_grant_id = ?,
                    edge_service_grant_expires_at = ?,
                    confirmed_at = ?
                WHERE session_id = ?
                """,
                (
                    technician_user_id,
                    technician_username,
                    edge_service_grant,
                    edge_service_grant_id,
                    edge_service_grant_expires_at,
                    time.time(),
                    session_id,
                ),
            )
            conn.commit()
            conn.close()

            log.info(
                "Auth session confirmed: %s by technician %s (%s)",
                session_id[:8],
                technician_username,
                technician_user_id,
            )
            return True

    def get_active_session(self, session_id: str) -> Optional[AuthSession]:
        """Get current session state."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                if session.status == "confirmed" and session.edge_service_grant_expires_at:
                    if time.time() > float(session.edge_service_grant_expires_at):
                        session.status = "expired"
                        session.edge_service_grant = None
                        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
                        conn.execute(
                            """
                            UPDATE technician_sessions
                            SET status = 'expired', edge_service_grant = NULL, headend_session_token = NULL
                            WHERE session_id = ?
                            """,
                            (session_id,),
                        )
                        conn.commit()
                        conn.close()
                        return None
                return session

            # Load from DB
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM technician_sessions
                WHERE session_id = ? AND expires_at > ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id, time.time()),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None
            if row["status"] == "confirmed" and row["edge_service_grant_expires_at"]:
                if time.time() > float(row["edge_service_grant_expires_at"]):
                    conn = sqlite3.connect(str(self._db_path), timeout=30.0)
                    conn.execute(
                        """
                        UPDATE technician_sessions
                        SET status = 'expired', edge_service_grant = NULL, headend_session_token = NULL
                        WHERE session_id = ?
                        """,
                        (session_id,),
                    )
                    conn.commit()
                    conn.close()
                    return None

            return AuthSession(
                session_id=row["session_id"],
                device_id=row["device_id"],
                challenge=row["challenge"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                status=row["status"],
                technician_user_id=row["technician_user_id"],
                technician_username=row["technician_username"],
                edge_service_grant=row["edge_service_grant"],
                edge_service_grant_id=row["edge_service_grant_id"],
                edge_service_grant_expires_at=row["edge_service_grant_expires_at"],
            )

    def revoke_session(self, session_id: str, *, reason: str = "revoked") -> bool:
        """Revoke a local technician session after central grant revocation or expiry."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = "revoked"
                session.edge_service_grant = None
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            cursor = conn.execute(
                """
                UPDATE technician_sessions
                SET status = ?, edge_service_grant = NULL, headend_session_token = NULL
                WHERE session_id = ?
                """,
                (reason, session_id),
            )
            changed = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return changed

    def apply_grant_status_snapshot(self, grants: list[dict[str, Any]]) -> int:
        """Apply central EdgeServiceGrant revoke/expiry state to local sessions."""
        revoked_ids = {
            str(item.get("grant_id"))
            for item in grants
            if item.get("grant_id") and str(item.get("status", "")).lower() != "active"
        }
        if not revoked_ids:
            return 0
        placeholders = ",".join("?" for _ in revoked_ids)
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        cursor = conn.execute(
            f"""
            UPDATE technician_sessions
            SET status = 'revoked', edge_service_grant = NULL, headend_session_token = NULL
            WHERE edge_service_grant_id IN ({placeholders})
            """,
            tuple(revoked_ids),
        )
        changed = cursor.rowcount
        conn.commit()
        conn.close()
        with self._lock:
            for session in self._sessions.values():
                if session.edge_service_grant_id in revoked_ids:
                    session.status = "revoked"
                    session.edge_service_grant = None
        return changed

    def cleanup_expired(self, days: int = 7) -> int:
        """Remove old expired sessions from database."""
        cutoff = time.time() - (days * 86400)
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        cursor = conn.execute(
            "DELETE FROM technician_sessions WHERE expires_at < ?",
            (cutoff,),
        )
        count = cursor.rowcount
        conn.commit()
        conn.close()

        if count > 0:
            log.info("Cleaned up %d expired technician sessions", count)

        return count


# Global instance
_auth_instance: Optional[TechnicianAuth] = None
_auth_lock = threading.Lock()


def get_auth(db_path: Path | str | None = None, device_id: str | None = None, headend_url: str | None = None) -> TechnicianAuth:
    """Get or create global technician auth instance."""
    global _auth_instance

    with _auth_lock:
        if _auth_instance is None:
            if db_path is None or device_id is None or headend_url is None:
                raise RuntimeError("TechnicianAuth not initialized and required params missing")
            _auth_instance = TechnicianAuth(db_path, device_id, headend_url)
        return _auth_instance
