"""LAB mode starts at once (Peter 2026-10-10: "LAB står stadig og venter LÆNGE").

Live log: the tunnel wake arrived in 2 s and the sync saw "Lab mode
aktiveret", but the normal tick then slept "64s until next capture" before
LAB began; and when LAB was switched off again, the loop (which had chosen
LAB from the previous config) still powered the camera up."""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))


def _agent():
    import agent as agent_mod

    a = agent_mod.EdgeAgent.__new__(agent_mod.EdgeAgent)
    a._wake_event = threading.Event()
    return a


def test_lab_activation_interrupts_the_idle_sleep():
    src = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    block = src.split('log.info("Lab mode aktiveret via config-ændring")', 1)[1].split("else:", 1)[0]
    assert "self._wake_event.set()" in block
    assert "if self._wake_event.wait(min(sleep_s, max_idle_sleep)):" in src


def test_lab_tick_does_not_power_camera_for_a_session_already_switched_off():
    a = _agent()
    a._check_and_apply_updates_if_due = lambda: None
    a._api = SimpleNamespace(fetch_config=lambda: (True, {"config_version": "same"}))
    a._cfg = {"config_version": "same", "debug_mode": {"enabled": False}}
    touched = []
    a._service_platform = SimpleNamespace(
        shared_or_lab_session=lambda *_a: touched.append("session"),
        call=lambda *a_, **k: touched.append(a_[0]),
    )
    a._lab_tick({"enabled": True})                 # chosen from the previous config
    assert touched == []                           # no lab session, no camera.power.acquire


def test_lab_camera_start_waits_for_warm_up_only_once(monkeypatch):
    """Live 2026-10-10: relay ON 10:56:09 → camera connected 10:56:39 — the
    10 s warm-up ran three times (relay itself, camera.power.acquire, LAB loop).
    Only the relay's own wait remains."""
    import agent as agent_mod
    from unittest.mock import MagicMock

    a = agent_mod.EdgeAgent.__new__(agent_mod.EdgeAgent)
    a._wake_event = threading.Event()
    a._device_id = "TL-T"
    cfg = {"config_version": "v1", "debug_mode": {"enabled": True}, "pending_params": [], "lab_command": {},
           "camera": {"relay_on_seconds_before": 10}}
    a._cfg = dict(cfg)
    a._api = MagicMock()
    a._api.fetch_config.return_value = (True, cfg)
    a._api._post.return_value = (True, {})
    a._cfg_mgr = MagicMock()
    a._cfg_mgr.load.return_value = cfg
    a._uploader = MagicMock()
    a._driver = MagicMock()
    a._live_frame_enabled = False
    a._lab_relay_on = False
    a._check_and_apply_updates_if_due = MagicMock()
    a._camera_power_mode = MagicMock(return_value="relay")
    a._camera_power_on = MagicMock()          # the real relay.power_on waits its own warm-up
    a._camera_power_off = MagicMock()
    a._build_camera_commands = MagicMock(return_value=[])
    a._apply_config_changes = MagicMock()
    a._check_config_version = MagicMock()
    a._lab_stop_frame_push = MagicMock()
    a._lab_start_frame_push = MagicMock()
    sleeps = []
    monkeypatch.setattr(agent_mod.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(agent_mod, "_FRAME_PUSH_AVAILABLE", False)
    a._lab_tick({"config_poll_s": 0})
    assert a._lab_relay_on is True
    assert 10 not in sleeps, sleeps            # no extra warm-up on top of the relay's
    src = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    acquire = src.split("def power_acquire(", 1)[1].split("def power_release(", 1)[0]
    assert "time.sleep" not in acquire
