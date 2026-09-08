"""BLE technician transport adapter.

This module deliberately contains no Bluetooth or hardware calls. A GATT
adapter feeds messages into this session object; the object authenticates with
the provisioned local TOTP and delegates all work to ServicePlatform.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ble_technician_protocol import (
    ProtocolError,
    decode_message,
    response,
    validate_auth_message,
    validate_operation_message,
)


class BleTechnicianSession:
    def __init__(
        self,
        platform: Any,
        *,
        totp_verifier: Callable[[str], bool],
        idle_timeout_s: int = 900,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.platform = platform
        self.totp_verifier = totp_verifier
        self.idle_timeout_s = idle_timeout_s
        self.now = now
        self.authenticated = False
        self.authenticated_at: float | None = None
        self.last_activity: float | None = None
        self._session = None

    def handle_auth(self, raw: bytes) -> bytes:
        try:
            code = validate_auth_message(decode_message(raw))
            if not self.totp_verifier(code):
                raise PermissionError("TOTP rejected")
            self._session = self.platform.start_offline_recovery_session("ble-technician")
            self.authenticated = True
            self.authenticated_at = self.last_activity = self.now()
            return response("auth", result={"authenticated": True, "expires_in_s": self.idle_timeout_s})
        except (ProtocolError, PermissionError, ValueError) as exc:
            self.invalidate("authentication_failed")
            return response("auth", error=str(exc))

    def handle_request(self, raw: bytes) -> bytes:
        try:
            request_id, operation, params = validate_operation_message(decode_message(raw))
            session = self._active_session()
            result = self.platform.call(operation, session=session, **params)
            self.last_activity = self.now()
            return response(request_id, result=result)
        except (ProtocolError, PermissionError, KeyError, ValueError, RuntimeError) as exc:
            request_id = "unknown"
            try:
                request_id = str(decode_message(raw).get("id") or "unknown")
            except ProtocolError:
                pass
            return response(request_id, error=str(exc))

    def invalidate(self, reason: str = "logout") -> None:
        if self._session is not None:
            self.platform.invalidate(self._session, reason=reason)
        self._session = None
        self.authenticated = False
        self.authenticated_at = None
        self.last_activity = None

    def status(self) -> dict[str, Any]:
        remaining = None
        authenticated = False
        if self.authenticated and self._session is not None and self.last_activity is not None:
            try:
                self._active_session()
                authenticated = True
            except PermissionError:
                authenticated = False
            remaining = max(0, int(self.idle_timeout_s - (self.now() - self.last_activity)))
        return {
            "authenticated": authenticated,
            "transport": "ble-gatt",
            "idle_expires_in_s": remaining,
        }

    def _active_session(self):
        if not self.authenticated or self._session is None:
            raise PermissionError("BLE technician authentication required")
        if self.last_activity is None or self.now() - self.last_activity >= self.idle_timeout_s:
            self.invalidate("ble_idle_timeout")
            raise PermissionError("BLE technician session expired")
        try:
            self._session.check_active(self.now())
        except PermissionError:
            self.invalidate(self._session.invalidation_reason or "grant_expired")
            raise
        return self._session
