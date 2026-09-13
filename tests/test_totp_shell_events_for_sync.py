"""edge/agent.py::_collect_totp_shell_events_for_sync() and
_persist_totp_shell_cursor_after_sync() (ADR-004, Development and Recovery
Shell Access) - the sibling of the already-proven break-glass SSH audit
drain/forward mechanism (see tests/test_break_glass_edge.py), reused here to
carry local-first audit events from edge/scripts/totp-service.py's
/mgmt/cli/bash/ws into the same consolidated Headend sync poll. Mirrors that
file's test structure and EdgeAgent.__new__() fixture pattern.
"""
import json
from pathlib import Path

import agent as edge_agent


def _make_agent():
    return edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)


def test_collect_totp_shell_events_parses_and_renames_queue(tmp_path):
    agent = _make_agent()
    agent.TOTP_SHELL_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    agent.TOTP_SHELL_EVENTS_PATH.write_text(
        json.dumps({
            "event_type": "shell_session_start", "severity": "warning",
            "session_id": "abcdef012345", "occurred_at": "2026-09-13T12:00:00Z",
            "totp_sid": "global", "source_ip": "192.168.42.10",
        }) + "\n"
    )

    events = agent._collect_totp_shell_events_for_sync()

    assert len(events) == 1
    assert events[0]["event_type"] == "shell_session_start"
    assert events[0]["source_ip"] == "192.168.42.10"
    assert events[0]["username"] is None  # no individual technician identity today
    # Queue file is drained immediately, .sending side file preserves the
    # read content until a sync poll actually confirms delivery.
    assert agent.TOTP_SHELL_EVENTS_PATH.read_text() == ""
    sending = agent.TOTP_SHELL_EVENTS_PATH.with_suffix(".jsonl.sending")
    assert sending.exists()


def test_collect_totp_shell_events_returns_empty_when_no_queue(tmp_path):
    agent = _make_agent()
    agent.TOTP_SHELL_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    assert agent._collect_totp_shell_events_for_sync() == []


def test_collect_totp_shell_events_merges_unsent_sending_file_instead_of_losing_it(tmp_path):
    agent = _make_agent()
    agent.TOTP_SHELL_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    sending = agent.TOTP_SHELL_EVENTS_PATH.with_suffix(".jsonl.sending")
    # Simulate a previous cycle whose sync POST failed - its .sending file
    # was never cleared.
    sending.write_text(json.dumps({"event_type": "shell_session_start", "session_id": "old"}) + "\n")
    agent.TOTP_SHELL_EVENTS_PATH.write_text(
        json.dumps({"event_type": "shell_session_end", "session_id": "old"}) + "\n"
    )

    events = agent._collect_totp_shell_events_for_sync()

    assert len(events) == 2
    assert {e["event_type"] for e in events} == {"shell_session_start", "shell_session_end"}
    # Nothing was silently dropped from the earlier failed attempt.
    assert agent.TOTP_SHELL_EVENTS_PATH.read_text() == ""


def test_collect_totp_shell_events_skips_malformed_lines_without_crashing(tmp_path):
    agent = _make_agent()
    agent.TOTP_SHELL_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    agent.TOTP_SHELL_EVENTS_PATH.write_text(
        "not valid json\n"
        + json.dumps({"event_type": "shell_session_start", "session_id": "ok"}) + "\n"
    )

    events = agent._collect_totp_shell_events_for_sync()

    assert len(events) == 1
    assert events[0]["event_type"] == "shell_session_start"


def test_persist_totp_shell_cursor_removes_sending_file(tmp_path):
    agent = _make_agent()
    agent.TOTP_SHELL_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    sending = agent.TOTP_SHELL_EVENTS_PATH.with_suffix(".jsonl.sending")
    sending.write_text("leftover\n")

    agent._persist_totp_shell_cursor_after_sync()

    assert not sending.exists()


def test_persist_totp_shell_cursor_is_a_noop_when_nothing_pending(tmp_path):
    agent = _make_agent()
    agent.TOTP_SHELL_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    agent._persist_totp_shell_cursor_after_sync()  # must not raise
