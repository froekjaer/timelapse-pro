#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — MJPEG Live View Server (F-013B)
──────────────────────────────────────────────────────────────────────────────────
Version  : 1.0.0
Dato     : 13. juli 2026
Formål   : Real-time video streaming fra kamera til browser via MJPEG

HTTP MJPEG streaming - meget simplere end WebRTC!
Browser: <img src="http://edge:8101/mjpeg" />

Kører på port 8101 (ved siden af technician UI på 8099).
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Configuration
MJPEG_PORT = 8101
FRAME_INTERVAL = 0.8  # Sekunder mellem frames (gphoto2 limit)
FRAME_DIR = Path(tempfile.gettempdir()) / "mjpeg_frames"
CONTENT_TYPE = "multipart/x-mixed-replace; boundary=FRAME"


# ═══════════════════════════════════════════════════════════════════════════════
# gphoto2 Frame Capture
# ═══════════════════════════════════════════════════════════════════════════════

class MJPEGFrameSource:
    """
    Captures preview frames from gphoto2 camera.
    Runs capture loop in background thread.
    """

    def __init__(self, interval: float = FRAME_INTERVAL):
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_path = FRAME_DIR / "preview.jpg"
        self._latest_frame: Optional[bytes] = None
        self._latest_timestamp = 0.0
        self._lock = threading.Lock()

    def start(self):
        """Start frame capture loop."""
        if self._running:
            return

        self._running = True
        FRAME_DIR.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="mjpeg-capture")
        self._thread.start()
        log.info(f"MJPEG: Frame capture started (interval={self._interval}s)")

    def stop(self):
        """Stop frame capture loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        log.info("MJPEG: Frame capture stopped")

    def _capture_loop(self):
        """Continuously capture frames from gphoto2."""
        while self._running:
            try:
                # Run gphoto2 capture-preview
                result = subprocess.run(
                    ["gphoto2", "--capture-preview", "--filename", str(self._frame_path), "--force-overwrite"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                )

                if result.returncode == 0 and self._frame_path.exists():
                    frame_data = self._frame_path.read_bytes()
                    with self._lock:
                        self._latest_frame = frame_data
                        self._latest_timestamp = time.time()
                else:
                    log.warning(f"MJPEG: gphoto2 capture failed: {result.stderr}")

            except subprocess.TimeoutExpired:
                log.warning("MJPEG: gphoto2 capture timeout")
            except Exception as e:
                log.error(f"MJPEG: gphoto2 capture error: {e}")

            time.sleep(self._interval)

    def get_frame(self) -> Optional[bytes]:
        """Get latest captured frame."""
        with self._lock:
            return self._latest_frame

    def get_timestamp(self) -> float:
        """Get timestamp of latest frame."""
        with self._lock:
            return self._latest_timestamp

    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._running


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP MJPEG Server
# ═══════════════════════════════════════════════════════════════════════════════

class MJPEGRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MJPEG streaming."""

    def __init__(self, *args, frame_source: MJPEGFrameSource, **kwargs):
        self.frame_source = frame_source
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Override to use proper logging."""
        log.info(f"MJPEG: {self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/mjpeg":
            self.serve_mjpeg_stream()
        elif self.path == "/health":
            self.serve_health()
        else:
            self.send_error(404, "Not found")

    def serve_mjpeg_stream(self) -> None:
        """Serve MJPEG stream to browser."""
        # Send HTTP headers
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

        # Stream frames
        try:
            while True:
                frame = self.frame_source.get_frame()
                if frame:
                    self.wfile.write(b"--FRAME\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n".encode())
                    self.wfile.write(b"\r\n")
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")

                # Small delay to prevent flooding
                time.sleep(0.1)

        except (BrokenPipeError, ConnectionResetError):
            log.debug("MJPEG: Client disconnected")
        except Exception as e:
            log.error(f"MJPEG: Stream error: {e}")

    def serve_health(self) -> None:
        """Serve health check."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


# ═══════════════════════════════════════════════════════════════════════════════
# Server Management
# ═══════════════════════════════════════════════════════════════════════════════

_global_frame_source: Optional[MJPEGFrameSource] = None
_global_server: Optional[HTTPServer] = None
_global_server_thread: Optional[threading.Thread] = None


def start_mjpeg_server(port: int = MJPEG_PORT) -> bool:
    """
    Start MJPEG server in background thread.
    Returns True if started successfully, False otherwise.
    """
    global _global_frame_source, _global_server, _global_server_thread

    if _global_server:
        log.info("MJPEG: Server already running")
        return True

    try:
        # Start frame source
        _global_frame_source = MJPEGFrameSource()
        _global_frame_source.start()

        # Start HTTP server
        def handler(*args, **kwargs):
            return MJPEGRequestHandler(*args, frame_source=_global_frame_source, **kwargs)

        _global_server = HTTPServer(("0.0.0.0", port), handler)
        _global_server_thread = threading.Thread(target=_global_server.serve_forever, daemon=True, name="mjpeg-server")
        _global_server_thread.start()

        log.info(f"MJPEG: Server started on port {port}")
        return True

    except Exception as e:
        log.error(f"MJPEG: Failed to start server: {e}")
        return False


def stop_mjpeg_server() -> None:
    """Stop MJPEG server."""
    global _global_frame_source, _global_server, _global_server_thread

    log.info("MJPEG: Stopping server")

    if _global_server:
        _global_server.shutdown()
        _global_server = None

    if _global_server_thread:
        _global_server_thread = None

    if _global_frame_source:
        _global_frame_source.stop()
        _global_frame_source = None

    log.info("MJPEG: Server stopped")


def is_running() -> bool:
    """Check if MJPEG server is running."""
    return _global_server is not None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    start_mjpeg_server()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_mjpeg_server()
