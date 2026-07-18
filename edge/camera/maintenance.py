"""Cross-process camera ownership for local technician operations."""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path


DEFAULT_LOCK_PATH = Path("/run/timelapse/camera-maintenance.lock")


class CameraMaintenanceBusy(RuntimeError):
    """Raised when another technician operation owns the camera."""


class CameraMaintenanceLease:
    """Exclusive process-safe lease released automatically on process exit."""

    def __init__(self, timeout_s: float = 45, lock_path: Path | None = None):
        configured = os.getenv("TIMELAPSE_CAMERA_MAINTENANCE_LOCK", "").strip()
        self.lock_path = Path(configured) if configured else (lock_path or DEFAULT_LOCK_PATH)
        self.timeout_s = max(0.0, float(timeout_s))
        self._file = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.lock_path.open("a+", encoding="utf-8")
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._file.seek(0)
                self._file.truncate()
                self._file.write(f"pid={os.getpid()} acquired={time.time():.3f}\n")
                self._file.flush()
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._file.close()
                    self._file = None
                    raise CameraMaintenanceBusy(
                        "Kameraet bruges allerede af en anden teknikerhandling eller Live View"
                    )
                time.sleep(0.2)

    def __exit__(self, _exc_type, _exc, _traceback):
        if self._file is not None:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None

