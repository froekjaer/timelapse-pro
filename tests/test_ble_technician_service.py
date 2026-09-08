from __future__ import annotations

from unittest.mock import MagicMock

from edge.ble_technician_service import BleTechnicianSession


def test_valid_totp_starts_offline_recovery_session():
    platform = MagicMock()
    session = MagicMock()
    platform.start_offline_recovery_session.return_value = session
    clock = iter([100.0, 100.0])
    ble = BleTechnicianSession(platform, totp_verifier=lambda code: code == "123456", now=lambda: next(clock))

    result = ble.handle_auth(b'{"type":"totp","code":"123456"}')

    assert result == b'{"id":"auth","ok":true,"result":{"authenticated":true,"expires_in_s":900}}'
    platform.start_offline_recovery_session.assert_called_once_with("ble-technician")


def test_invalid_totp_fails_closed_without_starting_session():
    platform = MagicMock()
    ble = BleTechnicianSession(platform, totp_verifier=lambda _code: False)

    result = ble.handle_auth(b'{"type":"totp","code":"123456"}')

    assert b'"ok":false' in result
    platform.start_offline_recovery_session.assert_not_called()
    assert ble.status()["authenticated"] is False


def test_request_requires_auth_and_delegates_to_service_platform():
    platform = MagicMock()
    ble = BleTechnicianSession(platform, totp_verifier=lambda _code: True)

    result = ble.handle_request(b'{"id":"r1","operation":"system.status"}')

    assert b'"ok":false' in result
    platform.call.assert_not_called()


def test_authenticated_request_uses_same_platform_session():
    platform = MagicMock()
    service_session = MagicMock()
    platform.start_offline_recovery_session.return_value = service_session
    platform.call.return_value = {"ok": True}
    clock = iter([100.0, 100.0, 101.0, 101.0])
    ble = BleTechnicianSession(platform, totp_verifier=lambda _code: True, now=lambda: next(clock))
    ble.handle_auth(b'{"type":"totp","code":"123456"}')

    result = ble.handle_request(b'{"id":"r1","operation":"system.status"}')

    assert b'"ok":true' in result
    platform.call.assert_called_once_with("system.status", session=service_session)


def test_idle_timeout_invalidates_service_session():
    platform = MagicMock()
    service_session = MagicMock()
    platform.start_offline_recovery_session.return_value = service_session
    clock = iter([100.0, 100.0 + 901.0])
    ble = BleTechnicianSession(platform, totp_verifier=lambda _code: True, now=lambda: next(clock))
    ble.handle_auth(b'{"type":"totp","code":"123456"}')

    result = ble.handle_request(b'{"id":"r1","operation":"system.status"}')

    assert b'"ok":false' in result
    platform.invalidate.assert_called_once_with(service_session, reason="ble_idle_timeout")
