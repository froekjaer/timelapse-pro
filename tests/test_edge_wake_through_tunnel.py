"""Headend wakes an Edge through its SSH tunnel (Peter 2026-10-10).

A shared key that can only ask the Edge to poll: accepted only from the
tunnel (127.0.0.1/::1), `restrict`, forced command. Verified manually against
a real OpenSSH sshd with the same authorized_keys line: the wake runs; any
other command, pty/shell, port forwarding and sftp are refused; a wrong host
key is refused before authentication (HANDOVER_LOG 2026-10-10)."""
import importlib.util
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from services import edge_wake as ew  # noqa: E402


def _baseline():
    spec = importlib.util.spec_from_file_location("baseline_wake", ROOT / "edge/scripts/timelapse_system_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_edge_accepts_the_key_only_through_the_tunnel_with_forced_command(tmp_path):
    b = _baseline()
    pub = tmp_path / "wake.pub"
    pub.write_text("ssh-ed25519 AAAATEST comment ignored\n")
    assert b.wake_account(tmp_path, apply=False, pubkey_path=pub)["status"] == "changed"
    line = (tmp_path / b.WAKE_HOME / ".ssh/authorized_keys").read_text()
    assert line == ('from="127.0.0.1,::1",restrict,command="/opt/timelapse/edge/scripts/timelapse_wake_request.sh" '
                    'ssh-ed25519 AAAATEST timelapse-edge-wake\n')
    assert oct((tmp_path / b.WAKE_HOME / ".ssh/authorized_keys").stat().st_mode & 0o777) == "0o600"
    assert b.wake_account(tmp_path, apply=False, pubkey_path=pub)["status"] == "ok"
    assert ("wake", b.wake_account) in b.STEPS


def test_shipped_public_key_and_forced_command():
    pub = (ROOT / "edge/config/timelapse-wake.pub").read_text().split()
    assert pub[0] == "ssh-ed25519" and len(pub[1]) > 60
    script = (ROOT / "edge/scripts/timelapse_wake_request.sh").read_text()
    commands = [l for l in script.splitlines() if l.strip() and not l.startswith("#")]
    assert commands == ["exec /usr/bin/touch -c /run/timelapse/wake-request"]


class _Key:
    def __init__(self, raw):
        self.raw = raw

    def asbytes(self):
        return self.raw


class _Transport:
    def __init__(self, raw_key, exit_status=0):
        self.raw_key, self.exit_status, self.authed, self.closed = raw_key, exit_status, None, False

    def __call__(self, _addr):
        return self

    def start_client(self, timeout=None):
        pass

    def get_remote_server_key(self):
        return _Key(self.raw_key)

    def auth_publickey(self, user, _key):
        self.authed = user

    def open_session(self, timeout=None):
        t = self
        return SimpleNamespace(settimeout=lambda _t: None, exec_command=lambda _c: None,
                               recv_exit_status=lambda: t.exit_status)

    def close(self):
        self.closed = True


def test_sender_refuses_unknown_host_key_before_authenticating(tmp_path, monkeypatch):
    import paramiko
    key = tmp_path / "k"
    key.write_text("placeholder")
    monkeypatch.setattr(paramiko.Ed25519Key, "from_private_key_file", classmethod(lambda cls, p: object()))
    t = _Transport(b"edge-host-key")
    ok, detail = ew.send_wake(2201, "SHA256:not-this-one", key_path=key, transport_factory=t)
    assert not ok and "mismatch" in detail and t.authed is None and t.closed
    good = ew.fingerprint_sha256(_Key(b"edge-host-key"))
    t2 = _Transport(b"edge-host-key")
    assert ew.send_wake(2201, good, key_path=key, transport_factory=t2) == (True, "exit 0")
    assert t2.authed == "tlwake" and t2.closed
    assert ew.send_wake(2201, good, key_path=tmp_path / "missing")[0] is False


def test_watcher_wakes_only_the_changed_connected_device(monkeypatch):
    tokens = {"TL-A": "a1", "TL-B": "b1"}
    monkeypatch.setattr(ew, "_tunnel_targets", lambda db: {"TL-A": (2201, "fpA"), "TL-B": (2204, "fpB")})
    monkeypatch.setattr(ew, "wake_token", lambda db, d: tokens[d])
    sent = []
    done = threading.Event()

    def sender(port, fp):
        sent.append((port, fp))
        done.set()
        return True, "exit 0"

    w = ew.EdgeWakeWatcher(lambda: SimpleNamespace(close=lambda: None), sender=sender)
    assert w.check_once() == []                     # first sight: remember, don't wake
    tokens["TL-B"] = "b2"                           # e.g. LAB mode switched on for TL-B
    assert w.check_once() == ["TL-B"]
    done.wait(2)
    assert sent == [(2204, "fpB")]
    assert w.check_once() == []


def test_watcher_registered_without_touching_main():
    src = (ROOT / "headend/edge_sync.py").read_text(encoding="utf-8")
    assert '@router.on_event("startup")' in src and "start_edge_wake_watcher()" in src


def test_agent_syncs_at_once_on_wake_and_rate_limits(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "edge"))
    import agent as agent_mod

    a = agent_mod.EdgeAgent.__new__(agent_mod.EdgeAgent)
    a._running = True
    a._stop_event = threading.Event()
    a._wake_event = threading.Event()
    a._last_heartbeat = datetime.now(timezone.utc)
    req = tmp_path / "wake-request"
    req.write_text("")
    monkeypatch.setattr(agent_mod.EdgeAgent, "WAKE_REQUEST_PATH", req)
    monkeypatch.setattr(agent_mod.EdgeAgent, "WAKE_MIN_INTERVAL_S", 0)
    ticks = iter(range(10))

    def fake_wait(_t=None):
        n = next(ticks)
        if n == 1:
            os.utime(req, (time.time() + 5, time.time() + 5))   # Headend's touch -c
        if n >= 3:
            a._running = False
    a._stop_event.wait = fake_wait
    a._wake_watch_loop()
    assert a._wake_event.is_set()
    assert a._last_heartbeat == datetime.min.replace(tzinfo=timezone.utc)
    src = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    assert "if self._wake_event.wait(min(sleep_s, max_idle_sleep)):" in src
