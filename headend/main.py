"""
TimeLapse Pro — Headend API
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
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    Capture, Device, Diagnostic, Event,
    create_tables, get_db, now_utc
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("headend")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "TimeLapse Pro Headend",
    description = "Central control API for TimeLapse Pro edge nodes",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],   # tighten in production
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

@app.on_event("startup")
def startup():
    create_tables()
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
    filename:       Optional[str] = None
    sha256:         Optional[str] = None
    captured_at:    Optional[str] = None
    filesize:       Optional[int] = None
    camera_model:   Optional[str] = None
    quality_flag:   Optional[str] = None
    quality_passed: Optional[bool] = None
    blur_score:     Optional[float] = None
    brightness_mean:Optional[float] = None
    uploaded_primary:Optional[bool] = None
    exposure_time:  Optional[str] = None
    aperture:       Optional[str] = None
    iso:            Optional[int] = None

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


# ── Bootstrap ─────────────────────────────────────────────────────────────────

@app.post("/api/bootstrap", response_model=BootstrapResponse)
def bootstrap(req: BootstrapRequest, db: Session = Depends(get_db)):
    """
    Edge node first contact. Validates bootstrap token, creates/updates
    device record, returns API token and config URL.
    """
    # In test phase: accept any token starting with "test-"
    # In production: look up token in a provisioning table
    if not req.bootstrap_token.startswith("test-"):
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")

    # Create or update device
    device = db.query(Device).filter_by(device_id=req.device_id).first()
    if not device:
        device = Device(device_id=req.device_id)
        db.add(device)
        log.info("New device registered: %s", req.device_id)
    else:
        log.info("Device re-bootstrapping: %s", req.device_id)

    # Issue a simple test token (use proper JWT in production)
    api_token = f"tk-{req.device_id}-{now_utc().strftime('%Y%m%d%H%M%S')}"
    device.api_token  = api_token
    device.last_seen  = now_utc()
    device.status     = "online"
    db.commit()

    base_url   = os.environ.get("BASE_URL", "http://192.168.86.132:8000")
    config_url = f"{base_url}/api/config/{req.device_id}"

    return BootstrapResponse(
        api_token  = api_token,
        config_url = config_url,
        device_id  = req.device_id,
    )


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config/{device_id}")
def get_config(device_id: str, db: Session = Depends(get_db)):
    """Return operational config for a device.
    Merges base defaults with per-device overrides from device_config column.
    """
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Opdater last_seen ved config pull — bruges til LAB ready detection
    device.last_seen = now_utc()
    db.commit()

    base_url = os.environ.get("BASE_URL", "http://192.168.86.132:8000")

    cfg = {
        "device": {
            "device_id":     device_id,
            "location_name": device.location_name or "Unknown",
            "tenant_id":     device.tenant_id or "default",
            "headend_url":   base_url + "/api",
            "customer_name": device.customer_name or "",
            "site_name":     device.site_name or "",
            "camera_name":   device.camera_name or "",
        },
        "schedule": {
            "timezone":         "Europe/Copenhagen",
            "capture_mode":     "interval",
            "interval_minutes": 60,
            "active_hours":     ["06:00", "21:00"],
        },
        "camera": {
            "device_id":               device_id,
            "relay_gpio_pin":          356,
            "relay_on_seconds_before": 10,
            "relay_off_seconds_after": 5,
            "relay_simulate":          False,
            "gphoto2_port":            "usb:",
            "delete_after_download":   True,
        },
        "modem": {
            "modem_relay_gpio_pin":        361,
            "modem_power_cycle_off_s":     5,
            "modem_power_cycle_recover_s": 15,
            "modem_cycle_after_failures":  3,
            "modem_min_cycle_interval_s":  600,
        },
        "quality": {
            "check_enabled":    True,
            "blur_threshold":   80,
            "dark_threshold":   25,
            "bright_threshold": 230,
        },
        "storage": {
            "local_path":         "/data/captures",
            "circular_buffer_gb": 50,
            "db_path":            "/data/timelapse_edge.db",
        },
        "location": {
            "gps_lat":   None,
            "gps_lon":   None,
            "gps_alt":   None,
            "gps_source": "manual",  # manual | gpsd
            "address":   None,
        },
        "sftp": {
            "host":        "192.168.86.132",
            "port":        22,
            "username":    "sftp_test",
            "password":    "timelapse123",
            "key_file":    "",
            "remote_base": "/incoming",
        },
        "diagnostics": {
            "heartbeat_interval_minutes": 60,
            "collect": [
                "cpu_temperature", "cpu_load",
                "memory_usage", "disk_usage", "connectivity_type"
            ],
        },
    }

    # Apply per-device overrides from database
    if device.device_config:
        try:
            overrides = json.loads(device.device_config or "{}")
            for section, values in overrides.items():
                if section in cfg and isinstance(cfg[section], dict):
                    cfg[section].update(values)
                else:
                    cfg[section] = values
        except Exception as exc:
            log.warning("Invalid device_config for %s: %s", device_id, exc)

    return cfg


@app.put("/api/admin/devices/{device_id}/config")
def update_device_config(
    device_id: str,
    config: dict,
    db: Session = Depends(get_db),
):
    """Update per-device config overrides.
    Only provided sections are updated — others preserved.
    Example: PUT {"schedule": {"interval_minutes": 10}}
    """
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    existing = {}
    if device.device_config:
        try:
            existing = json.loads(device.device_config or "{}")
        except Exception:
            existing = {}

    for section, values in config.items():
        if section in existing and isinstance(existing[section], dict):
            existing[section].update(values)
        else:
            existing[section] = values

    device.device_config = json.dumps(existing, ensure_ascii=False)
    db.commit()
    log.info("Updated device config for %s: %s", device_id, list(config.keys()))
    return {"status": "ok", "device_id": device_id, "config": existing}


# ── Heartbeat ─────────────────────────────────────────────────────────────────

@app.post("/api/heartbeat/{device_id}")
def heartbeat(
    device_id: str,
    req: HeartbeatRequest,
    db: Session = Depends(get_db),
):
    """Receive periodic heartbeat with diagnostics from edge node."""
    # Update device record
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        device = Device(device_id=device_id)
        db.add(device)
        log.info("Auto-creating device from heartbeat: %s", device_id)

    device.last_seen  = now_utc()
    device.status     = "online"
    if req.ip_address:
        device.ip_address = req.ip_address

    # Store diagnostics
    diag = req.diagnostics
    stats = req.capture_stats
    # Extract camera diagnostics sub-dict
    cam = diag.get("camera", {})
    cam_status = cam.get("camera_status", {})
    cam_config = cam.get("camera_config", {})

    db.add(Diagnostic(
        device_id    = device_id,
        cpu_temp_c   = diag.get("cpu_temperature"),
        cpu_load_pct = diag.get("cpu_load"),
        ram_used_mb  = diag.get("memory_used_mb"),
        disk_used_gb = diag.get("disk_used_gb"),
        battery_v    = diag.get("battery_voltage"),
        solar_v      = diag.get("solar_voltage"),
        connectivity = diag.get("connectivity_type"),
        wifi_ssid    = diag.get("wifi_ssid"),
        uptime_s     = diag.get("uptime_s"),
        capture_total   = stats.get("total"),
        capture_passed  = stats.get("passed"),
        capture_uploaded= stats.get("uploaded"),
        # Extended diagnostics
        ntp_offset_s    = diag.get("ntp_offset_s"),
        ssd_total_gb    = diag.get("ssd_total_gb"),
        ssd_used_pct    = diag.get("ssd_used_pct"),
        ssd_free_gb     = diag.get("ssd_free_gb"),
        service_restarts= diag.get("service_restarts"),
        upload_queue    = diag.get("upload_queue_size"),
        # Camera diagnostics
        cam_battery_pct = cam_status.get("battery_pct"),
        cam_shutter_cnt = cam_status.get("shutter_count"),
        cam_shutter_pct = cam.get("shutter_pct"),
        cam_shutter_alarm = cam.get("shutter_alarm", False),
        cam_available_shots = cam_status.get("available_shots"),
        cam_lens_name   = cam_status.get("lens_name"),
        cam_config_json = json.dumps(cam_config) if cam_config else None,
        cam_drift_json  = json.dumps(cam.get("camera_config_drift", [])),
    ))
    db.commit()

    log.info(
        "Heartbeat: %s | temp=%.1f°C | disk=%.1fGB | connectivity=%s",
        device_id,
        diag.get("cpu_temperature") or 0,
        diag.get("disk_used_gb") or 0,
        diag.get("connectivity_type", "?"),
    )

    return {"status": "ok", "server_time": now_utc().isoformat()}


# ── Captures ──────────────────────────────────────────────────────────────────

@app.post("/api/captures/{device_id}")
def receive_capture(
    device_id: str,
    req: CaptureRequest,
    db: Session = Depends(get_db),
):
    """Receive capture metadata from edge node."""
    # Parse captured_at
    captured_at = None
    if req.captured_at:
        try:
            captured_at = datetime.fromisoformat(req.captured_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    capture = Capture(
        device_id       = device_id,
        filename        = req.filename,
        sha256          = req.sha256,
        captured_at     = captured_at,
        filesize        = req.filesize,
        camera_model    = req.camera_model,
        quality_flag    = req.quality_flag,
        quality_passed  = req.quality_passed,
        blur_score      = req.blur_score,
        brightness_mean = req.brightness_mean,
        uploaded        = req.uploaded_primary or False,
        exposure_time   = req.exposure_time,
        aperture        = req.aperture,
        iso             = req.iso,
    )
    db.add(capture)

    # Update device last_seen
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device:
        device.last_seen = now_utc()
        device.status    = "online"

    db.commit()

    quality = "PASS" if req.quality_passed else "FAIL"
    log.info(
        "Capture: %s | %s | %s | blur=%.1f brightness=%.1f",
        device_id,
        req.filename or "?",
        quality,
        req.blur_score or 0,
        req.brightness_mean or 0,
    )

    return {"status": "ok", "capture_id": capture.id}


# ── Events ────────────────────────────────────────────────────────────────────

@app.post("/api/events/{device_id}")
def receive_event(
    device_id: str,
    req: EventRequest,
    db: Session = Depends(get_db),
):
    """Receive event/log entry from edge node."""
    db.add(Event(
        device_id = device_id,
        level     = req.level,
        category  = req.category,
        message   = req.message,
        extra     = json.dumps(req.extra) if req.extra else None,
    ))
    db.commit()
    return {"status": "ok"}


# ── Reverse SSH ───────────────────────────────────────────────────────────────

@app.post("/api/reverse-ssh/ready")
def reverse_ssh_ready(req: ReverseSshRequest, db: Session = Depends(get_db)):
    """Edge notifies headend that reverse SSH tunnel is ready."""
    log.info(
        "Reverse SSH ready: %s on port %d",
        req.device_id, req.port
    )
    db.add(Event(
        device_id = req.device_id,
        level     = "INFO",
        category  = "system",
        message   = f"Reverse SSH tunnel ready on port {req.port}",
        extra     = json.dumps({"port": req.port}),
    ))
    db.commit()
    return {"status": "ok", "port": req.port}


# ── Admin / status endpoints ──────────────────────────────────────────────────

@app.put("/api/admin/devices/{device_id}/info")
def update_device_info(
    device_id: str,
    info: dict,
    db: Session = Depends(get_db),
):
    """Update device metadata: customer_name, site_name, camera_name, installed_date, installed_time."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    for field in ["customer_name", "site_name", "camera_name", "installed_date", "installed_time", "location_name"]:
        if field in info:
            setattr(device, field, info[field])
    db.commit()
    log.info("Updated device info for %s", device_id)
    return {"status": "ok", "device_id": device_id}


