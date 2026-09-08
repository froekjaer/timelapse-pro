"""Small dependency-free TOTP verifier for system services."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import struct
import time


def verify_totp(secret: str, code: str, *, now: float | None = None, window: int = 3) -> bool:
    if not secret or len(code) != 6 or not code.isdigit() or window < 0:
        return False
    try:
        key = base64.b32decode(
            secret.replace(" ", "").upper() + "=" * (-len(secret) % 8),
            casefold=True,
        )
    except (ValueError, binascii.Error):
        return False
    counter = int((time.time() if now is None else now) // 30)
    for offset in range(-window, window + 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        value = (struct.unpack(">I", digest[index:index + 4])[0] & 0x7FFFFFFF) % 1_000_000
        if hmac.compare_digest(code, f"{value:06d}"):
            return True
    return False
