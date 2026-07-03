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
Produktion: PostgreSQL (timelapse_db).
DATABASE_URL sættes via launchd plist:
  postgresql://timelapse@localhost/timelapse_db
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
    String, Text, create_engine, event,
    LargeBinary, BigInteger, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://timelapse@localhost/timelapse_db")

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10")),
        "connect_args": {
            "options": " ".join([
                f"-c idle_in_transaction_session_timeout={os.getenv('DB_IDLE_TX_TIMEOUT_MS', '300000')}",
                f"-c statement_timeout={os.getenv('DB_STATEMENT_TIMEOUT_MS', '60000')}",
            ])
        },
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

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
    customer_id     = Column(String(36), index=True)
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
    # ── Zero-touch provisioning (Sprint D) ───────────────────────────────
    hardware_model    = Column(String(50))    # "rpi4", "orangepi4pro", "rpi5", "jetson-orin-nano", …
    enrollment_state  = Column(String(20), default="active")  # "unassigned" | "active"
    ssh_pubkey        = Column(Text)          # ed25519 public key genereret ved first-boot


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
    ai_result           = Column(Text)
    ai_analyzed_at      = Column(DateTime)
    ai_tags             = Column(Text)


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
    customer_id   = Column(String(36))
    totp_secret   = Column(String(64))
    mfa_enabled   = Column(Boolean, default=False)                     # null = adgang til alle kunder
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
    # ── AI-kontekst (v10) — fodres til vision-prompten pr. billede ─────────
    # baseline_description: fritekst om hvad kameraet NORMALT viser (synsfelt,
    #   faste objekter, hvad der er forventeligt) → modellen kan vurdere afvigelser
    #   (ny bil i indkørslen, personer i baggård om natten osv.).
    # context_notes: ekstra driftsnoter til AI (fx "nabogrund under byggeri",
    #   "vej med trafik i baggrunden") der ikke skal udløse falske anomalier.
    baseline_description = Column(Text)
    context_notes        = Column(Text)
    # ── Selvlærende baseline (v11) — auto-genereret fra kameraets tag-historik ──
    # auto_baseline: AI-kontekst udledt statistisk af hvad kameraet NORMALT viser
    #   (persistente tags, dag/nat-mønster, sæson, og for dynamiske sites
    #   udvikling/fremskridt). Genberegnes løbende → "selvlærende".
    #   baseline_description (håndskrevet) vinder hvis sat; ellers bruges auto.
    auto_baseline        = Column(Text)
    auto_baseline_at     = Column(DateTime)
    auto_baseline_kind   = Column(String(20))   # 'static' | 'dynamic'
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    retired_at    = Column(DateTime)                       # null = aktiv
    # Netværkskonfiguration (v7 migration)
    network_type  = Column(String(20), default="ethernet") # 'ethernet' | 'wifi' | 'usb_modem'
    wifi_ssid     = Column(String(200))
    wifi_password = Column(String(200))
    wifi_country  = Column(String(2), default="DK")
    # SSH keypair + reverse tunnel (v8 migration) — unik per enhed, genereret ved provisioning
    ssh_private_key     = Column(Text,    default=None)
    ssh_public_key      = Column(Text,    default=None)
    reverse_tunnel_port = Column(Integer, default=None)
    # BT PAN TOTP (v9 migration) — device-specifikt secret genereret ved enrollment
    # Factory default bruges indtil enrolled: JBSWY3DPEHPK3PXP / sid=factory-default
    bt_totp_secret      = Column(String(64), default=None)
    bt_totp_sid         = Column(String(100), default=None)


