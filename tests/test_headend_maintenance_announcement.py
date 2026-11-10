from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from headend_maintenance import HeadendMaintenanceWindow


def test_valid_announcement_is_cached_and_expires(tmp_path: Path):
    now = datetime(2026, 11, 10, 2, 55, tzinfo=UTC)
    window = HeadendMaintenanceWindow(tmp_path / "until")
    assert window.update((now + timedelta(minutes=20)).isoformat(), now=now)
    assert window.active(now=now + timedelta(minutes=19))
    assert not window.active(now=now + timedelta(minutes=21))
    assert not window.path.exists()


def test_announcement_beyond_30_minutes_fails_open(tmp_path: Path):
    now = datetime(2026, 11, 10, 2, 55, tzinfo=UTC)
    window = HeadendMaintenanceWindow(tmp_path / "until")
    assert not window.update((now + timedelta(hours=2)).isoformat(), now=now)
    assert not window.active(now=now)


def test_malformed_announcement_clears_prior_window(tmp_path: Path):
    now = datetime(2026, 11, 10, 2, 55, tzinfo=UTC)
    window = HeadendMaintenanceWindow(tmp_path / "until")
    assert window.update((now + timedelta(minutes=20)).isoformat(), now=now)
    assert not window.update("not-a-time", now=now)
    assert not window.path.exists()


def test_reboot_script_announces_for_more_than_one_edge_poll_interval():
    root = Path(__file__).resolve().parents[1]
    script = (root / "deploy/scripts/timelapse-nightly-maintenance").read_text(encoding="utf-8")
    marker = script.index('> "$MAINTENANCE_MARKER"')
    wait = script.index('sleep "$EDGE_ANNOUNCEMENT_SECONDS"')
    reboot = script.index("exec shutdown -r now")
    assert marker < wait < reboot
    assert "EDGE_ANNOUNCEMENT_SECONDS=360" in script
