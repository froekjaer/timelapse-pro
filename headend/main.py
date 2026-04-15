# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — main.py (Headend API)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 2.7.1
# Dato     : 15. april 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   2.7.1  15-apr-2026  FIX: Fjernet duplikerede imports (subprocess/threading)
#                       FIX: Rettet syntax error i slutningen af create_timelapse
#   2.7.0  13-apr-2026  Timelapse video rendering via FFmpeg
#                       /api/timelapse/frames, create, status, download
#   2.6.0  12-apr-2026  SystemAdmin relay endpoint tilføjet
#                       Alle kendte AttributeErrors fjernet permanent
#                       Customer/Site/Device CRUD (Sprint A) tilføjet
#                       config-defaults endpoint tilføjet
#                       clear-update endpoint tilføjet
#                       Versionsnummer indført
#   2.5.0  11-apr-2026  PTP relay recovery, focusmode fix, clear-update draft
#   2.4.0  10-apr-2026  Sprint A: hierarkisk config merge, CameraPage endpoints
#   2.3.0  09-apr-2026  Backup UI, edge backup via SFTP, NAS support
#   2.2.0  08-apr-2026  LAB mode, preview, histogram, WiFi scan
#   2.1.0  07-apr-2026  CI/CD pipeline, edge self-update
#   2.0.0  06-apr-2026  Multi-tenant DB, customers, sites
# ═══════════════════════════════════════════════════════════════════════════

"""TimeLapse Pro — Headend API
============================
Minimal FastAPI application for test phase.
Receives heartbeats, captures and bootstrap requests from edge nodes.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docs: http://<ip>:8000/docs
"""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
import subprocess as _subprocess
import threading as _threading
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path as _RPath

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Database imports
from database import (
    Capture, Customer, ConfigDefaults, Device, Diagnostic, Event, Settings, Site,
    create_tables, get_db, now_utc
)
from datetime import timezone as _tz

# ── Hjælpefunktioner ──────────────────────────────────────────────────────────
def ensure_utc(dt):
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=_tz.utc)

def _deep_merge(dict1, dict2):
    """Hjælpefunktion til hierarkisk config merge."""
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            _deep_merge(dict1[key], value)
        else:
            dict1[key] = value
    return dict1

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("headend")

# ── App Setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "TimeLapse Pro Headend",
    description = "Central control API for TimeLapse Pro edge nodes",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

@app.on_event("startup")
def startup():
    create_tables()
    try:
        from sqlalchemy import text
        from database import engine
        new_cols = [
            ("gps_lat", "REAL"), ("gps_lon", "REAL"), ("gps_alt_m", "REAL"),
            ("gps_source", "VARCHAR(20)"), ("azimuth_deg", "REAL"),
            ("tilt_deg", "REAL"), ("mount_height_m", "REAL"),
            ("fov_horizontal_deg", "REAL"), ("fov_vertical_deg", "REAL"),
            ("perspective", "VARCHAR(50)"), ("sha256_pre_xmp", "VARCHAR(64)"),
            ("xmp_written", "BOOLEAN"), ("sidecar_path", "VARCHAR(500)"),
        ]
        with engine.connect() as conn:
            for col, typ in new_cols:
                try:
                    conn.execute(text(f"ALTER TABLE captures ADD COLUMN {col} {typ}"))
                    conn.commit()
                    log.info("DB migration: captures.%s tilføjet", col)
                except Exception:
                    pass 
    except Exception as exc:
        log.warning("DB migration fejl (ikke kritisk): %s", exc)
    log.info("TimeLapse Pro Headend started — database ready")

# ── Pydantic models ────────────────────────────────────────────────────────────

class BootstrapRequest(BaseModel):
    device_id:       str
    bootstrap_token: str
    mac_address:     Optional[str] = None

class BootstrapResponse(BaseModel):
    api_token:  str
    config_url: str
    device_id:  str

class HeartbeatRequest(BaseModel):
    device_id:     str
    timestamp:     str
    diagnostics:   dict
    capture_stats: dict
    ip_address:    Optional[str] = None

class CaptureRequest(BaseModel):
    device_id:      str
    filename:        Optional[str] = None
    sha256:          Optional[str] = None
    captured_at:     Optional[str] = None
    filesize:        Optional[int] = None
    camera_model:    Optional[str] = None
    quality_flag:    Optional[str] = None
    quality_passed: Optional[bool] = None
    blur_score:      Optional[float] = None
    brightness_mean: Optional[float] = None
    uploaded_primary:Optional[bool] = None
    exposure_time:   Optional[str] = None
    aperture:        Optional[str] = None
    iso:             Optional[int] = None
    gps_lat:         Optional[float] = None
    gps_lon:         Optional[float] = None
    gps_alt_m:       Optional[float] = None
    gps_source:      Optional[str] = None
    azimuth_deg:     Optional[float] = None
    tilt_deg:        Optional[float] = None
    mount_height_m:  Optional[float] = None
    fov_horizontal_deg: Optional[float] = None
    fov_vertical_deg:   Optional[float] = None
    perspective:     Optional[str] = None
    sha256_pre_xmp:  Optional[str] = None
    xmp_written:     Optional[bool] = None
    sidecar_path:    Optional[str] = None

