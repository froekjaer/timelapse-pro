"""Tests for the TPA-00 commissioner provisioning + fail-closed edge auth.

Run: python3 -m pytest test_tpa00_commissioner.py -v
Pure stdlib + injected verifiers; no bcrypt/pyotp/app needed.
"""
import time

import pytest

import bt_totp_security as sec
import commissioner as hh
import commissioner_auth as edge

KEY = b"test-signing-key-not-for-prod"


# ---- bt_totp_security (fail-closed base secret) ---------------------------

def test_known_weak_secret_rejected():
    assert sec.is_known_weak_secret("JBSWY3DPEHPK3PXP")
    assert sec.is_known_weak_secret("")
    assert sec.is_known_weak_secret(None)


def test_generated_secret_is_not_weak_and_unique():
    a, b = sec.generate_bootstrap_secret(), sec.generate_bootstrap_secret()
    assert a != b
    assert not sec.is_known_weak_secret(a)
    assert len(a) >= 16


def test_resolve_base_fails_closed_on_missing_or_weak():
    # missing device -> None
    assert sec.resolve_bt_totp_base(None, None, getter=lambda d, x: "x") is None
    # stored weak secret -> None (never returns the world-known default)
    assert sec.resolve_bt_totp_base(None, "TL-1", getter=lambda d, x: "JBSWY3DPEHPK3PXP") is None
    # missing stored -> None
    assert sec.resolve_bt_totp_base(None, "TL-1", getter=lambda d, x: None) is None
    # good per-device secret -> returned
    assert sec.resolve_bt_totp_base(None, "TL-1", getter=lambda d, x: "ABCDEF23456789") == "ABCDEF23456789"


def test_factory_default_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TIMELAPSE_ALLOW_FACTORY_TOTP", raising=False)
    assert sec.allow_factory_default() is False
    monkeypatch.setenv("TIMELAPSE_ALLOW_FACTORY_TOTP", "1")
    assert sec.allow_factory_default() is True


# ---- commissioner bundle (build + verify) ---------------------------------

def _rec(username="alice"):
    return hh.CommissionerRecord(
        username=username,
        password_hash="$2b$12$abcdefghijklmnopqrstuv",  # bcrypt-shaped
        totp_secret_enc="enc:SECRET",
    )


def test_bundle_roundtrip_ok():
    b = hh.build_commissioner_bundle(
        device_id="TL-DEVICE-1", commissioners=[_rec()],
        signing_key=KEY, key_id="k1", now=1000, ttl_seconds=3600)
    payload = hh.verify_commissioner_bundle(
        b, signing_key=KEY, expected_device_id="TL-DEVICE-1", now=1500)
    assert payload["commissioners"][0]["username"] == "alice"


def test_bundle_rejects_non_commissioner():
    bad = hh.CommissionerRecord(username="bob", password_hash="$2b$x",
                                totp_secret_enc="e", role="admin")
    with pytest.raises(hh.BundleError, match="not a commissioner"):
        hh.build_commissioner_bundle(device_id="d", commissioners=[bad],
                                     signing_key=KEY, key_id="k")


def test_bundle_requires_bcrypt_hash():
    bad = hh.CommissionerRecord(username="c", password_hash="plaintextpw",
                                totp_secret_enc="e")
    with pytest.raises(hh.BundleError, match="bcrypt"):
        hh.build_commissioner_bundle(device_id="d", commissioners=[bad],
                                     signing_key=KEY, key_id="k")


def test_bundle_tamper_detected():
    b = hh.build_commissioner_bundle(device_id="d", commissioners=[_rec()],
                                     signing_key=KEY, key_id="k", now=1000)
    b["payload"]["commissioners"][0]["username"] = "mallory"
    with pytest.raises(hh.BundleError, match="signature invalid"):
        hh.verify_commissioner_bundle(b, signing_key=KEY, expected_device_id="d", now=1100)


def test_bundle_wrong_device_rejected():
    b = hh.build_commissioner_bundle(device_id="d1", commissioners=[_rec()],
                                     signing_key=KEY, key_id="k", now=1000)
    with pytest.raises(hh.BundleError, match="different device"):
        hh.verify_commissioner_bundle(b, signing_key=KEY, expected_device_id="d2", now=1100)


