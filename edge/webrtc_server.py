#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — WebRTC Live View Server
──────────────────────────────────────────────────────────────────────────────────
Version  : 1.0.0
Dato     : 13. juli 2026
Formål   : Real-time video streaming fra kamera til browser via WebRTC

Bruger aiortc til WebRTC peer connection og gphoto2 til frame capture.
Kører på port 8100 (ved siden af technician UI på 8099).

Integration:
- Startes/stoppes fra agent.py når LAB mode aktiveres/deaktiveres
- Signaling via headend REST API (/api/lab/{id}/webrtc-*)
- Fallback til polling hvis WebRTC fejler
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    from av import VideoFrame
    import av
except ImportError as e:
    # Dependencies ikke installeret - log og exit gracefully
    print(f"WebRTC dependencies mangler: {e}")
    print("Installer med: pip install aiortc av")
    raise

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

WEBRTC_PORT = int(os.getenv("TIMELAPSE_WEBRTC_PORT", "8100"))
FRAME_DIR = Path(os.getenv("TIMELAPSE_WEBRTC_FRAME_DIR", tempfile.gettempdir())) / "webrtc_frames"
FRAME_INTERVAL = float(os.getenv("TIMELAPSE_WEBRTC_FRAME_INTERVAL", "0.8"))  # Sekunder mellan frames


# ═══════════════════════════════════════════════════════════════════════════════
# gphoto2 Frame Source
# ═══════════════════════════════════════════════════════════════════════════════

class GPhoto2FrameSource:
    """
    Captures preview frames from gphoto2 camera.
    Uses `gphoto2 --capture-preview` like technician UI MJPEG stream.
    """

    def __init__(self, interval: float = FRAME_INTERVAL):
        self._interval = interval
        self._running = False
        self._frame_path = FRAME_DIR / "preview.jpg"
        self._latest_frame: Optional[bytes] = None
        self._latest_timestamp = 0.0

    async def start(self):
        """Start frame capture loop."""
        if self._running:
            return
        self._running = True
        FRAME_DIR.mkdir(parents=True, exist_ok=True)
        asyncio.create_task(self._capture_loop())
        log.info(f"WebRTC: gphoto2 frame capture started (interval={self._interval}s)")

    async def stop(self):
        """Stop frame capture loop."""
        self._running = False
        log.info("WebRTC: gphoto2 frame capture stopped")

    async def _capture_loop(self):
        """Continuously capture frames from gphoto2."""
        while self._running:
            try:
                # Run gphoto2 capture-preview
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["gphoto2", "--capture-preview", "--filename", str(self._frame_path), "--force-overwrite"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                )

                if result.returncode == 0 and self._frame_path.exists():
                    self._latest_frame = self._frame_path.read_bytes()
                    self._latest_timestamp = asyncio.get_event_loop().time()
                else:
                    log.warning(f"WebRTC: gphoto2 capture failed: {result.stderr}")

            except Exception as e:
                log.error(f"WebRTC: gphoto2 capture error: {e}")

            await asyncio.sleep(self._interval)

    def get_frame(self) -> Optional[bytes]:
        """Get latest captured frame."""
        return self._latest_frame

    def get_timestamp(self) -> float:
        """Get timestamp of latest frame."""
        return self._latest_timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# WebRTC Video Track
# ═══════════════════════════════════════════════════════════════════════════════

class GPhoto2VideoTrack(MediaStreamTrack):
    """
    WebRTC MediaStreamTrack that streams gphoto2 preview frames.
    Converts JPEG frames to VideoFrame for aiortc.
    """

    kind = "video"

    def __init__(self, frame_source: GPhoto2FrameSource):
        super().__init__()
        self._source = frame_source
        self._timestamp = 0

    async def recv(self):
        """Return next video frame."""
        # Wait for new frame
        while True:
            frame_data = self._source.get_frame()
            if frame_data:
                break
            await asyncio.sleep(0.1)

        # Decode JPEG to VideoFrame using PyAV
        # PyAV/aiortc pattern: Decode JPEG packet using mjpeg codec
        packet = av.Packet(frame_data)
        codec = av.CodecContext.create('mjpeg', 'r')
        frames = codec.decode(packet)
        frame = frames[0]  # First frame from decoded packet

        # Set WebRTC timestamp
        frame.pts = self._timestamp
        frame.time_base = "90000Hz"  # RTP standard for video
        self._timestamp += 3000  # ~33ms per frame at 30fps (we run slower)
        return frame


# ═══════════════════════════════════════════════════════════════════════════════
# WebRTC Peer Connection Manager
# ═══════════════════════════════════════════════════════════════════════════════

