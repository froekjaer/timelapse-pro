"""Central, authoritative device connectivity (freshness) calculation.

Phase 3 of the reliability work order (2026-11-03). Fixes the "persisted
representation treated as current physical state" defect (Edge2 was shown
"online" for ~87h while offline): connectivity MUST be derived from the
freshness of the most recent authenticated sync/heartbeat (headend receipt
time = ``device.last_seen``), computed at READ time, using ONE definition
shared by dashboard, CMDB, APIs and ITIM. Status must change as time passes
even when no new message arrives.

Connectivity is distinct from lifecycle. The persisted ``device.status``
column carries lifecycle/semantic states (provisioning, import, unknown, and
states written by the reboot lifecycle); those are passed through unchanged.
Any other value is overridden by the freshness-derived connectivity state, so
a stale "online" can never be presented as current.

Thresholds are configurable. Defaults are the INITIAL TEST thresholds approved
in the work order (online <= 10 min, offline > 15 min, stale between) and must
be validated against real poll timing/jitter before production tuning.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

# <= ONLINE_MAX_AGE_S -> online ; <= OFFLINE_MIN_AGE_S -> stale ; else offline
ONLINE_MAX_AGE_S = int(os.getenv("TIMELAPSE_CONN_ONLINE_S", "600"))    # 10 min
OFFLINE_MIN_AGE_S = int(os.getenv("TIMELAPSE_CONN_OFFLINE_S", "900"))  # 15 min

# Raw ``device.status`` values that are lifecycle/semantic (not connectivity)
# and must be shown as-is rather than overridden by freshness.
NON_CONNECTIVITY_STATUS = {"provisioning", "import", "unknown"}


def _now(now: datetime | None = None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def connectivity_state(last_seen: datetime | None, now: datetime | None = None) -> str:
    """Return online|stale|offline|unknown from the freshness of the last
    received sync. ``unknown`` when there is no observation at all, or when the
    receipt time is in the future (clock skew / replay protection)."""
    if last_seen is None:
        return "unknown"
    if getattr(last_seen, "tzinfo", None) is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_s = (_now(now) - last_seen).total_seconds()
    if age_s < 0:
        # Receipt time in the future: never trust it as "online".
        return "unknown"
    if age_s <= ONLINE_MAX_AGE_S:
        return "online"
    if age_s <= OFFLINE_MIN_AGE_S:
        return "stale"
    return "offline"


def is_up(last_seen: datetime | None, now: datetime | None = None) -> bool:
    """Binary liveness for the ITIM 'up' metric: online or stale => up."""
    return connectivity_state(last_seen, now) in ("online", "stale")


def display_status(device, now: datetime | None = None) -> str:
    """Authoritative status for display/API responses. Lifecycle/semantic
    states pass through unchanged; otherwise connectivity is computed from
    ``device.last_seen`` freshness. Accepts None (-> "unknown")."""
    if device is None:
        return "unknown"
    raw = getattr(device, "status", None) or "unknown"
    if raw in NON_CONNECTIVITY_STATUS:
        return raw
    last_seen = getattr(device, "last_seen", None)
    if last_seen is None:
        return "offline"
    return connectivity_state(last_seen, now)
