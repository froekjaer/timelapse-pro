"""Usernameless passkey login for browser AutoFill (Peter, 2026-10-09).

"Nu hænger login igen på Safari … fotografer bruger kun Mac og Safari."
Safari repeatedly sat in the Touch ID step after login-begin and never
reached login-complete. Apple's recommended flow is passkey AutoFill
(WebAuthn conditional mediation): the login page asks for a passkey *without*
a username, Safari offers the saved passkey as a suggestion in the username
field, and Touch ID runs from that suggestion. If Safari has no passkey for
the site it simply shows none, so the page never looks hung.

Without a username there is no per-user challenge row, so the challenge is
stored under its own value (single use, 5 minute lifetime) and the user is
found from the credential that answered it. User verification (Touch ID /
password on the Mac) is required for this path.
"""
from __future__ import annotations

import base64
import json
import time

CHALLENGE_PREFIX = "webauthn_anon_challenge_"
CHALLENGE_TTL_S = 300
MAX_OPEN_CHALLENGES = 200


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _purge(db, settings_model, now: float) -> None:
    rows = db.query(settings_model).filter(settings_model.key.like(f"{CHALLENGE_PREFIX}%")).all()
    live = []
    for row in rows:
        try:
            created = float(json.loads(row.value).get("created", 0))
        except (ValueError, TypeError, AttributeError):
            created = 0
        if now - created > CHALLENGE_TTL_S:
            db.delete(row)
        else:
            live.append((created, row))
    # Unauthenticated endpoint: never let it grow the table without bound.
    for _created, row in sorted(live, key=lambda item: item[0])[: max(0, len(live) - MAX_OPEN_CHALLENGES + 1)]:
        db.delete(row)


def begin(db, settings_model, rp_id: str, now: float | None = None) -> dict:
    """Authentication options with no allowCredentials (any passkey for rp_id)."""
    import webauthn
    from webauthn.helpers.structs import UserVerificationRequirement

    now = time.time() if now is None else now
    _purge(db, settings_model, now)
    options = webauthn.generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    opts = json.loads(webauthn.options_to_json(options))
    db.add(settings_model(key=CHALLENGE_PREFIX + opts["challenge"],
                          value=json.dumps({"challenge": opts["challenge"], "created": now})))
    db.commit()
    return opts


def resolve(db, payload: dict, settings_model, credential_model, user_model, now: float | None = None):
    """(user, challenge_row, credential) for a usernameless assertion, or raise ValueError.

    The challenge row is returned so the caller deletes it after verifying
    (single use); expired or unknown challenges are refused here.
    """
    now = time.time() if now is None else now
    try:
        client_data = json.loads(_b64url_decode(payload["response"]["clientDataJSON"]))
        challenge = str(client_data["challenge"])
        credential_id = _b64url_decode(str(payload.get("rawId") or ""))
    except (KeyError, TypeError, ValueError):
        raise ValueError("Ugyldigt passkey-svar")
    row = db.query(settings_model).filter_by(key=CHALLENGE_PREFIX + challenge).first()
    if row is None:
        raise ValueError("Ingen aktiv udfordring")
    if now - float(json.loads(row.value).get("created", 0)) > CHALLENGE_TTL_S:
        db.delete(row)
        db.commit()
        raise ValueError("Udfordringen er udløbet")
    cred = db.query(credential_model).filter_by(credential_id=credential_id).first()
    if cred is None:
        raise ValueError("Credential ikke fundet")
    user = db.query(user_model).filter_by(id=cred.user_id, is_active=True).first()
    if user is None:
        raise ValueError("Bruger ikke aktiv")
    user_handle = (payload.get("response") or {}).get("userHandle")
    if user_handle and _b64url_decode(user_handle) != str(user.id).encode():
        raise ValueError("Passkey tilhører en anden bruger")
    return user, row, cred
