"""Small config-merge helpers moved out of main.py (ratchet, 2026-10-10)."""
from __future__ import annotations


def merge_missing_defaults(existing: dict, defaults: dict) -> dict:
    """Add default keys that are missing, recursively; never overwrite a set value."""
    result = dict(existing or {})
    for key, value in (defaults or {}).items():
        if key not in result:
            result[key] = value
        elif isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge_missing_defaults(result[key], value)
    return result
