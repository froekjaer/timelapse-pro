"""TimeLapse Pro — Edge commissioner authentication (TPA-00 / SEC-016).

Runs on the edge. Decides HOW a commissioner may log in to the edge-local
management UI, given connectivity and available factors, and verifies offline
credentials against the signed, device-bound cache baked at image generation.

Guarantees:
- No world-known secret anywhere. Missing/expired/invalid cache => DENY.
- The strongest available method is chosen automatically.
- Every result carries a human-readable ``message`` the login UI MUST display,
  so the operator always knows which method (and online/offline) is in force.

Pure-ish and unit-testable: crypto is stdlib (hmac/hashlib); password check and
TOTP check are injected so tests need no bcrypt/pyotp, while production wires the
real verifiers.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence


class LoginMethod(str, Enum):
    WEBAUTHN_ONLINE = "webauthn_online"          # Windows Hello / Touch ID via headend
    TOTP_ONLINE = "totp_online"                  # user+password+personal TOTP via headend
    TOTP_OFFLINE_CACHE = "totp_offline_cache"    # verified against signed local cache
    BOOTSTRAP_FIRST_RUN = "bootstrap_first_run"  # per-device bootstrap code, first commissioning
    DENIED = "denied"                            # fail closed


# Danish login-UI messages. The UI MUST render `message` for the chosen method.
_MESSAGES = {
    LoginMethod.WEBAUTHN_ONLINE:
        "Online — Windows Hello / Touch ID (verificeret mod headend).",
    LoginMethod.TOTP_ONLINE:
        "Online — bruger, adgangskode og personlig TOTP (verificeret mod headend).",
    LoginMethod.TOTP_OFFLINE_CACHE:
        "Offline — verificeret mod lokal, signeret idriftsætter-cache (udløber {expiry}).",
    LoginMethod.BOOTSTRAP_FIRST_RUN:
        "Førstegangs-idriftsættelse — per-device bootstrap-kode (engangs; skift ved online-sync).",
    LoginMethod.DENIED:
        "Enheden er ikke idriftsat, eller den lokale idriftsætter-cache er udløbet. "
        "Kontakt headend for at re-provisionere.",
}


class BundleError(Exception):
    """Cache invalid — fail closed."""


@dataclass(frozen=True)
class LoginPlan:
    method: LoginMethod
    message: str
    online: bool


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    method: LoginMethod
    message: str
    username: Optional[str] = None


def _canonical(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_verified_cache(
    bundle: Mapping[str, Any],
    *,
    signing_key: bytes,
    device_id: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify signature + device binding + expiry (fail closed). Return payload."""
    if not isinstance(bundle, Mapping) or "payload" not in bundle or "signature" not in bundle:
        raise BundleError("malformed cache")
    payload = bundle["payload"]
    expected = hmac.new(signing_key, _canonical(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(bundle["signature"])):
        raise BundleError("cache signature invalid (fail closed)")
    if payload.get("device_id") != device_id:
        raise BundleError("cache bound to a different device (fail closed)")
    current = time.time() if now is None else now
    if current >= payload.get("expires_at", 0):
        raise BundleError("cache expired — re-sync required (fail closed)")
    return payload


def resolve_login_method(
    *,
    online: bool,
    has_verified_cache: bool,
    cache_expires_at: Optional[int],
    commissioner_has_webauthn: bool,
    is_first_run: bool,
    now: float | None = None,
) -> LoginPlan:
    """Pick the strongest available method and build the mandatory login message."""
    if online and commissioner_has_webauthn:
        m = LoginMethod.WEBAUTHN_ONLINE
    elif online:
        m = LoginMethod.TOTP_ONLINE
    elif has_verified_cache:
        m = LoginMethod.TOTP_OFFLINE_CACHE
    elif is_first_run:
        m = LoginMethod.BOOTSTRAP_FIRST_RUN
    else:
        m = LoginMethod.DENIED

    msg = _MESSAGES[m]
    if m is LoginMethod.TOTP_OFFLINE_CACHE and cache_expires_at:
        expiry = time.strftime("%Y-%m-%d", time.gmtime(cache_expires_at))
        msg = msg.format(expiry=expiry)
    return LoginPlan(method=m, message=msg, online=online)


def authenticate_offline(
    *,
    payload: Mapping[str, Any],
    username: str,
    password: str,
    totp_code: str,
    verify_password: Callable[[str, str], bool],
    verify_totp: Callable[[str, str], bool],
    decrypt_totp_secret: Callable[[str], str],
) -> AuthResult:
    """Verify a commissioner offline against the signed cache. Fail closed.

    Both factors (password AND personal TOTP) are required. Injected verifiers
    keep this testable; production passes bcrypt.checkpw and pyotp.verify.
    """
    plan_msg = _MESSAGES[LoginMethod.TOTP_OFFLINE_CACHE]
    expiry = payload.get("expires_at")
    if expiry:
        plan_msg = plan_msg.format(expiry=time.strftime("%Y-%m-%d", time.gmtime(expiry)))

    record = None
    for rec in payload.get("commissioners", []):
        if rec.get("username") == username and rec.get("role") == "commissioner":
            record = rec
            break
    if record is None:
        return AuthResult(False, LoginMethod.DENIED, _MESSAGES[LoginMethod.DENIED])

    if not verify_password(password, record["password_hash"]):
        return AuthResult(False, LoginMethod.DENIED, _MESSAGES[LoginMethod.DENIED], username)

    try:
        secret = decrypt_totp_secret(record["totp_secret_enc"])
    except Exception:
        return AuthResult(False, LoginMethod.DENIED, _MESSAGES[LoginMethod.DENIED], username)
    if not secret or not verify_totp(secret, totp_code):
        return AuthResult(False, LoginMethod.DENIED, _MESSAGES[LoginMethod.DENIED], username)

    return AuthResult(True, LoginMethod.TOTP_OFFLINE_CACHE, plan_msg, username)
