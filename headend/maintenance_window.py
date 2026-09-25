"""Planned-maintenance alert suppression (2026-09-21).

A single, deliberately simple mechanism: a marker file containing an
ISO-8601 UTC expiry timestamp. While `now < expiry`, connectivity-related
alert *notifications* (not the alerts themselves — those are still recorded
for audit) are suppressed, so a nightly full server reboot doesn't spam
email/SMS/Teams about the headend being briefly unreachable to itself and
to edges.

Written by deploy/scripts/timelapse-nightly-maintenance right before
`shutdown -r now`. Read by headend/itim.py::_notify_alert() (gated on
`rule.metric == "up"`) and headend/siem.py::ingest_events() (gated on
`category == "connectivity"`) — see HANDOVER_LOG.md 2026-09-21 for why only
these two, not all alerts: resource alerts (RAM/disk) are never suppressed,
and a post-reboot recovery that never actually completes is caught by this
same window expiring — normal alerting resumes and fires for real.

Fails open by design: any missing file, unreadable file, or unparseable
timestamp is treated as "not in a maintenance window" (returns False), so a
bug in this mechanism can only ever cause a spurious notification, never a
silently-suppressed real one.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

MAINTENANCE_MARKER_PATH = Path("/etc/timelapse/maintenance-until")


def is_maintenance_window_active(now: datetime | None = None) -> bool:
    try:
        raw = MAINTENANCE_MARKER_PATH.read_text().strip()
        if not raw:
            return False
        expiry = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
    except (OSError, ValueError) as exc:
        log.debug("Maintenance-window marker unavailable/unparseable (%s) — treating as inactive", exc)
        return False
    current = now if now is not None else datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current < expiry
