"""Retired legacy updater.

All Edge updates must use ``EdgeAgent._check_and_apply_updates`` and a
Headend-signed artifact.  This module intentionally performs no Git, apt,
network or package action if an old integration imports it.
"""
from __future__ import annotations

import logging

log = logging.getLogger("cmdb.executor")


def process_targets(api, device_id: str, lab_active: bool) -> int:
    """Reject the retired CMDB executor without changing the Edge."""
    log.error(
        "Legacy CMDB executor was invoked for %s; no action taken. "
        "Use the Headend-signed artifact update flow.",
        device_id,
    )
    return 0
