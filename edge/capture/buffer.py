"""
TimeLapse Pro — Circular Buffer Manager
=========================================
Enforces a maximum local disk usage on the capture directory by deleting the
oldest already-uploaded-and-verified images first — never anything else.

History: the original implementation (2026-05) fell back to deleting
UNVERIFIED files whenever a database query failed or whenever the buffer was
still over its target after every uploaded candidate had been exhausted
(`except Exception: uploaded.append(f)  # assume safe to delete on DB error`,
plus `candidates = uploaded + not_uploaded`). Under real capacity pressure —
uploads falling behind captures — that design would eventually delete
captures that had never reached Headend at all. Peter shut deletion off
entirely on 2026-07-15 (commit 3464a07f) rather than run that risk in
production, and Headend gained disk-usage alerting instead
(headend/itim.py, "Edge disk næsten fuld"/"...kritisk fuld").

This version restores pruning with every fail-open path removed: a database
error, a missing upload record, or running out of verified-uploaded
candidates all mean "stop, delete nothing further" — never "delete
something unverified instead". A file is only ever eligible once Headend has
independently recomputed and matched its SHA-256
(headend/main.py::receive_capture_files) AND at least
`min_hours_since_upload` has passed since that confirmation, as an extra
grace margin.

SABSA: Availability — disk never fills completely, captures always possible.
       Integrity    — only Headend-checksum-verified, aged uploads are ever deleted.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Delete until usage drops to this fraction of the limit.
HYSTERESIS = 0.90

# Extra safety margin beyond "Headend confirmed the checksum matched" before
# a file becomes eligible for local deletion.
DEFAULT_MIN_HOURS_SINCE_UPLOAD = 24.0


class CircularBuffer:
    """
    Manages local image storage within a size limit.

    Config keys (from config.yaml storage section):
        local_path:              str    e.g. "/data/captures"
        circular_buffer_gb:      int    max GB to use (default 50)
        min_hours_since_upload:  float  grace period after upload confirmation
                                         before a file may be deleted (default 24)

    Deletion candidates come exclusively from EdgeDatabase.get_deletion_candidates(),
    which itself fails closed (returns [] rather than raising) — see its docstring.
    """

    def __init__(self, config: dict):
        storage_cfg = config.get("storage", {})
        self._path        = Path(storage_cfg.get("local_path", "/data/captures"))
        self._max_bytes   = int(float(storage_cfg.get("circular_buffer_gb", 50)) * 1_073_741_824)
        self._target_bytes = int(self._max_bytes * HYSTERESIS)
        self._min_hours_since_upload = float(
            storage_cfg.get("min_hours_since_upload", DEFAULT_MIN_HOURS_SINCE_UPLOAD)
        )
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
        Delete oldest verified-uploaded files until usage is below target.

        Args:
            db: EdgeDatabase session. Required — without it there is no way
                to confirm upload status, so nothing is ever deleted.

        Returns:
            Number of files deleted.
        """
        current = self.usage_bytes()
        if current < self._max_bytes:
            return 0

        if db is None:
            log.critical(
                "Capture storage threshold exceeded: %.1f GB / %.1f GB — "
                "no database session available, cannot verify upload status, "
                "deleting nothing",
                current / 1e9, self._max_bytes / 1e9,
            )
            return 0

        log.warning(
            "Buffer full: %.1f GB / %.1f GB — pruning verified-uploaded files…",
            current / 1e9, self._max_bytes / 1e9,
        )

        candidates = db.get_deletion_candidates(self._min_hours_since_upload)
        deleted = 0

        for row in candidates:
            if self.usage_bytes() <= self._target_bytes:
                break
            filepath = Path(row["filepath"])
            try:
                if not filepath.exists():
                    continue
                size = filepath.stat().st_size
                filepath.unlink()
                log.info("Buffer prune: deleted %s (%.1f MB, uploaded_at=%s)",
                         filepath.name, size / 1e6, row.get("uploaded_at"))
                deleted += 1
            except OSError as exc:
                log.warning("Could not delete %s: %s", filepath, exc)

        remaining = self.usage_bytes()
        if remaining > self._max_bytes:
            log.critical(
                "Capture storage still over threshold after pruning all eligible "
                "files: %.1f GB / %.1f GB — no further captures are verified-and-"
                "aged enough to delete; deleting nothing else",
                remaining / 1e9, self._max_bytes / 1e9,
            )
        log.info(
            "Buffer prune complete: deleted %d files, now %.1f GB",
            deleted, remaining / 1e9,
        )
        return deleted

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
