#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — Frame Push Live View (F-013C)
──────────────────────────────────────────────────────────────────────────────────
Version  : 1.1.0
Dato     : 13. juli 2026
Formål   : Real-time video streaming via frame push

Edge pushes frames to headend via HTTP POST.
Browser polls frames from headend via GET.

Arkitektur:
  Camera → gphoto2 → Edge → HTTP POST → Headend → Browser GET

Ingen direkte forbindelse fra headend til edge!

v1.1.0: Integrated camera driver - uses shared driver instance to avoid
        gphoto2 exclusive access conflicts.
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Configuration
FRAME_INTERVAL = 0.8  # Sekunder mellem frames
FRAME_DIR = Path(tempfile.gettempdir()) / "frame_push"
FRAME_PATH = FRAME_DIR / "live_preview.jpg"


class FramePusher:
    """
    Captures preview frames from gphoto2 and pushes to headend.

    Runs in background thread, continuously capturing and uploading.
    """

    def __init__(self, device_id: str, api_client, camera_driver=None):
        """
        Initialize frame pusher.

        Args:
            device_id: Device ID for API calls
            api_client: Edge API client instance
            camera_driver: Optional camera driver instance (GPhoto2Driver).
                          If provided, uses driver.capture_preview() instead
                          of direct gphoto2 subprocess to avoid exclusive
                          access conflicts.
        """
        self._device_id = device_id
        self._api = api_client
        self._camera = camera_driver
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_upload_time = 0
        self._upload_lock = threading.Lock()
        self._preview_dir = FRAME_DIR

    def start(self):
        """Start frame capture and upload loop."""
        if self._running:
            return

        self._running = True
        self._preview_dir.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(target=self._capture_and_upload_loop, daemon=True, name="frame-pusher")
        self._thread.start()
        log.info("FRAME PUSH: Started (device=%s, camera=%s)",
                 self._device_id, "shared" if self._camera else "direct")

    def stop(self):
        """Stop frame capture and upload loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("FRAME PUSH: Stopped")

    def _capture_and_upload_loop(self):
        """Continuously capture frames and push to headend."""
        while self._running:
            try:
                # Capture frame from gphoto2
                frame_data = self._capture_frame()

                if frame_data:
                    # Upload to headend
                    self._upload_frame(frame_data)

            except Exception as e:
                log.debug("FRAME PUSH: Error in loop: %s", e)

            time.sleep(FRAME_INTERVAL)

    def _capture_frame(self) -> Optional[bytes]:
        """
        Capture preview frame from gphoto2.

        Uses shared camera driver if available, otherwise direct subprocess.
        """
        try:
            if self._camera:
                # Use shared camera driver's capture_preview method
                # This avoids exclusive access conflicts
                preview_path = self._camera.capture_preview(self._preview_dir)
                if preview_path and preview_path.exists():
                    return preview_path.read_bytes()
                else:
                    log.warning("FRAME PUSH: Camera preview capture returned no file")
                    return None
            else:
                # Fallback: direct gphoto2 subprocess (legacy mode)
                import subprocess
                result = subprocess.run(
                    ["gphoto2", "--capture-preview", "--filename", str(FRAME_PATH), "--force-overwrite"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                )

                if result.returncode == 0 and FRAME_PATH.exists():
                    return FRAME_PATH.read_bytes()
                else:
                    log.warning("FRAME PUSH: gphoto2 capture failed: %s", result.stderr)
                    return None

        except Exception as e:
            log.warning("FRAME PUSH: Capture error: %s", e)
            return None

    def _upload_frame(self, frame_data: bytes):
        """Upload frame to headend via API."""
        try:
            with self._upload_lock:
                # Check if we should rate-limit uploads
                now = time.time()
                if now - self._last_upload_time < FRAME_INTERVAL:
                    return  # Skip upload if too soon

                # Upload via existing API client
                self._api.upload_live_frame(self._device_id, frame_data)
                self._last_upload_time = now

        except Exception as e:
            log.debug("FRAME PUSH: Upload error: %s", e)

    def is_running(self) -> bool:
        """Check if frame pusher is running."""
        return self._running


# ── Global instance for agent.py integration ─────────────────────────────────────

_global_frame_pusher: Optional[FramePusher] = None


def start_frame_push(device_id: str, api_client, camera_driver=None) -> bool:
    """
    Start frame pusher for device.

    Args:
        device_id: Device ID
        api_client: Edge API client instance
        camera_driver: Optional camera driver instance (recommended)

    Returns:
        True if started successfully, False otherwise
    """
    global _global_frame_pusher

    if _global_frame_pusher and _global_frame_pusher.is_running():
        log.info("FRAME PUSH: Already running")
        return True

    try:
        _global_frame_pusher = FramePusher(device_id, api_client, camera_driver)
        _global_frame_pusher.start()
        return True

    except Exception as e:
        log.error("FRAME PUSH: Failed to start: %s", e)
        return False


def stop_frame_push() -> None:
    """Stop global frame pusher."""
    global _global_frame_pusher

    if _global_frame_pusher:
        _global_frame_pusher.stop()
        _global_frame_pusher = None


def is_running() -> bool:
    """Check if frame pusher is running."""
    return _global_frame_pusher is not None and _global_frame_pusher.is_running()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Test mode - requires API client mock
    print("Frame Push module loaded (test mode)")