class DeviceAssignment(Base):
    """Historik: hvilken Orange Pi kørte hvilket logisk kamera hvornår."""
    __tablename__ = "device_assignments"

    id              = Column(Integer, primary_key=True)
    device_id       = Column(String(50), nullable=False, index=True)   # MAC-baseret
    camera_id       = Column(String(36), nullable=False, index=True)   # → Camera.id
    assigned_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    unassigned_at   = Column(DateTime)                                 # null = aktiv assignment
    assigned_by     = Column(String(100))                              # brugernavn
    assignment_type = Column(String(20), default="manual")             # "auto" | "manual"
    notes           = Column(Text)


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
    rollback_at       = Column(DateTime)
    environment       = Column(String(20), default="production")  # test|production
    target_device_ids = Column(Text)          # JSON liste af specifikke device_ids
    deployed_count    = Column(Integer, default=0)
    failed_count      = Column(Integer, default=0)


class ChangeTicket(Base):
    """Signeret, menneske- og maskinlæsbart change ticket."""
    __tablename__ = "change_tickets"

    id                 = Column(Integer, primary_key=True)
    ticket_id          = Column(String(80), unique=True, nullable=False, index=True)
    title              = Column(String(200), nullable=False)
    summary            = Column(Text)
    pending_update_id  = Column(Integer, index=True)
    update_type        = Column(String(50))
    severity           = Column(String(20))
    environment        = Column(String(20), default="production")
    scope              = Column(String(20))
    scope_id           = Column(String(36))
    status             = Column(String(30), default="draft", index=True)
    # draft|ready|pending_approval|approved|rejected|deployed|rolled_back|cancelled
    source_commit      = Column(String(64))
    source_ref         = Column(String(200))
    artifact_id        = Column(String(80))
    sbom_ref           = Column(String(500))
    test_evidence_ref  = Column(String(500))
    rollback_plan      = Column(Text)
    reboot_required    = Column(Boolean, default=False)
    maintenance_window = Column(String(50))
    human_readable_md  = Column(Text)
    machine_json       = Column(Text)
    content_sha256     = Column(String(64), index=True)
    signature          = Column(Text)
    signed_by          = Column(String(200))
    signed_at          = Column(DateTime)
    created_by         = Column(String(100))
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at         = Column(DateTime)


class ChangeApproval(Base):
    """Godkendelser/afvisninger knyttet til et change ticket."""
    __tablename__ = "change_approvals"

    id                 = Column(Integer, primary_key=True)
    ticket_id          = Column(String(80), nullable=False, index=True)
    decision           = Column(String(30), nullable=False)  # approved|rejected|cancelled
    decided_by         = Column(String(100), nullable=False)
    decided_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    approval_context   = Column(Text)       # JSON: IP, MFA, role, customer/site context
    signature          = Column(Text)
    signed_payload_sha256 = Column(String(64))
    notes              = Column(Text)


class UpdateArtifact(Base):
    """Release artifact eller OS/app update manifest distribueret via Headend."""
    __tablename__ = "update_artifacts"

    id                 = Column(Integer, primary_key=True)
    artifact_id        = Column(String(80), unique=True, nullable=False, index=True)
    artifact_type      = Column(String(50), nullable=False)  # app|os|dependency|config
    version            = Column(String(100))
    source_commit      = Column(String(64))
    source_ref         = Column(String(200))
    filename           = Column(String(500))
    storage_path       = Column(String(1000))
    size_bytes         = Column(Integer)
    sha256             = Column(String(64), nullable=False, index=True)
    manifest_json      = Column(Text)
    sbom_ref           = Column(String(500))
    signature          = Column(Text)
    signed_by          = Column(String(200))
    signed_at          = Column(DateTime)
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class UpdateTarget(Base):
    """Per-device/per-camera deployment status for en update eller change."""
    __tablename__ = "update_targets"
    __table_args__ = (
        UniqueConstraint("pending_update_id", "device_id", name="uq_update_targets_update_device"),
    )

    id                 = Column(Integer, primary_key=True)
    pending_update_id  = Column(Integer, index=True)
    ticket_id          = Column(String(80), index=True)
    artifact_id        = Column(String(80), index=True)
    device_id          = Column(String(50), nullable=False, index=True)
    camera_id          = Column(String(36), index=True)
    customer_id        = Column(String(36), index=True)
    site_id            = Column(String(36), index=True)
    status             = Column(String(30), default="pending", index=True)
    # pending|queued|downloading|verifying|installing|deployed|failed|rollback_requested|rolled_back
    attempt_count      = Column(Integer, default=0)
    last_error         = Column(Text)
    current_version    = Column(String(100))
    target_version     = Column(String(100))
    rollback_version   = Column(String(100))
    started_at         = Column(DateTime)
    completed_at       = Column(DateTime)
    rollback_at        = Column(DateTime)
    last_report_at     = Column(DateTime)
    report_json        = Column(Text)


