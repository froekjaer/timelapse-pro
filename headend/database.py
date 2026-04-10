"""
TimeLapse Pro — Headend Database Models v2
==========================================
Hierarkisk model: customers → sites → devices
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, create_engine, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship

DATABASE_URL = "sqlite:////home/peter/headend/timelapse_headend.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def now_utc():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id               = Column(String(36), primary_key=True)
    name             = Column(String(200), nullable=False)
    contact_name     = Column(String(200))
    contact_email    = Column(String(200))
    contact_phone    = Column(String(50))
    address          = Column(String(500))
    config_overrides = Column(Text, default="{}")  # JSON — Kunde-niveau config
    notes            = Column(Text)
    created_at       = Column(DateTime, default=now_utc)
    updated_at       = Column(DateTime, default=now_utc, onupdate=now_utc)

    sites = relationship("Site", back_populates="customer", cascade="all, delete-orphan")


class Site(Base):
    __tablename__ = "sites"

    id               = Column(String(36), primary_key=True)
    customer_id      = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    name             = Column(String(200), nullable=False)
    address          = Column(String(500))
    gps_lat          = Column(Float)
    gps_lon          = Column(Float)
    gps_alt          = Column(Float)
    timezone         = Column(String(50), default="Europe/Copenhagen")
    config_overrides = Column(Text, default="{}")  # JSON — Site-niveau config
    notes            = Column(Text)
    created_at       = Column(DateTime, default=now_utc)
    updated_at       = Column(DateTime, default=now_utc, onupdate=now_utc)

    customer = relationship("Customer", back_populates="sites")
    devices  = relationship("Device", back_populates="site")


class Device(Base):
    __tablename__ = "devices"

    id                  = Column(Integer, primary_key=True)
    device_id           = Column(String(50), unique=True, nullable=False, index=True)
    site_id             = Column(String(36), ForeignKey("sites.id"), index=True)
    camera_index        = Column(Integer, default=0)       # 0=første, 1=andet, 2=tredje kamera
    relay_gpio_camera   = Column(Integer, default=356)     # GPIO pin til kamera relay
    relay_gpio_modem    = Column(Integer, default=361)     # GPIO pin til modem relay
    location_name       = Column(String(200))
    camera_name         = Column(String(200))
    customer_name       = Column(String(200))              # Beholdes for bagud-kompatibilitet
    site_name           = Column(String(200))              # Beholdes for bagud-kompatibilitet
    camera_model        = Column(String(100))
    driver_name         = Column(String(50))
    ip_address          = Column(String(50))
    last_seen           = Column(DateTime)
    first_seen          = Column(DateTime, default=now_utc)
    api_token           = Column(String(500))
    config_version      = Column(String(50))
    config_overrides    = Column(Text, default="{}")      # JSON — Kamera-niveau config (ISO, shutter osv.)
    device_config       = Column(Text)                    # JSON — Runtime state (LAB, backup flags osv.)
    status              = Column(String(20), default="unknown")
    shutter_speed       = Column(String(20))
    focal_length        = Column(Float)
    app_version         = Column(String(50))
    created_at          = Column(DateTime, default=now_utc)

    site     = relationship("Site", back_populates="devices")
    captures = relationship("Capture", back_populates="device",
                           foreign_keys="Capture.device_id",
                           primaryjoin="Device.device_id == Capture.device_id")


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
    shutter_speed   = Column(String(20))
    focal_length    = Column(Float)
    received_at     = Column(DateTime, default=now_utc)

    device = relationship("Device", back_populates="captures",
                         foreign_keys=[device_id],
                         primaryjoin="Capture.device_id == Device.device_id")


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id               = Column(Integer, primary_key=True)
    device_id        = Column(String(50), nullable=False, index=True)
    recorded_at      = Column(DateTime, default=now_utc, index=True)
    cpu_temp_c       = Column(Float)
    cpu_load_pct     = Column(Float)
    ram_used_mb      = Column(Integer)
    disk_used_gb     = Column(Float)
    battery_v        = Column(Float)
    solar_v          = Column(Float)
    connectivity     = Column(String(20))
    wifi_ssid        = Column(String(100))
    uptime_s         = Column(Integer)
    capture_total    = Column(Integer)
    capture_passed   = Column(Integer)
    capture_uploaded = Column(Integer)
    ntp_offset_s     = Column(Float)
    ssd_total_gb     = Column(Float)
    ssd_used_pct     = Column(Float)
    ssd_free_gb      = Column(Float)
    service_restarts = Column(Integer)
    upload_queue     = Column(Integer)
    cam_shutter_cnt  = Column(Integer)
    cam_shutter_pct  = Column(Float)
    cam_shutter_alarm= Column(Boolean, default=False)
    cam_battery_pct  = Column(Integer)
    cam_drift_json   = Column(Text)
    cam_config_json  = Column(Text)
    cam_lens_name    = Column(String(200))
    cam_available_shots = Column(Integer)


class Event(Base):
    __tablename__ = "events"

    id         = Column(Integer, primary_key=True)
    device_id  = Column(String(50), nullable=False, index=True)
    recorded_at= Column(DateTime, default=now_utc, index=True)
    level      = Column(String(20))
    category   = Column(String(50))
    message    = Column(Text)


class ConfigDefaults(Base):
    __tablename__ = "config_defaults"

    id          = Column(Integer, primary_key=True)
    schedule    = Column(Text, default="{}")
    camera      = Column(Text, default="{}")
    quality     = Column(Text, default="{}")
    storage     = Column(Text, default="{}")
    diagnostics = Column(Text, default="{}")
    updated_at  = Column(DateTime, default=now_utc)


class Settings(Base):
    __tablename__ = "settings"

    key   = Column(String(100), primary_key=True)
    value = Column(Text)


def create_tables():
    Base.metadata.create_all(bind=engine)
