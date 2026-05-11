# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Node Agent Transport
# ═══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

TIMEOUT = 15


def _post(url: str, payload: Any, token: str = "") -> tuple[bool, str]:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            return True, body
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


def post_inventory(cfg, payload: dict) -> tuple[bool, str]:
    url = f"{cfg.headend_url}/api/inventory/{cfg.device_id}"
    return _post(url, payload, cfg.api_token)


def post_security_events(cfg, events: list[dict]) -> tuple[bool, str]:
    url = f"{cfg.headend_url}/api/siem/events/{cfg.device_id}"
    return _post(url, {"events": events}, cfg.api_token)
