from __future__ import annotations

import json

import pytest

from edge.ble_technician_protocol import (
    MAX_MESSAGE_BYTES,
    ProtocolError,
    decode_message,
    encode_message,
    validate_auth_message,
    validate_operation_message,
)


def test_totp_auth_message_is_strictly_bounded():
    assert validate_auth_message({"type": "totp", "code": "123456"}) == "123456"
    for code in ("12345", "1234567", "abcdef", ""):
        with pytest.raises(ProtocolError):
            validate_auth_message({"type": "totp", "code": code})


def test_auth_does_not_accept_another_credential_type():
    with pytest.raises(ProtocolError):
        validate_auth_message({"type": "password", "code": "123456"})


def test_operation_message_is_bounded_and_structured():
    assert validate_operation_message({"id": "1", "operation": "system.status"}) == (
        "1",
        "system.status",
        {},
    )
    with pytest.raises(ProtocolError):
        validate_operation_message({"id": "1", "operation": "system.status", "params": []})


def test_messages_are_json_and_size_limited():
    raw = encode_message({"id": "1", "result": {"ok": True}})
    assert json.loads(raw) == {"id": "1", "result": {"ok": True}}
    with pytest.raises(ProtocolError):
        decode_message(b"x" * (MAX_MESSAGE_BYTES + 1))


def test_malformed_message_fails_closed():
    with pytest.raises(ProtocolError):
        decode_message(b"not-json")
    with pytest.raises(ProtocolError):
        decode_message(b"[]")