class UpdateJobRecord(Base):
    """Persistente background jobs for update-flow, så status overlever Headend restart."""
    __tablename__ = "update_jobs"

    id            = Column(Integer, primary_key=True)
    job_id        = Column(String(80), unique=True, nullable=False, index=True)
    kind          = Column(String(50), nullable=False, index=True)
    title         = Column(String(200))
    running       = Column(Boolean, default=False, index=True)
    status        = Column(String(30), default="queued", index=True)
    phase         = Column(String(50), default="queued")
    progress      = Column(Integer, default=0)
    requested_by  = Column(String(100))
    message       = Column(Text)
    payload_json  = Column(Text)
    result_json   = Column(Text)
    error         = Column(Text)
    stdout_tail   = Column(Text)
    stderr_tail   = Column(Text)
    started_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    finished_at   = Column(DateTime)
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class KeyCredential(Base):
    """Lifecycle-styret credential til Headend, Edge, SSH, API og signing."""
    __tablename__ = "key_credentials"

    id                 = Column(Integer, primary_key=True)
    credential_id      = Column(String(80), unique=True, nullable=False, index=True)
    entity_type        = Column(String(30), nullable=False, index=True)   # headend|edge|user|service
    entity_id          = Column(String(100), nullable=False, index=True)  # CMDB/device/user ref
    key_type           = Column(String(30), nullable=False, index=True)   # api|ssh|signing|bootstrap
    label              = Column(String(200))
    status             = Column(String(30), default="active", index=True) # active|revoked|expired|rotated
    scopes_json        = Column(Text)
    public_key         = Column(Text)
    fingerprint        = Column(String(128), index=True)
    secret_hash        = Column(String(128), index=True)
    algorithm          = Column(String(50))
    compliance_domains = Column(String(200), default="SABSA,IEC62443,ISO27000,NIS2,CRA")
    created_by         = Column(String(100))
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at         = Column(DateTime, index=True)
    last_used_at       = Column(DateTime)
    last_used_from     = Column(String(100))
    use_count          = Column(Integer, default=0)
    revoked_at         = Column(DateTime)
    revoked_by         = Column(String(100))
    revoke_reason      = Column(Text)
    rotated_from_id    = Column(String(80), index=True)
    metadata_json      = Column(Text)


class KeyAuditEvent(Base):
    """Auditspor for nøglelivscyklus og compliance-evidens."""
    __tablename__ = "key_audit_events"

    id                 = Column(Integer, primary_key=True)
    credential_id      = Column(String(80), index=True)
    event_type         = Column(String(50), nullable=False, index=True)
    actor              = Column(String(100))
    entity_type        = Column(String(30), index=True)
    entity_id          = Column(String(100), index=True)
    details_json       = Column(Text)
    occurred_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class WebAuthnCredential(Base):
    """FIDO2/WebAuthn credentials — Windows Hello, Touch ID, Face ID."""
    __tablename__ = "webauthn_credentials"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, nullable=False)
    credential_id = Column(LargeBinary, nullable=False, unique=True)
    public_key    = Column(LargeBinary, nullable=False)
    sign_count    = Column(BigInteger, nullable=False, default=0)
    device_name   = Column(String(200))
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class BootstrapToken(Base):
    """Bootstrap tokens til provisionering af nye edge-enheder.

    Understøtter to modes:
      - Single-use (max_uses=1):  klassisk token til én enhed
      - Batch/multi-use (max_uses>1):  token bagt ind i et disk-image;
        kan bruges af op til max_uses enheder (typisk 50-500)
    """
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
    used_at      = Column(DateTime)        # tidspunkt for FØRSTE brug
    used_by_device = Column(String(50))    # første device_id der brugte token
    revoked      = Column(Boolean, default=False)
    # ── Multi-use / batch-tokens (til image-indbagte tokens) ─────────────
    max_uses     = Column(Integer, default=1)   # 1 = single-use, N = batch
    use_count    = Column(Integer, default=0)   # antal gange brugt hidtil
    token_type   = Column(String(20), default="single")  # "single" | "batch"
    # ── Kamera lokation (Sprint D) ────────────────────────────────────────
    camera_id    = Column(String(36), index=True)  # → Camera.id


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
    session_policy = Column(Text)


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

