"""Wake long-poll (Peter 2026-10-10: LAB mode should not take minutes).

While the SSH tunnel is up the Edge holds POST /api/edge/wait; Headend
answers as soon as the device's wake token changes (config edit — LAB mode
is device config — or an approved update), and the Edge syncs at once."""
import asyncio
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

import edge_sync  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_first_call_only_hands_out_token(monkeypatch):
    monkeypatch.setattr(edge_sync, "_fresh_token", lambda device_id: "t1")
    assert _run(edge_sync.edge_wait("TL-X", edge_sync.EdgeWaitRequest(since="", timeout_s=50))) == {"wake": False, "token": "t1"}


def test_returns_wake_as_soon_as_token_changes(monkeypatch):
    tokens = iter(["t1", "t1", "t2"])
    monkeypatch.setattr(edge_sync, "_fresh_token", lambda device_id: next(tokens))
    monkeypatch.setattr(edge_sync, "WAIT_STEP_S", 0.01)
    assert _run(edge_sync.edge_wait("TL-X", edge_sync.EdgeWaitRequest(since="t1", timeout_s=50))) == {"wake": True, "token": "t2"}


def test_times_out_without_wake_and_clamps_timeout(monkeypatch):
    monkeypatch.setattr(edge_sync, "_fresh_token", lambda device_id: "t1")
    monkeypatch.setattr(edge_sync, "WAIT_STEP_S", 0.01)
    monkeypatch.setattr(edge_sync, "WAIT_MIN_S", 0)
    assert _run(edge_sync.edge_wait("TL-X", edge_sync.EdgeWaitRequest(since="t1", timeout_s=-5))) == {"wake": False, "token": "t1"}


def test_wake_token_tracks_config_version_and_approved_updates():
    class _Q:
        def __init__(self, rows):
            self.rows = rows

        def filter_by(self, **_kw):
            return self

        def filter(self, *_a):
            return self

        def first(self):
            return self.rows[0] if self.rows else None

        def all(self):
            return self.rows

    def db(config_version, approved):
        return SimpleNamespace(query=lambda model: _Q(
            [SimpleNamespace(config_version=config_version)] if model is edge_sync.Device
            else [SimpleNamespace(id=i) for i in approved]))

    base = edge_sync.wake_token(db("v1", [3]), "TL-X")
    assert edge_sync.wake_token(db("v1", [3]), "TL-X") == base
    assert edge_sync.wake_token(db("v2", [3]), "TL-X") != base       # LAB toggle / config edit
    assert edge_sync.wake_token(db("v1", [3, 9]), "TL-X") != base    # update approved


def test_endpoint_uses_same_device_auth_as_sync():
    src = (ROOT / "headend/edge_sync.py").read_text(encoding="utf-8")
    wait = src.split('@router.post("/wait/{device_id}")', 1)[1]
    assert "Depends(_require_edge_sync_auth)" in wait


# ── Edge side ────────────────────────────────────────────────────────────────

def _agent_with(api_results, tunnel_up=True):
    sys.path.insert(0, str(ROOT / "edge"))
    import agent as agent_mod

    a = agent_mod.EdgeAgent.__new__(agent_mod.EdgeAgent)
    a._running = True
    a._stop_event = threading.Event()
    a._wake_event = threading.Event()
    a._wake_token = ""
    a._last_heartbeat = datetime.now(timezone.utc)
    a._cfg = {"diagnostics": {}}
    a._tunnel = SimpleNamespace(is_connected=lambda: tunnel_up)
    calls = []
    results = iter(api_results)

    def wait_for_wake(since, timeout_s):
        calls.append((since, timeout_s))
        try:
            return next(results)
        except StopIteration:
            a._running = False
            return False, None
    a._api = SimpleNamespace(wait_for_wake=wait_for_wake)
    a._stop_event.wait = lambda _t=None: None      # no real sleeping in tests
    return a, calls


def test_edge_wakes_main_loop_and_forces_sync():
    a, calls = _agent_with([(True, {"wake": False, "token": "t1"}), (True, {"wake": True, "token": "t2"})])
    a._wake_channel_loop()
    assert calls[0] == ("", 50) and calls[1] == ("t1", 50)
    assert a._wake_event.is_set()
    assert a._last_heartbeat == datetime.min.replace(tzinfo=timezone.utc)


def test_edge_idles_without_tunnel():
    a, calls = _agent_with([], tunnel_up=False)
    a._stop_event.wait = lambda _t=None: setattr(a, "_running", False)
    a._wake_channel_loop()
    assert calls == []


def test_main_loop_sleep_is_interruptible_by_wake():
    src = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    assert "if self._wake_event.wait(min(sleep_s, max_idle_sleep)):" in src
    assert "self._start_wake_channel()" in src
