"""Camera ownership and relay lifecycle for the local technician stream."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path

import yaml

from camera.live_video import GPhoto2FrameSource
from camera.maintenance import CameraMaintenanceLease
from camera.relay import RelayController


log = logging.getLogger(__name__)


class TechnicianStreamManager:
    """Own one bounded local stream and always restore normal Edge operation."""

    def __init__(
        self,
        edge_root: Path,
        service_name: str = "timelapse-edge",
        source_factory=GPhoto2FrameSource,
        relay_factory=RelayController,
    ):
        self.edge_root = Path(edge_root)
        self.service_name = service_name
        self.source_factory = source_factory
        self.relay_factory = relay_factory
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: GPhoto2FrameSource | None = None
        self._latest_frame: bytes | None = None
        self._sequence = 0
        self._status = "stopped"
        self._error = ""
        self._model = ""
        self._port = ""
        self._mode = ""
        self._started_at = 0.0
        self._finished_at = 0.0
        self._frame_count = 0
        self._max_duration_s = 180
        self._preview_interval_s = 0.8

    def start(self, max_duration_s: int = 180, preview_interval_s: float = 0.8) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            self._stop.clear()
            self._latest_frame = None
            self._sequence = 0
            self._status = "starting"
            self._error = ""
            self._model = ""
            self._port = ""
            self._mode = ""
            self._started_at = time.monotonic()
            self._finished_at = 0.0
            self._frame_count = 0
            self._max_duration_s = max(30, min(int(max_duration_s), 3600))
            self._preview_interval_s = max(0.1, float(preview_interval_s))
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="technician-camera-stream",
            )
            self._thread.start()
            return self.status()

    def stop(self, join_timeout_s: float = 45) -> dict:
        with self._condition:
            if self._thread and self._thread.is_alive() and self._status != "error":
                self._status = "stopping"
                self._condition.notify_all()
        self._stop.set()
        source = self._source
        if source:
            source.stop()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=join_timeout_s)
        return self.status()

    def status(self) -> dict:
        with self._lock:
            end = self._finished_at or time.monotonic()
            elapsed = end - self._started_at if self._started_at else 0.0
            active = self._status in {"starting", "running", "stopping"}
            fps = self._frame_count / elapsed if elapsed > 0 else 0.0
            return {
                "status": self._status,
                "running": active,
                "frame_ready": active and self._latest_frame is not None,
                "model": self._model,
                "port": self._port,
                "mode": self._mode,
                "frame_count": self._frame_count,
                "fps": round(fps, 1),
                "max_duration_s": self._max_duration_s,
                "error": self._error,
            }

    def wait_for_frame(self, after_sequence: int, timeout_s: float = 5) -> tuple[int, bytes | None, dict]:
        with self._condition:
            self._condition.wait_for(
                lambda: self._sequence > after_sequence or self._status in {"stopped", "error"},
                timeout=timeout_s,
            )
            return self._sequence, self._latest_frame, self.status()

    def _service_is_active(self) -> bool:
        result = subprocess.run(
            ["systemctl", "is-active", self.service_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip() == "active"

    def _service_is_enabled(self) -> bool:
        result = subprocess.run(
            ["systemctl", "is-enabled", self.service_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip() in {"enabled", "enabled-runtime"}

    def _service_action(self, action: str, timeout: int) -> None:
        subprocess.run(
            ["systemctl", action, self.service_name],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )

    def _run(self) -> None:
        relay = None
        was_active = False
        should_restore_service = False
        lease = CameraMaintenanceLease(timeout_s=45)
        try:
            lease.__enter__()
            was_active = self._service_is_active()
            should_restore_service = was_active or self._service_is_enabled()
            if was_active:
                self._service_action("stop", 120)

            config = yaml.safe_load((self.edge_root / "config.yaml").read_text()) or {}
            relay = self.relay_factory(config)
            relay.camera.power_on()

            camera_config = config.get("camera", {})
            self._source = self.source_factory(
                camera_config.get("gphoto2_port", "usb:"),
                preview_interval_s=self._preview_interval_s,
                movie_segment_s=self._max_duration_s,
            )
            info = self._source.detect()
            with self._condition:
                self._model = info.model
                self._port = info.port
                self._mode = info.mode
                self._condition.notify_all()

            deadline = time.monotonic() + self._max_duration_s
            for frame in self._source.frames():
                if self._stop.is_set() or time.monotonic() >= deadline:
                    break
                with self._condition:
                    self._latest_frame = frame
                    self._sequence += 1
                    self._frame_count += 1
                    self._status = "running"
                    self._condition.notify_all()
        except Exception as exc:
            log.exception("Technician live stream failed")
            with self._condition:
                self._status = "error"
                self._error = str(exc)
                self._condition.notify_all()
        finally:
            if self._source:
                self._source.stop()
            if relay is not None:
                try:
                    relay.camera.force_off()
                except Exception:
                    log.exception("Could not force camera relay off after technician stream")
                try:
                    relay.cleanup(camera=True, modem=False)
                except Exception:
                    log.exception("Could not clean up camera GPIO after technician stream")
            if should_restore_service:
                try:
                    self._service_action("start", 60)
                except Exception:
                    log.exception("Could not restart Edge agent after technician stream")
                    with self._lock:
                        self._error = (self._error + "; " if self._error else "") + "Edge-agent kunne ikke genstartes"
                        self._status = "error"
            lease.__exit__(None, None, None)
            with self._condition:
                self._finished_at = time.monotonic()
                if self._status != "error":
                    self._status = "stopped"
                self._condition.notify_all()
