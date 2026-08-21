"""Regression tests for the 2026-08-19 sync-poll consolidation.

Before this, edge/agent.py's _tick() ran three independently-timed loops
that each made their own HTTP round-trip — a 5-minute config/update-check
poll, a 60-minute heartbeat, and a 5-minute SIEM-log forward — plus a
redundant nested update-check timer inside the "5-minute" block. None of
them shared a network round-trip, and the heartbeat never even carried an
app_version (see test_heartbeat_reports_app_version.py for that half of the
incident). See Dokumentation/HANDOVER_LOG.md 2026-08-19.

_run_sync() replaces all of that with one request/response per poll cycle,
composing the same apply logic (_apply_fetched_config, _apply_update_policy)
the old separate loops already used — these tests prove that composition,
not the individual apply functions themselves (already covered elsewhere).
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import agent as edge_agent
from utils import inventory

AGENT_PATH = Path(__file__).resolve().parents[1] / "edge" / "agent.py"


def _make_agent():
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    agent._device_id = "TL-TESTDEVICE0001"
    agent._running = True
    agent._stop_event = MagicMock(is_set=MagicMock(return_value=False))
    agent._diag = MagicMock(collect=MagicMock(return_value={"cpu_temperature": 42.0}))
    agent._db = MagicMock(capture_stats=MagicMock(return_value={}))
    agent._connectivity = MagicMock()
    agent._last_heartbeat = None
    agent._last_inventory = None
    agent._cfg = {}
    agent._pending_siem_cursor = None
    agent._apply_technician_keys = MagicMock()
    return agent


def test_tick_gates_on_a_single_sync_interval_not_three_separate_timers():
    """Lock in the consolidation: _tick()'s own body must use one
    sync_interval-gated call to _run_sync(), and must not still carry the
    old separate config_poll_interval_minutes / heartbeat_interval_minutes /
    forward_interval_s gates it used to have.
    """
    source = AGENT_PATH.read_text(encoding="utf-8")
    tick_body = source.split("def _tick(self, mode: str) -> None:", 1)[1].split("\n    def ", 1)[0]

    assert "sync_poll_interval_minutes" in tick_body
    assert tick_body.count("self._run_sync()") == 1
    assert "heartbeat_interval_minutes" not in tick_body
    assert "config_poll_interval_minutes" not in tick_body
    assert "forward_interval_s" not in tick_body
    assert "self._send_heartbeat()" not in tick_body
    assert "self._forward_siem_logs()" not in tick_body


def test_run_sync_sends_one_request_with_app_version_siem_and_inventory(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(inventory, "current_app_version", lambda: "cab4e7f95109297c85e4aec58acac66330d2db13")
    agent._collect_siem_events_for_sync = MagicMock(return_value=[{"event_type": "log"}])
    agent._collect_inventory_if_due = MagicMock(return_value={"os_name": "ubuntu"})
    agent._apply_fetched_config = MagicMock()
    agent._apply_update_policy = MagicMock()
    agent._persist_siem_cursor_after_sync = MagicMock()
    agent._sync_time_from_headend = MagicMock()

    captured = {}

    def _fake_sync(diagnostics, capture_stats, siem_events, inventory_payload):
        captured["diagnostics"] = diagnostics
        captured["siem_events"] = siem_events
        captured["inventory"] = inventory_payload
        return True, {"server_time": "t", "config": {"config_version": "v"}, "pending_updates": []}

    agent._api = MagicMock(sync=_fake_sync)

    agent._run_sync()

    assert captured["diagnostics"]["updates"] == {"app_version": "cab4e7f95109297c85e4aec58acac66330d2db13"}
    assert captured["siem_events"] == [{"event_type": "log"}]
    assert captured["inventory"] == {"os_name": "ubuntu"}
    agent._apply_fetched_config.assert_called_once_with({"config_version": "v"})
    agent._apply_update_policy.assert_called_once_with(
        {"server_time": "t", "config": {"config_version": "v"}, "pending_updates": []}
    )
    agent._persist_siem_cursor_after_sync.assert_called_once()
    agent._connectivity.report_success.assert_called_once()


def test_run_sync_applies_technician_keys_from_response(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(inventory, "current_app_version", lambda: "x")
    agent._collect_siem_events_for_sync = MagicMock(return_value=[])
    agent._collect_inventory_if_due = MagicMock(return_value=None)
    agent._apply_fetched_config = MagicMock()
    agent._apply_update_policy = MagicMock()
    agent._sync_time_from_headend = MagicMock()
    fake_keys = [{"public_key": "ssh-ed25519 AAAA", "identity": "tekniker1:laptop"}]
    agent._api = MagicMock(sync=MagicMock(return_value=(True, {"pending_updates": [], "technician_keys": fake_keys})))

    agent._run_sync()

    agent._apply_technician_keys.assert_called_once_with(fake_keys)


def test_run_sync_skips_config_apply_when_response_has_no_config_change(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(inventory, "current_app_version", lambda: "x")
    agent._collect_siem_events_for_sync = MagicMock(return_value=[])
    agent._collect_inventory_if_due = MagicMock(return_value=None)
    agent._apply_fetched_config = MagicMock()
    agent._apply_update_policy = MagicMock()
    agent._persist_siem_cursor_after_sync = MagicMock()
    agent._sync_time_from_headend = MagicMock()
    agent._api = MagicMock(sync=MagicMock(return_value=(True, {"pending_updates": []})))

    agent._run_sync()

    agent._apply_fetched_config.assert_not_called()
    agent._persist_siem_cursor_after_sync.assert_not_called()
    agent._apply_update_policy.assert_called_once()


def test_run_sync_reports_failure_and_does_not_apply_anything_when_sync_fails():
    agent = _make_agent()
    agent._collect_siem_events_for_sync = MagicMock(return_value=[])
    agent._collect_inventory_if_due = MagicMock(return_value=None)
    agent._apply_fetched_config = MagicMock()
    agent._apply_update_policy = MagicMock()
    agent._api = MagicMock(sync=MagicMock(return_value=(False, None)))

    agent._run_sync()

    agent._apply_fetched_config.assert_not_called()
    agent._apply_update_policy.assert_not_called()
    agent._connectivity.report_failure.assert_called_once()
    agent._connectivity.report_success.assert_not_called()


def test_collect_siem_events_for_sync_does_not_post_directly(monkeypatch, tmp_path):
    """The old _forward_siem_logs() posted directly via self._api.send_siem_events();
    the replacement must only collect and return — _run_sync() is responsible for
    sending, as part of the single consolidated request."""
    agent = _make_agent()
    agent._siem_cursor_path = tmp_path / "cursor"
    agent._api = MagicMock()

    with patch.object(edge_agent, "subprocess") as fake_subprocess:
        fake_subprocess.run.return_value = MagicMock(returncode=0, stdout="")
        events = agent._collect_siem_events_for_sync()

    assert events == []
    agent._api.send_siem_events.assert_not_called()
