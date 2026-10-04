#!/usr/bin/env python3
"""Controlled nightly reboot for every Edge (Peter, 2026-10-04: "Natlig
reboot på alle").

Replaces Edge1's two hand-made cron reboots (03:00 and 04:00). Run every few
minutes by timelapse-nightly-reboot.timer; reboots only when ALL hold:

  * system.nightly_reboot.enabled is true (Headend config: Global Config →
    System, overridable per customer/site/camera)
  * local time is inside [time, time + window_minutes)
  * uptime >= min_uptime_hours (so it reboots once per night, never loops)
  * no app/OS update is pending health confirmation
  * no technician Service Session is active
  * the camera maintenance lock is free — taken and held until the reboot,
    so a capture can never be cut off and none starts meanwhile
"""
from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

CONFIG = Path(os.getenv("TIMELAPSE_EDGE_CONFIG", "/opt/timelapse/edge/config.yaml"))
REPO = Path(os.getenv("TIMELAPSE_EDGE_REPO", "/opt/timelapse"))
LOCK = Path(os.getenv("TIMELAPSE_CAMERA_MAINTENANCE_LOCK", "/run/timelapse/camera-maintenance.lock"))
SERVICE_STATE_DIR = Path(os.getenv("TIMELAPSE_SERVICE_STATE_DIR", "/run/timelapse"))

DEFAULTS = {"enabled": True, "time": "03:00", "window_minutes": 30, "min_uptime_hours": 6}


def settings(cfg: dict) -> dict:
    raw = ((cfg.get("system") or {}).get("nightly_reboot") or {})
    out = dict(DEFAULTS)
    out.update({k: v for k, v in raw.items() if k in DEFAULTS and v not in (None, "")})
    # UI dropdowns store strings ("false", "30"); "false" must not be truthy.
    out["enabled"] = str(out["enabled"]).strip().lower() in {"1", "true", "yes", "ja", "on"}
    for key in ("window_minutes", "min_uptime_hours"):
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            out[key] = DEFAULTS[key]
    return out


def in_window(now: datetime, hhmm: str, window_minutes: int) -> bool:
    hour, minute = (int(x) for x in str(hhmm).split(":", 1))
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start > now:
        start -= timedelta(days=1)          # window may cross midnight
    return now < start + timedelta(minutes=int(window_minutes))


def uptime_hours() -> float:
    return float(Path("/proc/uptime").read_text().split()[0]) / 3600.0


def _edge_import():
    edge = REPO / "edge"
    if str(edge) not in sys.path:
        sys.path.insert(0, str(edge))


def update_pending() -> bool:
    """An app update waiting for post-restart health confirmation."""
    try:
        _edge_import()
        from update_lifecycle import load_pending_app_update, pending_app_update_path
        payload = load_pending_app_update(pending_app_update_path(REPO))
    except Exception:
        return False
    return bool(payload) and payload.get("state") == "awaiting_restart_health"


def technician_session_active() -> bool:
    try:
        _edge_import()
        from service_platform import ServicePlatform
        return ServicePlatform(state_dir=SERVICE_STATE_DIR).current_session() is not None
    except Exception:
        return False


def decide(cfg: dict, now: datetime, uptime_h: float, pending: bool, session: bool) -> tuple[bool, str]:
    s = settings(cfg)
    if not s["enabled"]:
        return False, "disabled"
    if not in_window(now, s["time"], s["window_minutes"]):
        return False, "outside_window"
    if uptime_h < float(s["min_uptime_hours"]):
        return False, "recently_booted"
    if pending:
        return False, "update_pending"
    if session:
        return False, "technician_session_active"
    return True, "reboot"


def main() -> int:
    try:
        import yaml
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[nightly-reboot] kan ikke læse config ({exc}) — bruger standard")
        cfg = {}
    ok, reason = decide(cfg, datetime.now(), uptime_hours(), update_pending(), technician_session_active())
    if not ok:
        if reason not in {"outside_window", "recently_booted"}:
            print(f"[nightly-reboot] ingen genstart: {reason}")
        return 0
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o660)
    deadline = time.time() + 300
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() > deadline:
                print("[nightly-reboot] kameraet er optaget i 5 min — prøver ved næste kørsel")
                return 0
            time.sleep(5)
    print(f"[nightly-reboot] planlagt natlig genstart (uptime {uptime_hours():.1f} t)")
    subprocess.run(["systemctl", "reboot"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
