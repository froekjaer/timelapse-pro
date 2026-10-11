"""Seed a login user with a password and a passkey for the browser login test.

Writes the passkey's private key to the JSON file given as argv[1]; the
Playwright test loads it into Chromium's virtual authenticator (standing in
for Touch ID), so the real login page, Headend and database run end to end.
Test-only: refuses any database whose name is not *_test or *_e2e.
"""
from __future__ import annotations

import base64
import json
import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL.rstrip("/").split("?")[0].endswith(("_test", "_e2e")):
    sys.exit(f"refusing to seed non-test database: {DB_URL!r}")

import cbor2  # noqa: E402

from auth import _hash_password  # noqa: E402
from database import SessionLocal, User, WebAuthnCredential, create_tables  # noqa: E402

USERNAME = "e2e-fotograf"
PASSWORD = "e2e-login-test-password"
RP_ID = os.environ.get("E2E_RP_ID", "localhost")
CRED_ID = os.urandom(16)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main(out_path: str) -> None:
    create_tables()
    key = ec.generate_private_key(ec.SECP256R1())
    n = key.public_key().public_numbers()
    cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})
    db = SessionLocal()
    try:
        for old in db.query(User).filter_by(username=USERNAME).all():
            db.query(WebAuthnCredential).filter_by(user_id=old.id).delete()
            db.delete(old)
        db.flush()
        user = User(username=USERNAME, password_hash=_hash_password(PASSWORD), role="viewer", is_active=True)
        db.add(user)
        db.flush()
        db.add(WebAuthnCredential(user_id=user.id, credential_id=CRED_ID, public_key=cose, sign_count=0,
                                  device_name="Playwright virtual authenticator", rp_id=RP_ID,
                                  transports='["internal"]'))
        db.commit()
        pkcs8 = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
        with open(out_path, "w") as fh:
            json.dump({"username": USERNAME, "password": PASSWORD, "rpId": RP_ID,
                       "credentialId": base64.b64encode(CRED_ID).decode(),
                       "userHandle": base64.b64encode(str(user.id).encode()).decode(),
                       "privateKey": base64.b64encode(pkcs8).decode()}, fh)
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1])
