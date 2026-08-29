"""Small serialization helpers for capture API responses."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


AI_RESULT_LIST_STRIP_TOP_KEYS = ("raw_response", "prompt")
AI_RESULT_LIST_STRIP_EDGE_KEYS = ("npu", "autonomous_optimizer", "cv_features")
DEFAULT_CAPTURE_TIMEZONE = "Europe/Copenhagen"


def trim_ai_result_for_list(raw: str | None) -> str | None:
    """Strip large diagnostic blobs from capture list responses."""
    if not raw:
        return raw
    try:
        parsed = json.loads(raw)
    except Exception:
        return raw
    if not isinstance(parsed, dict):
        return raw
    for key in AI_RESULT_LIST_STRIP_TOP_KEYS:
        parsed.pop(key, None)
    edge_ai = parsed.get("edge_ai")
    if isinstance(edge_ai, dict):
        for key in AI_RESULT_LIST_STRIP_EDGE_KEYS:
            edge_ai.pop(key, None)
    return json.dumps(parsed)


def capture_timezone_from_config(device_config: str | None) -> str:
    try:
        config = json.loads(device_config or "{}")
        timezone_name = config.get("schedule", {}).get("timezone")
        if isinstance(timezone_name, str) and timezone_name:
            ZoneInfo(timezone_name)
            return timezone_name
    except Exception:
        pass
    return DEFAULT_CAPTURE_TIMEZONE


def capture_timestamp_fields(captured_at: datetime | None, timezone_name: str = DEFAULT_CAPTURE_TIMEZONE) -> dict:
    if not captured_at:
        return {"captured_at": None, "captured_at_local": None, "captured_timezone": timezone_name}
    if captured_at.tzinfo is None:
        local_value = captured_at.isoformat()
        utc_value = None
    else:
        try:
            local_dt = captured_at.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
        except Exception:
            timezone_name = DEFAULT_CAPTURE_TIMEZONE
            local_dt = captured_at.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
        local_value = local_dt.isoformat()
        utc_value = captured_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "captured_at": captured_at.isoformat(),
        "captured_at_local": local_value,
        "captured_at_utc": utc_value,
        "captured_timezone": timezone_name,
    }
