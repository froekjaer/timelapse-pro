#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — Frame Push Live View (F-013C)
──────────────────────────────────────────────────────────────────────────────────
Version  : 1.0.0
Dato     : 13. juli 2026
Formål   : Real-time video streaming via frame push

Edge pushes frames to headend via HTTP POST.
Browser polls frames from headend via GET.

Arkitektur:
  Camera → gphoto2 → Edge → HTTP POST → Headend → Browser GET

Ingen direkte forbindelse fra headend til edge!
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Configuration
FRAME_INTERVAL = 0.8  # Sekunder mellem frames (gphoto2 limit)
FRAME_DIR = Path(tempfile.gettempdir()) / "frame_push"
FRAME_PATH = FRAME_DIR / "live_preview.jpg"


class FramePusher:
    """
    Captures preview frames from gphoto2 and pushes to headend.

    Runs in background thread, continuously capturing and uploading.
    """

    def __init__(self, device_id: str, api_client):
        """
        Initialize frame pusher.

        Args:
            device_id: Device ID for API calls
            api_client: Edge API client instance
        """
        self._device_id = device_id
        self._api = api_client
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_path = FRAME_PATH
        self._last_upload_time = 0
        self._upload_lock = threading.Lock()

    def start(self):
        """Start frame capture and upload loop."""
        if self._running:
            return

        self._running = True
        FRAME_DIR.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(target=self._capture_and_upload_loop, daemon=True, name="frame-pusher")
        self._thread.start()
        log.info("FRAME PUSH: Started (device=%s)", self._device_id)

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
                log.error("FRAME PUSH: Error in loop: %s", e)

            time.sleep(FRAME_INTERVAL)

    def _capture_frame(self) -> Optional[bytes]:
        """Capture preview frame from gphoto2."""
        try:
            result = subprocess.run(
                ["gphoto2", "--capture-preview", "--filename", str(self._frame_path), "--force-overwrite"],
                capture_output=True,
                text=True,
                timeout=12,
            )

            if result.returncode == 0 and self._frame_path.exists():
                return self._frame_path.read_bytes()
            else:
                log.warning("FRAME PUSH: gphoto2 capture failed: %s", result.stderr)
                return None

        except subprocess.TimeoutExpired:
            log.warning("FRAME PUSH: gphoto2 capture timeout")
            return None
        except Exception as e:
            log.error("FRAME PUSH: Capture error: %s", e)
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


def start_frame_push(device_id: str, api_client) -> bool:
    """
    Start frame pusher for device.

    Args:
        device_id: Device ID
        api_client: Edge API client instance

    Returns:
        True if started successfully, False otherwise
    """
    global _global_frame_pusher

    if _global_frame_pusher and _global_frame_pusher.is_running():
        log.info("FRAME PUSH: Already running")
        return True

    try:
        _global_frame_pusher = FramePusher(device_id, api_client)
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
