"""Timelapse payload driver — wraps the REAL edge camera interface behind the
PayloadDriver contract (ADR-002 vertical slice).

This is the first payload. It imports only:
  - contracts/            (the pure platform/payload seam)
  - edge.camera.base      (the existing CameraBase/CaptureResult TYPES)
It does NOT import platform_host/ (anti-coupling invariant, tested).

In production the platform injects a concrete CameraBase (e.g. GPhoto2Driver);
in tests a fake CameraBase is injected. The capture loop, policy handling,
health and command surface mirror the existing edge capture flow, so this
adapter is a credible wrap of the real logic — not a toy.

Tests-only: nothing in edge/agent runtime imports this yet.
"""
from __future__ import annotations

import datetime as _dt
import threading
from pathlib import Path
from typing import Optional

from contracts.control import (
    Command,
    CommandRejected,
    CommandResult,
    HealthReport,
    HealthStatus,
    PayloadDriver,
    PayloadPolicy,
    PolicyRejected,
)
from contracts.data import BlobMeta, DataSink, TimeseriesPoint, Backpressure

# Types only — edge/camera/base.py is import-light (abc/dataclasses/pathlib).
from camera.base import CameraBase, CameraError, CameraState, CaptureResult  # type: ignore


class TimelapsePayloadDriver(PayloadDriver):
    """Drives an injected CameraBase on a schedule, publishing captures as
    classified blobs and capture metrics as timeseries points."""

    ALLOWED_COMMANDS = {"capture_now", "get_stats", "run_autofocus"}

    def __init__(self, camera: CameraBase, sink: DataSink, spool_dir: Path) -> None:
        self._camera = camera
        self._sink = sink
        self._dest = Path(spool_dir)
        self._interval_s: float = 60.0
        self._configured = False
        self._running = threading.Event()
        self._stop_signal = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ok = 0
        self._failed = 0

    # ── control contract ────────────────────────────────────────────────
    def configure(self, policy: PayloadPolicy) -> None:
        interval = policy.settings.get("interval_s")
        if not isinstance(interval, (int, float)) or interval <= 0:
            raise PolicyRejected(f"interval_s must be a positive number, got {interval!r}")
        self._interval_s = float(interval)
        self._dest.mkdir(parents=True, exist_ok=True)
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise PolicyRejected("start() before configure() (fail closed)")
        if self._running.is_set():
            return
        self._camera.connect()  # raises CameraNotFoundError if absent -> supervisor handles
        self._stop_signal.clear()
        self._running.set()
        self._thread = threading.Thread(target=self._loop, name="timelapse-capture", daemon=True)
        self._thread.start()

    def stop(self, deadline_s: float) -> None:
        self._running.clear()
        self._stop_signal.set()
        if self._thread is not None:
            self._thread.join(timeout=deadline_s)
            self._thread = None
        try:
            self._camera.disconnect()
        except Exception:
            pass

    def health(self) -> HealthReport:
        with self._lock:
            ok, failed = self._ok, self._failed
        total = ok + failed
        if total and failed / total > 0.5:
            status = HealthStatus.FAILED
        elif failed:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.OK
        return HealthReport(status=status, detail=f"{ok} ok / {failed} failed",
                            metrics={"captures_ok": ok, "captures_failed": failed})

    def handle_command(self, cmd: Command) -> CommandResult:
        if cmd.name not in self.ALLOWED_COMMANDS:
            raise CommandRejected(f"command {cmd.name!r} not allowlisted (fail closed)")
        if cmd.name == "capture_now":
            receipt = self._capture_once()
            return CommandResult(ok=receipt is not None,
                                 detail="captured" if receipt else "capture failed",
                                 data={"object_id": receipt.object_id} if receipt else {})
        if cmd.name == "run_autofocus":
            return CommandResult(ok=self._camera.run_autofocus())
        with self._lock:
            return CommandResult(ok=True, data={"captures_ok": self._ok,
                                                "captures_failed": self._failed})

    # ── internals ────────────────────────────────────────────────────────
    def _capture_once(self):
        now = _dt.datetime.now(_dt.timezone.utc).isoformat()
        try:
            if not self._camera.health_check():
                raise CameraError("camera health_check failed")
            result: CaptureResult = self._camera.capture_image(self._dest)
            frame = Path(result.filepath).read_bytes()
            receipt = self._sink.put_blob(
                "images", frame,
                BlobMeta(content_type="image/jpeg",
                         captured_at=result.timestamp.isoformat()
                         if hasattr(result.timestamp, "isoformat") else now,
                         attributes={"sha256": result.sha256,
                                     "camera_model": result.camera_model,
                                     "iso": result.iso, "aperture": result.aperture,
                                     "exposure_time": result.exposure_time}))
            with self._lock:
                self._ok += 1
            self._sink.put_point("capture-metrics",
                                 TimeseriesPoint(ts=now, value=1.0, labels={"result": "ok"}))
            return receipt
        except Backpressure:
            with self._lock:
                self._failed += 1  # declared strategy: drop frame, count it
            return None
        except Exception:
            with self._lock:
                self._failed += 1
            try:
                self._sink.put_point("capture-metrics",
                                     TimeseriesPoint(ts=now, value=0.0, labels={"result": "fail"}))
            except Exception:
                pass
            return None

    def _loop(self) -> None:
        while self._running.is_set():
            self._capture_once()
            self._stop_signal.wait(timeout=self._interval_s)