class DeviceInventory(Base):
    """
    CMDB-registrering af en edge-enhed.

    Oprettes første gang edge rapporterer inventar (POST /api/inventory/{device_id}).
    Opdateres ved hvert genstart af edge-agenten.

    Relation: 1:1 med devices.device_id (ikke FK constraint — edge kan rapportere
    før den er fuldt registreret, men headend-siden validerer device_id).
    """
    __tablename__ = "device_inventory"

    id                      = Column(Integer, primary_key=True)
    device_id               = Column(String(50), unique=True, nullable=False, index=True)

    # ── Miljø ────────────────────────────────────────────────────────────
    environment             = Column(String(20), default="production")
    # Mulige værdier: lab | staging | production

    # ── Hardware (rapporteret af edge) ───────────────────────────────────
    hardware_model          = Column(String(100))   # "Orange Pi 4 Pro"
    soc_model               = Column(String(50))    # "RK3588S" | "Allwinner H3"
    cpu_cores               = Column(Integer)
    ram_mb                  = Column(Integer)
    mac_address             = Column(String(20))    # primær ethernet MAC
    serial_number           = Column(String(100))   # /proc/cpuinfo Serial
    hostname                = Column(String(100))

    # ── OS / Software ────────────────────────────────────────────────────
    os_name                 = Column(String(100))   # "Ubuntu 24.04.1 LTS"
    kernel_version          = Column(String(100))   # "6.1.0-armbian"
    firmware_version        = Column(String(200))
    python_version          = Column(String(20))    # "3.12.3"
    app_version             = Column(String(50))    # TimeLapse Pro edge version
    package_manager         = Column(String(50))
    os_packages             = Column(Text)
    venv_packages           = Column(Text)
    # JSON: {"gphoto2": "2.5.28", "paramiko": "3.4.0", ...}
    software_inventory      = Column(Text)

    # ── Storage ──────────────────────────────────────────────────────────
    boot_storage_type       = Column(String(20))    # emmc | sd | nvme
    boot_storage_total_gb   = Column(Float)
    boot_storage_used_pct   = Column(Float)
    data_partition_path     = Column(String(100))   # "/data"
    data_partition_total_gb = Column(Float)
    data_partition_used_pct = Column(Float)

    # ── Netværk ──────────────────────────────────────────────────────────
    primary_interface       = Column(String(20))    # "end0" | "eth0"
    wifi_capable            = Column(Boolean, default=False)
    wifi_ssid               = Column(String(100))   # hvis tilsluttet WiFi

    # ── Signering ────────────────────────────────────────────────────────
    gpg_fingerprint         = Column(String(64))
    # GPG-nøglens fingerprint — til verifikation af pakke-signaturer

    # ── Lokation (pre-Location Model) ────────────────────────────────────
    location_id             = Column(String(36))
    # Udfyldes af admin efter provisioning. FK til kommende locations-tabel.

    # ── Provisioning ─────────────────────────────────────────────────────
    provisioned_at          = Column(DateTime)
    provisioned_by          = Column(String(100))   # admin-brugernavn

    # ── Tracking ─────────────────────────────────────────────────────────
    inventory_reported_at   = Column(DateTime)
    # Tidspunkt for seneste edge-rapportering

    notes                   = Column(Text)

    created_at              = Column(DateTime,
                                default=lambda: datetime.now(timezone.utc))
    updated_at              = Column(DateTime,
                                default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc))