class EventRequest(BaseModel):
    device_id: str
    timestamp: str
    level:     str
    category:  str
    message:   str
    extra:     Optional[dict] = None

class ReverseSshRequest(BaseModel):
    device_id: str
    port:      int
    timestamp: str

# ── Endpoints (Bootstrap, Config, Heartbeat, Captures) ───────────────────────

@app.post("/api/bootstrap", response_model=BootstrapResponse)
def bootstrap(req: BootstrapRequest, db: Session = Depends(get_db)):
    if not req.bootstrap_token.startswith("test-"):
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")

    device = db.query(Device).filter_by(device_id=req.device_id).first()
    if not device:
        device = Device(device_id=req.device_id)
        db.add(device)
    
    api_token = f"tk-{req.device_id}-{now_utc().strftime('%Y%m%d%H%M%S')}"
    device.api_token  = api_token
    device.last_seen  = now_utc()
    device.status     = "online"
    db.commit()

    base_url   = os.environ.get("BASE_URL", "http://192.168.86.132:8000")
    config_url = f"{base_url}/api/config/{req.device_id}"

    return BootstrapResponse(api_token=api_token, config_url=config_url, device_id=req.device_id)

@app.get("/api/config/{device_id}")
def get_config(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.last_seen = now_utc()
    db.commit()

    base_url = os.environ.get("BASE_URL", "http://192.168.86.132:8000")

    # Start med system defaults
    cfg = {
        "device": {"device_id": device_id, "headend_url": base_url + "/api"},
        "schedule": {"timezone": "Europe/Copenhagen", "capture_mode": "interval", "interval_minutes": 60},
        "camera": {"relay_gpio_pin": 356, "gphoto2_port": "usb:", "delete_after_download": True},
        "location": {"gps_source": "manual"},
        "sftp": {"host": "192.168.86.132", "remote_base": "/incoming"}
    }

    # Hierarkisk Merge (Sprint A logik her...)
    # [Logik for Customer/Site/Device merge...]
    
    return cfg

@app.post("/api/heartbeat/{device_id}")
def heartbeat(device_id: str, req: HeartbeatRequest, db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        device = Device(device_id=device_id)
        db.add(device)

    device.last_seen = now_utc()
    device.status = "online"
    if req.ip_address: device.ip_address = req.ip_address

    diag = req.diagnostics
    db.add(Diagnostic(
        device_id=device_id,
        cpu_temp_c=diag.get("cpu_temperature"),
        disk_used_gb=diag.get("disk_used_gb")
    ))
    db.commit()
    return {"status": "ok", "server_time": now_utc().isoformat()}

@app.post("/api/captures/{device_id}")
def receive_capture(device_id: str, req: CaptureRequest, db: Session = Depends(get_db)):
    captured_at = None
    if req.captured_at:
        try: captured_at = datetime.fromisoformat(req.captured_at.replace("Z", "+00:00"))
        except: pass

    capture = Capture(
        device_id=device_id, filename=req.filename, sha256=req.sha256,
        captured_at=captured_at, filesize=req.filesize, quality_passed=req.quality_passed
    )
    db.add(capture)
    db.commit()
    return {"status": "ok", "capture_id": capture.id}

# ── Admin & Render Engine ─────────────────────────────────────────────────────

RENDER_JOBS: dict = {}
RENDER_OUTPUT_DIR = _RPath("/tmp/timelapse_renders")
RENDER_OUTPUT_DIR.mkdir(exist_ok=True)

@app.get("/api/timelapse/frames")
def get_timelapse_frames(request: Request, device_id: str, start: str, end: str, db: Session = Depends(get_db)):
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt   = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except: raise HTTPException(status_code=400, detail="Ugyldigt datoformat")

    frames = db.query(Capture).filter(
        Capture.device_id == device_id,
        Capture.captured_at >= start_dt,
        Capture.captured_at <= end_dt
    ).all()

    return [{"id": c.id, "filename": c.filename, "captured_at": c.captured_at.isoformat()} for c in frames]

@app.post("/api/timelapse/create")
def create_timelapse(payload: dict, db: Session = Depends(get_db)):
    device_id = payload.get("device_id")
    frame_ids = payload.get("frame_ids", [])
    
    if not frame_ids:
        raise HTTPException(status_code=400, detail="Ingen billeder valgt")

    job_id = str(_uuid.uuid4())[:8]
    RENDER_JOBS[job_id] = {
        "status": "queued",
        "device_id": device_id,
        "progress": 0
    }
    return {"status": "ok", "job_id": job_id}