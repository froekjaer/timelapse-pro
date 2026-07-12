"""
TimeLapse Pro — Edge Activity Logger

Logs all edge activities with offline caching and deferred upload.
Designed for compliance, audit trails, and operational monitoring.

SABSA: Accountability — every action is logged with timestamp, source,
and context. Logs survive network outages and upload when connectivity
returns.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Optional

log = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log levels for activity filtering."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActivitySource(Enum):
    """Where the activity originated."""
    INIT = "init"                    # During edge initialization
    CAMERA = "camera"                # Camera capture operations
    UPLOAD = "upload"                # Upload to headend
    AI = "ai"                        # AI/ML operations
    TECHNICIAN = "technician"        # Technician CLI/UI actions
    SYSTEM = "system"                # System operations
    NETWORK = "network"              # Network connectivity
    UPDATE = "update"                # Edge updates/patches
    SECURITY = "security"            # Security events


@dataclass
class ActivityLog:
    """Single activity log entry."""
    id: str                           # UUID
    timestamp: float                  # Unix timestamp
    level: str                        # LogLevel
    source: str                       # ActivitySource
    event_type: str                   # Specific event (e.g., "capture_start")
    device_id: Optional[str]          # Device identifier
    message: str                      # Human-readable description
    context: dict[str, Any]           # Additional structured data
    uploaded: bool = False            # Whether uploaded to headend

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "level": self.level,
            "source": self.source,
            "event_type": self.event_type,
            "device_id": self.device_id,
            "message": self.message,
            "context": self.context,
            "uploaded": self.uploaded,
        }


class EdgeActivityLogger:
    """
    Thread-safe activity logger with offline caching.

    Logs are written to local SQLite DB immediately. A background process
    uploads pending logs when headend connectivity is available.
    """

    def __init__(self, db_path: Path | str, device_id: str | None = None):
        self._db_path = Path(db_path)
        self._device_id = device_id
        self._lock = Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with activity_log table."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._db_path.parent, 0o750)
        except OSError:
            pass

        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                level TEXT NOT NULL,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                device_id TEXT,
                message TEXT NOT NULL,
                context TEXT,
                uploaded INTEGER DEFAULT 0,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_uploaded
            ON activity_log(uploaded, timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_timestamp
            ON activity_log(source, timestamp)
        """)
        conn.commit()
        conn.close()

    def log(
        self,
        level: LogLevel | str,
        source: ActivitySource | str,
        event_type: str,
        message: str,
        context: dict[str, Any] | None = None,
        device_id: str | None = None,
    ) -> str:
        """
        Log an activity event.

        Returns the log entry UUID.
        """
        if isinstance(level, Enum):
            level = level.value
        if isinstance(source, Enum):
            source = source.value

        entry_id = uuid.uuid4().hex
        timestamp = time.time()
        dev_id = device_id or self._device_id
        ctx_json = json.dumps(context or {}) if context else None

        with self._lock:
            try:
                conn = sqlite3.connect(str(self._db_path), timeout=30.0)
                conn.execute(
                    """
                    INSERT INTO activity_log
                    (id, timestamp, level, source, event_type, device_id, message, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entry_id, timestamp, level, source, event_type, dev_id, message, ctx_json),
                )
                conn.commit()
                conn.close()
            except sqlite3.Error as exc:
                log.error("Failed to write activity log: %s", exc)

        # Also log to standard logger for immediate visibility
        log_func = getattr(logging, level.lower(), logging.info)
        log_func("[%s] %s: %s", source, event_type, message)

        return entry_id

    def info(self, source: ActivitySource | str, event_type: str, message: str, **context) -> str:
        return self.log(LogLevel.INFO, source, event_type, message, context)

    def warning(self, source: ActivitySource | str, event_type: str, message: str, **context) -> str:
        return self.log(LogLevel.WARNING, source, event_type, message, context)

    def error(self, source: ActivitySource | str, event_type: str, message: str, **context) -> str:
        return self.log(LogLevel.ERROR, source, event_type, message, context)

    def debug(self, source: ActivitySource | str, event_type: str, message: str, **context) -> str:
        return self.log(LogLevel.DEBUG, source, event_type, message, context)

    def get_pending_upload(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Get logs that haven't been uploaded yet."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, timestamp, level, source, event_type,
                       device_id, message, context
                FROM activity_log
                WHERE uploaded = 0
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            conn.close()

        results = []
        for row in rows:
            entry = dict(row)
            if entry.get("context"):
                try:
                    entry["context"] = json.loads(entry["context"])
                except (json.JSONDecodeError, TypeError):
                    entry["context"] = {}
            results.append(entry)
        return results

    def mark_uploaded(self, entry_ids: list[str] | set[str]) -> int:
        """Mark logs as uploaded."""
        if not entry_ids:
            return 0
        with self._lock:
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            cursor = conn.execute(
                """
                UPDATE activity_log
                SET uploaded = 1
                WHERE id IN ({})
                """.format(",".join("?" * len(entry_ids))),
                list(entry_ids),
            )
            count = cursor.rowcount
            conn.commit()
            conn.close()
        return count

    def get_recent(
        self,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get recent logs for local UI display."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row

            if source:
                cursor = conn.execute(
                    """
                    SELECT id, timestamp, level, source, event_type,
                           device_id, message, context, uploaded
                    FROM activity_log
                    WHERE source = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                    """,
                    (source, limit, offset),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, timestamp, level, source, event_type,
                           device_id, message, context, uploaded
                    FROM activity_log
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = cursor.fetchall()
            conn.close()

        results = []
        for row in rows:
            entry = dict(row)
            if entry.get("context"):
                try:
                    entry["context"] = json.loads(entry["context"])
                except (json.JSONDecodeError, TypeError):
                    entry["context"] = {}
            results.append(entry)
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get logging statistics."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN uploaded = 0 THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN uploaded = 1 THEN 1 ELSE 0 END) as uploaded,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest
                FROM activity_log
                """
            )
            row = cursor.fetchone()
            conn.close()

        if not row or row[0] == 0:
            return {"total": 0, "pending": 0, "uploaded": 0}

        return {
            "total": row[0],
            "pending": row[1] or 0,
            "uploaded": row[2] or 0,
            "earliest": row[3],
            "latest": row[4],
        }

    def cleanup_old(self, days: int = 90, keep_failed: bool = True) -> int:
        """
        Delete old logs that have been uploaded.

        Args:
            days: Keep logs newer than this
            keep_failed: If True, keep failed uploads regardless of age
        """
        cutoff = time.time() - (days * 86400)
        with self._lock:
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)

            if keep_failed:
                # Only delete uploaded logs
                cursor = conn.execute(
                    """
                    DELETE FROM activity_log
                    WHERE uploaded = 1 AND timestamp < ?
                    """,
                    (cutoff,),
                )
            else:
                # Delete all old logs
                cursor = conn.execute(
                    """
                    DELETE FROM activity_log
                    WHERE timestamp < ?
                    """,
                    (cutoff,),
                )

            count = cursor.rowcount
            conn.commit()
            conn.close()

        if count > 0:
            log.info("Cleaned up %d old activity log entries", count)

        return count


