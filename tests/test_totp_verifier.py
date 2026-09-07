from __future__ import annotations

import base64
import hashlib
import hmac
import struct

from edge.totp_verifier import verify_totp


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    index = digest[-1] & 0x0F
    return f"{(struct.unpack('>I', digest[index:index + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def test_rfc6238_style_totp_and_window():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert verify_totp(secret, _code(secret, 1), now=30, window=0)
    assert verify_totp(secret, _code(secret, 2), now=30, window=1)
    assert not verify_totp(secret, "000000", now=30, window=0)


def test_invalid_totp_inputs_fail_closed():
    assert not verify_totp("", "123456")
    assert not verify_totp("not-base32", "123456")
    assert not verify_totp("GEZDGNBVGY3TQOJQ", "12345")
