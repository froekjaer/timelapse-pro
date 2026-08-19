"""Regression test: heartbeat must carry app_version so Headend's app-update
auto-detection (_process_update_report in headend/main.py) can actually fire.

Found 2026-08-19: DiagnosticsCollector.collect() (what every heartbeat sends)
never included an "updates" key at all. app_version was only computed by
collect_inventory(), which posts to a different endpoint (/api/inventory,
~once/day) that Headend never routes through _process_update_report. Net
effect: a newer Headend release was never auto-detected from real device
traffic — confirmed live when the edge/tools NPU-runner fix (PR #75) sat
cataloged and approvable for 10+ minutes without a PendingUpdate ever being
created for TL-043EB9E72EFD. See Dokumentation/HANDOVER_LOG.md 2026-08-19.
"""
from unittest.mock import MagicMock, patch

import agent as edge_agent
from utils import inventory


def _make_agent():
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    agent._device_id = "TL-TESTDEVICE0001"
    agent._running = True
    agent._stop_event = MagicMock(is_set=MagicMock(return_value=False))
    agent._diag = MagicMock(collect=MagicMock(return_value={"cpu_temperature": 42.0}))
    agent._db = MagicMock(capture_stats=MagicMock(return_value={}))
    agent._connectivity = MagicMock()
    agent._last_heartbeat = None
    agent._cfg = {}
    agent._report_inventory = MagicMock()
    return agent


def test_send_heartbeat_includes_current_app_version_in_updates_block(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(inventory, "current_app_version", lambda: "cab4e7f95109297c85e4aec58acac66330d2db13")

    sent = {}

    def _fake_send_heartbeat(diag, stats):
        sent.update(diag)
        return True, {}

    agent._api = MagicMock(send_heartbeat=_fake_send_heartbeat)

    agent._send_heartbeat(check_updates=False)

    assert sent.get("updates") == {"app_version": "cab4e7f95109297c85e4aec58acac66330d2db13"}


def test_send_heartbeat_still_works_when_app_version_lookup_fails(monkeypatch):
    """A version-lookup failure must not take down the whole heartbeat."""
    agent = _make_agent()

    def _boom():
        raise OSError("git not found")

    monkeypatch.setattr(inventory, "current_app_version", _boom)
    agent._api = MagicMock(send_heartbeat=MagicMock(return_value=(True, {})))

    agent._send_heartbeat(check_updates=False)  # must not raise

    agent._connectivity.report_success.assert_not_called()
    agent._connectivity.report_failure.assert_called_once()


def test_current_app_version_prefers_release_receipt_over_git(monkeypatch):
    monkeypatch.setattr(inventory, "_artifact_release_metadata", lambda: {"source_commit": "release-commit-abc"})
    monkeypatch.setattr(inventory, "_git_app_version", lambda: "git-short-sha")
    monkeypatch.setattr(inventory, "_git_app_tag", lambda: "v2.8.1-lab.30")

    assert inventory.current_app_version() == "release-commit-abc"


def test_current_app_version_falls_back_to_git_tag_then_commit(monkeypatch):
    monkeypatch.setattr(inventory, "_artifact_release_metadata", lambda: {})
    monkeypatch.setattr(inventory, "_git_app_version", lambda: "git-short-sha")
    monkeypatch.setattr(inventory, "_git_app_tag", lambda: None)

    assert inventory.current_app_version() == "git-short-sha"
