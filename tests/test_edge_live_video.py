"""Hardware-free contracts for capability-based Edge Live View."""

from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

from camera import live_video
from camera.service_stream import TechnicianStreamManager


def test_nikon_uses_true_movie_stream_while_canons_keep_preview_compatibility():
    assert live_video.stream_mode_for_model("Nikon Z30") == "movie"
    assert live_video.stream_mode_for_model("Canon EOS 1300D") == "preview"
    assert live_video.stream_mode_for_model("Canon EOS 2000D") == "preview"


def test_unknown_camera_does_not_inherit_nikon_movie_capability():
    assert live_video.stream_mode_for_model("Unknown PTP Camera") == "preview"


def test_auto_detect_prefers_configured_port_without_mixing_camera_profiles():
    output = """Model                          Port
----------------------------------------------------------
Canon EOS 1300D                usb:001,004
Nikon Z30                      usb:002,081
"""
    assert live_video.parse_auto_detect(output, "usb:002,081") == ("Nikon Z30", "usb:002,081")


def test_movie_source_uses_bounded_capture_movie_and_not_still_frames(monkeypatch):
    jpeg = b"\xff\xd8" + (b"x" * 2048) + b"\xff\xd9"
    commands = []

    class _Stream:
        def __init__(self, chunks):
            self.chunks = list(chunks)

        def read(self, _size):
            return self.chunks.pop(0) if self.chunks else b""

    class _Process:
        def __init__(self):
            self.stdout = _Stream([jpeg])
            self.stderr = _Stream([])

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            return None

        def kill(self):
            return None

    def fake_popen(command, **_kwargs):
        commands.append(command)
        return _Process()

    monkeypatch.setattr(live_video.subprocess, "Popen", fake_popen)
    source = live_video.GPhoto2FrameSource(movie_segment_s=180)
    info = live_video.CameraStreamInfo("Nikon Z30", "usb:002,081", "movie", True, True)
    first_frame = next(source._movie_frames(info))
    source.stop()

    assert first_frame == jpeg
    assert commands == [[
        "gphoto2",
        "--port",
        "usb:002,081",
        "--capture-movie=180s",
        "--stdout",
    ]]


def test_canon_preview_source_never_uses_nikon_movie_command(monkeypatch):
    jpeg = b"\xff\xd8" + (b"c" * 2048) + b"\xff\xd9"
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        target = Path(command[command.index("--filename") + 1])
        target.write_bytes(jpeg)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(live_video.subprocess, "run", fake_run)
    source = live_video.GPhoto2FrameSource(preview_interval_s=0.1)
    info = live_video.CameraStreamInfo("Canon EOS 2000D", "usb:001,004", "preview", True, False)
    first_frame = next(source._preview_frames(info))
    source.stop()

    assert first_frame == jpeg
    assert "--capture-preview" in commands[0]
    assert not any(any("capture-movie" in part for part in command) for command in commands)


def test_technician_stream_always_restores_relay_and_edge_service(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text('camera:\n  gphoto2_port: "usb:"\n', encoding="utf-8")
    events = []

    class _CameraRelay:
        def power_on(self):
            events.append("relay_on")

        def force_off(self):
            events.append("relay_off")

    class _Relay:
        camera = _CameraRelay()

        def cleanup(self, camera=True, modem=False):
            events.append("relay_cleanup")

    class _Source:
        def __init__(self, *_args, **_kwargs):
            pass

        def detect(self):
            events.append("detect")
            return SimpleNamespace(model="Nikon Z30", port="usb:002,081", mode="movie")

        def frames(self):
            raise RuntimeError("probe failure")
            yield b""

        def stop(self):
            events.append("source_stop")

    manager = TechnicianStreamManager(
        tmp_path,
        source_factory=_Source,
        relay_factory=lambda _config: _Relay(),
    )
    monkeypatch.setattr(manager, "_service_is_active", lambda: True)
    monkeypatch.setattr(manager, "_service_action", lambda action, _timeout: events.append(action))

    manager.start()
    manager._thread.join(timeout=3)

    assert manager.status()["status"] == "error"
    assert events == [
        "stop",
        "relay_on",
        "detect",
        "source_stop",
        "relay_off",
        "relay_cleanup",
        "start",
    ]
    assert manager.status()["frame_ready"] is False
