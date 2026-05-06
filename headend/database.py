# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — database.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 3.0.0
# Dato     : 06. maj 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   3.0.0  06-maj-2026  Sprint C: User, Camera, DeviceAssignment,
#                       SshTunnelLog, PendingUpdate tabeller
#   2.1.0  13-apr-2026  Capture tabel udvidet med lokation/orientering:
#                         gps_lat, gps_lon, gps_alt, azimuth_deg, tilt_deg
#                         mount_height_m, fov_horizontal_deg, fov_vertical_deg
#                         perspective, xmp_written, sha256_pre_xmp
#   2.0.0  10-apr-2026  Customer, Site, ConfigDefaults, Settings tabeller
#   1.0.0  09-apr-2026  Initial schema
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — Headend Database
==================================
SQLite for test phase, PostgreSQL-ready for production.
Switch by changing DATABASE_URL in .env:
  SQLite:     sqlite:///./timelapse_headend.db
  PostgreSQL: postgresql://user:pass@localhost/timelapse_db
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
import os

load_dotenv()

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./timelapse_headend.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Enable WAL mode for SQLite — power-loss resilience
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    id              = Column(Integer, primary_key=True)
    device_id       = Column(String(50), unique=True, nullable=False, index=True)
    location_name   = Column(String(200))
    tenant_id       = Column(String(50), default="default")
    camera_model    = Column(String(100))
    driver_name     = Column(String(50))
    ip_address      = Column(String(50))
    last_seen       = Column(DateTime)
    first_seen      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    api_token       = Column(String(500))
    config_version  = Column(String(50))
    device_config   = Column(Text)
    customer_name   = Column(String(200))
    site_name       = Column(String(200))
    site_id         = Column(String(36))
    camera_index    = Column(Integer, default=0)
    camera_name     = Column(String(200))
    installed_date  = Column(String(10))
    installed_time  = Column(String(5))
    app_version     = Column(String(50))
    status          = Column(String(20), default="unknown")  # online/offline/unknown
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Capture(Base):
    __tablename__ = "captures"

    id              = Column(Integer, primary_key=True)
    device_id       = Column(String(50), nullable=False, index=True)
    filename        = Column(String(200))
    sha256          = Column(String(64))
    captured_at     = Column(DateTime, index=True)
    filesize        = Column(Integer)
    camera_model    = Column(String(100))
    quality_flag    = Column(String(20))
    quality_passed  = Column(Boolean)
    blur_score      = Column(Float)
    brightness_mean = Column(Float)
    uploaded        = Column(Boolean, default=False)
    exposure_time   = Column(String(20))
    aperture        = Column(String(20))
    iso             = Column(Integer)
    received_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Lokation og orientering (fra site/kamera config) ─────────────────
    gps_lat             = Column(Float)
    gps_lon             = Column(Float)
    gps_alt_m           = Column(Float)
    gps_source          = Column(String(20))       # manual | gpsd
    azimuth_deg         = Column(Float)            # 0-360°, 0=Nord
    tilt_deg            = Column(Float)            # negativ=ned, 0=vandret
    mount_height_m      = Column(Float)            # meter over terræn
    fov_horizontal_deg  = Column(Float)            # horisontalt synsfelt
    fov_vertical_deg    = Column(Float)            # vertikalt synsfelt
    perspective         = Column(String(50))       # eye_level|high_angle etc.

    # ── XMP og integritet ─────────────────────────────────────────────────
    sha256_pre_xmp      = Column(String(64))       # SHA-256 inden XMP
    xmp_written         = Column(Boolean, default=False)
    sidecar_path        = Column(String(500))


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id              = Column(Integer, primary_key=True)
    device_id       = Column(String(50), nullable=False, index=True)
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    cpu_temp_c      = Column(Float)
    cpu_load_pct    = Column(Float)
    ram_used_mb     = Column(Integer)
    disk_used_gb    = Column(Float)
    battery_v       = Column(Float)
    solar_v         = Column(Float)
    connectivity    = Column(String(20))
    uptime_s        = Column(Integer)
    capture_total   = Column(Integer)
    capture_passed  = Column(Integer)
    capture_uploaded= Column(Integer)
    # Extended diagnostics
    ntp_offset_s    = Column(Float)
    ssd_total_gb    = Column(Float)
    ssd_used_pct    = Column(Float)
    ssd_free_gb     = Column(Float)
    service_restarts= Column(Integer)
    upload_queue    = Column(Integer)
    # Camera diagnostics
    cam_battery_pct = Column(Integer)
    cam_shutter_cnt = Column(Integer)
    cam_shutter_pct = Column(Float)
    cam_shutter_alarm = Column(Boolean, default=False)
    cam_available_shots = Column(Integer)
    cam_lens_name   = Column(String(100))
    cam_config_json = Column(Text)
    cam_drift_json  = Column(Text)


class Event(Base):
    __tablename__ = "events"

    id          = Column(Integer, primary_key=True)
    device_id   = Column(String(50), nullable=False, index=True)
    event_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    level       = Column(String(20))
    category    = Column(String(50))
    message     = Column(Text)
    extra       = Column(Text)  # JSON






