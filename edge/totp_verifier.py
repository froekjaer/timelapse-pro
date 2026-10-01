"""Small dependency-free TOTP verifier for system services."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import struct
import time


def _key(secret: str) -> bytes | None:
    try:
        return base64.b32decode(
            secret.replace(" ", "").upper() + "=" * (-len(secret) % 8),
            casefold=True,
        )
    except (ValueError, binascii.Error):
        return None


def code_at_step(key: bytes, step: int) -> str:
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    index = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[index:index + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def matching_steps(secret: str, code: str, *, now: float | None = None, window: int = 3) -> list[int]:
    """All time steps within +-window of ``now`` at which ``code`` is valid,
    closest to ``now`` first (newer before older on ties)."""
    if not secret or len(code) != 6 or not code.isdigit() or window < 0:
        return []
    key = _key(secret)
    if key is None:
        return []
    counter = int((time.time() if now is None else now) // 30)
    offsets = sorted(range(-window, window + 1), key=lambda o: (abs(o), -o))
    return [counter + o for o in offsets if hmac.compare_digest(code, code_at_step(key, counter + o))]


def verify_totp(secret: str, code: str, *, now: float | None = None, window: int = 3) -> bool:
    """Stateless check — accepts reuse. Logins must use
    totp_login_guard.TotpLoginGuard.verify_and_consume (single-use)."""
    return bool(matching_steps(secret, code, now=now, window=window))
