#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — Frame Push Live View (F-013C)
──────────────────────────────────────────────────────────────────────────────────
Version  : 2.0.0
Dato     : 13. juli 2026
Formål   : Real-time video streaming via MJPEG frame push

Edge pushes frames to headend via HTTP POST.
Browser polls frames from headend via GET.

Arkitektur:
  Camera → gphoto2 --capture-movie → MJPEG stream → Edge → HTTP POST → Headend → Browser

Ingen direkte forbindelse fra headend til edge!

v2.0.0: Live video streaming using gphoto2 --capture-movie --stdout
        Parses MJPEG stream and extracts individual JPEG frames at ~15-30 FPS
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from camera.live_video import GPhoto2FrameSource, LiveVideoError, MJPEGParser

log = logging.getLogger(__name__)

# Configuration
FRAME_INTERVAL = 0.2  # Upload frames max every 200ms (5 FPS for preview)
STARTUP_TIMEOUT_S = 20


class LiveVideoStreamer:
    """
    Stream live video from camera using gphoto2 --capture-movie.

    Runs gphoto2 in subprocess, parses MJPEG output,
    and pushes frames to headend.
    """

    def __init__(self, device_id: str, api_client, camera_port: str = "usb:"):
        self._device_id = device_id
        self._api = api_client
        self._camera_port = camera_port
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_upload_time = 0
        self._frames_uploaded = 0
        self._source: Optional[GPhoto2FrameSource] = None
        self._ready = threading.Event()
        self._started = threading.Event()
        self._last_error = ""

    def start(self) -> bool:
        """Start live video streaming."""
        if self._running:
            return self._ready.is_set()

        self._running = True
        self._ready.clear()
        self._started.clear()
        self._last_error = ""
        self._thread = threading.Thread(target=self._stream_loop, daemon=True, name="live-video-streamer")
        self._thread.start()
        self._started.wait(STARTUP_TIMEOUT_S)
        if not self._ready.is_set():
            self.stop()
            log.error("LIVE VIDEO: Startup failed for %s: %s", self._device_id, self._last_error)
            return False
        log.info("LIVE VIDEO: Started streaming for device %s", self._device_id)
        return True

    def stop(self):
        """Stop live video streaming."""
        self._running = False
        if self._source:
            self._source.stop()
        if self._thread:
            self._thread.join(timeout=3)
        log.info("LIVE VIDEO: Stopped (uploaded %d frames)", self._frames_uploaded)

    def _stream_loop(self):
        """Stream live video and push frames to headend."""
        try:
            self._source = GPhoto2FrameSource(self._camera_port)
            info = self._source.detect()
            log.info(
                "LIVE VIDEO: %s selected for %s on %s",
                info.mode,
                info.model,
                info.port,
            )
            for frame_data in self._source.frames():
                if not self._running:
                    break
                if not self._ready.is_set():
                    self._ready.set()
                    self._started.set()
                self._upload_frame(frame_data)
        except LiveVideoError as exc:
            self._last_error = str(exc)
            log.error("LIVE VIDEO: Camera stream failed: %s", exc)
        except Exception as exc:
            self._last_error = str(exc)
            log.exception("LIVE VIDEO: Fatal error: %s", exc)
        finally:
            self._running = False
            self._started.set()
            if self._source:
                self._source.stop()

    def _upload_frame(self, frame_data: bytes):
        """Upload frame to headend via API."""
        try:
            # Rate limit uploads
            now = time.time()
            if now - self._last_upload_time < FRAME_INTERVAL:
                return  # Skip if too soon

            self._last_upload_time = now
            success, error = self._api.upload_live_frame(frame_data)

            if success:
                self._frames_uploaded += 1
                if self._frames_uploaded % 100 == 0:  # Log every 100 frames
                    log.info("LIVE VIDEO: Streamed %d frames", self._frames_uploaded)
            else:
                # Only log non-503 errors (503 = headend busy, just skip frame)
                if error and "503" not in error:
                    log.warning("LIVE VIDEO: Upload failed - %s", error)

        except Exception as e:
            log.warning("LIVE VIDEO: Upload exception: %s", e)

    def is_running(self) -> bool:
        """Check if streamer is running."""
        return self._running

    def status(self) -> dict:
        info = self._source.info.to_dict() if self._source and self._source.info else {}
        return {
            "running": self._running,
            "ready": self._ready.is_set(),
            "frames_uploaded": self._frames_uploaded,
            "error": self._last_error,
            **info,
        }


# ── Global instance for agent.py integration ─────────────────────────────────────

_global_streamer: Optional[LiveVideoStreamer] = None


def start_frame_push(device_id: str, api_client, camera_driver=None) -> bool:
    """
    Start live video streaming for device.

    Args:
        device_id: Device ID
        api_client: Edge API client instance
        camera_driver: Used only for the configured gphoto2 port. Movie
            capture still owns its own gphoto2 process.

    Returns:
        True if started successfully, False otherwise
    """
    global _global_streamer

    if _global_streamer and _global_streamer.is_running():
        log.info("LIVE VIDEO: Already running")
        return True

    try:
        camera_port = getattr(camera_driver, "_port", "usb:")
        _global_streamer = LiveVideoStreamer(device_id, api_client, camera_port)
        return _global_streamer.start()

    except Exception as e:
        log.error("LIVE VIDEO: Failed to start: %s", e)
        return False


def stop_frame_push() -> None:
    """Stop live video streaming."""
    global _global_streamer

    if _global_streamer:
        _global_streamer.stop()
        _global_streamer = None


def is_running() -> bool:
    """Check if live video streaming is running."""
    return _global_streamer is not None and _global_streamer.is_running()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    print("Live Video Streamer module loaded (test mode)")