def test_bundle_expiry_rejected():
    b = hh.build_commissioner_bundle(device_id="d", commissioners=[_rec()],
                                     signing_key=KEY, key_id="k", now=1000, ttl_seconds=100)
    with pytest.raises(hh.BundleError, match="expired"):
        hh.verify_commissioner_bundle(b, signing_key=KEY, expected_device_id="d", now=2000)


# ---- edge login-method resolver -------------------------------------------

def test_online_prefers_webauthn():
    p = edge.resolve_login_method(online=True, has_verified_cache=True, cache_expires_at=None,
                                  commissioner_has_webauthn=True, is_first_run=False)
    assert p.method is edge.LoginMethod.WEBAUTHN_ONLINE and "Windows Hello" in p.message


def test_online_without_webauthn_uses_totp_online():
    p = edge.resolve_login_method(online=True, has_verified_cache=True, cache_expires_at=None,
                                  commissioner_has_webauthn=False, is_first_run=False)
    assert p.method is edge.LoginMethod.TOTP_ONLINE and "verificeret mod headend" in p.message


def test_offline_with_cache_uses_cache_and_shows_expiry():
    exp = int(time.time()) + 3600
    p = edge.resolve_login_method(online=False, has_verified_cache=True, cache_expires_at=exp,
                                  commissioner_has_webauthn=True, is_first_run=False)
    assert p.method is edge.LoginMethod.TOTP_OFFLINE_CACHE
    assert "Offline" in p.message and "udløber" in p.message


def test_offline_first_run_uses_bootstrap():
    p = edge.resolve_login_method(online=False, has_verified_cache=False, cache_expires_at=None,
                                  commissioner_has_webauthn=False, is_first_run=True)
    assert p.method is edge.LoginMethod.BOOTSTRAP_FIRST_RUN


def test_no_method_fails_closed():
    p = edge.resolve_login_method(online=False, has_verified_cache=False, cache_expires_at=None,
                                  commissioner_has_webauthn=False, is_first_run=False)
    assert p.method is edge.LoginMethod.DENIED and "ikke idriftsat" in p.message


# ---- edge offline credential verification ---------------------------------

def _payload():
    b = hh.build_commissioner_bundle(device_id="d", commissioners=[_rec()],
                                     signing_key=KEY, key_id="k", now=1000, ttl_seconds=10_000)
    return edge.load_verified_cache(b, signing_key=KEY, device_id="d", now=1500)


def test_offline_auth_success_requires_both_factors():
    r = edge.authenticate_offline(
        payload=_payload(), username="alice", password="pw", totp_code="123456",
        verify_password=lambda pw, h: pw == "pw",
        verify_totp=lambda secret, code: code == "123456",
        decrypt_totp_secret=lambda enc: "REALSECRET")
    assert r.ok and r.method is edge.LoginMethod.TOTP_OFFLINE_CACHE


def test_offline_auth_wrong_password_denied():
    r = edge.authenticate_offline(
        payload=_payload(), username="alice", password="bad", totp_code="123456",
        verify_password=lambda pw, h: pw == "pw",
        verify_totp=lambda s, c: True,
        decrypt_totp_secret=lambda enc: "S")
    assert not r.ok and r.method is edge.LoginMethod.DENIED


def test_offline_auth_wrong_totp_denied():
    r = edge.authenticate_offline(
        payload=_payload(), username="alice", password="pw", totp_code="000000",
        verify_password=lambda pw, h: True,
        verify_totp=lambda s, c: c == "123456",
        decrypt_totp_secret=lambda enc: "S")
    assert not r.ok


def test_offline_auth_unknown_user_denied():
    r = edge.authenticate_offline(
        payload=_payload(), username="ghost", password="pw", totp_code="123456",
        verify_password=lambda pw, h: True, verify_totp=lambda s, c: True,
        decrypt_totp_secret=lambda enc: "S")
    assert not r.ok


def test_edge_cache_tamper_fails_closed():
    b = hh.build_commissioner_bundle(device_id="d", commissioners=[_rec()],
                                     signing_key=KEY, key_id="k", now=1000, ttl_seconds=10_000)
    b["signature"] = "deadbeef"
    with pytest.raises(edge.BundleError):
        edge.load_verified_cache(b, signing_key=KEY, device_id="d", now=1500)
