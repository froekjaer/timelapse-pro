"""timelapse-timesync.service must not set RemainAfterExit=yes.

Regression for a real, live recurring failure on Edge 1 (and matching
symptoms observed on Edge 2), 2026-09-09: timelapse-timesync.timer is meant
to run sync-time.sh every 6 minutes (OnUnitActiveSec=6min) to correct clock
drift on a device whose hardware RTC can't be read. With RemainAfterExit=yes
on the oneshot service it triggers, systemd considers the service
permanently "active" after its first successful run, so the timer's
relative re-arm timer never gets a fresh "became active" transition to
count 6 minutes from — the well-documented oneshot+RemainAfterExit+
OnUnitActiveSec systemd anti-pattern. Live symptom: `systemctl status
timelapse-timesync.timer` showed "Trigger: n/a" and the timer never fired
again after its first post-boot run, so a multi-hour clock drift (system
clock correct per GPS reference in chrony, but never actually stepped) went
uncorrected until manually forced via `chronyc makestep`, breaking all
signed Edge<->Headend communication in the meantime.
"""
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "edge" / "scripts"


def _service_text(name: str) -> str:
    path = _SCRIPTS_DIR / name
    assert path.exists(), f"missing {path}"
    return path.read_text()


def test_timesync_service_does_not_set_remain_after_exit():
    text = _service_text("timelapse-timesync.service")
    directive_lines = [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any(line.startswith("RemainAfterExit=") for line in directive_lines), (
        "RemainAfterExit on this oneshot service prevents its triggering "
        "timer from ever re-arming (OnUnitActiveSec) after the first run"
    )


def test_timesync_service_is_still_a_oneshot():
    # The fix removes RemainAfterExit, not Type=oneshot itself — sync-time.sh
    # genuinely runs to completion once per invocation.
    text = _service_text("timelapse-timesync.service")
    assert "Type=oneshot" in text


def test_timesync_timer_still_repeats_every_6_minutes():
    path = _SCRIPTS_DIR / "timelapse-timesync.timer"
    text = path.read_text()
    assert "OnUnitActiveSec=6min" in text
    assert "OnBootSec=" in text
