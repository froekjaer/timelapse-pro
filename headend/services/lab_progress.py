"""LAB start progress, shown step by step in the LAB page (Peter 2026-10-10:
"feedback step, når man har trykket start lab, så man kan se at der sker
noget, og hvor langt den er").

Kept in memory on purpose: it is transient UI feedback, and writing it into
device_config would change config_version, which triggers a tunnel wake and a
config re-fetch on the Edge for every step.
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone

# Ordered steps the UI knows; unknown phases are still stored and shown.
PHASES = (
    "woken",              # Headend: wake sent through the SSH tunnel
    "received",           # Edge: LAB seen in its config
    "camera_power",       # Edge: camera relay switching on (detail: warm-up seconds)
    "camera_connecting",  # Edge: connecting via gphoto2
    "camera_retry",       # Edge: retrying / power-cycling the camera
    "ready",              # Edge: camera connected
    "params",             # Edge: camera parameters sent
    "camera_failed",      # Edge: gave up — detail says why
)
MAX_EVENTS = 50

_events: dict[str, deque] = {}
_lock = threading.Lock()


def record(device_id: str, phase: str, detail: str = "", extra: dict | None = None) -> dict:
    event = {
        "phase": str(phase)[:40],
        "detail": str(detail or "")[:300],
        "at": datetime.now(timezone.utc).isoformat(),
        **({"extra": extra} if isinstance(extra, dict) else {}),
    }
    with _lock:
        _events.setdefault(device_id, deque(maxlen=MAX_EVENTS)).append(event)
    return event


def events(device_id: str, since: str | None = None) -> list[dict]:
    with _lock:
        rows = list(_events.get(device_id, ()))
    if since:
        try:
            cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            rows = [r for r in rows if datetime.fromisoformat(r["at"]) >= cutoff]
        except ValueError:
            pass
    return rows
