"""Technician CLI: pick camera values from the camera's own options instead
of guessing what to type (Peter, 2026-10-04). Z30: focusmode is read-only ->
use the writable liveviewaffocus; imageformat is missing -> imagequality."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bootstrap_cli_choose_test", ROOT / "edge" / "tools" / "bootstrap_cli.py")
cli = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_cli_choose_test"] = cli
_spec.loader.exec_module(cli)

Z30 = {
    "/main/capturesettings/focusmode": "Label: Focus Mode\nReadonly: 1\nType: RADIO\nCurrent: AF-A\nChoice: 0 Manual\nChoice: 1 AF-S\n",
    "/main/capturesettings/liveviewaffocus": "Label: Live View AF Focus\nReadonly: 0\nType: RADIO\nCurrent: Single-servo AF\nChoice: 0 Single-servo AF\nChoice: 1 Continuous-servo AF\nChoice: 2 Manual Focus (selection)\n",
    "/main/capturesettings/imagequality": "Label: Image Quality\nReadonly: 0\nType: RADIO\nCurrent: JPEG Fine\nChoice: 0 JPEG Basic\nChoice: 1 JPEG Fine\nChoice: 2 NEF (Raw)\n",
    "/main/imgsettings/iso": "Label: ISO Speed\nReadonly: 0\nType: RADIO\nCurrent: 100\nChoice: 0 100\nChoice: 1 200\n",
    "/main/actions/manualfocusdrive": "Label: Manual Focus Drive\nReadonly: 0\nType: RANGE\nCurrent: 0\nBottom: -32767\nTop: 32767\nStep: 1\n",
    "/main/actions/viewfinder": "Label: Viewfinder\nReadonly: 0\nType: TOGGLE\nCurrent: 0\n",
}


def _camera(monkeypatch, inputs):
    sets = []

    def fake_run(cmd, check=True, timeout=15):
        if cmd[:2] == ["gphoto2", "--get-config"]:
            out = Z30.get(cmd[2])
            return SimpleNamespace(returncode=0 if out else 1, stdout=out or "", stderr="" if out else "not found")
        if cmd[:2] == ["gphoto2", "--set-config"]:
            sets.append(cmd[2])
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli, "run", fake_run)
    it = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda _p="": next(it))
    return sets


def test_readonly_focusmode_uses_writable_liveviewaffocus_and_choice_list(monkeypatch, capsys):
    sets = _camera(monkeypatch, ["6", "3"])
    assert cli.choose_photo_setting() is True
    out = capsys.readouterr().out
    assert "Fokusmode (focus_mode) = Single-servo AF  (via liveviewaffocus)" in out
    assert "3. Manual Focus (selection)" in out and "Single-servo AF  ← nu" in out
    assert sets == ["/main/capturesettings/liveviewaffocus=Manual Focus (selection)"]


def test_image_format_found_via_imagequality(monkeypatch, capsys):
    sets = _camera(monkeypatch, ["7", "3"])
    cli.choose_photo_setting()
    assert "Billedformat (image_format) = JPEG Fine  (via imagequality)" in capsys.readouterr().out
    assert sets == ["/main/capturesettings/imagequality=NEF (Raw)"]


def test_missing_setting_is_reported_not_typed(monkeypatch, capsys):
    sets = _camera(monkeypatch, ["5"])          # aperture: not in the fake camera
    assert cli.choose_photo_setting() is False
    assert "findes ikke på dette kamera" in capsys.readouterr().out and sets == []


def test_readonly_without_alternative_is_explained():
    info = {"path": "/main/x", "readonly": True, "choices": []}
    assert cli.choose_config_value(info) is None


def test_range_and_toggle(monkeypatch):
    _camera(monkeypatch, ["500", "99999", "1"])
    rng = cli.gphoto_config_info("/main/actions/manualfocusdrive")
    assert cli.choose_config_value(rng) == "500"
    assert cli.choose_config_value(rng) is None            # outside range
    tog = cli.gphoto_config_info("/main/actions/viewfinder")
    assert cli.choose_config_value(tog) == "1"


def test_raw_path_menu_offers_choices(monkeypatch):
    sets = _camera(monkeypatch, ["11", "/main/imgsettings/iso", "2", "12"])
    cli.camera_menu(Path("/tmp"))
    assert sets == ["/main/imgsettings/iso=200"]
