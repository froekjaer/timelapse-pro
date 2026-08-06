"""
TimeLapse Pro — Edge Database
===============================
SQLite database with WAL mode for resilience against power loss.
Stores capture records, diagnostics, upload queue, and config history.

SABSA: Accountability — full audit trail of every capture and system event.
       Integrity      — SHA-256 and quality scores stored per image.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DB_VERSION = 3
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

-- One row per captured image
CREATE TABLE IF NOT EXISTS captures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    camera_model    TEXT,
    driver_name     TEXT,
    filepath        TEXT NOT NULL UNIQUE,
    filename        TEXT NOT NULL,
    filesize        INTEGER,
    sha256          TEXT NOT NULL,
    captured_at     TEXT NOT NULL,   -- UTC ISO-8601
    exposure_time   TEXT,
    aperture        TEXT,
    iso             INTEGER,
    focus_mode      TEXT,

    -- Quality assessment
    quality_flag    TEXT,            -- ok / blurry / underexposed / overexposed / error
    quality_passed  INTEGER,         -- 0 or 1
    blur_score      REAL,
    brightness_mean REAL,

    -- Upload tracking
    uploaded_primary   INTEGER DEFAULT 0,   -- 0/1
    uploaded_secondary INTEGER DEFAULT 0,
    uploaded_tertiary  INTEGER DEFAULT 0,
    uploaded_at        TEXT,
    upload_attempts    INTEGER DEFAULT 0,

    -- Sync to headend API
    synced_to_headend  INTEGER DEFAULT 0,
    synced_at          TEXT,

    -- Circular-buffer local deletion (2026-08-05). NULL = file still present
    -- locally. Only ever set for captures with uploaded_primary=1 (headend
    -- has independently verified the SHA-256 before acknowledging the
    -- upload — see headend/main.py::receive_capture_files) — kept as a
    -- timestamp rather than deleting the row outright, for accountability
    -- (SABSA: full audit trail of every capture, per this file's header).
    deleted_at      TEXT,

    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_captures_uploaded ON captures(uploaded_primary);
CREATE INDEX IF NOT EXISTS idx_captures_captured_at ON captures(captured_at);
CREATE INDEX IF NOT EXISTS idx_captures_synced ON captures(synced_to_headend);

-- Diagnostics time-series (heartbeat data)
CREATE TABLE IF NOT EXISTS diagnostics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    recorded_at     TEXT NOT NULL,
    cpu_temp_c      REAL,
    cpu_load_pct    REAL,
    ram_used_mb     INTEGER,
    disk_used_gb    REAL,
    battery_v       REAL,
    solar_v         REAL,
    connectivity    TEXT,   -- ethernet / wifi / 5g / none
    uptime_s        INTEGER,
    extra           TEXT    -- JSON for extensibility
);

CREATE INDEX IF NOT EXISTS idx_diag_recorded ON diagnostics(recorded_at);

-- Event log (errors, state changes, updates)
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    event_at    TEXT NOT NULL,
    level       TEXT NOT NULL,   -- INFO / WARNING / ERROR / CRITICAL
    category    TEXT NOT NULL,   -- capture / upload / camera / system / update
    message     TEXT NOT NULL,
    extra       TEXT             -- JSON
);

CREATE INDEX IF NOT EXISTS idx_events_at ON events(event_at);

-- Upload queue (retry tracking)
CREATE TABLE IF NOT EXISTS upload_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id      INTEGER NOT NULL REFERENCES captures(id),
    target          TEXT NOT NULL,      -- 'primary' or 'secondary'
    remote_path     TEXT NOT NULL,
    queued_at       TEXT NOT NULL,
    attempts        INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    last_error      TEXT,
    completed       INTEGER DEFAULT 0,
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_queue_pending ON upload_queue(completed, attempts);
"""


