"""Regression contracts for Edge 2 safety symptoms seen 2026-08-29."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))
sys.path.insert(0, str(ROOT / "headend"))

import agent as edge_agent  # noqa: E402
from api import ssh_tunnel_terminal_api as terminal_api  # noqa: E402
from database import now_utc  # noqa: E402


class _FakeTunnelQuery:
    def __init__(self, latest):
        self._latest = latest

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._latest


class _FakeDb:
    def __init__(self, latest):
        self._latest = latest

    def query(self, *_args, **_kwargs):
        return _FakeTunnelQuery(self._latest)


def test_active_reverse_tunnel_requires_reachable_local_tcp_port(monkeypatch) -> None:
    latest = SimpleNamespace(event="connected", remote_port=2204, event_at=now_utc())
    monkeypatch.setattr(terminal_api, "_localhost_tcp_reachable", lambda _port: False)

    assert terminal_api._active_reverse_tunnel(_FakeDb(latest), "TL-043EB9E72EFD") is None


def test_active_reverse_tunnel_allows_old_connected_log_when_port_is_reachable(monkeypatch) -> None:
    latest = SimpleNamespace(event="connected", remote_port=2204, event_at=now_utc() - timedelta(hours=1))
    monkeypatch.setattr(terminal_api, "_localhost_tcp_reachable", lambda _port: True)

    assert terminal_api._active_reverse_tunnel(_FakeDb(latest), "TL-C87FF9587CA0") is latest


def test_denied_terminal_closes_short_lived_grant() -> None:
    source = (ROOT / "headend/api/ssh_tunnel_terminal_api.py").read_text(encoding="utf-8")

    deny_block = source.split("def _deny_terminal", 1)[1].split("def create_ssh_tunnel_terminal_router", 1)[0]
    assert "grant.status = \"expired\"" in deny_block
    assert "grant.status = \"revoked\"" in deny_block
    assert "grant.revoked_by = \"ssh_terminal\"" in deny_block
    assert "grant.revoke_reason = reason" in deny_block


def test_camera_feature_detection_powers_off_relay_after_driver_failure() -> None:
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    agent._camera_power_on = MagicMock()
    agent._camera_power_off = MagicMock()
    agent._camera_power_mode = MagicMock(return_value="relay")
    agent._driver = MagicMock()
    agent._driver.connect.side_effect = RuntimeError("ptp unavailable")
    agent._emit_siem_event = MagicMock()

    agent._load_camera_features()

    agent._camera_power_on.assert_called_once_with("feature detection")
    agent._camera_power_off.assert_called_once_with("feature detection", force=True)
    assert agent._has_autofocus is False
    assert agent._has_refocus is False


def test_camera_feature_detection_powers_off_relay_after_success() -> None:
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    agent._camera_power_on = MagicMock()
    agent._camera_power_off = MagicMock()
    agent._camera_power_mode = MagicMock(return_value="relay")
    agent._check_camera_profile_known = MagicMock()
    agent._driver = MagicMock()
    agent._driver.supports_autofocus.return_value = True
    agent._driver.supports_remote_focus.return_value = False

    agent._load_camera_features()

    agent._driver.disconnect.assert_called_once()
    agent._camera_power_off.assert_called_once_with("feature detection", force=True)
    assert agent._has_autofocus is True
    assert agent._has_refocus is False
