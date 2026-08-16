"""Canonical update-to-Edge applicability rules.

This module is intentionally free of database access so the same predicate can be
used by policy delivery, reporting validation, matrices, and deterministic tests.
"""

from __future__ import annotations

import json
from typing import Any


_TEST_ENVIRONMENTS = {"lab", "test", "rd", "dev", "development"}
_PRODUCTION_ENVIRONMENTS = {"prod", "production"}


def _normalize_environment(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw in _TEST_ENVIRONMENTS:
        return "test"
    if raw in _PRODUCTION_ENVIRONMENTS:
        return "production"
    if raw == "staging":
        return "staging"
    return raw


def _parse_target_device_ids(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except Exception:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def update_applies_to_device(update: Any, device: Any, inventory: Any) -> bool:
    """Return True only when both scope and environment authorize this Edge.

    Unknown device environment fails closed. Explicit ``target_device_ids`` narrows
    scope but never bypasses the environment boundary.
    """
    device_id = str(getattr(inventory, "device_id", None) or getattr(device, "device_id", None) or "").strip()
    if not device_id:
        return False

    update_environment = _normalize_environment(getattr(update, "environment", None) or "production")
    device_environment = _normalize_environment(
        getattr(inventory, "environment", None) or getattr(device, "environment", None)
    )
    if not device_environment or update_environment != device_environment:
        return False

    target_ids = _parse_target_device_ids(getattr(update, "target_device_ids", None))
    if target_ids:
        return device_id in target_ids

    scope = str(getattr(update, "scope", None) or "device").strip().lower()
    scope_id = str(getattr(update, "scope_id", None) or "").strip()
    if scope == "global":
        return True
    if scope == "device":
        return scope_id == device_id
    if scope == "customer" and device is not None:
        return scope_id == str(getattr(device, "customer_id", None) or "")
    if scope == "site" and device is not None:
        return scope_id == str(getattr(device, "site_id", None) or "")
    return False
