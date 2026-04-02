"""
TimeLapse Pro — gPhoto2 Camera Driver
======================================
Implements CameraBase for Canon EOS DSLR cameras via gphoto2 CLI.
Tested with: EOS 1300D, EOS 2000D, EOS 800D.

Design decisions:
  - Uses gphoto2 CLI (not the Python binding) for maximum compatibility
    and simpler error handling / subprocess isolation.
  - Camera power is managed externally via GPIO relay — this driver
    assumes the camera is already powered on when connect() is called.
  - Images are downloaded to a temp path first, then moved to dest_dir
    atomically to avoid partial-file reads by the upload manager.
  - SHA-256 is computed immediately after download, before the temp
    file is moved, to catch any download corruption.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from camera.base import (
    CameraBase,
    CameraError,
    CameraNotFoundError,
    CameraState,
    CameraStatus,
    CameraTimeoutError,
    CaptureResult,
    CaptureFailed,
)

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

GPHOTO2_CMD          = "gphoto2"
CONNECT_TIMEOUT_S    = 15
CAPTURE_TIMEOUT_S    = 60   # generous — RAW takes longer
DOWNLOAD_TIMEOUT_S   = 30
STATUS_TIMEOUT_S     = 10
HEALTH_TIMEOUT_S     = 5
MAX_DETECT_RETRIES   = 3
DETECT_RETRY_DELAY_S = 2


# ── Helper ────────────────────────────────────────────────────────────────────

def _run(args: list[str], timeout: int, check: bool = True) -> subprocess.CompletedProcess:
    """Run gphoto2 subprocess, return CompletedProcess."""
    log.debug("gphoto2 cmd: %s", " ".join(args))
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise CameraError(
                f"gphoto2 returned {result.returncode}: {result.stderr.strip()}"
            )
        return result
    except subprocess.TimeoutExpired as exc:
        raise CameraTimeoutError(
            f"gphoto2 timed out after {timeout}s: {' '.join(args)}"
        ) from exc
    except FileNotFoundError as exc:
        raise CameraError(
            "gphoto2 not found — run: apt install gphoto2"
        ) from exc


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Driver ────────────────────────────────────────────────────────────────────

def _parse_gphoto2_config(output: str) -> list[dict]:
    """Parse output of gphoto2 --list-all-config into structured dicts."""
    params = []
    current: dict = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("/main/"):
            if current.get("path"):
                params.append(current)
            current = {"path": line, "label": "", "type": "", "current": "",
                       "choices": [], "readonly": False}
        elif line.startswith("Label:"):
            current["label"] = line.split(":", 1)[1].strip()
        elif line.startswith("Type:"):
            current["type"] = line.split(":", 1)[1].strip()
        elif line.startswith("Readonly:"):
            current["readonly"] = line.split(":", 1)[1].strip() == "1"
        elif line.startswith("Current:"):
            current["current"] = line.split(":", 1)[1].strip()
        elif line.startswith("Choice:"):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                current["choices"].append({"index": parts[1], "label": parts[2]})
        elif line == "END" and current.get("path"):
            params.append(current)
            current = {}
    return params


class GPhoto2Driver(CameraBase):
    """
    gPhoto2-based driver for Canon EOS DSLR cameras.

    Config keys (from config.yaml camera section):
        gphoto2_port:          str   e.g. "usb:" or "usb:001,004"
        capture_timeout:       int   seconds (default 60)
        download_timeout:      int   seconds (default 30)
        delete_after_download: bool  (default true)
    """

    SUPPORTED = [
        "Canon EOS 1300D", "Canon EOS 1200D", "Canon EOS 1100D",
        "Canon EOS 2000D", "Canon EOS 4000D", "Canon EOS 800D",
        "Canon EOS 750D", "Canon EOS 700D", "Canon EOS 650D",
        "Canon EOS 600D", "Canon EOS 550D", "Canon EOS 100D",
        "Canon EOS 200D", "Canon EOS 250D", "Canon EOS 90D",
        "Canon EOS 80D",  "Canon EOS 77D",  "Canon EOS 760D",
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self._port:         str           = config.get("gphoto2_port", "usb:")
        self._model:        Optional[str] = None
        self._cap_timeout:  int           = config.get("capture_timeout", CAPTURE_TIMEOUT_S)
        self._dl_timeout:   int           = config.get("download_timeout", DOWNLOAD_TIMEOUT_S)
        self._delete_after: bool          = config.get("delete_after_download", True)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Detect camera on USB, verify it responds."""
        log.info("Connecting to camera via gphoto2 (port=%s)…", self._port)

        for attempt in range(1, MAX_DETECT_RETRIES + 1):
            try:
                result = _run(
                    [GPHOTO2_CMD, "--auto-detect"],
                    timeout=CONNECT_TIMEOUT_S,
                )
                # Parse model from output:
                #   Model                          Port
                #   Canon EOS 1300D                usb:002,004
                lines = result.stdout.strip().splitlines()
                for line in lines[2:]:  # skip header rows
                    if "usb" in line.lower() or "ptpip" in line.lower():
                        self._model = line.split("  ")[0].strip()
                        break

                if not self._model:
                    raise CameraNotFoundError("No camera found by gphoto2 --auto-detect")

                log.info("Camera detected: %s", self._model)
                self._connected = True
                return

            except (CameraNotFoundError, CameraError) as exc:
                if attempt < MAX_DETECT_RETRIES:
                    log.warning(
                        "Detection attempt %d/%d failed: %s — retrying in %ds",
                        attempt, MAX_DETECT_RETRIES, exc, DETECT_RETRY_DELAY_S
                    )
                    time.sleep(DETECT_RETRY_DELAY_S)
                else:
                    raise CameraNotFoundError(
                        f"Camera not found after {MAX_DETECT_RETRIES} attempts: {exc}"
                    ) from exc

    def disconnect(self) -> None:
        """Release camera. For gphoto2 CLI this is a no-op."""
        self._connected = False
        self._model = None
        log.debug("gPhoto2Driver disconnected")

    # ── Core operations ────────────────────────────────────────────────────

    def capture_image(self, dest_dir: Path) -> CaptureResult:
        """
        Trigger capture, wait for processing, download, delete from camera.
        Image filename includes UTC timestamp for unambiguous ordering.
        """
        if not self._connected:
            raise CameraError("Not connected — call connect() first")

        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc)

        # Use a temp dir inside dest_dir so the atomic rename stays on the
        # same filesystem (avoids cross-device link errors on SSD + tmpfs).
        with tempfile.TemporaryDirectory(dir=dest_dir, prefix=".tmp_capture_") as tmp:
            tmp_path = Path(tmp)

            log.info("Triggering capture…")
            try:
                result = _run(
                    [
                        GPHOTO2_CMD,
                        "--port", self._port,
                        "--capture-image-and-download",
                        "--filename", str(tmp_path / "%Y%m%d_%H%M%S.%C"),
                        "--force-overwrite",
                        "--keep-raw",       # download all files camera produced
                    ],
                    timeout=self._cap_timeout,
                )
            except CameraError as exc:
                raise CaptureFailed(f"Capture failed: {exc}") from exc

            # Find downloaded file(s) — pick largest (RAW > JPG if both exist)
            files = sorted(tmp_path.iterdir(), key=lambda p: p.stat().st_size, reverse=True)
            if not files:
                raise CaptureFailed(
                    f"gphoto2 ran but no file downloaded to {tmp_path}. "
                    f"stdout={result.stdout[:200]}"
                )

            tmp_file = files[0]
            log.info("Downloaded: %s (%d bytes)", tmp_file.name, tmp_file.stat().st_size)

            # Compute hash before moving
            sha256 = _sha256(tmp_file)

            # Build final filename: <kunde>_<site>_<kamera>_<timestamp>.<ext>
            # Fallback til device_id hvis navne ikke er konfigureret
            import re
            def _sanitize(s):
                return re.sub(r'[^A-Za-z0-9æøåÆØÅ]', '_', str(s)).strip('_') if s else ''
            device_id = self._config.get("device_id", "unknown")
            customer  = _sanitize(self._config.get("customer_name", ""))
            site      = _sanitize(self._config.get("site_name", ""))
            camera    = _sanitize(self._config.get("camera_name", ""))
            ts_str    = timestamp.strftime("%Y%m%d_%H%M%S")
            if customer and site and camera:
                final_name = f"{customer}_{site}_{camera}_{ts_str}{tmp_file.suffix}"
            else:
                final_name = f"{device_id}_{ts_str}{tmp_file.suffix}"
            final_path = dest_dir / final_name

            # Atomic rename within same filesystem
            shutil.move(str(tmp_file), str(final_path))

        # Delete from camera if configured
        if self._delete_after:
            self._delete_camera_files()

        # Read EXIF-like data from gphoto2 config
        exposure, aperture, iso, focus_mode = self._read_capture_settings()

        return CaptureResult(
            filepath      = final_path,
            timestamp     = timestamp,
            filesize      = final_path.stat().st_size,
            sha256        = sha256,
            camera_model  = self._model or "Unknown Canon DSLR",
            driver_name   = self.driver_name,
            exposure_time = exposure,
            aperture      = aperture,
            iso           = iso,
            focus_mode    = focus_mode,
        )

    def get_status(self) -> CameraStatus:
        """Return camera status including battery level."""
        try:
            result = _run(
                [GPHOTO2_CMD, "--port", self._port, "--summary"],
                timeout=STATUS_TIMEOUT_S,
                check=False,
            )
            battery = self._parse_battery(result.stdout)
            state = (CameraState.CONNECTED
                     if result.returncode == 0
                     else CameraState.ERROR)
            return CameraStatus(
                state           = state,
                model           = self._model or "Unknown",
                driver          = self.driver_name,
                battery_pct     = battery,
                storage_free_mb = None,   # not easily available via gphoto2
                error_message   = result.stderr.strip() if result.returncode != 0 else None,
                raw             = {"stdout": result.stdout[:500]},
            )
        except Exception as exc:
            return CameraStatus(
                state         = CameraState.ERROR,
                model         = self._model or "Unknown",
                driver        = self.driver_name,
                battery_pct   = None,
                storage_free_mb=None,
                error_message = str(exc),
            )

    def health_check(self) -> bool:
        """Quick check: can gphoto2 see the camera?"""
        try:
            result = _run(
                [GPHOTO2_CMD, "--auto-detect"],
                timeout=HEALTH_TIMEOUT_S,
                check=False,
            )
            return result.returncode == 0 and "usb" in result.stdout.lower()
        except Exception:
            return False

    # ── Feature detection ──────────────────────────────────────────────────

    def supports_autofocus(self) -> bool:
        """
        Canon EOS DSLRs do not reliably support remote AF via gphoto2.
        PTP protocol exposes autofocusdrive but it is camera-dependent
        and unreliable for unattended operation.
        """
        return False

    def supports_liveview(self) -> bool:
        """gphoto2 supports liveview capture on many Canon models."""
        return True

    def supports_remote_focus(self) -> bool:
        """Step-motor focus control not available via gphoto2."""
        return False

    # ── Config / settings ──────────────────────────────────────────────────

    def capture_preview(self, dest_dir: Path) -> Path:
        """
        Capture a low-resolution preview image (no shutter count increment).
        Returns path to saved JPEG (1056x704 on Canon EOS 1300D).
        """
        import tempfile, shutil, time
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"preview_{ts_str}.jpg"
        # gphoto2 adds 'thumb_' prefix for previews
        tmp_path = dest_dir / f"thumb_{filename}"
        target   = dest_dir / filename
        _run(
            [GPHOTO2_CMD, "--capture-preview",
             "--filename", str(dest_dir / filename)],
            timeout=15,
        )
        # gphoto2 may save as thumb_<filename>
        if tmp_path.exists() and not target.exists():
            shutil.move(str(tmp_path), str(target))
        elif not target.exists():
            # Find any recently created preview
            previews = sorted(dest_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
            if previews:
                target = previews[-1]
        log.info("Preview captured: %s (%d KB)", target.name, target.stat().st_size // 1024)
        return target

    def get_all_config(self) -> list[dict]:
        """
        Read all camera configuration via gphoto2 --list-all-config.
        Returns list of dicts with keys: path, label, type, current, choices, readonly.
        """
        result = _run(
            [GPHOTO2_CMD, "--list-all-config"],
            timeout=30, check=False
        )
        if result.returncode != 0:
            return []
        return _parse_gphoto2_config(result.stdout)

    def set_config(self, key: str, value: str) -> None:
        """Set a camera config value via gphoto2 --set-config."""
        log.debug("set_config %s = %s", key, value)
        _run(
            [GPHOTO2_CMD, "--port", self._port,
             "--set-config", f"{key}={value}"],
            timeout=STATUS_TIMEOUT_S,
        )

    # ── Driver metadata ────────────────────────────────────────────────────

    @property
    def driver_name(self) -> str:
        return "gphoto2"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED

    # ── Private helpers ────────────────────────────────────────────────────

    def _delete_camera_files(self) -> None:
        """Delete all files from camera memory after download."""
        try:
            _run(
                [GPHOTO2_CMD, "--port", self._port, "--delete-all-files"],
                timeout=DOWNLOAD_TIMEOUT_S,
            )
            log.debug("Camera memory cleared")
        except CameraError as exc:
            # Non-fatal — log and continue
            log.warning("Could not delete camera files: %s", exc)

    def _parse_battery(self, summary_text: str) -> Optional[int]:
        """Extract battery percentage from gphoto2 --summary output."""
        # Typical line: "Battery Level: 75%"
        match = re.search(r"[Bb]attery[^:]*:\s*(\d+)\s*%", summary_text)
        if match:
            return int(match.group(1))
        return None

    def _read_capture_settings(self) -> tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
        """
        Read current shutter speed, aperture, ISO, focus mode from camera.
        Returns (exposure, aperture, iso, focus_mode). Any may be None.
        """
        settings = {
            "/main/capturesettings/shutterspeed": None,
            "/main/capturesettings/aperture":     None,
            "/main/capturesettings/iso":          None,
            "/main/capturesettings/focusmode":    None,
        }
        for key in settings:
            try:
                r = _run(
                    [GPHOTO2_CMD, "--port", self._port, "--get-config", key],
                    timeout=STATUS_TIMEOUT_S,
                    check=False,
                )
                if r.returncode == 0:
                    # Output: "Current: 1/250"
                    m = re.search(r"Current:\s*(.+)", r.stdout)
                    if m:
                        settings[key] = m.group(1).strip()
            except Exception:
                pass

        exposure   = settings["/main/capturesettings/shutterspeed"]
        aperture   = settings["/main/capturesettings/aperture"]
        iso_str    = settings["/main/capturesettings/iso"]
        focus_mode = settings["/main/capturesettings/focusmode"]

        try:
            iso = int(iso_str) if iso_str else None
        except ValueError:
            iso = None

        return exposure, aperture, iso, focus_mode
