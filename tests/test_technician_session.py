"""Behaviour test (2026-08-08): the shared camera-relay session that
totp-service.py and bootstrap_cli.py --camera-session both read/write.

Peter: "en tekniker-session... tvinges tændt når man er i menuen (både UI og
CLI)". No GPIO/DB needed — CameraSession only touches its own state file and
whatever relay object it's given, so a fake relay is enough to prove the
lifecycle (start warms it up once, stop always powers off even with no
active session, expiry is respected).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

from camera.technician_session import CameraSession, MAX_DURATION_S, MIN_DURATION_S  # noqa: E402


class _FakeCameraRelay:
    def __init__(self):
        self.power_on_calls = 0
        self.force_off_calls = 0

    def power_on(self):
        self.power_on_calls += 1

    def force_off(self):
        self.force_off_calls += 1


class _FakeRelay:
    def __init__(self):
        self.camera = _FakeCameraRelay()


@pytest.fixture
def session(tmp_path):
    return CameraSession(state_path=tmp_path / "camera-session.json")


def test_no_session_by_default(session):
    assert session.is_active() is False
    assert session.status() == {"active": False}


def test_start_powers_relay_and_opens_session(session):
    relay = _FakeRelay()
    status = session.start(relay, duration_s=1800, started_by="tester")
    assert relay.camera.power_on_calls == 1
    assert status["active"] is True
    assert status["started_by"] == "tester"
    assert session.is_active() is True


def test_duration_is_clamped_to_bounds(session):
    relay = _FakeRelay()
    session.start(relay, duration_s=1, started_by="")   # below MIN_DURATION_S
    status = session.status()
    assert status["remaining_s"] <= MIN_DURATION_S
    assert status["remaining_s"] > 0

    session2 = CameraSession(state_path=session.state_path.parent / "other.json")
    relay2 = _FakeRelay()
    session2.start(relay2, duration_s=999_999_999, started_by="")   # above MAX_DURATION_S
    assert session2.status()["remaining_s"] <= MAX_DURATION_S


def test_stop_always_forces_relay_off_even_with_no_active_session(session):
    relay = _FakeRelay()
    session.stop(relay)   # no start() called first
    assert relay.camera.force_off_calls == 1
    assert not session.state_path.exists()


def test_stop_clears_state_after_start(session):
    relay = _FakeRelay()
    session.start(relay, duration_s=600, started_by="")
    assert session.state_path.exists()
    session.stop(relay)
    assert relay.camera.force_off_calls == 1
    assert not session.state_path.exists()
    assert session.is_active() is False


def test_extend_without_active_session_raises(session):
    with pytest.raises(RuntimeError):
        session.extend(600)


def test_extend_pushes_expiry_out(session):
    relay = _FakeRelay()
    session.start(relay, duration_s=MIN_DURATION_S, started_by="")
    before = session.status()["remaining_s"]
    status = session.extend(3600)
    assert status["remaining_s"] > before


def test_expired_session_reads_as_inactive(session, monkeypatch):
    relay = _FakeRelay()
    session.start(relay, duration_s=MIN_DURATION_S, started_by="")
    # Simulate time passing beyond expiry without sleeping in the test.
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + MIN_DURATION_S + 10)
    assert session.is_active() is False
    assert session.status() == {"active": False}
