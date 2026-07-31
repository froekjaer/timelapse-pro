"""TimeLapse Pro — Commissioner bundle builder/verifier (headend side, TPA-00).

Builds the signed, device-bound offline commissioner cache that is baked into a
new edge image and refreshed on every online sync. The edge verifies it before
trusting it (see edge/commissioner/auth.py).

Signing: HMAC-SHA256 over canonical JSON in this reference implementation, so it
is testable without key infrastructure. PRODUCTION MUST use the existing
asymmetric OTA/config signing chain (Ed25519) — swap ``_sign``/``_verify`` for
the project's signer; the bundle shape and rules are unchanged.

Rules enforced here (all fail closed on the edge):
- bundle is bound to exactly one ``device_id`` (cannot be moved to another edge);
- bundle carries an explicit ``expires_at`` (a stolen edge cannot use it forever);
- only users holding the ``commissioner`` role are included;
- password hashes are bcrypt (never plaintext); TOTP secrets are carried
  encrypted by the caller before being placed in the bundle.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

BUNDLE_VERSION = 1
COMMISSIONER_ROLE = "commissioner"
DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # 30 days offline validity, then must re-sync


class BundleError(Exception):
    """Bundle could not be built or verified — treat as fail closed."""


@dataclass(frozen=True)
class CommissionerRecord:
    username: str
    password_hash: str          # bcrypt
    totp_secret_enc: str        # ciphertext, decryptable only on the device
    webauthn_cred_ids: tuple[str, ...] = field(default_factory=tuple)
    role: str = COMMISSIONER_ROLE


def _canonical(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(payload: Mapping[str, Any], key: bytes) -> str:
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


def build_commissioner_bundle(
    *,
    device_id: str,
    commissioners: Sequence[CommissionerRecord],
    signing_key: bytes,
    key_id: str,
    now: float | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    """Return a signed, device-bound commissioner bundle (JSON-serialisable)."""
    if not device_id:
        raise BundleError("device_id is required (bundle must be device-bound)")
    for rec in commissioners:
        if rec.role != COMMISSIONER_ROLE:
            raise BundleError(f"user {rec.username!r} is not a commissioner")
        if not rec.password_hash or not rec.password_hash.startswith("$2"):
            raise BundleError(f"user {rec.username!r} lacks a bcrypt password hash")
    issued = time.time() if now is None else now
    payload = {
        "bundle_version": BUNDLE_VERSION,
        "device_id": device_id,
        "issued_at": int(issued),
        "expires_at": int(issued + ttl_seconds),
        "key_id": key_id,
        "commissioners": [
            {
                "username": r.username,
                "password_hash": r.password_hash,
                "totp_secret_enc": r.totp_secret_enc,
                "webauthn_cred_ids": list(r.webauthn_cred_ids),
                "role": r.role,
            }
            for r in commissioners
        ],
    }
    return {"payload": payload, "signature": _sign(payload, signing_key)}


def verify_commissioner_bundle(
    bundle: Mapping[str, Any],
    *,
    signing_key: bytes,
    expected_device_id: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify signature, device binding and expiry. Raises BundleError on any
    problem (fail closed). Returns the payload on success.

    NOTE: this mirrors the edge-side check; kept here so headend tests and tools
    can validate what they emit.
    """
    if "payload" not in bundle or "signature" not in bundle:
        raise BundleError("malformed bundle")
    payload = bundle["payload"]
    expected_sig = _sign(payload, signing_key)
    if not hmac.compare_digest(expected_sig, str(bundle["signature"])):
        raise BundleError("signature invalid (fail closed)")
    if payload.get("device_id") != expected_device_id:
        raise BundleError("bundle is bound to a different device (fail closed)")
    current = time.time() if now is None else now
    if current >= payload.get("expires_at", 0):
        raise BundleError("bundle expired — device must re-sync online (fail closed)")
    return payload
