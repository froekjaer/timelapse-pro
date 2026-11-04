"""Passkey login end to end through the real HTTP endpoints and the configured
database (2026-10-11).

In the normal CI job this runs on SQLite; the "Auth on Postgres" CI job runs
it against a real Postgres, which enforces column types and lengths. That is
exactly what the SQLite-only tests missed when passkey AutoFill returned 500
in production for a day and a half (settings.key VARCHAR(100), PR #300).

A software authenticator (P-256) signs the assertions, so the whole server
side runs for real: options, challenge storage, signature verification,
sign-count update, session cookie, /api/auth/me.
"""
import base64
import hashlib
import json
import struct

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import main
from database import Base, SessionLocal, Settings, User, WebAuthnCredential, engine

ORIGIN = "https://backend.timelapse-pro.dk:8443"
RP_ID = "timelapse-pro.dk"
USERNAME = "e2e-passkey-user"
CRED_ID = b"e2e-mac-passkey"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _cose(pub) -> bytes:
    import cbor2
    n = pub.public_numbers()
    return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})


def _assertion(key, challenge: str, user_id: int, counter: int):
    auth_data = hashlib.sha256(RP_ID.encode()).digest() + bytes([0x01 | 0x04]) + struct.pack(">I", counter)
    client = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": ORIGIN}).encode()
    sig = key.sign(auth_data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
    return {"id": _b64(CRED_ID), "rawId": _b64(CRED_ID), "type": "public-key",
            "response": {"authenticatorData": _b64(auth_data), "clientDataJSON": _b64(client),
                         "signature": _b64(sig), "userHandle": _b64(str(user_id).encode())}}


def _set(db, key, value):
    row = db.query(Settings).filter_by(key=key).first()
    previous = row.value if row else None
    if row:
        row.value = value
    else:
        db.add(Settings(key=key, value=value))
    return previous


@pytest.fixture()
def env():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for user in db.query(User).filter_by(username=USERNAME).all():
        db.query(WebAuthnCredential).filter_by(user_id=user.id).delete()
        db.delete(user)
    db.commit()
    previous = _set(db, "webauthn_allowed_origins", ORIGIN)
    user = User(username=USERNAME, password_hash="x", role="viewer", is_active=True)
    db.add(user)
    db.flush()
    key = ec.generate_private_key(ec.SECP256R1())
    db.add(WebAuthnCredential(user_id=user.id, credential_id=CRED_ID, public_key=_cose(key.public_key()),
                              sign_count=0, device_name="e2e", rp_id=RP_ID))
    db.commit()
    client = TestClient(main.app, base_url=ORIGIN, headers={"Origin": ORIGIN})
    try:
        yield client, key, user.id
    finally:
        db.query(Settings).filter(Settings.key.like("webauthn_anon_challenge_%")).delete(synchronize_session=False)
        db.query(Settings).filter_by(key=f"wabauthn_auth_challenge_{user.id}").delete()
        db.query(WebAuthnCredential).filter_by(user_id=user.id).delete()
        db.query(User).filter_by(id=user.id).delete()
        if previous is None:
            db.query(Settings).filter_by(key="webauthn_allowed_origins").delete()
        else:
            _set(db, "webauthn_allowed_origins", previous)
        db.commit()
        db.close()


def _logged_in_as(client) -> str:
    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return me.json()["username"]


def test_autofill_passkey_login_end_to_end(env):
    client, key, user_id = env
    begin = client.post("/api/auth/webauthn/login-begin", json={})
    assert begin.status_code == 200, begin.text
    options = begin.json()
    assert options["rpId"] == RP_ID and options["userVerification"] == "required"
    done = client.post("/api/auth/webauthn/login-complete", json=_assertion(key, options["challenge"], user_id, 1))
    assert done.status_code == 200, done.text
    assert _logged_in_as(client) == USERNAME


def test_username_passkey_login_end_to_end(env):
    client, key, user_id = env
    begin = client.post("/api/auth/webauthn/login-begin", json={"username": USERNAME})
    assert begin.status_code == 200, begin.text
    payload = {**_assertion(key, begin.json()["challenge"], user_id, 1), "username": USERNAME}
    done = client.post("/api/auth/webauthn/login-complete", json=payload)
    assert done.status_code == 200, done.text
    assert _logged_in_as(client) == USERNAME


def test_challenge_is_single_use(env):
    client, key, user_id = env
    challenge = client.post("/api/auth/webauthn/login-begin", json={}).json()["challenge"]
    assert client.post("/api/auth/webauthn/login-complete", json=_assertion(key, challenge, user_id, 1)).status_code == 200
    replay = client.post("/api/auth/webauthn/login-complete", json=_assertion(key, challenge, user_id, 2))
    assert replay.status_code == 401


def test_many_page_loads_keep_working_and_stay_bounded(env):
    client, _key, _user_id = env
    from services import webauthn_autofill as af
    for _ in range(af.MAX_OPEN_CHALLENGES + 10):
        assert client.post("/api/auth/webauthn/login-begin", json={}).status_code == 200
    db = SessionLocal()
    try:
        open_rows = db.query(Settings).filter(Settings.key.like(f"{af.CHALLENGE_PREFIX}%")).count()
    finally:
        db.close()
    assert open_rows <= af.MAX_OPEN_CHALLENGES