@app.get("/api/admin/devices")
def list_devices(db: Session = Depends(get_db)):
    """List all devices with latest status."""
    devices = db.query(Device).order_by(Device.last_seen.desc()).all()
    result = []
    for d in devices:
        # Check if device is online (seen within last 90 minutes)
        online = False
        if d.last_seen:
            delta = (now_utc() - d.last_seen.replace(tzinfo=timezone.utc)).total_seconds()
            online = delta < 5400  # 90 minutes

        result.append({
            "device_id":      d.device_id,
            "location_name":  d.location_name,
            "tenant_id":      d.tenant_id,
            "ip_address":     d.ip_address,
            "status":         "online" if online else "offline",
            "last_seen":      d.last_seen.isoformat() if d.last_seen else None,
            "first_seen":     d.first_seen.isoformat() if d.first_seen else None,
            "customer_name":  d.customer_name,
            "site_name":      d.site_name,
            "camera_name":    d.camera_name,
            "installed_date": d.installed_date,
            "installed_time": d.installed_time,
        })
    return result


@app.get("/api/admin/devices/{device_id}")
def get_device(device_id: str, db: Session = Depends(get_db)):
    """Get device details with latest diagnostics and captures."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Latest diagnostics
    latest_diag = (
        db.query(Diagnostic)
        .filter_by(device_id=device_id)
        .order_by(Diagnostic.recorded_at.desc())
        .first()
    )

    # Last 200 captures for graphs
    captures = (
        db.query(Capture)
        .filter_by(device_id=device_id)
        .order_by(Capture.captured_at.desc())
        .limit(200)
        .all()
    )

    return {
        "device": {
            "device_id":      device.device_id,
            "location_name":  device.location_name,
            "ip_address":     device.ip_address,
            "last_seen":      device.last_seen.isoformat() if device.last_seen else None,
            "customer_name":  device.customer_name,
            "site_name":      device.site_name,
            "camera_name":    device.camera_name,
            "installed_date": device.installed_date,
            "installed_time": device.installed_time,
            "device_config":  device.device_config,
        },
        "diagnostics": {
            "cpu_temp_c":   latest_diag.cpu_temp_c   if latest_diag else None,
            "ntp_offset_s":  latest_diag.ntp_offset_s  if latest_diag else None,
            "ssd_used_pct":  latest_diag.ssd_used_pct  if latest_diag else None,
            "ssd_free_gb":   latest_diag.ssd_free_gb   if latest_diag else None,
            "service_restarts": latest_diag.service_restarts if latest_diag else None,
            "upload_queue":  latest_diag.upload_queue  if latest_diag else None,
            "cam_battery_pct": latest_diag.cam_battery_pct if latest_diag else None,
            "cam_shutter_cnt": latest_diag.cam_shutter_cnt if latest_diag else None,
            "cam_shutter_pct": latest_diag.cam_shutter_pct if latest_diag else None,
            "cam_shutter_alarm": latest_diag.cam_shutter_alarm if latest_diag else None,
            "cam_lens_name": latest_diag.cam_lens_name if latest_diag else None,
            "cam_config_json": latest_diag.cam_config_json if latest_diag else None,
            "cam_drift_json": latest_diag.cam_drift_json if latest_diag else None,
            "cpu_load_pct": latest_diag.cpu_load_pct if latest_diag else None,
            "disk_used_gb": latest_diag.disk_used_gb if latest_diag else None,
            "connectivity": latest_diag.connectivity if latest_diag else None,
            "wifi_ssid":   latest_diag.wifi_ssid if latest_diag else None,
            "uptime_s":     latest_diag.uptime_s     if latest_diag else None,
        } if latest_diag else None,
        "gps": {
            "lat":    device_cfg.get("location", {}).get("gps_lat"),
            "lon":    device_cfg.get("location", {}).get("gps_lon"),
            "alt":    device_cfg.get("location", {}).get("gps_alt"),
            "source": device_cfg.get("location", {}).get("gps_source", "manual"),
            "address":device_cfg.get("location", {}).get("address"),
        } if (device_cfg := json.loads(device.device_config or "{}")) else None,
        "captures": [
            {
                "id":           c.id,
                "device_id":     c.device_id,
                "filename":      c.filename,
                "captured_at":   c.captured_at.isoformat() if c.captured_at else None,
                "quality_flag":  c.quality_flag,
                "quality_passed":c.quality_passed,
                "blur_score":    round(c.blur_score, 1) if c.blur_score else None,
                "brightness":    round(c.brightness_mean, 1) if c.brightness_mean else None,
                "filesize_mb":   round(c.filesize / 1e6, 1) if c.filesize else None,
                "iso":           c.iso,
                "aperture":      c.aperture,
                "shutter_speed": c.shutter_speed if hasattr(c, 'shutter_speed') else None,
                "focal_length":  c.focal_length if hasattr(c, 'focal_length') else None,
            }
            for c in captures
        ],
    }


@app.get("/api/admin/captures")
def list_captures(
    device_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List recent captures, optionally filtered by device."""
    q = db.query(Capture).order_by(Capture.captured_at.desc())
    if device_id:
        q = q.filter_by(device_id=device_id)
    captures = q.limit(limit).all()
    return [
        {
            "id":            c.id,
            "device_id":     c.device_id,
            "filename":      c.filename,
            "captured_at":   c.captured_at.isoformat() if c.captured_at else None,
            "quality_flag":  c.quality_flag,
            "quality_passed":c.quality_passed,
            "blur_score":    round(c.blur_score, 1) if c.blur_score else None,
            "brightness":    round(c.brightness_mean, 1) if c.brightness_mean else None,
            "filesize_mb":   round(c.filesize / 1e6, 1) if c.filesize else None,
            "uploaded":      c.uploaded,
            "iso":           c.iso,
            "aperture":      c.aperture,
            "shutter_speed": c.shutter_speed if hasattr(c, 'shutter_speed') else None,
        }
        for c in captures
    ]


