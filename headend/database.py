# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — database.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 2.1.0
# Dato     : 13. april 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
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

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./timelapse_headend.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite only
)

# Enable WAL mode for SQLite — power-loss resilience
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
