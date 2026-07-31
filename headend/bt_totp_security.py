"""TimeLapse Pro — BT PAN TOTP security helpers (TPA-00 / SEC-016 fix).

Purpose: remove the world-known factory TOTP secret (``JBSWY3DPEHPK3PXP``) as a
fail-open base and replace it with a fail-CLOSED, per-device secret.

Design:
- ``generate_bootstrap_secret()`` mints a unique base32 secret per device at
  provisioning / image-generation time.
- ``resolve_bt_totp_base(db, device_id)`` returns the per-device base secret or
  ``None``. ``None`` means "not provisioned" and callers MUST fail closed
  (deny + show a provisioning message), never fall back to a shared constant.
- ``is_known_weak_secret()`` lets CI and runtime reject any known demo secret so
  the class of bug cannot silently return.

This module is intentionally dependency-light (pyotp only for secret minting,
with a stdlib fallback) so it can be unit-tested without the app.
"""
from __future__ import annotations

import base64
import os
import secrets as _secrets
from typing import Optional

# Publicly known demo/test secrets that must NEVER be accepted in production.
# JBSWY3DPEHPK3PXP is pyotp's documentation example (== base32 "Hello!\xde\xad\xbe\xef").
KNOWN_WEAK_SECRETS = frozenset({
    "JBSWY3DPEHPK3PXP",
    "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",  # base32 of "12345678901234567890"
})


def is_known_weak_secret(secret: Optional[str]) -> bool:
    """True if ``secret`` is empty or a publicly known demo secret."""
    if not secret:
        return True
    return secret.strip().upper() in KNOWN_WEAK_SECRETS


def generate_bootstrap_secret(nbytes: int = 20) -> str:
    """Return a fresh, unique base32 TOTP secret (RFC 4226 recommends >=20 bytes).

    Uses pyotp if available for canonical formatting, else a stdlib base32.
    """
    try:  # pragma: no cover - exercised when pyotp present
        import pyotp  # type: ignore
        secret = pyotp.random_base32(length=32)
    except Exception:  # pragma: no cover - stdlib fallback path
        raw = _secrets.token_bytes(nbytes)
        secret = base64.b32encode(raw).decode("ascii").rstrip("=")
    # Defensive: never emit a known-weak value (astronomically unlikely).
    if is_known_weak_secret(secret):  # pragma: no cover
        return generate_bootstrap_secret(nbytes)
    return secret


def resolve_bt_totp_base(
    db,
    device_id: Optional[str],
    *,
    getter=None,
) -> Optional[str]:
    """Return the per-device bootstrap TOTP secret, or None (fail closed).

    ``getter`` is an injection point for testing / decoupling from the ORM. In
    production, callers pass a function that reads the encrypted per-device
    secret from CMDB. If the stored value is missing or known-weak, this returns
    None so the caller denies access instead of using a shared default.
    """
    if not device_id:
        return None
    if getter is None:  # pragma: no cover - real wiring done by caller
        def getter(_db, _dev):  # type: ignore
            from cmdb import get_device_secret  # lazy, optional
            return get_device_secret(_db, _dev, "bt_totp_secret")
    stored = getter(db, device_id)
    if is_known_weak_secret(stored):
        return None
    return stored


def allow_factory_default() -> bool:
    """Escape hatch for isolated LAB benches ONLY.

    Returns True only if the operator has *explicitly* opted in via
    ``TIMELAPSE_ALLOW_FACTORY_TOTP=1``. Default is False (fail closed). Even when
    True, callers should log loudly and never expose the device to a network.
    This exists so a developer can bring up a throwaway rig without provisioning,
    not as a production path.
    """
    return os.getenv("TIMELAPSE_ALLOW_FACTORY_TOTP", "0") == "1"
