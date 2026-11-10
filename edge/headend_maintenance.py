"""Bounded Edge-side cache of an announced Headend maintenance window."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path


MAX_ANNOUNCEMENT_SECONDS = 30 * 60


class HeadendMaintenanceWindow:
    """Persist only a short expiry received through authenticated Edge sync."""

    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _parse(value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def update(self, value: object, *, now: datetime | None = None) -> bool:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        expiry = self._parse(value)
        if expiry is None or not (current < expiry <= current + timedelta(seconds=MAX_ANNOUNCEMENT_SECONDS)):
            self.clear()
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text(expiry.isoformat(), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.path)
        return True

    def active(self, *, now: datetime | None = None) -> bool:
        try:
            expiry = self._parse(self.path.read_text(encoding="utf-8"))
        except OSError:
            return False
        current = (now or datetime.now(UTC)).astimezone(UTC)
        if expiry is None or not (current < expiry <= current + timedelta(seconds=MAX_ANNOUNCEMENT_SECONDS)):
            self.clear()
            return False
        return True

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
