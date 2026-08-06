"""
TimeLapse Pro — Capture Circular Buffer
=========================================
Monitors local capture storage and, once disk usage crosses a configured
percentage threshold, deletes the OLDEST captures that are 100% confirmed
uploaded to Headend — freeing space for new captures without ever touching
an image whose only copy might still be local. Cleanup targets that same
trigger threshold; a separate, stricter minimum-free-space floor is a hard
guarantee that must never be violated, escalating to CRITICAL if it is.

"Confirmed uploaded" means uploaded_primary=1 in the local SQLite DB, which
is only ever set after Headend has independently recomputed and verified
the SHA-256 of the received bytes (constant-time comparison against the
edge-declared manifest hash) and durably stored the file — see
headend/main.py::receive_capture_files. A capture that isn't confirmed
uploaded is NEVER deleted, no matter how full the disk gets.

SABSA: Availability   — frees disk space so capture never silently stops.
       Integrity      — only ever deletes a LOCAL copy after Headend has
                         independently verified it holds a byte-identical,
                         durable copy. The capture row itself is kept
                         (deleted_at timestamp, not a row delete) for audit.
       Accountability  — every deletion is logged with capture id + filename;
                         if the confirmed-uploaded backlog isn't enough to
                         reach the configured free-space floor, this raises
                         a CRITICAL log (forwarded to SIEM) instead of ever
                         falling back to deleting an unconfirmed capture.

2026-08-05 (Peter): replaces the previous "never delete anything, ever"
placeholder with the actual policy-driven mechanism that placeholder's own
UI tooltip had already been describing as if it existed.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

class CircularBuffer:
    """
    Deletes the oldest confirmed-uploaded captures once disk usage crosses
    a configured trigger percentage, cleaning back down to that same
    trigger level. A separate, stricter minimum-free-space percentage is a
    hard floor that must never be violated — not a cleanup target — and
    only comes into play (as a CRITICAL alarm) if the confirmed-uploaded
    backlog runs out before that floor is reached.

    Config keys (from config.yaml / Headend-delivered storage section):
        local_path:                     str    e.g. "/data/captures"
        circular_buffer_gb:             int    legacy fixed cap, stats/back-compat only
        circular_buffer_delete_at_pct:  float  disk-used%% that triggers deletion AND the
                                                level cleanup aims to return to (default 70)
        circular_buffer_min_free_pct:   float  disk-free%% hard floor, never to be violated
                                                (default 20)

    The historical class name is retained for compatibility.
    """

    def __init__(self, config: dict):
        storage_cfg = config.get("storage", {})
        self._path        = Path(storage_cfg.get("local_path", "/data/captures"))
        self._max_bytes    = int(storage_cfg.get("circular_buffer_gb", 50)) * 1_073_741_824
        self._delete_at_pct = float(storage_cfg.get("circular_buffer_delete_at_pct", 70))
        self._min_free_pct  = float(storage_cfg.get("circular_buffer_min_free_pct", 20))
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

    def _disk_used_pct(self) -> float:
        total, used, _free = shutil.disk_usage(self._path)
        if total <= 0:
            return 0.0
        return 100.0 * used / total

    def enforce(self, db=None) -> int:
        """
        Delete the oldest confirmed-uploaded captures once disk usage
        (of the actual filesystem, not just this directory's own byte
        total) reaches circular_buffer_delete_at_pct, continuing until
        usage drops back to that same trigger level or no more eligible
        captures remain.

        circular_buffer_min_free_pct is a SEPARATE, stricter hard floor:
        it is not the cleanup target, it's the "must never be violated"
        guarantee. If the confirmed-uploaded backlog runs out before disk
        usage even gets back down to the trigger level, that's a WARNING;
        it only escalates to CRITICAL if usage stays above the min-free
        floor as well (i.e. the guarantee itself is broken).

        Returns the number of files actually deleted. No-ops (returns 0)
        if ``db`` isn't provided — deletion eligibility can only be
        determined from the upload-confirmation record, never guessed from
        file age/mtime alone.
        """
        if db is None:
            return 0

        used_pct = self._disk_used_pct()
        if used_pct < self._delete_at_pct:
            return 0

        hard_floor_used_pct = 100.0 - self._min_free_pct
        log.warning(
            "Circular buffer: disk usage %.1f%% >= trigger %.1f%% — deleting oldest "
            "confirmed-uploaded captures down to %.1f%% used (hard floor: %.1f%% free, "
            "never to be violated)",
            used_pct, self._delete_at_pct, self._delete_at_pct, self._min_free_pct,
        )

        candidates = db.get_confirmed_uploaded_captures_oldest_first(limit=2000)
        deleted = 0
        for row in candidates:
            if self._disk_used_pct() <= self._delete_at_pct:
                break
            filepath = Path(row["filepath"])
            try:
                if filepath.exists():
                    filepath.unlink()
                db.mark_deleted(row["id"])
                deleted += 1
                log.info(
                    "Circular buffer: deleted confirmed-uploaded capture id=%s file=%s "
                    "(uploaded_at=%s)",
                    row["id"], filepath.name, row.get("uploaded_at"),
                )
            except Exception as exc:
                log.warning(
                    "Circular buffer: failed to delete capture id=%s file=%s: %s",
                    row["id"], filepath, exc,
                )

        final_used_pct = self._disk_used_pct()
        if final_used_pct > hard_floor_used_pct:
            log.critical(
                "Circular buffer: disk usage still %.1f%% (hard floor <=%.1f%%, i.e. minimum "
                "%.1f%% free) after deleting all %d eligible confirmed-uploaded capture(s) — "
                "the guaranteed free-space floor is being VIOLATED because there isn't enough "
                "confirmed-uploaded backlog. NOT deleting any unconfirmed capture. Likely "
                "cause: uploads to Headend are stalled or falling behind capture rate — "
                "investigate connectivity/Headend health.",
                final_used_pct, hard_floor_used_pct, self._min_free_pct, deleted,
            )
        elif final_used_pct > self._delete_at_pct:
            log.warning(
                "Circular buffer: disk usage still %.1f%% after deleting all %d eligible "
                "confirmed-uploaded capture(s) — could not fully return to the %.1f%% "
                "trigger level, but stayed within the %.1f%% free-space floor.",
                final_used_pct, deleted, self._delete_at_pct, self._min_free_pct,
            )
        return deleted

    def stats(self) -> dict:
        """Return buffer statistics as a dict."""
        used = self.usage_bytes()
        disk_used_pct = self._disk_used_pct()
        return {
            "path":       str(self._path),
            "used_gb":    round(used / 1e9, 2),
            "max_gb":     round(self._max_bytes / 1e9, 2),
            "used_pct":   round(100 * used / self._max_bytes, 1) if self._max_bytes else 0.0,
            "disk_used_pct": round(disk_used_pct, 1),
            "circular_buffer_delete_at_pct": self._delete_at_pct,
            "circular_buffer_min_free_pct":  self._min_free_pct,
            "file_count": sum(1 for f in self._path.rglob("*") if f.is_file()),
        }
