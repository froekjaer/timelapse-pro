"""Availability contract for the Edge agent's independent watchdog.

The reverse SSH tunnel is owned by the agent today.  A manual service stop must
therefore recover without the tunnel or a person on site.  These tests execute
the real shell watchdog against a fake systemctl rather than merely checking
for source-code strings.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG = ROOT / "edge/scripts/watchdog.sh"
CONTROL = ROOT / "edge/scripts/timelapse_edge_maintenance.sh"
UNIT = ROOT / "edge/scripts/timelapse-watchdog.service"


def _fake_systemctl(tmp_path: Path) -> tuple[Path, Path, Path]:
    calls = tmp_path / "calls"
    active = tmp_path / "active"
    script = tmp_path / "systemctl"
    script.write_text(
        """#!/bin/bash
set -eu
printf '%s\\n' "$*" >> "$FAKE_SYSTEMCTL_CALLS"
case "${1:-}" in
  is-active)
    if [[ -f "$FAKE_SYSTEMCTL_ACTIVE" ]]; then echo active; exit 0; fi
    echo inactive; exit 3 ;;
  start)
    touch "$FAKE_SYSTEMCTL_ACTIVE" ;;
  stop)
    rm -f "$FAKE_SYSTEMCTL_ACTIVE" ;;
  show)
    echo 0 ;;
  status)
    exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script, calls, active


def _run_watchdog(tmp_path: Path, *, down_since: int, marker_until: int | None = None):
    systemctl, calls, active = _fake_systemctl(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    (state / "agent-down-since").write_text(f"{down_since}\n", encoding="utf-8")
    marker = tmp_path / "maintenance-until"
    if marker_until is not None:
        marker.write_text(f"{marker_until}\nreason\n", encoding="utf-8")
    env = {
        **os.environ,
        "SYSTEMCTL_BIN": str(systemctl),
        "FAKE_SYSTEMCTL_CALLS": str(calls),
        "FAKE_SYSTEMCTL_ACTIVE": str(active),
        "WATCHDOG_STATE_DIR": str(state),
        "WATCHDOG_MAINTENANCE_UNTIL_FILE": str(marker),
        "WATCHDOG_NOW_EPOCH": "1000",
        "WATCHDOG_ONCE": "1",
        "MAX_AGENT_DOWN_SECONDS": "60",
        "MAX_MAINTENANCE_SECONDS": "900",
        "TIMELAPSE_RELAY_PIN": "999999",
    }
    result = subprocess.run(
        ["bash", str(WATCHDOG)], env=env, text=True, capture_output=True, timeout=5
    )
    return result, calls.read_text(encoding="utf-8"), active, marker


def test_inactive_agent_is_started_without_the_tunnel(tmp_path: Path):
    result, calls, active, _ = _run_watchdog(tmp_path, down_since=900)
    assert result.returncode == 0, result.stderr
    assert "start timelapse-edge.service" in calls
    assert active.exists()
    assert "Recovery successful" in result.stdout


def test_short_maintenance_hold_defers_recovery(tmp_path: Path):
    result, calls, active, marker = _run_watchdog(
        tmp_path, down_since=900, marker_until=1100
    )
    assert result.returncode == 0, result.stderr
    assert "start timelapse-edge.service" not in calls
    assert not active.exists()
    assert marker.exists()
    assert "maintenance hold active" in result.stdout.lower()


def test_unbounded_hold_fails_safe_and_recovers(tmp_path: Path):
    result, calls, active, marker = _run_watchdog(
        tmp_path, down_since=900, marker_until=100_000
    )
    assert result.returncode == 0, result.stderr
    assert "start timelapse-edge.service" in calls
    assert active.exists()
    assert not marker.exists()
    assert "beyond 900s safety limit" in result.stdout


def test_watchdog_is_independent_from_agent_lifecycle():
    unit = UNIT.read_text(encoding="utf-8")
    assert "After=timelapse-edge.service" not in unit
    assert "Restart=always" in unit


def test_maintenance_control_is_bounded_and_removes_hold_before_start():
    source = CONTROL.read_text(encoding="utf-8")
    assert "MAX_MINUTES=15" in source
    start_case = source.split("start)", 1)[1].split("status)", 1)[0]
    assert start_case.index('rm -f -- "$MARKER"') < start_case.index(
        '"$SYSTEMCTL_BIN" start timelapse-edge.service'
    )


def test_app_update_treats_recovery_scripts_as_management_runtime():
    agent = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    install_block = agent.split("management_runtime_paths =", 1)[1].split(
        "management_changed =", 1
    )[0]
    assert '"edge/scripts/watchdog.sh"' in install_block
    assert '"edge/scripts/timelapse_edge_maintenance.sh"' in install_block
