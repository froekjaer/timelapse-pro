"""Edge-side tests for break-glass password delivery and session auditing
(2026-08-25). See headend/tests/test_break_glass_delivery.py for the
headend half and Dokumentation/HANDOVER_LOG.md for the full story."""
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import agent as edge_agent


def _make_agent():
    return edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)


def test_apply_break_glass_password_runs_chpasswd_and_reports_hash(monkeypatch):
    agent = _make_agent()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs.get("input")))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run))

    result = agent._apply_break_glass_password([{"username": "emergency", "password": "s3cr3t"}])

    assert calls == [(["chpasswd"], "emergency:s3cr3t\n")]
    assert result == [{
        "username": "emergency",
        "password_sha256": hashlib.sha256(b"s3cr3t").hexdigest(),
    }]


def test_apply_break_glass_password_skips_malformed_entries(monkeypatch):
    agent = _make_agent()
    fake_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run))

    result = agent._apply_break_glass_password([
        {"username": "", "password": "x"},
        {"username": "emergency", "password": ""},
        "not-a-dict",
        None,
    ])

    assert result == []
    fake_run.assert_not_called()


def test_apply_break_glass_password_continues_after_chpasswd_failure(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(
        edge_agent, "subprocess",
        MagicMock(run=MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="no such user"))),
    )

    result = agent._apply_break_glass_password([{"username": "ghost", "password": "x"}])

    assert result == []


def test_repair_emergency_account_creates_user_and_sshd_block(tmp_path, monkeypatch):
    agent = _make_agent()
    agent.SSHD_CONFIG_PATH = tmp_path / "sshd_config"
    agent.SSHD_CONFIG_PATH.write_text("PasswordAuthentication no\n")
    agent.AUTHORIZED_TECHNICIANS_PATH = tmp_path / "authorized_technicians.json"
    agent.BREAKGLASS_LOG_DIR = tmp_path / "breakglass"
    agent.BREAKGLASS_EVENTS_PATH = agent.BREAKGLASS_LOG_DIR / "pending_events.jsonl"
    agent.BREAKGLASS_WRAPPER_PATH = tmp_path / "breakglass_shell_wrapper.sh"
    agent.BREAKGLASS_SUDOERS_PATH = tmp_path / "sudoers-timelapse-breakglass"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "getent":
            return MagicMock(returncode=1, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run))

    agent._repair_emergency_breakglass_account()

    assert any(c[0] == "useradd" for c in calls)
    assert any(c[0] == "/usr/sbin/sshd" and "-t" in c for c in calls)
    patched = agent.SSHD_CONFIG_PATH.read_text()
    assert "Match User emergency" in patched
    assert "PasswordAuthentication yes" in patched
    assert agent.BREAKGLASS_LOG_DIR.is_dir()
    assert agent.BREAKGLASS_EVENTS_PATH.exists()


def test_repair_emergency_account_chowns_log_tree_to_emergency_user(tmp_path, monkeypatch):
    """2026-08-25 (Peter's live login): the agent runs as root, which bypasses
    DAC permission checks, so root-owned 0700 log dirs looked fine from here
    but were unwritable by breakglass_shell_wrapper.sh, which runs AS
    "emergency" — an unprivileged login shell. `script` and the event-append
    both hit Permission denied before a shell was ever handed back, closing
    the SSH connection right after a successful password auth. The fix
    chowns the log tree to "emergency" so its own login shell can write to
    it; root keeps full access regardless of ownership."""
    agent = _make_agent()
    agent.SSHD_CONFIG_PATH = tmp_path / "sshd_config"
    original = "PasswordAuthentication no\n\nMatch User emergency\n    PasswordAuthentication yes\n"
    agent.SSHD_CONFIG_PATH.write_text(original)
    agent.AUTHORIZED_TECHNICIANS_PATH = tmp_path / "authorized_technicians.json"
    agent.BREAKGLASS_LOG_DIR = tmp_path / "breakglass"
    agent.BREAKGLASS_LOG_DIR.mkdir()
    (agent.BREAKGLASS_LOG_DIR / "sessions").mkdir()
    agent.BREAKGLASS_EVENTS_PATH = agent.BREAKGLASS_LOG_DIR / "pending_events.jsonl"
    agent.BREAKGLASS_EVENTS_PATH.write_text("")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "getent":
            return MagicMock(returncode=0, stdout="emergency:x:1002:1002::/home/emergency:/bin/bash", stderr="")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run))
    monkeypatch.setattr(
        "pwd.getpwnam",
        lambda name: MagicMock(pw_uid=1002, pw_gid=1002) if name == "emergency" else (_ for _ in ()).throw(KeyError(name)),
    )
    chown_calls = []
    monkeypatch.setattr(edge_agent.os, "chown", lambda path, uid, gid: chown_calls.append((Path(path), uid, gid)))

    agent._repair_emergency_breakglass_account()

    chowned_paths = {c[0] for c in chown_calls}
    assert chowned_paths == {
        agent.BREAKGLASS_LOG_DIR,
        agent.BREAKGLASS_LOG_DIR / "sessions",
        agent.BREAKGLASS_EVENTS_PATH,
    }
    assert all(c[1:] == (1002, 1002) for c in chown_calls)


