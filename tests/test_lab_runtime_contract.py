"""Focused regression tests for the LAB camera-control contracts.

These tests are hardware-free. They protect the contracts that previously made
the LAB UI appear to work while commands were never executed by the Edge.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

from camera.drivers import gphoto2_driver
from frame_push import LiveVideoStreamer


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _nikon_driver():
    driver = gphoto2_driver.GPhoto2Driver({"gphoto2_port": "usb:001,007"})
    driver._profile = gphoto2_driver.CAMERA_PROFILES["Nikon Z30"]
    driver._profile_key = "Nikon Z30"
    driver._model = "Nikon Z30"
    return driver


def test_nikon_profile_summary_exposes_ui_features():
    summary = _nikon_driver().get_profile_summary()

    assert summary["features"]["autofocus"] is True
    assert summary["features"]["remote_focus"] is True
    assert summary["features"]["liveview"] is True
    assert summary["features"] == summary["camera_capabilities"]


def test_config_read_uses_the_selected_camera_port(monkeypatch):
    seen = []

    def fake_run(command, **_kwargs):
        seen.append(command)
        return _Result(stdout="")

    monkeypatch.setattr(gphoto2_driver, "_run", fake_run)
    assert _nikon_driver().get_all_config() == []
    assert seen == [["gphoto2", "--port", "usb:001,007", "--list-all-config"]]


def test_manual_focus_stops_when_nikon_manual_context_cannot_be_set(monkeypatch):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return _Result(returncode=1, stderr="context unsupported")

    monkeypatch.setattr(gphoto2_driver, "_run", fake_run)
    assert _nikon_driver().drive_manual_focus("500") is False
    assert len(calls) == 1
    assert "liveviewaffocus=Manual Focus (selection)" in calls[0][-1]


def test_live_streamer_marks_itself_stopped_when_camera_stream_ends(monkeypatch):
    class _Stdout:
        def read(self, _size):
            return b""

    class _Process:
        pid = 42
        stdout = _Stdout()

        def terminate(self):
            return None

    # frame_push owns its own subprocess module; replace it directly.
    import frame_push
    monkeypatch.setattr(frame_push.subprocess, "Popen", lambda *_args, **_kwargs: _Process())

    streamer = LiveVideoStreamer("TL-TEST", api_client=object())
    streamer._running = True
    streamer._stream_loop()

    assert streamer.is_running() is False


def test_headend_lab_commands_are_serialised_and_live_stream_is_device_authenticated():
    source = (Path(__file__).resolve().parents[1] / "headend" / "main.py").read_text(encoding="utf-8")

    assert 'status_code=409' in source
    assert '"type": "live_stream"' in source
    assert 'async def receive_live_frame(' in source
    live_frame_block = source.split('async def receive_live_frame(', 1)[1].split('@app.get("/api/lab/{device_id}/live-frame")', 1)[0]
    assert 'Depends(_verify_device_token)' in live_frame_block


def test_edge_update_reports_are_bound_to_the_authenticated_device():
    source = (Path(__file__).resolve().parents[1] / "headend" / "main.py").read_text(encoding="utf-8")

    assert 'async def _verify_payload_device_token(' in source
    assert 'await _verify_device_token(' in source
    report_block = source.split('def report_update(', 1)[1].split('@app.post("/api/updates/available")', 1)[0]
    available_block = source.split('def report_available_updates(', 1)[1].split('# ── PROVISION PACKAGE', 1)[0]
    assert 'Depends(_verify_payload_device_token)' in report_block
    assert 'Depends(_verify_payload_device_token)' in available_block
    assert 'device_id != authenticated_device_id' in report_block
    assert 'device_id != authenticated_device_id' in available_block