@app.get("/api/admin/stats")
def stats(db: Session = Depends(get_db)):
    """Overall system statistics."""
    total_devices  = db.query(Device).count()
    total_captures = db.query(Capture).count()
    passed         = db.query(Capture).filter_by(quality_passed=True).count()
    uploaded       = db.query(Capture).filter_by(uploaded=True).count()

    return {
        "total_devices":   total_devices,
        "total_captures":  total_captures,
        "quality_pass_pct": round(100 * passed / total_captures, 1) if total_captures else 0,
        "upload_pct":       round(100 * uploaded / total_captures, 1) if total_captures else 0,
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "time": now_utc().isoformat()}

from pathlib import Path as _Path
from fastapi.responses import FileResponse
from PIL import Image
SFTP_BASE = _Path("/data/sftp/incoming")

import re as _re

def _find_image(device_id: str, filename: str) -> Optional[_Path]:
    """
    Find image in either:
      - New structure:  SFTP_BASE/customer/site/YYYY/MM/DD/filename
      - Old structure:  SFTP_BASE/device_id/filename
    """
    # Try new hierarchical structure first — extract date from filename
    m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
        # Search all customer/site dirs for this date + filename
        date_glob = f"*/*/{yyyy}/{mm}/{dd}/{filename}"
        matches = list(SFTP_BASE.glob(date_glob))
        if matches:
            return matches[0]

    # Fallback: flat structure SFTP_BASE/device_id/filename
    flat = SFTP_BASE / device_id / filename
    if flat.exists():
        return flat

    return None

