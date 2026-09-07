"""Contracts for starting the macOS Headend without an interactive login."""

from pathlib import Path
import plistlib


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "deploy/macos/timelapse-headend-start.sh"
PLISTS = (
    ROOT / "deploy/launchd/macos/dk.froekjaer.timelapse-headend.plist",
    ROOT / "deploy/launchd/dk.froekjaer.timelapse-headend.plist",
)


def test_headend_waits_for_real_writable_volume():
    source = START_SCRIPT.read_text()
    assert "wait_for_data_volume" in source
    assert "/sbin/mount" in source
    assert "-w \"$WORKDIR\"" in source
    assert 'wait_for_path "/Volumes/data-fast"' not in source


def test_headend_retries_after_transient_boot_dependency_failure():
    for path in PLISTS:
        plist = plistlib.loads(path.read_bytes())
        assert plist["RunAtLoad"] is True
        assert plist["KeepAlive"] is True
        assert plist["ThrottleInterval"] >= 10
