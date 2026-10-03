"""Focus lock from the DB/UI camera config (Peter, 2026-10-02).

A relay-powered Nikon Z30 comes back in AF-S after every power-up, so the
body re-ran AF at the shutter and overwrote the good LAB focus (blurry
images). AF must only run on explicit request (lens motor wear). All values
are camera config keys (DB hierarchy, editable in the UI) — nothing is
hard-coded per camera model, and empty means off.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

from camera.drivers import gphoto2_driver as gd  # noqa: E402

Z30 = {
    "focus_lock_commands": "liveviewaffocus=Manual Focus (selection); d0cd=1",
    "autofocus_commands": "viewfinder=1; liveviewaffocus=Single-servo AF; autofocusdrive=1",
    "autofocus_settle_seconds": "3",
    "after_autofocus_commands": "viewfinder=0",
}


def _driver(monkeypatch, startup_cfg=None):
    d = gd.GPhoto2Driver({"gphoto2_port": "usb:003,046", **(startup_cfg or {})})
    calls = []
    monkeypatch.setattr(gd, "_run", lambda args, timeout, check=True: calls.append(args) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(gd.time, "sleep", lambda s: calls.append(["sleep", s]))
    return d, calls


def _sets(args):
    return [args[i + 1] for i, a in enumerate(args) if a == "--set-config"]


def test_focus_lock_sent_in_one_call_without_af(monkeypatch):
    d, calls = _driver(monkeypatch)
    assert d.prepare_focus_for_capture(Z30) is True
    assert len(calls) == 1
    assert _sets(calls[0]) == ["liveviewaffocus=Manual Focus (selection)", "d0cd=1"]


def test_empty_config_is_off(monkeypatch):
    d, calls = _driver(monkeypatch)
    assert d.prepare_focus_for_capture({}) is True and calls == []
    assert d.prepare_focus_for_capture({"focus_lock_commands": ""}) is True and calls == []


def test_ui_change_applies_without_agent_restart(monkeypatch):
    """The driver is built once at agent start; the agent passes its current
    camera config on every call, so a UI change is used at the next capture."""
    d, calls = _driver(monkeypatch, startup_cfg={})
    d.prepare_focus_for_capture(Z30)
    assert calls, "current config from the agent must win over the startup config"


def test_autofocus_runs_configured_commands_then_relocks(monkeypatch):
    d, calls = _driver(monkeypatch)
    assert d.run_autofocus(Z30) is True
    af, sleep, lock = calls
    assert _sets(af) == ["viewfinder=1", "liveviewaffocus=Single-servo AF", "autofocusdrive=1"]
    assert sleep == ["sleep", 3.0]
    assert _sets(lock) == ["liveviewaffocus=Manual Focus (selection)", "d0cd=1", "viewfinder=0"]


def test_list_values_accepted(monkeypatch):
    d, calls = _driver(monkeypatch)
    d.prepare_focus_for_capture({"focus_lock_commands": ["/main/other/d0cd=1"]})
    assert _sets(calls[0]) == ["/main/other/d0cd=1"]


def test_no_model_specific_hardcoding():
    src = (ROOT / "edge/camera/drivers/gphoto2_driver.py").read_text(encoding="utf-8")
    assert '"focus_lock":' not in src


def test_agent_sends_current_camera_config_before_precise_wait():
    src = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    cycle = src.split("# 2. Apply configuration commands", 1)[1]
    lock = cycle.index('self._driver.prepare_focus_for_capture(self._cfg.get("camera", {}))')
    assert lock < cycle.index("# 3. Health check before capture") < cycle.index("capture_image(dest_dir)")
    thread = src.split("def _capture_single_camera", 1)[1].split("driver.capture_image(dest_dir)", 1)[0]
    assert 'driver.prepare_focus_for_capture(cam_cfg["camera"])' in thread
    assert src.count('run_autofocus(self._cfg.get("camera", {}))') == 2


def test_ui_exposes_all_focus_keys():
    camera_page = (ROOT / "timelapse-ui/src/pages/CameraPage.tsx").read_text(encoding="utf-8")
    global_page = (ROOT / "timelapse-ui/src/pages/GlobalConfigPage.tsx").read_text(encoding="utf-8")
    for key in Z30:
        assert f"key: 'camera.{key}'" in camera_page
        assert f"key: '{key}'" in global_page


def test_z30_shutter_speed_from_ui_uses_fraction_setting():
    d = gd.GPhoto2Driver({"gphoto2_port": "usb:"})
    d._profile_key, d._profile = d._profile_for_model("Nikon Z30")
    assert d.build_config_command("shutter_speed", "1/500") == "/main/capturesettings/shutterspeed2=1/500"
    assert d.build_config_command("shutter_speed", "Auto") is None
