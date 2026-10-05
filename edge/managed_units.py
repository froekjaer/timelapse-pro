"""systemd units the Edge agent manages (installs from edge/scripts/).

One list for both paths that install them:
  * the app-update flow (agent._run_artifact_app_update) when a release
    changes a management file, and
  * agent startup (reconcile_managed_units), so a unit a release *introduces*
    is installed by that same release.

Why startup matters (lab.60, 2026-10-05): an update is applied by the agent
that is already running, i.e. the previous release's code with the previous
release's unit list. lab.60 added five units, but the lab.59 agent that
installed lab.60 did not know them, so they were never installed. The new
agent now installs whatever is missing when it starts.
"""
from __future__ import annotations

import filecmp
import shutil
import subprocess
from pathlib import Path
from typing import Callable

MANAGED_UNITS: tuple[str, ...] = (
    "timelapse-bt-pan.service",
    "timelapse-bt-agent.service",
    "timelapse-ble-technician.service",
    "timelapse-captive.service",
    "timelapse-wifi-ap.service",
    "timelapse-totp.service",
    "timelapse-timesync.service",
    "timelapse-timesync.timer",
    # System baseline (Edge1/Edge2 comparison 2026-10-04): previously
    # hand-installed on one Edge only, or not at all.
    "timelapse-watchdog.service",
    "timelapse-system-baseline.service",
    "timelapse-bt-address.service",
    "timelapse-nightly-reboot.service",
    "timelapse-nightly-reboot.timer",
)
# Started by its timer; has no [Install] section, so never `enable` it.
TIMER_DRIVEN_UNITS = frozenset({"timelapse-nightly-reboot.service"})
# Safe to (re)start whenever installed or changed: oneshots, timers and the
# watchdog. Restarting the technician services (bt-pan, totp, …) mid-session
# is left to the update flow, which verifies them.
START_WHEN_CHANGED: tuple[str, ...] = (
    "timelapse-system-baseline.service",
    "timelapse-bt-address.service",
    "timelapse-nightly-reboot.timer",
    "timelapse-timesync.timer",
    "timelapse-watchdog.service",
)

Runner = Callable[[list[str]], object]


def _default_runner(cmd: list[str]) -> object:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60)


def reconcile_managed_units(
    repo: Path,
    systemd_dir: Path = Path("/etc/systemd/system"),
    runner: Runner = _default_runner,
) -> dict:
    """Install managed units that are missing or differ from the release.

    Never touches timelapse-edge.service (it is running us). Returns which
    units were installed/updated so the caller can log it.
    """
    source_dir = Path(repo) / "edge" / "scripts"
    installed: list[str] = []
    updated: list[str] = []
    for unit in MANAGED_UNITS:
        source = source_dir / unit
        if not source.is_file():
            continue
        target = systemd_dir / unit
        if target.is_file() and filecmp.cmp(source, target, shallow=False):
            continue
        (updated if target.exists() else installed).append(unit)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    changed = installed + updated
    if changed:
        runner(["systemctl", "daemon-reload"])
        for unit in installed:
            if unit not in TIMER_DRIVEN_UNITS:
                runner(["systemctl", "enable", unit])
        for unit in START_WHEN_CHANGED:
            if unit in changed:
                runner(["systemctl", "restart", unit])
    return {"installed": installed, "updated": updated}
