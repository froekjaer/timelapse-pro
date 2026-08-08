"""Shared camera-relay session for the local technician UI and the CLI.

2026-08-08 (Claude, Peter): "Vil du tænde strøm til kamera og modem manuelt,
så længe du er logget ind / i 30 min?" — until now every single technician
action (via bootstrap_cli.py --maintenance, called by both totp-service.py
and the CLI directly) powered the relay on, ran ONE command, and powered it
off again — paying the full 10s warmup / 5s cooldown cost on every click,
and never leaving the camera powered long enough to be handled physically.

This is deliberately a small, file-based session (mirrors
camera/maintenance.py's CameraMaintenanceLease — same /run/timelapse
directory, same "always releasable by another process" philosophy) rather
than a long-lived daemon: both totp-service.py (a systemd service) and
bootstrap_cli.py (a one-shot CLI invocation) need to read/write the same
state without either one owning the process lifecycle.

Note: the modem relay is already powered on unconditionally at startup
(see RelayController -> ModemRelay._startup() in camera/relay.py) and is
never touched by CameraMaintenanceLease-based operations — there is no
"modem session" to build here, it's simply always on already.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

DEFAULT_STATE_PATH = Path("/run/timelapse/camera-session.json")
MIN_DURATION_S = 60
MAX_DURATION_S = 24 * 3600


def _state_path() -> Path:
    configured = os.getenv("TIMELAPSE_CAMERA_SESSION_STATE", "").strip()
    return Path(configured) if configured else DEFAULT_STATE_PATH


class CameraSession:
    """Reads/writes the shared session-state file. No relay access itself —
    callers pass a RelayController so this stays testable without GPIO."""

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or _state_path()

    def _read(self) -> Optional[dict]:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write(self, data: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self.state_path)

    def status(self) -> dict:
        data = self._read()
        now = time.time()
        if not data or data.get("expires_at", 0) <= now:
            return {"active": False}
        return {
            "active": True,
            "started_at": data["started_at"],
            "expires_at": data["expires_at"],
            "remaining_s": max(0, int(data["expires_at"] - now)),
            "started_by": data.get("started_by", ""),
        }

    def is_active(self) -> bool:
        return self.status()["active"]

    def start(self, relay, duration_s: int, started_by: str = "") -> dict:
        """Power the camera relay on and open a session for duration_s
        (clamped to [MIN_DURATION_S, MAX_DURATION_S])."""
        duration_s = max(MIN_DURATION_S, min(MAX_DURATION_S, int(duration_s)))
        relay.camera.power_on()
        now = time.time()
        data = {"started_at": now, "expires_at": now + duration_s, "started_by": started_by}
        self._write(data)
        return self.status()

    def extend(self, duration_s: int) -> dict:
        """Push expiry out by duration_s from now, only if a session is active."""
        data = self._read()
        if not data or data.get("expires_at", 0) <= time.time():
            raise RuntimeError("Ingen aktiv tekniker-session at forlænge")
        duration_s = max(MIN_DURATION_S, min(MAX_DURATION_S, int(duration_s)))
        data["expires_at"] = time.time() + duration_s
        self._write(data)
        return self.status()

    def stop(self, relay) -> None:
        """Force the relay off and clear session state — always safe to
        call, even if no session was active (matches CameraMaintenanceLease's
        'never leave the camera relay in maintenance state' guarantee)."""
        try:
            relay.camera.force_off()
        finally:
            try:
                self.state_path.unlink(missing_ok=True)
            except OSError:
                pass
