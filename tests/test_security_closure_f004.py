"""Kimi F-004: integration tests must never have an implicit live target."""

import pytest

import conftest


def test_integration_target_missing_fails_closed(monkeypatch):
    monkeypatch.setattr(conftest, "BASE_URL", "")
    monkeypatch.setattr(conftest, "TEST_TARGET_ACK", "")
    with pytest.raises(RuntimeError, match="target is unset"):
        conftest.require_explicit_test_target()


def test_integration_target_requires_explicit_ack(monkeypatch):
    monkeypatch.setattr(conftest, "BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setattr(conftest, "TEST_TARGET_ACK", "")
    with pytest.raises(RuntimeError, match="Integration HTTP disabled"):
        conftest.require_explicit_test_target()


def test_explicit_target_and_ack_are_accepted(monkeypatch):
    monkeypatch.setattr(conftest, "BASE_URL", "https://test-headend.invalid:8443")
    monkeypatch.setattr(
        conftest,
        "TEST_TARGET_ACK",
        "I_UNDERSTAND_THIS_IS_A_TEST_TARGET",
    )
    assert conftest.require_explicit_test_target() == "https://test-headend.invalid:8443"


def test_no_implicit_port_8000_default_remains():
    source = (conftest.REPO_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert '"http://127.0.0.1:8000"' not in source
