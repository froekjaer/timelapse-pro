"""Edge technician UI offers the camera's OWN values (Peter, 2026-10-04).

"Hent kameraets valg" runs the camera.config.read service operation with
choices=true (WP-3: the UI never talks to gphoto2 itself). The operation
returns every parameter (same parser as the LAB scan) plus the writable path
per photo setting — Nikon Z30: focusmode read-only → liveviewaffocus.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))
import service_operations as so  # noqa: E402

UI = (ROOT / "edge" / "scripts" / "totp-service.py").read_text(encoding="utf-8")

LIST_ALL = """/main/capturesettings/focusmode
Label: Focus Mode
Readonly: 1
Type: RADIO
Current: Manual
Choice: 0 Manual
Choice: 1 AF-S
END
/main/capturesettings/liveviewaffocus
Label: Live View AF Focus
Readonly: 0
Type: RADIO
Current: Manual Focus (selection)
Choice: 0 Single-servo AF
Choice: 1 Manual Focus (selection)
END
/main/imgsettings/whitebalance
Label: WhiteBalance
Readonly: 0
Type: RADIO
Current: Automatic
Choice: 0 Automatic
Choice: 1 Tungsten
END
/main/capturesettings/f-number
Label: F-Number
Readonly: 1
Type: RADIO
Current: f/8
Choice: 0 f/8
END
/main/actions/manualfocusdrive
Label: Manual Focus Drive
Readonly: 0
Type: RANGE
Current: 0
Bottom: -32767
Top: 32767
Step: 1
END
"""


def _ops(monkeypatch):
    ops = so.ServiceOperations(base_dir=Path("/tmp"))
    monkeypatch.setattr(ops, "_gphoto", lambda args, timeout=15: {
        "ok": args == ["--list-all-config"], "stdout": LIST_ALL, "stderr": "", "returncode": 0})
    return ops


def test_choices_op_returns_params_and_writable_setting_paths(monkeypatch):
    result = _ops(monkeypatch).camera_config_read(None, None, {"choices": True})
    assert result["ok"] and len(result["params"]) == 5
    settings = result["settings"]
    assert settings["focus_mode"]["path"] == "/main/capturesettings/liveviewaffocus"
    assert [c["label"] for c in settings["white_balance"]["choices"]] == ["Automatic", "Tungsten"]
    # Read-only without alternative is still returned, marked read-only.
    assert settings["aperture"]["readonly"] is True
    assert settings["iso"] is None                      # not on this fake camera


def test_plain_read_unchanged(monkeypatch):
    ops = _ops(monkeypatch)
    monkeypatch.setattr(ops, "_read_gphoto_current", lambda path: "x")
    assert ops.camera_config_read(None, None, {"path": "/main/a"}) == {"ok": True, "path": "/main/a", "value": "x"}


def test_ui_fetches_through_service_operation_and_uses_resolved_path():
    assert '"--service-operation", "camera.config.read", "--service-param", "choices=true"' in UI
    assert "path = _photo_setting_path(key)" in UI
    assert "Hent kameraets valg" in UI
    assert "← nu" in UI and "select.disabled = readonly" in UI


def _load_ui(monkeypatch):
    spec = importlib.util.spec_from_file_location("totp_service_choices_test", ROOT / "edge" / "scripts" / "totp-service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ui_helpers_prefer_camera_values(monkeypatch):
    try:
        ui = _load_ui(monkeypatch)
    except Exception as exc:  # pragma: no cover - service deps missing on this host
        import pytest
        pytest.skip(f"totp-service not importable here: {exc}")
    assert ui._photo_value_options()["white_balance"] == ui.PHOTO_VALUE_OPTIONS["white_balance"]
    result = so.ServiceOperations(base_dir=Path("/tmp"))
    result._gphoto = lambda args, timeout=15: {"ok": True, "stdout": LIST_ALL, "stderr": "", "returncode": 0}
    ui._CAMERA_CHOICES.update({"result": result._camera_choices(), "fetched_at": "now"})
    assert ui._photo_value_options()["white_balance"] == ["Automatic", "Tungsten"]
    assert ui._photo_setting_path("focus_mode") == "/main/capturesettings/liveviewaffocus"
    assert ui._focus_drive_options() == ["-1000", "-500", "-200", "-100", "-50", "50", "100", "200", "500", "1000"]
    assert ui._parse_service_json('noise\n{"ok": true, "params": []}\nwarn') == {"ok": True, "params": []}
