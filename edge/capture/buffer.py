"""
TimeLapse Pro — Capture Capacity Guard
=======================================
Monitors local capture storage without deleting image evidence.

SABSA: Availability — warns before storage exhaustion.
       Integrity    — captured images are never deleted automatically.
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

    The historical class name is retained for compatibility. TimeLapse Pro
    treats images as immutable evidence, so this component never removes them.
    """

    def __init__(self, config: dict):
        storage_cfg = config.get("storage", {})
        self._path        = Path(storage_cfg.get("local_path", "/data/captures"))
        self._max_bytes   = int(storage_cfg.get("circular_buffer_gb", 50)) * 1_073_741_824
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
        Report capacity pressure without deleting captures.

        Returns zero for backward compatibility with callers that used the old
        pruning implementation. ``db`` is intentionally unused.
        """
        current = self.usage_bytes()
        if current < self._max_bytes:
            return 0

        log.critical(
            "Capture storage threshold exceeded: %.1f GB / %.1f GB; "
            "automatic deletion is prohibited",
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
