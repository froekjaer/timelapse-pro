"""Passkey AutoFill (usernameless) login, verified with a software authenticator
(Peter 2026-10-09: Safari hung after login-begin; Apple's recommended flow)."""
import base64
import hashlib
import json
import struct
from pathlib import Path

import pytest
import webauthn
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import Boolean, Column, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from headend.services import webauthn_autofill as af

ROOT = Path(__file__).resolve().parents[1]
RP_ID = "timelapse-pro.dk"
ORIGIN = "https://backend.timelapse-pro.dk:8443"
Base = declarative_base()


class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50))
    is_active = Column(Boolean, default=True)


class Cred(Base):
    __tablename__ = "creds"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    credential_id = Column(LargeBinary)
    public_key = Column(LargeBinary)
    sign_count = Column(Integer, default=0)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _cose(pub: ec.EllipticCurvePublicKey) -> bytes:
    import cbor2
    n = pub.public_numbers()
    return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})


@pytest.fixture()
def env():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    key = ec.generate_private_key(ec.SECP256R1())
    db.add(User(id=1, username="peter", is_active=True))
    db.add(User(id=2, username="lasse", is_active=True))
    db.add(Cred(id=10, user_id=1, credential_id=b"mac-passkey", public_key=_cose(key.public_key())))
    db.commit()
    return db, key


def _assertion(key, challenge: str, uv: bool = True, user_handle: bytes = b"1", cred_id: bytes = b"mac-passkey"):
    flags = 0x01 | (0x04 if uv else 0)
    auth_data = hashlib.sha256(RP_ID.encode()).digest() + bytes([flags]) + struct.pack(">I", 0)
    client = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": ORIGIN}).encode()
    sig = key.sign(auth_data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
    return {"id": _b64(cred_id), "rawId": _b64(cred_id), "type": "public-key",
            "response": {"authenticatorData": _b64(auth_data), "clientDataJSON": _b64(client),
                         "signature": _b64(sig), "userHandle": _b64(user_handle)}}


def _verify(db, payload):
    user, row, cred = af.resolve(db, payload, Settings, Cred, User)
    challenge = webauthn.base64url_to_bytes(json.loads(row.value)["challenge"])
    webauthn.verify_authentication_response(
        credential=payload, expected_challenge=challenge, expected_rp_id=RP_ID, expected_origin=ORIGIN,
        credential_public_key=cred.public_key, credential_current_sign_count=cred.sign_count,
        require_user_verification=True)
    db.delete(row)
    db.commit()
    return user


def test_options_ask_for_any_passkey_with_touch_id(env):
    db, _ = env
    opts = af.begin(db, Settings, RP_ID)
    assert opts["allowCredentials"] == [] and opts["userVerification"] == "required" and opts["rpId"] == RP_ID


def test_autofill_login_end_to_end_and_single_use(env):
    db, key = env
    opts = af.begin(db, Settings, RP_ID)
    payload = _assertion(key, opts["challenge"])
    assert _verify(db, payload).username == "peter"
    with pytest.raises(ValueError, match="Ingen aktiv udfordring"):
        af.resolve(db, payload, Settings, Cred, User)           # replay refused


def test_without_user_verification_is_refused(env):
    db, key = env
    opts = af.begin(db, Settings, RP_ID)
    with pytest.raises(Exception):
        _verify(db, _assertion(key, opts["challenge"], uv=False))


def test_expired_unknown_and_foreign_user_handle_refused(env):
    db, key = env
    opts = af.begin(db, Settings, RP_ID, now=1000.0)
    with pytest.raises(ValueError, match="udløbet"):
        af.resolve(db, _assertion(key, opts["challenge"]), Settings, Cred, User, now=1000.0 + af.CHALLENGE_TTL_S + 1)
    opts = af.begin(db, Settings, RP_ID)
    with pytest.raises(ValueError, match="Credential ikke fundet"):
        af.resolve(db, _assertion(key, opts["challenge"], cred_id=b"other"), Settings, Cred, User)
    with pytest.raises(ValueError, match="anden bruger"):
        af.resolve(db, _assertion(key, opts["challenge"], user_handle=b"2"), Settings, Cred, User)


def test_unauthenticated_begin_cannot_grow_settings_without_bound(env):
    db, _ = env
    for i in range(af.MAX_OPEN_CHALLENGES + 50):
        af.begin(db, Settings, RP_ID, now=5000.0 + i)
    assert db.query(Settings).filter(Settings.key.like(f"{af.CHALLENGE_PREFIX}%")).count() <= af.MAX_OPEN_CHALLENGES


def test_main_and_login_page_wiring():
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    begin = main.split("def webauthn_login_begin", 1)[1].split("@app.", 1)[0]
    complete = main.split("def webauthn_login_complete", 1)[1].split("@app.", 1)[0]
    assert "_webauthn_autofill.begin(db, Settings" in begin
    assert "_webauthn_autofill.resolve(db, payload, Settings, WebAuthnCredential, User)" in complete
    assert "require_user_verification = not username," in complete
    assert "db.delete(setting)" in complete
    assert "ResidentKeyRequirement.PREFERRED" in main
    page = (ROOT / "timelapse-ui/src/pages/LoginPage.tsx").read_text(encoding="utf-8")
    assert 'autoComplete="username webauthn"' in page and "useBrowserAutofill: true" in page
    for f in ("timelapse-ui/src/pages/UsersPage.tsx", "timelapse-ui/src/components/SshTerminalModal.tsx"):
        src = (ROOT / f).read_text(encoding="utf-8")
        assert "useAbortPasskeyOnLeave()" in src and "withPasskeyDeadline(start" in src
