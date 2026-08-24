"""
TimeLapse Pro — Capture Capacity Guard
=======================================
Monitors local capture storage and prunes delivered Edge-local buffer copies.

SABSA: Availability — warns before storage exhaustion.
       Integrity    — only locally buffered files that reached every required
                      transport are eligible for deletion.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

class CircularBuffer:
    """
    Monitors local image storage against a configured capacity threshold.

    Config keys (from config.yaml storage section):
        local_path:           str  e.g. "/data/captures"
        circular_buffer_gb:   int  max GB to use (default 50)
        circular_buffer_bytes:int  optional exact byte limit for tests/lab
        local_retention_enabled: bool default true
        local_retention_low_watermark_pct: int default 85

    The historical class name is retained for compatibility. Headend/project
    data remains authoritative; this component only removes Edge-local buffer
    copies after all configured transports have completed.
    """

    def __init__(self, config: dict):
        storage_cfg = config.get("storage", {})
        self._path        = Path(storage_cfg.get("local_path", "/data/captures"))
        self._max_bytes   = int(
            storage_cfg.get(
                "circular_buffer_bytes",
                int(storage_cfg.get("circular_buffer_gb", 50)) * 1_073_741_824,
            )
        )
        self._enabled     = bool(storage_cfg.get("local_retention_enabled", True))
        low_watermark_pct = int(storage_cfg.get("local_retention_low_watermark_pct", 85))
        self._low_watermark_pct = min(99, max(1, low_watermark_pct))
        self._required_targets = self._required_upload_targets(config)
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
        Prune oldest delivered Edge-local buffer copies when over capacity.

        A capture is eligible only when the Edge DB says it has been uploaded
        through every transport that is enabled in the current config. The DB
        row is kept as audit/history; only local files and sidecars are removed.
        """
        current = self.usage_bytes()
        if current < self._max_bytes:
            return 0

        if not self._enabled or db is None:
            log.critical(
                "Capture storage threshold exceeded: %.1f GB / %.1f GB; "
                "local retention disabled or DB unavailable",
                current / 1e9,
                self._max_bytes / 1e9,
            )
            return 0

        target_bytes = int(self._max_bytes * (self._low_watermark_pct / 100))
        deleted = 0
        freed = 0
        candidates = db.local_retention_candidates(self._required_targets, limit=1000)
        for row in candidates:
            if current - freed <= target_bytes:
                break
            filepath = Path(row.get("filepath") or "")
            removed_bytes = self._delete_capture_files(filepath)
            if removed_bytes <= 0 and filepath.exists():
                continue
            db.mark_local_files_deleted(
                int(row["id"]),
                "edge_local_fifo_after_required_uploads",
            )
            deleted += 1
            freed += removed_bytes

        if deleted:
            log.warning(
                "Edge local retention pruned %d delivered capture(s), freed %.2f GB; "
                "required_targets=%s",
                deleted,
                freed / 1_073_741_824,
                ",".join(self._required_targets),
            )
            return deleted

        log.critical(
            "Capture storage threshold exceeded: %.1f GB / %.1f GB; "
            "no delivered captures eligible for local FIFO retention",
            current / 1e9,
            self._max_bytes / 1e9,
        )
        return 0

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

    def _delete_capture_files(self, filepath: Path) -> int:
        if not self._is_under_root(filepath):
            log.warning("Retention skipped path outside capture root: %s", filepath)
            return 0
        candidates = [
            filepath,
            filepath.with_suffix(".json"),
            filepath.with_suffix(filepath.suffix + ".qa.json"),
            filepath.parent / ".thumbs" / filepath.name,
        ]
        removed = 0
        for path in candidates:
            if not self._is_under_root(path):
                log.warning("Retention skipped sidecar outside capture root: %s", path)
                continue
            if not path.exists():
                continue
            if not path.is_file():
                log.warning("Retention skipped non-file path: %s", path)
                continue
            size = path.stat().st_size
            path.unlink()
            removed += size
        return removed

    def _is_under_root(self, path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(self._path.resolve(strict=False))
            return True
        except ValueError:
            return False

    @staticmethod
    def _required_upload_targets(config: dict) -> list[str]:
        targets = ["primary"]
        sftp = config.get("sftp", {}) if isinstance(config.get("sftp", {}), dict) else {}
        if sftp.get("enabled", False):
            targets.append(sftp.get("role") or "customer_sftp")
        for key, default_role in (
            ("secondary_sftp", "backup_sftp"),
            ("backup_sftp", "backup_sftp"),
        ):
            nested = sftp.get(key, {}) if isinstance(sftp.get(key, {}), dict) else {}
            if nested.get("enabled", False):
                targets.append(nested.get("role") or default_role)
        return list(dict.fromkeys(targets))