# Global logger instance
_logger_instance: EdgeActivityLogger | None = None
_logger_lock = Lock()


def get_logger(db_path: Path | str | None = None, device_id: str | None = None) -> EdgeActivityLogger:
    """Get or create the global activity logger instance."""
    global _logger_instance

    with _logger_lock:
        if _logger_instance is None:
            if db_path is None:
                raise RuntimeError("Logger not initialized and no db_path provided")
            _logger_instance = EdgeActivityLogger(db_path, device_id)
        return _logger_instance


def log_init(message: str, **context) -> str:
    """Convenience function for init-phase logging."""
    logger = get_logger()
    return logger.info(ActivitySource.INIT, "init_phase", message, context)


def log_camera(event: str, message: str, **context) -> str:
    """Convenience function for camera operations."""
    logger = get_logger()
    return logger.info(ActivitySource.CAMERA, event, message, context)


def log_upload(event: str, message: str, **context) -> str:
    """Convenience function for upload operations."""
    logger = get_logger()
    return logger.info(ActivitySource.UPLOAD, event, message, context)


def log_technician(event: str, message: str, **context) -> str:
    """Convenience function for technician actions."""
    logger = get_logger()
    return logger.info(ActivitySource.TECHNICIAN, event, message, context)


def log_security(event: str, message: str, level: LogLevel = LogLevel.WARNING, **context) -> str:
    """Convenience function for security events."""
    logger = get_logger()
    return logger.log(level, ActivitySource.SECURITY, event, message, context)
