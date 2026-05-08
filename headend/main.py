# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — main.py (Headend API)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 3.0.0
# Dato     : 13. april 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   3.0.0  06-maj-2026  Sprint C: RBAC, JWT auth, User CRUD,
#                       Camera/Pi-kobling, SSH tunnel, Opdateringsstyring
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
#import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datetime import timezone as _tz

#Peter:
import re as _re
from sqlalchemy import text
import subprocess as _subprocess
import threading as _threading
import json as _json
import os, tempfile
# ── Auth imports (Sprint C) ───────────────────────────────────────────────
from jose import JWTError, jwt as _jwt
import bcrypt as _bcrypt_lib
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Security
import secrets as _secrets

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

JWT_SECRET    = os.getenv("JWT_SECRET", _secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 12   # access token levetid




def ensure_utc(dt):
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=_tz.utc)

from database import (
    BootstrapToken,
    Capture, Camera, Customer, ConfigDefaults, Device, DeviceAssignment,
    Diagnostic, Event, PendingUpdate, Settings, Site, SshTunnelLog, User,
    create_tables, get_db, now_utc
)
import uuid as _uuid

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
    # DB migration — tilføj nye kolonner hvis de mangler
    try:
#Peter        from sqlalchemy import text
        engine = next(iter([].__class__.mro())) if False else __import__('database').engine
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
                    pass  # Kolonnen findes allerede
    except Exception as exc:
        log.warning("DB migration fejl (ikke kritisk): %s", exc)

        # Sprint C: MFA + SFTP isolation kolonner (migration)
        new_cols_v3 = [
            # customers
            ("customers", "mfa_required",        "BOOLEAN DEFAULT 0"),
            ("customers", "mfa_method",           "VARCHAR(50) DEFAULT 'none'"),
            ("customers", "mfa_documented_at",    "DATETIME"),
            ("customers", "mfa_documented_by",    "VARCHAR(100)"),
            ("customers", "data_classification",  "VARCHAR(30) DEFAULT 'internal'"),
            # sites
            ("sites", "sftp_user",                "VARCHAR(100)"),
            ("sites", "sftp_chroot_verified",     "BOOLEAN DEFAULT 0"),
            ("sites", "sftp_chroot_verified_at",  "DATETIME"),
            ("sites", "mfa_required",             "BOOLEAN DEFAULT 0"),
            ("sites", "mfa_method",               "VARCHAR(50) DEFAULT 'none'"),
            ("sites", "mfa_documented_at",        "DATETIME"),
            ("sites", "mfa_documented_by",        "VARCHAR(100)"),
            ("sites", "data_classification",      "VARCHAR(30) DEFAULT 'internal'"),
        ]
        with engine.connect() as conn:
            for table, col, typ in new_cols_v3:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                    conn.commit()
                    log.info("DB migration: %s.%s tilføjet", table, col)
                except Exception:
                    pass  # Kolonnen findes allerede

    log.info("TimeLapse Pro Headend started — database ready")


# ── Pydantic models ────────────────────────────────────────────────────────────

def _get_setting(db: Session, key: str, default: str = "") -> str:
    """Hent en setting fra databasen."""
    try:
        row = db.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": key}).fetchone()
        return row[0] if row else default
    except Exception:
        return default


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
    # Lokation og orientering
    gps_lat:             Optional[float] = None
    gps_lon:             Optional[float] = None
    gps_alt_m:           Optional[float] = None
    gps_source:          Optional[str] = None
    azimuth_deg:         Optional[float] = None
    tilt_deg:            Optional[float] = None
    mount_height_m:      Optional[float] = None
    fov_horizontal_deg:  Optional[float] = None
    fov_vertical_deg:    Optional[float] = None
    perspective:         Optional[str] = None
    # Integritet
    sha256_pre_xmp:      Optional[str] = None
    xmp_written:         Optional[bool] = None
    sidecar_path:        Optional[str] = None

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

# ═══════════════════════════════════════════════════════════════════════════
# ── AUTH / RBAC ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

def _hash_password(pw: str) -> str:
    return _bcrypt_lib.hashpw(pw.encode(), _bcrypt_lib.gensalt()).decode()

def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def _create_token(data: dict, expire_hours: int = JWT_EXPIRE_H) -> str:
    from datetime import timedelta
    payload = data.copy()
    payload["exp"] = now_utc() + timedelta(hours=expire_hours)
    return _jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(token: str) -> dict | None:
    try:
        return _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

def _ensure_super_admin(db):
    """Opretter standard super_admin hvis ingen brugere findes."""
    from database import User
    if db.query(User).count() == 0:
        admin = User(
            username      = "admin",
            email         = "admin@timelapse.local",
            password_hash = _hash_password("changeme"),
            role          = "super_admin",
            is_active     = True,
        )
        db.add(admin)
        db.commit()
        log.warning("Standard super_admin oprettet — SKIFT PASSWORD STRAKS via /api/auth/change-password")

def get_current_user(
    token: str = Security(_oauth2_scheme),
    db: Session = Depends(get_db)
):
    """FastAPI dependency — returnerer current user eller None."""
    if not token:
        return None
    payload = _decode_token(token)
    if not payload:
        return None
    from database import User
    user = db.query(User).filter_by(username=payload.get("sub"), is_active=True).first()
    return user

# Rollehierarki — højere roller inkluderer lavere rollers rettigheder
_ROLE_HIERARCHY = {
    "super_admin": {"super_admin", "admin", "operator", "viewer"},
    "admin":       {"admin", "operator", "viewer"},
    "operator":    {"operator", "viewer"},
    "viewer":      {"viewer"},
}

def require_role(*roles: str):
    """FastAPI dependency factory — kræver en af de angivne roller.
    Rollehierarki: super_admin > admin > operator > viewer.
    """
    def _check(user=Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        return user
    return Depends(_check)


# ── Auth models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class UserCreateRequest(BaseModel):
    username:    str
    email:       Optional[str] = None
    password:    str
    role:        str = "viewer"
    customer_id: Optional[str] = None

class UserUpdateRequest(BaseModel):
    email:       Optional[str] = None
    role:        Optional[str] = None
    customer_id: Optional[str] = None
    is_active:   Optional[bool] = None


# ── Auth endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup_ensure_admin():
    """Ensure super_admin exists on startup."""
    db = next(get_db())
    try:
        _ensure_super_admin(db)
    finally:
        db.close()

@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login — returnerer JWT access token."""
    from database import User
    user = db.query(User).filter_by(username=req.username, is_active=True).first()
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Forkert brugernavn eller adgangskode")
    user.last_login = now_utc()
    db.commit()
    token = _create_token({"sub": user.username, "role": user.role, "cid": user.customer_id})
    log.info("Login: %s (%s)", user.username, user.role)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role,
        "username":     user.username,
        "expires_in":   JWT_EXPIRE_H * 3600,
    }

@app.post("/api/auth/logout")
def logout():
    """Logout — klienten sletter token lokalt."""
    return {"ok": True}

@app.post("/api/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Skift adgangskode for den indloggede bruger."""
    if current_user is None:
        raise HTTPException(status_code=401)
    if not _verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Forkert nuværende adgangskode")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Adgangskode skal være mindst 8 tegn")
    current_user.password_hash = _hash_password(req.new_password)
    db.commit()
    log.info("Adgangskode skiftet: %s", current_user.username)
    return {"ok": True}

@app.get("/api/auth/me")
def me(current_user=Depends(get_current_user)):
    """Returnerer den aktuelle brugers info."""
    if current_user is None:
        raise HTTPException(status_code=401)
    return {
        "username":    current_user.username,
        "email":       current_user.email,
        "role":        current_user.role,
        "customer_id": current_user.customer_id,
    }


# ── User CRUD (kun super_admin) ───────────────────────────────────────────

