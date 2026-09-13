"""ADR-004 (Development and Recovery Shell Access) — scoped implementation of
the multi-IP session tracking, shell-session cleanup on expiry, and local-first
shell audit logging identified in the corrected R04 analysis of
`codex/edge-terminal-renderer` (never merged) and the shell-endpoint security
assessment.

Provenance: the multi-IP session semantics reimplemented here mirror the
reasoning in `codex/edge-terminal-renderer` commit d67ca26d (2026-08-06,
never merged) - a technician's apparent source IP can legitimately change
mid-session across Bluetooth PAN / WiFi / Ethernet reconnects, and the session
token itself (256-bit HMAC, only issued after a correct TOTP code) is the real
access boundary, not the source IP. The shell-session audit logging reuses the
already-proven, already-merged break-glass SSH audit pattern
(`edge/scripts/breakglass_shell_wrapper.sh` +
`edge/agent.py::_collect_breakglass_events_for_sync()`), applied to the
Bluetooth TOTP portal's interactive shell instead. Neither change touches
TOTP verification, fail-closed `enable_interactive_shell` gating, or the
session cookie mechanism - those were verified correct in the prior
assessment and are intentionally left unchanged.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "edge" / "scripts" / "totp-service.py"


def _load_totp_service():
    os.environ["TIMELAPSE_EDGE_ROOT"] = str(ROOT / "edge")
    spec = importlib.util.spec_from_file_location(
        f"totp_service_shell_robustness_under_test_{time.time_ns()}", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _silence_iptables_and_bluetooth(totp_service, monkeypatch):
    """These tests exercise session/audit logic, not the real firewall or
    Bluetooth stack - neither exists on the machine running this test suite."""
    monkeypatch.setattr(totp_service, "_iptables_add", mock.Mock())
    monkeypatch.setattr(totp_service, "_iptables_remove", mock.Mock())
    monkeypatch.setattr(totp_service, "_forget_bluetooth_peer_for_ip", mock.Mock())


# -- Multi-IP session tracking -------------------------------------------------

def test_session_stays_valid_when_client_ip_changes_mid_session(monkeypatch):
    """A BT-PAN reconnect or WiFi roam can hand a technician a new IP without
    ending their TOTP session - the session token is the access boundary."""
    totp_service = _load_totp_service()
    _silence_iptables_and_bluetooth(totp_service, monkeypatch)

    token = "tok123"
    totp_service._sessions[token] = {
        "ips": {"192.168.42.10"},
        "expires": time.time() + 3600,
        "sid": "test-sid",
    }

    assert totp_service._valid_token(token, "192.168.42.10") is True
    # Reconnect from a new IP (new BT-PAN DHCP lease) - must NOT invalidate.
    assert totp_service._valid_token(token, "192.168.42.99") is True
    assert totp_service._sessions[token]["ips"] == {"192.168.42.10", "192.168.42.99"}


def test_new_ip_is_whitelisted_and_logged(monkeypatch):
    totp_service = _load_totp_service()
    iptables_add = mock.Mock()
    monkeypatch.setattr(totp_service, "_iptables_add", iptables_add)
    monkeypatch.setattr(totp_service, "_iptables_remove", mock.Mock())
    monkeypatch.setattr(totp_service, "_forget_bluetooth_peer_for_ip", mock.Mock())

    token = "tok456"
    totp_service._sessions[token] = {"ips": {"10.0.0.1"}, "expires": time.time() + 3600, "sid": "s"}

    totp_service._valid_token(token, "10.0.0.2")

    iptables_add.assert_called_once_with("10.0.0.2")
    # Already-seen IPs are not re-whitelisted on every request.
    iptables_add.reset_mock()
    totp_service._valid_token(token, "10.0.0.2")
    iptables_add.assert_not_called()


def test_unknown_token_is_rejected(monkeypatch):
    totp_service = _load_totp_service()
    _silence_iptables_and_bluetooth(totp_service, monkeypatch)
    assert totp_service._valid_token("does-not-exist", "1.2.3.4") is False


def test_expiry_removes_all_tracked_ips_not_just_the_current_one(monkeypatch):
    """A session seen from three different IPs over its lifetime must have
    all three un-whitelisted on expiry, not only the one in the current
    request - otherwise stale firewall entries accumulate."""
    totp_service = _load_totp_service()
    iptables_remove = mock.Mock()
    forget_peer = mock.Mock()
    monkeypatch.setattr(totp_service, "_iptables_add", mock.Mock())
    monkeypatch.setattr(totp_service, "_iptables_remove", iptables_remove)
    monkeypatch.setattr(totp_service, "_forget_bluetooth_peer_for_ip", forget_peer)

    token = "tok789"
    totp_service._sessions[token] = {
        "ips": {"192.168.42.10", "192.168.42.20", "10.1.1.1"},
        "expires": time.time() - 1,  # already expired
        "sid": "s",
    }

    assert totp_service._valid_token(token, "10.1.1.1") is False
    assert token not in totp_service._sessions
    assert {c.args[0] for c in iptables_remove.call_args_list} == {
        "192.168.42.10", "192.168.42.20", "10.1.1.1",
    }
    assert {c.args[0] for c in forget_peer.call_args_list} == {
        "192.168.42.10", "192.168.42.20", "10.1.1.1",
    }


# -- /logout closes shells and un-whitelists every tracked IP -----------------

def test_logout_closes_shell_and_removes_all_tracked_ips(monkeypatch):
    import asyncio

    totp_service = _load_totp_service()

    iptables_remove_calls = []
    forget_peer_calls = []
    monkeypatch.setattr(totp_service, "_iptables_remove", lambda ip: iptables_remove_calls.append(ip))
    monkeypatch.setattr(totp_service, "_forget_bluetooth_peer_for_ip", lambda ip: forget_peer_calls.append(ip))
    kill_calls = []
    monkeypatch.setattr(totp_service.os, "kill", lambda pid, sig: kill_calls.append(pid))
    monkeypatch.setattr(totp_service.os, "waitpid", lambda pid, opt: (0, 0))
    monkeypatch.setattr(totp_service.os, "close", lambda fd: None)
    audit_calls = []
    monkeypatch.setattr(totp_service, "_emit_shell_audit_event", lambda *a, **k: audit_calls.append((a, k)))

    token = "tok-logout"
    totp_service._sessions[token] = {
        "ips": {"192.168.42.10", "10.0.0.5"},
        "expires": totp_service.time.time() + 3600,
        "sid": "s",
    }
    totp_service._register_shell_session(token, child_pid=555, master_fd=7)

    class _FakeRequest:
        class client:
            host = "192.168.42.10"
        cookies = {totp_service.SESSION_COOKIE: token}

    class _FakeCookies(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    request = _FakeRequest()
    request.cookies = _FakeCookies({totp_service.SESSION_COOKIE: token})

    asyncio.run(totp_service.logout(request))

    assert token not in totp_service._sessions
    assert set(iptables_remove_calls) == {"192.168.42.10", "10.0.0.5"}
    assert set(forget_peer_calls) == {"192.168.42.10", "10.0.0.5"}
    assert kill_calls == [555]
    assert token not in totp_service.SHELL_SESSIONS


# -- Shell-session cleanup on expiry --------------------------------------------

def test_expired_session_closes_its_registered_shell(monkeypatch):
    totp_service = _load_totp_service()
    _silence_iptables_and_bluetooth(totp_service, monkeypatch)
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_DIR", Path("/nonexistent/should-not-be-created"))

    kill_calls = []
    monkeypatch.setattr(totp_service.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))
    monkeypatch.setattr(totp_service.os, "waitpid", lambda pid, opt: (0, 0))
    close_calls = []
    monkeypatch.setattr(totp_service.os, "close", lambda fd: close_calls.append(fd))
    monkeypatch.setattr(totp_service, "_emit_shell_audit_event", mock.Mock())

    token = "tok-with-shell"
    totp_service._sessions[token] = {"ips": {"1.2.3.4"}, "expires": time.time() - 1, "sid": "s"}
    totp_service._register_shell_session(token, child_pid=4242, master_fd=99)

    assert totp_service._valid_token(token, "1.2.3.4") is False

    assert kill_calls == [(4242, totp_service.signal.SIGTERM)]
    assert close_calls == [99]
    assert token not in totp_service.SHELL_SESSIONS
    totp_service._emit_shell_audit_event.assert_called_once()
    assert totp_service._emit_shell_audit_event.call_args.args[0] == "shell_session_end"


def test_close_shell_session_is_idempotent(monkeypatch):
    """Both the websocket handler's own cleanup and _valid_token()'s expiry
    path call _close_shell_session() with the same token - a session that
    expires while its websocket is still (apparently) open must not be
    killed or audited twice."""
    totp_service = _load_totp_service()
    kill_calls = []
    monkeypatch.setattr(totp_service.os, "kill", lambda pid, sig: kill_calls.append(pid))
    monkeypatch.setattr(totp_service.os, "waitpid", lambda pid, opt: (0, 0))
    monkeypatch.setattr(totp_service.os, "close", lambda fd: None)
    audit_calls = []
    monkeypatch.setattr(totp_service, "_emit_shell_audit_event", lambda *a, **k: audit_calls.append(a))

    token = "tok-double-close"
    totp_service._register_shell_session(token, child_pid=1, master_fd=2)

    totp_service._close_shell_session(token, reason="first")
    totp_service._close_shell_session(token, reason="second")

    assert kill_calls == [1]
    assert len(audit_calls) == 1


def test_close_shell_session_on_unknown_token_is_a_safe_noop(monkeypatch):
    totp_service = _load_totp_service()
    monkeypatch.setattr(totp_service, "_emit_shell_audit_event", mock.Mock())
    totp_service._close_shell_session("never-registered", reason="noop")
    totp_service._emit_shell_audit_event.assert_not_called()


def test_close_shell_session_tolerates_already_dead_process(monkeypatch):
    """The child may already have exited on its own between registration and
    cleanup - os.kill on a dead pid must not raise out of this function."""
    totp_service = _load_totp_service()

    def raise_lookup_error(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(totp_service.os, "kill", raise_lookup_error)
    monkeypatch.setattr(totp_service.os, "waitpid", lambda pid, opt: (_ for _ in ()).throw(ChildProcessError()))
    monkeypatch.setattr(totp_service.os, "close", lambda fd: None)
    monkeypatch.setattr(totp_service, "_emit_shell_audit_event", mock.Mock())

    token = "tok-already-dead"
    totp_service._register_shell_session(token, child_pid=9999, master_fd=3)

    totp_service._close_shell_session(token, reason="disconnected")  # must not raise

    totp_service._emit_shell_audit_event.assert_called_once()


# -- Local-first shell audit logging --------------------------------------------

def test_shell_audit_event_is_written_locally_without_any_network_call(tmp_path, monkeypatch):
    totp_service = _load_totp_service()
    events_dir = tmp_path / "totp-shell"
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_DIR", events_dir)
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_PATH", events_dir / "pending_events.jsonl")

    totp_service._emit_shell_audit_event(
        "shell_session_start", "abcdef0123456789", totp_sid="my-sid", source_ip="192.168.42.10",
    )

    written = (events_dir / "pending_events.jsonl").read_text(encoding="utf-8").strip()
    entry = json.loads(written)
    assert entry["event_type"] == "shell_session_start"
    # Only a short prefix of the token is logged - never the full secret.
    assert entry["session_id"] == "abcdef012345"
    assert entry["session_id"] != "abcdef0123456789"
    assert entry["totp_sid"] == "my-sid"
    assert entry["source_ip"] == "192.168.42.10"
    assert "occurred_at" in entry


def test_shell_audit_event_appends_multiple_lines(tmp_path, monkeypatch):
    totp_service = _load_totp_service()
    events_dir = tmp_path / "totp-shell"
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_DIR", events_dir)
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_PATH", events_dir / "pending_events.jsonl")

    totp_service._emit_shell_audit_event("shell_session_start", "tok1", totp_sid="s", source_ip="1.1.1.1")
    totp_service._emit_shell_audit_event("shell_session_end", "tok1", reason="disconnected")

    lines = (events_dir / "pending_events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "shell_session_start"
    assert json.loads(lines[1])["event_type"] == "shell_session_end"
    assert json.loads(lines[1])["reason"] == "disconnected"


def test_shell_audit_event_failure_is_swallowed_not_raised(monkeypatch):
    """A logging failure (e.g. read-only filesystem, disk full) must never
    take down the shell itself - this is a diagnostic/recovery path."""
    totp_service = _load_totp_service()

    class _UnwritableDir:
        def mkdir(self, *a, **k):
            raise OSError("simulated read-only filesystem")

    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_DIR", _UnwritableDir())

    totp_service._emit_shell_audit_event("shell_session_start", "tok", totp_sid="s", source_ip="1.1.1.1")
    # No exception means the test passed.


def test_shell_audit_event_does_not_import_or_touch_networking(tmp_path, monkeypatch):
    """Guard against a future regression that adds a Headend/network call
    into the local audit path - that would violate the no-new-recovery-
    dependency requirement from ADR-004."""
    totp_service = _load_totp_service()
    events_dir = tmp_path / "totp-shell"
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_DIR", events_dir)
    monkeypatch.setattr(totp_service, "TOTP_SHELL_EVENTS_PATH", events_dir / "pending_events.jsonl")

    def fail_if_called(*a, **k):
        raise AssertionError("shell audit logging must not perform network I/O")

    monkeypatch.setattr(totp_service, "_fetch_headend_config", fail_if_called, raising=False)

    totp_service._emit_shell_audit_event("shell_session_start", "tok", totp_sid="s", source_ip="1.1.1.1")
    assert (events_dir / "pending_events.jsonl").exists()
