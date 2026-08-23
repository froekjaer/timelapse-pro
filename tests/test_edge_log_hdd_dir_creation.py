"""Regression test for a boot-order race found live on TL-043EB9E72EFD
(2026-08-21): timelapse-totp.service and timelapse-timesync.service both log
to /var/log.hdd/timelapse/, but neither created that directory — it only
ever existed as a side effect of timelapse-bt-pan.service's own startup
script, which timesync doesn't even order after and totp only "Wants"
(non-blocking). Whether a given device ended up with the directory depended
on whether bt-pan happened to succeed before totp/timesync started on an
early boot — pure luck, not provisioning. Both services must create their
own log directory instead of depending on another service's side effect.
"""
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "edge" / "scripts"


def _service_text(name: str) -> str:
    path = _SCRIPTS_DIR / name
    assert path.exists(), f"missing {path}"
    return path.read_text()


def test_totp_service_creates_its_own_log_directory():
    text = _service_text("timelapse-totp.service")
    assert "ExecStartPre=/bin/mkdir -p /var/log.hdd/timelapse" in text
    # The mkdir must run before StandardOutput is ever opened by systemd,
    # i.e. it must appear as an ExecStartPre, not just anywhere in the file.
    mkdir_line = next(l for l in text.splitlines() if "mkdir -p /var/log.hdd/timelapse" in l)
    assert mkdir_line.strip().startswith("ExecStartPre=")


def test_timesync_service_creates_its_own_log_directory():
    text = _service_text("timelapse-timesync.service")
    assert "ExecStartPre=/bin/mkdir -p /var/log.hdd/timelapse" in text
    mkdir_line = next(l for l in text.splitlines() if "mkdir -p /var/log.hdd/timelapse" in l)
    assert mkdir_line.strip().startswith("ExecStartPre=")


def test_totp_and_timesync_no_longer_rely_solely_on_bt_pan_for_log_dir():
    """Belt-and-suspenders: bt-pan.sh may still create the directory too
    (harmless, mkdir -p is idempotent) — the regression is depending on it
    being the ONLY creator. Both dependents must be self-sufficient."""
    for name in ("timelapse-totp.service", "timelapse-timesync.service"):
        text = _service_text(name)
        assert "mkdir -p /var/log.hdd/timelapse" in text, (
            f"{name} logs to /var/log.hdd/timelapse but doesn't create it itself"
        )