@app.get("/api/admin/users")
def list_users(
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    users = db.query(User).order_by(User.username).all()
    return [
        {
            "id":          u.id,
            "username":    u.username,
            "email":       u.email,
            "role":        u.role,
            "customer_id": u.customer_id,
            "is_active":   u.is_active,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "last_login":  u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]

@app.post("/api/admin/users")
def create_user(
    req: UserCreateRequest,
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    if db.query(User).filter_by(username=req.username).first():
        raise HTTPException(status_code=400, detail="Brugernavn findes allerede")
    if req.role not in ("super_admin", "admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Ugyldig rolle")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Adgangskode skal være mindst 8 tegn")
    u = User(
        username      = req.username,
        email         = req.email,
        password_hash = _hash_password(req.password),
        role          = req.role,
        customer_id   = req.customer_id,
    )
    db.add(u); db.commit(); db.refresh(u)
    log.info("Bruger oprettet: %s (%s)", u.username, u.role)
    return {"id": u.id, "username": u.username}

@app.put("/api/admin/users/{user_id}")
def update_user(
    user_id: int,
    req: UserUpdateRequest,
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if req.role and req.role not in ("super_admin", "admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Ugyldig rolle")
    for field in ["email", "role", "customer_id", "is_active"]:
        val = getattr(req, field)
        if val is not None:
            setattr(u, field, val)
    db.commit()
    return {"ok": True}

@app.delete("/api/admin/users/{user_id}")
def delete_user(
    user_id: int,
    current_user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if u.username == "admin" and u.role == "super_admin":
        raise HTTPException(status_code=400, detail="Kan ikke slette primær super_admin")
    db.delete(u); db.commit()
    return {"ok": True}




# ── Bootstrap ─────────────────────────────────────────────────────────────────

@app.post("/api/bootstrap", response_model=BootstrapResponse)
def bootstrap(req: BootstrapRequest, db: Session = Depends(get_db)):
    """
    Edge node first contact. Validates bootstrap token, creates/updates
    device record, returns API token and config URL.
    """
    # In test phase: accept any token starting with "test-"
    # In production: look up token in a provisioning table
    # Valider bootstrap token — tjek DB eller accepter "test-" prefix i DEV
    token_record = db.query(BootstrapToken).filter_by(
        token=req.bootstrap_token, revoked=False
    ).first()
    if token_record:
        # Produktions-token fra DB
        if token_record.expires_at and now_utc() > token_record.expires_at.replace(tzinfo=_tz.utc):
            raise HTTPException(status_code=401, detail="Bootstrap token udløbet")
        if token_record.used_at:
            raise HTTPException(status_code=401, detail="Bootstrap token allerede brugt")
        # Marker som brugt
        token_record.used_at = now_utc()
        token_record.used_by_device = req.device_id
    elif req.bootstrap_token.startswith("test-"):
        pass  # DEV-mode: accepter test- prefix
    else:
        raise HTTPException(status_code=401, detail="Ugyldigt eller ukendt bootstrap token")

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



# ── API Token auth ───────────────────────────────────────────────────────────




def _verify_device_token(
    device_id: str,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    """Validér per-device Bearer token på edge-vendte endpoints."""
    scheme, _, provided = authorization.partition(" ")
    if scheme.lower() != "bearer" or not provided:
        raise HTTPException(status_code=401, detail="Manglende Bearer token")
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device or not device.api_token:
        raise HTTPException(status_code=401, detail="Ukendt device eller token ikke sat")
    if provided != device.api_token:
        raise HTTPException(status_code=401, detail="Ugyldig API token for dette device")

# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config/{device_id}")
def get_config(device_id: str, _auth: None = Depends(_verify_device_token), db: Session = Depends(get_db)):
    """Return operational config for a device.
    Merges base defaults with per-device overrides from device_config column.
    """
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Opdater last_seen ved config pull — bruges til LAB ready detection
    device.last_seen = now_utc()
    db.commit()

    base_url = _get_setting(db, "base_url", os.environ.get("BASE_URL", "http://192.168.86.102:8000"))

    cfg = {
        "device": {
            "device_id":     device_id,
            "location_name": device.location_name or (f"{device.customer_name} — {device.site_name} — {device.camera_name}" if device.customer_name and device.site_name else "Unknown"),
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
            "host":        _get_setting(db, "sftp_host", os.getenv("SFTP_HOST", "")),
            "port":        int(_get_setting(db, "sftp_port", os.getenv("SFTP_PORT", "22"))),
            "username":    _get_setting(db, "sftp_user", os.getenv("SFTP_USER", "")),
            "password":    _get_setting(db, "sftp_password", os.getenv("SFTP_PASSWORD", "")),
            "key_file":    "",
            "remote_base": _get_setting(db, "sftp_remote_base", os.getenv("SFTP_REMOTE_BASE", "/incoming")),
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
                if section == "device":
                    continue  # device-sektion styres af DB-kolonner, ikke device_config
                if section in cfg and isinstance(cfg[section], dict):
                    cfg[section].update(values)
                else:
                    cfg[section] = values
        except Exception as exc:
            log.warning("Invalid device_config for %s: %s", device_id, exc)

    # Apply hierarchical config overrides (Sprint A)
    try:
        from database import Customer, Site
        site    = db.query(Site).filter_by(id=device.site_id).first() if hasattr(device, "site_id") and device.site_id else None
        customer = db.query(Customer).filter_by(id=site.customer_id).first() if site else None
        defaults = db.query(ConfigDefaults).first()
        # Lag 1: config_defaults
        if defaults:
            for section in ["schedule", "camera", "quality", "storage", "diagnostics", "system"]:
                if hasattr(defaults, section):
                    val = getattr(defaults, section)
                    if val:
                        d = json.loads(val)
                        if section in cfg and isinstance(cfg[section], dict):
                            cfg[section] = _deep_merge(d, cfg[section])
                        else:
                            cfg[section] = d
        # Lag 2: customer overrides
        if customer and customer.config_overrides:
            for section, values in json.loads(customer.config_overrides).items():
                if section in cfg and isinstance(cfg[section], dict):
                    cfg[section] = _deep_merge(cfg[section], values)
                else:
                    cfg[section] = values
        # Lag 3: site overrides + GPS + timezone
        if site:
            if site.config_overrides:
                for section, values in json.loads(site.config_overrides).items():
                    if section in cfg and isinstance(cfg[section], dict):
                        cfg[section] = _deep_merge(cfg[section], values)
                    else:
                        cfg[section] = values
            if site.gps_lat:
                cfg["location"]["gps_lat"] = site.gps_lat
                cfg["location"]["gps_lon"] = site.gps_lon
            if site.timezone:
                cfg["schedule"]["timezone"] = site.timezone
        # Lag 4: device config_overrides
        if hasattr(device, "config_overrides") and device.config_overrides:
            for section, values in json.loads(device.config_overrides).items():
                if section in cfg and isinstance(cfg[section], dict):
                    cfg[section] = _deep_merge(cfg[section], values)
                else:
                    cfg[section] = values
    except Exception as exc:
        log.warning("Hierarkisk config merge fejl for %s: %s", device_id, exc)

    # Tilføj felter fra device_config til edge-config
    try:
        node_cfg = json.loads(device.device_config or "{}")
        cfg["node_cameras"]     = node_cfg.get("node_cameras", [])
        cfg["multi_camera_mode"]= node_cfg.get("multi_camera_mode", "single")
        # SSH tunnel config — edgen bruger dette til at styre tunnelen
        if "ssh_tunnel" in node_cfg:
            cfg["ssh_tunnel"] = node_cfg["ssh_tunnel"]
        # Opdateringspolitik
        if "update_policy" in node_cfg:
            cfg["update_policy"] = node_cfg["update_policy"]
    except Exception:
        cfg["node_cameras"] = []
        cfg["multi_camera_mode"] = "single"

    # Inkluder config_version så edge kan detektere ændringer
    cfg["config_version"] = device.config_version or ""

    return cfg


@app.put("/api/admin/devices/{device_id}/config")
def update_device_config(
    device_id: str,
    config: dict,
    _user=require_role("admin"),
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
    # Genberegn config_version så edge opdager ændringen
    import hashlib as _hl
    device.config_version = _hl.md5(device.device_config.encode()).hexdigest()
    db.commit()
    log.info("Updated device config for %s: %s", device_id, list(config.keys()))
    return {"status": "ok", "device_id": device_id, "config": existing}



def _process_update_report(device_id: str, diag: dict, db) -> None:
    """Opret PendingUpdate-poster baseret på update-info fra heartbeat."""
    from database import PendingUpdate
    updates = diag.get("updates", {})
    if not updates:
        return

    os_security  = int(updates.get("os_security_count", 0))
    os_total     = int(updates.get("os_updates_count", 0))
    edge_version = updates.get("app_version", "")

    # Headend's egen git-commit som reference
    try:
        import subprocess as _sp
        repo_dir = _os.getenv("TIMELAPSE_REPO_DIR", "/Users/peter/projects/timelapse-pro")
        headend_version = _sp.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()[:7]
    except Exception:
        headend_version = ""

    def _has_pending(update_type: str) -> bool:
        return db.query(PendingUpdate).filter_by(
            update_type=update_type, scope="device",
            scope_id=device_id, status="pending"
        ).first() is not None

    if os_security > 0 and not _has_pending("os_security"):
        db.add(PendingUpdate(
            update_type = "os_security",
            version     = f"{os_security} pakker",
            description = f"{os_security} sikkerhedsopdatering(er) klar til installation (apt)",
            severity    = "high" if os_security >= 10 else "medium",
            scope="device", scope_id=device_id, status="pending",
        ))
        log.info("PendingUpdate oprettet: os_security for %s (%d pakker)", device_id, os_security)

    if os_total > 0 and not _has_pending("os_updates"):
        db.add(PendingUpdate(
            update_type = "os_updates",
            version     = f"{os_total} pakker",
            description = f"{os_total} funktionelle OS-opdatering(er) klar via apt",
            severity    = "low",
            scope="device", scope_id=device_id, status="pending",
        ))
        log.info("PendingUpdate oprettet: os_updates for %s (%d pakker)", device_id, os_total)

    if edge_version and headend_version and edge_version != headend_version:
        if not _has_pending("app_updates"):
            db.add(PendingUpdate(
                update_type = "app_updates",
                version     = headend_version,
                description = f"TimeLapse Pro opdatering tilgængelig (edge: {edge_version} → headend: {headend_version})",
                severity    = "medium",
                scope="device", scope_id=device_id, status="pending",
            ))
            log.info("PendingUpdate oprettet: app_updates for %s", device_id)

# ── Heartbeat ─────────────────────────────────────────────────────────────────

@app.post("/api/heartbeat/{device_id}")
def heartbeat(
    device_id: str,
    req: HeartbeatRequest,
    _auth: None = Depends(_verify_device_token),
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

    log.info("UPDATE DEBUG: updates felt=%s", diag.get('updates'))
    _process_update_report(device_id, diag, db)
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
    _auth: None = Depends(_verify_device_token),
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

    # Læs EXIF fra filen i baggrunden og gem i DB
    _cap_id = capture.id
    _dev_id = device_id
    _fname  = req.filename
    def _enrich_exif():
        try:
            import exifread
            src = _find_image(_dev_id, _fname)
            if not src or not src.exists():
                return
            with open(str(src), "rb") as fh:
                tags = exifread.process_file(fh, details=True)
            if not tags:
                return
            exif_json = _json.dumps({k: str(v) for k, v in tags.items()}, ensure_ascii=False)
            # Opdater capture record
            db2 = next(get_db())
            try:
                c2 = db2.query(Capture).filter(Capture.id == _cap_id).first()
                if c2:
                    c2.exif_data = exif_json
                    db2.commit()
                    log.info("EXIF gemt for capture %d (%d felter)", _cap_id, len(tags))
            finally:
                db2.close()
        except Exception as exc:
            log.warning("EXIF baggrunds-læsning fejl: %s", exc)
    _threading.Thread(target=_enrich_exif, daemon=True).start()

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
    _auth: None = Depends(_verify_device_token),
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




# ═══════════════════════════════════════════════════════════════════════════
# ── SSH TUNNEL ENDPOINTS (Sprint C) ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

class SshTunnelEventRequest(BaseModel):
    device_id:      str
    event:          str          # connected|disconnected|failed|denied
    remote_port:    Optional[int] = None
    local_port:     Optional[int] = 22
    duration_s:     Optional[int] = None
    using_fallback: Optional[bool] = False
    timestamp:      str

@app.post("/api/ssh-tunnel/event")
def ssh_tunnel_event(req: SshTunnelEventRequest, db: Session = Depends(get_db)):
    """Edge notificerer headend om SSH tunnel events (connect, disconnect, fail)."""
    from database import SshTunnelLog
    entry = SshTunnelLog(
        device_id    = req.device_id,
        event        = req.event,
        remote_port  = req.remote_port,
        local_port   = req.local_port,
        initiated_by = "edge_auto",
        duration_s   = req.duration_s,
        extra        = _json.dumps({"using_fallback": req.using_fallback}) if req.using_fallback else None,
    )
    db.add(entry); db.commit()
    log.info("SSH tunnel %s: device=%s port=%s", req.event, req.device_id, req.remote_port)
    return {"status": "ok"}

@app.get("/api/ssh-tunnel/active")
def ssh_tunnel_active(
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """Returnerer liste af devices med aktiv SSH tunnel."""
    from database import SshTunnelLog
    from sqlalchemy import text as _t

    # Find seneste event pr. device — aktiv = seneste event er "connected"
    rows = db.execute(_t("""
        SELECT s.device_id, s.remote_port, s.local_port, s.event_at, s.extra
        FROM ssh_tunnel_log s
        INNER JOIN (
            SELECT device_id, MAX(event_at) as max_at
            FROM ssh_tunnel_log
            GROUP BY device_id
        ) latest ON s.device_id = latest.device_id AND s.event_at = latest.max_at
        WHERE s.event = 'connected'
        ORDER BY s.event_at DESC
    """)).fetchall()

    return [
        {
            "device_id":   r[0],
            "remote_port": r[1],
            "local_port":  r[2],
            "connected_at": r[3],
        }
        for r in rows
    ]

@app.get("/api/ssh-tunnel/log/{device_id}")
def ssh_tunnel_log(
    device_id: str,
    limit: int = 50,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Audit log for SSH tunnel sessioner på en device."""
    from database import SshTunnelLog
    entries = (
        db.query(SshTunnelLog)
        .filter_by(device_id=device_id)
        .order_by(SshTunnelLog.event_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "event":       e.event,
            "remote_port": e.remote_port,
            "duration_s":  e.duration_s,
            "initiated_by":e.initiated_by,
            "event_at":    e.event_at.isoformat() if e.event_at else None,
        }
        for e in entries
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ── CAMERA / PI KOBLING (Sprint C) ────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/admin/cameras")
def list_cameras(
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """List alle logiske kameraer."""
    from database import Camera, DeviceAssignment
    cameras = db.query(Camera).filter(Camera.retired_at.is_(None)).all()
    result = []
    for cam in cameras:
        # Find aktiv device assignment
        assignment = (
            db.query(DeviceAssignment)
            .filter_by(camera_id=cam.id)
            .filter(DeviceAssignment.unassigned_at.is_(None))
            .first()
        )
        result.append({
            "id":            cam.id,
            "site_id":       cam.site_id,
            "customer_id":   cam.customer_id,
            "camera_name":   cam.camera_name,
            "serial_number": cam.serial_number,
            "model":         cam.model,
            "notes":         cam.notes,
            "current_device_id": assignment.device_id if assignment else None,
            "assigned_at":   assignment.assigned_at.isoformat() if assignment and assignment.assigned_at else None,
            "created_at":    cam.created_at.isoformat() if cam.created_at else None,
        })
    return result

@app.post("/api/admin/cameras")
def create_camera(
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Opret et nyt logisk kamera."""
    from database import Camera
    import uuid as _u
    cam = Camera(
        id          = str(_u.uuid4()),
        site_id     = payload.get("site_id"),
        customer_id = payload.get("customer_id"),
        camera_name = payload.get("camera_name", "Nyt kamera"),
        serial_number = payload.get("serial_number"),
        model       = payload.get("model"),
        notes       = payload.get("notes"),
        config      = _json.dumps(payload.get("config", {})),
    )
    db.add(cam); db.commit()
    log.info("Kamera oprettet: %s (%s)", cam.camera_name, cam.id)
    return {"id": cam.id}

@app.post("/api/admin/cameras/{camera_id}/assign")
def assign_camera_to_device(
    camera_id: str,
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Tildel et logisk kamera til en fysisk device (Orange Pi).
    Afslutter eventuel eksisterende assignment automatisk.
    """
    from database import Camera, DeviceAssignment, Device
    import uuid as _u

    camera = db.query(Camera).filter_by(id=camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")

    device_id = payload.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id påkrævet")

    # Afslut eksisterende aktive assignments for dette kamera
    old = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=camera_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .all()
    )
    for o in old:
        o.unassigned_at = now_utc()
        log.info("Assignment afsluttet: device=%s kamera=%s", o.device_id, camera_id)

    # Afslut også eksisterende assignments for denne device (til andre kameraer)
    old_dev = (
        db.query(DeviceAssignment)
        .filter_by(device_id=device_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .all()
    )
    for o in old_dev:
        o.unassigned_at = now_utc()

    # Opret ny assignment
    assignment = DeviceAssignment(
        device_id   = device_id,
        camera_id   = camera_id,
        assigned_by = payload.get("assigned_by", "admin"),
        notes       = payload.get("notes"),
    )
    db.add(assignment)

    # Synkroniser camera_name, site, customer til device (for bagudkompatibilitet)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device:
        device.camera_name   = camera.camera_name
        device.site_id       = camera.site_id
        device.customer_id   = camera.customer_id

    db.commit()
    log.info("Kamera %s tildelt device %s", camera_id, device_id)
    return {"ok": True, "camera_id": camera_id, "device_id": device_id}

@app.get("/api/admin/cameras/{camera_id}/history")
def camera_assignment_history(
    camera_id: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Historik over alle device-assignments for et kamera."""
    from database import DeviceAssignment
    entries = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=camera_id)
        .order_by(DeviceAssignment.assigned_at.desc())
        .all()
    )
    return [
        {
            "device_id":     e.device_id,
            "assigned_at":   e.assigned_at.isoformat() if e.assigned_at else None,
            "unassigned_at": e.unassigned_at.isoformat() if e.unassigned_at else None,
            "assigned_by":   e.assigned_by,
            "notes":         e.notes,
            "active":        e.unassigned_at is None,
        }
        for e in entries
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ── OPDATERINGSSTYRING (Sprint C) ─────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/updates/pending")
def list_pending_updates(
    status: Optional[str] = None,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """List opdateringer der afventer godkendelse eller deployment."""
    from database import PendingUpdate
    q = db.query(PendingUpdate)
    if status:
        q = q.filter_by(status=status)
    else:
        q = q.filter(PendingUpdate.status.in_(["pending", "approved"]))
    updates = q.order_by(PendingUpdate.created_at.desc()).all()
    return [
        {
            "id":          u.id,
            "update_type": u.update_type,
            "version":     u.version,
            "description": u.description,
            "severity":    u.severity,
            "scope":       u.scope,
            "scope_id":    u.scope_id,
            "status":      u.status,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
            "approved_by": u.approved_by,
        }
        for u in updates
    ]

@app.post("/api/updates/{update_id}/approve")
def approve_update(
    update_id: int,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Godkend en opdatering til deployment."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id, status="pending").first()
    if not u:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet eller ikke pending")
    u.status      = "approved"
    u.approved_at = now_utc()
    u.approved_by = current_user.username
    db.commit()
    log.info("Opdatering godkendt: %s v%s af %s", u.update_type, u.version, current_user.username)
    return {"ok": True}

@app.post("/api/updates/{update_id}/reject")
def reject_update(
    update_id: int,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Afvis en opdatering."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id, status="pending").first()
    if not u:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    u.status      = "rejected"
    u.approved_by = current_user.username
    u.approved_at = now_utc()
    db.commit()
    return {"ok": True}

@app.get("/api/updates/policy/{device_id}")
def get_update_policy(
    device_id: str,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db)
):
    """Returnerer resolved update_policy for et device (bruges af edge)."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)

    # Default policy
    policy = {
        "app_security":  "auto",
        "os_security":   "auto",
        "app_updates":   "manual",
        "os_updates":    "manual",
        "maintenance_window": "02:00-04:00",
    }

    # Merge hierarki (global → customer → site → device)
    try:
        site     = db.query(Site).filter_by(id=device.site_id).first() if device.site_id else None
        customer = db.query(Customer).filter_by(id=site.customer_id).first() if site else None
        defaults = db.query(ConfigDefaults).first()

        if defaults and getattr(defaults, "system", None):
            sys_cfg = _json.loads(defaults.system)
            if "update_policy" in sys_cfg:
                policy.update(sys_cfg["update_policy"])

        for obj in [customer, site, device]:
            if not obj:
                continue
            overrides_raw = getattr(obj, "config_overrides", None) or getattr(obj, "device_config", None)
            if overrides_raw:
                try:
                    overrides = _json.loads(overrides_raw) if isinstance(overrides_raw, str) else overrides_raw
                    if "update_policy" in overrides:
                        # Mest restriktive vinder: manual > auto
                        for k, v in overrides["update_policy"].items():
                            if k in policy:
                                if v == "manual" or policy[k] == "auto":
                                    policy[k] = v
                except Exception:
                    pass
    except Exception as exc:
        log.warning("Update policy resolution fejl: %s", exc)

    return policy

@app.post("/api/updates/report")
def report_update(payload: dict, db: Session = Depends(get_db)):
    """Edge rapporterer resultat af deployment (deployed/rolled_back)."""
    from database import PendingUpdate
    update_id = payload.get("update_id")
    status    = payload.get("status")  # deployed|rolled_back
    if not update_id or status not in ("deployed", "rolled_back"):
        raise HTTPException(status_code=400)
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    u.status = status
    if status == "deployed":
        u.deployed_at = now_utc()
    elif status == "rolled_back":
        u.rollback_at = now_utc()
    db.commit()
    log.info("Update %d rapporteret som %s fra device", update_id, status)
    return {"ok": True}





# ════════════════════════════════════════════════════════════════════════

@app.post("/api/updates/available")
def report_available_updates(
    payload: dict,
    db: Session = Depends(get_db),
):
    """Edge rapporterer tilgængelige opdateringer — opretter PendingUpdate-poster."""
    from database import PendingUpdate

    device_id          = payload.get("device_id", "unknown")
    os_security_count  = int(payload.get("os_security_count", 0))
    os_updates_count   = int(payload.get("os_updates_count", 0))
    app_version        = payload.get("app_version", "")
    app_behind_commits = int(payload.get("app_behind_commits", 0))
    app_security       = bool(payload.get("app_security", False))

    created = []

    def _has_pending(update_type: str) -> bool:
        return db.query(PendingUpdate).filter_by(
            update_type=update_type,
            scope="device",
            scope_id=device_id,
            status="pending",
        ).first() is not None

    if os_security_count > 0 and not _has_pending("os_security"):
        db.add(PendingUpdate(
            update_type = "os_security",
            version     = f"{os_security_count} pakker",
            description = f"{os_security_count} sikkerhedsopdatering(er) klar til installation via apt",
            severity    = "high" if os_security_count >= 10 else "medium",
            scope       = "device",
            scope_id    = device_id,
            status      = "pending",
        ))
        created.append("os_security")

    if os_updates_count > 0 and not _has_pending("os_updates"):
        db.add(PendingUpdate(
            update_type = "os_updates",
            version     = f"{os_updates_count} pakker",
            description = f"{os_updates_count} funktionelle OS-opdatering(er) klar via apt",
            severity    = "low",
            scope       = "device",
            scope_id    = device_id,
            status      = "pending",
        ))
        created.append("os_updates")

    if app_security and not _has_pending("app_security"):
        db.add(PendingUpdate(
            update_type = "app_security",
            version     = app_version or "ukendt",
            description = "TimeLapse Pro sikkerhedsopdatering tilgængelig",
            severity    = "critical",
            scope       = "device",
            scope_id    = device_id,
            status      = "pending",
        ))
        created.append("app_security")

    if app_behind_commits > 0 and not _has_pending("app_updates"):
        db.add(PendingUpdate(
            update_type = "app_updates",
            version     = app_version or "ukendt",
            description = f"TimeLapse Pro er {app_behind_commits} commit(s) bagud",
            severity    = "medium",
            scope       = "device",
            scope_id    = device_id,
            status      = "pending",
        ))
        created.append("app_updates")

    db.commit()
    log.info("Update rapport fra %s: %s", device_id, created or "ingen nye")
    return {"ok": True, "created": created}

# ── PROVISION PACKAGE (Sprint C) ─────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════

from fastapi.responses import StreamingResponse
import io as _io
import zipfile as _zipfile

def _generate_ed25519_keypair() -> tuple[str, str]:
    """Generer Ed25519 nøglepar — returnerer (privat_pem, offentlig_openssh)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, PublicFormat, NoEncryption
        )
        private_key = Ed25519PrivateKey.generate()
        private_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.OpenSSH,
            encryption_algorithm=NoEncryption()
        ).decode()
        public_openssh = private_key.public_key().public_bytes(
            encoding=Encoding.OpenSSH,
            format=PublicFormat.OpenSSH
        ).decode()
        return private_pem, public_openssh
    except ImportError:
        # Fallback: brug subprocess + ssh-keygen
        import subprocess, tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            key_path = os.path.join(tmp, "key")
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-C", "timelapse-provision"],
                check=True, capture_output=True
            )
            priv = open(key_path).read()
            pub  = open(key_path + ".pub").read().strip()
        return priv, pub


def _build_bootstrap_yaml(device_id_hint: str, headend_url: str, token: str,
                           location_name: str) -> str:
    return f"""# TimeLapse Pro — Bootstrap Configuration
# Genereret: {now_utc().strftime('%Y-%m-%d %H:%M UTC')}
# Kopiér til: /opt/timelapse/edge/bootstrap.yaml

device_id: {device_id_hint}
headend_url: {headend_url}
bootstrap_token: {token}
location_name: {location_name}
"""


def _build_install_md(site_name: str, camera_name: str, headend_url: str,
                      tunnel_pub: str, sftp_pub: str, device_hint: str) -> str:
    return f"""# TimeLapse Pro — Installationsguide
## {site_name} — {camera_name}
Genereret: {now_utc().strftime('%Y-%m-%d %H:%M UTC')}

---

## Forudsætninger

- Orange Pi 4 Pro med Ubuntu 22.04
- TimeLapse Pro edge-kode deployed via GitHub Actions
- Kamera tilsluttet via USB
- Netværksforbindelse

---

## Trin 1 — Kopiér provisionerings-filer til Orange Pi

Fra Mac Mini (erstat `<orange-pi-ip>`):
```bash
scp bootstrap.yaml pi@<orange-pi-ip>:/opt/timelapse/edge/
scp tunnel_key pi@<orange-pi-ip>:/opt/timelapse/edge/ssh/
scp tunnel_key.pub pi@<orange-pi-ip>:/opt/timelapse/edge/ssh/
scp sftp_key pi@<orange-pi-ip>:/opt/timelapse/edge/ssh/
scp sftp_key.pub pi@<orange-pi-ip>:/opt/timelapse/edge/ssh/
```

---

## Trin 2 — Sæt korrekte filrettigheder på Orange Pi

```bash
chmod 600 /opt/timelapse/edge/ssh/tunnel_key
chmod 644 /opt/timelapse/edge/ssh/tunnel_key.pub
chmod 600 /opt/timelapse/edge/ssh/sftp_key
chmod 644 /opt/timelapse/edge/ssh/sftp_key.pub
chmod 600 /opt/timelapse/edge/bootstrap.yaml
chmod 644 /opt/timelapse/edge/ssh/known_hosts
```

> **Bemærk:** `known_hosts` indeholder headendens SSH-fingerprint.
> Orange Pi verificerer automatisk at den forbinder til den rigtige server.

---

## Trin 3 — Tilføj tunnel-nøgle til headend

På Mac Mini headend:
```bash
echo "{tunnel_pub} {device_hint}" >> /home/tunnel/.ssh/authorized_keys
```

---

## Trin 4 — Tilføj SFTP-nøgle til headend

På Mac Mini headend (erstat `sftp_<site-kode>` med den rigtige bruger):
```bash
echo "{sftp_pub} {site_name}" >> /Users/Shared/timelapse/sftp_keys/authorized_keys_<site-kode>
```

---

## Trin 5 — Start timelapse-edge service

```bash
sudo systemctl restart timelapse-edge
sudo systemctl status timelapse-edge
```

Forventet output:
```
● timelapse-edge.service — TimeLapse Pro Edge Agent
   Active: active (running)
   ...
   Config loaded — device_id=TL-... location={site_name} — {camera_name}
   Bootstrapping device TL-... with headend…
   Bootstrap OK
```

---

## Trin 6 — Verificer i UI

1. Åbn TimeLapse Pro UI → Dashboard
2. Ny enhed vises som online
3. Tildel enheden til site: **{site_name}** → kamera: **{camera_name}**
4. Start LAB mode for at verificere kameraforbindelsen

---

## Fejlfinding

```bash
# Tjek logs
journalctl -u timelapse-edge -f

# Tjek netværk
curl {headend_url}/health

# Tjek SSH tunnel
ssh -T -i /opt/timelapse/edge/ssh/tunnel_key tunnel@<headend-host>
```

---

*TimeLapse Pro v3.0.0 — Headend: {headend_url}*
"""




# ── Password politik ──────────────────────────────────────────────────────────

def _get_password_policy(db: Session) -> dict:
    """Hent password-politik fra settings."""
    return {
        "min_length":        int(_get_setting(db, "pw_min_length",        "8")),
        "require_uppercase": _get_setting(db, "pw_require_uppercase", "false").lower() == "true",
        "require_number":    _get_setting(db, "pw_require_number",    "false").lower() == "true",
        "require_special":   _get_setting(db, "pw_require_special",   "false").lower() == "true",
    }


def _validate_password(pw: str, policy: dict) -> list[str]:
    """Returnerer liste af fejl — tom liste = OK."""
    errors = []
    if len(pw) < policy["min_length"]:
        errors.append(f"Mindst {policy['min_length']} tegn")
    if policy["require_uppercase"] and not any(c.isupper() for c in pw):
        errors.append("Mindst ét stort bogstav")
    if policy["require_number"] and not any(c.isdigit() for c in pw):
        errors.append("Mindst ét tal")
    if policy["require_special"] and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pw):
        errors.append("Mindst ét specialtegn")
    return errors


@app.get("/api/admin/password-policy")
def get_password_policy(
    _user=require_role("super_admin", "admin", "operator", "viewer"),
    db: Session = Depends(get_db)
):
    """Returner gældende password-politik."""
    return _get_password_policy(db)


@app.put("/api/admin/password-policy")
def update_password_policy(
    payload: dict,
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    """Opdater password-politik i settings."""
    mapping = {
        "min_length":        ("pw_min_length",        str),
        "require_uppercase": ("pw_require_uppercase", lambda v: "true" if v else "false"),
        "require_number":    ("pw_require_number",    lambda v: "true" if v else "false"),
        "require_special":   ("pw_require_special",   lambda v: "true" if v else "false"),
    }
    for key, (setting_key, converter) in mapping.items():
        if key in payload:
            val = converter(payload[key])
            existing = db.query(Settings).filter_by(key=setting_key).first()
            if existing:
                existing.value = val
            else:
                db.add(Settings(key=setting_key, value=val))
    db.commit()
    return _get_password_policy(db)



# ── Bootstrap Token CRUD ──────────────────────────────────────────────────────

@app.get("/api/admin/bootstrap-tokens")
def list_bootstrap_tokens(
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """List aktive bootstrap tokens."""
    from datetime import timedelta
    tokens = (
        db.query(BootstrapToken)
        .filter_by(revoked=False)
        .order_by(BootstrapToken.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "token":         t.token,
            "device_label":  t.device_label,
            "site_id":       t.site_id,
            "camera_name":   t.camera_name,
            "created_by":    t.created_by,
            "created_at":    t.created_at.isoformat() if t.created_at else None,
            "expires_at":    t.expires_at.isoformat() if t.expires_at else None,
            "used":          t.used_at is not None,
            "used_by_device":t.used_by_device,
        }
        for t in tokens
    ]


@app.post("/api/admin/bootstrap-tokens")
def create_bootstrap_token(
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Generer nyt bootstrap token (24 timers levetid)."""
    import secrets
    from datetime import timedelta
    token_str = f"test-{secrets.token_hex(24)}"   # "test-" prefix for bagudkompatibilitet med DEV
    expires_hours = int(payload.get("expires_hours", 24))
    t = BootstrapToken(
        token        = token_str,
        device_label = payload.get("device_label", "Ny enhed"),
        site_id      = payload.get("site_id"),
        customer_id  = payload.get("customer_id"),
        camera_name  = payload.get("camera_name"),
        created_by   = current_user.username,
        expires_at   = now_utc() + timedelta(hours=expires_hours),
    )
    db.add(t); db.commit()
    log.info("Bootstrap token oprettet af %s til %s", current_user.username, t.device_label)
    return {
        "token":      token_str,
        "expires_at": t.expires_at.isoformat(),
        "device_label": t.device_label,
    }


@app.delete("/api/admin/bootstrap-tokens/{token}")
def revoke_bootstrap_token(
    token: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Revokér et bootstrap token."""
    t = db.query(BootstrapToken).filter_by(token=token).first()
    if not t:
        raise HTTPException(status_code=404)
    t.revoked = True
    db.commit()
    return {"ok": True}


# ── Provision Package ─────────────────────────────────────────────────────────

@app.post("/api/admin/provision-package")
def create_provision_package(
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """
    Generer komplet provisionerings-ZIP til ny Orange Pi edge-enhed.

    ZIP indeholder:
      bootstrap.yaml       — device_id (foreløbig), headend_url, bootstrap_token
      tunnel_key           — Ed25519 privat nøgle til reverse SSH tunnel
      tunnel_key.pub       — Tilhørende public key (kopiér til headend authorized_keys)
      sftp_key             — Ed25519 privat nøgle til SFTP upload
      sftp_key.pub         — Tilhørende public key
      INSTALL.md           — Trin-for-trin installationsguide
    """
    site_id     = payload.get("site_id")
    camera_name = payload.get("camera_name", "Kamera 1")
    device_id   = payload.get("device_id")  # valgfrit — hvis None genereres foreløbig ID

    if not site_id:
        raise HTTPException(status_code=400, detail="site_id er påkrævet")

    # Hent site og kunde-info
    site     = db.query(Site).filter_by(id=site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site ikke fundet")
    customer = db.query(Customer).filter_by(id=site.customer_id).first()

    site_name     = site.name
    customer_name = customer.name if customer else "Ukendt kunde"
    location_name = f"{customer_name} — {site_name} — {camera_name}"

    # Generer foreløbigt device_id hvis ikke angivet
    device_id_hint = device_id or f"TL-PROV-{_uuid.uuid4().hex[:8].upper()}"

    # Headend URL fra settings
    headend_url = _get_setting(db, "base_url", os.getenv("BASE_URL", "http://timelapse.froekjaer.dk:8000"))

    # Generer bootstrap token
    import secrets
    from datetime import timedelta
    token_str = f"test-{secrets.token_hex(24)}"
    token_rec = BootstrapToken(
        token        = token_str,
        device_label = location_name,
        site_id      = site_id,
        customer_id  = site.customer_id,
        camera_name  = camera_name,
        created_by   = current_user.username,
        expires_at   = now_utc() + timedelta(hours=48),
    )
    db.add(token_rec)
    db.commit()

    # Generer SSH-nøglepar
    tunnel_priv, tunnel_pub = _generate_ed25519_keypair()
    sftp_priv,   sftp_pub   = _generate_ed25519_keypair()

    # Tilføj kommentar til public keys
    tunnel_pub = f"{tunnel_pub.strip()} {device_id_hint}"
    sftp_pub   = f"{sftp_pub.strip()} sftp@{site_name.replace(' ', '_')}"

    # Byg filindhold
    bootstrap_yaml = _build_bootstrap_yaml(device_id_hint, headend_url, token_str, location_name)
    install_md     = _build_install_md(site_name, camera_name, headend_url, tunnel_pub, sftp_pub, device_id_hint)

    # Generer known_hosts med headendens SSH fingerprint
    known_hosts_content = ""
    try:
        import subprocess as _sp
        headend_host = headend_url.replace("https://", "").replace("http://", "").split(":")[0]
        result = _sp.run(
            ["ssh-keyscan", "-H", headend_host],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            known_hosts_content = result.stdout
            log.info("known_hosts genereret for %s (%d linjer)",
                     headend_host, len(result.stdout.splitlines()))
        else:
            log.warning("ssh-keyscan fejlede for %s — known_hosts udelades", headend_host)
    except Exception as exc:
        log.warning("known_hosts generering fejlede: %s", exc)

    # Byg ZIP i hukommelsen
    zip_buffer = _io.BytesIO()
    safe_site  = site_name.replace(" ", "_").replace("/", "-")[:20]

    with _zipfile.ZipFile(zip_buffer, "w", _zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bootstrap.yaml",   bootstrap_yaml)
        zf.writestr("tunnel_key",       tunnel_priv)
        zf.writestr("tunnel_key.pub",   tunnel_pub + "\n")
        zf.writestr("sftp_key",         sftp_priv)
        zf.writestr("sftp_key.pub",     sftp_pub + "\n")
        if known_hosts_content:
            zf.writestr("known_hosts", known_hosts_content)
        zf.writestr("INSTALL.md",       install_md)

    zip_buffer.seek(0)

    # Log audit-event
    db.add(Event(
        device_id = device_id_hint,
        level     = "INFO",
        category  = "provision",
        message   = f"Provisionerings-pakke genereret til {location_name}",
        extra     = _json.dumps({
            "site_id":    site_id,
            "created_by": current_user.username,
            "token":      token_str[:16] + "…",
        }),
    ))
    db.commit()
    log.info("Provisionerings-pakke genereret: %s af %s", location_name, current_user.username)

    filename = f"timelapse_provision_{safe_site}_{now_utc().strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        _io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



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
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Update device metadata: customer_name, site_name, camera_name, installed_date, installed_time."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    for field in ["customer_name", "site_name", "camera_name", "location_name"]:
        if field in info:
            setattr(device, field, info[field])
    db.commit()
    log.info("Updated device info for %s", device_id)
    return {"status": "ok", "device_id": device_id}


@app.get("/api/admin/devices")
def list_devices(_user=require_role("viewer"), db: Session = Depends(get_db)):
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
                                })
    return result



@app.get("/api/admin/captures")
def list_captures(
    device_id: Optional[str] = None,
    limit: int = 50,
    _user=require_role("viewer"),
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
            "gps_lat":       c.gps_lat if hasattr(c, 'gps_lat') else None,
            "gps_lon":       c.gps_lon if hasattr(c, 'gps_lon') else None,
            "azimuth_deg":   c.azimuth_deg if hasattr(c, 'azimuth_deg') else None,
            "tilt_deg":      c.tilt_deg if hasattr(c, 'tilt_deg') else None,
            "xmp_written":   c.xmp_written if hasattr(c, 'xmp_written') else None,
        }
        for c in captures
    ]


@app.get("/api/admin/stats")
def stats(_user=require_role("viewer"), db: Session = Depends(get_db)):
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

@app.get("/api/sidecar/{device_id}/{filename}")
def get_sidecar(device_id: str, filename: str):
    """Returner sidecar JSON metadata for et billede."""
#Peter    import re as _re
#Peter    from fastapi.responses import JSONResponse
    # Find billedet samme sted som thumbnails
    m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
        json_filename = filename.rsplit(".", 1)[0] + ".json"
        # Chroot struktur: sftp_user/data/customer/site/yyyy/mm/dd/
        matches = list(SFTP_BASE.glob(f"*/data/*/*/{yyyy}/{mm}/{dd}/{json_filename}"))
        # Fallback: gammel struktur
        if not matches:
            matches = list(SFTP_BASE.glob(f"*/*/{yyyy}/{mm}/{dd}/{json_filename}"))
        if matches:
            sidecar_path = matches[0]
            if sidecar_path.exists():
#Peter                import json as _json
                return _json.loads(sidecar_path.read_text(encoding='utf-8'))
    # Fallback: flat struktur
    flat = SFTP_BASE / device_id / filename
    if flat.exists():
#Peter        import json as _json
        return _json.loads(flat.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="Sidecar ikke fundet")



# ═══════════════════════════════════════════════════════════════════════════
# Timelapse Video Rendering
# ═══════════════════════════════════════════════════════════════════════════

#Peter import subprocess as _subprocess
#Peter import threading as _threading
import uuid as _render_uuid
from pathlib import Path as _RPath

RENDER_JOBS: dict = {}          # job_id → {status, progress, error, output_path}
RENDER_OUTPUT_DIR = _RPath("/tmp/timelapse_renders")
RENDER_OUTPUT_DIR.mkdir(exist_ok=True)


@app.get("/api/timelapse/frames")
def get_timelapse_frames(
    request: Request,
    device_id: str,
    start: str,
    end: str,
    min_blur: float = 0,
    quality_only: bool = False,
    db: Session = Depends(get_db),
):
    """Returner billeder i tidsinterval til timelapse preview."""
    from datetime import datetime as _dt
    try:
        start_dt = _dt.fromisoformat(start.replace("Z", "+00:00"))
        end_dt   = _dt.fromisoformat(end.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Ugyldigt datoformat")

    q = db.query(Capture).filter(
        Capture.device_id == device_id,
        Capture.captured_at >= start_dt,
        Capture.captured_at <= end_dt,
        Capture.captured_at.isnot(None),
    ).order_by(Capture.captured_at.asc())

    if quality_only:
        q = q.filter(Capture.quality_passed == True)
    if min_blur > 0:
        q = q.filter(Capture.blur_score >= min_blur)
    # Lysstyrke filter
    min_brightness = float(request.query_params.get("min_brightness", 0))
    max_brightness = float(request.query_params.get("max_brightness", 255))
    if min_brightness > 0:
        q = q.filter(Capture.brightness_mean >= min_brightness)
    if max_brightness < 255:
        q = q.filter(Capture.brightness_mean <= max_brightness)
    # Dag/nat filter via capture tidspunkt og GPS koordinater
    day_night = request.query_params.get("day_night", "all")
    if day_night in ("day", "night"):
        try:
#Peter            from datetime import timezone as _tz
            import math as _math
            lat = float(request.query_params.get("gps_lat", 0))
            lon = float(request.query_params.get("gps_lon", 0))
            if lat == 0 and lon == 0:
                lat, lon = 55.7, 12.6  # Default DK
            def _is_daytime(dt):
                if not dt: return True
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_tz.utc)
                doy = dt.timetuple().tm_yday
                hour = dt.hour + dt.minute/60 + dt.second/3600 + lon/15
                decl = 23.45 * _math.sin(_math.radians(360/365 * (doy - 81)))
                ha = (hour - 12) * 15
                elev = _math.degrees(_math.asin(
                    _math.sin(_math.radians(lat))*_math.sin(_math.radians(decl)) +
                    _math.cos(_math.radians(lat))*_math.cos(_math.radians(decl))*_math.cos(_math.radians(ha))
                ))
                return elev > -0.833
            frames_all = q.all()
            if day_night == "day":
                frames_all = [f for f in frames_all if _is_daytime(f.captured_at)]
            else:
                frames_all = [f for f in frames_all if not _is_daytime(f.captured_at)]
            frames = frames_all
        except Exception as exc:
            import traceback
            log.warning("Dag/nat filter fejl: %s\n%s", exc, traceback.format_exc())
    else:
        frames = q.all()
        frames = q.all()
    return [
        {
            "id":            c.id,
            "filename":      c.filename,
            "device_id":     c.device_id,
            "captured_at":   c.captured_at.isoformat() if c.captured_at else None,
            "blur_score":    round(c.blur_score, 1) if c.blur_score else None,
            "quality_passed":c.quality_passed,
            "quality_flag":  c.quality_flag,
            "filesize_mb":   round(c.filesize / 1e6, 1) if c.filesize else None,
            "brightness":    round(c.brightness_mean, 1) if c.brightness_mean else None,
        }
        for c in frames
    ]


@app.post("/api/timelapse/create")
def create_timelapse(payload: dict, db: Session = Depends(get_db)):
    """Start timelapse video rendering job.

    payload: {
        device_id: str,
        frame_ids: [int],           # Valgte billeder (sorteret)
        fps: int,                   # 12|24|25|30|60
        resolution: str,            # "1080p"|"4k"|"original"
        codec: str,                 # "h264"|"h265"
        deflicker: bool,
        fade_frames: int,           # 0 = ingen fade
        timestamp_overlay: bool,
        timestamp_position: str,    # "tl"|"tr"|"bl"|"br"
        ken_burns: str,             # "none"|"zoom_in"|"zoom_out"
        crop_ratio: str,            # "16:9"|"4:3"|"1:1"|"original"
        title: str,                 # Til filnavn
    }
    """
    device_id  = payload.get("device_id")
    frame_ids  = payload.get("frame_ids", [])
    fps        = int(payload.get("fps", 25))
    resolution = payload.get("resolution", "1080p")
    codec      = payload.get("codec", "h264")
    deflicker  = bool(payload.get("deflicker", False))
    fade_frames= int(payload.get("fade_frames", 0))
    ts_overlay = bool(payload.get("timestamp_overlay", False))
    ts_pos     = payload.get("timestamp_position", "br")
    ken_burns  = payload.get("ken_burns", "none")
    crop_ratio = payload.get("crop_ratio", "16:9")
    title      = payload.get("title", "timelapse")

    if not frame_ids:
        raise HTTPException(status_code=400, detail="Ingen billeder valgt")

    # Hent billeder fra DB
    frames = db.query(Capture).filter(
        Capture.id.in_(frame_ids)
    ).order_by(Capture.captured_at.asc()).all()

    if not frames:
        raise HTTPException(status_code=404, detail="Ingen billeder fundet")

    # Find billedstier
    image_paths = []
    for f in frames:
        path = _find_image(f.device_id, f.filename)
        if path:
            image_paths.append((str(path), f.captured_at))

    if len(image_paths) < 2:
        raise HTTPException(status_code=400, detail="For få billeder fundet på disk")

    job_id = str(_render_uuid.uuid4())[:8]
    RENDER_JOBS[job_id] = {
        "status":   "queued",
        "progress": 0,
        "error":    None,
        "output_path": None,
        "frame_count": len(image_paths),
        "fps": fps,
        "duration_s": round(len(image_paths) / fps, 1),
        "title": title,
    }

    # Start render i baggrunden
    t = _threading.Thread(
        target=_render_timelapse,
        args=(job_id, image_paths, fps, resolution, codec,
              deflicker, fade_frames, ts_overlay, ts_pos,
              ken_burns, crop_ratio, title),
        daemon=True
    )
    t.start()
    log.info("Timelapse job %s startet: %d frames @ %d fps", job_id, len(image_paths), fps)
    return {"job_id": job_id, "frame_count": len(image_paths), "duration_s": round(len(image_paths)/fps, 1)}


def _render_timelapse(job_id, image_paths, fps, resolution, codec,
                      deflicker, fade_frames, ts_overlay, ts_pos,
                      ken_burns, crop_ratio, title):
    """Kør FFmpeg rendering i baggrundstråd."""
#Peter    import os, tempfile

    RENDER_JOBS[job_id]["status"] = "rendering"
    output_file = RENDER_OUTPUT_DIR / f"{job_id}_{title.replace(' ','_')}.mp4"

    try:
        # Skriv billedliste til temp fil (FFmpeg concat demuxer)
        list_file = RENDER_OUTPUT_DIR / f"{job_id}_list.txt"
        with open(list_file, "w") as lf:
            for path, captured_at in image_paths:
                lf.write(f"file '{path}'\n")
                lf.write(f"duration {1/fps:.6f}\n")
            # Gentag sidste billede (FFmpeg krav)
            lf.write(f"file '{image_paths[-1][0]}'\n")

        # Byg FFmpeg video filter kæde
        vf_parts = []

        # Beskæring — safe crop
        if crop_ratio == "16:9":
            vf_parts.append("crop='min(iw,ih*16/9)':'min(ih,iw*9/16)'")
        elif crop_ratio == "4:3":
            vf_parts.append("crop='min(iw,ih*4/3)':'min(ih,iw*3/4)'")
        elif crop_ratio == "1:1":
            vf_parts.append("crop='min(iw,ih)':'min(iw,ih)'")

        # Opløsning
        if resolution == "1080p":
            vf_parts.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
        elif resolution == "4k":
            vf_parts.append("scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2")

        # Deflicker
        if deflicker:
            vf_parts.append("deflicker=size=10:mode=pm")

        # Ken Burns
        if ken_burns == "zoom_in":
            vf_parts.append("zoompan=z='min(zoom+0.0015,1.3)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
        elif ken_burns == "zoom_out":
            vf_parts.append("zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0015))':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")

        # Fade in/ud
        n = len(image_paths)
        if fade_frames > 0:
            vf_parts.append(f"fade=t=in:st=0:d={fade_frames/fps:.2f}")
            vf_parts.append(f"fade=t=out:st={(n-fade_frames)/fps:.2f}:d={fade_frames/fps:.2f}")

        # Tidsstempel overlay
        if ts_overlay:
            positions = {
                "tl": "x=20:y=20",
                "tr": "x=w-tw-20:y=20",
                "bl": "x=20:y=h-th-20",
                "br": "x=w-tw-20:y=h-th-20",
            }
            pos = positions.get(ts_pos, positions["br"])
            vf_parts.append(
                f"drawtext=fontsize=36:fontcolor=white:borderw=2:bordercolor=black:"
                f"text='%{{pts\:hms}}':box=1:boxcolor=black@0.4:boxborderw=5:{pos}"
            )

        vf = ",".join(vf_parts) if vf_parts else "null"

        # Codec indstillinger
        codec_args = ["-c:v", "h264_videotoolbox", "-q:v", "50"]
        if codec == "h265":
            codec_args = ["-c:v", "hevc_videotoolbox", "-q:v", "50"]

        # FFmpeg kommando
        cmd = [
            os.getenv("FFMPEG_PATH", "ffmpeg"), "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-vf", vf,
            "-r", str(fps),
            *codec_args,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_file)
        ]

        log.info("FFmpeg: %s", " ".join(cmd))

        proc = _subprocess.Popen(
            cmd,
            stdout=_subprocess.PIPE,
            stderr=_subprocess.PIPE,
            text=True
        )

        # Læs stderr for progress
        total = len(image_paths)
        for line in proc.stderr:
            if "frame=" in line:
                try:
                    frame_str = line.split("frame=")[1].split()[0]
                    frame_num = int(frame_str)
                    RENDER_JOBS[job_id]["progress"] = min(95, int(100 * frame_num / total))
                except Exception:
                    pass

        proc.wait()

        if proc.returncode == 0 and output_file.exists():
            RENDER_JOBS[job_id]["status"]      = "done"
            RENDER_JOBS[job_id]["progress"]    = 100
            RENDER_JOBS[job_id]["output_path"] = str(output_file)
            RENDER_JOBS[job_id]["filesize_mb"] = round(output_file.stat().st_size / 1e6, 1)
            log.info("Timelapse %s færdig: %s (%.1f MB)", job_id, output_file.name,
                     RENDER_JOBS[job_id]["filesize_mb"])
        else:
            err = proc.stderr.read() if proc.stderr else "Ukendt fejl"
            raise Exception(f"FFmpeg fejl: {err[:200]}")

    except Exception as exc:
        log.error("Timelapse %s fejlede: %s", job_id, exc)
        RENDER_JOBS[job_id]["status"] = "error"
        RENDER_JOBS[job_id]["error"]  = str(exc)
    finally:
        # Ryd op
        try: list_file.unlink()
        except Exception: pass


@app.get("/api/timelapse/status/{job_id}")
def timelapse_status(job_id: str):
    job = RENDER_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    return job


@app.get("/api/timelapse/download/{job_id}")
def timelapse_download(job_id: str):
    from fastapi.responses import FileResponse as _FR
    job = RENDER_JOBS.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(status_code=404, detail="Video ikke klar")
    path = _RPath(job["output_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fil ikke fundet")
    return _FR(str(path), media_type="video/mp4",
               filename=path.name, headers={"Content-Disposition": f"attachment; filename={path.name}"})


@app.get("/api/timelapse/jobs")
def list_timelapse_jobs():
    return [{"job_id": k, **{kk: vv for kk, vv in v.items() if kk != "output_path"}}
            for k, v in RENDER_JOBS.items()]

# ── API Token auth ────────────────────────────────────────────────────────────



@app.get("/health")
def health():
    return {"status": "ok", "time": now_utc().isoformat()}

from pathlib import Path as _Path
from fastapi.responses import FileResponse
from PIL import Image
def _init_sftp_base():
    from sqlalchemy.orm import Session
    db = next(get_db())
    return _Path(_get_setting(db, "sftp_base", os.getenv("SFTP_BASE", "/Users/Shared/timelapse/incoming")))

SFTP_BASE = _init_sftp_base()

#Peter import re as _re

def _find_image(device_id: str, filename: str) -> Optional[_Path]:
    """
    Find image — håndterer tre strukturer:
      1. Ny chroot:   SFTP_BASE/{sftp_user}/data/{customer}/{site}/YYYY/MM/DD/filename
      2. Gammel:      SFTP_BASE/{customer}/{site}/YYYY/MM/DD/filename
      3. Flad:        SFTP_BASE/{device_id}/filename
    """
    m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)

        # Struktur 1 — chroot: sftp_user/data/customer/site/YYYY/MM/DD/
        chroot_glob = f"*/data/*/*/{yyyy}/{mm}/{dd}/{filename}"
        matches = list(SFTP_BASE.glob(chroot_glob))
        if matches:
            return matches[0]

        # Struktur 2 — gammel hierarkisk: customer/site/YYYY/MM/DD/
        old_glob = f"*/*/{yyyy}/{mm}/{dd}/{filename}"
        matches = list(SFTP_BASE.glob(old_glob))
        if matches:
            return matches[0]

        # Struktur 3 — rekursiv fallback (langsommere men sikker)
        matches = list(SFTP_BASE.rglob(filename))
        if matches:
            return matches[0]

    # Flad struktur SFTP_BASE/device_id/filename
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
def set_debug_mode(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
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


@app.post("/api/lab/{device_id}/relay")
def toggle_relay(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Toggle relay TIL/FRA — bruges af SystemAdminPage til test."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    relay   = payload.get("relay", "camera")
    state   = payload.get("state", False)
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {
        "type":  "relay_toggle",
        "relay": relay,
        "state": state,
    }
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("Relay toggle: %s %s → %s", device_id, relay, state)
    return {"status": "ok", "relay": relay, "state": state}


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

#Peter import subprocess as _subprocess
#Peter import threading as _threading
import tempfile as _tempfile
import shutil as _shutil
from fastapi.responses import FileResponse as _FileResponse

_backup_status = {"running": False, "progress": [], "file": None, "error": None}

def _run_backup():
    """Kør backup i baggrunden."""
    global _backup_status
    _backup_status = {"running": True, "progress": [], "file": None, "error": None}
    try:
        import datetime, os, json
        date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nas_path = _get_nas_path()
        base_dir = nas_path if (nas_path and os.path.isdir(nas_path)) else "/tmp"
        backup_dir = f"{base_dir}/timelapse-backup-headend-{date}"
        os.makedirs(f"{backup_dir}/database", exist_ok=True)
        os.makedirs(f"{backup_dir}/configs", exist_ok=True)

        _backup_status["progress"].append("Database backup (pg_dump)...")
        db_url = os.environ.get("DATABASE_URL", "postgresql://timelapse@localhost/timelapse_db")
        db_name = db_url.rstrip("/").split("/")[-1].split("?")[0]
        db_user = db_url.split("://")[1].split("@")[0].split(":")[0]
        sql_path = f"{backup_dir}/database/timelapse_db_{date}.sql"
        r = _subprocess.run(
            ["/opt/homebrew/bin/pg_dump", "-U", db_user, "-h", "localhost", "--no-password", db_name],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            with open(sql_path, "w") as f:
                f.write(r.stdout)
            _backup_status["progress"].append(f"Database OK ({len(r.stdout)//1024} KB SQL)")
        else:
            raise Exception(f"pg_dump fejlede: {r.stderr[:300]}")
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
        archive = f"{base_dir}/timelapse-backup-headend-{date}.tar.gz"
        _subprocess.run(["tar", "czf", archive, "-C", base_dir, f"timelapse-backup-headend-{date}"],
                       check=True, capture_output=True)
        _shutil.rmtree(backup_dir, ignore_errors=True)

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
#Peter        from sqlalchemy import text
        from database import SessionLocal
        db = SessionLocal()
        result = db.execute(text("SELECT value FROM settings WHERE key='backup_nas_path'")).fetchone()
        db.close()
        return result[0] if result else None
    except:
        return None



# ═══════════════════════════════════════════════════════════════════════════
# Sprint A — Customer / Site / Device CRUD
# ═══════════════════════════════════════════════════════════════════════════

def _deep_merge(base: dict, override: dict) -> dict:
    """Rekursiv merge — override vinder ved konflikt."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ── Customers ─────────────────────────────────────────────────────────────

@app.get("/api/admin/customers")
def list_customers(_user=require_role("viewer"), db: Session = Depends(get_db)):
    customers = db.query(Customer).order_by(Customer.name).all()
    return [
        {
            "id":            c.id,
            "name":          c.name,
            "contact_name":  c.contact_name,
            "contact_email": c.contact_email,
            "contact_phone": c.contact_phone,
            "address":       c.address,
            "notes":         c.notes,
            "sites_count":   len(c.sites) if hasattr(c, "sites") else 0,
            "config_overrides": json.loads(c.config_overrides or "{}"),
        }
        for c in customers
    ]


@app.post("/api/admin/customers")
def create_customer(payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    c = Customer(
        id=str(_uuid.uuid4()),
        name=payload.get("name", "Ny kunde"),
        contact_name=payload.get("contact_name"),
        contact_email=payload.get("contact_email"),
        contact_phone=payload.get("contact_phone"),
        address=payload.get("address"),
        notes=payload.get("notes"),
    )
    db.add(c); db.commit(); db.refresh(c)
    log.info("Kunde oprettet: %s", c.id)
    return {"id": c.id}


@app.get("/api/admin/customers/{customer_id}")
def get_customer(customer_id: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404)
    sites = db.query(Site).filter_by(customer_id=customer_id).all()
    return {
        "id": c.id, "name": c.name,
        "contact_name": c.contact_name, "contact_email": c.contact_email,
        "contact_phone": c.contact_phone, "address": c.address, "notes": c.notes,
        "config_overrides": json.loads(c.config_overrides or "{}"),
        "sites": [
            {
                "id": s.id, "name": s.name, "address": s.address,
                "gps_lat": s.gps_lat, "gps_lon": s.gps_lon,
                "devices_count": 0,
            }
            for s in sites
        ],
    }


@app.put("/api/admin/customers/{customer_id}")
def update_customer(customer_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404)
    for f in ["name", "contact_name", "contact_email", "contact_phone", "address", "notes"]:
        if f in payload:
            setattr(c, f, payload[f])
    db.commit()
    return {"status": "ok"}


@app.delete("/api/admin/customers/{customer_id}")
def delete_customer(customer_id: str, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404)
    if db.query(Site).filter_by(customer_id=customer_id).count():
        raise HTTPException(status_code=400, detail="Slet sites først")
    db.delete(c); db.commit()
    return {"status": "ok"}


# ── Sites ─────────────────────────────────────────────────────────────────

@app.get("/api/admin/sites")
def list_sites(_user=require_role("viewer"), db: Session = Depends(get_db)):
    sites = db.query(Site).all()
    return [
        {
            "id":            s.id,
            "customer_id":   s.customer_id,
            "customer_name": db.query(Customer).filter_by(id=s.customer_id).first().name if s.customer_id else "",
            "name":          s.name,
            "address":       s.address,
            "gps_lat":       s.gps_lat,
            "gps_lon":       s.gps_lon,
            "timezone":      s.timezone or "Europe/Copenhagen",
            "devices_count": 0,
        }
        for s in sites
    ]


@app.post("/api/admin/sites")
def create_site(payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    s = Site(
        id=str(_uuid.uuid4()),
        customer_id=payload.get("customer_id"),
        name=payload.get("name", "Nyt site"),
        address=payload.get("address"),
        gps_lat=payload.get("gps_lat"),
        gps_lon=payload.get("gps_lon"),
        timezone=payload.get("timezone", "Europe/Copenhagen"),
    )
    db.add(s); db.commit(); db.refresh(s)
    return {"id": s.id}


@app.get("/api/admin/sites/{site_id}")
def get_site(site_id: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    s = db.query(Site).filter_by(id=site_id).first()
    if not s:
        raise HTTPException(status_code=404)
    customer = db.query(Customer).filter_by(id=s.customer_id).first()
    devices  = db.query(Device).filter_by(site_id=site_id).all()
    return {
        "id": s.id, "customer_id": s.customer_id,
        "customer_name": customer.name if customer else "",
        "name": s.name, "address": s.address,
        "gps_lat": s.gps_lat, "gps_lon": s.gps_lon,
        "gps_alt": s.gps_alt if hasattr(s, "gps_alt") else None,
        "timezone": s.timezone or "Europe/Copenhagen",
        "notes": s.notes if hasattr(s, "notes") else None,
        "config_overrides": json.loads(s.config_overrides or "{}"),
        "devices": [
            {
                "device_id":    d.device_id,
                "camera_name":  d.camera_name,
                "camera_index": d.camera_index if hasattr(d, "camera_index") else 0,
                "status":       "online" if d.last_seen and (now_utc() - d.last_seen.replace(tzinfo=_tz.utc) if d.last_seen.tzinfo is None else d.last_seen).total_seconds() < 300 else "offline",
                "last_seen":    d.last_seen.isoformat() if d.last_seen else None,
            }
            for d in devices
        ],
    }


@app.put("/api/admin/sites/{site_id}")
def update_site(site_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    s = db.query(Site).filter_by(id=site_id).first()
    if not s:
        raise HTTPException(status_code=404)
    for f in ["name", "address", "gps_lat", "gps_lon", "timezone", "notes"]:
        if f in payload:
            setattr(s, f, payload[f])
    if hasattr(s, "gps_alt") and "gps_alt" in payload:
        s.gps_alt = payload["gps_alt"]
    if "config_overrides" in payload:
        s.config_overrides = json.dumps(payload["config_overrides"])
    db.commit()
    return {"status": "ok"}


@app.delete("/api/admin/sites/{site_id}")
def delete_site(site_id: str, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    s = db.query(Site).filter_by(id=site_id).first()
    if not s:
        raise HTTPException(status_code=404)
    if db.query(Device).filter_by(site_id=site_id).count():
        raise HTTPException(status_code=400, detail="Flyt enheder først")
    db.delete(s); db.commit()
    return {"status": "ok"}


# ── Device overrides ──────────────────────────────────────────────────────

@app.put("/api/admin/devices/{device_id}/overrides")
def update_device_overrides(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    if "camera_index" in payload and hasattr(device, "camera_index"):
        device.camera_index = payload["camera_index"]
    if "relay_gpio_camera" in payload and hasattr(device, "relay_gpio_camera"):
        device.relay_gpio_camera = payload["relay_gpio_camera"]
    if "relay_gpio_modem" in payload and hasattr(device, "relay_gpio_modem"):
        device.relay_gpio_modem = payload["relay_gpio_modem"]
    if "config_overrides" in payload:
        device.config_overrides = json.dumps(payload["config_overrides"])
    db.commit()
    return {"status": "ok"}


@app.get("/api/admin/devices/{device_id}")
def get_device_detail(device_id: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    online = device.last_seen and (now_utc() - ensure_utc(device.last_seen)).total_seconds() < 300
    diag   = db.query(Diagnostic).filter_by(device_id=device_id).order_by(Diagnostic.id.desc()).first()
    d_cfg  = json.loads(device.device_config or "{}")
    return {
        "device": {
            "device_id":        device.device_id,
            "location_name":    device.location_name,
            "ip_address":       device.ip_address,
            "status":           "online" if online else "offline",
            "last_seen":        device.last_seen.isoformat() if device.last_seen else None,
            "first_seen":       device.first_seen.isoformat() if device.first_seen else None,
            "customer_name":    device.customer_name,
            "site_name":        device.site_name,
            "camera_name":      device.camera_name,
            "camera_index":     device.camera_index if hasattr(device, "camera_index") else 0,
            "relay_gpio_camera":device.relay_gpio_camera if hasattr(device, "relay_gpio_camera") else 356,
            "relay_gpio_modem": device.relay_gpio_modem if hasattr(device, "relay_gpio_modem") else 361,
            "camera_model":     d_cfg.get("camera_model"),
            "app_version":      d_cfg.get("app_version"),
            "config_overrides": json.loads(device.config_overrides or "{}") if hasattr(device, "config_overrides") else {},
            "site_id":          device.site_id if hasattr(device, "site_id") else None,
        },
        "device_config": d_cfg,
        "update_requested": d_cfg.get("update_requested", False),
        "update_version":   d_cfg.get("update_version"),
        "backup_requested": d_cfg.get("backup_requested", False),
        "lab_camera_ready": d_cfg.get("lab_camera_ready", False),
    }


@app.delete("/api/admin/devices/{device_id}")
def delete_device(device_id: str, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    db.query(Capture).filter_by(device_id=device_id).delete()
    db.query(Diagnostic).filter_by(device_id=device_id).delete()
    db.query(Event).filter_by(device_id=device_id).delete()
    db.delete(device); db.commit()
    return {"status": "ok"}


@app.post("/api/admin/devices/{device_id}/clear-update")
def clear_update_flag(device_id: str, _user=require_role("admin"), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    if existing.get("update_requested"):
        existing["update_requested"] = False
        device.device_config = json.dumps(existing)
        db.commit()
        log.info("update_requested nulstillet for %s", device_id)
    return {"status": "ok"}


# ── Config defaults ───────────────────────────────────────────────────────

def _get_or_create_defaults(db: Session) -> ConfigDefaults:
    d = db.query(ConfigDefaults).first()
    if not d:
        d = ConfigDefaults(
            schedule    = json.dumps({"timezone": "Europe/Copenhagen", "capture_mode": "interval", "interval_minutes": 60, "active_hours": ["06:00", "21:00"]}),
            camera      = json.dumps({"relay_on_seconds_before": 10, "relay_off_seconds_after": 5, "delete_after_download": True, "gphoto2_port": "usb:"}),
            quality     = json.dumps({"check_enabled": True, "blur_threshold": 80, "dark_threshold": 25, "bright_threshold": 230}),
            storage     = json.dumps({"local_path": "/data/captures", "circular_buffer_gb": 50, "db_path": "/data/timelapse_edge.db"}),
            diagnostics = json.dumps({"heartbeat_interval_minutes": 60, "config_poll_interval_minutes": 5}),
            system      = json.dumps({"error_recovery_sleep_s": 30, "min_sleep_s": 60, "api_timeout_s": 15}),
        )
        db.add(d); db.commit(); db.refresh(d)
    return d


@app.get("/api/admin/config-defaults")
def get_config_defaults(_user=require_role("admin"), db: Session = Depends(get_db)):
    d = _get_or_create_defaults(db)
    return {
        "schedule":    json.loads(d.schedule    or "{}"),
        "camera":      json.loads(d.camera      or "{}"),
        "quality":     json.loads(d.quality     or "{}"),
        "storage":     json.loads(d.storage     or "{}"),
        "diagnostics": json.loads(d.diagnostics or "{}"),
        "system":      json.loads(d.system      or "{}") if hasattr(d, "system") else {},
    }


@app.put("/api/admin/config-defaults")
def update_config_defaults(payload: dict, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    d = _get_or_create_defaults(db)
    for section in ["schedule", "camera", "quality", "storage", "diagnostics", "system"]:
        if section in payload and hasattr(d, section):
            setattr(d, section, json.dumps(payload[section]))
    db.commit()
    return {"status": "ok"}



# ═══════════════════════════════════════════════════════════════════════════
# Multi-kamera node management
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/node/{device_id}/bootstrap-camera")
def bootstrap_camera(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Auto-bootstrap et sibling kamera på samme node.
    
    Opretter et nyt device med ID: {device_id}-{camera_index}
    Kopierer site_id, customer_name, site_name fra primary device.
    """
    primary = db.query(Device).filter_by(device_id=device_id).first()
    if not primary:
        raise HTTPException(status_code=404, detail="Primary device not found")

    camera_index    = payload.get("camera_index", 1)
    relay_gpio      = payload.get("relay_gpio_camera", 357)
    camera_name     = payload.get("camera_name", f"Kamera {camera_index + 1}")
    sibling_id      = f"{device_id}-{camera_index}"

    # Opret eller opdater sibling device
    sibling = db.query(Device).filter_by(device_id=sibling_id).first()
    if not sibling:
        sibling = Device(device_id=sibling_id)
        db.add(sibling)
        log.info("Auto-bootstrap nyt kamera: %s", sibling_id)
    else:
        log.info("Opdaterer sibling kamera: %s", sibling_id)

    # Kopier site/kunde info fra primary
    sibling.customer_name  = primary.customer_name
    sibling.site_name      = primary.site_name
    sibling.camera_name    = camera_name
    sibling.location_name  = primary.location_name
    sibling.last_seen      = now_utc()
    sibling.ip_address     = primary.ip_address

    if hasattr(sibling, "site_id"):
        sibling.site_id = primary.site_id if hasattr(primary, "site_id") else None
    if hasattr(sibling, "camera_index"):
        sibling.camera_index = camera_index
    if hasattr(sibling, "relay_gpio_camera"):
        sibling.relay_gpio_camera = relay_gpio

    # Sæt config_overrides med relay GPIO og ISO
    primary_overrides = json.loads(primary.config_overrides or "{}") if hasattr(primary, "config_overrides") else {}
    cam_overrides = dict(primary_overrides.get("camera", {}))
    cam_overrides["relay_gpio_pin"] = relay_gpio

    sibling.config_overrides = json.dumps({
        **primary_overrides,
        "camera": cam_overrides,
    })

    db.commit()
    log.info("Kamera bootstrapped: %s (GPIO %d)", sibling_id, relay_gpio)
    return {"status": "ok", "device_id": sibling_id, "camera_index": camera_index}


@app.get("/api/node/{device_id}/cameras")
def list_node_cameras(device_id: str, db: Session = Depends(get_db)):
    """Returner alle kameraer på samme fysiske node (primary + siblings)."""
    primary = db.query(Device).filter_by(device_id=device_id).first()
    if not primary:
        raise HTTPException(status_code=404)

    # Find alle siblings: device_id starter med primary device_id + "-"
    all_devices = db.query(Device).all()
    node_devices = [d for d in all_devices
                    if d.device_id == device_id or d.device_id.startswith(device_id + "-")]
    node_devices.sort(key=lambda d: d.device_id)

    return [
        {
            "device_id":    d.device_id,
            "camera_index": d.camera_index if hasattr(d, "camera_index") else 0,
            "camera_name":  d.camera_name,
            "relay_gpio":   d.relay_gpio_camera if hasattr(d, "relay_gpio_camera") else 356,
            "status":       "online" if d.last_seen and (now_utc() - (d.last_seen.replace(tzinfo=__import__("datetime").timezone.utc) if d.last_seen.tzinfo is None else d.last_seen)).total_seconds() < 300 else "offline",
        }
        for d in node_devices
    ]


@app.put("/api/node/{device_id}/multi-camera-config")
def set_multi_camera_config(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """Gem multi-kamera konfiguration på primary device.
    
    payload: {
        multi_camera_mode: "single" | "auto_bootstrap" | "manual",
        node_cameras: [{camera_index, relay_gpio_camera, camera_name}, ...]
    }
    """
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)

    existing = json.loads(device.device_config or "{}")
    existing["multi_camera_mode"] = payload.get("multi_camera_mode", "single")
    existing["node_cameras"]      = payload.get("node_cameras", [])
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("Multi-camera config opdateret for %s: %d kameraer",
             device_id, len(existing["node_cameras"]))
    return {"status": "ok"}


@app.post("/api/admin/backup/trigger")
def trigger_backup(_user=require_role("admin")):
    """Start backup i baggrunden."""
    global _backup_status
    if _backup_status.get("running"):
        return {"status": "already_running", "progress": _backup_status["progress"]}
    _backup_status = {"running": True, "progress": ["Starter backup..."], "file": None, "error": None}
    t = _threading.Thread(target=_run_backup, daemon=True)
    t.start()
    return {"status": "started"}

@app.get("/api/admin/backup/status")
def backup_status(_user=require_role("viewer")):
    """Hent backup status."""
    return {
        "running": _backup_status.get("running", False),
        "progress": _backup_status.get("progress", []),
        "ready": _backup_status.get("file") is not None,
        "error": _backup_status.get("error"),
        "filename": os.path.basename(_backup_status["file"]) if _backup_status.get("file") else None,
    }

@app.get("/api/admin/backup/download")
def download_backup(_user=require_role("admin")):
    """Download seneste backup fil."""
#Peter    import os
    f = _backup_status.get("file")
    if not f or not os.path.exists(f):
        raise HTTPException(status_code=404, detail="Ingen backup klar — kør trigger først")
    return _FileResponse(
        path=f,
        filename=os.path.basename(f),
        media_type="application/gzip"
    )

@app.put("/api/admin/backup/settings")
def update_backup_settings(payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Gem backup indstillinger (NAS sti, auto-backup interval)."""
    try:
#Peter        from sqlalchemy import text
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
def get_backup_settings(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Hent backup indstillinger."""
    try:
#Peter        from sqlalchemy import text
        keys = ["backup_nas_path", "backup_auto_interval", "backup_include_images"]
        result = {}
        for k in keys:
            row = db.execute(text("SELECT value FROM settings WHERE key=:k"), {"k": k}).fetchone()
            result[k] = row[0] if row else None
        return result
    except:
        return {"backup_nas_path": None, "backup_auto_interval": "manual", "backup_include_images": "false"}


@app.post("/api/admin/backup/trigger-edge/{device_id}")
def trigger_edge_backup(device_id: str, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Anmod edge enhed om at lave backup."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["backup_requested"] = True
    existing["backup_requested_at"] = now_utc().isoformat()
    existing.pop("backup_complete", None)
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "message": f"Backup anmodet for {device_id}"}


@app.post("/api/admin/backup/edge-complete/{device_id}")
def edge_backup_complete(device_id: str, payload: dict, _user=require_role("operator"), db: Session = Depends(get_db)):
    """Edge rapporterer at backup er komplet — flyt til backup mappe lokalt på Pi 5."""
    import os as _os
    import shutil as _sh
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)

    filename = payload.get("filename", "")

    # Filen er landet i SFTP incoming — flyt den lokalt til backup mappe
    SFTP_INCOMING = "/data/sftp/incoming"
    local_sftp_path = _os.path.join(SFTP_INCOMING, "_backups", device_id, filename)

    nas = _get_nas_path()
    backup_dest = nas if (nas and _os.path.isdir(nas)) else "/home/peter/backup"
    _os.makedirs(backup_dest, exist_ok=True)

    final_path = local_sftp_path
    if _os.path.exists(local_sftp_path):
        try:
            dest = _os.path.join(backup_dest, filename)
            _sh.move(local_sftp_path, dest)
            final_path = dest
            log.info("Edge backup flyttet til: %s", dest)
        except Exception as e:
            log.warning("Kunne ikke flytte edge backup: %s", e)
    else:
        log.warning("Edge backup fil ikke fundet: %s", local_sftp_path)

    existing = json.loads(device.device_config or "{}")
    existing["backup_requested"] = False
    existing["backup_complete"] = {
        "filename": filename,
        "size_kb":  payload.get("size_kb"),
        "path":     final_path,
        "sftp_path": sftp_path,
        "at":       now_utc().isoformat(),
    }
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("Edge backup komplet for %s: %s (%d KB)",
             device_id, filename, payload.get("size_kb", 0))
    return {"status": "ok", "path": final_path}


@app.get("/api/admin/backup/edge-status/{device_id}")
def edge_backup_status(device_id: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    """Hent backup status for en edge enhed."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    cfg = json.loads(device.device_config or "{}")
    return {
        "requested":      cfg.get("backup_requested", False),
        "requested_at":   cfg.get("backup_requested_at"),
        "complete":       cfg.get("backup_complete"),
    }


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
#Peter     import re as _re
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
def lab_clear_command(device_id: str, _user=require_role("operator"), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    cfg = json.loads(device.device_config or "{}")
    cfg.pop("lab_command", None)
    device.device_config = json.dumps(cfg)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/devices/{device_id}/lab-clear-params")
def lab_clear_params(device_id: str, _user=require_role("operator"), db: Session = Depends(get_db)):
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
    _user=require_role("viewer"),
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
        from sqlalchemy import func
        tz = "Europe/Copenhagen"
        local_ts = func.timezone(tz, Capture.captured_at)
        captures = q.filter(
            func.extract("year",  local_ts) == year,
            func.extract("month", local_ts) == month,
            func.extract("day",   local_ts) == day,
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
        from sqlalchemy import func as _func, text as _text
        tz = "Europe/Copenhagen"
        local_ts = func.timezone(tz, Capture.captured_at)
        rows = db.query(
            func.extract("year",  local_ts).label("year"),
            func.extract("month", local_ts).label("month"),
            func.extract("day",   local_ts).label("day"),
            func.count(Capture.id).label("count")
        ).filter(
            Capture.device_id == device_id,
            Capture.captured_at.isnot(None)
        ).group_by("year", "month", "day").order_by("year", "month", "day").all()
        return [
            {"year": int(r.year), "month": int(r.month), "day": int(r.day), "count": r.count}
            for r in rows
        ]


# ═══════════════════════════════════════════════════════════════════════════
# System Settings
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/admin/settings")
def get_settings(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Returner alle system settings."""
    rows = db.execute(text("SELECT key, value FROM settings")).fetchall()
    return {row[0]: row[1] for row in rows}

@app.put("/api/admin/settings")
def update_settings(payload: dict, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    """Opdater system settings."""
    for key, value in payload.items():
        existing = db.execute(text("SELECT id FROM settings WHERE key = :k"), {"k": key}).fetchone()
        if existing:
            db.execute(text("UPDATE settings SET value = :v WHERE key = :k"), {"v": str(value), "k": key})
        else:
            db.execute(text("INSERT INTO settings (key, value) VALUES (:k, :v)"), {"k": key, "v": str(value)})
    db.commit()
    return {"ok": True}


@app.put("/api/admin/devices/{device_id}/assign")
def assign_device(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Tildel en device til et site og en kunde."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    site_id = payload.get("site_id")
    if site_id:
        site = db.query(Site).filter_by(id=site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Site ikke fundet")
        customer = db.query(Customer).filter_by(id=site.customer_id).first()
        device.site_id      = site_id
        device.site_name    = site.name
        device.customer_name = customer.name if customer else ""
    else:
        device.site_id       = None
        device.site_name     = None
        device.customer_name = None
    if "camera_name" in payload:
        device.camera_name = payload["camera_name"]
    db.commit()
    return {"status": "ok"}


# ── Slet capture ──────────────────────────────────────────────────────────────

@app.delete("/api/admin/captures/{capture_id}")
def delete_capture(capture_id: int, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Slet et billede: fil, thumbnail, sidecar JSON og DB-record."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")

    deleted = {"file": False, "thumbnail": False, "sidecar": False, "db": False}

    # Slet billedfil
    path = _find_image(capture.device_id, capture.filename)
    if path and path.exists():
        try:
            path.unlink()
            deleted["file"] = True
        except Exception as exc:
            log.warning("Kunne ikke slette fil %s: %s", path, exc)

        # Slet thumbnail
        thumb = _thumbs_dir_for(path) / capture.filename
        if thumb.exists():
            try:
                thumb.unlink()
                deleted["thumbnail"] = True
            except Exception as exc:
                log.warning("Kunne ikke slette thumbnail %s: %s", thumb, exc)

        # Slet sidecar JSON
        sidecar = path.with_suffix(".json")
        if sidecar.exists():
            try:
                sidecar.unlink()
                deleted["sidecar"] = True
            except Exception as exc:
                log.warning("Kunne ikke slette sidecar %s: %s", sidecar, exc)

    # Slet fra DB
    db.delete(capture)
    db.commit()
    deleted["db"] = True

    log.info("Capture %d slettet: %s", capture_id, deleted)
    return {"status": "ok", "capture_id": capture_id, "deleted": deleted}


@app.post("/api/admin/captures/bulk-delete")
def delete_captures_bulk(payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Slet flere captures på én gang. payload: {ids: [int]}"""
    ids = payload.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="Ingen ids angivet")
    results = []
    for cid in ids:
        try:
            capture = db.query(Capture).filter(Capture.id == cid).first()
            if not capture:
                results.append({"id": cid, "status": "not_found"})
                continue
            path = _find_image(capture.device_id, capture.filename)
            if path and path.exists():
                path.unlink(missing_ok=True)
                (_thumbs_dir_for(path) / capture.filename).unlink(missing_ok=True)
                path.with_suffix(".json").unlink(missing_ok=True)
            db.delete(capture)
            results.append({"id": cid, "status": "ok"})
        except Exception as exc:
            results.append({"id": cid, "status": "error", "error": str(exc)})
    db.commit()
    log.info("Bulk slettet %d captures", len([r for r in results if r["status"] == "ok"]))
    return {"status": "ok", "results": results}



# ── EXIF fra billedfil ────────────────────────────────────────────────────────

@app.get("/api/exif/{device_id}/{filename}")
def get_exif(device_id: str, filename: str):
    """Læs komplet EXIF metadata fra billedfil via exifread."""
    src = _find_image(device_id, filename)
    if not src or not src.exists():
        raise HTTPException(status_code=404, detail="Billede ikke fundet")
    try:
        import exifread
        with open(str(src), "rb") as f:
            tags = exifread.process_file(f, details=True)
        if not tags:
            return {"exif": {}, "note": "Ingen EXIF i fil"}
        exif = {}
        for key, value in tags.items():
            try:
                exif[key] = str(value)
            except Exception:
                exif[key] = "—"
        return {"exif": exif, "count": len(exif)}
    except Exception as exc:
        log.warning("EXIF læsning fejl %s: %s", filename, exc)
        return {"exif": {}, "error": str(exc)}



# ── Diagnostics historik ──────────────────────────────────────────────────

@app.get("/api/admin/devices/{device_id}/diagnostics/history")
def get_diagnostics_history(
    device_id: str,
    days: int = 7,
    limit: int = 500,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    """Hent diagnostics time-series for en device (seneste N dage)."""
    from datetime import timedelta
    since = now_utc() - timedelta(days=days)
    rows = (
        db.query(Diagnostic)
        .filter(Diagnostic.device_id == device_id, Diagnostic.recorded_at >= since)
        .order_by(Diagnostic.recorded_at.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "ts":                  r.recorded_at.isoformat() if r.recorded_at else None,
            "cpu_temp_c":          r.cpu_temp_c,
            "cpu_load_pct":        r.cpu_load_pct,
            "ram_used_mb":         r.ram_used_mb,
            "disk_used_gb":        r.disk_used_gb,
            "ssd_used_pct":        r.ssd_used_pct,
            "ssd_free_gb":         r.ssd_free_gb,
            "ntp_offset_s":        r.ntp_offset_s,
            "connectivity":        r.connectivity,
            "uptime_s":            r.uptime_s,
            "upload_queue":        r.upload_queue,
            "service_restarts":    r.service_restarts,
            "cam_battery_pct":     r.cam_battery_pct,
            "cam_shutter_cnt":     r.cam_shutter_cnt,
            "cam_shutter_pct":     r.cam_shutter_pct,
            "cam_shutter_alarm":   r.cam_shutter_alarm,
            "cam_available_shots": r.cam_available_shots,
            "capture_total":       r.capture_total,
            "capture_passed":      r.capture_passed,
            "capture_uploaded":    r.capture_uploaded,
        }
        for r in rows
    ]


# ── EXIF statistik ────────────────────────────────────────────────────────

@app.get("/api/admin/captures/stats/exif")
def get_exif_stats(device_id: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    """EXIF-baseret statistik: ISO, lukkertid, blænde fordeling."""
    rows = (
        db.query(Capture.exif_data)
        .filter(Capture.device_id == device_id, Capture.exif_data.isnot(None))
        .order_by(Capture.captured_at.desc())
        .limit(1000)
        .all()
    )
    iso_dist, shutter_dist, aperture_dist, lens_dist = {}, {}, {}, {}
    for (exif_json,) in rows:
        try:
            exif = _json.loads(exif_json)
        except Exception:
            continue
        if iso := exif.get("EXIF ISOSpeedRatings"):
            iso_dist[iso] = iso_dist.get(iso, 0) + 1
        if sh := exif.get("EXIF ExposureTime"):
            shutter_dist[sh] = shutter_dist.get(sh, 0) + 1
        if ap := exif.get("EXIF FNumber"):
            aperture_dist[ap] = aperture_dist.get(ap, 0) + 1
        if ln := exif.get("EXIF LensModel"):
            lens_dist[ln] = lens_dist.get(ln, 0) + 1
    def top(d, n=15):
        return sorted(d.items(), key=lambda x: -x[1])[:n]
    return {
        "total_with_exif": len(rows),
        "iso":      [{"value": k, "count": v} for k, v in top(iso_dist)],
        "shutter":  [{"value": k, "count": v} for k, v in top(shutter_dist)],
        "aperture": [{"value": k, "count": v} for k, v in top(aperture_dist)],
        "lens":     [{"value": k, "count": v} for k, v in top(lens_dist)],
    }


# ── Slet captures ─────────────────────────────────────────────────────────────

@app.delete("/api/admin/captures/{capture_id}")
def delete_capture(capture_id: int, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Slet et billede: fil, thumbnail, sidecar og DB-record."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")
    path = _find_image(capture.device_id, capture.filename)
    if path and path.exists():
        path.unlink(missing_ok=True)
        (_thumbs_dir_for(path) / capture.filename).unlink(missing_ok=True)
        path.with_suffix(".json").unlink(missing_ok=True)
    db.delete(capture)
    db.commit()
    log.info("Capture %d slettet: %s", capture_id, capture.filename)
    return {"status": "ok", "capture_id": capture_id}


@app.post("/api/admin/captures/bulk-delete")
def delete_captures_bulk(payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Bulk-slet captures. Body: {ids: [int]}"""
    ids = payload.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="Ingen ids")
    ok = 0
    for cid in ids:
        try:
            c = db.query(Capture).filter(Capture.id == cid).first()
            if not c:
                continue
            path = _find_image(c.device_id, c.filename)
            if path and path.exists():
                path.unlink(missing_ok=True)
                (_thumbs_dir_for(path) / c.filename).unlink(missing_ok=True)
                path.with_suffix(".json").unlink(missing_ok=True)
            db.delete(c)
            ok += 1
        except Exception as exc:
            log.warning("Bulk slet fejl id=%d: %s", cid, exc)
    db.commit()
    log.info("Bulk slettet %d captures", ok)
    return {"status": "ok", "deleted": ok}


@app.put("/api/admin/users/{user_id}/password")
def change_user_password(
    user_id: int,
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")
    pw = payload.get("password", "")
    policy = _get_password_policy(db)
    errors = _validate_password(pw, policy)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    u.password_hash = _hash_password(pw)
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/users/{user_id}")
def delete_user(
    user_id: int,
    current_user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")
    if u.username == current_user.username:
        raise HTTPException(status_code=400, detail="Du kan ikke slette dig selv")
    db.delete(u)
    db.commit()
    return {"ok": True}