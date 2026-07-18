"""Capability-based gPhoto2 live-view frame source.

Nikon bodies with movie support use the camera's real MJPEG movie stream.
Canon bodies without remote movie support retain a lower-rate preview stream.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from camera.drivers.gphoto2_driver import CAMERA_PROFILES


log = logging.getLogger(__name__)

GPHOTO2_CMD = "gphoto2"
MAX_FRAME_SIZE = 2 * 1024 * 1024


class LiveVideoError(RuntimeError):
    """Raised when the camera cannot provide a usable live-view stream."""


class MJPEGParser:
    """Extract complete JPEG images from a byte stream."""

    def __init__(self, max_frame_size: int = MAX_FRAME_SIZE):
        self.buffer = bytearray()
        self.frame_count = 0
        self.max_frame_size = max_frame_size

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        frames: list[bytes] = []
        while self.buffer:
            start = self.buffer.find(b"\xff\xd8")
            if start < 0:
                self.buffer = self.buffer[-100:]
                break
            if start:
                del self.buffer[:start]
            end = self.buffer.find(b"\xff\xd9", 2)
            if end < 0:
                if len(self.buffer) > self.max_frame_size:
                    self.buffer.clear()
                break
            frame = bytes(self.buffer[: end + 2])
            del self.buffer[: end + 2]
            if 1024 <= len(frame) <= self.max_frame_size:
                frames.append(frame)
                self.frame_count += 1
        return frames


@dataclass(frozen=True)
class CameraStreamInfo:
    model: str
    port: str
    mode: str
    liveview: bool
    movie: bool

    def to_dict(self) -> dict:
        return asdict(self)


def profile_for_model(model: str) -> dict:
    """Return the most specific profile without coupling camera families."""
    if model in CAMERA_PROFILES:
        return CAMERA_PROFILES[model]
    if model.startswith("Canon EOS"):
        return CAMERA_PROFILES["Canon EOS"]
    return CAMERA_PROFILES["default"]


def stream_mode_for_model(model: str) -> str:
    capabilities = profile_for_model(model).get("camera_capabilities", {})
    if capabilities.get("movie"):
        return "movie"
    if capabilities.get("liveview"):
        return "preview"
    return "unavailable"


def parse_auto_detect(output: str, port_hint: str = "usb:") -> tuple[str, str]:
    candidates: list[tuple[str, str]] = []
    for line in output.splitlines():
        if "usb:" not in line and "ptpip:" not in line:
            continue
        port = line.split()[-1]
        model = line[: line.rfind(port)].strip()
        if model:
            candidates.append((model, port))
    if not candidates:
        raise LiveVideoError("gphoto2 fandt intet kamera")
    if port_hint and port_hint not in {"usb:", "auto"}:
        for candidate in candidates:
            if candidate[1] == port_hint:
                return candidate
    return candidates[0]


class GPhoto2FrameSource:
    """Yield camera frames using the selected model capability."""

    def __init__(
        self,
        port_hint: str = "usb:",
        preview_interval_s: float = 0.8,
        movie_segment_s: int = 300,
    ):
        self.port_hint = port_hint
        self.preview_interval_s = max(0.1, float(preview_interval_s))
        self.movie_segment_s = max(5, int(movie_segment_s))
        self.info: CameraStreamInfo | None = None
        self.last_error = ""
        self._stop = threading.Event()
        self._process: subprocess.Popen | None = None
        self._stderr_tail = bytearray()
        self._stderr_thread: threading.Thread | None = None

    def detect(self) -> CameraStreamInfo:
        result = subprocess.run(
            [GPHOTO2_CMD, "--auto-detect"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            raise LiveVideoError((result.stderr or result.stdout or "Kameradetektion fejlede").strip())
        model, port = parse_auto_detect(result.stdout, self.port_hint)
        profile = profile_for_model(model)
        capabilities = profile.get("camera_capabilities", {})
        self.info = CameraStreamInfo(
            model=model,
            port=port,
            mode=stream_mode_for_model(model),
            liveview=bool(capabilities.get("liveview")),
            movie=bool(capabilities.get("movie")),
        )
        if self.info.mode == "unavailable":
            raise LiveVideoError(f"{model} har ikke en understøttet Live View-funktion")
        return self.info

    def frames(self) -> Iterator[bytes]:
        info = self.info or self.detect()
        if info.mode == "movie":
            yield from self._movie_frames(info)
        else:
            yield from self._preview_frames(info)

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    def _drain_stderr(self, stream) -> None:
        while not self._stop.is_set():
            chunk = stream.read(1024)
            if not chunk:
                return
            self._stderr_tail.extend(chunk)
            if len(self._stderr_tail) > 8192:
                del self._stderr_tail[:-8192]

    def _movie_frames(self, info: CameraStreamInfo) -> Iterator[bytes]:
        parser = MJPEGParser()
        while not self._stop.is_set():
            command = [
                GPHOTO2_CMD,
                "--port",
                info.port,
                f"--capture-movie={self.movie_segment_s}s",
                "--stdout",
            ]
            self._stderr_tail.clear()
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            assert self._process.stdout is not None
            assert self._process.stderr is not None
            self._stderr_thread = threading.Thread(
                target=self._drain_stderr,
                args=(self._process.stderr,),
                daemon=True,
                name="gphoto2-live-stderr",
            )
            self._stderr_thread.start()
            frames_in_segment = 0
            while not self._stop.is_set():
                chunk = self._process.stdout.read(64 * 1024)
                if not chunk:
                    break
                for frame in parser.feed(chunk):
                    frames_in_segment += 1
                    yield frame
            return_code = self._process.wait(timeout=3)
            if self._stop.is_set():
                return
            if return_code != 0 or frames_in_segment == 0:
                error = self._stderr_tail.decode(errors="replace").strip()
                self.last_error = error or "Kameraets movie stream gav ingen billeder"
                raise LiveVideoError(self.last_error)
            log.info("LIVE VIDEO: restarting bounded movie segment for %s", info.model)

    def _preview_frames(self, info: CameraStreamInfo) -> Iterator[bytes]:
        with tempfile.TemporaryDirectory(prefix="timelapse-live-preview-") as temp_dir:
            target = Path(temp_dir) / "preview.jpg"
            while not self._stop.is_set():
                result = subprocess.run(
                    [
                        GPHOTO2_CMD,
                        "--port",
                        info.port,
                        "--capture-preview",
                        "--filename",
                        str(target),
                        "--force-overwrite",
                    ],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                if result.returncode != 0 or not target.exists():
                    error = (result.stderr or result.stdout).decode(errors="replace").strip()
                    self.last_error = error or "Kameraets preview fejlede"
                    raise LiveVideoError(self.last_error)
                frame = target.read_bytes()
                if not frame.startswith(b"\xff\xd8") or not frame.endswith(b"\xff\xd9"):
                    raise LiveVideoError("Kameraets preview var ikke et gyldigt JPEG-billede")
                yield frame
                self._stop.wait(self.preview_interval_s)
