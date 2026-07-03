# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Node Agent Transport
# ═══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

log = logging.getLogger(__name__)

TIMEOUT = 15


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _request_signature_headers(token: str, method: str, url: str, payload: Any) -> dict[str, str]:
    if not token:
        return {}
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.removeprefix("/api")
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    body = _canonical_json(payload or {}) if payload else ""
    signed = "\n".join([method.upper(), path, timestamp, nonce, body])
    signature = hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-TLP-Signature-Alg": "hmac-sha256-v1",
        "X-TLP-Timestamp": timestamp,
        "X-TLP-Nonce": nonce,
        "X-TLP-Signature": signature,
    }


def _post(url: str, payload: Any, token: str = "") -> tuple[bool, str]:
    data = _canonical_json(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers.update(_request_signature_headers(token, "POST", url, payload))
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