class WebRTCPeerManager:
    """
    Manages WebRTC peer connection.
    Handles SDP offer/answer and ICE candidates.
    """

    def __init__(self, frame_source: GPhoto2FrameSource):
        self._source = frame_source
        self._pc: Optional[RTCPeerConnection] = None
        self._video_track: Optional[GPhoto2VideoTrack] = None
        self._relay = MediaRelay()
        self._remote_offer: Optional[RTCSessionDescription] = None
        self._local_answer: Optional[RTCSessionDescription] = None

    async def create_connection(self, offer_sdp: str) -> str:
        """
        Create peer connection from remote offer.
        Returns local answer SDP.
        """
        # Clean up existing connection
        await self.close()

        # Create new peer connection
        self._pc = RTCPeerConnection()
        self._video_track = GPhoto2VideoTrack(self._source)

        @self._pc.on("connectionstatechange")
        async def on_connectionstatechange():
            log.info(f"WebRTC: Connection state {self._pc.connectionState}")
            if self._pc.connectionState == "failed":
                await self.close()

        @self._pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            log.info(f"WebRTC: ICE connection state {self._pc.iceConnectionState}")

        # Set remote description (offer)
        self._remote_offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await self._pc.setRemoteDescription(self._remote_offer)

        # Add video track
        self._pc.addTrack(self._video_track)

        # Create answer
        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)
        self._local_answer = self._pc.localDescription

        return self._local_answer.sdp

    async def add_ice_candidate(self, candidate_str: str):
        """Add ICE candidate from remote peer."""
        if not self._pc:
            log.warning("WebRTC: No peer connection to add ICE candidate")
            return

        # Parse ICE candidate and add to peer connection
        from aiortc import ICECandidate
        parts = candidate_str.split(":", 1)
        if len(parts) == 2:
            # Parse candidate format
            candidate = ICECandidate(
                sdpMid=parts[0].strip(),
                sdpMLineIndex=0,
                candidate=parts[1].strip(),
            )
            await self._pc.addIceCandidate(candidate)
            log.debug(f"WebRTC: Added ICE candidate")

    async def close(self):
        """Close peer connection."""
        if self._pc:
            log.info("WebRTC: Closing peer connection")
            await self._pc.close()
            self._pc = None
        self._video_track = None
        self._remote_offer = None
        self._local_answer = None


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI WebRTC Server
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="TimeLapse WebRTC Server", version="1.0.0")
_frame_source: Optional[GPhoto2FrameSource] = None
_peer_manager: Optional[WebRTCPeerManager] = None


@app.on_event("startup")
async def startup():
    """Initialize frame source on startup."""
    global _frame_source
    _frame_source = GPhoto2FrameSource()
    await _frame_source.start()
    log.info(f"WebRTC server starting on port {WEBRTC_PORT}")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    global _frame_source, _peer_manager
    if _peer_manager:
        await _peer_manager.close()
    if _frame_source:
        await _frame_source.stop()
    log.info("WebRTC server stopped")


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "webrtc", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "ok",
        "frame_source_running": _frame_source is not None and _frame_source._running,
        "peer_connected": _peer_manager is not None and _peer_manager._pc is not None,
    }


@app.post("/offer")
async def handle_offer(request: dict):
    """
    Handle WebRTC offer from browser.
    Expects: { "sdp": "..." }
    Returns: { "answer": "..." }
    """
    global _peer_manager

    if not _frame_source:
        raise HTTPException(status_code=503, detail="Frame source not initialized")

    offer_sdp = request.get("sdp")
    if not offer_sdp:
        raise HTTPException(status_code=400, detail="Missing SDP offer")

    try:
        if not _peer_manager:
            _peer_manager = WebRTCPeerManager(_frame_source)

        answer_sdp = await _peer_manager.create_connection(offer_sdp)
        return {"answer": answer_sdp}

    except Exception as e:
        log.error(f"WebRTC: Offer handling error: {e}")
        raise HTTPException(status_code=500, detail=f"Offer handling failed: {e}")


@app.post("/ice")
async def handle_ice(request: dict):
    """
    Handle ICE candidate from browser.
    Expects: { "candidate": "..." }
    """
    global _peer_manager

    if not _peer_manager:
        return {"status": "ignored", "reason": "No active peer connection"}

    candidate = request.get("candidate")
    if not candidate:
        raise HTTPException(status_code=400, detail="Missing ICE candidate")

    try:
        await _peer_manager.add_ice_candidate(candidate)
        return {"status": "ok"}

    except Exception as e:
        log.error(f"WebRTC: ICE candidate error: {e}")
        return {"status": "error", "detail": str(e)}


def run_server():
    """Run WebRTC server (for testing/standalone use)."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBRTC_PORT, log_level="info")


# ── Background server management (for agent.py integration) ────────────────────

_webrtc_thread = None
_webrtc_running = False


def run_webrtc_server(port: int = WEBRTC_PORT) -> bool:
    """
    Start WebRTC server in background thread.
    Returns True if started successfully, False otherwise.
    """
    global _webrtc_thread, _webrtc_running

    if _webrtc_running:
        log.info("WebRTC: Server already running")
        return True

    try:
        import uvicorn
        import threading

        def run_in_thread():
            global _webrtc_running
            _webrtc_running = True
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
            _webrtc_running = False

        _webrtc_thread = threading.Thread(target=run_in_thread, daemon=True, name="webrtc-server")
        _webrtc_thread.start()
        log.info(f"WebRTC: Server started on port {port}")
        return True

    except Exception as e:
        log.error(f"WebRTC: Failed to start server: {e}")
        return False


def stop_webrtc_server() -> None:
    """Stop WebRTC server background thread."""
    global _webrtc_thread, _webrtc_running, _peer_manager, _frame_source

    if not _webrtc_running:
        return

    log.info("WebRTC: Stopping server")

    # Clean up peer connection and frame source
    if _peer_manager:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_peer_manager.close())
            else:
                asyncio.run(_peer_manager.close())
        except Exception as e:
            log.warning(f"WebRTC: Error closing peer manager: {e}")
        _peer_manager = None

    if _frame_source:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_frame_source.stop())
            else:
                asyncio.run(_frame_source.stop())
        except Exception as e:
            log.warning(f"WebRTC: Error stopping frame source: {e}")
        _frame_source = None

    _webrtc_running = False
    _webrtc_thread = None
    log.info("WebRTC: Server stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    run_server()
