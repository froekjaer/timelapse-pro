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