def _thumbs_dir_for(image_path: _Path) -> _Path:
    """Return .thumbs directory next to the image."""
    return image_path.parent / ".thumbs"

@app.get("/api/images/{device_id}/{filename}")
def get_image(device_id: str, filename: str):
    path = _find_image(device_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path), media_type="image/jpeg")

@app.get("/api/thumbnails/{device_id}/{filename}")
def get_thumbnail(device_id: str, filename: str):
    src = _find_image(device_id, filename)
    if not src:
        raise HTTPException(status_code=404, detail="Image not found")
    thumbs_dir = _thumbs_dir_for(src)
    thumbs_dir.mkdir(exist_ok=True)
    thumb = thumbs_dir / filename
    if not thumb.exists():
        try:
            img = Image.open(src).convert("RGB")
            # Landscape 16:9 thumbnail (320x180)
            img.thumbnail((320, 180), Image.LANCZOS)
            canvas = Image.new("RGB", (320, 180), (15, 15, 15))
            offset = ((320 - img.width) // 2, (180 - img.height) // 2)
            canvas.paste(img, offset)
            canvas.save(str(thumb), "JPEG", quality=78)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return FileResponse(str(thumb), media_type="image/jpeg")


# ── Kamera-laboratorium endpoints ─────────────────────────────────────────────

@app.put("/api/admin/devices/{device_id}/debug")
def set_debug_mode(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Enable or disable debug/lab mode for a device."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    enabled = payload.get("enabled", False)
    # Store in device_config
    existing = json.loads(device.device_config or "{}")
    existing["debug_mode"] = {
        "enabled":           enabled,
        "relay_always_on":   payload.get("relay_always_on", True),
        "config_poll_s":     payload.get("config_poll_s", 1),
        "support_tier":      payload.get("support_tier", "standard"),
    }
    # Nulstil lab_camera_ready når debug mode aktiveres
    if enabled:
        existing["lab_camera_ready"] = False

    device.device_config = json.dumps(existing)
    db.commit()
    log.info("Debug mode %s for %s", "ENABLED" if enabled else "DISABLED", device_id)
    return {"status": "ok", "device_id": device_id, "debug_mode": existing["debug_mode"]}


@app.post("/api/lab/{device_id}/preview")
def request_preview(device_id: str, db: Session = Depends(get_db)):
    """Request a preview capture from the device (no shutter count)."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    # Set a pending_preview flag in device_config
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "preview", "requested_at": now_utc().isoformat()}
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "preview"}


@app.post("/api/lab/{device_id}/capture")
def request_capture(device_id: str, db: Session = Depends(get_db)):
    """Request a full-resolution capture from the device."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "capture", "requested_at": now_utc().isoformat()}
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "capture"}


@app.post("/api/lab/{device_id}/set-param")
def set_camera_param(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Set a camera parameter on the device (queued for next poll)."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    key   = payload.get("key")
    value = payload.get("value")
    if not key or value is None:
        raise HTTPException(status_code=400, detail="key and value required")
    existing = json.loads(device.device_config or "{}")
    pending  = existing.get("pending_params", [])
    # Remove existing entry for same key
    pending  = [p for p in pending if p["key"] != key]
    pending.append({"key": key, "value": str(value)})
    existing["pending_params"] = pending
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "key": key, "value": value}


# ── Backup ────────────────────────────────────────────────────────────────────

import subprocess as _subprocess
import threading as _threading
import tempfile as _tempfile
import shutil as _shutil
from fastapi.responses import FileResponse as _FileResponse

_backup_status = {"running": False, "progress": [], "file": None, "error": None}

def _run_backup():
    """Kør backup i baggrunden."""
    global _backup_status
    _backup_status = {"running": True, "progress": [], "file": None, "error": None}
    try:
        import datetime, os, json, sqlite3 as _sqlite3
        date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = f"/tmp/timelapse-backup-headend-{date}"
        os.makedirs(f"{backup_dir}/database", exist_ok=True)
        os.makedirs(f"{backup_dir}/configs", exist_ok=True)
        os.makedirs(f"{backup_dir}/logs", exist_ok=True)

        _backup_status["progress"].append("Database backup...")
        db_src = "/home/peter/headend/timelapse_headend.db"
        if os.path.exists(db_src):
            _shutil.copy2(db_src, f"{backup_dir}/database/timelapse_headend.db")
            conn = _sqlite3.connect(db_src)
            with open(f"{backup_dir}/database/timelapse_headend_dump.sql", "w") as f:
                for line in conn.iterdump():
                    f.write(line + "\n")
            conn.close()
            _backup_status["progress"].append("Database OK")

        _backup_status["progress"].append("Config backup...")
        for f in ["timelapse-headend.service", "timelapse-deploy.service", "timelapse-deploy.timer"]:
            src = f"/etc/systemd/system/{f}"
            if os.path.exists(src):
                _shutil.copy2(src, f"{backup_dir}/configs/{f}")
        for f in ["timelapse-deploy", "timelapse-headend"]:
            src = f"/etc/sudoers.d/{f}"
            if os.path.exists(src):
                _shutil.copy2(src, f"{backup_dir}/configs/sudoers-{f}")
        poller = "/home/peter/timelapse-pro/deploy/headend_poller.sh"
        if os.path.exists(poller):
            _shutil.copy2(poller, f"{backup_dir}/configs/headend_poller.sh")
        _backup_status["progress"].append("Config OK")

        _backup_status["progress"].append("System info...")
        import platform
        with open(f"{backup_dir}/SYSTEMINFO.txt", "w") as f:
            f.write(f"TimeLapse Pro — Headend Backup\nDato: {date}\n")
            f.write(f"OS: {platform.platform()}\n")
        _backup_status["progress"].append("System info OK")

        _backup_status["progress"].append("Pakker backup...")
        archive = f"/tmp/timelapse-backup-headend-{date}.tar.gz"
        _subprocess.run(["tar", "czf", archive, "-C", "/tmp", f"timelapse-backup-headend-{date}"],
                       check=True, capture_output=True)
        _shutil.rmtree(backup_dir, ignore_errors=True)

        # Kopier til NAS hvis konfigureret
        nas_path = _get_nas_path()
        if nas_path and os.path.isdir(nas_path):
            _shutil.copy2(archive, nas_path)
            _backup_status["progress"].append(f"Kopieret til NAS: {nas_path}")

        _backup_status["file"] = archive
        _backup_status["running"] = False
        _backup_status["progress"].append(f"✅ Backup komplet: {os.path.getsize(archive)//1024} KB")
        log.info("Backup komplet: %s", archive)
    except Exception as e:
        _backup_status["error"] = str(e)
        _backup_status["running"] = False
        _backup_status["progress"].append(f"❌ Fejl: {e}")
        log.error("Backup fejl: %s", e)

def _get_nas_path():
    """Hent NAS sti fra settings i DB."""
    try:
        from sqlalchemy import text
        from database import SessionLocal
        db = SessionLocal()
        result = db.execute(text("SELECT value FROM settings WHERE key='backup_nas_path'")).fetchone()
        db.close()
        return result[0] if result else None
    except:
        return None

@app.post("/api/admin/backup/trigger")
def trigger_backup():
    """Start backup i baggrunden."""
    global _backup_status
    if _backup_status.get("running"):
        return {"status": "already_running", "progress": _backup_status["progress"]}
    _backup_status = {"running": True, "progress": ["Starter backup..."], "file": None, "error": None}
    t = _threading.Thread(target=_run_backup, daemon=True)
    t.start()
    return {"status": "started"}

@app.get("/api/admin/backup/status")
def backup_status():
    """Hent backup status."""
    return {
        "running": _backup_status.get("running", False),
        "progress": _backup_status.get("progress", []),
        "ready": _backup_status.get("file") is not None,
        "error": _backup_status.get("error"),
        "filename": os.path.basename(_backup_status["file"]) if _backup_status.get("file") else None,
    }

@app.get("/api/admin/backup/download")
def download_backup():
    """Download seneste backup fil."""
    import os
    f = _backup_status.get("file")
    if not f or not os.path.exists(f):
        raise HTTPException(status_code=404, detail="Ingen backup klar — kør trigger først")
    return _FileResponse(
        path=f,
        filename=os.path.basename(f),
        media_type="application/gzip"
    )

@app.put("/api/admin/backup/settings")
def update_backup_settings(payload: dict, db: Session = Depends(get_db)):
    """Gem backup indstillinger (NAS sti, auto-backup interval)."""
    try:
        from sqlalchemy import text
        for key, value in payload.items():
            if key in ["backup_nas_path", "backup_auto_interval", "backup_include_images"]:
                db.execute(text(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (:k, :v)"
                ), {"k": key, "v": str(value)})
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/backup/settings")
def get_backup_settings(db: Session = Depends(get_db)):
    """Hent backup indstillinger."""
    try:
        from sqlalchemy import text
        keys = ["backup_nas_path", "backup_auto_interval", "backup_include_images"]
        result = {}
        for k in keys:
            row = db.execute(text("SELECT value FROM settings WHERE key=:k"), {"k": k}).fetchone()
            result[k] = row[0] if row else None
        return result
    except:
        return {"backup_nas_path": None, "backup_auto_interval": "manual", "backup_include_images": "false"}


@app.post("/api/admin/backup/trigger-edge/{device_id}")
def trigger_edge_backup(device_id: str, db: Session = Depends(get_db)):
    """Anmod edge enhed om at lave backup."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["backup_requested"] = True
    existing["backup_requested_at"] = now_utc().isoformat()
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "message": f"Backup anmodet for {device_id}"}


@app.post("/api/lab/{device_id}/params")
def lab_store_params(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Edge poster live kamera-parametre til headend efter get_params kommando."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["camera_params"] = payload.get("params", [])
    existing.pop("lab_command", None)
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("LAB params stored for %s: %d params", device_id, len(existing["camera_params"]))
    return {"status": "ok"}


@app.post("/api/lab/{device_id}/get-params")
def lab_get_params(device_id: str, db: Session = Depends(get_db)):
    """Queue get-params kommando til edge."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "get_params"}
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("LAB get-params queued for %s", device_id)
    return {"status": "ok"}


@app.get("/api/lab/{device_id}/previews")
def list_previews(device_id: str, limit: int = 20):
    """List recent preview images for a device."""
    import re as _re
    preview_dir = SFTP_BASE / "_lab" / device_id
    if not preview_dir.exists():
        return []
    files = sorted(preview_dir.glob("preview_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files[:limit]:
        result.append({
            "filename":   f.name,
            "size_kb":    f.stat().st_size // 1024,
            "url":        f"/api/lab/{device_id}/preview-image/{f.name}",
            "thumb_url":  f"/api/lab/{device_id}/preview-thumb/{f.name}",
        })
    return result


@app.get("/api/lab/{device_id}/preview-image/{filename}")
def get_preview_image(device_id: str, filename: str):
    """Serve a preview image."""
    path = SFTP_BASE / "_lab" / device_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(str(path), media_type="image/jpeg")


@app.get("/api/lab/{device_id}/preview-thumb/{filename}")
def get_preview_thumb(device_id: str, filename: str):
    """Serve a thumbnail of a preview image."""
    src = SFTP_BASE / "_lab" / device_id / filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    thumbs_dir = SFTP_BASE / "_lab" / device_id / ".thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    thumb = thumbs_dir / filename
    if not thumb.exists():
        img = Image.open(src)
        img.thumbnail((400, 400), Image.LANCZOS)
        img.save(str(thumb), "JPEG", quality=75)
    return FileResponse(str(thumb), media_type="image/jpeg")

@app.post("/api/admin/devices/{device_id}/lab-clear-command")
def lab_clear_command(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    cfg = json.loads(device.device_config or "{}")
    cfg.pop("lab_command", None)
    device.device_config = json.dumps(cfg)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/devices/{device_id}/lab-clear-params")
def lab_clear_params(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    cfg = json.loads(device.device_config or "{}")
    cfg.pop("pending_params", None)
    device.device_config = json.dumps(cfg)
    db.commit()
    return {"status": "ok"}


@app.post("/api/lab/{device_id}/camera-ready")
def lab_camera_ready(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Edge melder at kameraet er forbundet og klar i LAB mode."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["lab_camera_ready"] = payload.get("ready", False)
    device.device_config = json.dumps(existing)
    device.last_seen = now_utc()
    db.commit()
    log.info("LAB camera ready: %s", device_id)
    return {"status": "ok"}

# ── WiFi konfiguration endpoints ─────────────────────────────────────────────

@app.post("/api/lab/{device_id}/wifi/scan")
def wifi_scan(device_id: str, db: Session = Depends(get_db)):
    """Request WiFi scan from device."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "wifi_scan", "requested_at": now_utc().isoformat()}
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "wifi_scan"}

@app.post("/api/lab/{device_id}/wifi/connect")
def wifi_connect(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Request WiFi connection on device."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    ssid     = payload.get("ssid", "")
    password = payload.get("password", "")
    if not ssid: raise HTTPException(status_code=400, detail="ssid required")
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {
        "type": "wifi_connect",
        "ssid": ssid,
        "password": password,
        "requested_at": now_utc().isoformat()
    }
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "wifi_connect", "ssid": ssid}

@app.post("/api/lab/{device_id}/wifi/forget")
def wifi_forget(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Request removal of saved WiFi network."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    ssid = payload.get("ssid", "")
    if not ssid: raise HTTPException(status_code=400, detail="ssid required")
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {
        "type": "wifi_forget",
        "ssid": ssid,
        "requested_at": now_utc().isoformat()
    }
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "wifi_forget", "ssid": ssid}

@app.post("/api/lab/{device_id}/wifi/result")
def wifi_result(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Receive WiFi operation result from edge agent."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["wifi_data"] = payload
    existing.pop("lab_command", None)
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok"}

@app.get("/api/admin/captures/timeline")
def captures_timeline(
    device_id: str,
    year:  Optional[int] = None,
    month: Optional[int] = None,
    day:   Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Hent captures til timeline navigation.
    - Uden parametre: returner antal captures per dag (alle tider)
    - Med year+month+day: returner alle captures den dag
    """
    q = db.query(Capture).filter(
        Capture.device_id == device_id,
        Capture.captured_at.isnot(None)
    )

    if year and month and day:
        # Hent alle captures på en specifik dag
        from datetime import date
        d_start = f"{year:04d}-{month:02d}-{day:02d} 00:00:00"
        d_end   = f"{year:04d}-{month:02d}-{day:02d} 23:59:59"
        captures = q.filter(
            Capture.captured_at >= d_start,
            Capture.captured_at <= d_end
        ).order_by(Capture.captured_at.asc()).all()
        return [
            {
                "id":           c.id,
                "device_id":    c.device_id,
                "filename":     c.filename,
                "captured_at":  c.captured_at.isoformat() if c.captured_at else None,
                "quality_flag": c.quality_flag,
                "quality_passed": c.quality_passed,
                "blur_score":   round(c.blur_score, 1) if c.blur_score else None,
                "brightness":   round(c.brightness_mean, 1) if c.brightness_mean else None,
                "filesize_mb":  round(c.filesize / 1e6, 1) if c.filesize else None,
                "uploaded":     c.uploaded,
            }
            for c in captures
        ]
    else:
        # Returner daglig tæller for hele historikken
        from sqlalchemy import func
        rows = db.query(
            func.strftime("%Y", Capture.captured_at).label("year"),
            func.strftime("%m", Capture.captured_at).label("month"),
            func.strftime("%d", Capture.captured_at).label("day"),
            func.count(Capture.id).label("count")
        ).filter(
            Capture.device_id == device_id,
            Capture.captured_at.isnot(None)
        ).group_by("year", "month", "day").order_by("year", "month", "day").all()
        return [
            {"year": int(r.year), "month": int(r.month), "day": int(r.day), "count": r.count}
            for r in rows
        ]
