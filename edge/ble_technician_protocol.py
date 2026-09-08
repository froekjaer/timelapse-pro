"""Small, bounded protocol shared by the Edge BLE adapter and iOS client.

BLE is a transport only. Authentication creates the same local
ServiceSession used by the HTTPS technician UI and every request is dispatched
through ServicePlatform.
"""

from __future__ import annotations

import json
from typing import Any


SERVICE_UUID = "6f2b0001-2f4e-4a8c-9b6e-74696d656c70"
AUTH_UUID = "6f2b0002-2f4e-4a8c-9b6e-74696d656c70"
REQUEST_UUID = "6f2b0003-2f4e-4a8c-9b6e-74696d656c70"
RESPONSE_UUID = "6f2b0004-2f4e-4a8c-9b6e-74696d656c70"
STATUS_UUID = "6f2b0005-2f4e-4a8c-9b6e-74696d656c70"

MAX_MESSAGE_BYTES = 8 * 1024
MAX_OPERATION_NAME = 96
MAX_REQUEST_ID = 64
ALLOWED_AUTH_TYPES = frozenset({"totp"})


class ProtocolError(ValueError):
    """A malformed or unsafe BLE protocol message."""


def decode_message(raw: bytes | bytearray | str) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        message = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("message must be UTF-8 JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("message must be an object")
    return message


def encode_message(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict):
        raise ProtocolError("message must be an object")
    encoded = json.dumps(message, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    return encoded


def validate_auth_message(message: dict[str, Any]) -> str:
    if message.get("type") not in ALLOWED_AUTH_TYPES:
        raise ProtocolError("unsupported authentication type")
    code = str(message.get("code") or "")
    if len(code) != 6 or not code.isdigit():
        raise ProtocolError("TOTP code must contain six digits")
    return code


def validate_operation_message(message: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    request_id = str(message.get("id") or "")
    operation = str(message.get("operation") or "")
    params = message.get("params", {})
    if not request_id or len(request_id) > MAX_REQUEST_ID:
        raise ProtocolError("invalid request id")
    if not operation or len(operation) > MAX_OPERATION_NAME:
        raise ProtocolError("invalid operation")
    if not isinstance(params, dict):
        raise ProtocolError("params must be an object")
    return request_id, operation, params


def response(request_id: str, *, result: Any = None, error: str | None = None) -> bytes:
    payload: dict[str, Any] = {"id": request_id, "ok": error is None}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return encode_message(payload)
