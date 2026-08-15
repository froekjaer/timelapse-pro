"""Kimi F-004: integration tests must never have an implicit live target."""

from pathlib import Path


CONFTEXT = (Path(__file__).resolve().parent / "conftest.py").read_text(encoding="utf-8")


def test_no_implicit_port_8000_default_remains():
    assert '"http://127.0.0.1:8000"' not in CONFTEXT
    assert 'os.getenv("TIMELAPSE_TEST_BASE_URL", "")' in CONFTEXT


def test_explicit_target_ack_is_required():
    assert 'TIMELAPSE_TEST_TARGET_ACK' in CONFTEXT
    assert 'I_UNDERSTAND_THIS_IS_A_TEST_TARGET' in CONFTEXT
    assert 'if TEST_TARGET_ACK != _REQUIRED_TEST_TARGET_ACK:' in CONFTEXT


def test_missing_target_fails_before_network_use():
    assert 'if not BASE_URL:' in CONFTEXT
    assert 'Integration test target is unset' in CONFTEXT
    assert 'self.base_url = require_explicit_test_target()' in CONFTEXT


def test_gate_is_rechecked_before_authenticated_requests():
    assert 'base_url = require_explicit_test_target()' in CONFTEXT
    assert 'requests.request(method, url' in CONFTEXT


def test_super_admin_fixture_cannot_mutate_db_before_target_gate():
    fixture_start = CONFTEXT.index('def super_admin_session():')
    fixture = CONFTEXT[fixture_start:]
    gate_pos = fixture.index('require_explicit_test_target()')
    db_pos = fixture.index('db_gen = get_db()')
    assert gate_pos < db_pos
