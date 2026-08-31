"""_service_policy_watch_loop() (edge/scripts/totp-service.py) polled Headend's
GET /api/config/{device_id} unconditionally every 10 seconds, forever, even
when no Live View or technician session was active on the device. Confirmed
live on TL-C87FF9587CA0 (2026-08-31): this ran 24/7 as a background thread of
the always-on timelapse-totp.service, completely independent of the intended
~1x/minute consolidated sync poll — a real, continuous data/power cost for
zero benefit while idle. Fixed to only fetch the central policy while
something is actually running that the policy could affect; the local status
checks that gate the fetch must themselves stay network-free, or the fix does
nothing.
"""
import importlib.util
import sys
from pathlib import Path
from unittest import mock

_MODULE_PATH = Path(__file__).resolve().parents[1] / "edge" / "scripts" / "totp-service.py"
_spec = importlib.util.spec_from_file_location("totp_service_gating_under_test", _MODULE_PATH)
totp_service = importlib.util.module_from_spec(_spec)
sys.modules["totp_service_gating_under_test"] = totp_service
_spec.loader.exec_module(totp_service)


def _run_one_iteration(monkeypatch, *, live_running, logged_in):
    monkeypatch.setattr(totp_service.VIDEO_MANAGER, "status", lambda: {"running": live_running})
    monkeypatch.setattr(totp_service, "_service_session_snapshot", lambda: {"logged_in": logged_in})
    refresh_mock = mock.Mock(return_value={"enabled": True, "live_view_enabled": True})
    monkeypatch.setattr(totp_service, "_refresh_service_policy", refresh_mock)

    calls = {"n": 0}
    def fake_wait(timeout):
        calls["n"] += 1
        if calls["n"] >= 1:
            totp_service.SERVICE_POLICY_STOP.set()
        return False
    monkeypatch.setattr(totp_service.SERVICE_POLICY_STOP, "wait", fake_wait)
    totp_service.SERVICE_POLICY_STOP.clear()

    totp_service._service_policy_watch_loop()
    totp_service.SERVICE_POLICY_STOP.clear()
    return refresh_mock


def test_idle_device_never_calls_headend(monkeypatch):
    refresh_mock = _run_one_iteration(monkeypatch, live_running=False, logged_in=False)
    refresh_mock.assert_not_called()


def test_active_live_view_calls_headend(monkeypatch):
    refresh_mock = _run_one_iteration(monkeypatch, live_running=True, logged_in=False)
    refresh_mock.assert_called_once()


def test_active_technician_session_calls_headend(monkeypatch):
    refresh_mock = _run_one_iteration(monkeypatch, live_running=False, logged_in=True)
    refresh_mock.assert_called_once()


def test_revoked_policy_stops_live_view(monkeypatch):
    monkeypatch.setattr(totp_service.VIDEO_MANAGER, "status", lambda: {"running": True})
    monkeypatch.setattr(totp_service, "_service_session_snapshot", lambda: {"logged_in": False})
    monkeypatch.setattr(
        totp_service, "_refresh_service_policy",
        mock.Mock(return_value={"enabled": False, "live_view_enabled": False}),
    )
    stop_mock = mock.Mock()
    monkeypatch.setattr(totp_service.VIDEO_MANAGER, "stop", stop_mock)

    calls = {"n": 0}
    def fake_wait(timeout):
        calls["n"] += 1
        totp_service.SERVICE_POLICY_STOP.set()
        return False
    monkeypatch.setattr(totp_service.SERVICE_POLICY_STOP, "wait", fake_wait)
    totp_service.SERVICE_POLICY_STOP.clear()

    totp_service._service_policy_watch_loop()
    totp_service.SERVICE_POLICY_STOP.clear()

    stop_mock.assert_called_once_with(reason="central_policy")