class EdgeDatabase:
    """
    Thread-safe SQLite wrapper for the edge agent.
    Uses WAL mode and NORMAL synchronous for power-loss resilience.
    """

    def __init__(self, config: dict):
        db_path = config.get("storage", {}).get(
            "db_path", "/data/timelapse_edge.db"
        )
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version VALUES (?, ?)",
                    (DB_VERSION, _now())
                )
            self._migrate(conn, row["version"] if row else 0)
            log.info("Database ready: %s", self._db_path)

    def _migrate(self, conn: sqlite3.Connection, current_version: int) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(captures)").fetchall()
        }
        if "uploaded_tertiary" not in columns:
            conn.execute("ALTER TABLE captures ADD COLUMN uploaded_tertiary INTEGER DEFAULT 0")
        if "deleted_at" not in columns:
            conn.execute("ALTER TABLE captures ADD COLUMN deleted_at TEXT")
        conn.execute(
            "UPDATE captures SET uploaded_secondary=1 "
            "WHERE uploaded_primary=1 AND uploaded_secondary=0"
        )
        if current_version < DB_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO schema_version VALUES (?, ?)",
                (DB_VERSION, _now()),
            )

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Captures ────────────────────────────────────────────────────────────

    def insert_capture(
        self,
        *,
        device_id:    str,
        filepath:     Path,
        sha256:       str,
        captured_at:  datetime,
        camera_model: Optional[str]  = None,
        driver_name:  Optional[str]  = None,
        filesize:     Optional[int]  = None,
        exposure_time:Optional[str]  = None,
        aperture:     Optional[str]  = None,
        iso:          Optional[int]  = None,
        focus_mode:   Optional[str]  = None,
        quality_flag: Optional[str]  = None,
        quality_passed:Optional[bool]= None,
        blur_score:   Optional[float]= None,
        brightness:   Optional[float]= None,
    ) -> int:
        """Insert a new capture record. Returns the row id."""
        with self._connect() as conn:
            cur = conn.execute("""
                INSERT INTO captures (
                    device_id, camera_model, driver_name,
                    filepath, filename, filesize, sha256, captured_at,
                    exposure_time, aperture, iso, focus_mode,
                    quality_flag, quality_passed, blur_score, brightness_mean
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                device_id, camera_model, driver_name,
                str(filepath), filepath.name, filesize,
                sha256, captured_at.isoformat(),
                exposure_time, aperture, iso, focus_mode,
                quality_flag,
                int(quality_passed) if quality_passed is not None else None,
                blur_score, brightness,
            ))
            return cur.lastrowid

    def mark_uploaded(
        self,
        capture_id: int,
        target: str,
    ) -> None:
        col = _upload_column(target)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE captures SET {col}=1, uploaded_at=? WHERE id=?",
                (_now(), capture_id)
            )

    def is_file_uploaded(self, filepath: str) -> bool:
        """Return True if the file has been uploaded to primary."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT uploaded_primary FROM captures WHERE filepath=?",
                (filepath,)
            ).fetchone()
            return bool(row and row["uploaded_primary"])

    def get_confirmed_uploaded_captures_oldest_first(self, limit: int = 500) -> list[dict]:
        """Return captures eligible for circular-buffer local deletion:
        uploaded_primary=1 (headend independently verified SHA-256 before
        acknowledging — see headend/main.py::receive_capture_files) AND not
        already deleted locally. Oldest first, so the circular buffer always
        frees the oldest confirmed-safe capture before a newer one."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM captures WHERE uploaded_primary=1 AND deleted_at IS NULL "
                "ORDER BY captured_at ASC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_deleted(self, capture_id: int) -> None:
        """Record that a capture's local file was removed by the circular
        buffer. The row itself is kept (not deleted) for audit purposes."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE captures SET deleted_at=? WHERE id=?",
                (_now(), capture_id)
            )

    def get_pending_uploads(self, target: str = "primary", limit: int = 50) -> list[dict]:
        """Return captures not yet uploaded to the given target."""
        col = _upload_column(target)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM captures WHERE {col}=0 ORDER BY captured_at LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_capture(self, capture_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM captures WHERE id=?", (capture_id,)).fetchone()
            return dict(row) if row else None

    def get_unsynced_captures(self, limit: int = 100) -> list[dict]:
        """Return captures not yet synced to headend API."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM captures WHERE synced_to_headend=0 ORDER BY captured_at LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_synced(self, capture_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE captures SET synced_to_headend=1, synced_at=? WHERE id=?",
                (_now(), capture_id)
            )

    # ── Diagnostics ──────────────────────────────────────────────────────────

    def insert_diagnostics(self, device_id: str, diag: dict) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO diagnostics (
                    device_id, recorded_at,
                    cpu_temp_c, cpu_load_pct, ram_used_mb,
                    disk_used_gb, battery_v, solar_v,
                    connectivity, uptime_s, extra
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                device_id, _now(),
                diag.get("cpu_temperature"),
                diag.get("cpu_load"),
                diag.get("memory_used_mb"),
                diag.get("disk_used_gb"),
                diag.get("battery_voltage"),
                diag.get("solar_voltage"),
                diag.get("connectivity_type"),
                diag.get("uptime_s"),
                json.dumps(diag.get("extra", {})),
            ))

    def get_latest_diagnostics(self, device_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM diagnostics WHERE device_id=? ORDER BY recorded_at DESC LIMIT 1",
                (device_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── Events ───────────────────────────────────────────────────────────────

    def log_event(
        self,
        device_id: str,
        level: str,
        category: str,
        message: str,
        extra: Optional[dict] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events (device_id, event_at, level, category, message, extra) "
                "VALUES (?,?,?,?,?,?)",
                (device_id, _now(), level, category, message,
                 json.dumps(extra) if extra else None)
            )

    def get_recent_events(self, device_id: str, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE device_id=? ORDER BY event_at DESC LIMIT ?",
                (device_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Stats ────────────────────────────────────────────────────────────────

    def capture_stats(self, device_id: str) -> dict:
        """Return summary statistics for dashboard / heartbeat."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)                                    AS total,
                    SUM(CASE WHEN quality_passed=1 THEN 1 END) AS passed,
                    SUM(CASE WHEN uploaded_primary=1 THEN 1 END) AS uploaded,
                    SUM(CASE WHEN synced_to_headend=0 AND uploaded_primary=1 THEN 1 END) AS pending_sync,
                    MAX(captured_at)                           AS last_capture_at
                FROM captures
                WHERE device_id=?
            """, (device_id,)).fetchone()
            return dict(row) if row else {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _upload_column(target: str) -> str:
    mapping = {
        "primary": "uploaded_primary",
        "api_primary": "uploaded_primary",
        "secondary": "uploaded_secondary",
        "customer_sftp": "uploaded_secondary",
        "tertiary": "uploaded_tertiary",
        "backup_sftp": "uploaded_tertiary",
    }
    return mapping.get(target, "uploaded_secondary")
