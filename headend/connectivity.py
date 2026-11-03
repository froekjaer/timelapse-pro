"""Central, authoritative device connectivity (freshness) calculation.

Phase 3 of the reliability work order (2026-11-03). Fixes the "persisted
representation treated as current physical state" defect (Edge2 was shown
"online" for ~87h while offline): connectivity MUST be derived from the
freshness of the most recent authenticated sync/heartbeat (headend receipt
time = ``device.last_seen``, set server-side as ``now_utc()`` on an
authenticated request — never from client payload), computed at READ time,
using ONE definition shared by dashboard, CMDB, APIs and ITIM. Status must
change as time passes even when no new message arrives.

Connectivity is distinct from lifecycle. The persisted ``device.status``
column carries administrative/lifecycle states (provisioning, import, and
states written by the reboot lifecycle); those are passed through unchanged.
Any other value -- including a stale "online", or a missing/"unknown" status --
is derived from freshness, so a stale "online" can never be presented as
current, and a fresh authenticated last_seen is never masked as "unknown".

Three distinct concepts (keep them separate — do not conflate):
  * connectivity_state(): categorical online|stale|offline|unknown (for display)
  * is_up():              binary liveness for alerting (online or stale => up)
  * last_seen_age_s:      the raw freshness age (exposed by ITIM as a metric)
Operational/lifecycle state (RUNNING/REBOOTING/…) is a separate axis handled by
the reboot lifecycle (Phase 2), not by this module.

Thresholds are configurable. Defaults are the INITIAL TEST thresholds approved
in the work order (online <= 10 min, offline > 15 min, stale between) and must
be validated against real poll timing/jitter before production tuning.
Misconfiguration is handled loudly, never silently: a non-integer, non-positive
or inconsistent (online > offline) setting is rejected with a logged warning and
the safe defaults are used, so configuration can never produce a misleading
"online".
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_DEFAULT_ONLINE_S = 600   # <= 10 min  -> online
_DEFAULT_OFFLINE_S = 900  # <= 15 min  -> stale ; above -> offline


def _resolve_thresholds(online_raw, offline_raw,
                        d_online: int = _DEFAULT_ONLINE_S,
                        d_offline: int = _DEFAULT_OFFLINE_S) -> tuple[int, int]:
    """Validate configured thresholds. On any invalid/inconsistent value, log a
    warning and fall back to the safe defaults. Never returns values that would
    make the online/stale/offline ordering incoherent."""
    def _one(raw, default, name):
        if raw is None:
            return default
        try:
            v = int(raw)
        except (TypeError, ValueError):
            log.warning("connectivity: %s=%r is not an integer; using default %d", name, raw, default)
            return default
        if v <= 0:
            log.warning("connectivity: %s=%r must be > 0; using default %d", name, raw, default)
            return default
        return v

    online = _one(online_raw, d_online, "TIMELAPSE_CONN_ONLINE_S")
    offline = _one(offline_raw, d_offline, "TIMELAPSE_CONN_OFFLINE_S")
    if online > offline:
        log.warning(
            "connectivity: online threshold (%ds) > offline threshold (%ds) is incoherent; "
            "using defaults %ds/%ds", online, offline, d_online, d_offline)
        return d_online, d_offline
    return online, offline


ONLINE_MAX_AGE_S, OFFLINE_MIN_AGE_S = _resolve_thresholds(
    os.getenv("TIMELAPSE_CONN_ONLINE_S"), os.getenv("TIMELAPSE_CONN_OFFLINE_S"))

# Administrative/lifecycle states that legitimately override connectivity: a
# device being provisioned, or an imported record, is not "online" merely
# because a row is fresh. "unknown" is deliberately NOT here -- it is the
# ABSENCE of a lifecycle value (the historical ``status or "unknown"`` default),
# so a fresh authenticated last_seen must still compute connectivity rather than
# be masked as "unknown".
#
# PHASE 2 (data-model, NOT Phase 3): move lifecycle/administrative state onto its
# own column/axis, separate from the connectivity-derived status, so connectivity
# is ALWAYS computed purely from freshness and administrative restrictions are
# represented independently. Needs a schema change; out of Phase 3 scope
# (see FF-TLP-0002 / reliability assessment).
LIFECYCLE_STATES = {"provisioning", "import"}


def _now(now: datetime | None = None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def connectivity_state(last_seen: datetime | None, now: datetime | None = None) -> str:
    """Return online|stale|offline|unknown from the freshness of the last
    received sync.

    ``unknown`` is returned when there is no observation at all (never seen) or
    when the receipt time is in the future (clock skew / replay): we must never
    treat an unverifiable timestamp as "online". ``unknown`` deliberately means
    "no trustworthy evidence of state", which is distinct from ``offline``
    ("we had evidence and it has gone stale")."""
    if last_seen is None:
        return "unknown"
    if getattr(last_seen, "tzinfo", None) is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_s = (_now(now) - last_seen).total_seconds()
    if age_s < 0:
        return "unknown"
    if age_s <= ONLINE_MAX_AGE_S:
        return "online"
    if age_s <= OFFLINE_MIN_AGE_S:
        return "stale"
    return "offline"


def is_up(last_seen: datetime | None, now: datetime | None = None) -> bool:
    """Binary liveness for the ITIM 'up' metric and 'Edge offline' alarm.

    ``up`` is True for ``online`` and ``stale``, False for ``offline`` and
    ``unknown``. Rationale: 'up' is a coarse reachability signal whose only job
    is to drive the up==0 "Edge offline" alarm; 'stale' means *recently seen
    but ageing* — not yet offline — so counting it as up avoids firing an
    offline alarm during the brief stale window (one poll interval of slack).
    The finer online/stale distinction, and the raw age, remain available via
    connectivity_state() and last_seen_age_s for dashboards and correlation.
    A future/never-seen timestamp is ``unknown`` and therefore NOT up, so an
    unverifiable observation can never mark a device live."""
    return connectivity_state(last_seen, now) in ("online", "stale")


def display_status(device, now: datetime | None = None) -> str:
    """Authoritative status for display/API responses. Lifecycle/semantic
    states pass through unchanged; otherwise connectivity is computed from
    ``device.last_seen`` freshness. Accepts None (-> "unknown").

    Never-seen (``last_seen is None``) resolves to ``unknown`` — the same as
    ``connectivity_state(None)`` — not ``offline``: a device we have never
    heard from has no evidence of state, and "unknown" says so honestly."""
    if device is None:
        return "unknown"
    raw = getattr(device, "status", None)
    if raw in LIFECYCLE_STATES:
        return raw
    # Any other value -- None/""/"unknown"/"online"/"offline" -- is derived from
    # observation freshness, independently of the persisted status column.
    return connectivity_state(getattr(device, "last_seen", None), now)
