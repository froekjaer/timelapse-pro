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
import subprocess
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

# Configuration
FRAME_INTERVAL = 0.2  # Upload frames max every 200ms (5 FPS for preview)
MAX_FRAME_SIZE = 512 * 1024  # Max 512KB per frame
JPEG_START = b'\xff\xd8\xff'  # JPEG start marker (SOI + first byte)
JPEG_END = b'\xff\xd9'  # JPEG end marker (EOI)
MJPG_HEADER = b'Content-Length:'


class MJPEGParser:
    """
    Parse MJPEG stream from gphoto2 --capture-movie.

    MJPEG format: HTTP multipart with JPEG frames.
    Each frame starts with headers followed by JPEG data.
    """

    def __init__(self):
        self.buffer = bytearray()
        self.frame_count = 0

    def feed(self, data: bytes) -> list[bytes]:
        """
        Feed new data from stdout and return complete JPEG frames.
        """
        self.buffer.extend(data)
        frames = []

        while len(self.buffer) > 0:
            # Find JPEG start marker
            start_idx = self.buffer.find(b'\xff\xd8')
            if start_idx == -1:
                # No start marker, clear buffer (keep last 100 bytes for partial matches)
                self.buffer = self.buffer[-100:] if len(self.buffer) > 100 else bytearray()
                break

            # Remove everything before JPEG start
            if start_idx > 0:
                self.buffer = self.buffer[start_idx:]

            # Find JPEG end marker (must come after start)
            end_idx = self.buffer.find(b'\xff\xd9', 2)  # Start search after SOI
            if end_idx == -1:
                # No end marker yet, wait for more data
                break

            # Extract complete JPEG frame
            frame_end = end_idx + 2  # Include EOI marker
            frame_data = bytes(self.buffer[:frame_end])

            # Only accept if reasonable size (basic validation)
            if 1024 <= len(frame_data) <= MAX_FRAME_SIZE:
                frames.append(frame_data)
                self.frame_count += 1

            # Remove consumed data from buffer
            self.buffer = self.buffer[frame_end:]

        return frames


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
        self._parser = MJPEGParser()
        self._last_upload_time = 0
        self._frames_uploaded = 0
        self._process: Optional[subprocess.Popen] = None

    def start(self):
        """Start live video streaming."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True, name="live-video-streamer")
        self._thread.start()
        log.info("LIVE VIDEO: Started streaming for device %s", self._device_id)

    def stop(self):
        """Stop live video streaming."""
        self._running = False
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
        if self._thread:
            self._thread.join(timeout=3)
        log.info("LIVE VIDEO: Stopped (uploaded %d frames)", self._frames_uploaded)

    def _stream_loop(self):
        """Stream live video and push frames to headend."""
        cmd = [
            "gphoto2",
            "--port", self._camera_port,
            "--capture-movie",
            "--stdout",
            "--frames", "0",  # Unlimited frames
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=8192,  # Line buffered for streaming
            )

            log.info("LIVE VIDEO: gphoto2 capture-movie started (PID: %d)", self._process.pid)

            while self._running:
                try:
                    # Read chunk from stdout
                    chunk = self._process.stdout.read(8192)
                    if not chunk:
                        log.warning("LIVE VIDEO: End of stream from gphoto2")
                        break

                    # Parse MJPEG and extract frames
                    frames = self._parser.feed(chunk)

                    # Upload each frame
                    for frame_data in frames:
                        self._upload_frame(frame_data)

                except Exception as e:
                    log.debug("LIVE VIDEO: Error in stream loop: %s", e)
                    time.sleep(0.1)

        except Exception as e:
            log.error("LIVE VIDEO: Fatal error: %s", e)
        finally:
            self._running = False
            if self._process:
                self._process.terminate()

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
        _global_streamer.start()
        return True

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
