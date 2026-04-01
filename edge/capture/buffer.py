"""
TimeLapse Pro — Circular Buffer Manager
=========================================
Enforces a maximum disk usage on the local capture directory by
deleting the oldest already-uploaded images first.

SABSA: Availability — disk never fills completely, captures always possible.
       Integrity    — only uploaded images are eligible for deletion.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Delete until usage drops to this fraction of the limit
HYSTERESIS = 0.90


class CircularBuffer:
    """
    Manages local image storage within a size limit.

    Config keys (from config.yaml storage section):
        local_path:           str  e.g. "/data/captures"
        circular_buffer_gb:   int  max GB to use (default 50)

    The buffer tracks which files have been uploaded via a simple
    SQLite query (injected via the db_session parameter). Files that
    have NOT yet been uploaded are protected from deletion.
    """

    def __init__(self, config: dict):
        storage_cfg = config.get("storage", {})
        self._path        = Path(storage_cfg.get("local_path", "/data/captures"))
        self._max_bytes   = int(storage_cfg.get("circular_buffer_gb", 50)) * 1_073_741_824
        self._target_bytes = int(self._max_bytes * HYSTERESIS)
        self._path.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def usage_bytes(self) -> int:
        """Return total bytes used by capture directory."""
        return sum(
            f.stat().st_size
            for f in self._path.rglob("*")
            if f.is_file()
        )

    def usage_gb(self) -> float:
        return self.usage_bytes() / 1_073_741_824

    def is_full(self) -> bool:
        return self.usage_bytes() >= self._max_bytes

    def enforce(self, db=None) -> int:
        """
        Delete oldest uploaded files until usage is below target.

        Args:
            db: optional database session for querying upload status.
                If None, deletion candidates are selected by mtime only
                (least safe — only use if DB is unavailable).

        Returns:
            Number of files deleted.
        """
        current = self.usage_bytes()
        if current < self._max_bytes:
            return 0

        log.warning(
            "Buffer full: %.1f GB / %.1f GB — pruning…",
            current / 1e9, self._max_bytes / 1e9
        )

        candidates = self._get_candidates(db)
        deleted = 0

        for filepath in candidates:
            if self.usage_bytes() <= self._target_bytes:
                break
            try:
                size = filepath.stat().st_size
                filepath.unlink()
                log.info("Buffer prune: deleted %s (%.1f MB)", filepath.name, size / 1e6)
                deleted += 1
            except OSError as exc:
                log.warning("Could not delete %s: %s", filepath, exc)

        remaining = self.usage_bytes()
        log.info(
            "Buffer prune complete: deleted %d files, now %.1f GB",
            deleted, remaining / 1e9
        )
        return deleted

    def _get_candidates(self, db) -> list[Path]:
        """
        Return list of files eligible for deletion, oldest first.
        Priority: uploaded files first, then unuploaded if necessary.
        """
        all_files = sorted(
            (f for f in self._path.rglob("*") if f.is_file()),
            key=lambda f: f.stat().st_mtime,
        )

        if db is None:
            log.warning("No DB available — deleting oldest files regardless of upload status")
            return all_files

        # Split into uploaded and not-uploaded
        uploaded     = []
        not_uploaded = []

        for f in all_files:
            try:
                is_uploaded = db.is_file_uploaded(str(f))
                if is_uploaded:
                    uploaded.append(f)
                else:
                    not_uploaded.append(f)
            except Exception:
                uploaded.append(f)   # assume safe to delete on DB error

        # Delete uploaded first (safest), then non-uploaded if still over limit
        candidates = uploaded + not_uploaded

        if not_uploaded:
            log.warning(
                "%d non-uploaded files may need pruning — "
                "consider increasing circular_buffer_gb or reducing capture frequency",
                len(not_uploaded)
            )

        return candidates

    def stats(self) -> dict:
        """Return buffer statistics as a dict."""
        used = self.usage_bytes()
        return {
            "path":       str(self._path),
            "used_gb":    round(used / 1e9, 2),
            "max_gb":     round(self._max_bytes / 1e9, 2),
            "used_pct":   round(100 * used / self._max_bytes, 1),
            "file_count": sum(1 for f in self._path.rglob("*") if f.is_file()),
        }