class BreakGlassAccount(Base):
    """
    Break-the-glass SSH-konto til nødadgang på edge-enheder.

    Én konto pr. device pr. admin. Adgangskoden:
      - Genereres tilfældigt (24 tegn, alphanumerisk)
      - Krypteres med Fernet (AES-128-CBC + HMAC-SHA256) inden lagring
      - Vises ÉN gang ved checkout (GET /api/cmdb/{device_id}/break-glass/checkout)
      - Roteres AUTOMATISK ved checkout — næste checkout giver nyt password
      - Rotation sker i baggrunden via headend → edge SSH-kommando (TODO: Sprint CMDB-2)

    Nøgle: env-variabel BREAK_GLASS_ENC_KEY (Fernet-format, base64url 32 bytes)
    Generér med: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    __tablename__ = "break_glass_accounts"
    __table_args__ = (
        UniqueConstraint("device_id", "admin_username",
                         name="uq_breakglass_device_admin"),
    )

    id              = Column(Integer, primary_key=True)
    device_id       = Column(String(50), nullable=False, index=True)
    admin_username  = Column(String(100), nullable=False)
    # Ejerskab: hvilken admin-konto der har adgang til denne instans

    # ── SSH-konto på edge ────────────────────────────────────────────────
    ssh_username    = Column(String(50), default="emergency")
    # Bruges til: ssh emergency@<edge-ip>
    # Denne bruger oprettes på edge ved provisioning (TODO: edge-side)

    password_enc    = Column(Text, nullable=False)
    # Fernet-krypteret adgangskode — ALDRIG vist i logs eller API-response
    # undtagen ved eksplicit checkout

    public_key      = Column(Text)
    # Admin's SSH public key uploadet til edge som authorized_keys (backup)
    # Gør at admin kan logge ind uden password hvis password-rotation fejler

    # ── Livscyklus ───────────────────────────────────────────────────────
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc))
    last_used_at    = Column(DateTime)
    last_used_by    = Column(String(100))   # admin der sidst checkede ud
    rotated_at      = Column(DateTime)      # tidspunkt for seneste rotation
    expires_at      = Column(DateTime)
    # Udløb — headend advarer 7 dage før. None = udløber ikke.

    # ── Audit ────────────────────────────────────────────────────────────
    checkout_count  = Column(Integer, default=0)
    rotation_reason = Column(Text)
    # Årsag til seneste rotation (manuel, checkout, scheduled)


class AiBatchJob(Base):
    """Gemini Batch API job — bulk AI-genanalyse til ~50% af normal pris.
    Asynkront: submitted → running → succeeded|failed|cancelled|expired.
    Polles periodisk af baggrundstråd i main.py (se _ai_batch_poller_loop).
    """
    __tablename__ = "ai_batch_jobs"

    id              = Column(String(36), primary_key=True)   # UUID
    gemini_job_name = Column(String(200))    # "batches/xxxxx" fra Google
    status          = Column(String(30), default="submitting")
    # submitting | running | succeeded | failed | cancelled | expired

    capture_ids     = Column(Text, default="[]")   # JSON liste — rækkefølge matcher batch-keys
    cloud_model     = Column(String(100))

    total_count     = Column(Integer, default=0)
    success_count   = Column(Integer, default=0)
    error_count     = Column(Integer, default=0)

    requested_by    = Column(String(100))
    notify_on_complete = Column(Boolean, default=True)

    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at    = Column(DateTime)
    completed_at    = Column(DateTime)

    error_message   = Column(Text)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        try:
            db.rollback()
        except Exception:
            pass
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
