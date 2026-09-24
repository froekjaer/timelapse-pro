"""Tests for headend/main.py::_webauthn_credential_transports() — added 2026-09-24
after a passkey login hung indefinitely from a MacBook (worked fine from the
Headend's own browser). webauthn_credentials never stored which transport
(internal platform authenticator vs. cross-device/hybrid vs. USB) a credential
uses, so login-begin sent every allowCredentials entry unrestricted, letting
browsers fall into an ambiguous cross-device wait instead of failing cleanly.
See Dokumentation/HANDOVER_LOG.md, 2026-09-24 entry.
"""
from webauthn.helpers.structs import AuthenticatorTransport


def test_none_transports_returns_none_unrestricted():
    from headend.main import _webauthn_credential_transports

    assert _webauthn_credential_transports(None) is None


def test_empty_string_returns_none_unrestricted():
    from headend.main import _webauthn_credential_transports

    assert _webauthn_credential_transports("") is None


def test_single_internal_transport_decoded():
    from headend.main import _webauthn_credential_transports

    assert _webauthn_credential_transports('["internal"]') == [AuthenticatorTransport.INTERNAL]


def test_multiple_transports_decoded_in_order():
    from headend.main import _webauthn_credential_transports

    result = _webauthn_credential_transports('["usb", "nfc"]')
    assert result == [AuthenticatorTransport.USB, AuthenticatorTransport.NFC]


def test_malformed_json_fails_open_to_unrestricted():
    """A bad/corrupt stored value must never crash login-begin — fail open,
    same as if transports had never been stored."""
    from headend.main import _webauthn_credential_transports

    assert _webauthn_credential_transports("not-json") is None


def test_unknown_transport_value_fails_open_to_unrestricted():
    from headend.main import _webauthn_credential_transports

    assert _webauthn_credential_transports('["carrier-pigeon"]') is None