def test_repair_emergency_account_is_noop_when_already_configured(tmp_path, monkeypatch):
    agent = _make_agent()
    agent.SSHD_CONFIG_PATH = tmp_path / "sshd_config"
    original = "PasswordAuthentication no\n\nMatch User emergency\n    PasswordAuthentication yes\n"
    agent.SSHD_CONFIG_PATH.write_text(original)
    agent.AUTHORIZED_TECHNICIANS_PATH = tmp_path / "authorized_technicians.json"
    agent.BREAKGLASS_LOG_DIR = tmp_path / "breakglass"
    agent.BREAKGLASS_EVENTS_PATH = agent.BREAKGLASS_LOG_DIR / "pending_events.jsonl"

    def fake_run(cmd, **kwargs):
        if cmd[0] == "getent":
            return MagicMock(returncode=0, stdout="emergency:x:1002:1002::/home/emergency:/bin/bash", stderr="")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run))

    agent._repair_emergency_breakglass_account()

    assert agent.SSHD_CONFIG_PATH.read_text() == original


def test_collect_breakglass_events_parses_and_renames_queue(tmp_path):
    agent = _make_agent()
    agent.BREAKGLASS_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    agent.BREAKGLASS_EVENTS_PATH.write_text(
        json.dumps({
            "event_type": "breakglass_session_start", "severity": "critical",
            "session_id": "abc", "occurred_at": "2026-08-25T12:00:00Z",
            "ssh_client": "10.0.0.5 51000 22",
        }) + "\n"
    )

    events = agent._collect_breakglass_events_for_sync()

    assert len(events) == 1
    assert events[0]["event_type"] == "breakglass_session_start"
    assert events[0]["username"] == "emergency"
    assert events[0]["source_ip"] == "10.0.0.5"
    # Queue file is drained immediately (wrapper appends fresh), but the
    # .sending side file preserves what was read until confirmed sent.
    assert agent.BREAKGLASS_EVENTS_PATH.read_text() == ""
    sending = agent.BREAKGLASS_EVENTS_PATH.with_suffix(".jsonl.sending")
    assert sending.exists()


def test_collect_breakglass_events_rechowns_recreated_queue_file_to_emergency(tmp_path, monkeypatch):
    """2026-08-25 (Peter's second live login attempt): the previous fix
    chowned the log tree once, but this method — which runs every sync
    cycle, as root — recreates pending_events.jsonl from scratch via
    path.write_text() whenever it drains events, silently resetting
    ownership back to root before breakglass_shell_wrapper.sh's next append.
    Peter kept hitting Permission denied on this exact file because his
    retries landed inside that window."""
    agent = _make_agent()
    agent.BREAKGLASS_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    agent.BREAKGLASS_EVENTS_PATH.write_text(
        json.dumps({"event_type": "breakglass_session_start", "occurred_at": "t1"}) + "\n"
    )
    monkeypatch.setattr(
        "pwd.getpwnam",
        lambda name: MagicMock(pw_uid=1002, pw_gid=1002) if name == "emergency" else (_ for _ in ()).throw(KeyError(name)),
    )
    chown_calls = []
    monkeypatch.setattr(edge_agent.os, "chown", lambda path, uid, gid: chown_calls.append((Path(path), uid, gid)))

    agent._collect_breakglass_events_for_sync()

    assert (agent.BREAKGLASS_EVENTS_PATH, 1002, 1002) in chown_calls


def test_collect_breakglass_events_returns_empty_when_no_queue(tmp_path):
    agent = _make_agent()
    agent.BREAKGLASS_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    assert agent._collect_breakglass_events_for_sync() == []


def test_persist_breakglass_cursor_removes_sending_file(tmp_path):
    agent = _make_agent()
    agent.BREAKGLASS_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    sending = agent.BREAKGLASS_EVENTS_PATH.with_suffix(".jsonl.sending")
    sending.write_text("leftover\n")

    agent._persist_breakglass_cursor_after_sync()

    assert not sending.exists()


def test_collect_breakglass_events_merges_unsent_sending_file_instead_of_losing_it(tmp_path):
    """A prior cycle's sync failed, leaving a .sending file un-deleted. New
    events queued since then must be merged in, not silently dropped."""
    agent = _make_agent()
    agent.BREAKGLASS_EVENTS_PATH = tmp_path / "pending_events.jsonl"
    sending = agent.BREAKGLASS_EVENTS_PATH.with_suffix(".jsonl.sending")
    sending.write_text(json.dumps({"event_type": "old_event", "occurred_at": "t1"}) + "\n")
    agent.BREAKGLASS_EVENTS_PATH.write_text(json.dumps({"event_type": "new_event", "occurred_at": "t2"}) + "\n")

    events = agent._collect_breakglass_events_for_sync()

    assert {e["event_type"] for e in events} == {"old_event", "new_event"}
