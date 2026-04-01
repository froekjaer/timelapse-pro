"""
TimeLapse Pro — Camera Abstraction Layer
========================================
All camera drivers must implement this interface.
The capture engine speaks only to this API — it never knows which
physical camera is attached.

SABSA mapping:
  Extensibility  — new cameras = new driver, zero changes to engine
  Availability   — health_check() called before every capture cycle
  Integrity      — capture returns CaptureResult with metadata
"""

from __future__ import annotations

import abc
import dataclasses
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class CameraState(Enum):
    UNKNOWN      = "unknown"
    CONNECTED    = "connected"
    DISCONNECTED = "disconnected"
    ERROR        = "error"
    BUSY         = "busy"


@dataclasses.dataclass
class CaptureResult:
    """Returned by capture_image() on success."""
    filepath:      Path            # absolute path to downloaded image
    timestamp:     datetime        # UTC time of capture trigger
    filesize:      int             # bytes
    sha256:        str             # hex digest
    camera_model:  str             # e.g. "Canon EOS 1300D"
    driver_name:   str             # e.g. "gphoto2"
    exposure_time: Optional[str]   # e.g. "1/250"
    aperture:      Optional[str]   # e.g. "f/8.0"
    iso:           Optional[int]   # e.g. 200
    focus_mode:    Optional[str]   # e.g. "MF"
    extra:         dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class CameraStatus:
    """Returned by get_status()."""
    state:          CameraState
    model:          str
    driver:         str
    battery_pct:    Optional[int]   # 0-100, None if unavailable
    storage_free_mb:Optional[int]   # camera internal storage
    error_message:  Optional[str]
    raw:            dict = dataclasses.field(default_factory=dict)


class CameraError(Exception):
    """Base exception for all camera driver errors."""


class CameraNotFoundError(CameraError):
    """Camera not detected on USB / serial."""


class CameraTimeoutError(CameraError):
    """Operation timed out."""


class CaptureFailed(CameraError):
    """Image capture did not produce a file."""


class CameraBase(abc.ABC):
    """
    Abstract base class for all camera drivers.

    Lifecycle:
        driver = GPhoto2Driver(config)
        driver.connect()          # raises CameraNotFoundError if absent
        result = driver.capture_image(dest_dir)
        driver.disconnect()

    Feature detection (called once at startup):
        driver.supports_autofocus()   -> bool
        driver.supports_liveview()    -> bool
        driver.supports_remote_focus()-> bool
    """

    def __init__(self, config: dict):
        """
        Args:
            config: the 'camera' section from config.yaml
        """
        self._config = config
        self._connected = False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @abc.abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the camera.
        Raises CameraNotFoundError if camera is not detected.
        """

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Release camera connection. Safe to call if not connected."""

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Core operations ───────────────────────────────────────────────────

    @abc.abstractmethod
    def capture_image(self, dest_dir: Path) -> CaptureResult:
        """
        Trigger capture, wait for processing, download image, delete
        from camera memory.

        Args:
            dest_dir: directory where the downloaded image is saved

        Returns:
            CaptureResult with filepath, hash, metadata

        Raises:
            CaptureFailed  — shutter fired but no file produced
            CameraTimeoutError — camera did not respond in time
            CameraError    — any other camera error
        """

    @abc.abstractmethod
    def get_status(self) -> CameraStatus:
        """
        Return current camera state, battery, storage info.
        Should not raise — return state=ERROR on failure.
        """

    @abc.abstractmethod
    def health_check(self) -> bool:
        """
        Quick liveness check. Returns True if camera is responsive.
        Used before every capture cycle. Should complete in < 5 seconds.
        """

    # ── Feature detection ─────────────────────────────────────────────────

    @abc.abstractmethod
    def supports_autofocus(self) -> bool:
        """True if the camera + driver support remote AF trigger."""

    @abc.abstractmethod
    def supports_liveview(self) -> bool:
        """True if liveview / MJPEG stream is available."""

    @abc.abstractmethod
    def supports_remote_focus(self) -> bool:
        """True if focus position can be set remotely (step motor)."""

    # ── Optional operations ───────────────────────────────────────────────

    def run_autofocus(self) -> bool:
        """
        Trigger autofocus. Returns True on success.
        Default: no-op, returns False. Override in capable drivers.
        """
        return False

    def run_refocus(self) -> bool:
        """
        Perform a scheduled refocus cycle (e.g. contrast AF + verify).
        Default: no-op, returns False. Override in capable drivers.
        """
        return False

    def set_config(self, key: str, value: str) -> None:
        """
        Set a camera configuration parameter.
        Default: no-op. Override in drivers that support it.

        Args:
            key:   gphoto2-style path e.g. '/main/capturesettings/iso'
            value: string value e.g. '200'
        """

    def apply_initial_commands(self, commands: list[str]) -> list[str]:
        """
        Apply a list of 'key=value' config strings from config.yaml.
        Returns list of any that failed.
        Default implementation calls set_config() for each.
        """
        failed = []
        for cmd in commands:
            try:
                if '=' not in cmd:
                    continue
                key, _, value = cmd.partition('=')
                self.set_config(key.strip(), value.strip())
            except Exception as exc:
                failed.append(f"{cmd}: {exc}")
        return failed

    # ── Driver metadata ───────────────────────────────────────────────────

    @property
    @abc.abstractmethod
    def driver_name(self) -> str:
        """Short identifier e.g. 'gphoto2', 'canon_sdk'."""

    @property
    @abc.abstractmethod
    def supported_models(self) -> list[str]:
        """
        List of model strings this driver handles.
        Used by driver auto-detection. Glob patterns supported.
        e.g. ['Canon EOS 1300D', 'Canon EOS 2000D']
        """

    def __repr__(self) -> str:
        return (f"<{self.__class__.__name__} "
                f"driver={self.driver_name} "
                f"connected={self._connected}>")