class User(Base):
    """RBAC brugere — super_admin, admin, operator, viewer."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    email         = Column(String(200), unique=True)
    password_hash = Column(String(200), nullable=False)
    role          = Column(String(50), default="viewer")   # super_admin|admin|operator|viewer
    customer_id   = Column(String(36))                     # null = adgang til alle kunder
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login    = Column(DateTime)


class Camera(Base):
    """Logisk kamera — adskilt fra fysisk Orange Pi hardware."""
    __tablename__ = "cameras"

    id            = Column(String(36), primary_key=True)   # UUID
    site_id       = Column(String(36), index=True)
    customer_id   = Column(String(36), index=True)
    camera_name   = Column(String(200), nullable=False)
    serial_number = Column(String(100))
    model         = Column(String(100))
    notes         = Column(Text)
    config        = Column(Text, default="{}")             # JSON camera-specifikke config overrides
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    retired_at    = Column(DateTime)                       # null = aktiv


class DeviceAssignment(Base):
    """Historik: hvilken Orange Pi kørte hvilket logisk kamera hvornår."""
    __tablename__ = "device_assignments"

    id            = Column(Integer, primary_key=True)
    device_id     = Column(String(50), nullable=False, index=True)   # MAC-baseret
    camera_id     = Column(String(36), nullable=False, index=True)   # → Camera.id
    assigned_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    unassigned_at = Column(DateTime)                                 # null = aktiv assignment
    assigned_by   = Column(String(100))                              # brugernavn
    notes         = Column(Text)


class SshTunnelLog(Base):
    """Audit log over SSH tunnel sessioner — SABSA Accountability."""
    __tablename__ = "ssh_tunnel_log"

    id           = Column(Integer, primary_key=True)
    device_id    = Column(String(50), nullable=False, index=True)
    event        = Column(String(50))    # connected|disconnected|failed|denied
    remote_port  = Column(Integer)
    local_port   = Column(Integer, default=22)
    initiated_by = Column(String(100))   # "edge_auto" | "admin:<username>"
    duration_s   = Column(Integer)       # udfyldes ved disconnect
    event_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    extra        = Column(Text)          # JSON: fejlbesked, IP osv.


class PendingUpdate(Base):
    """Opdateringer der afventer godkendelse eller deployment."""
    __tablename__ = "pending_updates"

    id          = Column(Integer, primary_key=True)
    update_type = Column(String(50))    # app_security|os_security|app_updates|os_updates
    version     = Column(String(100))
    description = Column(Text)
    severity    = Column(String(20))    # critical|high|medium|low
    scope       = Column(String(20))    # global|customer|site|device
    scope_id    = Column(String(36))    # customer_id, site_id eller device_id
    status      = Column(String(30), default="pending")
    # pending|approved|rejected|deployed|rolled_back
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    approved_at = Column(DateTime)
    approved_by = Column(String(100))
    deployed_at = Column(DateTime)
    rollback_at = Column(DateTime)


class BootstrapToken(Base):
    """Éngangsbrug bootstrap tokens til provisionering af nye edge-enheder."""
    __tablename__ = "bootstrap_tokens"

    id           = Column(Integer, primary_key=True)
    token        = Column(String(100), unique=True, nullable=False, index=True)
    device_label = Column(String(200))     # menneskevenligt navn (fx "NVJ17c Kamera 1")
    site_id      = Column(String(36))
    customer_id  = Column(String(36))
    camera_name  = Column(String(200))
    created_by   = Column(String(100))
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at   = Column(DateTime, nullable=False)
    used_at      = Column(DateTime)        # udfyldes når token bruges
    used_by_device = Column(String(50))    # device_id der brugte token
    revoked      = Column(Boolean, default=False)


class Customer(Base):
    __tablename__ = "customers"
    id               = Column(String(36), primary_key=True)
    name             = Column(String(200), nullable=False)
    contact_name     = Column(String(200))
    contact_email    = Column(String(200))
    contact_phone    = Column(String(50))
    address          = Column(String(500))
    notes            = Column(Text)
    config_overrides = Column(Text, default="{}")
    # ── Sikkerhed og compliance ───────────────────────────────────────
    mfa_required          = Column(Boolean, default=False)
    mfa_method            = Column(String(50), default="none")   # totp|hardware_key|sms|none
    mfa_documented_at     = Column(DateTime)
    mfa_documented_by     = Column(String(100))
    data_classification   = Column(String(30), default="internal")


class Site(Base):
    __tablename__ = "sites"
    id               = Column(String(36), primary_key=True)
    customer_id      = Column(String(36))
    name             = Column(String(200), nullable=False)
    address          = Column(String(500))
    gps_lat          = Column(Float)
    gps_lon          = Column(Float)
    gps_alt          = Column(Float)
    timezone         = Column(String(50), default="Europe/Copenhagen")
    notes            = Column(Text)
    config_overrides = Column(Text, default="{}")
    # ── SFTP isolation og compliance ──────────────────────────────────
    sftp_user             = Column(String(100))          # fx sftp_nvj17c
    sftp_chroot_verified  = Column(Boolean, default=False)
    sftp_chroot_verified_at = Column(DateTime)
    mfa_required          = Column(Boolean, default=False)
    mfa_method            = Column(String(50), default="none")
    mfa_documented_at     = Column(DateTime)
    mfa_documented_by     = Column(String(100))
    data_classification   = Column(String(30), default="internal")


class ConfigDefaults(Base):
    __tablename__ = "config_defaults"
    id          = Column(Integer, primary_key=True)
    schedule    = Column(Text)
    camera      = Column(Text)
    quality     = Column(Text)
    storage     = Column(Text)
    diagnostics = Column(Text)
    system      = Column(Text)


class Settings(Base):
    __tablename__ = "settings"
    id    = Column(Integer, primary_key=True)
    key   = Column(String(100), unique=True)
    value = Column(Text)


def ensure_utc(dt):
    """Ensure datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt) -> datetime | None:
    """Ensure datetime is timezone-aware UTC. Fixes naive vs aware mismatch."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
