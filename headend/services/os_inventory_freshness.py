"""Freshness rules for CMDB inventories used to create OS update candidates."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


def stale_os_inventory_reason(reported_at: datetime | None) -> str | None:
    """Return an operator-safe reason when an OS inventory cannot drive updates."""
    max_age_hours = float(os.getenv("TIMELAPSE_OS_CATALOG_MAX_INVENTORY_AGE_HOURS", "72"))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, max_age_hours))
    if reported_at is None:
        return "CMDB-inventory mangler rapporteringstidspunkt og må ikke oprette en OS-opdateringskandidat"
    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=timezone.utc)
    if reported_at < cutoff:
        return (
            f"CMDB-inventory er for gammel ({reported_at.isoformat()}); "
            f"maksimal alder er {max_age_hours:g} timer. Vent på frisk Edge-inventory."
        )
    return None
