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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import json
import logging
#import os
import base64
import hashlib
import hmac
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datetime import timezone as _tz

#Peter:
import re as _re
from sqlalchemy import and_, false as _sql_false, func, or_, text
import subprocess as _subprocess
import threading as _threading
import json as _json
import os, tempfile
from collections import defaultdict as _defaultdict
import gzip as _gzip
import lzma as _lzma
import urllib.request as _urlrequest
import functools as _functools
# ── Auth imports (Sprint C) ───────────────────────────────────────────────
from jose import JWTError, jwt as _jwt
import bcrypt as _bcrypt_lib
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Security
import secrets as _secrets

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


TIMELAPSE_ENV = os.getenv("TIMELAPSE_ENV", "lab").strip().lower()
_jwt_secret_from_env = os.getenv("JWT_SECRET")
if TIMELAPSE_ENV in {"prod", "production"}:
    if not _jwt_secret_from_env or len(_jwt_secret_from_env) < 32:
        raise RuntimeError(
            "JWT_SECRET must be explicitly set to at least 32 characters in production"
        )

JWT_SECRET    = _jwt_secret_from_env or _secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 12   # access token levetid
COOKIE_NAME   = "tl_session"
OPENWEBUI_COOKIE_NAME = "tl_openwebui_access"
OPENWEBUI_COOKIE_DOMAIN = os.getenv("OPENWEBUI_COOKIE_DOMAIN", "")
OPENWEBUI_PUBLIC_URL = os.getenv("OPENWEBUI_PUBLIC_URL", "http://127.0.0.1:8080/")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
def ensure_utc(dt):
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=_tz.utc)

from importer import router as import_router
from ai.settings_api import settings_router
from siem import router as siem_router, start_headend_log_collector
from cmdb import router as cmdb_router, report_inventory as _cmdb_report_inventory
from itim import router as itim_router, start_itim_collector
from database import (
    BootstrapToken,
    ChangeApproval, ChangeTicket, UpdateArtifact, UpdateTarget,
    Capture, Camera, Customer, ConfigDefaults, Device, DeviceAssignment,
    DeviceInventory, Diagnostic, Event, KeyAuditEvent, KeyCredential,
    PendingUpdate, Settings, Site, SshTunnelLog, UpdateJobRecord, User,
    AiBatchJob,
    SessionLocal, create_tables, get_db, now_utc
)
import uuid as _uuid




# ── Logging ───────────────────────────────────────────────────────────────────
import os as _os
from logging.handlers import TimedRotatingFileHandler as _TRFHandler

_LOG_DIR = os.getenv("TIMELAPSE_LOG_DIR", str(Path.home() / "Library" / "Logs" / "timelapse"))
_os.makedirs(_LOG_DIR, exist_ok=True)

_fmt = logging.Formatter(
    fmt="%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler = _TRFHandler(
    filename=f"{_LOG_DIR}/headend.log",
    when="midnight",
    backupCount=30,     # 30 dages rotation
    encoding="utf-8",
)
_file_handler.setFormatter(_fmt)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
log = logging.getLogger("headend")

# ── App ───────────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

def _sanitize_device_id(device_id: str) -> str:
    """Sanitér device_id — afvis path traversal forsøg."""
    import re as _re2
    if not device_id:
        raise HTTPException(status_code=400, detail="Ugyldigt device_id")
    # Kun tilladte tegn: bogstaver, tal, bindestreg, underscore
    if not _re2.match(r'^[A-Za-z0-9_-]{3,60}$', device_id):
        raise HTTPException(status_code=400, detail="Ugyldigt device_id format")
    # Afvis path traversal
    if '..' in device_id or '/' in device_id or '\\' in device_id:
        raise HTTPException(status_code=400, detail="Ugyldigt device_id")
    return device_id


def _sanitize_filename(filename: str) -> str:
    """Sanitér filnavn til lokal lagring."""
    import re as _re2
    name = os.path.basename(filename or "").strip()
    name = _re2.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name or name in {".", ".."} or ".." in name:
        raise HTTPException(status_code=400, detail="Ugyldigt filnavn")
    return name[:180]


app = FastAPI(
    title       = "TimeLapse Pro Headend",
    description = "Central control API for TimeLapse Pro edge nodes",
    version     = "1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", os.getenv("BASE_URL", "http://127.0.0.1:5173"))

app.add_middleware(
    CORSMiddleware,
    allow_origins      = [ALLOWED_ORIGIN],
    allow_methods      = ["*"],
    allow_headers      = ["*"],
    allow_credentials  = True,
)

def _baseline_recompute_loop(run_hour: int = 3) -> None:
    """Natlig genberegning af selvlærende kamera-baselines på de rene tags.
    Kører én gang i døgnet ved run_hour (lokal tid). Robust: tjekker hver 30. min
    og kører kun hvis dagens kørsel mangler. Idempotent."""
    import time as _t
    from datetime import datetime as _dt
    last_date = None
    _t.sleep(120)  # lille forsinkelse efter opstart
    while True:
        try:
            now = _dt.now()
            if now.hour >= run_hour and last_date != now.date():
                last_date = now.date()
                from database import SessionLocal as _SL
                from ai.camera_profile import recompute_all_baselines
                _db = _SL()
                try:
                    res = recompute_all_baselines(_db, apply=True)
                    log.info("Natlig baseline-genberegning: %s", res)
                finally:
                    _db.close()
        except Exception as _bl_exc:
            log.warning("Natlig baseline-genberegning fejl: %s", _bl_exc)
        _t.sleep(1800)


@app.on_event("startup")
def startup():
    create_tables()
    start_headend_log_collector()
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

    # Sprint C v3: MFA + SFTP isolation kolonner — kører altid (F-01 fix)
    try:
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
        engine_v3 = __import__('database').engine
        with engine_v3.connect() as conn:
            for table, col, typ in new_cols_v3:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                    conn.commit()
                    log.info("DB migration v3: %s.%s tilføjet", table, col)
                except Exception:
                    pass  # Kolonnen findes allerede
    except Exception as exc_v3:
        log.warning("DB migration v3 fejl (ikke kritisk): %s", exc_v3)

    # Auth/session policy kolonner — eksisterende installationer kan mangle dem.
    try:
        _eng_auth = __import__('database').engine
        _auth_cols = [
            ("config_defaults", "session_policy", "TEXT"),
            ("config_defaults", "system",         "TEXT"),
        ]
        with _eng_auth.connect() as _conn_auth:
            for _tbl, _col, _typ in _auth_cols:
                try:
                    _conn_auth.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    _conn_auth.commit()
                    log.info("DB migration auth: %s.%s tilføjet", _tbl, _col)
                except Exception:
                    pass
    except Exception as _exc_auth:
        log.warning("DB migration auth fejl: %s", _exc_auth)

    # ── DB migration v9: BT PAN TOTP per kamera ──────────────────────────
    try:
        _eng_v9 = __import__('database').engine
        _v9_cols = [
            ("cameras", "bt_totp_secret", "VARCHAR(64)"),
            ("cameras", "bt_totp_sid",    "VARCHAR(100)"),
        ]
        with _eng_v9.connect() as _conn_v9:
            for _tbl, _col, _typ in _v9_cols:
                try:
                    _conn_v9.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    _conn_v9.commit()
                    log.info("DB migration v9: %s.%s tilføjet", _tbl, _col)
                except Exception:
                    pass  # allerede der
    except Exception as _exc_v9:
        log.warning("DB migration v9 fejl: %s", _exc_v9)

    # ── DB migration v10: AI-kontekst/baseline per kamera ────────────────
    try:
        _eng_v10 = __import__('database').engine
        _v10_cols = [
            ("cameras", "baseline_description", "TEXT"),
            ("cameras", "context_notes",        "TEXT"),
        ]
        with _eng_v10.connect() as _conn_v10:
            for _tbl, _col, _typ in _v10_cols:
                try:
                    _conn_v10.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    _conn_v10.commit()
                    log.info("DB migration v10: %s.%s tilføjet", _tbl, _col)
                except Exception:
                    pass  # allerede der
    except Exception as _exc_v10:
        log.warning("DB migration v10 fejl: %s", _exc_v10)

    # ── DB migration v11: selvlærende baseline per kamera ────────────────
    try:
        _eng_v11 = __import__('database').engine
        _v11_cols = [
            ("cameras", "auto_baseline",      "TEXT"),
            ("cameras", "auto_baseline_at",   "TIMESTAMP"),
            ("cameras", "auto_baseline_kind", "VARCHAR(20)"),
        ]
        with _eng_v11.connect() as _conn_v11:
            for _tbl, _col, _typ in _v11_cols:
                try:
                    _conn_v11.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    _conn_v11.commit()
                    log.info("DB migration v11: %s.%s tilføjet", _tbl, _col)
                except Exception:
                    pass
    except Exception as _exc_v11:
        log.warning("DB migration v11 fejl: %s", _exc_v11)

    # ── DB migration v12: kamera-lokation + tenant direkte på captures ───
    # Additiv/nullable — ingen eksisterende adfærd ændres. Se
    # Claude_Kritisk_Statusgennemgang_2026-07-03.md §2.4/§2.5. Backfill af
    # historiske rækker sker IKKE her (kan være mange tusind rækker) — se
    # headend/tools/backfill_capture_camera_customer.py, som køres separat
    # og eksplicit (matcher projektets øvrige backfill-værktøjer).
    try:
        _eng_v12 = __import__('database').engine
        _v12_cols = [
            ("captures", "camera_id",   "VARCHAR(36)"),
            ("captures", "customer_id", "VARCHAR(36)"),
        ]
        with _eng_v12.connect() as _conn_v12:
            for _tbl, _col, _typ in _v12_cols:
                try:
                    _conn_v12.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    _conn_v12.commit()
                    log.info("DB migration v12: %s.%s tilføjet", _tbl, _col)
                except Exception:
                    pass  # allerede der
            for _idx_name, _idx_sql in [
                ("ix_captures_camera_id",   "CREATE INDEX IF NOT EXISTS ix_captures_camera_id ON captures (camera_id)"),
                ("ix_captures_customer_id", "CREATE INDEX IF NOT EXISTS ix_captures_customer_id ON captures (customer_id)"),
            ]:
                try:
                    _conn_v12.execute(text(_idx_sql))
                    _conn_v12.commit()
                except Exception:
                    pass
    except Exception as _exc_v12:
        log.warning("DB migration v12 fejl: %s", _exc_v12)

    # ── DB migration v13: site_id direkte på captures (fase 4) ──────────
    # Additiv/nullable — samme mønster som v12. Fuldender kunde/site/kamera-
    # lokations-hierarkiet på Capture-niveau, så en fremtidig, mere restriktiv
    # RBAC-granularitet end "hele kunden" kan indføres uden at skulle
    # genudlede historikken via et live join (se R16 i RISK_ASSESSMENT_v10.md
    # for hvorfor det er vigtigt at fryse dette ved capture-tidspunktet).
    # Bevidst KUN tagging i denne omgang — bruges endnu ikke til håndhævelse.
    try:
        _eng_v13 = __import__('database').engine
        with _eng_v13.connect() as _conn_v13:
            try:
                _conn_v13.execute(text("ALTER TABLE captures ADD COLUMN site_id VARCHAR(36)"))
                _conn_v13.commit()
                log.info("DB migration v13: captures.site_id tilføjet")
            except Exception:
                pass  # allerede der
            try:
                _conn_v13.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_captures_site_id ON captures (site_id)"
                ))
                _conn_v13.commit()
            except Exception:
                pass
    except Exception as _exc_v13:
        log.warning("DB migration v13 fejl: %s", _exc_v13)

    # ── AI SETUP ──────────────────────────────────────────────────────────
    try:
        run_ai_migration(engine)
        setup_ai(get_db, _find_image)
        setup_ai_router(get_db, _find_image, get_current_user, _allowed_capture_device_ids)
        app.include_router(ai_router)
        log.info("AI integration klar — Ollama: http://localhost:11434")
    except Exception as _ai_err:
        log.warning("AI integration ikke tilgængelig: %s", _ai_err)

    # ── Tag-vokabular: seed/migrér ved OPSTART, ikke kun ved første billede ──
    # TagVocabulary instantieres normalt først inde i AI-workerens per-billede
    # loop — det betyder seeding/oprydning af vokabularet (fx dansk→engelsk
    # migreringen) ikke kører før et billede rent faktisk analyseres. Kald den
    # derfor eksplicit her, så det altid sker pålideligt ved genstart.
    try:
        from ai.tag_vocabulary import TagVocabulary
        TagVocabulary(get_db)
        log.info("Tag-vokabular initialiseret ved opstart")
    except Exception as _vocab_err:
        log.warning("Kunne ikke initialisere tag-vokabular ved opstart: %s", _vocab_err)

    log.info("TimeLapse Pro Headend started — database ready")

    # ── GitHub tag poller ───────────────────────────────────────────────────
    try:
        interval_h = float(os.getenv("TIMELAPSE_GIT_TAG_POLL_INTERVAL_HOURS", "1"))
        t = _threading.Thread(
            target=_git_tag_poller_loop,
            args=(interval_h,),
            name="git-tag-poller",
            daemon=True,
        )
        t.start()
        log.info("GitHub tag poller startet (interval=%.1fh)", interval_h)
    except Exception as _gtp_err:
        log.warning("Kunne ikke starte GitHub tag poller: %s", _gtp_err)

    # ── Auto OS bundle poller ───────────────────────────────────────────────
    try:
        interval_m = float(os.getenv("TIMELAPSE_OS_BUNDLE_AUTO_POLL_MINUTES", "10"))
        t_os = _threading.Thread(
            target=_os_bundle_auto_poller_loop,
            args=(interval_m,),
            name="os-bundle-auto-poller",
            daemon=True,
        )
        t_os.start()
        log.info("OS bundle auto-poller startet (interval=%.0fm)", interval_m)
    except Exception as _obp_err:
        log.warning("Kunne ikke starte OS bundle auto-poller: %s", _obp_err)

    # ── AI batch-job poller (Gemini Batch API) ───────────────────────────────
    try:
        interval_m = float(os.getenv("TIMELAPSE_AI_BATCH_POLL_MINUTES", "5"))
        t_batch = _threading.Thread(
            target=_ai_batch_poller_loop,
            args=(interval_m,),
            name="ai-batch-poller",
            daemon=True,
        )
        t_batch.start()
    except Exception as _abp_err:
        log.warning("Kunne ikke starte AI batch-poller: %s", _abp_err)

    # ── ITIM / Observability collector ───────────────────────────────────────
    try:
        start_itim_collector()
    except Exception as _itim_err:
        log.warning("Kunne ikke starte ITIM collector: %s", _itim_err)

    # ── Natlig baseline-genberegning (selvlærende kamera-baselines) ──────────
    try:
        if os.getenv("TIMELAPSE_BASELINE_RECOMPUTE_ENABLED", "true").lower() in ("1", "true", "yes", "on"):
            bl_hour = int(os.getenv("TIMELAPSE_BASELINE_RECOMPUTE_HOUR", "3"))
            _threading.Thread(target=_baseline_recompute_loop, args=(bl_hour,),
                              name="baseline-recompute", daemon=True).start()
            log.info("Natlig baseline-genberegning aktiv (kl. %02d lokal tid)", bl_hour)
    except Exception as _bl_err:
        log.warning("Kunne ikke starte natlig baseline-genberegning: %s", _bl_err)


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

class EdgeProvisioningPrepareRequest(BaseModel):
    device_id: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    site_id: Optional[str] = None
    site_name: Optional[str] = None
    camera_id: Optional[str] = None        # UUID til eksisterende Camera (lokation)
    camera_name: Optional[str] = None
    location_name: Optional[str] = None
    note: Optional[str] = None
    expires_hours: Optional[int] = 48
    headend_url: Optional[str] = None
    # Netværkskonfiguration (v7)
    network_type: Optional[str] = "ethernet"   # 'ethernet' | 'wifi' | 'usb_modem'
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    wifi_country: Optional[str] = "DK"

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
    sha256_pre_xmp: Optional[str] = None
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
    edge_ai_result: Optional[dict] = None
    edge_ai_engine: Optional[str] = None
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

def _cookie_header(name: str, value: str, max_age: int, *, domain: str | None = None) -> str:
    parts = [
        f"{name}={value}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        f"Max-Age={max_age}",
    ]
    if domain:
        parts.append(f"Domain={domain}")
    if COOKIE_SECURE:
        parts.append("Secure")
    return "; ".join(parts)

def _delete_cookie_header(name: str, *, domain: str | None = None) -> str:
    parts = [
        f"{name}=",
        "Path=/",
        "HttpOnly",
        "Max-Age=0",
        "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
    ]
    if domain:
        parts.append(f"Domain={domain}")
    if COOKIE_SECURE:
        parts.append("Secure")
    return "; ".join(parts)

def _session_payload(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    return _decode_token(token) if token else None

def _session_is_mfa_verified(payload: dict | None) -> bool:
    if not payload:
        return False
    if payload.get("mfa_verified") is True:
        return True
    amr = payload.get("amr") or []
    if isinstance(amr, str):
        amr = [amr]
    return bool({"totp", "webauthn", "passkey", "fido2"}.intersection(set(amr)))


_SESSION_POLICY_DEFAULTS = {
    "session_duration_hours": 12,
    "remember_me_days":       30,
    "absolute_max_days":      90,
    "rolling_enabled":        True,
    "remember_me_allowed":    True,
    "mfa_required":           False,
    "webauthn_required":      False,
    "mfa_required_by_role": {
        "super_admin": True,
        "admin":       True,
        "operator":    False,
        "viewer":      False,
    },
    "mfa_exempt_usernames": [],
}


def _normalise_session_policy(policy: dict | None) -> dict:
    merged = _deep_merge(_SESSION_POLICY_DEFAULTS, policy or {}) if "_deep_merge" in globals() else {
        **_SESSION_POLICY_DEFAULTS,
        **(policy or {}),
    }
    role_defaults = dict(_SESSION_POLICY_DEFAULTS["mfa_required_by_role"])
    role_defaults.update((merged.get("mfa_required_by_role") or {}))
    merged["mfa_required_by_role"] = role_defaults
    exemptions = merged.get("mfa_exempt_usernames") or []
    if isinstance(exemptions, str):
        exemptions = [v.strip() for v in exemptions.split(",") if v.strip()]
    if not isinstance(exemptions, list):
        exemptions = []
    merged["mfa_exempt_usernames"] = sorted({str(v).strip() for v in exemptions if str(v).strip()})
    return merged


def _policy_from_json(raw: object) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _merge_session_policy(policy: dict, overrides_raw: object) -> dict:
    overrides = _policy_from_json(overrides_raw)
    session_policy = overrides.get("session_policy") if isinstance(overrides, dict) else None
    if isinstance(session_policy, dict):
        return _normalise_session_policy(_deep_merge(policy, session_policy))
    return _normalise_session_policy(policy)


def _resolve_session_policy(
    db: Session,
    user: User | None = None,
    *,
    customer_id: str | None = None,
    site_id: str | None = None,
    camera_id: str | None = None,
) -> dict:
    policy = _normalise_session_policy({})
    try:
        defaults = db.query(ConfigDefaults).first()
        if defaults and getattr(defaults, "session_policy", None):
            policy = _normalise_session_policy(_deep_merge(policy, _policy_from_json(defaults.session_policy)))
    except Exception as exc:
        log.warning("session_policy global resolver fejl: %s", exc)

    effective_customer_id = customer_id or getattr(user, "customer_id", None)
    site = None
    camera = None

    try:
        if camera_id:
            camera = db.query(Camera).filter_by(id=camera_id).first()
            if camera:
                site_id = site_id or camera.site_id
                effective_customer_id = effective_customer_id or camera.customer_id
        if site_id:
            site = db.query(Site).filter_by(id=site_id).first()
            if site:
                effective_customer_id = effective_customer_id or site.customer_id
        if effective_customer_id:
            customer = db.query(Customer).filter_by(id=effective_customer_id).first()
            if customer:
                policy = _merge_session_policy(policy, customer.config_overrides)
        if site:
            policy = _merge_session_policy(policy, site.config_overrides)
        if camera and camera.config:
            cam_cfg = _policy_from_json(camera.config)
            if isinstance(cam_cfg.get("session_policy"), dict):
                policy = _normalise_session_policy(_deep_merge(policy, cam_cfg["session_policy"]))
    except Exception as exc:
        log.warning("session_policy hierarki resolver fejl: %s", exc)
    return _normalise_session_policy(policy)


def _mfa_required_for_role(policy: dict, role: str | None) -> bool:
    if bool(policy.get("mfa_required")):
        return True
    return bool((policy.get("mfa_required_by_role") or {}).get(role or "", False))


def _mfa_required_for_user(db: Session, user: User | None, **scope) -> bool:
    if not user:
        return False
    policy = _resolve_session_policy(db, user, **scope)
    exempt = {str(v).strip().lower() for v in (policy.get("mfa_exempt_usernames") or [])}
    if user.username.strip().lower() in exempt:
        return False
    return _mfa_required_for_role(policy, user.role)


def _user_has_totp(user: User | None) -> bool:
    return bool(user and user.mfa_enabled and user.totp_secret)


def _user_has_partial_mfa(user: User | None) -> bool:
    return bool(user and (user.mfa_enabled or user.totp_secret) and not _user_has_totp(user))

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
    request: Request,
    db: Session = Depends(get_db)
):
    """FastAPI dependency — returnerer current user fra cookie eller None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = _decode_token(token)
    if not payload:
        return None
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
    def _check(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
        return user
    return Depends(_check)


def _is_platform_admin(user: User | None) -> bool:
    """Return True for users allowed to see all tenants."""
    if user is None:
        return False
    return user.role == "super_admin" or (user.role == "admin" and not user.customer_id)


def _ensure_customer_access(user: User | None, customer_id: str | None) -> None:
    """Enforce tenant boundary for customer scoped records."""
    if _is_platform_admin(user):
        return
    if not user or not user.customer_id or customer_id != user.customer_id:
        raise HTTPException(status_code=403, detail="Ingen adgang til denne kunde")


def _ensure_site_access(db: Session, user: User | None, site_id: str | None) -> Site:
    site = db.query(Site).filter_by(id=site_id).first()
    if not site:
        raise HTTPException(status_code=404)
    _ensure_customer_access(user, site.customer_id)
    return site


def _visible_customer_query(db: Session, user: User | None):
    q = db.query(Customer)
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Customer.id == "__none__")
    return q.filter(Customer.id == user.customer_id)


def _visible_site_query(db: Session, user: User | None):
    q = db.query(Site)
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Site.id == "__none__")
    return q.filter(Site.customer_id == user.customer_id)


def _visible_device_query(db: Session, user: User | None):
    q = db.query(Device)
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Device.device_id == "__none__")
    site_ids = db.query(Site.id).filter(Site.customer_id == user.customer_id)
    return q.filter(or_(Device.customer_id == user.customer_id, Device.site_id.in_(site_ids)))





@app.get("/api/auth/session-policy")
def get_session_policy(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Returnerer resolved session policy for den indloggede bruger."""
    if current_user is None:
        raise HTTPException(status_code=401)
    policy = _resolve_session_policy(db, current_user)
    return {
        **policy,
        "mfa_required_effective": _mfa_required_for_role(policy, current_user.role),
        "mfa_verified": _session_is_mfa_verified(_session_payload(request)),
    }

# ── WebAuthn / FIDO2 ───────────────────────────────────────────────────────

def _webauthn_settings(db: Session) -> tuple[str, str, str]:
    """Return WebAuthn RP settings from DB, then env, then local bootstrap defaults."""
    from urllib.parse import urlparse

    base_url = _get_setting(db, "base_url", os.getenv("BASE_URL", "http://127.0.0.1:8000")).strip().rstrip("/")
    origin = _get_setting(db, "webauthn_origin", os.getenv("WEBAUTHN_ORIGIN", base_url)).strip().rstrip("/")
    host = urlparse(origin).hostname or "localhost"
    rp_id = _get_setting(db, "webauthn_rp_id", os.getenv("WEBAUTHN_RP_ID", host)).strip() or host
    rp_name = _get_setting(db, "webauthn_rp_name", os.getenv("WEBAUTHN_RP_NAME", "TimeLapse Pro")).strip() or "TimeLapse Pro"
    return rp_id, rp_name, origin

@app.post("/api/auth/webauthn/register-begin")
def webauthn_register_begin(payload: dict, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Trin 1: Generer WebAuthn registreringsudfordring."""
    import webauthn
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria, UserVerificationRequirement,
        ResidentKeyRequirement
    )
    from database import WebAuthnCredential
    if current_user is None:
        raise HTTPException(status_code=401)

    existing = db.query(WebAuthnCredential).filter_by(user_id=current_user.id).all()
    exclude_creds = [
        webauthn.helpers.structs.PublicKeyCredentialDescriptor(id=c.credential_id)
        for c in existing
    ]

    rp_id, rp_name, _origin = _webauthn_settings(db)
    options = webauthn.generate_registration_options(
        rp_id                    = rp_id,
        rp_name                  = rp_name,
        user_id                  = str(current_user.id).encode(),
        user_name                = current_user.username,
        user_display_name        = current_user.username,
        exclude_credentials      = exclude_creds,
        authenticator_selection  = AuthenticatorSelectionCriteria(
            user_verification    = UserVerificationRequirement.PREFERRED,
            resident_key         = ResidentKeyRequirement.DISCOURAGED,
        ),
    )

    import json as _json
    opts_json = webauthn.options_to_json(options)
    # Gem challenge i session (midlertidigt i DB via settings)
    db.query(Settings).filter_by(key=f"wabauthn_challenge_{current_user.id}").delete()
    db.add(Settings(key=f"wabauthn_challenge_{current_user.id}", value=opts_json))
    db.commit()
    return _json.loads(opts_json)

@app.post("/api/auth/webauthn/register-complete")
def webauthn_register_complete(payload: dict, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Trin 2: Valider og gem WebAuthn credential."""
    import webauthn, json as _json
    from database import WebAuthnCredential
    if current_user is None:
        raise HTTPException(status_code=401)

    setting = db.query(Settings).filter_by(key=f"wabauthn_challenge_{current_user.id}").first()
    if not setting:
        raise HTTPException(status_code=400, detail="Ingen aktiv udfordring")

    opts = _json.loads(setting.value)
    challenge = webauthn.base64url_to_bytes(opts["challenge"])

    try:
        rp_id, _rp_name, origin = _webauthn_settings(db)
        verification = webauthn.verify_registration_response(
            credential          = payload,
            expected_challenge  = challenge,
            expected_rp_id      = rp_id,
            expected_origin     = origin,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verifikation fejlede: {e}")

    device_name = payload.get("deviceName", "Ukendt enhed")
    db.add(WebAuthnCredential(
        user_id       = current_user.id,
        credential_id = verification.credential_id,
        public_key    = verification.credential_public_key,
        sign_count    = verification.sign_count,
        device_name   = device_name,
    ))
    db.query(Settings).filter_by(key=f"wabauthn_challenge_{current_user.id}").delete()
    db.commit()
    log.info("WebAuthn credential registreret for %s (%s)", current_user.username, device_name)
    return {"ok": True}

@app.post("/api/auth/webauthn/login-begin")
def webauthn_login_begin(payload: dict, db: Session = Depends(get_db)):
    """Trin 1 login: Generer WebAuthn autentificeringsudfordring."""
    import webauthn, json as _json
    from database import WebAuthnCredential
    username = payload.get("username", "")
    user = db.query(User).filter_by(username=username, is_active=True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")

    creds = db.query(WebAuthnCredential).filter_by(user_id=user.id).all()
    if not creds:
        raise HTTPException(status_code=404, detail="Ingen WebAuthn credentials registreret")

    allow_creds = [
        webauthn.helpers.structs.PublicKeyCredentialDescriptor(id=c.credential_id)
        for c in creds
    ]
    rp_id, _rp_name, _origin = _webauthn_settings(db)
    options = webauthn.generate_authentication_options(
        rp_id             = rp_id,
        allow_credentials = allow_creds,
    )
    opts_json = webauthn.options_to_json(options)
    db.query(Settings).filter_by(key=f"wabauthn_auth_challenge_{user.id}").delete()
    db.add(Settings(key=f"wabauthn_auth_challenge_{user.id}", value=opts_json))
    db.commit()
    return _json.loads(opts_json)

@app.post("/api/auth/webauthn/login-complete")
def webauthn_login_complete(payload: dict, db: Session = Depends(get_db)):
    """Trin 2 login: Valider WebAuthn og udsted session cookie."""
    import webauthn, json as _json
    from database import WebAuthnCredential
    username = payload.get("username", "")
    user = db.query(User).filter_by(username=username, is_active=True).first()
    if not user:
        raise HTTPException(status_code=401)

    setting = db.query(Settings).filter_by(key=f"wabauthn_auth_challenge_{user.id}").first()
    if not setting:
        raise HTTPException(status_code=400, detail="Ingen aktiv udfordring")

    opts = _json.loads(setting.value)
    challenge = webauthn.base64url_to_bytes(opts["challenge"])

    credential_id = webauthn.base64url_to_bytes(payload.get("rawId", ""))
    cred = db.query(WebAuthnCredential).filter_by(
        user_id=user.id, credential_id=credential_id
    ).first()
    if not cred:
        raise HTTPException(status_code=401, detail="Credential ikke fundet")

    try:
        rp_id, _rp_name, origin = _webauthn_settings(db)
        verification = webauthn.verify_authentication_response(
            credential          = payload,
            expected_challenge  = challenge,
            expected_rp_id      = rp_id,
            expected_origin     = origin,
            credential_public_key = cred.public_key,
            credential_current_sign_count = cred.sign_count,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Autentificering fejlede: {e}")

    cred.sign_count = verification.new_sign_count
    db.query(Settings).filter_by(key=f"wabauthn_auth_challenge_{user.id}").delete()
    db.commit()

    session_token = _create_token({
        "sub": user.username,
        "role": user.role,
        "cid": user.customer_id,
        "amr": ["webauthn"],
        "mfa_verified": True,
    })
    log.info("WebAuthn login OK: %s", user.username)
    from fastapi.responses import JSONResponse as _JR
    _resp = _JR(content={"ok": True, "role": user.role, "username": user.username, "customer_id": user.customer_id})
    _resp.headers.append("Set-Cookie", _cookie_header(COOKIE_NAME, session_token, JWT_EXPIRE_H * 3600))
    return _resp

@app.get("/api/auth/webauthn/credentials")
def list_webauthn_credentials(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """List brugerens registrerede WebAuthn credentials."""
    from database import WebAuthnCredential
    if current_user is None:
        raise HTTPException(status_code=401)
    creds = db.query(WebAuthnCredential).filter_by(user_id=current_user.id).all()
    return [
        {
            "id":         c.id,
            "device_name": c.device_name,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in creds
    ]

@app.delete("/api/auth/webauthn/credentials/{cred_id}")
def delete_webauthn_credential(cred_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Slet en WebAuthn credential."""
    from database import WebAuthnCredential
    if current_user is None:
        raise HTTPException(status_code=401)
    cred = db.query(WebAuthnCredential).filter_by(id=cred_id, user_id=current_user.id).first()
    if not cred:
        raise HTTPException(status_code=404)
    db.delete(cred)
    db.commit()
    return {"ok": True}

# ── MFA / TOTP ─────────────────────────────────────────────────────────────

@app.post("/api/auth/setup-mfa")
def setup_mfa(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Generér TOTP secret og returner QR-kode til authenticator app."""
    import pyotp, qrcode, base64
    from io import BytesIO
    if current_user is None:
        raise HTTPException(status_code=401)
    secret = pyotp.random_base32()
    current_user.totp_secret = secret
    db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.username,
        issuer_name="TimeLapse Pro"
    )
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"}

@app.post("/api/auth/confirm-mfa")
def confirm_mfa(payload: dict, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Bekræft TOTP-kode og aktiver MFA."""
    import pyotp
    if current_user is None:
        raise HTTPException(status_code=401)
    code = payload.get("code", "")
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Kør setup-mfa først")
    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Forkert kode — prøv igen")
    current_user.mfa_enabled = True
    db.commit()
    log.info("MFA aktiveret for %s", current_user.username)
    session_token = _create_token({
        "sub": current_user.username,
        "role": current_user.role,
        "cid": current_user.customer_id,
        "amr": ["password", "totp"],
        "mfa_verified": True,
    })
    from fastapi.responses import JSONResponse as _JR
    _resp = _JR(content={
        "ok": True,
        "role": current_user.role,
        "username": current_user.username,
        "customer_id": current_user.customer_id,
    })
    _resp.headers.append("Set-Cookie", _cookie_header(COOKIE_NAME, session_token, JWT_EXPIRE_H * 3600))
    return _resp

@app.post("/api/auth/disable-mfa")
def disable_mfa(payload: dict, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Deaktiver MFA — super_admin kan deaktivere for andre brugere via user_id."""
    if current_user is None:
        raise HTTPException(status_code=401)
    user_id = payload.get("user_id")
    if user_id and current_user.role in ("super_admin", "admin"):
        target = db.query(User).filter_by(id=user_id).first()
        if not target:
            raise HTTPException(status_code=404)
    else:
        target = current_user
    target.mfa_enabled = False
    target.totp_secret = None
    db.commit()
    log.info("MFA deaktiveret for %s af %s", target.username, current_user.username)
    return {"ok": True}

@app.post("/api/auth/verify-mfa")
def verify_mfa(payload: dict, db: Session = Depends(get_db)):
    """Trin 2 login: valider TOTP-kode og udsted session cookie."""
    import pyotp
    from database import User as _User
    mfa_token = payload.get("mfa_token", "")
    code      = payload.get("code", "")
    if not mfa_token or not code:
        raise HTTPException(status_code=400, detail="mfa_token og code påkrævet")
    payload_data = _decode_token(mfa_token)
    if not payload_data or payload_data.get("type") != "mfa_pending":
        raise HTTPException(status_code=401, detail="Ugyldig eller udløbet MFA token")
    user = db.query(_User).filter_by(username=payload_data.get("sub")).first()
    if not user or not user.mfa_enabled or not user.totp_secret:
        raise HTTPException(status_code=401)
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Forkert kode")
    session_token = _create_token({
        "sub": user.username,
        "role": user.role,
        "cid": user.customer_id,
        "amr": ["password", "totp"],
        "mfa_verified": True,
    })
    log.info("MFA login OK: %s", user.username)
    from fastapi.responses import JSONResponse as _JR
    _resp = _JR(content={"ok": True, "role": user.role, "username": user.username, "customer_id": user.customer_id})
    _resp.headers.append("Set-Cookie", _cookie_header(COOKIE_NAME, session_token, JWT_EXPIRE_H * 3600))
    return _resp

# ── Auth models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    remember: bool = False

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
    db_gen = get_db()
    db = next(db_gen)
    try:
        _ensure_super_admin(db)
    finally:
        db_gen.close()

@app.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    """Login — returnerer JWT access token."""
    from database import User
    user = db.query(User).filter_by(username=req.username, is_active=True).first()
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Forkert brugernavn eller adgangskode")
    user.last_login = now_utc()
    db.commit()
    policy = _resolve_session_policy(db, user)
    mfa_required = _mfa_required_for_role(policy, user.role)
    # MFA check: eksisterende TOTP kræves altid; policy kan også kræve enrollment.
    if _user_has_totp(user):
        mfa_token = _create_token({"sub": user.username, "type": "mfa_pending"}, expire_hours=5/60)
        log.info("Login MFA påkrævet: %s", user.username)
        return {"mfa_required": True, "mfa_token": mfa_token}
    if mfa_required:
        setup_max_age = 15 * 60
        setup_token = _create_token({
            "sub": user.username,
            "role": user.role,
            "cid": user.customer_id,
            "max_age": setup_max_age,
            "amr": ["password"],
            "mfa_verified": False,
            "mfa_enrollment_required": True,
        }, expire_hours=setup_max_age / 3600)
        from fastapi.responses import JSONResponse as _JR
        _resp = _JR(content={
            "mfa_setup_required": True,
            "role": user.role,
            "username": user.username,
            "customer_id": user.customer_id,
            "detail": "MFA skal oprettes for denne rolle",
        })
        _resp.headers.append("Set-Cookie", _cookie_header(COOKIE_NAME, setup_token, setup_max_age))
        log.info("Login MFA enrollment påkrævet: %s", user.username)
        return _resp
    log.info("Login: %s (%s)", user.username, user.role)
    from fastapi.responses import JSONResponse as _JR
    _resp = _JR(content={
        "ok":          True,
        "role":        user.role,
        "username":    user.username,
        "customer_id": user.customer_id,
    })
    # Hent session policy
    try:
        sp = policy
    except Exception:
        sp = {}
    remember_me_days      = int(sp.get("remember_me_days",       30))
    session_duration_hours = int(sp.get("session_duration_hours", JWT_EXPIRE_H))
    remember_me_allowed   = bool(sp.get("remember_me_allowed",   True))

    if req.remember and remember_me_allowed:
        max_age = remember_me_days * 24 * 3600
    else:
        max_age = session_duration_hours * 3600
    token = _create_token({
        "sub": user.username,
        "role": user.role,
        "cid": user.customer_id,
        "max_age": max_age,
        "amr": ["password"],
        "mfa_verified": False,
    })
    _resp.headers.append("Set-Cookie", _cookie_header(COOKIE_NAME, token, max_age))
    return _resp

@app.post("/api/auth/logout")
def logout(db: Session = Depends(get_db)):
    """Logout — ryd session cookie."""
    from fastapi.responses import JSONResponse as _JR
    _resp = _JR(content={"ok": True})
    _resp.headers.append("Set-Cookie", _delete_cookie_header(COOKIE_NAME))
    _resp.headers.append("Set-Cookie", _delete_cookie_header(OPENWEBUI_COOKIE_NAME, domain=_openwebui_cookie_domain(db)))
    return _resp

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
def me(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Returnerer brugerinfo og fornyr rolling session cookie."""
    if current_user is None:
        raise HTTPException(status_code=401)
    from fastapi.responses import JSONResponse as _JR
    payload_data = _session_payload(request)
    policy = _resolve_session_policy(db, current_user)
    data = {
        "username":    current_user.username,
        "email":       current_user.email,
        "role":        current_user.role,
        "customer_id": current_user.customer_id,
        "mfa_required_effective": _mfa_required_for_role(policy, current_user.role),
        "mfa_verified": _session_is_mfa_verified(payload_data),
    }
    # Forny rolling session
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        token = existing
        max_age = payload_data.get("max_age", JWT_EXPIRE_H * 3600) if payload_data else JWT_EXPIRE_H * 3600
        new_token = _create_token({
            "sub": current_user.username,
            "role": current_user.role,
            "cid": current_user.customer_id,
            "max_age": max_age,
            "amr": payload_data.get("amr", ["password"]) if payload_data else ["password"],
            "mfa_verified": _session_is_mfa_verified(payload_data),
        })
        resp = _JR(content=data)
        resp.headers.append("Set-Cookie", _cookie_header(COOKIE_NAME, new_token, max_age))
        return resp
    return data


# ── User CRUD (kun super_admin) ───────────────────────────────────────────

@app.get("/api/admin/users")
def list_users(
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User, WebAuthnCredential
    users = db.query(User).order_by(User.username).all()
    cred_counts = dict(
        db.query(WebAuthnCredential.user_id, func.count(WebAuthnCredential.id))
        .group_by(WebAuthnCredential.user_id)
        .all()
    )
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
            "mfa_enabled": bool(u.mfa_enabled),
            "totp_configured": bool(u.totp_secret),
            "mfa_partial": _user_has_partial_mfa(u),
            "mfa_required": _mfa_required_for_user(db, u),
            "webauthn_count": int(cred_counts.get(u.id, 0)),
        }
        for u in users
    ]


@app.post("/api/admin/users/{user_id}/mfa/reset")
def reset_user_mfa(
    user_id: int,
    payload: dict | None = None,
    current_user=require_role("super_admin"),
    db: Session = Depends(get_db),
):
    """Nulstil hel eller halv TOTP MFA-state, så brugeren kan oprette MFA igen."""
    from database import User, WebAuthnCredential
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404)
    clear_webauthn = bool((payload or {}).get("clear_webauthn", False))
    u.mfa_enabled = False
    u.totp_secret = None
    removed_webauthn = 0
    if clear_webauthn:
        removed_webauthn = (
            db.query(WebAuthnCredential)
            .filter_by(user_id=u.id)
            .delete(synchronize_session=False)
        )
    db.commit()
    log.warning(
        "MFA nulstillet for %s af %s (clear_webauthn=%s, removed_webauthn=%s)",
        u.username, current_user.username, clear_webauthn, removed_webauthn,
    )
    return {
        "ok": True,
        "user_id": u.id,
        "username": u.username,
        "mfa_enabled": False,
        "totp_configured": False,
        "removed_webauthn": removed_webauthn,
        "mfa_required": _mfa_required_for_user(db, u),
    }

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
    if u.username == current_user.username:
        raise HTTPException(status_code=400, detail="Du kan ikke slette dig selv")
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
    # DEV-mode fjernet — alle tokens skal være i DB
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
    if token_record:
        device.customer_id = token_record.customer_id or device.customer_id
        device.site_id = token_record.site_id or device.site_id
        device.camera_name = token_record.camera_name or device.camera_name
        device.location_name = token_record.device_label or device.location_name
        try:
            cfg = json.loads(device.device_config or "{}")
        except Exception:
            cfg = {}
        provisioning = cfg.get("provisioning") if isinstance(cfg.get("provisioning"), dict) else {}
        provisioning.update({
            "status": "bootstrapped",
            "bootstrapped_at": now_utc().isoformat(),
            "bootstrap_token_id": token_record.id,
        })
        cfg["provisioning"] = provisioning
        device.device_config = json.dumps(cfg, ensure_ascii=False)
    for old in db.query(KeyCredential).filter_by(
        entity_type="edge",
        entity_id=req.device_id,
        key_type="api",
        status="active",
    ).all():
        old.status = "rotated"
        old.revoked_at = now_utc()
        old.revoked_by = "bootstrap"
        old.revoke_reason = "Device re-bootstrapped and received a new API credential"
    credential = KeyCredential(
        credential_id=f"TL-KEY-{now_utc():%Y%m%d}-{_secrets.token_hex(6)}",
        entity_type="edge",
        entity_id=req.device_id,
        key_type="api",
        label=f"Bootstrap API credential for {req.device_id}",
        status="active",
        scopes_json=_canonical_json(_key_scopes("api")),
        fingerprint=_fingerprint_material(_secret_hash(api_token)),
        secret_hash=_secret_hash(api_token),
        algorithm="sha256-token-hash",
        compliance_domains="SABSA,IEC62443,ISO27000,NIS2,CRA",
        created_by="bootstrap",
        created_at=now_utc(),
        metadata_json=_canonical_json({
            "bootstrap_token_device_label": token_record.device_label if token_record else None,
            "require_request_signature": True,
            "request_signature_policy": "required-by-default-for-device-api",
        }),
    )
    db.add(credential)
    _audit_key_event(db, credential, "created_by_bootstrap", "bootstrap", {"device_id": req.device_id})
    db.commit()

    base_url   = _headend_api_url(db).removesuffix("/api")
    config_url = f"{base_url}/api/config/{req.device_id}"

    return BootstrapResponse(
        api_token  = api_token,
        config_url = config_url,
        device_id  = req.device_id,
    )


# ── Zero-touch Enrollment ─────────────────────────────────────────────────────

class EnrollRequest(BaseModel):
    bootstrap_token: str
    device_id:       str                    # af edge udledt fra MAC: TL-AABBCCDDEEFF
    hardware_model:  Optional[str] = None   # "rpi4", "orangepi4pro", …
    ssh_pubkey:      Optional[str] = None   # ed25519 public key
    mac_address:     Optional[str] = None

class EnrollResponse(BaseModel):
    device_id:        str
    api_token:        str
    config_url:       str
    enrollment_state: str   # "unassigned" | "active"

@app.post("/api/api/devices/enroll", response_model=EnrollResponse, include_in_schema=False)
def enroll_device_compat(req: EnrollRequest, db: Session = Depends(get_db)):
    """Bagudkompatibelt alias — gamle images kalder /api/api/devices/enroll ved fejl."""
    return enroll_device(req, db)


@app.post("/api/devices/enroll", response_model=EnrollResponse)
def enroll_device(req: EnrollRequest, db: Session = Depends(get_db)):
    """
    Zero-touch enrollment endpoint.
    Kaldet af bootstrap_agent.py ved første boot.

    Forskel fra /api/bootstrap:
      - device_id er udledt af edge-boardet selv (fra MAC)
      - Modtager hardware_model og ssh_pubkey
      - Sætter enrollment_state="unassigned" hvis token ikke har site_id
      - Eksisterende /api/bootstrap er uændret (bagud-kompatibilitet)
    """
    _sanitize_device_id(req.device_id)

    token_record = db.query(BootstrapToken).filter_by(
        token=req.bootstrap_token, revoked=False
    ).first()
    if not token_record:
        raise HTTPException(status_code=401, detail="Ugyldigt eller ukendt bootstrap token")
    if token_record.expires_at and now_utc() > token_record.expires_at.replace(tzinfo=_tz.utc):
        raise HTTPException(status_code=401, detail="Bootstrap token udløbet")

    # Batch-token: check use_count < max_uses
    # Single-use: used_at sættes ved første brug og token kan ikke bruges igen
    max_uses  = token_record.max_uses  or 1
    use_count = token_record.use_count or 0
    is_batch  = max_uses > 1

    if is_batch:
        if use_count >= max_uses:
            raise HTTPException(
                status_code=401,
                detail=f"Batch bootstrap token udtømt ({use_count}/{max_uses} brugt)"
            )
    else:
        if token_record.used_at:
            raise HTTPException(status_code=401, detail="Bootstrap token allerede brugt")

    # Opdatér token-tæller
    _now = now_utc()
    token_record.use_count = use_count + 1
    if not token_record.used_at:
        # Sæt used_at og used_by_device første gang
        token_record.used_at       = _now
        token_record.used_by_device = req.device_id

    # Find eller opret device
    device = db.query(Device).filter_by(device_id=req.device_id).first()
    is_new = device is None
    if is_new:
        device = Device(device_id=req.device_id)
        db.add(device)
        log.info("Zero-touch: ny enhed registreret: %s", req.device_id)
    else:
        log.info("Zero-touch: re-enrollment: %s", req.device_id)

    # API-token
    api_token = f"tk-{req.device_id}-{now_utc().strftime('%Y%m%d%H%M%S')}"
    device.api_token  = api_token
    device.last_seen  = now_utc()
    device.status     = "online"

    # Kopiér feltér fra token
    device.customer_id   = token_record.customer_id   or device.customer_id
    device.site_id       = token_record.site_id       or device.site_id
    device.camera_name   = token_record.camera_name   or device.camera_name
    device.location_name = token_record.device_label  or device.location_name

    # Sæt hardware-felter fra enrollment-request
    if req.hardware_model:
        device.hardware_model = req.hardware_model
    if req.ssh_pubkey:
        device.ssh_pubkey = req.ssh_pubkey

    # Enrollment state: "unassigned" hvis ingen site, ellers "active"
    enrollment_state = "active" if device.site_id else "unassigned"
    device.enrollment_state = enrollment_state

    # Opdatér provisioning-metadata i device_config
    try:
        cfg = json.loads(device.device_config or "{}")
    except Exception:
        cfg = {}
    cfg["provisioning"] = {
        "status":             "zero_touch_enrolled",
        "enrolled_at":        now_utc().isoformat(),
        "bootstrap_token_id": token_record.id,
        "hardware_model":     req.hardware_model,
        "mac_address":        req.mac_address,
        "enrollment_state":   enrollment_state,
    }
    device.device_config = json.dumps(cfg, ensure_ascii=False)

    # Roter evt. gamle API-credentials
    for old in db.query(KeyCredential).filter_by(
        entity_type="edge", entity_id=req.device_id, key_type="api", status="active"
    ).all():
        old.status = "rotated"
        old.revoked_at = now_utc()
        old.revoked_by = "zero_touch_enroll"
        old.revoke_reason = "Device re-enrolled via zero-touch bootstrap"

    credential = KeyCredential(
        credential_id=f"TL-KEY-{now_utc():%Y%m%d}-{_secrets.token_hex(6)}",
        entity_type="edge",
        entity_id=req.device_id,
        key_type="api",
        label=f"Zero-touch enrollment credential for {req.device_id}",
        status="active",
        scopes_json=_canonical_json(_key_scopes("api")),
        fingerprint=_fingerprint_material(_secret_hash(api_token)),
        secret_hash=_secret_hash(api_token),
        algorithm="sha256-token-hash",
        compliance_domains="SABSA,IEC62443,ISO27000,NIS2,CRA",
        created_by="zero_touch_enroll",
        created_at=now_utc(),
        metadata_json=_canonical_json({
            "hardware_model":   req.hardware_model,
            "mac_address":      req.mac_address,
            "enrollment_state": enrollment_state,
            "require_request_signature": True,
            "request_signature_policy": "required-by-default-for-device-api",
        }),
    )
    db.add(credential)
    _audit_key_event(db, credential, "created_by_zero_touch_enroll", "zero_touch_enroll",
                     {"device_id": req.device_id, "hardware_model": req.hardware_model})

    # ── Auto-opret DeviceAssignment hvis token er bundet til en kamera-lokation ──
    token_camera_id = getattr(token_record, "camera_id", None)
    if token_camera_id:
        from database import DeviceAssignment as _DA
        # Afslut alle aktive assignments for dette device
        for old_da in (db.query(_DA)
                       .filter_by(device_id=req.device_id)
                       .filter(_DA.unassigned_at.is_(None)).all()):
            old_da.unassigned_at = now_utc()
        # Afslut alle aktive assignments for denne kamera-lokation (ny enhed overtager)
        for old_da in (db.query(_DA)
                       .filter_by(camera_id=token_camera_id)
                       .filter(_DA.unassigned_at.is_(None)).all()):
            old_da.unassigned_at = now_utc()
        # Opret ny assignment
        new_da = _DA(
            device_id       = req.device_id,
            camera_id       = token_camera_id,
            assigned_by     = "zero_touch_enroll",
            assignment_type = "auto",
            notes           = f"Auto-tildelt ved enrollment (token {token_record.id})",
        )
        db.add(new_da)
        # Synkroniser camera_name, site, customer til device
        from database import Camera as _CamModel
        cam = db.query(_CamModel).filter_by(id=token_camera_id).first()
        if cam:
            device.camera_name = cam.camera_name or device.camera_name
            device.site_id     = cam.site_id     or device.site_id
            device.customer_id = cam.customer_id or device.customer_id
        log.info("Auto DeviceAssignment: %s → kamera %s", req.device_id, token_camera_id)

    db.commit()

    base_url   = _headend_api_url(db).removesuffix("/api")
    config_url = f"{base_url}/api/config/{req.device_id}"

    log.info("Zero-touch enrollment OK: %s state=%s hw=%s",
             req.device_id, enrollment_state, req.hardware_model)

    return EnrollResponse(
        device_id        = req.device_id,
        api_token        = api_token,
        config_url       = config_url,
        enrollment_state = enrollment_state,
    )


@app.get("/api/admin/devices/unassigned")
def list_unassigned_devices(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returnerer enheder der er enrollet men endnu ikke tildelt en site."""
    devices = db.query(Device).filter(
        Device.enrollment_state == "unassigned"
    ).order_by(Device.created_at.desc()).all()

    return [
        {
            "device_id":       d.device_id,
            "hardware_model":  d.hardware_model,
            "enrollment_state": d.enrollment_state,
            "created_at":      d.created_at.isoformat() if d.created_at else None,
            "last_seen":       d.last_seen.isoformat() if d.last_seen else None,
            "location_name":   d.location_name,
            "customer_id":     d.customer_id,
        }
        for d in devices
    ]


@app.put("/api/admin/devices/{device_id}/assign-site")
def assign_device_to_site(
    device_id: str,
    payload: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Tildel en unassigned enhed til en site.
    Body: { site_id, camera_name?, location_name? }
    """
    _sanitize_device_id(device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Enhed ikke fundet")

    site_id = payload.get("site_id")
    if not site_id:
        raise HTTPException(status_code=400, detail="site_id er påkrævet")

    site = db.query(Site).filter_by(id=site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site ikke fundet")

    device.site_id          = site_id
    device.site_name        = site.name
    device.customer_id      = site.customer_id or device.customer_id
    device.enrollment_state = "active"
    if payload.get("camera_name"):
        device.camera_name = payload["camera_name"]
    if payload.get("location_name"):
        device.location_name = payload["location_name"]

    # Opdatér provisioning-metadata
    try:
        cfg = json.loads(device.device_config or "{}")
    except Exception:
        cfg = {}
    prov = cfg.get("provisioning", {})
    prov["site_assigned_at"] = now_utc().isoformat()
    prov["site_id"] = site_id
    prov["enrollment_state"] = "active"
    cfg["provisioning"] = prov
    device.device_config = json.dumps(cfg, ensure_ascii=False)

    db.commit()
    log.info("Device %s tildelt site %s (%s)", device_id, site_id, site.name)

    return {
        "ok":             True,
        "device_id":      device_id,
        "site_id":        site_id,
        "site_name":      site.name,
        "enrollment_state": "active",
    }


# ── API Token auth ───────────────────────────────────────────────────────────




async def _verify_device_token(
    device_id: str,
    request: Request,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    """Validér per-device Bearer token på edge-vendte endpoints."""
    scheme, _, provided = authorization.partition(" ")
    if scheme.lower() != "bearer" or not provided:
        raise HTTPException(status_code=401, detail="Manglende Bearer token")
    token_hash = _secret_hash(provided)
    credential = (
        db.query(KeyCredential)
        .filter(
            KeyCredential.entity_type.in_(["edge", "headend", "service"]),
            KeyCredential.entity_id == device_id,
            KeyCredential.key_type == "api",
            KeyCredential.secret_hash == token_hash,
        )
        .first()
    )
    active_secret = None
    if credential:
        if credential.status != "active":
            raise HTTPException(status_code=401, detail="API token er ikke aktiv")
        if credential.expires_at and ensure_utc(credential.expires_at) < now_utc():
            credential.status = "expired"
            db.commit()
            raise HTTPException(status_code=401, detail="API token er udløbet")
        active_secret = provided
        require_signature = False
        try:
            credential_meta = json.loads(credential.metadata_json or "{}")
            require_signature = bool(credential_meta.get("require_request_signature"))
        except Exception:
            require_signature = False
        if credential.entity_type in {"headend", "service"}:
            require_signature = True
        await _verify_edge_request_signature(request, active_secret, required=require_signature)
        await _verify_edge_attestation_signature(request, device_id, db)
        credential.last_used_at = now_utc()
        credential.last_used_from = request.client.host if request.client else None
        credential.use_count = (credential.use_count or 0) + 1
        db.commit()
        return
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device or not device.api_token:
        raise HTTPException(status_code=401, detail="Ukendt device eller token ikke sat")
    if not hmac.compare_digest(provided, device.api_token):
        raise HTTPException(status_code=401, detail="Ugyldig API token for dette device")
    await _verify_edge_request_signature(request, provided)
    await _verify_edge_attestation_signature(request, device_id, db)
    migrated = _upsert_legacy_device_api_credential(db, device, actor="legacy-auth")
    if migrated:
        migrated.last_used_at = now_utc()
        migrated.last_used_from = request.client.host if request.client else None
        migrated.use_count = (migrated.use_count or 0) + 1
        db.commit()


async def _verify_edge_request_signature(request: Request, secret: str, *, required: bool = False) -> None:
    """Validate optional Edge request signature.

    Legacy devices may omit signatures for now. If signature headers are present,
    they must be correct. This gives immediate tamper/replay metadata without
    breaking existing LAB nodes.
    """
    signature = request.headers.get("X-TLP-Signature")
    if not signature:
        if required:
            raise HTTPException(status_code=401, detail="Edge request signature mangler")
        return
    alg = request.headers.get("X-TLP-Signature-Alg", "")
    timestamp = request.headers.get("X-TLP-Timestamp", "")
    nonce = request.headers.get("X-TLP-Nonce", "")
    if alg != "hmac-sha256-v1" or not timestamp or not nonce:
        raise HTTPException(status_code=401, detail="Ugyldige Edge signatur-headere")
    try:
        ts = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Ugyldigt Edge signatur-tidspunkt")
    if abs(int(now_utc().timestamp()) - ts) > 300:
        raise HTTPException(status_code=401, detail="Edge signatur er udenfor tidsvindue")
    body_text = request.headers.get("X-TLP-Signature-Payload-SHA256", "")
    if body_text and request.headers.get("X-TLP-Signature-Scope") != "payload-sha256":
        raise HTTPException(status_code=401, detail="Ugyldig Edge signatur-scope")
    body_text_candidates = [body_text]
    if not body_text:
        body = await request.body()
        if body:
            try:
                parsed_body = json.loads(body.decode("utf-8"))
                body_text = _canonical_json(parsed_body)
                body_text_candidates = [body_text]
                if parsed_body == {}:
                    body_text_candidates.append("")
            except Exception:
                body_text = body.decode("utf-8", errors="replace")
                body_text_candidates = [body_text]
    path = request.url.path.removeprefix("/api")
    expected_signatures = []
    for candidate in body_text_candidates:
        signed = "\n".join([request.method.upper(), path, timestamp, nonce, candidate])
        expected_signatures.append(hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest())
    if not any(hmac.compare_digest(signature, expected) for expected in expected_signatures):
        raise HTTPException(status_code=401, detail="Edge request signature mismatch")


async def _verify_edge_attestation_signature(request: Request, device_id: str, db: Session) -> None:
    """Validate optional Ed25519 Edge payload attestation.

    This is optional until edge_signal_signing_required is enabled. The Edge can
    therefore roll out signing before we enforce it fleet-wide.
    """
    signature = request.headers.get("X-TLP-Edge-Signature")
    required = _get_setting(db, "edge_signal_signing_required", "false").lower() == "true"
    if not signature:
        if required:
            raise HTTPException(status_code=401, detail="Edge attestation signature mangler")
        return
    alg = request.headers.get("X-TLP-Edge-Signature-Alg", "")
    key_fingerprint = request.headers.get("X-TLP-Edge-Signature-Key", "")
    timestamp = request.headers.get("X-TLP-Edge-Signature-Timestamp", "")
    nonce = request.headers.get("X-TLP-Edge-Signature-Nonce", "")
    if alg != "ed25519-v1" or not key_fingerprint or not timestamp or not nonce:
        raise HTTPException(status_code=401, detail="Ugyldige Edge attestation-headere")
    try:
        ts = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Ugyldigt Edge attestation-tidspunkt")
    if abs(int(now_utc().timestamp()) - ts) > 300:
        raise HTTPException(status_code=401, detail="Edge attestation er udenfor tidsvindue")
    credential = (
        db.query(KeyCredential)
        .filter_by(
            entity_type="edge",
            entity_id=device_id,
            key_type="signing",
            status="active",
            fingerprint=key_fingerprint,
        )
        .first()
    )
    if not credential or not credential.public_key:
        if not required:
            return
        raise HTTPException(status_code=401, detail="Ukendt Edge signing key")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_ssh_public_key

        public_key = load_ssh_public_key(credential.public_key.encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("not ed25519")
        body_text = request.headers.get("X-TLP-Edge-Signature-Payload-SHA256", "")
        if body_text and request.headers.get("X-TLP-Edge-Signature-Scope") != "payload-sha256":
            raise HTTPException(status_code=401, detail="Ugyldig Edge attestation-scope")
        body_text_candidates = [body_text]
        if not body_text:
            body = await request.body()
            if body:
                try:
                    parsed_body = json.loads(body.decode("utf-8"))
                    body_text = _canonical_json(parsed_body)
                    body_text_candidates = [body_text]
                    if parsed_body == {}:
                        body_text_candidates.append("")
                except Exception:
                    body_text = body.decode("utf-8", errors="replace")
                    body_text_candidates = [body_text]
        path = request.url.path.removeprefix("/api")
        last_error = None
        for candidate in body_text_candidates:
            signed = "\n".join([request.method.upper(), path, timestamp, nonce, candidate])
            try:
                public_key.verify(base64.b64decode(signature), signed.encode("utf-8"))
                last_error = None
                break
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Edge attestation signature mismatch")
    credential.last_used_at = now_utc()
    credential.last_used_from = request.client.host if request.client else None
    credential.use_count = (credential.use_count or 0) + 1


class KeyCredentialPayload(BaseModel):
    entity_type: str
    entity_id: str
    key_type: str
    label: Optional[str] = None
    scopes: Optional[list[str]] = None
    expires_days: Optional[int] = 365
    public_key: Optional[str] = None
    generate_keypair: Optional[bool] = False
    rotated_from_id: Optional[str] = None
    metadata: Optional[dict] = None


class KeyRevokePayload(BaseModel):
    reason: Optional[str] = None


class KeySignaturePolicyPayload(BaseModel):
    require_request_signature: bool = True
    reason: Optional[str] = None


class StaleCredentialCleanupPayload(BaseModel):
    dry_run: bool = True
    older_than_days: int = 14
    reason: Optional[str] = None


class EdgeSigningEnrollmentPayload(BaseModel):
    public_key: str
    label: Optional[str] = None
    algorithm: Optional[str] = "ed25519"


def _secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _fingerprint_material(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _key_scopes(key_type: str, scopes: list[str] | None = None) -> list[str]:
    if scopes:
        return [str(s) for s in scopes if str(s).strip()]
    defaults = {
        "api": ["config:read", "heartbeat:write", "capture:write", "updates:poll"],
        "ssh": ["ssh:manual-debug", "ssh:reverse-tunnel"],
        "signing": ["artifact:sign", "change-ticket:sign", "inventory:sign"],
        "bootstrap": ["device:bootstrap"],
    }
    return defaults.get(key_type, [])


def _credential_state(credential: KeyCredential) -> str:
    if credential.status != "active":
        return credential.status
    if credential.expires_at and ensure_utc(credential.expires_at) < now_utc():
        return "expired"
    return "active"


def _audit_key_event(
    db: Session,
    credential: KeyCredential,
    event_type: str,
    actor: str,
    details: dict | None = None,
) -> None:
    db.add(KeyAuditEvent(
        credential_id=credential.credential_id,
        event_type=event_type,
        actor=actor,
        entity_type=credential.entity_type,
        entity_id=credential.entity_id,
        details_json=_canonical_json(details or {}),
        occurred_at=now_utc(),
    ))


def _credential_metadata(credential: KeyCredential) -> dict:
    try:
        return json.loads(credential.metadata_json or "{}")
    except Exception:
        return {}


def _set_credential_metadata(credential: KeyCredential, metadata: dict) -> None:
    credential.metadata_json = _canonical_json(metadata)


def _credential_request_signature_required(credential: KeyCredential) -> bool:
    metadata = _credential_metadata(credential)
    if credential.entity_type in {"headend", "service"} and credential.key_type == "api":
        return True
    return bool(metadata.get("require_request_signature"))


def _credential_sort_timestamp(credential: KeyCredential) -> datetime:
    value = credential.last_used_at or credential.created_at
    if value:
        return ensure_utc(value)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _primary_credential_ids(db: Session, credentials: list[KeyCredential]) -> set[int]:
    """Find den credential der bør bevares pr. aktiv entity/key_type gruppe."""
    grouped: dict[tuple[str, str, str], list[KeyCredential]] = {}
    for credential in credentials:
        if _credential_state(credential) != "active":
            continue
        grouped.setdefault((credential.entity_type, credential.entity_id, credential.key_type), []).append(credential)

    devices = {d.device_id: d for d in db.query(Device).all()}
    primary_ids: set[int] = set()
    for (entity_type, entity_id, key_type), group in grouped.items():
        primary: KeyCredential | None = None
        if entity_type == "edge" and key_type == "api":
            device = devices.get(entity_id)
            if device and device.api_token:
                token_hash = _secret_hash(device.api_token)
                matches = [c for c in group if c.secret_hash == token_hash]
                if matches:
                    primary = max(matches, key=_credential_sort_timestamp)
        if primary is None:
            primary = max(group, key=_credential_sort_timestamp)
        if primary.id is not None:
            primary_ids.add(primary.id)
    return primary_ids


def _credential_cleanup_candidates(
    db: Session,
    *,
    older_than_days: int = 30,
) -> list[dict]:
    now = now_utc()
    cutoff = now - timedelta(days=max(int(older_than_days), 1))
    credentials = (
        db.query(KeyCredential)
        .filter(
            KeyCredential.entity_type == "edge",
            KeyCredential.key_type.in_(["api", "signing"]),
            KeyCredential.status == "active",
        )
        .order_by(KeyCredential.entity_id.asc(), KeyCredential.key_type.asc(), KeyCredential.created_at.desc())
        .all()
    )
    primary_ids = _primary_credential_ids(db, credentials)
    grouped_counts: dict[tuple[str, str, str], int] = {}
    for credential in credentials:
        grouped_counts[(credential.entity_type, credential.entity_id, credential.key_type)] = (
            grouped_counts.get((credential.entity_type, credential.entity_id, credential.key_type), 0) + 1
        )

    candidates = []
    for credential in credentials:
        ref = credential.last_used_at or credential.created_at
        ref_utc = ensure_utc(ref) if ref else None
        is_primary = credential.id in primary_ids
        group_count = grouped_counts.get((credential.entity_type, credential.entity_id, credential.key_type), 0)
        stale = ref_utc is None or ref_utc < cutoff
        action = None
        reason = None
        auto_revoke = False
        if group_count > 1 and not is_primary:
            action = "revoke_secondary"
            reason = "Sekundær aktiv credential; en anden credential er primær for samme edge/key-type."
            auto_revoke = True
        elif is_primary and stale:
            action = "review_stale_primary"
            reason = "Primær credential er stale, men revokeres ikke automatisk for ikke at afbryde en mulig aktiv enhed."
        if not action:
            continue
        candidates.append({
            "credential_id": credential.credential_id,
            "entity_id": credential.entity_id,
            "key_type": credential.key_type,
            "status": _credential_state(credential),
            "last_used_at": credential.last_used_at.isoformat() if credential.last_used_at else None,
            "created_at": credential.created_at.isoformat() if credential.created_at else None,
            "is_primary": is_primary,
            "group_count": group_count,
            "stale": stale,
            "action": action,
            "auto_revoke": auto_revoke,
            "reason": reason,
        })
    return candidates


def _upsert_legacy_device_api_credential(
    db: Session,
    device: Device,
    actor: str = "migration",
) -> KeyCredential | None:
    """Representer et eksisterende legacy device.api_token som lifecycle credential.

    Dette ændrer ikke Edge-hemmeligheden og er derfor en non-breaking bro fra
    LAB-tokenmodellen til key_credentials, audit og senere revocation/rotation.
    """
    if not device or not device.device_id or not device.api_token:
        return None
    token_hash = _secret_hash(device.api_token)
    existing = (
        db.query(KeyCredential)
        .filter_by(
            entity_type="edge",
            entity_id=device.device_id,
            key_type="api",
            secret_hash=token_hash,
        )
        .first()
    )
    if existing:
        changed = False
        if existing.status != "active":
            existing.status = "active"
            existing.revoked_at = None
            existing.revoked_by = None
            existing.revoke_reason = None
            changed = True
        if not existing.metadata_json:
            existing.metadata_json = _canonical_json({
                "migrated_from_legacy_device_api_token": True,
                "secret_material_stored": False,
                "legacy_token_retained_for_agent_compatibility": True,
            })
            changed = True
        if changed:
            _audit_key_event(db, existing, "legacy_token_reactivated", actor, {
                "device_id": device.device_id,
                "reason": "Existing device.api_token matched credential hash",
            })
        return existing

    now = now_utc()
    credential = KeyCredential(
        credential_id=f"TL-KEY-{now:%Y%m%d}-{_secrets.token_hex(6)}",
        entity_type="edge",
        entity_id=device.device_id,
        key_type="api",
        label=f"Legacy API credential for {device.device_id}",
        status="active",
        scopes_json=_canonical_json(_key_scopes("api")),
        fingerprint=_fingerprint_material(token_hash),
        secret_hash=token_hash,
        algorithm="sha256-token-hash",
        compliance_domains="SABSA,IEC62443,ISO27000,NIS2,CRA",
        created_by=actor,
        created_at=now,
        metadata_json=_canonical_json({
            "migrated_from_legacy_device_api_token": True,
            "secret_material_stored": False,
            "legacy_token_retained_for_agent_compatibility": True,
            "next_step": "Rotate device to a managed API credential and remove devices.api_token after agent confirmation.",
        }),
    )
    db.add(credential)
    _audit_key_event(db, credential, "legacy_token_migrated", actor, {
        "device_id": device.device_id,
        "legacy_token_retained": True,
    })
    return credential


def _credential_to_dict(credential: KeyCredential) -> dict:
    try:
        scopes = json.loads(credential.scopes_json or "[]")
    except Exception:
        scopes = []
    try:
        metadata = json.loads(credential.metadata_json or "{}")
    except Exception:
        metadata = {}
    status = _credential_state(credential)
    include_tags = [
        credential.entity_type,
        credential.key_type,
        status,
    ]
    if credential.secret_hash:
        include_tags.append("secret-managed")
    if metadata.get("migrated_from_legacy_device_api_token"):
        include_tags.append("legacy-migrated")
    if metadata.get("gpg_fingerprint"):
        include_tags.append("release-signer")
    request_signature_required = _credential_request_signature_required(credential)
    if credential.key_type == "api":
        include_tags.append("hmac-required" if request_signature_required else "hmac-missing")
    include_tags = sorted(set(include_tags))
    return {
        "id": credential.id,
        "credential_id": credential.credential_id,
        "entity_type": credential.entity_type,
        "entity_id": credential.entity_id,
        "key_type": credential.key_type,
        "label": credential.label,
        "status": status,
        "scopes": scopes,
        "public_key": credential.public_key,
        "fingerprint": credential.fingerprint,
        "algorithm": credential.algorithm,
        "compliance_domains": credential.compliance_domains,
        "created_by": credential.created_by,
        "created_at": credential.created_at.isoformat() if credential.created_at else None,
        "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        "last_used_at": credential.last_used_at.isoformat() if credential.last_used_at else None,
        "last_used_from": credential.last_used_from,
        "use_count": credential.use_count or 0,
        "revoked_at": credential.revoked_at.isoformat() if credential.revoked_at else None,
        "revoked_by": credential.revoked_by,
        "revoke_reason": credential.revoke_reason,
        "rotated_from_id": credential.rotated_from_id,
        "metadata": metadata,
        "request_signature_required": request_signature_required,
        "has_secret": bool(credential.secret_hash),
        "tags": include_tags,
    }


def _trusted_release_signers(db: Session) -> list[dict]:
    signers = (
        db.query(KeyCredential)
        .filter_by(entity_type="headend", key_type="signing", status="active")
        .order_by(KeyCredential.created_at.desc())
        .all()
    )
    result = []
    for signer in signers:
        try:
            scopes = json.loads(signer.scopes_json or "[]")
        except Exception:
            scopes = []
        try:
            metadata = json.loads(signer.metadata_json or "{}")
        except Exception:
            metadata = {}
        if "artifact:sign" not in scopes and "change-ticket:sign" not in scopes:
            continue
        result.append({
            "credential_id": signer.credential_id,
            "entity_id": signer.entity_id,
            "label": signer.label,
            "algorithm": signer.algorithm,
            "fingerprint": signer.fingerprint,
            "gpg_fingerprint": metadata.get("gpg_fingerprint"),
            "public_key": signer.public_key,
            "scopes": scopes,
            "expires_at": signer.expires_at.isoformat() if signer.expires_at else None,
        })
    return result


@app.get("/api/admin/key-management")
def list_key_management(
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    credentials = db.query(KeyCredential).order_by(KeyCredential.created_at.desc()).all()
    devices = db.query(Device).order_by(Device.device_id).all()
    inventories = {i.device_id: i for i in db.query(DeviceInventory).all()}
    rows = [_credential_to_dict(c) for c in credentials]
    counts = {
        "active": sum(1 for c in rows if c["status"] == "active"),
        "revoked": sum(1 for c in rows if c["status"] == "revoked"),
        "expired": sum(1 for c in rows if c["status"] == "expired"),
        "legacy_device_tokens": sum(1 for d in devices if d.api_token),
        "missing_edge_api_key": 0,
        "missing_signing_key": 0,
        "active_api_credentials": sum(1 for c in rows if c["status"] == "active" and c["key_type"] == "api"),
        "api_hmac_required": sum(1 for c in rows if c["status"] == "active" and c["key_type"] == "api" and c["request_signature_required"]),
        "api_hmac_missing": sum(1 for c in rows if c["status"] == "active" and c["key_type"] == "api" and not c["request_signature_required"]),
        "cleanup_candidates": 0,
        "auto_revoke_candidates": 0,
        "trusted_release_signers": 0,
    }
    trusted_release_signers = _trusted_release_signers(db)
    counts["trusted_release_signers"] = len(trusted_release_signers)
    cleanup_candidates = _credential_cleanup_candidates(db, older_than_days=14)
    counts["cleanup_candidates"] = len(cleanup_candidates)
    counts["auto_revoke_candidates"] = sum(1 for c in cleanup_candidates if c.get("auto_revoke"))
    active_by_entity_type = {
        (c.entity_type, c.entity_id, c.key_type)
        for c in credentials
        if _credential_state(c) == "active"
    }
    device_rows = []
    for device in devices:
        inv = inventories.get(device.device_id)
        has_api = ("edge", device.device_id, "api") in active_by_entity_type
        has_signing = ("edge", device.device_id, "signing") in active_by_entity_type
        if not has_api:
            counts["missing_edge_api_key"] += 1
        if not has_signing:
            counts["missing_signing_key"] += 1
        device_rows.append({
            "device_id": device.device_id,
            "status": device.status,
            "customer_name": device.customer_name,
            "site_name": device.site_name,
            "hostname": inv.hostname if inv else None,
            "hardware_model": inv.hardware_model if inv else None,
            "has_api_key": has_api,
            "has_signing_key": has_signing,
            "has_legacy_token": bool(device.api_token),
        })
    controls = [
        {
            "status": "warning" if counts["legacy_device_tokens"] else "pass",
            "title": "Legacy device tokens",
            "evidence": f"{counts['legacy_device_tokens']} device(s) har stadig plain legacy api_token i devices-tabellen.",
            "domains": ["ISO27000", "IEC62443", "CRA"],
            "recommendation": "Roter edge-enheder over på key_credentials og fjern plain legacy token efter agent update.",
        },
        {
            "status": "warning" if counts["missing_edge_api_key"] else "pass",
            "title": "Edge API identities",
            "evidence": f"{counts['missing_edge_api_key']} device(s) mangler aktiv Edge API credential.",
            "domains": ["SABSA", "IEC62443", "NIS2"],
            "recommendation": "Udsted én aktiv API credential pr. Edge og bind den til CMDB device_id.",
        },
        {
            "status": "warning" if counts["missing_signing_key"] else "pass",
            "title": "Device signing identities",
            "evidence": f"{counts['missing_signing_key']} device(s) mangler signing credential til inventory/update attestation.",
            "domains": ["IEC62443", "ISO27000", "CRA"],
            "recommendation": "Registrer public signing key pr. Headend og Edge; private keys må aldrig gemmes i Headend DB.",
        },
        {
            "status": "pass" if counts["trusted_release_signers"] else "fail",
            "title": "Code-signing trust root",
            "evidence": f"{counts['trusted_release_signers']} aktiv(e) Headend signing key(s) kan bruges til artifact/change-ticket verification.",
            "domains": ["IEC62443", "ISO27000", "NIS2", "CRA"],
            "recommendation": "Edge må kun installere artifacts med signatur fra en trusted Headend/release key. Pin root public key i base image og distribuer rotation via signeret trust policy.",
        },
        {
            "status": "warning" if counts["api_hmac_missing"] else "pass",
            "title": "Signal mutual authentication",
            "evidence": f"{counts['api_hmac_required']} aktiv(e) API credential(s) kræver HMAC request-signature; {counts['api_hmac_missing']} mangler enforcement.",
            "domains": ["SABSA", "IEC62443", "ISO27000", "NIS2"],
            "recommendation": "Kræv HMAC på alle aktive Edge/Headend API credentials og migrer gamle noder, før global enforcement slås til.",
        },
        {
            "status": "warning" if counts["cleanup_candidates"] else "pass",
            "title": "Stale og sekundære credentials",
            "evidence": f"{counts['cleanup_candidates']} credential(s) bør gennemgås; {counts['auto_revoke_candidates']} kan revokeres automatisk som sekundære.",
            "domains": ["ISO27000", "IEC62443", "CRA"],
            "recommendation": "Revoker sekundære credentials og gennemgå stale primære manuelt, så CMDB kun viser reelle adgangsveje.",
        },
    ]
    return {
        "credentials": rows,
        "devices": device_rows,
        "summary": counts,
        "controls": controls,
        "cleanup_candidates": cleanup_candidates,
        "trust_policy": {
            "artifact_verification_required": True,
            "mutual_auth_required": True,
            "trusted_release_signers": trusted_release_signers,
            "edge_acceptance_rule": "Edge must verify manifest signature, artifact sha256 and signer fingerprint before install.",
        },
    }


@app.post("/api/admin/key-management/migrate-legacy-device-tokens")
def migrate_legacy_device_tokens(
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Migrer eksisterende devices.api_token til KeyCredential uden at ændre token.

    Bruges til LAB/R&D-overgangen, hvor Edge allerede har en hemmelighed lokalt.
    Det giver revocation, audit, last-used og compliance-evidens nu, mens vi
    planlægger egentlig rotation og fjernelse af legacy-feltet senere.
    """
    devices = db.query(Device).order_by(Device.device_id).all()
    migrated = 0
    already_registered = 0
    skipped = 0
    rows = []
    actor = current_user.username
    for device in devices:
        if not device.api_token:
            skipped += 1
            rows.append({
                "device_id": device.device_id,
                "status": "skipped_no_legacy_token",
                "credential_id": None,
            })
            continue
        before = (
            db.query(KeyCredential)
            .filter_by(
                entity_type="edge",
                entity_id=device.device_id,
                key_type="api",
                secret_hash=_secret_hash(device.api_token),
            )
            .first()
        )
        credential = _upsert_legacy_device_api_credential(db, device, actor=actor)
        if before:
            already_registered += 1
            status = "already_registered"
        else:
            migrated += 1
            status = "migrated"
        rows.append({
            "device_id": device.device_id,
            "status": status,
            "credential_id": credential.credential_id if credential else None,
        })
    db.commit()
    return {
        "migrated": migrated,
        "already_registered": already_registered,
        "skipped": skipped,
        "devices": rows,
    }


@app.post("/api/admin/key-management/credentials")
def create_key_credential(
    payload: KeyCredentialPayload,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    entity_type = payload.entity_type.strip().lower()
    key_type = payload.key_type.strip().lower()
    if entity_type not in {"headend", "edge", "user", "service"}:
        raise HTTPException(status_code=400, detail="Ugyldig entity_type")
    if key_type not in {"api", "ssh", "signing", "bootstrap"}:
        raise HTTPException(status_code=400, detail="Ugyldig key_type")
    if not payload.entity_id.strip():
        raise HTTPException(status_code=400, detail="entity_id er påkrævet")

    now = now_utc()
    expires_at = None
    if payload.expires_days and payload.expires_days > 0:
        from datetime import timedelta
        expires_at = now + timedelta(days=int(payload.expires_days))
    credential_id = f"TL-KEY-{now:%Y%m%d}-{_secrets.token_hex(6)}"
    secret_once = None
    private_key_once = None
    public_key = payload.public_key.strip() if payload.public_key else None
    secret_hash = None
    algorithm = "external"

    if key_type in {"ssh", "signing"} and payload.generate_keypair and not public_key:
        private_key_once, public_key = _generate_ed25519_keypair()
        algorithm = "ed25519"
    elif public_key:
        algorithm = "ed25519" if public_key.startswith("ssh-ed25519") else "public-key"

    if key_type == "api":
        secret_once = f"tlp_{entity_type}_{_secrets.token_urlsafe(32)}"
        secret_hash = _secret_hash(secret_once)
        algorithm = "sha256-token-hash"
        if entity_type == "edge":
            device = db.query(Device).filter_by(device_id=payload.entity_id).first()
            if device:
                device.api_token = secret_once
    elif key_type in {"ssh", "signing"} and not public_key:
        raise HTTPException(status_code=400, detail="SSH/signing credential kræver public_key eller generate_keypair")

    metadata = dict(payload.metadata or {})
    if key_type == "api" and entity_type in {"edge", "headend", "service"}:
        metadata.setdefault("require_request_signature", True)
        metadata.setdefault("request_signature_policy", "required-by-default-for-device-api")

    fingerprint_source = public_key or secret_hash or credential_id
    credential = KeyCredential(
        credential_id=credential_id,
        entity_type=entity_type,
        entity_id=payload.entity_id.strip(),
        key_type=key_type,
        label=payload.label or f"{entity_type}:{payload.entity_id}:{key_type}",
        status="active",
        scopes_json=_canonical_json(_key_scopes(key_type, payload.scopes)),
        public_key=public_key,
        fingerprint=_fingerprint_material(fingerprint_source),
        secret_hash=secret_hash,
        algorithm=algorithm,
        compliance_domains="SABSA,IEC62443,ISO27000,NIS2,CRA",
        created_by=current_user.username,
        created_at=now,
        expires_at=expires_at,
        rotated_from_id=payload.rotated_from_id,
        metadata_json=_canonical_json(metadata),
    )
    db.add(credential)
    _audit_key_event(db, credential, "created", current_user.username, {
        "key_type": key_type,
        "entity_type": entity_type,
        "rotated_from_id": payload.rotated_from_id,
        "generated_private_key_returned_once": bool(private_key_once),
    })
    if payload.rotated_from_id:
        old = db.query(KeyCredential).filter_by(credential_id=payload.rotated_from_id).first()
        if old and old.status == "active":
            old.status = "rotated"
            old.revoked_at = now
            old.revoked_by = current_user.username
            old.revoke_reason = f"Rotated to {credential_id}"
            _audit_key_event(db, old, "rotated", current_user.username, {"rotated_to": credential_id})
    db.commit()
    data = _credential_to_dict(credential)
    if secret_once:
        data["secret_once"] = secret_once
    if private_key_once:
        data["private_key_once"] = private_key_once
    return data


@app.post("/api/admin/key-management/credentials/{credential_id}/revoke")
def revoke_key_credential(
    credential_id: str,
    payload: KeyRevokePayload = KeyRevokePayload(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    credential = db.query(KeyCredential).filter_by(credential_id=credential_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential ikke fundet")
    credential.status = "revoked"
    credential.revoked_at = now_utc()
    credential.revoked_by = current_user.username
    credential.revoke_reason = payload.reason or "Manuelt revokeret"
    if credential.entity_type == "edge" and credential.key_type == "api":
        device = db.query(Device).filter_by(device_id=credential.entity_id).first()
        if device and device.api_token and credential.secret_hash == _secret_hash(device.api_token):
            device.api_token = None
    _audit_key_event(db, credential, "revoked", current_user.username, {"reason": credential.revoke_reason})
    db.commit()
    return {"ok": True, "credential_id": credential.credential_id}


@app.post("/api/admin/key-management/credentials/{credential_id}/request-signature")
def set_key_credential_request_signature_policy(
    credential_id: str,
    payload: KeySignaturePolicyPayload,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    credential = db.query(KeyCredential).filter_by(credential_id=credential_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential ikke fundet")
    if credential.key_type != "api":
        raise HTTPException(status_code=400, detail="Request signature policy gælder kun API credentials")
    if credential.status != "active":
        raise HTTPException(status_code=400, detail="Kun aktive credentials kan ændre request signature policy")
    if credential.entity_type in {"headend", "service"} and not payload.require_request_signature:
        raise HTTPException(status_code=400, detail="Headend/service API credentials skal kræve request signature")

    metadata = _credential_metadata(credential)
    metadata["require_request_signature"] = bool(payload.require_request_signature)
    metadata["request_signature_policy_updated_at"] = now_utc().isoformat()
    metadata["request_signature_policy_updated_by"] = current_user.username
    if payload.reason:
        metadata["request_signature_policy_reason"] = payload.reason
    _set_credential_metadata(credential, metadata)
    _audit_key_event(db, credential, "request_signature_policy_updated", current_user.username, {
        "require_request_signature": bool(payload.require_request_signature),
        "reason": payload.reason,
    })
    db.commit()
    return _credential_to_dict(credential)


@app.post("/api/admin/key-management/cleanup-stale-credentials")
def cleanup_stale_key_credentials(
    payload: StaleCredentialCleanupPayload,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    older_than_days = max(int(payload.older_than_days or 30), 1)
    candidates = _credential_cleanup_candidates(db, older_than_days=older_than_days)
    revoked = []
    if not payload.dry_run:
        by_id = {
            c.credential_id: c
            for c in db.query(KeyCredential).filter(
                KeyCredential.credential_id.in_([item["credential_id"] for item in candidates if item.get("auto_revoke")])
            ).all()
        }
        for item in candidates:
            if not item.get("auto_revoke"):
                continue
            credential = by_id.get(item["credential_id"])
            if not credential or credential.status != "active":
                continue
            credential.status = "revoked"
            credential.revoked_at = now_utc()
            credential.revoked_by = current_user.username
            credential.revoke_reason = payload.reason or item.get("reason") or "Sekundær/stale credential cleanup"
            _audit_key_event(db, credential, "cleanup_revoked", current_user.username, {
                "cleanup_action": item.get("action"),
                "reason": credential.revoke_reason,
                "older_than_days": older_than_days,
            })
            revoked.append(credential.credential_id)
        db.commit()
        candidates = _credential_cleanup_candidates(db, older_than_days=older_than_days)
    return {
        "dry_run": bool(payload.dry_run),
        "older_than_days": older_than_days,
        "revoked": revoked,
        "revoked_count": len(revoked),
        "candidates": candidates,
        "auto_revoke_candidates": sum(1 for c in candidates if c.get("auto_revoke")),
        "review_only_candidates": sum(1 for c in candidates if not c.get("auto_revoke")),
    }


@app.post("/api/keys/signing/enroll/{device_id}")
def enroll_edge_signing_key(
    device_id: str,
    payload: EdgeSigningEnrollmentPayload,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    """Registrer Edge public signing key uden at Headend modtager privat nøgle."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device ikke fundet")
    public_key = (payload.public_key or "").strip()
    if not public_key:
        raise HTTPException(status_code=400, detail="public_key er påkrævet")
    if not public_key.startswith("ssh-ed25519 "):
        raise HTTPException(status_code=400, detail="Kun ssh-ed25519 public keys accepteres for Edge signing")

    now = now_utc()
    fingerprint = _fingerprint_material(public_key)
    existing = (
        db.query(KeyCredential)
        .filter_by(entity_type="edge", entity_id=device_id, key_type="signing", fingerprint=fingerprint)
        .first()
    )
    if existing:
        if existing.status != "active":
            existing.status = "active"
            existing.revoked_at = None
            existing.revoked_by = None
            existing.revoke_reason = None
            _audit_key_event(db, existing, "edge_signing_key_reactivated", "edge", {"device_id": device_id})
        existing.last_used_at = now
        existing.use_count = (existing.use_count or 0) + 1
        db.commit()
        return {
            "status": "already_registered",
            "credential_id": existing.credential_id,
            "fingerprint": existing.fingerprint,
        }

    for old in (
        db.query(KeyCredential)
        .filter_by(entity_type="edge", entity_id=device_id, key_type="signing", status="active")
        .all()
    ):
        old.status = "rotated"
        old.revoked_at = now
        old.revoked_by = "edge"
        old.revoke_reason = "Rotated by Edge signing enrollment"
        _audit_key_event(db, old, "rotated", "edge", {"rotated_by_device": device_id})

    credential = KeyCredential(
        credential_id=f"TL-KEY-{now:%Y%m%d}-{_secrets.token_hex(6)}",
        entity_type="edge",
        entity_id=device_id,
        key_type="signing",
        label=payload.label or f"Edge signing key for {device_id}",
        status="active",
        scopes_json=_canonical_json(_key_scopes("signing", ["inventory:sign", "heartbeat:sign", "update-result:sign"])),
        public_key=public_key,
        fingerprint=fingerprint,
        algorithm=payload.algorithm or "ed25519",
        compliance_domains="SABSA,IEC62443,ISO27000,NIS2,CRA",
        created_by="edge",
        created_at=now,
        last_used_at=now,
        use_count=1,
        metadata_json=_canonical_json({
            "private_key_location": "edge-local",
            "private_key_stored_in_headend": False,
            "enrollment_model": "edge-call-home",
            "accepted_for": ["inventory_attestation", "heartbeat_attestation", "update_result_attestation"],
        }),
    )
    db.add(credential)
    _audit_key_event(db, credential, "edge_signing_key_enrolled", "edge", {
        "device_id": device_id,
        "private_key_stored_in_headend": False,
    })
    db.commit()
    return {
        "status": "enrolled",
        "credential_id": credential.credential_id,
        "fingerprint": credential.fingerprint,
    }

# ── Config ────────────────────────────────────────────────────────────────────


@app.post("/api/admin/provisioning-tokens")
def create_provisioning_token(
    payload: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Generer et nyt bootstrap-token til en edge-enhed."""
    import secrets as _secrets
    from sqlalchemy import text as _text
    from datetime import timedelta as _timedelta

    token = _secrets.token_urlsafe(32)
    hours = int(payload.get("expires_hours", 24))
    expires = now_utc() + _timedelta(hours=hours)

    db.execute(_text("""
        INSERT INTO provisioning_tokens
            (token, device_id, customer_id, site_id, note, created_by, expires_at)
        VALUES
            (:token, :device_id, :customer_id, :site_id, :note, :created_by, :expires_at)
    """), {
        "token":       token,
        "device_id":   payload.get("device_id"),
        "customer_id": payload.get("customer_id"),
        "site_id":     payload.get("site_id"),
        "note":        payload.get("note", ""),
        "created_by":  current_user.username,
        "expires_at":  expires,
    })
    db.commit()
    log.info("Provisioning token oprettet af %s — udløber %s", current_user.username, expires)
    return {"token": token, "expires_at": expires.isoformat()}


@app.get("/api/admin/provisioning-tokens")
def list_provisioning_tokens(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Liste alle provisioning tokens."""
    from sqlalchemy import text as _text
    rows = db.execute(_text(
        "SELECT id, token, device_id, note, created_by, created_at, "
        "expires_at, used_at, used_by, revoked "
        "FROM provisioning_tokens ORDER BY created_at DESC LIMIT 50"
    )).fetchall()
    return [dict(r._mapping) for r in rows]


@app.delete("/api/admin/provisioning-tokens/{token_id}")
def revoke_provisioning_token(
    token_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Revoker et provisioning token."""
    from sqlalchemy import text as _text
    db.execute(_text(
        "UPDATE provisioning_tokens SET revoked = TRUE WHERE id = :id"
    ), {"id": token_id})
    db.commit()
    return {"status": "revoked"}


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

    base_url = _get_setting(db, "base_url", os.environ.get("BASE_URL", "http://127.0.0.1:8000"))
    api_credential = (
        db.query(KeyCredential)
        .filter_by(entity_type="edge", entity_id=device_id, key_type="api", status="active")
        .order_by(KeyCredential.created_at.desc())
        .first()
    )
    signing_credential = (
        db.query(KeyCredential)
        .filter_by(entity_type="edge", entity_id=device_id, key_type="signing", status="active")
        .order_by(KeyCredential.created_at.desc())
        .first()
    )
    edge_signal_signing_required = _get_setting(db, "edge_signal_signing_required", "false").lower() == "true"

    sftp_enabled = _get_setting(db, "sftp_enabled", os.getenv("SFTP_ENABLED", "false")).lower() == "true"
    sftp_host = _get_setting(db, "sftp_host", os.getenv("SFTP_HOST", "")) if sftp_enabled else ""
    sftp_user = _get_setting(db, "sftp_user", os.getenv("SFTP_USER", "")) if sftp_enabled else ""
    sftp_password = _get_setting(db, "sftp_password", os.getenv("SFTP_PASSWORD", "")) if sftp_enabled else ""
    sftp_remote_base = _get_setting(db, "sftp_remote_base", os.getenv("SFTP_REMOTE_BASE", "")) if sftp_enabled else ""
    upload_slot_cycle_s = int(_get_setting(db, "upload_slot_cycle_seconds", os.getenv("UPLOAD_SLOT_CYCLE_SECONDS", "600")))
    upload_slot_window_s = int(_get_setting(db, "upload_slot_window_seconds", os.getenv("UPLOAD_SLOT_WINDOW_SECONDS", "90")))
    upload_slot_span = max(1, upload_slot_cycle_s - upload_slot_window_s)
    upload_slot_offset_s = int(hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:8], 16) % upload_slot_span
    upload_slot_max_pending = int(_get_setting(db, "upload_slot_max_pending_per_window", os.getenv("UPLOAD_SLOT_MAX_PENDING_PER_WINDOW", "3")))
    upload_slot_enforced = (
        _get_setting(db, "upload_slot_enforced", os.getenv("UPLOAD_SLOT_ENFORCED", "false"))
        .strip()
        .lower()
        in {"1", "true", "yes", "ja", "on"}
    )

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
            "capture_avoid_windows": [],
        },
        "camera": {
            "device_id":               device_id,
            "power_mode":              "relay",
            "relay_gpio_pin":          356,
            "relay_on_seconds_before": 10,
            "relay_off_seconds_after": 5,
            "relay_simulate":          False,
            "gphoto2_port":            "usb:",
            "delete_after_download":   True,
        },
        "security": {
            "artifact_verification_required": True,
            "mutual_auth_required": True,
            "accepted_artifact_signature_scopes": ["artifact:sign", "change-ticket:sign"],
            "trusted_release_signers": _trusted_release_signers(db),
            "edge_api_credential": {
                "registered": bool(api_credential),
                "credential_id": api_credential.credential_id if api_credential else None,
                "last_used_at": api_credential.last_used_at.isoformat() if api_credential and api_credential.last_used_at else None,
                "legacy_token_present": bool(device.api_token),
                "rotation_required": bool(device.api_token),
            },
            "edge_signal_signing": {
                "required": edge_signal_signing_required,
                "planned": True,
                "registered": bool(signing_credential),
                "credential_id": signing_credential.credential_id if signing_credential else None,
                "note": "Next agent step: sign heartbeat/inventory/update-result payloads with the Edge signing key.",
            },
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
            "adaptive_exposure": {
                "enabled": False,
                "target_brightness": 118,
                "brightness_tolerance": 32,
                "step_ev": 0.3,
                "min_ev": -2.0,
                "max_ev": 2.0,
            },
            "edge_ai": {
                "enabled": True,
                "mode": "assist",
                "prefer_npu": True,
                "runner": "/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py",
                "model_path": "",
                "vendor_binary": "",
                "timeout_s": 8,
                "lens_obstruction_enabled": True,
                "direct_sun_detection_enabled": True,
            },
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
        "upload": {
            "primary": "api",
            "secondary": "customer_sftp",
            "tertiary": "backup_sftp",
            "api": {
                "enabled": True,
                "endpoint": f"/captures/{device_id}/files",
                "signed_payload_hash": True,
                "timeslot": {
                    "enabled": True,
                    "enforced": upload_slot_enforced,
                    "policy": "free_when_capacity_available",
                    "assigned_by": "headend",
                    "cycle_seconds": upload_slot_cycle_s,
                    "window_seconds": upload_slot_window_s,
                    "start_offset_seconds": upload_slot_offset_s,
                    "max_pending_per_window": upload_slot_max_pending,
                    "defer_large_uploads_only": True,
                },
            },
        },
        "sftp": {
            "enabled":     sftp_enabled,
            "host":        sftp_host,
            "port":        int(_get_setting(db, "sftp_port", os.getenv("SFTP_PORT", "22"))),
            "username":    sftp_user,
            "password":    sftp_password,
            "key_file":    "",
            "remote_base": sftp_remote_base,
            "role":        "customer_sftp",
            "layout_version": "customer-site-camera-date-v1",
            "backup_sftp": {
                "enabled": False,
                "host": "",
                "port": 22,
                "username": "",
                "password": "",
                "key_file": "",
                "remote_base": "/backup/timelapse",
                "role": "backup_sftp",
            },
        },
        "diagnostics": {
            "heartbeat_interval_minutes":        60,
            "update_poll_interval_minutes":       5,
            "inventory_report_interval_hours":   24,
            "collect": [
                "cpu_temperature", "cpu_load",
                "memory_usage", "disk_usage", "connectivity_type"
            ],
        },
        "siem": {
            "enabled": True,
            "mode": "lab",
            "min_severity": "info",
            "forward_interval_s": 300,
            "max_events_per_batch": 200,
            "initial_since_minutes": 10,
            "journal_units": ["timelapse-edge.service"],
        },
        "time": {
            # Tidssynkronisering — prioritet: gps → headend → ntp → local
            "sources": {
                "gps": {
                    "enabled": True,
                    "device": "/dev/ttyS3",
                    "baud": 9600,
                },
                "headend": {
                    "enabled": True,
                    "url": base_url,
                    "interval_minutes": 6,
                },
                "ntp": {
                    "enabled": True,
                    "servers": ["pool.ntp.org"],
                },
            },
            "totp_valid_window": 3,
            "timezone": "Europe/Copenhagen",
        },
        # BT PAN TOTP — prioritet: fabriksstandard < global (Settings) <
        # kunde/site/device (config_overrides, sat i hierarki-merge nedenfor) <
        # kamera (Camera.bt_totp_secret, sat efter merge — se nedenfor)
        "bt_totp": (
            {"secret": _get_setting(db, "bt_totp_secret", ""), "sid": _get_setting(db, "bt_totp_sid", "global")}
            if _get_setting(db, "bt_totp_secret", "")
            else {"secret": "JBSWY3DPEHPK3PXP", "sid": "factory-default"}
        ),
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
            for section in ["schedule", "camera", "quality", "storage", "diagnostics", "system", "session_policy"]:
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
            if cfg.get("sftp", {}).get("enabled") and getattr(site, "sftp_user", None):
                cfg["sftp"]["username"] = site.sftp_user
                cfg["sftp"]["remote_base"] = _get_setting(db, "sftp_remote_base", os.getenv("SFTP_REMOTE_BASE", ""))
            if site.config_overrides:
                for section, values in json.loads(site.config_overrides).items():
                    if section in cfg and isinstance(cfg[section], dict):
                        cfg[section] = _deep_merge(cfg[section], values)
                    else:
                        cfg[section] = values
            # Site-GPS er KUN et fallback-defaultpunkt. Hvis edgen selv er
            # konfigureret (via device_config, laget ovenfor) til at bruge et
            # tilsluttet GPS-modul ("gpsd") eller allerede har en manuel
            # lat/lon, skal det ikke overskrives af sitets generelle
            # koordinat — ellers mister vi den mere præcise, enhedsspecifikke
            # kilde. Se Peters afklaring 2026-07-03: "hvis der er GPS i
            # kameraet, må det ikke overskrives."
            if (
                site.gps_lat
                and cfg["location"].get("gps_source", "manual") != "gpsd"
                and cfg["location"].get("gps_lat") is None
            ):
                cfg["location"]["gps_lat"] = site.gps_lat
                cfg["location"]["gps_lon"] = site.gps_lon
            if site.timezone:
                cfg["schedule"]["timezone"] = site.timezone
        # Lag 4: logisk kamera-lokation config (Camera.config) — følger kameraet,
        # ikke den fysiske Edge. Dette er det normale laveste override-lag.
        active_camera = _active_camera_for_device(db, device_id)
        if active_camera and active_camera.config:
            for section, values in json.loads(active_camera.config or "{}").items():
                if section in cfg and isinstance(cfg[section], dict):
                    cfg[section] = _deep_merge(cfg[section], values)
                else:
                    cfg[section] = values
        # Legacy: device config_overrides, hvis en ældre database har kolonnen.
        if hasattr(device, "config_overrides") and device.config_overrides:
            for section, values in json.loads(device.config_overrides).items():
                if section in cfg and isinstance(cfg[section], dict):
                    cfg[section] = _deep_merge(cfg[section], values)
                else:
                    cfg[section] = values
    except Exception as exc:
        log.warning("Hierarkisk config merge fejl for %s: %s", device_id, exc)

    # Lag 5: kamera-specifik bt_totp override — højeste prioritet i hierarkiet.
    # Slår op via aktiv DeviceAssignment (device_id → camera_id).
    try:
        from database import Camera as _Camera_btt, DeviceAssignment as _DA_btt
        _da_btt = (
            db.query(_DA_btt)
            .filter_by(device_id=device_id)
            .filter(_DA_btt.unassigned_at.is_(None))
            .order_by(_DA_btt.assigned_at.desc())
            .first()
        )
        _cam_btt = db.query(_Camera_btt).filter_by(id=_da_btt.camera_id).first() if _da_btt else None
        if _cam_btt and _cam_btt.bt_totp_secret:
            cfg["bt_totp"] = {"secret": _cam_btt.bt_totp_secret, "sid": _cam_btt.bt_totp_sid or "kamera"}
    except Exception as _exc_btt:
        log.warning("bt_totp kamera-lag fejl for %s: %s", device_id, _exc_btt)

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

    if not cfg.get("sftp", {}).get("enabled"):
        cfg["sftp"].update({
            "enabled": False,
            "host": "",
            "username": "",
            "password": "",
            "key_file": "",
            "remote_base": "",
        })

    # Versioner den effektive config, så Edge også opdager globale DB-ændringer
    # som fx NAS/SFTP roots, upload-politik eller kamera/site defaults.
    try:
        version_payload = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
        cfg["config_version"] = hashlib.md5(version_payload.encode("utf-8")).hexdigest()
    except Exception:
        cfg["config_version"] = device.config_version or ""

    # bt_totp er sat som base + overrides via hierarkiet — intet ekstra her.

    return cfg



@app.get("/api/admin/devices/{device_id}/config")
def get_device_config_admin(
    device_id: str,
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db),
):
    """Hent merged device config til UI (JWT-beskyttet admin version af /api/config/{device_id})."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device ikke fundet")

    # Brug samme merge-logik som get_config
    from sqlalchemy.orm import Session as _S
    return get_config(device_id=device_id, _auth=None, db=db)

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
    """Opret app PendingUpdate-poster baseret på heartbeat.

    OS update counts fra Edge er kun telemetry. De maa ikke oprette OS update
    candidates, fordi Headend skal reconciliere CMDB installed-state mod et
    Headend-ejet lab/mirror-katalog.
    """
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
        repo_dir = _os.getenv("TIMELAPSE_REPO_DIR", str(_repo_root()))
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

    if os_security > 0 or os_total > 0:
        log.info(
            "Ignorerer Edge OS update counts for %s: security=%d functional=%d; "
            "Headend CMDB+katalog reconcile er paakraevet",
            device_id, os_security, os_total,
        )

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

    capture = _upsert_capture_record(
        db,
        device_id=device_id,
        filename=req.filename,
        sha256=req.sha256,
        sha256_pre_xmp=req.sha256_pre_xmp,
        captured_at=captured_at,
        filesize=req.filesize,
        camera_model=req.camera_model,
        quality_flag=req.quality_flag,
        quality_passed=req.quality_passed,
        blur_score=req.blur_score,
        brightness_mean=req.brightness_mean,
        uploaded=req.uploaded_primary or False,
        exposure_time=req.exposure_time,
        aperture=req.aperture,
        iso=req.iso,
        gps_lat=req.gps_lat,
        gps_lon=req.gps_lon,
        gps_alt_m=req.gps_alt_m,
        gps_source=req.gps_source,
        azimuth_deg=req.azimuth_deg,
        tilt_deg=req.tilt_deg,
        mount_height_m=req.mount_height_m,
        fov_horizontal_deg=req.fov_horizontal_deg,
        fov_vertical_deg=req.fov_vertical_deg,
        perspective=req.perspective,
        xmp_written=req.xmp_written,
    )
    if req.edge_ai_result and not capture.ai_result:
        capture.ai_result = json.dumps({
            **req.edge_ai_result,
            "source": "edge",
            "edge_ai_engine": req.edge_ai_engine or req.edge_ai_result.get("engine"),
        }, ensure_ascii=False)

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
            db2_gen = get_db()
            db2 = next(db2_gen)
            try:
                c2 = db2.query(Capture).filter(Capture.id == _cap_id).first()
                if c2:
                    c2.exif_data = exif_json
                    db2.commit()
                    log.info("EXIF gemt for capture %d (%d felter)", _cap_id, len(tags))
            finally:
                db2_gen.close()
        except Exception as exc:
            log.warning("EXIF baggrunds-læsning fejl: %s", exc)
    _threading.Thread(target=_enrich_exif, daemon=True).start()

    # ── AI KØDNING ──────────────────────────────────────────────────────
    try:
        queue_capture_for_analysis(capture.id)
    except Exception:
        pass

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


def _safe_storage_segment(value: str | None, fallback: str) -> str:
    cleaned = _re.sub(r"[^A-Za-z0-9æøåÆØÅ_-]", "_", str(value or fallback)).strip("_")
    return cleaned[:120] or fallback


def _capture_storage_dir(db: Session, device_id: str, filename: str, captured_at: datetime | None = None) -> _Path:
    device = db.query(Device).filter_by(device_id=device_id).first()
    customer = _safe_storage_segment(device.customer_name if device else None, "UnknownCustomer")
    site = _safe_storage_segment(device.site_name if device else None, "UnknownSite")
    camera = _safe_storage_segment(device.camera_name if device else None, device_id)
    when = captured_at
    if when is None:
        m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
        if m:
            when = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    if when is None:
        when = now_utc()
    return _sftp_base_path(db) / customer / site / camera / f"{when.year:04d}" / f"{when.month:02d}" / f"{when.day:02d}"


def _parse_capture_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_upload_filename(filename: str | None) -> str:
    name = _Path(filename or "").name
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Ugyldigt filnavn")
    if not _re.match(r"^[A-Za-z0-9æøåÆØÅ_.-]{3,220}$", name):
        raise HTTPException(status_code=400, detail="Ugyldigt filnavn format")
    if _Path(name).suffix.lower() not in {".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Kun JPEG-billeder er tilladt")
    return name


def _resolve_capture_camera_customer(
    db: Session, device_id: str | None, captured_at: "datetime | None" = None
) -> tuple[str | None, str | None, str | None]:
    """Slår (camera_id, customer_id, site_id) op for et device_id på et givet tidspunkt.

    Tilføjet 2026-07-03 — se Claude_Kritisk_Statusgennemgang_2026-07-03.md §2.4/§2.5.
    Udvidet 2026-07-03 (fase 4) med site_id, så hele kunde/site/kamera-lokations-
    hierarkiet er tagget på captureren ved optagelsestidspunktet — ikke kun kunde og
    kamera-lokation. Det giver mulighed for en senere, mere restriktiv RBAC-
    granularitet end "hele kunden" uden at skulle genudlede historikken via et live
    join (samme lektie som R16 i RISK_ASSESSMENT_v10.md: frys hierarkiet ved
    optagelsestidspunktet, følg ikke et device, der senere flyttes/omtildeles).
    Bevidst KUN tagging indtil videre — site_id bruges endnu ikke til håndhævelse.

    customer_id kommer primært fra Device.customer_id (bred dækning — sat for
    alle devices, inkl. bulk-importerede, uanset om de er bundet til en logisk
    kamera-lokation). camera_id og site_id kommer fra den DeviceAssignment, der var
    aktiv på capture-tidspunktet (kun devices, der reelt er bundet til en kamera-
    lokation, har dette — resten forbliver bevidst NULL, ikke gættet).
    Camera.customer_id/Camera.site_id foretrækkes over Device.customer_id/
    Device.site_id, hvis en binding findes, da kamera-lokationen er den mere
    autoritative kilde.
    """
    if not device_id:
        return None, None, None
    camera_id: str | None = None
    customer_id: str | None = None
    site_id: str | None = None
    try:
        device = db.query(Device).filter_by(device_id=device_id).first()
        if device and device.customer_id:
            customer_id = device.customer_id
        if device and device.site_id:
            site_id = device.site_id
    except Exception:
        pass
    try:
        ts = captured_at or now_utc()
        q = db.query(DeviceAssignment).filter(DeviceAssignment.device_id == device_id)
        q = q.filter(DeviceAssignment.assigned_at <= ts)
        q = q.filter(
            or_(DeviceAssignment.unassigned_at.is_(None), DeviceAssignment.unassigned_at > ts)
        )
        assignment = q.order_by(DeviceAssignment.assigned_at.desc()).first()
        if assignment:
            camera_id = assignment.camera_id
            camera = db.query(Camera).filter_by(id=camera_id).first()
            if camera and camera.customer_id:
                customer_id = camera.customer_id
            if camera and camera.site_id:
                site_id = camera.site_id
    except Exception as exc:
        log.debug("Kunne ikke resolve camera/customer/site for device %s: %s", device_id, exc)
    return camera_id, customer_id, site_id


def _upsert_capture_record(db: Session, **values) -> Capture:
    device_id = values.get("device_id")
    sha256 = values.get("sha256")
    filename = values.get("filename")
    q = db.query(Capture).filter(Capture.device_id == device_id)
    capture = None
    if sha256:
        capture = q.filter(Capture.sha256 == sha256).order_by(Capture.id.desc()).first()
    if not capture and filename:
        capture = q.filter(Capture.filename == filename).order_by(Capture.id.desc()).first()
    if not capture:
        capture = Capture(device_id=device_id)
        db.add(capture)
    # GPS-felter er del af den signerede capture-pakke fra optagelsestidspunktet
    # (se sidecar "location"-blok + integrity.sha256_original). Den først
    # registrerede aflæsning må ikke overskrives af en senere upload/re-sync —
    # ellers kan en mere upræcis efterfølgende værdi tavst erstatte en
    # troværdig live GPS-aflæsning. Peters afklaring 2026-07-03.
    _gps_locked_fields = {"gps_lat", "gps_lon", "gps_alt_m", "gps_source"}
    for key, value in values.items():
        if value is None or not hasattr(capture, key):
            continue
        if key in _gps_locked_fields and getattr(capture, key, None) is not None:
            continue
        setattr(capture, key, value)
    if not capture.camera_id or not capture.customer_id or not capture.site_id:
        try:
            resolved_camera_id, resolved_customer_id, resolved_site_id = _resolve_capture_camera_customer(
                db, device_id, capture.captured_at
            )
            if not capture.camera_id and resolved_camera_id:
                capture.camera_id = resolved_camera_id
            if not capture.customer_id and resolved_customer_id:
                capture.customer_id = resolved_customer_id
            if not capture.site_id and resolved_site_id:
                capture.site_id = resolved_site_id
        except Exception as _exc_resolve:
            log.debug("camera/customer/site-resolution sprunget over: %s", _exc_resolve)
    return capture


def _coerce_float(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _sidecar_capture_metadata(sidecar_data: dict | None) -> dict:
    """Normalize metadata from an Edge/import sidecar into Capture columns."""
    if not isinstance(sidecar_data, dict):
        return {}
    camera = sidecar_data.get("camera") if isinstance(sidecar_data.get("camera"), dict) else {}
    loc = sidecar_data.get("location") if isinstance(sidecar_data.get("location"), dict) else {}
    integrity = sidecar_data.get("integrity") if isinstance(sidecar_data.get("integrity"), dict) else {}
    return {
        "camera_model": camera.get("model"),
        "iso": _coerce_int(camera.get("iso")),
        "aperture": camera.get("aperture"),
        "exposure_time": camera.get("shutter_speed") or camera.get("exposure_time"),
        "gps_lat": _coerce_float(loc.get("gps_lat")),
        "gps_lon": _coerce_float(loc.get("gps_lon")),
        "gps_alt_m": _coerce_float(loc.get("gps_alt_m") if loc.get("gps_alt_m") is not None else loc.get("gps_alt")),
        "gps_source": loc.get("gps_source"),
        "azimuth_deg": _coerce_float(loc.get("azimuth_deg")),
        "tilt_deg": _coerce_float(loc.get("tilt_deg")),
        "mount_height_m": _coerce_float(loc.get("mount_height_m")),
        "fov_horizontal_deg": _coerce_float(loc.get("fov_horizontal_deg")),
        "fov_vertical_deg": _coerce_float(loc.get("fov_vertical_deg")),
        "perspective": loc.get("perspective"),
        "xmp_written": integrity.get("xmp_written"),
    }


@app.post("/api/captures/{device_id}/files")
async def receive_capture_files(
    device_id: str,
    manifest: str = Form(...),
    image: UploadFile = File(...),
    sidecar: UploadFile | None = File(default=None),
    thumbnail: UploadFile | None = File(default=None),
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    """Receive image payloads from an Edge over the signed Headend API."""
    _sanitize_device_id(device_id)
    try:
        meta = json.loads(manifest)
    except Exception:
        raise HTTPException(status_code=400, detail="Ugyldigt upload manifest")
    if meta.get("device_id") and meta["device_id"] != device_id:
        raise HTTPException(status_code=400, detail="Manifest device_id matcher ikke URL")

    filename = _safe_upload_filename(meta.get("filename") or image.filename)
    captured_at = _parse_capture_timestamp(meta.get("captured_at"))
    dest_dir = _capture_storage_dir(db, device_id, filename, captured_at)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    tmp_path = dest_dir / f".{filename}.uploading"

    hasher = hashlib.sha256()
    size = 0
    with open(tmp_path, "wb") as out:
        while True:
            chunk = await image.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            hasher.update(chunk)
            out.write(chunk)
    actual_sha = hasher.hexdigest()
    expected_sha = meta.get("sha256")
    if expected_sha and not hmac.compare_digest(str(expected_sha), actual_sha):
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="Billedets SHA-256 matcher ikke manifest")
    os.replace(tmp_path, dest_path)

    sidecar_path = dest_path.with_suffix(".json")
    sidecar_received = False
    sidecar_data = None
    if sidecar:
        raw_sidecar = await sidecar.read()
        if raw_sidecar:
            try:
                sidecar_data = _json.loads(raw_sidecar.decode("utf-8"))
            except Exception:
                raise HTTPException(status_code=400, detail="Sidecar JSON er ugyldig")
            sidecar_path.write_bytes(raw_sidecar)
            sidecar_received = True
    elif meta:
        sidecar_data = meta if isinstance(meta, dict) else None
        sidecar_path.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    thumbnail_received = False
    if thumbnail:
        thumb_dir = dest_dir / ".thumbs"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        raw_thumb = await thumbnail.read()
        if raw_thumb:
            thumb_tmp = thumb_dir / f".{filename}.uploading"
            thumb_tmp.write_bytes(raw_thumb)
            os.replace(thumb_tmp, thumb_dir / filename)
            thumbnail_received = True

    sidecar_meta = _sidecar_capture_metadata(sidecar_data)
    capture_values = {
        **sidecar_meta,
        "camera_model": meta.get("camera_model") or sidecar_meta.get("camera_model"),
        "exposure_time": meta.get("exposure_time") or sidecar_meta.get("exposure_time"),
        "aperture": meta.get("aperture") or sidecar_meta.get("aperture"),
        "iso": _coerce_int(meta.get("iso")) if meta.get("iso") is not None else sidecar_meta.get("iso"),
        "gps_lat": _coerce_float(meta.get("gps_lat")) if meta.get("gps_lat") is not None else sidecar_meta.get("gps_lat"),
        "gps_lon": _coerce_float(meta.get("gps_lon")) if meta.get("gps_lon") is not None else sidecar_meta.get("gps_lon"),
        "gps_alt_m": _coerce_float(meta.get("gps_alt_m")) if meta.get("gps_alt_m") is not None else sidecar_meta.get("gps_alt_m"),
        "gps_source": meta.get("gps_source") or sidecar_meta.get("gps_source"),
        "azimuth_deg": _coerce_float(meta.get("azimuth_deg")) if meta.get("azimuth_deg") is not None else sidecar_meta.get("azimuth_deg"),
        "tilt_deg": _coerce_float(meta.get("tilt_deg")) if meta.get("tilt_deg") is not None else sidecar_meta.get("tilt_deg"),
        "mount_height_m": _coerce_float(meta.get("mount_height_m")) if meta.get("mount_height_m") is not None else sidecar_meta.get("mount_height_m"),
        "fov_horizontal_deg": _coerce_float(meta.get("fov_horizontal_deg")) if meta.get("fov_horizontal_deg") is not None else sidecar_meta.get("fov_horizontal_deg"),
        "fov_vertical_deg": _coerce_float(meta.get("fov_vertical_deg")) if meta.get("fov_vertical_deg") is not None else sidecar_meta.get("fov_vertical_deg"),
        "perspective": meta.get("perspective") or sidecar_meta.get("perspective"),
        "xmp_written": meta.get("xmp_written") if meta.get("xmp_written") is not None else sidecar_meta.get("xmp_written"),
    }
    capture = _upsert_capture_record(
        db,
        device_id=device_id,
        filename=filename,
        sha256=actual_sha,
        sha256_pre_xmp=meta.get("sha256_pre_xmp"),
        captured_at=captured_at,
        filesize=size,
        camera_model=meta.get("camera_model"),
        quality_flag=meta.get("quality_flag"),
        quality_passed=meta.get("quality_passed"),
        blur_score=meta.get("blur_score"),
        brightness_mean=meta.get("brightness_mean"),
        uploaded=True,
        sidecar_path=str(sidecar_path) if sidecar_path.exists() else None,
        **capture_values,
    )
    if meta.get("edge_ai_result") and not capture.ai_result:
        edge_ai = meta.get("edge_ai_result")
        capture.ai_result = json.dumps({
            **edge_ai,
            "source": "edge",
            "edge_ai_engine": meta.get("edge_ai_engine") or edge_ai.get("engine"),
        }, ensure_ascii=False)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device:
        device.last_seen = now_utc()
        device.status = "online"
    db.commit()
    try:
        queue_capture_for_analysis(capture.id)
    except Exception:
        pass
    log.info(
        "Capture API files received: device=%s filename=%s image_bytes=%s sidecar=%s thumbnail=%s",
        device_id,
        filename,
        size,
        "uploaded" if sidecar_received else ("manifest_fallback" if sidecar_path.exists() else "missing"),
        thumbnail_received,
    )
    return {
        "status": "ok",
        "capture_id": capture.id,
        "sha256": actual_sha,
        "bytes": size,
        "storage": "canonical",
    }


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
    site_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """List alle logiske kameraer. Filtreres med ?site_id= eller ?customer_id="""
    from database import Camera, DeviceAssignment
    q = db.query(Camera).filter(Camera.retired_at.is_(None))
    if site_id:
        q = q.filter(Camera.site_id == site_id)
    if customer_id:
        q = q.filter(Camera.customer_id == customer_id)
    cameras = q.order_by(Camera.camera_name).all()
    result = []
    for cam in cameras:
        site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
        customer = db.query(Customer).filter_by(id=cam.customer_id or (site.customer_id if site else None)).first() if (cam.customer_id or site) else None
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
            "site_name":     site.name if site else None,
            "customer_name": customer.name if customer else None,
            "camera_name":   cam.camera_name,
            "serial_number": cam.serial_number,
            "model":         cam.model,
            "notes":         cam.notes,
            "baseline_description": getattr(cam, "baseline_description", None),
            "context_notes":        getattr(cam, "context_notes", None),
            "current_device_id": assignment.device_id if assignment else None,
            "assigned_at":   assignment.assigned_at.isoformat() if assignment and assignment.assigned_at else None,
            "created_at":    cam.created_at.isoformat() if cam.created_at else None,
            # Netværkskonfiguration (v7)
            "network_type":  getattr(cam, "network_type", "ethernet") or "ethernet",
            "wifi_ssid":     getattr(cam, "wifi_ssid", None),
            "wifi_country":  getattr(cam, "wifi_country", "DK") or "DK",
            # wifi_password + ssh_private_key returneres IKKE her af sikkerhedshensyn
            # SSH / reverse tunnel (v8)
            "ssh_public_key":      getattr(cam, "ssh_public_key", None),
            "reverse_tunnel_port": getattr(cam, "reverse_tunnel_port", None),
        })
    return result


@app.get("/api/admin/cameras/{camera_id}/ssh-key")
def download_camera_ssh_key(
    camera_id: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Hent SSH private key til direkte SSH-adgang til edge-enhed (via reverse tunnel).
    Returnerer PEM-formateret Ed25519 private key som plaintext fil."""
    from database import Camera as _Camera
    from fastapi.responses import PlainTextResponse
    cam = db.query(_Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    pk = getattr(cam, "ssh_private_key", None)
    if not pk:
        raise HTTPException(status_code=404, detail="Ingen SSH-nøgle genereret for dette kamera endnu")
    safe_name = (cam.camera_name or camera_id).replace(" ", "_").replace("/", "-")
    return PlainTextResponse(
        content=pk,
        headers={"Content-Disposition": f'attachment; filename="timelapse_{safe_name}.pem"'},
    )


@app.get("/api/admin/headend/ssh-public-key")
def get_headend_ssh_public_key(
    _user=require_role("super_admin", "admin"),
):
    """Returnerer headendens SSH public key — injectes i edge-images authorized_keys
    så headenden kan SSH direkte ind i enheden."""
    import os, subprocess as _sp
    key_path = os.path.expanduser("~/.ssh/timelapse_headend_ed25519")
    pub_path  = key_path + ".pub"
    if not os.path.exists(pub_path):
        # Generer headend-nøgle første gang
        _sp.run(
            ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-C", "timelapse-headend"],
            check=True, capture_output=True,
        )
        log.info("Headend SSH keypair genereret: %s", key_path)
    return {"public_key": open(pub_path).read().strip()}


@app.post("/api/admin/cameras")
def create_camera(
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Opret et nyt logisk kamera."""
    from database import Camera
    import uuid as _u
    site = db.query(Site).filter_by(id=payload.get("site_id")).first() if payload.get("site_id") else None
    customer_id = payload.get("customer_id") or (site.customer_id if site else None)
    if site:
        _ensure_site_access(db, _user, site.id)
    elif customer_id:
        _ensure_customer_access(_user, customer_id)
    cam = Camera(
        id          = str(_u.uuid4()),
        site_id     = site.id if site else payload.get("site_id"),
        customer_id = customer_id,
        camera_name = payload.get("camera_name", "Nyt kamera"),
        serial_number = payload.get("serial_number"),
        model       = payload.get("model"),
        notes       = payload.get("notes"),
        config      = _json.dumps(payload.get("config", {})),
        # bt_totp_secret + bt_totp_sid: NULL = fabriksstandard JBSWY3DPEHPK3PXP
    )
    db.add(cam); db.commit()
    log.info("Kamera oprettet: %s (%s)", cam.camera_name, cam.id)
    return {"id": cam.id}


@app.put("/api/admin/cameras/{camera_id}")
def update_camera(
    camera_id: str,
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Opdater metadata på et logisk kamera uden at ændre device-binding."""
    from database import Camera, Device, DeviceAssignment
    cam = db.query(Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    if cam.site_id:
        _ensure_site_access(db, _user, cam.site_id)
    elif cam.customer_id:
        _ensure_customer_access(_user, cam.customer_id)

    if "site_id" in payload:
        new_site = _ensure_site_access(db, _user, payload.get("site_id")) if payload.get("site_id") else None
        cam.site_id = new_site.id if new_site else None
        cam.customer_id = payload.get("customer_id") or (new_site.customer_id if new_site else cam.customer_id)
    elif "customer_id" in payload:
        _ensure_customer_access(_user, payload.get("customer_id"))
        cam.customer_id = payload.get("customer_id")

    for field in ["camera_name", "serial_number", "model", "notes", "baseline_description", "context_notes", "network_type", "wifi_ssid", "wifi_country"]:
        if field in payload:
            setattr(cam, field, payload[field])
    if "wifi_password" in payload and payload.get("wifi_password"):
        cam.wifi_password = payload["wifi_password"]
    if "config" in payload and isinstance(payload["config"], dict):
        cam.config = _json.dumps(payload["config"], ensure_ascii=False)

    # Hold aktiv device metadata læsbar for gamle views og captures.
    active = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=cam.id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .first()
    )
    if active:
        dev = db.query(Device).filter_by(device_id=active.device_id).first()
        if dev:
            dev.camera_name = cam.camera_name
            dev.site_id = cam.site_id
            dev.customer_id = cam.customer_id
            site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
            customer = db.query(Customer).filter_by(id=cam.customer_id).first() if cam.customer_id else None
            if site:
                dev.site_name = site.name
            if customer:
                dev.customer_name = customer.name

    db.commit()
    return {"status": "ok", "id": cam.id}


@app.get("/api/admin/cameras/{camera_id}/bt-totp-qr")
def get_camera_bt_totp_qr(
    camera_id: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Returner QR-kode (data-URI) til BT PAN TOTP for dette kamera.
    Beregner det gældende secret ved at gå op i hierarkiet:
      fabriksstandard → global (Settings) → kunde.config_overrides.bt_totp
      → site.config_overrides.bt_totp → kamera.bt_totp_secret (højeste prioritet)
    """
    import pyotp as _pyotp, qrcode as _qrcode, io as _io, base64 as _b64
    from database import Camera, Site, Customer

    cam = db.query(Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")

    # Fabriksstandard som udgangspunkt
    secret = "JBSWY3DPEHPK3PXP"
    sid    = "factory-default"
    source = "factory-default"

    # Lag 1: global override (Settings-tabel)
    _g_secret = _get_setting(db, "bt_totp_secret", "")
    _g_sid    = _get_setting(db, "bt_totp_sid", "")
    if _g_secret:
        secret, sid, source = _g_secret, _g_sid or "global", "global"

    # Lag 2: customer.config_overrides
    site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
    customer = db.query(Customer).filter_by(id=site.customer_id).first() if site else None
    if customer and customer.config_overrides:
        _co = _json.loads(customer.config_overrides).get("bt_totp", {})
        if _co.get("secret"):
            secret, sid, source = _co["secret"], _co.get("sid", "kunde"), "kunde"

    # Lag 3: site.config_overrides
    if site and site.config_overrides:
        _so = _json.loads(site.config_overrides).get("bt_totp", {})
        if _so.get("secret"):
            secret, sid, source = _so["secret"], _so.get("sid", "site"), "site"

    # Lag 4: camera-specifik override (bt_totp_secret kolonne)
    if cam.bt_totp_secret:
        secret, sid, source = cam.bt_totp_secret, cam.bt_totp_sid or "kamera", "kamera"

    issuer = "TimeLapse Pro"
    label  = f"{issuer}:{cam.camera_name or camera_id}"
    uri    = _pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)

    buf = _io.BytesIO()
    _qrcode.make(uri).save(buf, format="PNG")
    qr_b64 = _b64.b64encode(buf.getvalue()).decode()
    return {
        "secret":   secret,
        "sid":      sid,
        "source":   source,    # hvilket lag der gælder: factory-default|global|kunde|site|kamera
        "uri":      uri,
        "qr_code":  f"data:image/png;base64,{qr_b64}",
        "is_factory_default": (source == "factory-default"),
    }


@app.post("/api/admin/cameras/{camera_id}/bt-totp-regenerate")
def regenerate_camera_bt_totp(
    camera_id: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Sæt et nyt kamera-specifikt TOTP secret (kamera-laget — højeste prioritet
    i hierarkiet). Overrider eventuelle global/kunde/site-lag for dette kamera.
    Edge skal eksplicit synkronisere (knappen 'Opdater TOTP fra CMDB' i mgmt-UI)
    før det træder i kraft — sker ALDRIG automatisk.
    """
    import pyotp as _pyotp
    import uuid as _u
    from database import Camera
    cam = db.query(Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    cam.bt_totp_secret = _pyotp.random_base32()
    cam.bt_totp_sid    = f"cam-{str(_u.uuid4())[:8]}"
    db.commit()
    log.info("BT TOTP (kamera-lag) regenereret for kamera %s sid=%s", camera_id, cam.bt_totp_sid)
    return {"sid": cam.bt_totp_sid, "message": "Nyt kamera-specifikt TOTP secret genereret — kræver eksplicit sync på edge"}


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
            "assignment_type": getattr(e, "assignment_type", "manual"),
            "notes":         e.notes,
            "active":        e.unassigned_at is None,
        }
        for e in entries
    ]


@app.get("/api/admin/devices/{device_id}/camera-location")
def get_device_camera_location(
    device_id: str,
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """Returnerer den aktive kamera-lokation (Camera) som en device er tildelt."""
    from database import Camera, DeviceAssignment, Customer, Site
    assignment = (
        db.query(DeviceAssignment)
        .filter_by(device_id=device_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .order_by(DeviceAssignment.assigned_at.desc())
        .first()
    )
    if not assignment:
        return {"assignment": None, "camera": None}

    cam = db.query(Camera).filter_by(id=assignment.camera_id).first()
    if not cam:
        return {"assignment": None, "camera": None}

    customer = db.query(Customer).filter_by(id=cam.customer_id).first() if cam.customer_id else None
    site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None

    return {
        "assignment": {
            "camera_id":    assignment.camera_id,
            "assigned_at":  assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            "assigned_by":  assignment.assigned_by,
            "assignment_type": getattr(assignment, "assignment_type", "manual"),
        },
        "camera": {
            "id":            cam.id,
            "camera_name":   cam.camera_name,
            "site_id":       cam.site_id,
            "site_name":     site.name if site else None,
            "customer_id":   cam.customer_id,
            "customer_name": customer.name if customer else None,
            "model":         cam.model,
            "notes":         cam.notes,
            "baseline_description": getattr(cam, "baseline_description", None),
            "context_notes":        getattr(cam, "context_notes", None),
        },
    }


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
    production_matches = {}
    for prod in db.query(PendingUpdate).filter(PendingUpdate.environment == "production").all():
        production_matches[(prod.update_type, prod.version, prod.scope, prod.scope_id)] = prod

    def _promotion_source(update: PendingUpdate) -> str | None:
        description = update.description or ""
        match = _re.match(r"^\[Promoveret fra ([^\]]+) til ([^\]]+)\]", description)
        if not match:
            return None
        return match.group(1)

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
            "environment": u.environment,
            "target_device_ids": json.loads(u.target_device_ids) if u.target_device_ids else None,
            "deployed_count": u.deployed_count or 0,
            "failed_count":   u.failed_count or 0,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
            "approved_by": u.approved_by,
            "deployed_at": u.deployed_at.isoformat() if u.deployed_at else None,
            "rollback_at": u.rollback_at.isoformat() if u.rollback_at else None,
            "production_promotion_id": (
                production_matches.get((u.update_type, u.version, u.scope, u.scope_id)).id
                if u.environment == "test" and production_matches.get((u.update_type, u.version, u.scope, u.scope_id))
                else None
            ),
            "production_promotion_status": (
                production_matches.get((u.update_type, u.version, u.scope, u.scope_id)).status
                if u.environment == "test" and production_matches.get((u.update_type, u.version, u.scope, u.scope_id))
                else None
            ),
            "promotion_source_environment": _promotion_source(u),
            "prod_ready": (
                u.environment == "production"
                and u.status == "pending"
                and _promotion_source(u) in {"lab", "test", "staging"}
            ),
        }
        for u in updates
    ]

UPDATE_CATEGORIES = [
    {
        "key": "os_security",
        "label": "OS Security update",
        "types": ["os_security"],
        "installed_field": "os_name",
    },
    {
        "key": "os_update",
        "label": "OS update",
        "types": ["os_updates", "os_update"],
        "installed_field": "os_name",
    },
    {
        "key": "timelapse_security",
        "label": "Timelapse Pro Security update",
        "types": ["app_security", "timelapse_security", "timelapse_pro_security"],
        "installed_field": "app_version",
    },
    {
        "key": "timelapse_update",
        "label": "Timelapse Pro update",
        "types": ["app_updates", "app_update", "timelapse_update", "timelapse_pro_update"],
        "installed_field": "app_version",
    },
    {
        "key": "application_security",
        "label": "Application Security update",
        "types": ["application_security", "dependency_security", "third_party_security"],
        "installed_field": "venv_packages",
    },
    {
        "key": "application_update",
        "label": "Application update",
        "types": ["application_update", "application_updates", "dependency_updates", "third_party_updates"],
        "installed_field": "venv_packages",
    },
]

UPDATE_TYPE_TO_CATEGORY = {
    update_type: category["key"]
    for category in UPDATE_CATEGORIES
    for update_type in category["types"]
}

# Device IDs that are placeholders / test fixtures and must be excluded from GRC, compliance and resilience
_PLACEHOLDER_DEVICE_IDS: frozenset[str] = frozenset({
    "TL-MACMINI-HEADEND-TEST-1",
})


def _is_placeholder_device(device_id: str) -> bool:
    """Return True if device_id is a known placeholder that should be excluded from risk/compliance views."""
    did = device_id.lower()
    if device_id in _PLACEHOLDER_DEVICE_IDS:
        return True
    # Legacy test naming conventions
    if did == "test" or did == "test-device" or did.startswith("test-"):
        return True
    return False

UPDATE_TYPE_POLICY_KEY = {
    "os_security": "os_security",
    "os_updates": "os_updates",
    "os_update": "os_updates",
    "application_security": "application_security",
    "dependency_security": "application_security",
    "third_party_security": "application_security",
    "application_update": "application_updates",
    "application_updates": "application_updates",
    "dependency_updates": "application_updates",
    "third_party_updates": "application_updates",
    "app_security": "timelapse_security",
    "timelapse_security": "timelapse_security",
    "timelapse_pro_security": "timelapse_security",
    "app_updates": "timelapse_updates",
    "app_update": "timelapse_updates",
    "timelapse_update": "timelapse_updates",
    "timelapse_pro_update": "timelapse_updates",
}

LEGACY_POLICY_ALIASES = {
    "app_security": "timelapse_security",
    "app_updates": "timelapse_updates",
}

HEADEND_LOCAL_OWNER = os.getenv("TIMELAPSE_HEADEND_OWNER", Path.home().name)
HEADEND_LOCAL_HOME = os.getenv("TIMELAPSE_HEADEND_HOME", str(Path.home()))
HEADEND_LAUNCH_AGENTS = str(Path(HEADEND_LOCAL_HOME) / "Library" / "LaunchAgents")

HEADEND_PLATFORM_BREW_ALLOWLIST = {
    "certbot": {
        "owner": HEADEND_LOCAL_OWNER,
        "home": HEADEND_LOCAL_HOME,
        "runtime_bin": "/opt/homebrew/bin/certbot",
        "description": "Certbot ACME client",
        "preflight": [
            ["/opt/homebrew/bin/certbot", "--version"],
            ["/opt/homebrew/bin/certbot", "certificates"],
            ["/bin/launchctl", "print", "system/dk.froekjaer.certbot-renewal"],
        ],
        "postflight": [
            ["/opt/homebrew/bin/certbot", "--version"],
            ["/opt/homebrew/bin/certbot", "certificates"],
            ["/bin/launchctl", "print", "system/dk.froekjaer.certbot-renewal"],
        ],
        "extra_backup_paths": ["/Library/LaunchDaemons/dk.froekjaer.certbot-renewal.plist"],
    },
    "ffmpeg": {
        "owner": HEADEND_LOCAL_OWNER,
        "home": HEADEND_LOCAL_HOME,
        "runtime_bin": "/opt/homebrew/bin/ffmpeg",
        "description": "FFmpeg timelapse rendering runtime",
        "preflight": [
            ["/opt/homebrew/bin/ffmpeg", "-version"],
        ],
        "postflight": [
            ["/opt/homebrew/bin/ffmpeg", "-version"],
            ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=1", "-frames:v", "1", "-f", "null", "-"],
        ],
    },
    "nginx": {
        "service": "nginx",
        "service_label": "homebrew.mxcl.nginx",
        "launch_agent": str(Path(HEADEND_LAUNCH_AGENTS) / "homebrew.mxcl.nginx.plist"),
        "owner": HEADEND_LOCAL_OWNER,
        "home": HEADEND_LOCAL_HOME,
        "runtime_bin": "/opt/homebrew/bin/nginx",
        "description": "Nginx reverse proxy",
        "preflight": [
            ["/opt/homebrew/bin/nginx", "-v"],
            ["/opt/homebrew/bin/nginx", "-t"],
        ],
        "postflight": [
            ["/opt/homebrew/bin/nginx", "-v"],
            ["/opt/homebrew/bin/nginx", "-t"],
            ["/usr/bin/curl", "-fsS", "-I", "http://127.0.0.1:8000/openapi.json"],
        ],
        "extra_backup_paths": [
            "/opt/homebrew/etc/nginx/nginx.conf",
            "/opt/homebrew/etc/nginx/servers",
        ],
    },
    "node": {
        "owner": HEADEND_LOCAL_OWNER,
        "home": HEADEND_LOCAL_HOME,
        "runtime_bin": "/opt/homebrew/bin/node",
        "description": "Node.js build/runtime tooling",
        "preflight": [
            ["/opt/homebrew/bin/node", "--version"],
            ["/opt/homebrew/bin/npm", "--version"],
        ],
        "postflight": [
            ["/opt/homebrew/bin/node", "--version"],
            ["/opt/homebrew/bin/node", "-e", "console.log(process.version)"],
            ["/opt/homebrew/bin/npm", "--version"],
        ],
    },
    "postgresql@17": {
        "service": "postgresql@17",
        "service_label": "homebrew.mxcl.postgresql@17",
        "launch_agent": str(Path(HEADEND_LAUNCH_AGENTS) / "homebrew.mxcl.postgresql@17.plist"),
        "owner": HEADEND_LOCAL_OWNER,
        "home": HEADEND_LOCAL_HOME,
        "runtime_bin": "/opt/homebrew/opt/postgresql@17/bin/psql",
        "description": "PostgreSQL database runtime",
        "preflight": [
            ["/opt/homebrew/opt/postgresql@17/bin/psql", "--version"],
            ["/opt/homebrew/opt/postgresql@17/bin/pg_isready", "-h", "127.0.0.1", "-p", "5432"],
            ["/opt/homebrew/opt/postgresql@17/bin/psql", "postgresql://timelapse@localhost/timelapse_db", "-c", "select current_database(), current_user, version();"],
            ["/opt/homebrew/bin/brew", "services", "list"],
        ],
        "postflight": [
            ["/opt/homebrew/opt/postgresql@17/bin/psql", "--version"],
            ["/opt/homebrew/opt/postgresql@17/bin/pg_isready", "-h", "127.0.0.1", "-p", "5432"],
            ["/opt/homebrew/opt/postgresql@17/bin/psql", "postgresql://timelapse@localhost/timelapse_db", "-c", "select count(*) from pending_updates;"],
            ["/opt/homebrew/opt/postgresql@17/bin/psql", "postgresql://timelapse@localhost/timelapse_db", "-c", "select now();"],
        ],
        "extra_backup_paths": [
            str(Path(HEADEND_LAUNCH_AGENTS) / "homebrew.mxcl.postgresql@17.plist"),
        ],
        "requires_db_backup": True,
    },
    "ollama": {
        "service": "ollama",
        "service_label": "homebrew.mxcl.ollama",
        "launch_agent": str(Path(HEADEND_LAUNCH_AGENTS) / "homebrew.mxcl.ollama.plist"),
        "runtime_bin": "/Applications/Ollama.app/Contents/Resources/ollama",
        "owner": HEADEND_LOCAL_OWNER,
        "home": HEADEND_LOCAL_HOME,
        "description": "Ollama AI runtime",
    },
}

HEADEND_PLATFORM_MANUAL_PROFILES = {}

_headend_update_lock = _threading.Lock()
_headend_update_status: dict[int, dict] = {}


def _headend_update_status_for(update_id: int) -> dict:
    return _headend_update_status.get(update_id, {
        "update_id": update_id,
        "running": False,
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "message": None,
        "phase": "idle",
        "backup_file": None,
        "preflight": None,
        "postflight": None,
        "rollback_performed": False,
        "rollback_message": None,
        "stdout_tail": "",
        "stderr_tail": "",
    })


def _parse_brew_formula_from_update(update: PendingUpdate) -> str | None:
    version = (update.version or "").strip()
    if " " not in version:
        return None
    formula = version.split(" ", 1)[0].strip()
    return formula if formula in HEADEND_PLATFORM_BREW_ALLOWLIST else None


def _parse_headend_formula_name(update: PendingUpdate) -> str | None:
    version = (update.version or "").strip()
    if " " not in version:
        return None
    return version.split(" ", 1)[0].strip()


def _brew_env_for(owner_home: str) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": owner_home,
        "PATH": "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOMEBREW_NO_AUTO_UPDATE": "1",
        "HOMEBREW_NO_ENV_HINTS": "1",
    }


def _run_brew_as_owner(owner: str, owner_home: str, args: list[str], timeout_s: int = 900) -> _subprocess.CompletedProcess:
    return _subprocess.run(
        ["/usr/bin/sudo", "-u", owner, "/usr/bin/env", *[f"{k}={v}" for k, v in {
            "HOME": owner_home,
            "PATH": "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOMEBREW_NO_AUTO_UPDATE": "1",
            "HOMEBREW_NO_ENV_HINTS": "1",
        }.items()], "/opt/homebrew/bin/brew", *args],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def _uid_for_user(username: str) -> str:
    result = _subprocess.run(["/usr/bin/id", "-u", username], capture_output=True, text=True, timeout=10)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Kunne ikke finde uid for {username}: {result.stderr[-300:]}")
    return result.stdout.strip()


def _headend_status_update(update_id: int, **fields) -> None:
    current = _headend_update_status_for(update_id)
    current.update(fields)
    _headend_update_status[update_id] = current


def _command_text(result: _subprocess.CompletedProcess) -> str:
    return (result.stdout or "") + (result.stderr or "")


def _copy_launch_agent_for_rollback(meta: dict, update_id: int) -> str | None:
    plist = meta.get("launch_agent")
    if not plist or not os.path.exists(plist):
        return None
    rollback_dir = Path("/tmp") / "timelapse-update-rollback"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    dst = rollback_dir / f"update-{update_id}-{Path(plist).name}"
    _shutil.copy2(plist, dst)
    return str(dst)


def _restore_launch_agent_from_backup(meta: dict, backup_plist: str | None) -> str:
    if not backup_plist:
        return "Ingen LaunchAgent backup at genskabe"
    target = meta.get("launch_agent")
    if not target:
        return "Ingen LaunchAgent target defineret"
    _shutil.copy2(backup_plist, target)
    return _restart_launch_agent(meta)


def _restart_launch_agent(meta: dict) -> str:
    uid = _uid_for_user(meta["owner"])
    label = meta["service_label"]
    plist = meta["launch_agent"]
    outputs: list[str] = []
    launchctl_prefix = []
    if os.geteuid() == 0 and meta.get("owner"):
        launchctl_prefix = ["/usr/bin/sudo", "-u", meta["owner"]]
    for cmd in (
        ["/bin/launchctl", "bootout", f"gui/{uid}/{label}"],
        ["/bin/launchctl", "bootstrap", f"gui/{uid}", plist],
        ["/bin/launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
    ):
        run_cmd = [*launchctl_prefix, *cmd]
        result = _subprocess.run(run_cmd, capture_output=True, text=True, timeout=120)
        outputs.append(f"$ {' '.join(run_cmd)}\n{result.stdout}{result.stderr}")
        if cmd[1] != "bootout" and result.returncode != 0:
            raise RuntimeError(f"launchctl fejlede: {result.stderr[-1000:] or result.stdout[-1000:]}")
    return "\n".join(outputs)


def _ollama_service_snapshot(meta: dict, log_offset: int | None = None) -> dict:
    runtime_bin = meta.get("runtime_bin") or "/opt/homebrew/bin/ollama"
    snapshot: dict[str, object] = {"runtime_bin": runtime_bin}
    for label, cmd, timeout_s in (
        ("runtime_version", [runtime_bin, "--version"], 30),
        ("api_version", ["/usr/bin/curl", "-fsS", "http://127.0.0.1:11434/api/version"], 20),
        ("models", [runtime_bin, "list"], 60),
    ):
        try:
            result = _subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=_brew_env_for(meta["home"]),
            )
            snapshot[label] = {
                "ok": result.returncode == 0,
                "output": _command_text(result)[-1500:],
            }
        except Exception as exc:
            snapshot[label] = {"ok": False, "output": str(exc)}
    log_path = Path("/opt/homebrew/var/log/ollama.log")
    if log_path.exists():
        try:
            with log_path.open("r", errors="replace") as f:
                if log_offset is not None:
                    f.seek(log_offset)
                snapshot["new_log_tail"] = f.read()[-2500:]
        except Exception as exc:
            snapshot["new_log_tail"] = f"log read failed: {exc}"
    return snapshot


def _run_profile_commands(meta: dict, commands: list[list[str]], label: str, timeout_s: int = 180) -> dict:
    results: dict[str, object] = {}
    for idx, cmd in enumerate(commands):
        key = f"{label}_{idx + 1}"
        try:
            result = _subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=_brew_env_for(meta["home"]),
            )
            output = _command_text(result)
            results[key] = {
                "cmd": " ".join(cmd),
                "ok": result.returncode == 0,
                "output": output[-2500:],
            }
            if result.returncode != 0:
                raise RuntimeError(f"{label} fejlede: {' '.join(cmd)}\n{output[-1200:]}")
        except Exception as exc:
            results[key] = {
                "cmd": " ".join(cmd),
                "ok": False,
                "output": str(exc)[-2500:],
            }
            raise
    return results


def _headend_profile_snapshot(formula: str, meta: dict, label: str, log_offset: int | None = None) -> dict:
    if formula == "ollama":
        return _ollama_service_snapshot(meta, log_offset)
    commands = meta.get(label, [])
    return _run_profile_commands(meta, commands, label) if commands else {}


def _validate_ollama_runtime(meta: dict) -> str:
    runtime_bin = meta.get("runtime_bin") or "/opt/homebrew/bin/ollama"
    version = _subprocess.run(
        [runtime_bin, "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        env=_brew_env_for(meta["home"]),
    )
    if version.returncode != 0:
        raise RuntimeError(f"Ollama version check fejlede: {version.stderr[-1000:] or version.stdout[-1000:]}")
    generate = _subprocess.run(
        [runtime_bin, "run", "llama3.2:latest", "Svar kun OK"],
        capture_output=True,
        text=True,
        timeout=180,
        env=_brew_env_for(meta["home"]),
    )
    if generate.returncode != 0:
        raise RuntimeError(f"Ollama inference validering fejlede: {generate.stderr[-1500:] or generate.stdout[-1500:]}")
    api_version = _subprocess.run(
        ["/usr/bin/curl", "-fsS", "http://127.0.0.1:11434/api/version"],
        capture_output=True,
        text=True,
        timeout=20,
        env=_brew_env_for(meta["home"]),
    )
    if api_version.returncode != 0:
        raise RuntimeError(f"Ollama API validering fejlede: {api_version.stderr[-1000:] or api_version.stdout[-1000:]}")
    return f"{version.stdout}{version.stderr}\nAPI OK:\n{api_version.stdout}\nInference OK:\n{generate.stdout[-1000:]}"


def _validate_headend_profile(formula: str, meta: dict) -> str:
    if formula == "ollama":
        return _validate_ollama_runtime(meta)
    results = _run_profile_commands(meta, meta.get("postflight", []), "postflight")
    return _json.dumps(results, indent=2, ensure_ascii=False)[-3000:]


def _run_headend_platform_update(update_id: int, requested_by: str) -> None:
    started = now_utc()
    _headend_update_status[update_id] = {
        "update_id": update_id,
        "running": True,
        "status": "running",
        "started_at": started.isoformat(),
        "finished_at": None,
        "message": "Installerer Headend platformopdatering",
        "phase": "starting",
        "backup_file": None,
        "preflight": None,
        "postflight": None,
        "rollback_performed": False,
        "rollback_message": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    with _headend_update_lock:
        db = SessionLocal()
        rollback_plist = None
        backup_file = None
        log_offset = None
        preflight = None
        try:
            update = db.query(PendingUpdate).filter_by(id=update_id).first()
            if not update:
                raise RuntimeError("Opdatering ikke fundet")
            formula = _parse_brew_formula_from_update(update)
            if not formula:
                raise RuntimeError("Kun allowlistede Headend Homebrew-opdateringer kan installeres her")
            meta = HEADEND_PLATFORM_BREW_ALLOWLIST[formula]
            if update.status != "approved":
                raise RuntimeError("Opdateringen skal være godkendt før installation")
            production_validation_only = False
            if update.environment != "test":
                if update.environment == "production":
                    deployed_test = db.query(PendingUpdate).filter(
                        PendingUpdate.update_type == update.update_type,
                        PendingUpdate.version == update.version,
                        PendingUpdate.environment == "test",
                        PendingUpdate.scope == update.scope,
                        PendingUpdate.scope_id == update.scope_id,
                        PendingUpdate.status == "deployed",
                    ).order_by(PendingUpdate.deployed_at.desc()).first()
                    if not deployed_test:
                        raise RuntimeError("Production kræver deployed test/lab-evidens for samme Headend update")
                    production_validation_only = True
                else:
                    raise RuntimeError("Headend UI-installation kræver test/lab eller production promotion fra deployed test")
            if update.scope != "device" or update.scope_id != "TL-MACMINI-HEADEND-TEST-1":
                raise RuntimeError("Headend platformopdatering skal være scoped til Headend-enheden")

            log_path = Path("/opt/homebrew/var/log/ollama.log") if formula == "ollama" else None
            if log_path and log_path.exists():
                log_offset = log_path.stat().st_size

            _headend_status_update(update_id, phase="preflight", message="Kører preflight før Headend-opdatering")
            before = _run_brew_as_owner(meta["owner"], meta["home"], ["list", "--versions", formula], timeout_s=60)
            preflight = _headend_profile_snapshot(formula, meta, "preflight", log_offset)
            _headend_status_update(update_id, preflight=preflight)

            _headend_status_update(update_id, phase="backup", message="Tager pre-update backup")
            rollback_plist = _copy_launch_agent_for_rollback(meta, update_id)
            extra_paths = [p for p in [rollback_plist, meta.get("launch_agent"), *(meta.get("extra_backup_paths") or [])] if p]
            backup_file = _run_backup_archive(f"pre-update-{update_id}-{formula}", extra_paths=extra_paths)
            _headend_status_update(update_id, backup_file=backup_file)

            restart_output = ""
            install = _subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            if production_validation_only:
                _headend_status_update(update_id, phase="install", message=f"Aktiverer {formula} i production uden ny installation")
                restart_output = "Production promotion validation only; package was already deployed in test/lab on this Headend."
            else:
                _headend_status_update(update_id, phase="install", message=f"Installerer {formula} via lab-godkendt flow")
                install = _run_brew_as_owner(meta["owner"], meta["home"], ["upgrade", formula], timeout_s=1800)
                if install.returncode != 0 and "already installed" not in (install.stdout + install.stderr).lower():
                    raise RuntimeError(f"brew upgrade fejlede: {install.stderr[-1000:] or install.stdout[-1000:]}")

                if meta.get("service_label") and meta.get("launch_agent"):
                    _headend_status_update(update_id, phase="restart", message=f"Genindlæser {formula} service")
                    restart_output = _restart_launch_agent(meta)
                else:
                    _headend_status_update(update_id, phase="restart", message=f"{formula} har ingen service der skal genstartes")

            _headend_status_update(update_id, phase="postflight", message="Validerer service, API og inference")
            validation_output = _validate_headend_profile(formula, meta)
            postflight = _headend_profile_snapshot(formula, meta, "postflight", log_offset)
            new_log = str(postflight.get("new_log_tail") or "")
            if formula == "ollama" and "llama-server binary not found" in new_log:
                raise RuntimeError("Postflight fandt Ollama runtime-fejl i log: llama-server binary not found")
            after = _run_brew_as_owner(meta["owner"], meta["home"], ["list", "--versions", formula], timeout_s=60)

            update.status = "deployed"
            update.deployed_at = now_utc()
            update.deployed_count = (update.deployed_count or 0) + 1
            evidence = (
                f"\n\n{'PROD activation' if production_validation_only else 'LAB evidence'} {now_utc().isoformat()}: "
                f"pre_update_backup={backup_file}; preflight/runtime={preflight.get('runtime_version') if isinstance(preflight, dict) else 'n/a'}; "
                f"postflight={postflight if isinstance(postflight, dict) else 'n/a'}; "
                f"profile validation OK; install_mode={'validation_only_after_deployed_test' if production_validation_only else 'brew_upgrade'}."
            )
            update.description = ((update.description or "").rstrip() + evidence)[-6000:]
            db.commit()
            _headend_update_status[update_id] = {
                "update_id": update_id,
                "running": False,
                "status": "deployed",
                "started_at": started.isoformat(),
                "finished_at": now_utc().isoformat(),
                "message": f"{formula} {'aktiveret i production' if production_validation_only else 'installeret og service genstartet'}",
                "phase": "complete",
                "backup_file": backup_file,
                "preflight": preflight,
                "postflight": postflight,
                "rollback_performed": False,
                "rollback_message": None,
                "stdout_tail": "\n".join([before.stdout, install.stdout, restart_output, validation_output, after.stdout])[-3000:],
                "stderr_tail": "\n".join([before.stderr, install.stderr, after.stderr])[-3000:],
            }
            log.info("Headend platform update deployed: update=%s formula=%s by=%s", update_id, formula, requested_by)
        except Exception as exc:
            rollback_message = None
            rollback_performed = False
            if rollback_plist:
                try:
                    rollback_message = _restore_launch_agent_from_backup(meta, rollback_plist)
                    rollback_performed = True
                except Exception as rollback_exc:
                    rollback_message = f"Rollback fejlede: {rollback_exc}"
            db.rollback()
            update = db.query(PendingUpdate).filter_by(id=update_id).first()
            if update:
                update.failed_count = (update.failed_count or 0) + 1
                failure_evidence = (
                    f"\n\nLAB failure {now_utc().isoformat()}: "
                    f"phase={_headend_update_status_for(update_id).get('phase')}; "
                    f"pre_update_backup={backup_file}; rollback_performed={rollback_performed}; "
                    f"error={str(exc)[:700]}"
                )
                update.description = ((update.description or "").rstrip() + failure_evidence)[-6000:]
                db.commit()
            _headend_update_status[update_id] = {
                **_headend_update_status_for(update_id),
                "running": False,
                "status": "failed",
                "finished_at": now_utc().isoformat(),
                "message": str(exc),
                "backup_file": backup_file,
                "rollback_performed": rollback_performed,
                "rollback_message": rollback_message,
            }
            log.warning("Headend platform update failed: update=%s error=%s", update_id, exc)
        finally:
            db.close()


@app.get("/api/updates/{update_id}/headend-deploy/status")
def headend_platform_update_status(
    update_id: int,
    _user=require_role("super_admin", "admin"),
):
    return _headend_update_status_for(update_id)


@app.post("/api/updates/{update_id}/headend-deploy")
def start_headend_platform_update(
    update_id: int,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    if update.status != "approved":
        raise HTTPException(status_code=400, detail="Opdateringen skal være godkendt før installation")
    if not _parse_brew_formula_from_update(update):
        raise HTTPException(status_code=400, detail="Denne opdatering kan ikke installeres som Headend Homebrew-opdatering")
    if _headend_update_lock.locked():
        raise HTTPException(status_code=409, detail="Der kører allerede en Headend-opdatering")
    thread = _threading.Thread(
        target=_run_headend_platform_update,
        args=(update_id, current_user.username),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "status": _headend_update_status_for(update_id)}


def _status_rank(status: str | None) -> int:
    return {
        "pending": 0,
        "approved": 1,
        "rollback_requested": 2,
        "blocked": 3,
        "failed": 4,
        "rolled_back": 5,
        "deployed": 6,
        "rejected": 7,
    }.get(status or "", 7)


def _update_is_matrix_candidate(update: PendingUpdate) -> bool:
    return update.status not in {"rejected", "cancelled"}


def _parse_target_device_ids(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(v) for v in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def _update_applies_to_device(update: PendingUpdate, device: Device | None, inv: DeviceInventory) -> bool:
    target_ids = _parse_target_device_ids(update.target_device_ids)
    if target_ids:
        return inv.device_id in target_ids
    if update.scope == "global":
        return True
    if update.scope == "device":
        return update.scope_id == inv.device_id
    if update.scope == "customer" and device:
        return update.scope_id == device.customer_id
    if update.scope == "site" and device:
        return update.scope_id == device.site_id
    return False


def _installed_value(inv: DeviceInventory, category_key: str) -> str | None:
    if category_key.startswith("os_"):
        parts = [p for p in [inv.os_name, inv.kernel_version] if p]
        return " / ".join(parts) if parts else None
    if category_key.startswith("timelapse_"):
        return inv.app_version
    if inv.venv_packages:
        try:
            packages = json.loads(inv.venv_packages)
            if isinstance(packages, dict):
                return f"{len(packages)} Python package(s)"
        except Exception:
            return "Package inventory rapporteret"
    return None


def _parse_update_version_gap(update: PendingUpdate | None, installed: str | None = None) -> dict:
    if not update:
        return {
            "current_version": installed,
            "latest_available_version": None,
            "package_count": None,
            "component": None,
            "version_gap_label": None,
        }
    version = (update.version or "").strip()
    component = None
    current = installed
    latest = version or None
    package_count = None
    match = _re.match(r"(.+?)\s+(.+?)\s*->\s*(.+)$", version)
    if match:
        component, current, latest = [part.strip() for part in match.groups()]
    else:
        count_match = _re.match(r"(\d+)\s+pakker", version)
        if count_match:
            package_count = int(count_match.group(1))
            latest = f"{package_count} pakker klar"
    label = f"{current or '-'} -> {latest or '-'}" if latest else None
    return {
        "current_version": current,
        "latest_available_version": latest,
        "package_count": package_count,
        "component": component,
        "version_gap_label": label,
    }


def _business_impact(inv: DeviceInventory | None, device: Device | None, update_type: str | None = None) -> tuple[int, list[str]]:
    factors: list[str] = []
    score = 35
    env = (inv.environment if inv else None) or (device.environment if device and hasattr(device, "environment") else None) or "production"
    if env == "production":
        score += 25
        factors.append("produktionsmiljø")
    elif env == "staging":
        score += 12
        factors.append("stagingmiljø")
    else:
        score -= 12
        factors.append("LAB/R&D miljø")

    device_id = (inv.device_id if inv else None) or (device.device_id if device else "")
    hostname = (inv.hostname if inv else "") or ""
    if "headend" in device_id.lower() or "headend" in hostname.lower() or "macmini" in device_id.lower():
        score += 20
        factors.append("headend/central komponent")
    if device and (device.customer_id or device.site_id):
        score += 8
        factors.append("kunde/site-tilknytning")
    if device and device.status and device.status != "online":
        score += 6
        factors.append(f"enhedsstatus: {device.status}")
    if inv and inv.data_partition_used_pct and inv.data_partition_used_pct >= 85:
        score += 8
        factors.append("høj data-partition udnyttelse")
    if update_type and "security" in update_type:
        score += 10
        factors.append("sikkerhedsrettelse")
    return max(0, min(100, score)), factors


def _risk_assessment(
    update_type: str | None,
    severity: str | None,
    inv: DeviceInventory | None = None,
    device: Device | None = None,
    status: str | None = None,
) -> dict:
    severity_score = {
        "critical": 95,
        "high": 78,
        "medium": 55,
        "low": 28,
    }.get((severity or "low").lower(), 35)
    category = UPDATE_TYPE_TO_CATEGORY.get(update_type or "", update_type or "unknown")
    category_score = {
        "timelapse_security": 90,
        "os_security": 84,
        "application_security": 78,
        "timelapse_update": 58,
        "application_update": 48,
        "os_update": 42,
    }.get(category, 45)
    impact_score, factors = _business_impact(inv, device, update_type)
    process_score = 0
    if status in ("failed", "rolled_back", "rollback_requested", "blocked"):
        process_score = 18
        factors.append(f"tidligere deployment-status: {status}")
    elif status == "approved":
        process_score = 6
        factors.append("godkendt men endnu ikke deployet")

    score = round((severity_score * 0.38) + (category_score * 0.22) + (impact_score * 0.32) + process_score)
    score = max(0, min(100, score))
    if score >= 85:
        level = "critical"
    elif score >= 70:
        level = "high"
    elif score >= 45:
        level = "medium"
    else:
        level = "low"
    return {
        "score": score,
        "level": level,
        "severity_component": severity_score,
        "category_component": category_score,
        "business_impact_component": impact_score,
        "factors": factors,
    }


@app.get("/api/updates/device-matrix")
def list_update_device_matrix(
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """CMDB-forankret opdateringsmatrix pr. enhed og update-kategori."""
    inventories = db.query(DeviceInventory).order_by(DeviceInventory.device_id).all()
    device_map = {d.device_id: d for d in db.query(Device).all()}
    updates = db.query(PendingUpdate).order_by(PendingUpdate.created_at.desc()).all()
    category_meta = [
        {"key": c["key"], "label": c["label"], "types": c["types"]}
        for c in UPDATE_CATEGORIES
    ]
    devices = []
    for inv in inventories:
        if inv.device_id.lower() == "test" and not inv.hostname:
            continue
        device = device_map.get(inv.device_id)
        categories = {}
        device_updates = [
            u for u in updates
            if _update_is_matrix_candidate(u) and _update_applies_to_device(u, device, inv)
        ]
        for category in UPDATE_CATEGORIES:
            candidates = [
                u for u in device_updates
                if u.update_type in category["types"]
            ]
            candidates.sort(
                key=lambda u: (
                    _status_rank(u.status),
                    -((u.created_at or now_utc()).timestamp()),
                )
            )
            update = candidates[0] if candidates else None
            installed = _installed_value(inv, category["key"])
            if update:
                state = "needs_approval" if update.status == "pending" else update.status
                risk = _risk_assessment(update.update_type, update.severity, inv, device, update.status)
                gap = _parse_update_version_gap(update, installed)
                categories[category["key"]] = {
                    "state": state,
                    "installed": installed,
                    "available": update.version,
                    "current_version": gap["current_version"],
                    "latest_available_version": gap["latest_available_version"],
                    "version_gap_label": gap["version_gap_label"],
                    "package_count": gap["package_count"],
                    "component": gap["component"],
                    "missing": update.status in ("pending", "approved", "rollback_requested"),
                    "pending_update_id": update.id,
                    "update_type": update.update_type,
                    "description": update.description,
                    "severity": update.severity,
                    "status": update.status,
                    "created_at": update.created_at.isoformat() if update.created_at else None,
                    "risk": risk,
                }
            else:
                categories[category["key"]] = {
                    "state": "no_update_reported" if installed else "no_inventory",
                    "installed": installed,
                    "available": None,
                    "current_version": installed,
                    "latest_available_version": None,
                    "version_gap_label": None,
                    "package_count": None,
                    "component": None,
                    "missing": False,
                    "pending_update_id": None,
                    "update_type": None,
                    "description": None,
                    "severity": None,
                    "status": None,
                    "created_at": None,
                    "risk": _risk_assessment(category["types"][0], "low", inv, device, None),
                }
        device_risks = [c["risk"]["score"] for c in categories.values() if c.get("missing")]
        devices.append({
            "device_id": inv.device_id,
            "cmdb_ref": f"CMDB:{inv.device_id}",
            "environment": inv.environment,
            "hardware_model": inv.hardware_model,
            "hostname": inv.hostname,
            "os_name": inv.os_name,
            "kernel_version": inv.kernel_version,
            "app_version": inv.app_version,
            "customer_name": device.customer_name if device else None,
            "site_name": device.site_name if device else None,
            "status": device.status if device else "unknown",
            "last_seen": device.last_seen.isoformat() if device and device.last_seen else None,
            "inventory_reported_at": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
            "categories": categories,
            "risk_score": max(device_risks) if device_risks else 0,
            "missing_count": sum(1 for c in categories.values() if c.get("missing")),
        })
    return {"categories": category_meta, "devices": devices}


@app.get("/api/grc/dashboard")
def grc_dashboard(
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Kvantitativ GRC-risk baseret på CMDB, missing updates, miljø og deployment-proces."""
    inventories = db.query(DeviceInventory).order_by(DeviceInventory.device_id).all()
    device_map = {d.device_id: d for d in db.query(Device).all()}
    updates = db.query(PendingUpdate).order_by(PendingUpdate.created_at.desc()).all()
    device_rows: list[dict] = []
    totals = {
        "devices": 0,
        "security_updates_missing": 0,
        "functional_updates_missing": 0,
        "blocked_updates": 0,
        "approved_updates": 0,
        "deployed_updates": 0,
        "rolled_back_updates": 0,
    }
    for inv in inventories:
        if _is_placeholder_device(inv.device_id):
            continue
        device = device_map.get(inv.device_id)
        device_updates = [
            u for u in updates
            if _update_is_matrix_candidate(u) and _update_applies_to_device(u, device, inv)
        ]
        risk_items: list[dict] = []
        missing_security = 0
        missing_functional = 0
        blocked = 0
        approved = 0
        for update in device_updates:
            category = UPDATE_TYPE_TO_CATEGORY.get(update.update_type or "", update.update_type or "unknown")
            installed = _installed_value(inv, category if category in {c["key"] for c in UPDATE_CATEGORIES} else "")
            gap = _parse_update_version_gap(update, installed)
            risk = _risk_assessment(update.update_type, update.severity, inv, device, update.status)
            if "security" in (update.update_type or "") and update.status in {"pending", "approved", "blocked", "rollback_requested"}:
                missing_security += 1
            elif update.status in {"pending", "approved", "blocked", "rollback_requested"}:
                missing_functional += 1
            if update.status == "blocked":
                blocked += 1
            if update.status == "approved":
                approved += 1
            risk_items.append({
                "update_id": update.id,
                "update_type": update.update_type,
                "category": category,
                "status": update.status,
                "severity": update.severity,
                "environment": update.environment,
                "current_version": gap["current_version"],
                "latest_available_version": gap["latest_available_version"],
                "package_count": gap["package_count"],
                "component": gap["component"],
                "risk": risk,
            })
        active_scores = [
            item["risk"]["score"]
            for item in risk_items
            if item["status"] in {"pending", "approved", "blocked", "rollback_requested"}
        ]
        max_score = max(active_scores) if active_scores else 0
        totals["devices"] += 1
        totals["security_updates_missing"] += missing_security
        totals["functional_updates_missing"] += missing_functional
        totals["blocked_updates"] += blocked
        totals["approved_updates"] += approved
        totals["deployed_updates"] += sum(1 for u in device_updates if u.status == "deployed")
        totals["rolled_back_updates"] += sum(1 for u in device_updates if u.status == "rolled_back")
        device_rows.append({
            "device_id": inv.device_id,
            "hostname": inv.hostname,
            "environment": inv.environment,
            "customer_name": device.customer_name if device else None,
            "site_name": device.site_name if device else None,
            "status": device.status if device else "unknown",
            "last_seen": device.last_seen.isoformat() if device and device.last_seen else None,
            "risk_score": max_score,
            "risk_level": "critical" if max_score >= 85 else "high" if max_score >= 70 else "medium" if max_score >= 45 else "low",
            "missing_security_updates": missing_security,
            "missing_functional_updates": missing_functional,
            "blocked_updates": blocked,
            "approved_updates": approved,
            "top_risks": sorted(risk_items, key=lambda item: item["risk"]["score"], reverse=True)[:5],
        })
    fleet_scores = [d["risk_score"] for d in device_rows]
    fleet_score = round(sum(fleet_scores) / len(fleet_scores)) if fleet_scores else 0
    return {
        "generated_at": now_utc().isoformat(),
        "model": "timelapse.grc_quantitative_risk.v1",
        "summary": {
            **totals,
            "fleet_risk_score": fleet_score,
            "highest_device_risk": max(fleet_scores) if fleet_scores else 0,
        },
        "risk_model": {
            "not_cvss_only": True,
            "components": [
                "technical severity",
                "update category",
                "business impact from CMDB environment/customer/site/headend role",
                "deployment process status",
                "blocked or rollback history",
            ],
        },
        "devices": sorted(device_rows, key=lambda row: row["risk_score"], reverse=True),
    }

class ApprovePayload(BaseModel):
    environment: Optional[str] = "production"
    scope: Optional[str] = None
    scope_id: Optional[str] = None
    target_device_ids: Optional[list] = None


class ChangeTicketPayload(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    rollback_plan: Optional[str] = None
    maintenance_window: Optional[str] = None
    reboot_required: Optional[bool] = False
    status: Optional[str] = "ready"


class ChangeDecisionPayload(BaseModel):
    notes: Optional[str] = None


class OsCatalogImportPayload(BaseModel):
    device_id: str
    apt_list_text: str
    source: Optional[str] = None
    environment: Optional[str] = "lab"
    create_updates: Optional[bool] = True


class OsCatalogBuilderPayload(BaseModel):
    device_id: str
    environment: Optional[str] = "lab"
    image: Optional[str] = "ubuntu:24.04"
    architecture: Optional[str] = "arm64"
    source: Optional[str] = None
    create_updates: Optional[bool] = True


class PromotePayload(BaseModel):
    target_environment: Optional[str] = "production"


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sign_payload(payload: str) -> tuple[str, str]:
    """Signér payload med OpenPGP hvis en key er konfigureret.

    Uden signing key returneres en hash-binding, som er nyttig i LAB men ikke
    en kryptografisk bruger-/release-signatur.
    """
    digest = _sha256_text(payload)
    key_id = os.getenv("CHANGE_TICKET_GPG_KEY") or os.getenv("TIMELAPSE_GPG_KEY")
    if not key_id:
        return f"sha256:{digest}", "system-hash"
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(payload)
            payload_path = f.name
        result = _subprocess.run(
            [
                "gpg", "--batch", "--yes", "--armor",
                "--local-user", key_id,
                "--detach-sign", "--output", "-", payload_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        try:
            os.unlink(payload_path)
        except Exception:
            pass
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), key_id
        log.warning("GPG signering fejlede, bruger hash-binding: %s", result.stderr[-300:])
    except Exception as exc:
        log.warning("GPG signering utilgængelig, bruger hash-binding: %s", exc)
    return f"sha256:{digest}", "system-hash"


def _ticket_to_dict(ticket: ChangeTicket) -> dict:
    machine = {}
    if ticket.machine_json:
        try:
            machine = json.loads(ticket.machine_json)
        except Exception:
            machine = {}
    return {
        "id": ticket.id,
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "summary": ticket.summary,
        "pending_update_id": ticket.pending_update_id,
        "update_type": ticket.update_type,
        "severity": ticket.severity,
        "environment": ticket.environment,
        "scope": ticket.scope,
        "scope_id": ticket.scope_id,
        "status": ticket.status,
        "source_commit": ticket.source_commit,
        "source_ref": ticket.source_ref,
        "artifact_id": ticket.artifact_id,
        "sbom_ref": ticket.sbom_ref,
        "test_evidence_ref": ticket.test_evidence_ref,
        "rollback_plan": ticket.rollback_plan,
        "reboot_required": bool(ticket.reboot_required),
        "maintenance_window": ticket.maintenance_window,
        "human_readable_md": ticket.human_readable_md,
        "machine": machine,
        "content_sha256": ticket.content_sha256,
        "signature": ticket.signature,
        "signed_by": ticket.signed_by,
        "signed_at": ticket.signed_at.isoformat() if ticket.signed_at else None,
        "created_by": ticket.created_by,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


def _artifact_to_dict(artifact: UpdateArtifact) -> dict:
    manifest = {}
    if artifact.manifest_json:
        try:
            manifest = json.loads(artifact.manifest_json)
        except Exception:
            manifest = {}
    return {
        "id": artifact.id,
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "version": artifact.version,
        "source_commit": artifact.source_commit,
        "source_ref": artifact.source_ref,
        "filename": artifact.filename,
        "storage_path": artifact.storage_path,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "manifest": manifest,
        "sbom_ref": artifact.sbom_ref,
        "signature": artifact.signature,
        "signed_by": artifact.signed_by,
        "signed_at": artifact.signed_at.isoformat() if artifact.signed_at else None,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_env() -> dict:
    """Git-miljø der tillader root at læse repos ejet af anden bruger (samme fix som på edge)."""
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    return env


def _git_text(args: list[str]) -> str | None:
    try:
        result = _subprocess.run(
            ["git", *args],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=10,
            env=_git_env(),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as exc:
        log.warning("Kunne ikke læse git metadata: %s", exc)
    return None


def _release_worktree_dirty() -> bool:
    ignored = {"headend/.webui_secret_key"}
    status = _git_text(["status", "--porcelain"]) or ""
    for line in status.splitlines():
        path = line[3:].strip()
        if path and path not in ignored:
            return True
    return False


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_release_outputs(root: Path) -> list[dict]:
    candidates = [
        root / "headend" / "main.py",
        root / "headend" / "database.py",
        root / "edge" / "agent.py",
        root / "edge" / "security.py",
        root / "edge" / "requirements.txt",
        root / "edge" / "camera",
        root / "edge" / "capture",
        root / "edge" / "config",
        root / "edge" / "diagnostics",
        root / "edge" / "tunnel",
        root / "edge" / "upload",
        root / "edge" / "update",
        root / "timelapse-ui" / "dist",
    ]
    outputs: list[dict] = []

    def _include_release_file(file_path: Path) -> bool:
        rel = str(file_path.relative_to(root))
        if "__pycache__" in file_path.parts:
            return False
        if any(ord(ch) < 32 for ch in rel):
            return False
        if file_path.name in {".DS_Store", "Icon\r"}:
            return False
        return True

    for candidate in candidates:
        if candidate.is_file():
            if not _include_release_file(candidate):
                continue
            outputs.append({
                "path": str(candidate.relative_to(root)),
                "size_bytes": candidate.stat().st_size,
                "sha256": _file_sha256(candidate),
            })
        elif candidate.is_dir():
            for file_path in sorted(p for p in candidate.rglob("*") if p.is_file()):
                if not _include_release_file(file_path):
                    continue
                outputs.append({
                    "path": str(file_path.relative_to(root)),
                    "size_bytes": file_path.stat().st_size,
                    "sha256": _file_sha256(file_path),
                })
    return outputs


def _find_artifact_for_update(db: Session, update: PendingUpdate) -> UpdateArtifact | None:
    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).order_by(ChangeTicket.created_at.desc()).first()
    if ticket and ticket.artifact_id:
        artifact = db.query(UpdateArtifact).filter_by(artifact_id=ticket.artifact_id).first()
        if artifact:
            return artifact
    version = (update.version or "").strip()
    if not version:
        return None
    q = db.query(UpdateArtifact).order_by(UpdateArtifact.created_at.desc())
    artifact = q.filter(UpdateArtifact.source_commit == version).first()
    if artifact:
        return artifact
    return q.filter(UpdateArtifact.version == version).first()


def _artifact_for_edge_policy(db: Session, artifact: UpdateArtifact | None) -> dict | None:
    if not artifact:
        return None
    signer_fingerprint = None
    headend_fingerprint = None  # fallback: headend's own signing identity
    for signer in _trusted_release_signers(db):
        if artifact.signed_by and artifact.signed_by in {
            signer.get("credential_id"),
            signer.get("gpg_fingerprint"),
        }:
            signer_fingerprint = signer.get("fingerprint")
            break
        # Gem headend-identitet som fallback for system-hash signerede artifacts
        if signer.get("entity_id") == "headend" and not headend_fingerprint:
            headend_fingerprint = signer.get("fingerprint")
    # system-hash = headend har signeret via hash-binding (ingen GPG-nøgle sat).
    # Behandles som headend-signeret og får headend-identitetens fingerprint.
    if signer_fingerprint is None and artifact.signed_by == "system-hash" and headend_fingerprint:
        signer_fingerprint = headend_fingerprint
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "version": artifact.version,
        "source_commit": artifact.source_commit,
        "source_ref": artifact.source_ref,
        "sha256": artifact.sha256,
        "manifest": json.loads(artifact.manifest_json) if artifact.manifest_json else None,
        "signature": artifact.signature,
        "signed_by": artifact.signed_by,
        "signed_at": artifact.signed_at.isoformat() if artifact.signed_at else None,
        "signer_fingerprint": signer_fingerprint,
    }


def _default_update_policy() -> dict:
    return {
        "os_security": "auto",
        "os_updates": "manual",
        "application_security": "auto",
        "application_updates": "manual",
        "timelapse_security": "auto",
        "timelapse_updates": "manual",
        "maintenance_window": "02:00-04:00",
        "staging_required": False,
        "customer_acceptance_required": False,
    }


def _normalise_update_policy(raw_policy: dict | None) -> dict:
    policy = {}
    for key, value in (raw_policy or {}).items():
        target_key = LEGACY_POLICY_ALIASES.get(key, key)
        if target_key in _default_update_policy():
            policy[target_key] = value
    return policy


def _merge_update_policy(base: dict, override: dict | None) -> dict:
    merged = dict(base)
    for key, value in _normalise_update_policy(override).items():
        if key.endswith("_required"):
            merged[key] = bool(value)
            continue
        if key == "maintenance_window":
            merged[key] = value
            continue
        if key in merged:
            # Manual is the restrictive override. Auto can only win if no stricter
            # inherited value already exists.
            if value == "manual" or merged.get(key) == "auto":
                merged[key] = value
    return merged


def _resolved_update_policy(db: Session, device: Device | None) -> dict:
    policy = _default_update_policy()
    if not device:
        return policy
    try:
        defaults = db.query(ConfigDefaults).first()
        if defaults and getattr(defaults, "system", None):
            sys_cfg = _json.loads(defaults.system)
            policy = _merge_update_policy(policy, sys_cfg.get("update_policy"))

        site = db.query(Site).filter_by(id=device.site_id).first() if device.site_id else None
        customer = None
        if site and site.customer_id:
            customer = db.query(Customer).filter_by(id=site.customer_id).first()
        elif device.customer_id:
            customer = db.query(Customer).filter_by(id=device.customer_id).first()

        for obj in [customer, site, device]:
            if not obj:
                continue
            overrides_raw = getattr(obj, "config_overrides", None) or getattr(obj, "device_config", None)
            if not overrides_raw:
                continue
            try:
                overrides = _json.loads(overrides_raw) if isinstance(overrides_raw, str) else overrides_raw
                policy = _merge_update_policy(policy, overrides.get("update_policy") if isinstance(overrides, dict) else None)
            except Exception:
                continue
    except Exception as exc:
        log.warning("Update policy resolution fejl: %s", exc)
    return policy


def _policy_key_for_update(update_type: str | None) -> str:
    return UPDATE_TYPE_POLICY_KEY.get(update_type or "", update_type or "unknown")


def _update_requires_headend_artifact(update_type: str | None) -> bool:
    return (update_type or "") in {
        "app_security",
        "app_updates",
        "app_update",
        "timelapse_update",
        "timelapse_pro_update",
        "timelapse_security",
        "timelapse_pro_security",
        "application_security",
        "application_update",
        "application_updates",
        "dependency_security",
        "dependency_updates",
        "third_party_security",
        "third_party_updates",
        "os_security",
        "os_updates",
    }


def _default_os_bundle_commands() -> list[dict]:
    return [
        {
            "name": "offline dpkg install",
            "argv": [
                "/bin/bash",
                "-lc",
                "dpkg -i {bundle}/packages/*.deb || apt-get --no-download -f install -y",
            ],
            "timeout_s": 1800,
        },
        {
            "name": "post install package audit",
            "argv": ["/bin/bash", "{bundle}/verify-installed.sh"],
            "timeout_s": 300,
        },
    ]


def _validate_os_bundle_commands(commands: list[dict]) -> None:
    allowed_commands = {
        "/bin/bash",
        "/usr/bin/bash",
        "/usr/bin/dpkg",
        "/usr/bin/apt-get",
        "/bin/dpkg",
    }
    for command in commands:
        if not isinstance(command, dict) or not isinstance(command.get("argv"), list) or not command.get("argv"):
            raise HTTPException(status_code=400, detail="commands skal indeholde argv-lister")
        argv = [str(arg) for arg in command["argv"]]
        executable = argv[0]
        if executable not in allowed_commands:
            raise HTTPException(status_code=400, detail=f"OS command er ikke allowlisted: {executable}")
        joined = " ".join(argv)
        if "apt-get" in joined:
            forbidden = {"upgrade", "dist-upgrade", "full-upgrade", "update"}
            if any(_re.search(rf"\b{_re.escape(token)}\b", joined) for token in forbidden) or "--no-download" not in joined:
                raise HTTPException(
                    status_code=400,
                    detail="apt-get i OS bundle må kun bruges offline med --no-download, ikke update/upgrade",
                )
        if "{bundle}" not in joined:
            raise HTTPException(status_code=400, detail="OS commands skal bruge {bundle} placeholder")


def _validate_os_bundle_file_policy(storage_path: Path, outputs: list[dict]) -> None:
    forbidden_patterns = [
        r"\bapt(-get)?\s+update\b",
        r"\bapt(-get)?\s+(dist-upgrade|full-upgrade|upgrade)\b",
        r"(^|[;&|]\s*)(curl|wget)\b",
        r"(^|[;&|]\s*)git\s+(clone|pull|fetch)\b",
        r"(^|[;&|]\s*)scp\b",
        r"(^|[;&|]\s*)rsync\b",
        r"(^|[;&|]\s*)python3?\s+-m\s+pip\b",
        r"(^|[;&|]\s*)pip3?\s+install\b",
    ]
    for item in outputs:
        rel = str(item.get("path") or "")
        if not rel.endswith((".sh", ".bash", ".conf", ".txt")):
            continue
        path = (storage_path / rel).resolve()
        try:
            text_content = path.read_text(errors="ignore")
        except Exception:
            continue
        for pattern in forbidden_patterns:
            if _re.search(pattern, text_content):
                raise HTTPException(
                    status_code=400,
                    detail=f"OS bundle script/config indeholder forbudt online update-kommando: {rel}",
                )
        for line in text_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "apt-get" in stripped or " apt " in stripped:
                if "--no-download" not in stripped:
                    raise HTTPException(
                        status_code=400,
                        detail=f"OS bundle apt-brug mangler --no-download: {rel}",
                    )


def _assert_update_has_required_artifact(db: Session, update: PendingUpdate) -> UpdateArtifact:
    artifact = _find_artifact_for_update(db, update)
    if (
        update.update_type in {"application_security", "application_update", "application_updates"}
        and update.scope == "device"
        and update.scope_id == "TL-MACMINI-HEADEND-TEST-1"
        and _parse_brew_formula_from_update(update)
    ):
        return artifact
    if _update_requires_headend_artifact(update.update_type) and not artifact:
        raise HTTPException(
            status_code=409,
            detail=(
                "Opdateringen mangler Headend-signeret artifact. "
                "Edge må ikke installere via direkte internet/GitHub/apt."
            ),
        )
    return artifact


def _auto_approve_update_for_target(
    db: Session,
    update: PendingUpdate,
    device: Device,
    requested_by: str = "system:auto-policy",
) -> tuple[bool, str]:
    policy = _resolved_update_policy(db, device)
    policy_key = _policy_key_for_update(update.update_type)
    if policy.get(policy_key) != "auto":
        return False, f"policy_{policy_key}_manual"
    if policy.get("customer_acceptance_required"):
        return False, "customer_acceptance_required"
    if update.environment == "production" and policy.get("staging_required"):
        staged = db.query(PendingUpdate).filter(
            PendingUpdate.update_type == update.update_type,
            PendingUpdate.version == update.version,
            PendingUpdate.environment == "staging",
            PendingUpdate.status == "deployed",
        ).first()
        if not staged:
            return False, "staging_required"
    artifact = _find_artifact_for_update(db, update)
    if _update_requires_headend_artifact(update.update_type) and not artifact:
        return False, "missing_signed_artifact"
    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).order_by(ChangeTicket.created_at.desc()).first()
    if not ticket:
        ticket = _build_change_ticket(
            update,
            ChangeTicketPayload(
                title=f"Auto policy approval: {update.update_type} {update.version}",
                summary=update.description or "Auto-approved according to resolved update policy.",
                status="approved",
            ),
            User(username=requested_by, role="system", password_hash=""),
            artifact,
        )
        db.add(ticket)
        db.flush()
    ticket.status = "approved"
    ticket.updated_at = now_utc()
    update.status = "approved"
    update.approved_at = now_utc()
    update.approved_by = requested_by
    update.scope = update.scope or "device"
    update.scope_id = update.scope_id or device.device_id
    if not update.target_device_ids and update.scope == "device":
        update.target_device_ids = json.dumps([device.device_id])
    _ensure_update_targets(db, update, ticket)
    return True, "approved"


@app.post("/api/updates/auto-deploy/evaluate")
def evaluate_auto_deploy_updates(
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Evaluer pending updates mod resolved customer/site/device update policy."""
    updates = db.query(PendingUpdate).filter(PendingUpdate.status == "pending").order_by(PendingUpdate.created_at).all()
    decisions = []
    for update in updates:
        devices = _resolve_update_targets(db, update)
        if not devices and update.scope == "device" and update.scope_id:
            device = db.query(Device).filter_by(device_id=update.scope_id).first()
            if device:
                devices = [device]
        if not devices:
            decisions.append({"update_id": update.id, "decision": "skipped", "reason": "no_targets"})
            continue
        approved_any = False
        reasons = []
        for device in devices:
            approved, reason = _auto_approve_update_for_target(db, update, device)
            approved_any = approved_any or approved
            reasons.append({"device_id": device.device_id, "approved": approved, "reason": reason})
        decisions.append({
            "update_id": update.id,
            "update_type": update.update_type,
            "version": update.version,
            "decision": "approved" if approved_any else "skipped",
            "targets": reasons,
        })
    db.commit()
    return {"ok": True, "evaluated": len(updates), "decisions": decisions}


_APT_UPGRADABLE_RE = _re.compile(
    r"^(?P<name>[^/]+)/(?P<repos>\S+)\s+"
    r"(?P<available>\S+)\s+"
    r"(?P<arch>\S+)\s+"
    r"\[upgradable from:\s+(?P<installed>[^\]]+)\]"
)


def _parse_lab_apt_catalog(text_value: str) -> list[dict]:
    packages = []
    seen = set()
    for raw_line in (text_value or "").splitlines():
        line = raw_line.strip()
        match = _APT_UPGRADABLE_RE.match(line)
        if not match:
            continue
        repos = match.group("repos")
        category = "os_security" if "security" in repos else "os_updates"
        key = (match.group("name"), match.group("available"), match.group("arch"))
        if key in seen:
            continue
        seen.add(key)
        packages.append({
            "name": match.group("name"),
            "installed_version": match.group("installed"),
            "available_version": match.group("available"),
            "architecture": match.group("arch"),
            "category": category,
            "severity": "high" if category == "os_security" else "low",
            "source_repo": repos,
        })
    packages.sort(key=lambda p: (p["category"], p["name"]))
    return packages


def _reconcile_os_catalog(installed: dict, catalog_packages: list[dict]) -> dict:
    grouped = _defaultdict(list)
    for package in catalog_packages:
        name = package.get("name")
        available = package.get("available_version")
        if not name or not available:
            continue
        installed_version = installed.get(name) or package.get("installed_version")
        if not installed_version or installed_version == available:
            continue
        category = package.get("category") or "os_updates"
        if category not in {"os_security", "os_updates"}:
            continue
        grouped[category].append({
            "name": name,
            "installed_version": installed_version,
            "available_version": available,
            "architecture": package.get("architecture"),
            "severity": package.get("severity") or ("high" if category == "os_security" else "low"),
            "source_repo": package.get("source_repo"),
            "category": category,
        })

    decisions = {}
    for category, packages in grouped.items():
        severities = {p["severity"] for p in packages}
        severity = "high" if "high" in severities else "medium" if "medium" in severities else "low"
        decisions[category] = {
            "package_count": len(packages),
            "severity": severity,
            "packages": packages,
            "package_preview": packages[:50],
            "truncated": max(0, len(packages) - 50),
        }
    return decisions


def _os_bundle_requests(device_id: str, environment: str, decisions: dict, catalog: dict) -> list[dict]:
    generated_at = now_utc().isoformat()
    requests = []
    for category, decision in decisions.items():
        packages = decision.get("packages") or []
        if not packages:
            continue
        requests.append({
            "schema": "dk.froekjaer.timelapse.os_bundle_request.v1",
            "source": "headend-cmdb-reconcile",
            "generated_at": generated_at,
            "device_id": device_id,
            "environment": environment,
            "category": category,
            "catalog_source": catalog.get("source"),
            "package_count": decision.get("package_count"),
            "severity": decision.get("severity"),
            "packages": packages,
            "edge_requires_direct_internet": False,
            "edge_may_run_apt_get_upgrade": False,
        })
    return requests


def _write_update_json(folder: str, filename: str, payload: dict) -> str:
    root = Path(os.getenv("TIMELAPSE_UPDATE_STORE", "/var/lib/timelapse")).expanduser()
    path = root / folder / filename
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return str(path)
    except PermissionError:
        fallback = Path("/tmp/timelapse-update-store") / folder / filename
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return str(fallback)


def _plan_path_for_update(update: PendingUpdate) -> str | None:
    match = _re.search(r"^Plan:\s*(\S+)", update.description or "", _re.MULTILINE)
    return match.group(1) if match else None


def _os_bundle_store_root() -> Path:
    configured = os.getenv("TIMELAPSE_OS_BUNDLE_STORE")
    if configured:
        return Path(configured).expanduser()
    return Path("/Users/Shared/TimeLapsePro/os-bundles") if sys.platform == "darwin" else Path("/var/lib/timelapse/os-bundles")


def _docker_available() -> tuple[bool, str | None]:
    docker = _shutil.which("docker") if "_shutil" in globals() else None
    if not docker:
        return False, "Docker/Colima er ikke installeret på Headend"
    try:
        result = _subprocess.run([docker, "version", "--format", "{{.Server.Version}}"], text=True, capture_output=True, timeout=10)
    except Exception as exc:
        return False, f"Docker runtime kunne ikke kontaktes: {exc}"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "Docker daemon svarer ikke").strip()
    return True, None


def _build_os_bundle_in_mac_container(
    *,
    plan_path: Path,
    output_path: Path,
    device_id: str,
    architecture: str,
    source_ref: str,
    image: str,
    category: str | None = None,
) -> dict:
    docker = _shutil.which("docker") if "_shutil" in globals() else None
    if not docker:
        raise HTTPException(status_code=409, detail="Docker/Colima er ikke installeret på Headend")
    build_root = output_path.parent
    build_root.mkdir(parents=True, exist_ok=True)
    os.chmod(build_root, 0o777)
    plan_copy = build_root / f"{output_path.name}.plan.json"
    plan_copy.write_text(plan_path.read_text())
    repo = _repo_root()
    container_output = f"/out/{output_path.name}"
    cmd = [
        docker,
        "run",
        "--rm",
        "--platform",
        "linux/arm64",
        "-e",
        "DEBIAN_FRONTEND=noninteractive",
        "-e",
        "TZ=UTC",
        "-v",
        f"{repo}:/repo:ro",
        "-v",
        f"{build_root}:/out",
        image,
        "bash",
        "-lc",
        (
            "set -euo pipefail; "
            "apt-get update; "
            "apt-get install -y --no-install-recommends python3 ca-certificates; "
            f"python3 /repo/headend/tools/build_os_bundle.py --device-id {device_id!r} "
            f"--catalog /out/{plan_copy.name!r} --output {container_output!r} "
            f"--architecture {architecture!r} --source-ref {source_ref!r} "
            f"{('--category ' + category) if category else ''} "
            "--include-dependencies --force"
        ),
    ]
    result = _subprocess.run(cmd, text=True, capture_output=True, timeout=3600)
    if result.returncode != 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "os_bundle_container_build_failed",
                "message": "Linux-containeren kunne ikke bygge OS-bundlet",
                "stdout_tail": (result.stdout or "")[-3000:],
                "stderr_tail": (result.stderr or "")[-3000:],
            },
        )
    return {
        "builder": "mac_docker_linux_arm64",
        "image": image,
        "stdout_tail": (result.stdout or "")[-3000:],
        "stderr_tail": (result.stderr or "")[-3000:],
    }


_update_job_lock = _threading.Lock()
_update_jobs: dict[str, dict] = {}


def _update_job_to_dict(record: UpdateJobRecord) -> dict:
    def parse_json(value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except Exception:
            return default

    return {
        "job_id": record.job_id,
        "kind": record.kind,
        "title": record.title,
        "running": bool(record.running),
        "status": record.status,
        "phase": record.phase,
        "progress": record.progress or 0,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "requested_by": record.requested_by,
        "message": record.message,
        "payload": parse_json(record.payload_json, {}),
        "result": parse_json(record.result_json, None),
        "error": record.error,
        "stdout_tail": record.stdout_tail or "",
        "stderr_tail": record.stderr_tail or "",
    }


def _json_or_none(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _new_update_job(kind: str, requested_by: str, title: str, payload: dict | None = None) -> str:
    job_id = f"TL-JOB-{now_utc():%Y%m%d%H%M%S}-{_secrets.token_hex(4)}"
    db = SessionLocal()
    try:
        record = UpdateJobRecord(
            job_id=job_id,
            kind=kind,
            title=title,
            running=True,
            status="running",
            phase="queued",
            progress=0,
            started_at=now_utc(),
            requested_by=requested_by,
            message="Job sat i kø",
            payload_json=_json_or_none(payload or {}),
            stdout_tail="",
            stderr_tail="",
            updated_at=now_utc(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        with _update_job_lock:
            _update_jobs[job_id] = _update_job_to_dict(record)
    finally:
        db.close()
    return job_id


def _update_job(job_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        record = db.query(UpdateJobRecord).filter_by(job_id=job_id).first()
        if not record:
            record = UpdateJobRecord(job_id=job_id, kind=str(fields.get("kind") or "unknown"))
            db.add(record)
        scalar_fields = {
            "kind", "title", "running", "status", "phase", "progress", "requested_by",
            "message", "error", "stdout_tail", "stderr_tail",
        }
        for key, value in fields.items():
            if key in scalar_fields:
                setattr(record, key, value)
            elif key == "payload":
                record.payload_json = _json_or_none(value)
            elif key == "result":
                record.result_json = _json_or_none(value)
            elif key == "started_at":
                record.started_at = ensure_utc(datetime.fromisoformat(value)) if isinstance(value, str) else value
            elif key == "finished_at":
                record.finished_at = ensure_utc(datetime.fromisoformat(value)) if isinstance(value, str) else value
        record.updated_at = now_utc()
        db.commit()
        db.refresh(record)
        with _update_job_lock:
            _update_jobs[job_id] = _update_job_to_dict(record)
    finally:
        db.close()


def _update_job_snapshot(job_id: str) -> dict:
    db = SessionLocal()
    try:
        record = db.query(UpdateJobRecord).filter_by(job_id=job_id).first()
        if record:
            snapshot = _update_job_to_dict(record)
            with _update_job_lock:
                _update_jobs[job_id] = snapshot
            return snapshot
    finally:
        db.close()
    with _update_job_lock:
        job = _update_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Update job ikke fundet")
        return dict(job)


def _human_update_job_error(detail) -> tuple[str, str, str]:
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("code") or "Update job fejlede")
        stderr_tail = str(detail.get("stderr_tail") or "")
        stdout_tail = str(detail.get("stdout_tail") or "")
        if stderr_tail:
            last_line = next((line.strip() for line in reversed(stderr_tail.splitlines()) if line.strip()), "")
            if last_line:
                message = f"{message}: {last_line}"
        return message[:1200], stdout_tail[-3000:], stderr_tail[-3000:]
    return str(detail)[:1200], "", ""


def _run_refresh_catalog_job(job_id: str, payload_data: dict, username: str) -> None:
    db = SessionLocal()
    try:
        _update_job(job_id, phase="cmdb_inventory", progress=5, message="Læser CMDB package inventory")
        user = db.query(User).filter_by(username=username).first()
        if not user:
            raise RuntimeError("Bruger findes ikke længere")
        payload = OsCatalogBuilderPayload(**payload_data)
        device_id = (payload.device_id or "").strip()
        inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
        if not inv:
            raise RuntimeError("CMDB inventory ikke fundet for device_id")
        try:
            installed = json.loads(inv.os_packages or "{}")
        except Exception:
            installed = {}
        if not isinstance(installed, dict) or not installed:
            raise RuntimeError("CMDB mangler OS package inventory for device")
        _update_job(job_id, phase="docker_catalog", progress=20, message=f"Scanner {len(installed)} CMDB-pakker via Mac Docker-builder")
        generated = _generate_os_update_catalog_candidates(
            installed=installed,
            device_id=device_id,
            architecture=payload.architecture or "arm64",
            image=payload.image or "ubuntu:24.04",
        )
        _update_job(job_id, phase="reconcile", progress=80, message=f"Reconciler {generated['upgradable_lines']} kandidater mod CMDB")
        result = import_os_catalog_from_lab_apt_list(
            OsCatalogImportPayload(
                device_id=device_id,
                apt_list_text=generated["apt_list_text"],
                source=payload.source or f"mac-docker-builder:{payload.image or 'ubuntu:24.04'}:{device_id}",
                environment=payload.environment or "lab",
                create_updates=payload.create_updates,
            ),
            user,
            db,
        )
        result["builder"] = {
            "builder": generated["builder"],
            "image": generated.get("image"),
            "input_packages": generated["input_packages"],
            "upgradable_lines": generated["upgradable_lines"],
            "apt_list_output_path": generated["output_path"],
            "fallback_from": generated.get("fallback_from"),
            "fallback_reason": generated.get("fallback_reason"),
        }
        _update_job(
            job_id,
            running=False,
            status="done",
            phase="complete",
            progress=100,
            finished_at=now_utc().isoformat(),
            message="OS-katalog opdateret fra CMDB/Mac-builder",
            result=result,
        )
    except HTTPException as exc:
        message, stdout_tail, stderr_tail = _human_update_job_error(exc.detail)
        _update_job(
            job_id,
            running=False,
            status="failed",
            phase="failed",
            finished_at=now_utc().isoformat(),
            message=message,
            error=message,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
    except Exception as exc:
        _update_job(
            job_id,
            running=False,
            status="failed",
            phase="failed",
            finished_at=now_utc().isoformat(),
            message=str(exc),
            error=str(exc),
        )
    finally:
        db.close()


def _run_os_bundle_build_bind_job(job_id: str, update_id: int, payload_data: dict, username: str) -> None:
    db = SessionLocal()
    try:
        _update_job(job_id, phase="plan", progress=5, message="Læser OS update-plan")
        user = db.query(User).filter_by(username=username).first()
        if not user:
            raise RuntimeError("Bruger findes ikke længere")
        update = db.query(PendingUpdate).filter_by(id=update_id).first()
        if not update:
            raise RuntimeError("Opdatering ikke fundet")
        if update.update_type not in {"os_security", "os_updates"}:
            raise RuntimeError("Kun OS updates kan få bygget OS bundle")
        device_id = (update.scope_id or payload_data.get("device_id") or "").strip()
        plan_path_raw = str(payload_data.get("plan_path") or _plan_path_for_update(update) or "").strip()
        if not plan_path_raw:
            raise RuntimeError("Update mangler OS plan. Importér eller refresh OS-katalog fra UI først.")
        plan_path = Path(plan_path_raw).expanduser().resolve()
        if not plan_path.is_file():
            raise RuntimeError(f"OS plan findes ikke på Headend: {plan_path}")
        docker_ok, docker_error = _docker_available()
        if not docker_ok:
            raise RuntimeError(f"Docker/Colima er ikke klar: {docker_error}")
        created_at = now_utc()
        safe_type = _re.sub(r"[^a-zA-Z0-9_.-]+", "-", update.update_type)
        output_root = _os_bundle_store_root().expanduser().resolve()
        output_path = output_root / f"update-{update.id}-{safe_type}-{created_at:%Y%m%d-%H%M%S}"
        architecture = str(payload_data.get("architecture") or "arm64")
        source_ref = str(payload_data.get("source_ref") or f"headend-mac-container:{created_at:%Y%m%dT%H%M%SZ}")
        image = str(payload_data.get("image") or "ubuntu:24.04")
        _update_job(job_id, phase="docker_build", progress=20, message="Bygger offline OS bundle i Linux/arm64 Docker-container")
        build = _build_os_bundle_in_mac_container(
            plan_path=plan_path,
            output_path=output_path,
            device_id=device_id,
            architecture=architecture,
            source_ref=source_ref,
            image=image,
            category=update.update_type,
        )
        _update_job(job_id, phase="catalog_artifact", progress=75, message="Registrerer og signerer OS artifact")
        artifact = catalog_os_update_artifact(
            {
                "storage_path": str(output_path),
                "version": f"{device_id}-{update.update_type}-{created_at:%Y%m%d-%H%M%S}",
                "architecture": architecture,
                "target_os": payload_data.get("target_os") or "ubuntu-24.04/orangepi",
                "source_ref": source_ref,
                "lab_evidence": {
                    "builder": build.get("builder"),
                    "image": build.get("image"),
                    "plan_path": str(plan_path),
                    "triggered_from": "headend_ui_job",
                },
            },
            user,
            db,
        )
        _update_job(job_id, phase="bind_artifact", progress=90, message=f"Binder {artifact['artifact_id']} til update #{update_id}")
        bind = bind_artifact_to_update(
            update_id,
            {
                "artifact_id": artifact["artifact_id"],
                "summary": "OS bundle bygget via Headend UI job og Mac container builder.",
                "test_evidence_ref": source_ref,
            },
            user,
            db,
        )
        _update_job(
            job_id,
            running=False,
            status="done",
            phase="complete",
            progress=100,
            finished_at=now_utc().isoformat(),
            message=f"OS artifact bygget og bundet: {artifact['artifact_id']}",
            result={"update_id": update_id, "bundle_path": str(output_path), "artifact": artifact, "bind": bind, "build": build},
        )
    except HTTPException as exc:
        message, stdout_tail, stderr_tail = _human_update_job_error(exc.detail)
        _update_job(
            job_id,
            running=False,
            status="failed",
            phase="failed",
            finished_at=now_utc().isoformat(),
            message=message,
            error=message,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
    except Exception as exc:
        _update_job(job_id, running=False, status="failed", phase="failed", finished_at=now_utc().isoformat(), message=str(exc), error=str(exc))
    finally:
        db.close()


def _generate_apt_list_from_mac_builder(
    *,
    installed: dict,
    device_id: str,
    architecture: str,
    image: str,
) -> dict:
    docker = _shutil.which("docker") if "_shutil" in globals() else None
    if not docker:
        raise HTTPException(status_code=409, detail="Docker/Colima er ikke installeret på Headend")
    docker_ok, docker_error = _docker_available()
    if not docker_ok:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "builder_runtime_missing",
                "message": "Headend er Mac og skal bruge Docker/Colima for at generere Linux/arm64 OS-katalog fra CMDB.",
                "runtime": "docker/colima",
                "reason": docker_error,
            },
        )
    build_root = (_os_bundle_store_root().expanduser().resolve() / "_catalog-builder")
    build_root.mkdir(parents=True, exist_ok=True)
    os.chmod(build_root, 0o777)
    safe_device = _re.sub(r"[^A-Za-z0-9_.-]+", "-", device_id)
    input_path = build_root / f"{safe_device}.installed.tsv"
    output_path = build_root / f"{safe_device}.apt-list.txt"
    lines = []
    for name, version in sorted(installed.items()):
        name_s = str(name).strip()
        version_s = str(version).strip()
        if not name_s or not version_s or "\t" in name_s or "\n" in name_s or "\n" in version_s:
            continue
        lines.append(f"{name_s}\t{version_s}")
    input_path.write_text("\n".join(lines) + "\n")
    output_path.write_text("")
    os.chmod(input_path, 0o666)
    os.chmod(output_path, 0o666)
    shell = (
        "set -euo pipefail; "
        "apt-get update >/dev/null; "
        "while IFS=$'\\t' read -r name installed; do "
        "[ -n \"$name\" ] || continue; "
        "candidate=$(apt-cache policy \"$name\" | awk '/Candidate:/ {print $2; exit}'); "
        "[ -n \"$candidate\" ] && [ \"$candidate\" != '(none)' ] || continue; "
        "if dpkg --compare-versions \"$candidate\" gt \"$installed\"; then "
        "repos=$(apt-cache policy \"$name\" | awk -v cand=\"$candidate\" '$1 == cand {getline; print $3; exit}'); "
        "[ -n \"$repos\" ] || repos=ubuntu-builder; "
        "case \"$repos\" in *security*) repo_label=noble-security ;; *updates*) repo_label=noble-updates ;; *) repo_label=\"$repos\" ;; esac; "
        f"printf '%s/%s %s {architecture} [upgradable from: %s]\\n' \"$name\" \"$repo_label\" \"$candidate\" \"$installed\"; "
        "fi; "
        "done < /out/" + input_path.name + " > /out/" + output_path.name
    )
    result = _subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "--platform",
            "linux/arm64",
            "-e",
            "DEBIAN_FRONTEND=noninteractive",
            "-v",
            f"{build_root}:/out",
            image,
            "bash",
            "-lc",
            shell,
        ],
        text=True,
        capture_output=True,
        timeout=3600,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "os_catalog_builder_failed",
                "message": "Linux-containeren kunne ikke generere OS-katalog fra CMDB",
                "stdout_tail": (result.stdout or "")[-3000:],
                "stderr_tail": (result.stderr or "")[-3000:],
            },
        )
    apt_text = output_path.read_text()
    return {
        "apt_list_text": apt_text,
        "input_packages": len(lines),
        "upgradable_lines": len([line for line in apt_text.splitlines() if line.strip()]),
        "builder": "mac_docker_linux_arm64",
        "image": image,
        "output_path": str(output_path),
    }


def _debian_version_order(ch: str) -> int:
    if not ch:
        return 0
    if ch == "~":
        return -1
    if ch.isalpha():
        return ord(ch)
    return ord(ch) + 256


def _debian_split_epoch(version: str) -> tuple[int, str]:
    if ":" not in version:
        return 0, version
    epoch, rest = version.split(":", 1)
    try:
        return int(epoch), rest
    except ValueError:
        return 0, version


def _debian_split_revision(version: str) -> tuple[str, str]:
    if "-" not in version:
        return version, ""
    upstream, revision = version.rsplit("-", 1)
    return upstream, revision


def _debian_compare_part(left: str, right: str) -> int:
    li = ri = 0
    while li < len(left) or ri < len(right):
        while (li < len(left) and not left[li].isdigit()) or (ri < len(right) and not right[ri].isdigit()):
            lc = left[li] if li < len(left) and not left[li].isdigit() else ""
            rc = right[ri] if ri < len(right) and not right[ri].isdigit() else ""
            lo = _debian_version_order(lc)
            ro = _debian_version_order(rc)
            if lo != ro:
                return -1 if lo < ro else 1
            if lc:
                li += 1
            if rc:
                ri += 1
        lstart = li
        while li < len(left) and left[li].isdigit():
            li += 1
        rstart = ri
        while ri < len(right) and right[ri].isdigit():
            ri += 1
        lnum = left[lstart:li].lstrip("0")
        rnum = right[rstart:ri].lstrip("0")
        if len(lnum) != len(rnum):
            return -1 if len(lnum) < len(rnum) else 1
        if lnum != rnum:
            return -1 if lnum < rnum else 1
    return 0


def _debian_compare_versions(left: str, right: str) -> int:
    left_epoch, left_rest = _debian_split_epoch(str(left or "0"))
    right_epoch, right_rest = _debian_split_epoch(str(right or "0"))
    if left_epoch != right_epoch:
        return -1 if left_epoch < right_epoch else 1
    left_upstream, left_revision = _debian_split_revision(left_rest)
    right_upstream, right_revision = _debian_split_revision(right_rest)
    upstream_cmp = _debian_compare_part(left_upstream, right_upstream)
    if upstream_cmp:
        return upstream_cmp
    return _debian_compare_part(left_revision, right_revision)


def _parse_debian_packages_index(text_value: str, *, suite: str, component: str, architecture: str, base_url: str) -> list[dict]:
    packages = []
    current: dict[str, str] = {}
    last_key = None
    for raw_line in (text_value or "").splitlines() + [""]:
        if not raw_line.strip():
            if current.get("Package") and current.get("Version"):
                packages.append({
                    "name": current.get("Package"),
                    "available_version": current.get("Version"),
                    "architecture": current.get("Architecture") or architecture,
                    "category": "os_security" if "security" in suite else "os_updates",
                    "severity": "high" if "security" in suite else "low",
                    "source_repo": f"{suite}/{component}",
                    "filename": current.get("Filename"),
                    "sha256": current.get("SHA256"),
                    "size": current.get("Size"),
                    "url": f"{base_url.rstrip('/')}/{current.get('Filename')}" if current.get("Filename") else None,
                })
            current = {}
            last_key = None
            continue
        if raw_line.startswith((" ", "\t")) and last_key:
            current[last_key] = current.get(last_key, "") + "\n" + raw_line.strip()
            continue
        key, sep, value = raw_line.partition(":")
        if sep:
            current[key] = value.strip()
            last_key = key
    return packages


def _fetch_ubuntu_packages_index(base_url: str, suite: str, component: str, architecture: str) -> str:
    rel = f"dists/{suite}/{component}/binary-{architecture}/Packages"
    errors = []
    for suffix, decoder in [
        (".xz", lambda data: _lzma.decompress(data).decode("utf-8", errors="replace")),
        (".gz", lambda data: _gzip.decompress(data).decode("utf-8", errors="replace")),
        ("", lambda data: data.decode("utf-8", errors="replace")),
    ]:
        url = f"{base_url.rstrip('/')}/{rel}{suffix}"
        try:
            with _urlrequest.urlopen(url, timeout=45) as response:
                return decoder(response.read())
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise HTTPException(
        status_code=409,
        detail={
            "code": "ubuntu_package_index_fetch_failed",
            "message": f"Kunne ikke hente Ubuntu package metadata for {suite}/{component}/{architecture}",
            "errors": errors[-3:],
        },
    )


def _generate_apt_list_from_ubuntu_metadata(
    *,
    installed: dict,
    device_id: str,
    architecture: str,
    suite: str = "noble",
    base_url: str | None = None,
    components: list[str] | None = None,
) -> dict:
    repo_base = base_url or os.getenv("TIMELAPSE_UBUNTU_PORTS_BASE_URL", "http://ports.ubuntu.com/ubuntu-ports")
    component_list = components or [
        item.strip()
        for item in os.getenv("TIMELAPSE_UBUNTU_COMPONENTS", "main,universe,restricted,multiverse").split(",")
        if item.strip()
    ]
    suites = [
        item.strip()
        for item in os.getenv("TIMELAPSE_UBUNTU_SUITES", f"{suite},{suite}-updates,{suite}-security").split(",")
        if item.strip()
    ]
    candidates: dict[str, dict] = {}
    indexes = 0
    for suite_name in suites:
        for component in component_list:
            index_text = _fetch_ubuntu_packages_index(repo_base, suite_name, component, architecture)
            indexes += 1
            for package in _parse_debian_packages_index(
                index_text,
                suite=suite_name,
                component=component,
                architecture=architecture,
                base_url=repo_base,
            ):
                name = package.get("name")
                version = package.get("available_version")
                if not name or not version or name not in installed:
                    continue
                current = candidates.get(name)
                if not current or _debian_compare_versions(version, current["available_version"]) > 0:
                    candidates[name] = package
                elif current and version == current["available_version"] and package.get("category") == "os_security":
                    candidates[name] = package

    lines = []
    for name, package in sorted(candidates.items()):
        installed_version = str(installed.get(name) or "").strip()
        available_version = str(package.get("available_version") or "").strip()
        if not installed_version or not available_version:
            continue
        if _debian_compare_versions(available_version, installed_version) <= 0:
            continue
        source_repo = package.get("source_repo") or "ubuntu-metadata"
        lines.append(
            f"{name}/{source_repo} {available_version} {package.get('architecture') or architecture} "
            f"[upgradable from: {installed_version}]"
        )

    build_root = (_os_bundle_store_root().expanduser().resolve() / "_catalog-builder")
    build_root.mkdir(parents=True, exist_ok=True)
    safe_device = _re.sub(r"[^A-Za-z0-9_.-]+", "-", device_id)
    output_path = build_root / f"{safe_device}.ubuntu-metadata.apt-list.txt"
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return {
        "apt_list_text": output_path.read_text(),
        "input_packages": len(installed),
        "upgradable_lines": len(lines),
        "builder": "headend_ubuntu_ports_metadata",
        "image": None,
        "output_path": str(output_path),
        "repo_base": repo_base,
        "suites": suites,
        "components": component_list,
        "indexes": indexes,
    }


def _generate_os_update_catalog_candidates(
    *,
    installed: dict,
    device_id: str,
    architecture: str,
    image: str,
) -> dict:
    try:
        return _generate_apt_list_from_mac_builder(
            installed=installed,
            device_id=device_id,
            architecture=architecture,
            image=image,
        )
    except HTTPException as exc:
        log.warning("Mac Docker OS-katalog builder fejlede; bruger Ubuntu metadata fallback: %s", exc.detail)
        generated = _generate_apt_list_from_ubuntu_metadata(
            installed=installed,
            device_id=device_id,
            architecture=architecture,
        )
        generated["fallback_from"] = "mac_docker_linux_arm64"
        generated["fallback_reason"] = exc.detail
        return generated


def _upsert_blocked_os_updates_from_plan(
    db: Session,
    device_id: str,
    environment: str,
    decisions: dict,
    catalog_source: str | None,
    plan_path: str,
) -> list[dict]:
    changes = []
    for update_type, decision in decisions.items():
        if update_type not in {"os_security", "os_updates"}:
            continue
        count = int(decision.get("package_count") or 0)
        if count <= 0:
            continue
        severity = decision.get("severity") or ("high" if update_type == "os_security" else "low")
        label = "sikkerhedsopdatering(er)" if update_type == "os_security" else "funktionelle OS-opdatering(er)"
        version = f"{count} pakker"
        existing = (
            db.query(PendingUpdate)
            .filter(
                PendingUpdate.update_type == update_type,
                PendingUpdate.scope == "device",
                PendingUpdate.scope_id == device_id,
                PendingUpdate.status.in_(["pending", "approved", "blocked"]),
            )
            .order_by(PendingUpdate.created_at.desc())
            .first()
        )
        description = (
            f"{count} {label} klar via Headend lab-katalog ({catalog_source or 'unknown source'}).\n"
            f"Plan: {plan_path}\n"
            "Blocked: afventer lab-bygget, testet og Headend-signeret offline OS artifact. "
            "Edge må ikke bruge direkte apt/internet."
        )
        if existing:
            existing.version = version
            existing.description = description
            existing.severity = severity
            existing.environment = environment
            if existing.status != "approved":
                existing.status = "blocked"
            changes.append({"update_type": update_type, "status": "updated", "id": existing.id})
            continue
        update = PendingUpdate(
            update_type=update_type,
            version=version,
            description=description,
            severity=severity,
            scope="device",
            scope_id=device_id,
            status="blocked",
            environment=environment,
        )
        db.add(update)
        db.flush()
        changes.append({"update_type": update_type, "status": "created", "id": update.id})
    return changes


@app.post("/api/updates/os-catalog/import-apt-list")
def import_os_catalog_from_lab_apt_list(
    payload: OsCatalogImportPayload,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Importer lab/mirror apt output, reconcile mod CMDB og opret blokerede OS update-poster."""
    device_id = (payload.device_id or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id er påkrævet")
    environment = (payload.environment or "lab").strip().lower()
    if environment not in {"lab", "staging", "production"}:
        raise HTTPException(status_code=400, detail="environment skal være lab, staging eller production")
    packages = _parse_lab_apt_catalog(payload.apt_list_text)
    if not packages:
        raise HTTPException(status_code=400, detail="Ingen apt upgradable-linjer fundet i input")
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="CMDB inventory ikke fundet for device_id")
    try:
        installed = json.loads(inv.os_packages or "{}")
    except Exception:
        installed = {}
    if not isinstance(installed, dict):
        installed = {}

    created_at = now_utc()
    catalog = {
        "schema": "dk.froekjaer.timelapse.os_update_catalog.v1",
        "source": payload.source or f"lab-import:apt-list:{device_id}:{created_at:%Y%m%dT%H%M%SZ}",
        "generated_at": created_at.isoformat(),
        "imported_by": current_user.username,
        "device_id": device_id,
        "edge_requires_direct_internet": False,
        "edge_may_run_apt_get_upgrade": False,
        "packages": packages,
        "summary": {
            "total": len(packages),
            "os_security": sum(1 for p in packages if p["category"] == "os_security"),
            "os_updates": sum(1 for p in packages if p["category"] == "os_updates"),
        },
    }
    decisions = _reconcile_os_catalog(installed, packages)
    plan = {
        "schema": "dk.froekjaer.timelapse.os_update_plan.v1",
        "source": "headend-cmdb-reconcile",
        "generated_at": created_at.isoformat(),
        "device_id": device_id,
        "environment": environment,
        "catalog_source": catalog["source"],
        "inventory_reported_at": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
        "decisions": decisions,
        "bundle_requests": _os_bundle_requests(device_id, environment, decisions, catalog),
    }
    stamp = f"{device_id}-{created_at:%Y%m%d-%H%M%S}"
    catalog_path = _write_update_json("update-catalogs", f"{stamp}.json", catalog)
    plan_path = _write_update_json("update-plans", f"{stamp}.json", plan)
    changes = []
    if payload.create_updates:
        changes = _upsert_blocked_os_updates_from_plan(db, device_id, environment, decisions, catalog["source"], plan_path)
        db.commit()
    return {
        "ok": True,
        "catalog_path": catalog_path,
        "plan_path": plan_path,
        "summary": catalog["summary"],
        "decisions": {
            key: {
                "package_count": value.get("package_count"),
                "severity": value.get("severity"),
                "package_preview": value.get("package_preview"),
                "truncated": value.get("truncated"),
            }
            for key, value in decisions.items()
        },
        "bundle_requests": [
            {
                "category": request["category"],
                "package_count": request["package_count"],
                "severity": request["severity"],
            }
            for request in plan["bundle_requests"]
        ],
        "updates": changes,
        "next": (
            "Byg offline OS bundle i lab med headend/tools/build_os_bundle.py --catalog "
            f"{plan_path}; kopiér bundlet til Headend; registrer OS artifact; bind artifact; godkend."
        ),
    }


@app.post("/api/updates/os-catalog/refresh-from-builder")
def refresh_os_catalog_from_mac_builder(
    payload: OsCatalogBuilderPayload,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Generér OS update-katalog fra CMDB inventory via Mac Headend Docker/arm64 builder."""
    device_id = (payload.device_id or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id er påkrævet")
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="CMDB inventory ikke fundet for device_id")
    try:
        installed = json.loads(inv.os_packages or "{}")
    except Exception:
        installed = {}
    if not isinstance(installed, dict) or not installed:
        raise HTTPException(status_code=409, detail="CMDB mangler OS package inventory for device")
    generated = _generate_os_update_catalog_candidates(
        installed=installed,
        device_id=device_id,
        architecture=payload.architecture or "arm64",
        image=payload.image or "ubuntu:24.04",
    )
    result = import_os_catalog_from_lab_apt_list(
        OsCatalogImportPayload(
            device_id=device_id,
            apt_list_text=generated["apt_list_text"],
            source=payload.source or f"mac-docker-builder:{payload.image or 'ubuntu:24.04'}:{device_id}",
            environment=payload.environment or "lab",
            create_updates=payload.create_updates,
        ),
        current_user,
        db,
    )
    result["builder"] = {
        "builder": generated["builder"],
        "image": generated.get("image"),
        "input_packages": generated["input_packages"],
        "upgradable_lines": generated["upgradable_lines"],
        "apt_list_output_path": generated["output_path"],
        "fallback_from": generated.get("fallback_from"),
        "fallback_reason": generated.get("fallback_reason"),
    }
    return result


@app.post("/api/updates/os-catalog/refresh-from-builder-job")
def start_refresh_os_catalog_from_mac_builder_job(
    payload: OsCatalogBuilderPayload,
    current_user=require_role("super_admin", "admin"),
):
    """Start asynkront job der genererer OS update-katalog fra CMDB via Mac Docker-builder."""
    payload_data = payload.dict()
    job_id = _new_update_job(
        "os_catalog_refresh",
        current_user.username,
        f"Refresh OS-katalog for {payload.device_id}",
        payload_data,
    )
    thread = _threading.Thread(
        target=_run_refresh_catalog_job,
        args=(job_id, payload_data, current_user.username),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "job_id": job_id, "status": _update_job_snapshot(job_id)}


@app.get("/api/updates/jobs/{job_id}")
def get_update_job_status(
    job_id: str,
    _user=require_role("super_admin", "admin"),
):
    return _update_job_snapshot(job_id)


@app.get("/api/updates/artifacts/{artifact_id}/files/{file_path:path}")
def download_update_artifact_file(
    artifact_id: str,
    file_path: str,
    device_id: str,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    """Edge henter kun filer, som er bundet i det signerede artifact-manifest."""
    artifact = db.query(UpdateArtifact).filter_by(artifact_id=artifact_id).first()
    if not artifact or not artifact.manifest_json:
        raise HTTPException(status_code=404, detail="Artifact ikke fundet")
    normalized = str(Path(file_path))
    if normalized.startswith("../") or normalized.startswith("/") or "/../" in normalized:
        raise HTTPException(status_code=400, detail="Ugyldig artifact path")
    manifest = json.loads(artifact.manifest_json)
    outputs = {
        str(item.get("path")): item
        for item in manifest.get("outputs", [])
        if isinstance(item, dict) and item.get("path")
    }
    expected = outputs.get(normalized)
    if not expected:
        raise HTTPException(status_code=404, detail="Fil er ikke del af artifact manifest")
    root = Path(artifact.storage_path or _repo_root()).resolve()
    full_path = (root / normalized).resolve()
    if root not in full_path.parents and full_path != root:
        raise HTTPException(status_code=400, detail="Artifact path udenfor storage root")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact fil mangler på Headend")
    actual_sha = _file_sha256(full_path)
    if actual_sha != expected.get("sha256"):
        raise HTTPException(status_code=409, detail="Artifact fil matcher ikke manifest SHA-256")
    return FileResponse(
        str(full_path),
        media_type="application/octet-stream",
        filename=Path(normalized).name,
        headers={
            "X-TLP-Artifact-Id": artifact_id,
            "X-TLP-Artifact-Path": normalized,
            "X-TLP-Artifact-Sha256": actual_sha,
        },
    )


@app.get("/api/updates/artifacts")
def list_update_artifacts(
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    artifacts = db.query(UpdateArtifact).order_by(UpdateArtifact.created_at.desc()).all()
    return [_artifact_to_dict(a) for a in artifacts]


@app.post("/api/updates/artifacts/catalog-current")
def catalog_current_release_artifact(
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Registrer den aktuelle Headend/UI release-manifest som signeret artifact."""
    root = _repo_root()
    commit = _git_text(["rev-parse", "HEAD"])
    if not commit:
        raise HTTPException(status_code=409, detail="Kunne ikke fastslå git commit for release artifact")
    ref = _git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    dirty = _release_worktree_dirty()
    created_at = now_utc()
    artifact_id = f"TL-ART-{created_at:%Y%m%d}-{commit[:12]}"
    existing = db.query(UpdateArtifact).filter_by(artifact_id=artifact_id).first()
    if existing:
        return _artifact_to_dict(existing)

    outputs = _collect_release_outputs(root)
    manifest = {
        "schema": "timelapse.update_artifact.v1",
        "artifact_id": artifact_id,
        "artifact_type": "app",
        "version": commit,
        "source": {
            "commit": commit,
            "ref": ref,
            "dirty_worktree": dirty,
        },
        "distribution_model": "headend_signed_artifact_catalog_edge_pull",
        "edge_constraints": {
            "edge_requires_direct_internet": False,
            "edge_requires_direct_github": False,
            "headend_is_update_authority": True,
        },
        "rollback": {
            "required": True,
            "strategy": "keep previous known-good artifact and rollback automatically on failed healthcheck",
        },
        "controls": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        "outputs": outputs,
        "created": {
            "by": current_user.username,
            "at": created_at.isoformat(),
        },
    }
    manifest_json = _canonical_json(manifest)
    manifest_sha = _sha256_text(manifest_json)
    signature, signed_by = _sign_payload(manifest_json)
    artifact = UpdateArtifact(
        artifact_id=artifact_id,
        artifact_type="app",
        version=commit,
        source_commit=commit,
        source_ref=ref,
        filename=f"{artifact_id}.manifest.json",
        storage_path=str(root),
        size_bytes=sum(int(o.get("size_bytes") or 0) for o in outputs),
        sha256=manifest_sha,
        manifest_json=manifest_json,
        sbom_ref=None,
        signature=signature,
        signed_by=signed_by,
        signed_at=created_at,
        created_at=created_at,
    )
    db.add(artifact)
    db.commit()
    return _artifact_to_dict(artifact)


# ── GitHub tag poller + artifact builder ──────────────────────────────────────

# Track which tags we've already catalogued (survives restart via DB query on start)
_git_tag_poller_seen: set[str] = set()
_git_tag_poller_lock = _threading.Lock()


def _build_artifact_from_git_tag(
    tag: str,
    triggered_by: str,
    db: Session,
) -> dict:
    """
    Byg og registrer et signeret release-artifact fra et GPG-signeret git-tag.
    Bruger `git archive` til at eksportere filerne uden at ændre working tree.
    """
    import tempfile as _tempfile

    root = _repo_root()

    # Verificer GPG-signatur på tagget
    verify = _subprocess.run(
        ["git", "tag", "-v", tag],
        cwd=str(root), capture_output=True, text=True, timeout=30,
    )
    if verify.returncode != 0:
        raise ValueError(
            f"GPG-verifikation fejlede for tag '{tag}': {verify.stderr.strip()}"
        )
    log.info("GPG-verifikation OK for tag %s", tag)

    # Hent commit-SHA for tagget
    commit = _git_text(["rev-list", "-n", "1", tag]) or ""
    if not commit:
        raise ValueError(f"Kunne ikke fastslå commit for tag '{tag}'")

    # Tjek om vi allerede har et artifact for dette commit
    existing = db.query(UpdateArtifact).filter_by(source_commit=commit, source_ref=tag).first()
    if existing:
        log.info("Artifact for tag %s / commit %s findes allerede: %s", tag, commit[:12], existing.artifact_id)
        return _artifact_to_dict(existing)

    # Eksporter git-arkiv til tempdir
    with _tempfile.TemporaryDirectory(prefix="tl-tag-") as tmpdir:
        archive_result = _subprocess.run(
            ["git", "archive", "--format=tar", f"--prefix=", tag],
            cwd=str(root), capture_output=True, timeout=120,
        )
        if archive_result.returncode != 0:
            raise ValueError(f"git archive fejlede: {archive_result.stderr.decode().strip()}")

        # Pak ud i tmpdir
        import tarfile as _tarfile
        import io as _io
        with _tarfile.open(fileobj=_io.BytesIO(archive_result.stdout)) as tar:
            tar.extractall(tmpdir)

        tmp_path = Path(tmpdir)
        outputs = _collect_release_outputs(tmp_path)
        if not outputs:
            raise ValueError(f"Ingen release-outputs fundet for tag {tag}")

        created_at = now_utc()
        artifact_id = f"TL-ART-{created_at:%Y%m%d}-{commit[:12]}"

        # Tjek endnu en gang med artifact_id (race guard)
        existing2 = db.query(UpdateArtifact).filter_by(artifact_id=artifact_id).first()
        if existing2:
            return _artifact_to_dict(existing2)

        manifest = {
            "schema": "timelapse.update_artifact.v1",
            "artifact_id": artifact_id,
            "artifact_type": "app",
            "version": tag,
            "source": {
                "commit": commit,
                "ref": tag,
                "dirty_worktree": False,
                "build_method": "git_archive_tag",
            },
            "distribution_model": "headend_signed_artifact_catalog_edge_pull",
            "edge_constraints": {
                "edge_requires_direct_internet": False,
                "edge_requires_direct_github": False,
                "headend_is_update_authority": True,
            },
            "rollback": {
                "required": True,
                "strategy": "keep previous known-good artifact and rollback automatically on failed healthcheck",
            },
            "controls": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
            "outputs": outputs,
            "created": {
                "by": triggered_by,
                "at": created_at.isoformat(),
            },
        }
        manifest_json = _canonical_json(manifest)
        manifest_sha = _sha256_text(manifest_json)
        signature, signed_by = _sign_payload(manifest_json)
        artifact = UpdateArtifact(
            artifact_id=artifact_id,
            artifact_type="app",
            version=tag,
            source_commit=commit,
            source_ref=tag,
            filename=f"{artifact_id}.manifest.json",
            storage_path=str(root),
            size_bytes=sum(int(o.get("size_bytes") or 0) for o in outputs),
            sha256=manifest_sha,
            manifest_json=manifest_json,
            sbom_ref=None,
            signature=signature,
            signed_by=signed_by,
            signed_at=created_at,
            created_at=created_at,
        )
        db.add(artifact)
        db.commit()
        log.info("Artifact %s bygget og registreret for tag %s", artifact_id, tag)
        return _artifact_to_dict(artifact)


def _git_tag_poller_loop(interval_hours: float = 1.0) -> None:
    """
    Baggrunds-tråd: poller GitHub for nye GPG-signerede tags og bygger artifacts automatisk.
    Kører kun hvis TIMELAPSE_REPO_DIR er sat (dvs. lab-headend med internet-adgang).
    """
    import time as _time
    interval_s = max(60, interval_hours * 3600)

    # Seed _git_tag_poller_seen med allerede kendte tags fra DB
    try:
        _seed_db = SessionLocal()
        existing_refs = {
            row[0]
            for row in _seed_db.execute(
                text("SELECT source_ref FROM update_artifacts WHERE source_ref IS NOT NULL")
            ).fetchall()
        }
        _seed_db.close()
        with _git_tag_poller_lock:
            _git_tag_poller_seen.update(existing_refs)
    except Exception as _seed_err:
        log.warning("Git tag poller: kunne ikke seed seen-set fra DB: %s", _seed_err)

    while True:
        try:
            root = _repo_root()
            # Hent seneste tags fra GitHub (kun hvis remote er tilgængeligt)
            fetch = _subprocess.run(
                ["git", "fetch", "--tags", "--force"],
                cwd=str(root), capture_output=True, text=True, timeout=60,
            )
            if fetch.returncode != 0:
                log.debug("git fetch --tags: %s", fetch.stderr.strip())
            else:
                # Find alle tags med en GPG-signatur (annotated tags med signatur)
                tags_raw = _git_text(["tag", "--list", "v*", "--sort=-version:refname"]) or ""
                tags = [t.strip() for t in tags_raw.splitlines() if t.strip()]
                with _git_tag_poller_lock:
                    new_tags = [t for t in tags if t not in _git_tag_poller_seen]

                for tag in new_tags:
                    # Kun GPG-signerede annotated tags
                    verify = _subprocess.run(
                        ["git", "tag", "-v", tag],
                        cwd=str(root), capture_output=True, text=True, timeout=15,
                    )
                    if verify.returncode != 0:
                        log.info("Git tag poller: tag '%s' er ikke GPG-signeret — springer over", tag)
                        with _git_tag_poller_lock:
                            _git_tag_poller_seen.add(tag)
                        continue

                    try:
                        _tag_db = SessionLocal()
                        result = _build_artifact_from_git_tag(tag, "git-tag-poller", _tag_db)
                        _tag_db.close()
                        log.info("Git tag poller: artifact bygget for tag %s → %s", tag, result.get("artifact_id"))
                    except Exception as _tag_err:
                        log.warning("Git tag poller: fejl ved build af tag '%s': %s", tag, _tag_err)
                    finally:
                        with _git_tag_poller_lock:
                            _git_tag_poller_seen.add(tag)
        except Exception as _poll_err:
            log.warning("Git tag poller fejl: %s", _poll_err)

        _time.sleep(interval_s)


# ── Automatisk OS bundle builder ──────────────────────────────────────────────

def _os_bundle_auto_poller_loop(interval_minutes: float = 10.0) -> None:
    """
    Baggrunds-tråd: finder pending OS updates uden artifact og bygger dem automatisk
    via fetch_os_bundle.py (rent Python, ingen Docker-afhængighed).

    Triggeres automatisk når edge rapporterer nye apt-opdateringer via inventory.
    Dette sikrer at godkendelsesflowet ikke blokeres af manglende artifacts.
    """
    import time as _time

    interval_s = max(60, interval_minutes * 60)

    # Giv serveren tid til at starte fuldt op
    _time.sleep(30)

    while True:
        try:
            _os_bundle_auto_build_pending()
        except Exception as _poll_err:
            log.warning("OS bundle auto-poller fejl: %s", _poll_err)
        _time.sleep(interval_s)


def _os_bundle_auto_build_pending() -> None:
    """
    Finder alle pending OS-updates uden artifact og bygger et offline .deb bundle
    via fetch_os_bundle.py (Python-mode, kræver ikke Docker).

    Bruger første super_admin som systembruger til artifact-signering.
    """
    import sys as _sys

    db = SessionLocal()
    try:
        # Find pending OS-updates uden artifact
        pending = (
            db.query(PendingUpdate)
            .filter(
                PendingUpdate.update_type.in_(["os_security", "os_updates"]),
                PendingUpdate.status.in_(["pending"]),
            )
            .order_by(PendingUpdate.created_at)
            .all()
        )
        if not pending:
            return

        # System-bruger til auto-signering
        system_user = (
            db.query(User)
            .filter(User.role == "super_admin")
            .order_by(User.id)
            .first()
        )
        if not system_user:
            log.warning("OS bundle auto-poller: ingen super_admin fundet — springer over")
            return

        for update in pending:
            # Tjek om artifact allerede er bundet
            existing_artifact = _find_artifact_for_update(db, update)
            if existing_artifact:
                continue

            device_id = (update.scope_id or "").strip()
            if not device_id:
                log.debug("OS bundle auto-poller: update #%d har ingen scope_id — springer over", update.id)
                continue

            log.info(
                "OS bundle auto-poller: bygger artifact for update #%d (%s, enhed %s)",
                update.id, update.update_type, device_id,
            )
            try:
                _auto_build_and_bind_os_bundle(db, update, device_id, system_user)
            except Exception as exc:
                log.warning(
                    "OS bundle auto-poller: fejl ved build af update #%d: %s",
                    update.id, exc,
                )
    finally:
        db.close()


def _auto_build_and_bind_os_bundle(
    db: Session,
    update: PendingUpdate,
    device_id: str,
    system_user: User,
) -> None:
    """
    Bygger offline OS bundle for én PendingUpdate via fetch_os_bundle.build_bundle().
    Registrerer og binder artifactet til opdateringen.
    Kræver ikke Docker — henter .deb filer direkte fra Ubuntu/Docker mirrors.
    """
    import importlib.util as _importlib_util

    # Dynamisk import af fetch_os_bundle (ligger i tools/ ikke i Python-path)
    _fb_path = _Path(__file__).parent / "tools" / "fetch_os_bundle.py"
    _spec = _importlib_util.spec_from_file_location("fetch_os_bundle", str(_fb_path))
    if not _spec or not _spec.loader:
        raise RuntimeError(f"Kan ikke importere fetch_os_bundle fra {_fb_path}")
    _fb_mod = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_fb_mod)  # type: ignore[union-attr]

    # Hent pakkeliste fra inventory (soft_inventory JSON i DB)
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    packages_raw: list[dict] = []
    if inv and inv.software_inventory:
        try:
            sw = json.loads(inv.software_inventory) if isinstance(inv.software_inventory, str) else inv.software_inventory
            apt_data = sw.get("_os_updates_available") or {}
            packages_raw = apt_data.get("packages") or []
        except Exception:
            pass

    if not packages_raw:
        raise RuntimeError(
            f"Ingen pakker i inventory for {device_id} — "
            "kan ikke bygge OS bundle uden pakkeliste"
        )

    # Konverter inventory-format (name + new_ver) til fetch_os_bundle-format (name + available_version)
    # Filtrer til den relevante update_type (security vs. non-security)
    want_security = (update.update_type == "os_security")
    packages = [
        {
            "name":               p["name"],
            "available_version":  p.get("new_ver") or p.get("available_version") or "",
            "installed_version":  p.get("old_ver") or p.get("installed_version") or "",
            "source_repo":        p.get("source_repo") or "",
            "category":           update.update_type,
        }
        for p in packages_raw
        if bool(p.get("security")) == want_security
        and (p.get("new_ver") or p.get("available_version"))
    ]

    if not packages and not any("security" in p for p in packages_raw):
        # Legacy inventory uden security-flag: brug hele listen som fallback.
        # Hvis security-flag findes og ingen pakker matcher, må vi ikke bygge et
        # funktionelt OS-bundle som om det var en security-update.
        packages = [
            {
                "name":               p["name"],
                "available_version":  p.get("new_ver") or p.get("available_version") or "",
                "installed_version":  p.get("old_ver") or p.get("installed_version") or "",
                "source_repo":        p.get("source_repo") or "",
                "category":           update.update_type,
            }
            for p in packages_raw
            if p.get("new_ver") or p.get("available_version")
        ]

    if not packages:
        raise RuntimeError(f"Ingen gyldige pakker at downloade for update #{update.id}")

    suite = _infer_ubuntu_suite_for_os_bundle(inv, packages)
    architecture = _infer_architecture_for_os_bundle(packages)
    target_os = f"ubuntu-{_ubuntu_version_label_for_suite(suite)}/orangepi"

    # Output-sti i OS bundle store
    created_at = now_utc()
    safe_type = _re.sub(r"[^a-zA-Z0-9_.-]+", "-", update.update_type)
    output_root = _os_bundle_store_root().expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / f"auto-{update.id}-{safe_type}-{created_at:%Y%m%d-%H%M%S}"

    # Byg bundlet
    result = _fb_mod.build_bundle(
        packages=packages,
        output=output_path,
        device_id=device_id,
        suite=suite,
        arch=architecture,
        target_os=target_os,
        source_ref=f"headend-auto-fetch:{created_at:%Y%m%dT%H%M%SZ}",
        verbose=True,
    )

    log.info(
        "OS bundle auto-poller: bundle bygget — %d debs, %d ikke fundet, sti: %s",
        result["deb_files"], len(result["not_found"]), output_path,
    )

    if not result.get("ok") or result["deb_files"] == 0:
        raise RuntimeError(
            f"OS bundle build fejlede: ingen .deb filer downloadet "
            f"(not_found={result['not_found']})"
        )

    # Registrer artifact i DB
    artifact_dict = catalog_os_update_artifact(
        {
            "storage_path": str(output_path),
            "version": f"{device_id}-{update.update_type}-{created_at:%Y%m%d-%H%M%S}",
            "architecture": architecture,
            "target_os": target_os,
            "source_ref": f"headend-auto-fetch:{created_at:%Y%m%dT%H%M%SZ}",
            "lab_evidence": {
                "builder": "fetch_os_bundle.py (headend-auto)",
                "packages_requested": result["packages_requested"],
                "deb_files": result["deb_files"],
                "not_found": result["not_found"],
                "ubuntu_suite": suite,
                "architecture": architecture,
                "triggered_from": "os_bundle_auto_poller",
            },
        },
        system_user,
        db,
    )
    log.info("OS bundle auto-poller: artifact registreret: %s", artifact_dict.get("artifact_id"))

    # Bind artifact til PendingUpdate
    bind_artifact_to_update(
        update.id,
        {
            "artifact_id": artifact_dict["artifact_id"],
            "summary": (
                f"OS bundle automatisk bygget af Headend auto-poller "
                f"({result['deb_files']} pakker downloadet fra Ubuntu/Docker mirrors; "
                f"suite={suite}, arch={architecture}). "
                f"Ingen Docker eller internet på edge krævet."
            ),
            "test_evidence_ref": f"headend-auto-fetch:{created_at:%Y%m%dT%H%M%SZ}",
        },
        system_user,
        db,
    )
    log.info(
        "OS bundle auto-poller: artifact %s bundet til update #%d ✓",
        artifact_dict["artifact_id"], update.id,
    )


def _infer_ubuntu_suite_for_os_bundle(inv: DeviceInventory | None, packages: list[dict]) -> str:
    """Infer Ubuntu suite from inventory/repo metadata; never upgrade across OS releases."""
    source_text = " ".join(str(p.get("source_repo") or "") for p in packages).lower()
    match = _re.search(r"/(jammy|noble|focal|bionic)(?:[-/]|$)", source_text)
    if match:
        return match.group(1)
    match = _re.search(r"ubuntu:(?:18\.04|20\.04|22\.04|24\.04)/(jammy|noble|focal|bionic)", source_text)
    if match:
        return match.group(1)

    os_name = str(getattr(inv, "os_name", "") or "").lower()
    if "24.04" in os_name:
        return "noble"
    if "22.04" in os_name:
        return "jammy"
    if "20.04" in os_name:
        return "focal"
    if "18.04" in os_name:
        return "bionic"
    return "noble"


def _ubuntu_version_label_for_suite(suite: str) -> str:
    return {
        "noble": "24.04",
        "jammy": "22.04",
        "focal": "20.04",
        "bionic": "18.04",
    }.get(str(suite or "").lower(), suite or "unknown")


def _infer_architecture_for_os_bundle(packages: list[dict]) -> str:
    for pkg in packages:
        arch = str(pkg.get("architecture") or pkg.get("arch") or "").strip()
        if arch and arch != "all":
            return arch
    return "arm64"


@app.post("/api/updates/artifacts/catalog-from-git-tag")
def catalog_artifact_from_git_tag(
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """
    Registrer et signeret release-artifact fra et GPG-signeret git-tag.
    Hvis tag er tomt/udeladt bruges det seneste signerede tag automatisk.
    """
    tag = str(payload.get("tag") or "").strip()

    root = _repo_root()

    # Hent seneste tags
    fetch = _subprocess.run(
        ["git", "fetch", "--tags", "--force"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )
    if fetch.returncode != 0:
        log.warning("git fetch --tags fejlede: %s", fetch.stderr.strip())

    if not tag:
        # Find seneste tag
        tag = _git_text(["describe", "--tags", "--abbrev=0"]) or ""
        if not tag:
            raise HTTPException(status_code=409, detail="Ingen git-tags fundet i repository")

    # Verificer tagget eksisterer
    check = _subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        cwd=str(root), capture_output=True, text=True, timeout=10,
    )
    if check.returncode != 0:
        raise HTTPException(status_code=404, detail=f"Git-tag '{tag}' ikke fundet")

    try:
        result = _build_artifact_from_git_tag(tag, current_user.username, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    with _git_tag_poller_lock:
        _git_tag_poller_seen.add(tag)

    return result


@app.post("/api/updates/artifacts/catalog-os-bundle")
def catalog_os_update_artifact(
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Registrer en lab-bygget offline OS update bundle som signeret artifact."""
    storage_path = Path(str(payload.get("storage_path") or "")).expanduser().resolve()
    if not storage_path.is_dir():
        raise HTTPException(status_code=400, detail="storage_path skal være en eksisterende mappe")
    version = str(payload.get("version") or storage_path.name).strip()
    if not version:
        raise HTTPException(status_code=400, detail="version er påkrævet")
    commands = payload.get("commands")
    if commands is None:
        commands = _default_os_bundle_commands()
    if not isinstance(commands, list) or not commands:
        raise HTTPException(status_code=400, detail="commands skal være en ikke-tom liste")
    _validate_os_bundle_commands(commands)

    outputs = []
    for file_path in sorted(p for p in storage_path.rglob("*") if p.is_file()):
        rel = str(file_path.relative_to(storage_path))
        if rel.startswith("../") or "/../" in rel or file_path.name in {".DS_Store", "Icon\r"}:
            continue
        outputs.append({
            "path": rel,
            "size_bytes": file_path.stat().st_size,
            "sha256": _file_sha256(file_path),
        })
    if not outputs:
        raise HTTPException(status_code=400, detail="OS bundle indeholder ingen filer")
    output_paths = {item["path"] for item in outputs}
    deb_outputs = [p for p in output_paths if p.startswith("packages/") and p.endswith(".deb")]
    if not deb_outputs:
        raise HTTPException(status_code=400, detail="OS bundle skal indeholde packages/*.deb")
    if "package-manifest.json" not in output_paths:
        raise HTTPException(status_code=400, detail="OS bundle mangler package-manifest.json fra lab builder")
    if "verify-installed.sh" not in output_paths:
        raise HTTPException(status_code=400, detail="OS bundle mangler verify-installed.sh fra lab builder")
    _validate_os_bundle_file_policy(storage_path, outputs)

    created_at = now_utc()
    bundle_hash = _sha256_text(_canonical_json({
        "version": version,
        "outputs": outputs,
        "commands": commands,
    }))[:12]
    artifact_id = f"TL-OS-{created_at:%Y%m%d}-{bundle_hash}"
    existing = db.query(UpdateArtifact).filter_by(artifact_id=artifact_id).first()
    if existing:
        return _artifact_to_dict(existing)

    manifest = {
        "schema": "timelapse.os_update_artifact.v1",
        "artifact_id": artifact_id,
        "artifact_type": "os",
        "version": version,
        "target": {
            "os": payload.get("target_os") or "debian/orangepi",
            "architecture": payload.get("architecture") or "arm64",
            "device_scope": payload.get("device_scope") or "edge",
        },
        "distribution_model": "headend_signed_offline_os_bundle_edge_pull",
        "edge_constraints": {
            "edge_requires_direct_internet": False,
            "edge_may_run_apt_get_upgrade": False,
            "install_commands_must_use_offline_bundle": True,
        },
        "commands": commands,
        "rollback": {
            "required": True,
            "strategy": payload.get("rollback_strategy") or "pre-update Edge backup; dpkg/apt rollback requires lab-defined package downgrade bundle if needed",
        },
        "controls": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        "outputs": outputs,
        "created": {
            "by": current_user.username,
            "at": created_at.isoformat(),
            "lab_evidence": payload.get("lab_evidence"),
        },
    }
    manifest_json = _canonical_json(manifest)
    manifest_sha = _sha256_text(manifest_json)
    signature, signed_by = _sign_payload(manifest_json)
    artifact = UpdateArtifact(
        artifact_id=artifact_id,
        artifact_type="os",
        version=version,
        source_commit=None,
        source_ref=str(payload.get("source_ref") or "lab-os-bundle"),
        filename=f"{artifact_id}.manifest.json",
        storage_path=str(storage_path),
        size_bytes=sum(int(o.get("size_bytes") or 0) for o in outputs),
        sha256=manifest_sha,
        manifest_json=manifest_json,
        sbom_ref=payload.get("sbom_ref"),
        signature=signature,
        signed_by=signed_by,
        signed_at=created_at,
        created_at=created_at,
    )
    db.add(artifact)
    db.commit()
    return _artifact_to_dict(artifact)


@app.post("/api/updates/{update_id}/os-bundle/build-bind")
def build_catalog_and_bind_os_bundle(
    update_id: int,
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Byg et offline OS bundle via Headend-styret builder, registrér artifact og bind til update."""
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    if update.update_type not in {"os_security", "os_updates"}:
        raise HTTPException(status_code=400, detail="Kun OS updates kan få bygget OS bundle")
    device_id = (update.scope_id or payload.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id kunne ikke fastslås for update")
    plan_path_raw = str(payload.get("plan_path") or _plan_path_for_update(update) or "").strip()
    if not plan_path_raw:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "os_plan_missing",
                "message": "Update mangler OS plan. Importér lab-katalog fra UI først, så Headend har pakkelisten.",
            },
        )
    plan_path = Path(plan_path_raw).expanduser().resolve()
    if not plan_path.is_file():
        raise HTTPException(status_code=409, detail=f"OS plan findes ikke på Headend: {plan_path}")

    mode = str(payload.get("builder_mode") or "auto").strip().lower()
    if mode not in {"auto", "mac_container"}:
        raise HTTPException(status_code=400, detail="builder_mode skal være auto eller mac_container")
    docker_ok, docker_error = _docker_available()
    if not docker_ok:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "builder_runtime_missing",
                "message": "Headend er Mac og skal bruge Docker/Colima eller en lab-builder runtime for at bygge Linux/arm64 OS-bundles fra UI.",
                "runtime": "docker/colima",
                "reason": docker_error,
            },
        )

    created_at = now_utc()
    safe_type = _re.sub(r"[^a-zA-Z0-9_.-]+", "-", update.update_type)
    output_root = _os_bundle_store_root().expanduser().resolve()
    output_path = output_root / f"update-{update.id}-{safe_type}-{created_at:%Y%m%d-%H%M%S}"
    architecture = str(payload.get("architecture") or "arm64")
    source_ref = str(payload.get("source_ref") or f"headend-mac-container:{created_at:%Y%m%dT%H%M%SZ}")
    image = str(payload.get("image") or "ubuntu:24.04")

    build = _build_os_bundle_in_mac_container(
        plan_path=plan_path,
        output_path=output_path,
        device_id=device_id,
        architecture=architecture,
        source_ref=source_ref,
        image=image,
        category=update.update_type,
    )
    artifact = catalog_os_update_artifact(
        {
            "storage_path": str(output_path),
            "version": f"{device_id}-{update.update_type}-{created_at:%Y%m%d-%H%M%S}",
            "architecture": architecture,
            "target_os": payload.get("target_os") or "ubuntu-24.04/orangepi",
            "source_ref": source_ref,
            "lab_evidence": {
                "builder": build.get("builder"),
                "image": build.get("image"),
                "plan_path": str(plan_path),
                "triggered_from": "headend_ui",
            },
        },
        current_user,
        db,
    )
    bind = bind_artifact_to_update(
        update_id,
        {
            "artifact_id": artifact["artifact_id"],
            "summary": "OS bundle bygget via Headend UI og Mac container builder.",
            "test_evidence_ref": source_ref,
        },
        current_user,
        db,
    )
    return {
        "ok": True,
        "update_id": update_id,
        "bundle_path": str(output_path),
        "artifact": artifact,
        "bind": bind,
        "build": build,
    }


@app.post("/api/updates/{update_id}/os-bundle/build-bind-job")
def start_build_catalog_and_bind_os_bundle_job(
    update_id: int,
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Start asynkront job der bygger offline OS bundle, registrerer artifact og binder det til update."""
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    if update.update_type not in {"os_security", "os_updates"}:
        raise HTTPException(status_code=400, detail="Kun OS updates kan få bygget OS bundle")
    payload_data = dict(payload or {})
    job_id = _new_update_job(
        "os_bundle_build_bind",
        current_user.username,
        f"Byg og bind OS artifact for update #{update_id}",
        {"update_id": update_id, **payload_data},
    )
    thread = _threading.Thread(
        target=_run_os_bundle_build_bind_job,
        args=(job_id, update_id, payload_data, current_user.username),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "job_id": job_id, "status": _update_job_snapshot(job_id)}


@app.post("/api/updates/{update_id}/bind-artifact")
def bind_artifact_to_update(
    update_id: int,
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Bind et signeret artifact til en konkret update og gør den klar til godkendelse."""
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    artifact_id = str(payload.get("artifact_id") or "").strip()
    artifact = db.query(UpdateArtifact).filter_by(artifact_id=artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact ikke fundet")
    if update.update_type in {"os_security", "os_updates"} and artifact.artifact_type != "os":
        raise HTTPException(status_code=400, detail="OS updates kræver OS artifact")
    if update.update_type not in {"os_security", "os_updates"} and artifact.artifact_type == "os":
        raise HTTPException(status_code=400, detail="OS artifact kan kun bindes til OS updates")

    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).order_by(ChangeTicket.created_at.desc()).first()
    if not ticket:
        ticket = _build_change_ticket(
            update,
            ChangeTicketPayload(
                title=f"Bind artifact {artifact.artifact_id} til {update.update_type}",
                summary=payload.get("summary") or update.description or "",
                rollback_plan=payload.get("rollback_plan") or "Pre-update Edge backup; rollback requires lab-defined downgrade bundle if OS packages must be reverted.",
                status="ready",
            ),
            current_user,
            artifact,
        )
        db.add(ticket)
    else:
        ticket.artifact_id = artifact.artifact_id
        ticket.sbom_ref = artifact.sbom_ref
        ticket.test_evidence_ref = payload.get("test_evidence_ref") or ticket.test_evidence_ref
        ticket.updated_at = now_utc()

    if update.status == "blocked":
        update.status = "pending"
    update.description = ((update.description or "").rstrip() + f"\n\nArtifact bound {now_utc().isoformat()}: {artifact.artifact_id}")[-6000:]
    db.commit()
    return {"ok": True, "update_id": update.id, "artifact_id": artifact.artifact_id, "status": update.status}


def _build_change_ticket(
    update: PendingUpdate,
    payload: ChangeTicketPayload,
    user: User,
    artifact: UpdateArtifact | None = None,
) -> ChangeTicket:
    created_at = now_utc()
    ticket_id = f"TL-CHG-{created_at:%Y%m%d}-{update.id:05d}"
    title = payload.title or f"{update.update_type} {update.version}"
    summary = payload.summary or update.description or ""
    rollback_plan = payload.rollback_plan or "Automatisk rollback ved fejlet healthcheck; manuel intervention hvis rollback fejler."
    maintenance_window = payload.maintenance_window or "Efter gældende update policy"
    risk = _risk_assessment(update.update_type, update.severity, None, None, update.status)
    machine = {
        "schema": "timelapse.change_ticket.v1",
        "ticket_id": ticket_id,
        "pending_update_id": update.id,
        "title": title,
        "summary": summary,
        "update": {
            "type": update.update_type,
            "version": update.version,
            "severity": update.severity,
            "environment": update.environment or "production",
            "scope": update.scope,
            "scope_id": update.scope_id,
            "target_device_ids": json.loads(update.target_device_ids) if update.target_device_ids else None,
            "distribution_model": "edge_pull_via_headend",
            "internet_dependency": "edge_must_not_require_direct_internet_or_github",
        },
        "risk": {
            "score": risk["score"],
            "level": risk["level"],
            "factors": risk["factors"],
            "reboot_required": bool(payload.reboot_required),
            "maintenance_window": maintenance_window,
            "rollback_plan": rollback_plan,
        },
        "created": {
            "by": user.username,
            "at": created_at.isoformat(),
        },
    }
    if artifact:
        machine["artifact"] = {
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type,
            "version": artifact.version,
            "source_commit": artifact.source_commit,
            "source_ref": artifact.source_ref,
            "sha256": artifact.sha256,
            "signed_by": artifact.signed_by,
            "signed_at": artifact.signed_at.isoformat() if artifact.signed_at else None,
        }
    machine_json = _canonical_json(machine)
    content_sha256 = _sha256_text(machine_json)
    signature, signed_by = _sign_payload(machine_json)
    human_md = "\n".join([
        f"# {ticket_id} - {title}",
        "",
        f"**Status:** {payload.status or 'ready'}",
        f"**Update:** {update.update_type} {update.version}",
        f"**Severity:** {update.severity}",
        f"**Risk score:** {risk['score']}/100 ({risk['level']})",
        f"**Miljø:** {update.environment or 'production'}",
        f"**Scope:** {update.scope or 'device'}{f' / {update.scope_id}' if update.scope_id else ''}",
        f"**Oprettet af:** {user.username}",
        f"**Oprettet:** {created_at.isoformat()}",
        "",
        "## Beskrivelse",
        summary or "Ingen beskrivelse angivet.",
        "",
        "## Deployment-flow",
        "Edge rapporterer inventory og tilgængelige opdateringer til Headend. Headend er update authority og holder signerede artifacts/change tickets. Edge henter kun godkendte opdateringer fra Headend ved næste poll; Headend pusher ikke til Edge i normal drift. SSH-tunnel bruges kun til manuel fejlsøgning.",
        "",
        "## Artifact",
        f"Artifact ID: `{artifact.artifact_id}`" if artifact else "Ingen artifact er bundet endnu. Opret/registrer artifact i Headend-kataloget før produktionsgodkendelse.",
        f"Artifact SHA-256: `{artifact.sha256}`" if artifact else "",
        f"Artifact signeret af: {artifact.signed_by or '-'}" if artifact else "",
        "",
        "## Rollback-plan",
        rollback_plan,
        "",
        "## Risikovurdering",
        "Score beregnes ud fra teknisk severity, update-kategori, miljø/business impact og deployment-status.",
        f"Faktorer: {', '.join(risk['factors']) if risk['factors'] else 'ingen særlige faktorer'}",
        "",
        "## Vedligehold/reboot",
        f"Maintenance window: {maintenance_window}",
        f"Reboot required: {bool(payload.reboot_required)}",
        "",
        "## Maskinlæsbar binding",
        f"SHA-256: `{content_sha256}`",
    ])
    return ChangeTicket(
        ticket_id=ticket_id,
        title=title,
        summary=summary,
        pending_update_id=update.id,
        update_type=update.update_type,
        severity=update.severity,
        environment=update.environment or "production",
        scope=update.scope,
        scope_id=update.scope_id,
        status=payload.status or "ready",
        source_commit=artifact.source_commit if artifact else (update.version if update.update_type in ("app_security", "app_updates") else None),
        source_ref=artifact.source_ref if artifact else None,
        artifact_id=artifact.artifact_id if artifact else None,
        sbom_ref=artifact.sbom_ref if artifact else None,
        rollback_plan=rollback_plan,
        reboot_required=bool(payload.reboot_required),
        maintenance_window=maintenance_window,
        human_readable_md=human_md,
        machine_json=machine_json,
        content_sha256=content_sha256,
        signature=signature,
        signed_by=signed_by,
        signed_at=created_at,
        created_by=user.username,
        created_at=created_at,
        updated_at=created_at,
    )


def _resolve_update_targets(db: Session, update: PendingUpdate) -> list[Device]:
    if update.target_device_ids:
        ids = json.loads(update.target_device_ids)
        return db.query(Device).filter(Device.device_id.in_(ids)).all()
    if update.scope == "global":
        return db.query(Device).all()
    if update.scope == "customer" and update.scope_id:
        return db.query(Device).filter(Device.customer_id == update.scope_id).all()
    if update.scope == "site" and update.scope_id:
        return db.query(Device).filter(Device.site_id == update.scope_id).all()
    if update.scope == "device" and update.scope_id:
        device = db.query(Device).filter_by(device_id=update.scope_id).first()
        return [device] if device else []
    return []


def _ensure_update_targets(db: Session, update: PendingUpdate, ticket: ChangeTicket | None = None) -> int:
    created = 0
    for device in _resolve_update_targets(db, update):
        existing = db.query(UpdateTarget).filter_by(
            pending_update_id=update.id,
            device_id=device.device_id,
        ).first()
        if existing:
            if ticket and ticket.ticket_id and not existing.ticket_id:
                existing.ticket_id = ticket.ticket_id
            if ticket and ticket.artifact_id and existing.artifact_id != ticket.artifact_id:
                existing.artifact_id = ticket.artifact_id
            if update.status == "approved" and existing.status in {"pending", "failed"}:
                existing.status = "queued"
                existing.last_error = None
            existing.customer_id = existing.customer_id or device.customer_id
            existing.site_id = existing.site_id or device.site_id
            existing.target_version = existing.target_version or update.version
            continue
        db.add(UpdateTarget(
            pending_update_id=update.id,
            ticket_id=ticket.ticket_id if ticket else None,
            artifact_id=ticket.artifact_id if ticket else None,
            device_id=device.device_id,
            camera_id=None,
            customer_id=device.customer_id,
            site_id=device.site_id,
            status="queued" if update.status == "approved" else "pending",
            current_version=device.app_version,
            target_version=update.version,
        ))
        created += 1
    return created


def _update_flow_stage(update: PendingUpdate, artifact: UpdateArtifact | None, targets: list[dict]) -> dict:
    if update.status == "pending":
        return {"key": "pending_approval", "label": "Afventer godkendelse"}
    if update.status == "blocked" and update.update_type in {"os_security", "os_updates"} and not artifact:
        return {"key": "waiting_for_lab_os_bundle", "label": "Afventer lab-bygget offline OS bundle"}
    if update.status == "blocked":
        return {"key": "blocked", "label": "Blokeret"}
    if update.status == "approved" and not artifact and _update_requires_headend_artifact(update.update_type):
        return {"key": "missing_artifact", "label": "Mangler signeret artifact"}
    if update.status == "approved":
        active = {str(t.get("status") or "") for t in targets}
        if active & {"downloading", "verifying", "backing_up", "installing"}:
            return {"key": sorted(active & {"downloading", "verifying", "backing_up", "installing"})[0], "label": "Edge arbejder"}
        if active & {"failed"}:
            return {"key": "target_failed", "label": "Edge blokeret/fejlet"}
        return {"key": "waiting_for_edge_poll", "label": "Afventer Edge heartbeat/policy-pull"}
    if update.status == "deployed":
        return {"key": "deployed", "label": "Installeret"}
    if update.status == "rolled_back":
        return {"key": "rolled_back", "label": "Rollback udført"}
    if update.status == "rejected":
        return {"key": "rejected", "label": "Afvist"}
    if update.status == "cancelled":
        return {"key": "cancelled", "label": "Annulleret"}
    return {"key": update.status or "unknown", "label": STATUS_LABELS.get(update.status, update.status or "Ukendt") if "STATUS_LABELS" in globals() else (update.status or "Ukendt")}


@app.get("/api/updates/{update_id}/flow-status")
def get_update_flow_status(
    update_id: int,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Detaljeret update-flow pr. target, inkl. hvad Edge/Headend venter på."""
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    artifact = _find_artifact_for_update(db, update)
    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).order_by(ChangeTicket.created_at.desc()).first()
    devices = _resolve_update_targets(db, update)
    target_rows = (
        db.query(UpdateTarget)
        .filter_by(pending_update_id=update.id)
        .order_by(UpdateTarget.device_id, UpdateTarget.id.desc())
        .all()
    )
    latest_target_by_device: dict[str, UpdateTarget] = {}
    for target in target_rows:
        latest_target_by_device.setdefault(target.device_id, target)
    device_ids = [device.device_id for device in devices]
    inventory_by_device = {
        inv.device_id: inv
        for inv in db.query(DeviceInventory).filter(DeviceInventory.device_id.in_(device_ids)).all()
    } if device_ids else {}
    now = now_utc()
    target_payloads: list[dict] = []
    for device in devices:
        inventory = inventory_by_device.get(device.device_id)
        target = latest_target_by_device.get(device.device_id)
        last_seen = ensure_utc(device.last_seen) if device and device.last_seen else None
        age_s = max(0, int((now - last_seen).total_seconds())) if last_seen else None
        status = target.status if target else ("queued" if update.status == "approved" else update.status)
        blocked_for_missing_os_artifact = update.status == "blocked" and update.update_type in {"os_security", "os_updates"} and not artifact
        if blocked_for_missing_os_artifact:
            status = "blocked"
            waiting_for = "lab_os_bundle"
        elif update.status == "approved" and status in {"queued", "pending"}:
            waiting_for = "edge_policy_pull"
        elif status in {"downloading", "verifying", "backing_up", "installing"}:
            waiting_for = status
        elif update.status == "blocked":
            waiting_for = "artifact_or_lab_evidence"
        else:
            waiting_for = None
        target_payloads.append({
            "device_id": device.device_id,
            "hostname": (inventory.hostname if inventory else None) or device.location_name or device.device_id,
            "status": status,
            "waiting_for": waiting_for,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "last_seen_age_s": age_s,
            "last_report_at": target.last_report_at.isoformat() if target and target.last_report_at else None,
            "started_at": target.started_at.isoformat() if target and target.started_at else None,
            "completed_at": target.completed_at.isoformat() if target and target.completed_at else None,
            "attempt_count": target.attempt_count if target else 0,
            "last_error": (
                "os_update_requires_headend_signed_offline_artifact"
                if blocked_for_missing_os_artifact
                else (target.last_error if target else None)
            ),
            "artifact_id": target.artifact_id if target else (artifact.artifact_id if artifact else None),
            "target_version": update.version if blocked_for_missing_os_artifact else (target.target_version if target else update.version),
        })
    if not target_payloads and update.scope_id:
        target_payloads.append({
            "device_id": update.scope_id,
            "hostname": None,
            "status": "target_not_in_cmdb",
            "waiting_for": "cmdb_device_record",
            "last_seen": None,
            "last_seen_age_s": None,
            "last_report_at": None,
            "started_at": None,
            "completed_at": None,
            "attempt_count": 0,
            "last_error": "Update scope peger på en enhed, som ikke findes i CMDB Device-tabellen.",
            "artifact_id": artifact.artifact_id if artifact else None,
            "target_version": update.version,
        })
    return {
        "update_id": update.id,
        "status": update.status,
        "update_type": update.update_type,
        "version": update.version,
        "environment": update.environment,
        "scope": update.scope,
        "scope_id": update.scope_id,
        "artifact": _artifact_for_edge_policy(db, artifact) if artifact else None,
        "ticket_id": ticket.ticket_id if ticket else None,
        "targets": target_payloads,
        "stage": _update_flow_stage(update, artifact, target_payloads),
        "next_edge_poll": "Edge henter update-policy ved næste agent update-check/heartbeat. Headend pusher ikke normalt til Edge.",
    }


@app.get("/api/change-tickets")
def list_change_tickets(
    status: Optional[str] = None,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """List change tickets til review, kundegodkendelse og audit."""
    q = db.query(ChangeTicket)
    if status:
        q = q.filter_by(status=status)
    tickets = q.order_by(ChangeTicket.created_at.desc()).all()
    return [_ticket_to_dict(t) for t in tickets]


@app.get("/api/change-tickets/{ticket_id}")
def get_change_ticket(
    ticket_id: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    ticket = db.query(ChangeTicket).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Change ticket ikke fundet")
    approvals = db.query(ChangeApproval).filter_by(ticket_id=ticket_id).order_by(ChangeApproval.decided_at.desc()).all()
    data = _ticket_to_dict(ticket)
    data["approvals"] = [
        {
            "decision": a.decision,
            "decided_by": a.decided_by,
            "decided_at": a.decided_at.isoformat() if a.decided_at else None,
            "signed_payload_sha256": a.signed_payload_sha256,
            "signature": a.signature,
            "notes": a.notes,
        }
        for a in approvals
    ]
    return data


@app.post("/api/updates/{update_id}/change-ticket")
def create_change_ticket_for_update(
    update_id: int,
    payload: ChangeTicketPayload = ChangeTicketPayload(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Generér et hash-bundet change ticket for en PendingUpdate."""
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    existing = db.query(ChangeTicket).filter_by(pending_update_id=update_id).first()
    if existing:
        return _ticket_to_dict(existing)
    artifact = _find_artifact_for_update(db, update)
    ticket = _build_change_ticket(update, payload, current_user, artifact)
    db.add(ticket)
    db.flush()
    created_targets = _ensure_update_targets(db, update, ticket)
    db.commit()
    log.info("Change ticket %s oprettet for update %d af %s", ticket.ticket_id, update_id, current_user.username)
    data = _ticket_to_dict(ticket)
    data["created_targets"] = created_targets
    return data


@app.post("/api/change-tickets/{ticket_id}/approve")
def approve_change_ticket(
    ticket_id: str,
    payload: ChangeDecisionPayload = ChangeDecisionPayload(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Godkend et change ticket og bind godkendelsen til en hash."""
    ticket = db.query(ChangeTicket).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Change ticket ikke fundet")
    decided_at = now_utc()
    signed_payload = {
        "ticket_id": ticket.ticket_id,
        "ticket_sha256": ticket.content_sha256,
        "decision": "approved",
        "decided_by": current_user.username,
        "decided_at": decided_at.isoformat(),
        "notes": payload.notes,
    }
    signed_hash = _sha256_text(_canonical_json(signed_payload))
    signature, signed_by = _sign_payload(_canonical_json(signed_payload))
    db.add(ChangeApproval(
        ticket_id=ticket.ticket_id,
        decision="approved",
        decided_by=current_user.username,
        decided_at=decided_at,
        approval_context=_canonical_json({
            "role": current_user.role,
            "customer_id": current_user.customer_id,
            "signed_by": signed_by,
        }),
        signature=signature,
        signed_payload_sha256=signed_hash,
        notes=payload.notes,
    ))
    ticket.status = "approved"
    ticket.updated_at = decided_at
    if ticket.pending_update_id:
        update = db.query(PendingUpdate).filter_by(id=ticket.pending_update_id).first()
        if update and update.status in ("pending", "rejected"):
            _assert_update_has_required_artifact(db, update)
            update.status = "approved"
            update.approved_at = decided_at
            update.approved_by = current_user.username
            _ensure_update_targets(db, update, ticket)
    db.commit()
    return {"ok": True, "ticket_id": ticket.ticket_id, "signed_payload_sha256": signed_hash}


@app.post("/api/change-tickets/{ticket_id}/reject")
def reject_change_ticket(
    ticket_id: str,
    payload: ChangeDecisionPayload = ChangeDecisionPayload(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Afvis et change ticket og bind beslutningen til en hash."""
    ticket = db.query(ChangeTicket).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Change ticket ikke fundet")
    decided_at = now_utc()
    signed_payload = {
        "ticket_id": ticket.ticket_id,
        "ticket_sha256": ticket.content_sha256,
        "decision": "rejected",
        "decided_by": current_user.username,
        "decided_at": decided_at.isoformat(),
        "notes": payload.notes,
    }
    signed_hash = _sha256_text(_canonical_json(signed_payload))
    signature, signed_by = _sign_payload(_canonical_json(signed_payload))
    db.add(ChangeApproval(
        ticket_id=ticket.ticket_id,
        decision="rejected",
        decided_by=current_user.username,
        decided_at=decided_at,
        approval_context=_canonical_json({
            "role": current_user.role,
            "customer_id": current_user.customer_id,
            "signed_by": signed_by,
        }),
        signature=signature,
        signed_payload_sha256=signed_hash,
        notes=payload.notes,
    ))
    ticket.status = "rejected"
    ticket.updated_at = decided_at
    if ticket.pending_update_id:
        update = db.query(PendingUpdate).filter_by(id=ticket.pending_update_id).first()
        if update and update.status == "pending":
            update.status = "rejected"
            update.approved_at = decided_at
            update.approved_by = current_user.username
    db.commit()
    return {"ok": True, "ticket_id": ticket.ticket_id, "signed_payload_sha256": signed_hash}


@app.post("/api/updates/{update_id}/approve")
def approve_update(
    update_id: int,
    payload: ApprovePayload = ApprovePayload(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Godkend en opdatering til deployment med scope og miljø."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    if u.status not in ("pending", "rejected"):
        raise HTTPException(status_code=400, detail=f"Kan ikke godkende opdatering med status '{u.status}'")
    if payload.scope == "device" and not payload.scope_id and not payload.target_device_ids:
        raise HTTPException(status_code=400, detail="Device scope kræver scope_id eller target_device_ids")
    _assert_update_has_required_artifact(db, u)

    artifact = _find_artifact_for_update(db, u)
    ticket = db.query(ChangeTicket).filter_by(pending_update_id=u.id).order_by(ChangeTicket.created_at.desc()).first()
    if not ticket:
        ticket = _build_change_ticket(
            u,
            ChangeTicketPayload(
                title=f"{u.update_type} {u.version}",
                summary=u.description or "",
                status="ready",
            ),
            current_user,
            artifact,
        )
        db.add(ticket)
        db.flush()

    decided_at = now_utc()
    signed_payload = {
        "ticket_id": ticket.ticket_id,
        "ticket_sha256": ticket.content_sha256,
        "decision": "approved",
        "decided_by": current_user.username,
        "decided_at": decided_at.isoformat(),
        "approval_surface": "updates_page_approve",
        "pending_update_id": u.id,
    }
    signed_hash = _sha256_text(_canonical_json(signed_payload))
    signature, signed_by = _sign_payload(_canonical_json(signed_payload))
    db.add(ChangeApproval(
        ticket_id=ticket.ticket_id,
        decision="approved",
        decided_by=current_user.username,
        decided_at=decided_at,
        approval_context=_canonical_json({
            "role": current_user.role,
            "customer_id": current_user.customer_id,
            "signed_by": signed_by,
        }),
        signature=signature,
        signed_payload_sha256=signed_hash,
    ))

    ticket.status       = "approved"
    ticket.updated_at   = decided_at
    u.status            = "approved"
    u.approved_at       = decided_at
    u.approved_by       = current_user.username
    u.environment       = payload.environment or "production"
    if payload.scope:
        u.scope    = payload.scope
        u.scope_id = None if payload.scope == "global" else payload.scope_id
    else:
        u.scope    = u.scope or "device"
    target_ids = payload.target_device_ids
    if target_ids is not None:
        u.target_device_ids = json.dumps(target_ids) if target_ids else None
    _ensure_update_targets(db, u, ticket)
    db.commit()
    log.info("Opdatering godkendt: %s v%s → %s/%s af %s",
             u.update_type, u.version, u.environment, u.scope, current_user.username)
    return {"ok": True, "ticket_id": ticket.ticket_id, "signed_payload_sha256": signed_hash}


def _control_summary_state(controls: list[dict]) -> dict:
    counts = {"pass": 0, "warning": 0, "fail": 0, "unknown": 0}
    for control in controls:
        status = control.get("status", "unknown")
        counts[status if status in counts else "unknown"] += 1
    return counts


def _approval_targets_for_update(db: Session, update: PendingUpdate) -> list[dict]:
    targets = []
    device_map = {d.device_id: d for d in _resolve_update_targets(db, update)}
    if not device_map and update.scope == "device" and update.scope_id:
        device = db.query(Device).filter_by(device_id=update.scope_id).first()
        if device:
            device_map[device.device_id] = device
    for device in device_map.values():
        targets.append({
            "device_id": device.device_id,
            "customer_id": device.customer_id,
            "customer_name": device.customer_name,
            "site_id": device.site_id,
            "site_name": device.site_name,
            "camera_name": device.camera_name,
        })
    return targets


def _user_can_approve_update(user: User, update: PendingUpdate, targets: list[dict]) -> bool:
    if user.role in ("super_admin", "admin"):
        return True
    if user.role != "operator":
        return False
    if not user.customer_id:
        return False
    if update.scope == "customer" and update.scope_id == user.customer_id:
        return True
    return any(t.get("customer_id") == user.customer_id for t in targets)


def _compliance_approval_state(db: Session, update: PendingUpdate) -> dict:
    artifact = _find_artifact_for_update(db, update)
    artifact_required = _update_requires_headend_artifact(update.update_type)
    if update.status != "pending":
        return {
            "actionable": False,
            "artifact_required": artifact_required,
            "artifact_missing": artifact_required and not artifact,
            "reason": f"status_{update.status}",
            "message": f"Opdateringen har status {update.status} og kan ikke accepteres fra Compliance.",
            "next_action": "Opret en ny lab/testet update eller brug Updates-flowet til at genåbne den korrekt.",
        }
    if artifact_required and not artifact:
        return {
            "actionable": False,
            "artifact_required": True,
            "artifact_missing": True,
            "reason": "missing_headend_signed_artifact",
            "message": (
                "Opdateringen mangler Headend-signeret artifact. "
                "Edge må ikke installere via direkte internet/GitHub/apt."
            ),
            "next_action": "Byg og signer artifact i Headendens update-flow, og bind artifact til opdateringen før godkendelse.",
        }
    return {
        "actionable": True,
        "artifact_required": artifact_required,
        "artifact_missing": False,
        "reason": None,
        "message": "Klar til Compliance-accept.",
        "next_action": "Acceptér update for at oprette/godkende change ticket.",
    }


def _approval_queue(db: Session, user: User) -> list[dict]:
    updates = (
        db.query(PendingUpdate)
        .filter(PendingUpdate.status == "pending")
        .order_by(PendingUpdate.created_at.desc())
        .all()
    )
    queue = []
    for update in updates:
        targets = _approval_targets_for_update(db, update)
        if not _user_can_approve_update(user, update, targets):
            continue
        ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).first()
        artifact = _find_artifact_for_update(db, update)
        approval_state = _compliance_approval_state(db, update)
        risk = _risk_assessment(update.update_type, update.severity, None, None, update.status)
        queue.append({
            "id": update.id,
            "update_type": update.update_type,
            "version": update.version,
            "description": update.description,
            "severity": update.severity,
            "status": update.status,
            "environment": update.environment,
            "scope": update.scope,
            "scope_id": update.scope_id,
            "created_at": update.created_at.isoformat() if update.created_at else None,
            "risk": risk,
            "targets": targets,
            "change_ticket": _ticket_to_dict(ticket) if ticket else None,
            "artifact": _artifact_to_dict(artifact) if artifact else None,
            "artifact_required": approval_state["artifact_required"],
            "artifact_missing": approval_state["artifact_missing"],
            "actionable": approval_state["actionable"],
            "block_reason": approval_state["reason"],
            "action_message": approval_state["message"],
            "next_action": approval_state["next_action"],
            "approval_mode": "simple_acceptance",
        })
    return queue


@app.get("/api/compliance/cockpit")
def compliance_cockpit(
    current_user=require_role("operator"),
    db: Session = Depends(get_db),
):
    """Samlet compliance cockpit og enkel approval-kø."""
    key_data = list_key_management(_user=object(), db=db)
    resilience = resilience_assessment(_user=object(), db=db)
    aiops = _aiops_snapshot(db)
    controls = []
    for source, items in [
        ("key_management", key_data.get("controls", [])),
        ("resilience", resilience.get("controls", [])),
    ]:
        for control in items:
            controls.append({**control, "source": source})
    if aiops["sast"]["finding_count"]:
        controls.append({
            "source": "ai_ops",
            "status": "warning",
            "title": "SAST review backlog",
            "evidence": f"{aiops['sast']['finding_count']} statiske review-signaler kræver triage.",
            "domains": ["ISO27000", "CRA"],
            "recommendation": "Konverter validerede fund til signerede change tickets.",
        })
    approvals = _approval_queue(db, current_user)
    return {
        "generated_at": now_utc().isoformat(),
        "mode": "near_realtime_compliance_posture",
        "user_scope": {
            "username": current_user.username,
            "role": current_user.role,
            "customer_id": current_user.customer_id,
        },
        "summary": {
            "controls": _control_summary_state(controls),
            "approval_queue": len(approvals),
            "devices": resilience.get("summary", {}).get("devices", 0),
            "change_tickets": resilience.get("summary", {}).get("change_tickets", 0),
            "sast_findings": aiops["sast"]["finding_count"],
        },
        "standards": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        "controls": controls,
        "approvals": approvals,
        "evidence_sources": [
            "CMDB inventory",
            "SIEM events",
            "Key credential lifecycle",
            "Signed artifacts",
            "Signed change tickets",
            "Resilience/backup assessment",
            "AI Ops read-only analysis",
        ],
    }


@app.get("/api/compliance/reports/{standard}")
def compliance_standard_report(
    standard: str,
    current_user=require_role("operator"),
    db: Session = Depends(get_db),
):
    """Generér en standard-specifik GRC/compliance rapport."""
    allowed = {"SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"}
    normalized = standard.upper().replace("IEC62443", "IEC62443").replace("IEC 62443", "IEC62443").replace("ISO27001", "ISO27000")
    if normalized not in allowed:
        raise HTTPException(status_code=404, detail="Ukendt standard")
    cockpit = compliance_cockpit(current_user=current_user, db=db)
    grc = grc_dashboard(_user=current_user, db=db)
    controls = [
        control for control in cockpit.get("controls", [])
        if normalized in control.get("domains", [])
    ]
    counts = _control_summary_state(controls)
    high_risk_devices = [
        device for device in grc.get("devices", [])
        if int(device.get("risk_score") or 0) >= 45
    ]
    gaps = [
        {
            "title": control.get("title"),
            "status": control.get("status"),
            "evidence": control.get("evidence"),
            "recommendation": control.get("recommendation"),
            "source": control.get("source"),
        }
        for control in controls
        if control.get("status") in {"warning", "fail"}
    ]
    emphasis = {
        "SABSA": "Business-attributter, risikoejerskab, accountability og arkitekturbeslutninger.",
        "IEC62443": "Industriel/edge sikkerhed, zones/conduits, identity, patch governance og teknisk hardening.",
        "ISO27000": "ISMS-kontrol, adgangsstyring, kryptografi, backup, logging og change management.",
        "NIS2": "Driftskontinuitet, leverancekæde, hændelsesberedskab, patch governance og ledelsesrapportering.",
        "CRA": "Produkt-sikkerhed, secure update, vulnerability handling, SBOM/artifact integrity og lifecycle evidence.",
    }
    return {
        "standard": normalized,
        "generated_at": now_utc().isoformat(),
        "scope": "TimeLapse Pro Headend, Edge devices, CMDB, update flow, key management, backup/resilience and SIEM evidence",
        "emphasis": emphasis[normalized],
        "summary": {
            "controls": counts,
            "control_count": len(controls),
            "gap_count": len(gaps),
            "fleet_risk_score": grc.get("summary", {}).get("fleet_risk_score", 0),
            "high_risk_devices": len(high_risk_devices),
            "approval_queue": cockpit.get("summary", {}).get("approval_queue", 0),
        },
        "controls": controls,
        "gaps": gaps,
        "high_risk_devices": high_risk_devices[:10],
        "evidence_sources": cockpit.get("evidence_sources", []),
        "recommended_next_steps": [
            gap["recommendation"] for gap in gaps[:8]
            if gap.get("recommendation")
        ],
    }


@app.post("/api/compliance/updates/{update_id}/accept")
def compliance_accept_update(
    update_id: int,
    payload: ChangeTicketPayload = ChangeTicketPayload(status="ready"),
    current_user=require_role("operator"),
    db: Session = Depends(get_db),
):
    """Simpel brugeraccept af relevant update med audit/change-ticket binding."""
    update = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    targets = _approval_targets_for_update(db, update)
    if not _user_can_approve_update(current_user, update, targets):
        raise HTTPException(status_code=403, detail="Du kan ikke godkende denne opdatering")
    if update.status != "pending":
        raise HTTPException(status_code=400, detail=f"Kan ikke godkende update med status {update.status}")
    approval_state = _compliance_approval_state(db, update)
    if not approval_state["actionable"]:
        status_code = 409 if approval_state["artifact_missing"] else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": approval_state["message"],
                "reason": approval_state["reason"],
                "next_action": approval_state["next_action"],
            },
        )
    _assert_update_has_required_artifact(db, update)

    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).first()
    if not ticket:
        artifact = _find_artifact_for_update(db, update)
        ticket = _build_change_ticket(update, payload, current_user, artifact)
        db.add(ticket)
        db.flush()
        _ensure_update_targets(db, update, ticket)

    decided_at = now_utc()
    signed_payload = {
        "ticket_id": ticket.ticket_id,
        "ticket_sha256": ticket.content_sha256,
        "decision": "approved",
        "decided_by": current_user.username,
        "decided_at": decided_at.isoformat(),
        "approval_surface": "compliance_cockpit_simple_acceptance",
        "notes": payload.summary,
    }
    signed_hash = _sha256_text(_canonical_json(signed_payload))
    signature, signed_by = _sign_payload(_canonical_json(signed_payload))
    db.add(ChangeApproval(
        ticket_id=ticket.ticket_id,
        decision="approved",
        decided_by=current_user.username,
        decided_at=decided_at,
        approval_context=_canonical_json({
            "role": current_user.role,
            "customer_id": current_user.customer_id,
            "signed_by": signed_by,
            "targets": targets,
        }),
        signature=signature,
        signed_payload_sha256=signed_hash,
        notes=payload.summary,
    ))
    ticket.status = "approved"
    ticket.updated_at = decided_at
    update.status = "approved"
    update.approved_at = decided_at
    update.approved_by = current_user.username
    _ensure_update_targets(db, update, ticket)
    db.commit()
    return {"ok": True, "update_id": update.id, "ticket_id": ticket.ticket_id, "signed_payload_sha256": signed_hash}

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


@app.post("/api/updates/{update_id}/promote")
def promote_update(
    update_id: int,
    payload: PromotePayload = PromotePayload(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Promovér en test/lab-godkendt opdatering til staging eller production."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    target_environment = (payload.target_environment or "production").strip().lower()
    if target_environment not in {"staging", "production"}:
        raise HTTPException(status_code=400, detail="target_environment skal være staging eller production")
    if u.environment not in {"lab", "test", "staging"}:
        raise HTTPException(status_code=400, detail="Kan kun promovere fra lab/test/staging")
    if target_environment == "staging" and u.environment not in {"lab", "test"}:
        raise HTTPException(status_code=400, detail="Staging-promotion kræver lab/test som kilde")
    if target_environment == "production" and u.environment == "staging" and u.status != "deployed":
        raise HTTPException(status_code=400, detail="Production fra staging kræver deployed staging-evidens")
    if target_environment == "production" and u.environment in {"lab", "test"} and u.status != "deployed":
        raise HTTPException(status_code=400, detail="Production kræver deployed lab/test-evidens")
    if target_environment == "staging" and u.status not in {"approved", "deployed"}:
        raise HTTPException(status_code=400, detail="Staging kræver godkendt eller deployet test/lab-update")
    existing_prod = db.query(PendingUpdate).filter(
        PendingUpdate.update_type == u.update_type,
        PendingUpdate.version == u.version,
        PendingUpdate.environment == target_environment,
        PendingUpdate.scope == u.scope,
        PendingUpdate.scope_id == u.scope_id,
        PendingUpdate.status.in_(["pending", "approved", "deployed"]),
    ).order_by(PendingUpdate.id.desc()).first()
    if existing_prod:
        return {"ok": True, "new_id": existing_prod.id, "existing": True}
    source_ticket = db.query(ChangeTicket).filter_by(pending_update_id=u.id).order_by(ChangeTicket.created_at.desc()).first()
    prod_update = PendingUpdate(
        update_type       = u.update_type,
        version           = u.version,
        description       = f"[Promoveret fra {u.environment} til {target_environment}] {u.description or ''}",
        severity          = u.severity,
        scope             = u.scope,
        scope_id          = u.scope_id,
        status            = "pending" if target_environment == "production" else "approved",
        approved_at       = now_utc() if target_environment == "staging" else None,
        approved_by       = current_user.username if target_environment == "staging" else None,
        environment       = target_environment,
        target_device_ids = u.target_device_ids,
    )
    db.add(prod_update)
    db.flush()
    if source_ticket and source_ticket.artifact_id:
        artifact = db.query(UpdateArtifact).filter_by(artifact_id=source_ticket.artifact_id).first()
        if artifact:
            ticket = _build_change_ticket(
                prod_update,
                ChangeTicketPayload(
                    title=f"Promotion to {target_environment}: {u.update_type} {u.version}",
                    summary=prod_update.description,
                    rollback_plan=source_ticket.rollback_plan,
                    maintenance_window=source_ticket.maintenance_window,
                    reboot_required=source_ticket.reboot_required,
                    status="ready" if target_environment == "production" else "approved",
                ),
                current_user,
                artifact,
            )
            db.add(ticket)
            if target_environment == "staging":
                _ensure_update_targets(db, prod_update, ticket)
    db.commit()
    log.info("Opdatering %d promoveret til %s af %s", update_id, target_environment, current_user.username)
    return {"ok": True, "new_id": prod_update.id}

@app.post("/api/updates/{update_id}/force-rollback")
def force_rollback(
    update_id: int,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Marker en opdatering til tvungen rollback — edge ruller tilbage ved næste check."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    u.status = "rollback_requested"
    db.commit()
    log.info("Rollback anmodet for opdatering %d af %s", update_id, current_user.username)
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

    policy = _resolved_update_policy(db, device)
    policy["app_security"] = policy.get("timelapse_security", "auto")
    policy["app_updates"] = policy.get("timelapse_updates", "manual")

    pending_candidates = db.query(PendingUpdate).filter(PendingUpdate.status == "pending").all()
    auto_changed = False
    for candidate in pending_candidates:
        if _update_applies_to_device(candidate, device, db.query(DeviceInventory).filter_by(device_id=device_id).first() or DeviceInventory(device_id=device_id)):
            approved, _reason = _auto_approve_update_for_target(db, candidate, device)
            auto_changed = auto_changed or approved
    if auto_changed:
        db.commit()

    # Find godkendte opdateringer til denne enhed
    from database import PendingUpdate as _PU
    from sqlalchemy import or_
    approved = db.query(_PU).filter(
        _PU.status.in_(["approved", "rollback_requested"]),
        or_(_PU.scope == "global", _PU.scope_id == device_id)
    ).all()

    filtered = []
    for u in approved:
        if u.target_device_ids:
            targets = json.loads(u.target_device_ids)
            if device_id not in targets:
                continue
        artifact = _find_artifact_for_update(db, u)
        if _update_requires_headend_artifact(u.update_type) and not artifact:
            log.warning(
                "Approved update %s/%s withheld from Edge policy for %s: missing signed artifact",
                u.id, u.update_type, device_id,
            )
            u.status = "blocked"
            u.description = ((u.description or "").rstrip() + (
                f"\n\nBlocked {now_utc().isoformat()}: approved update withheld from Edge policy "
                "because it lacks required Headend-signed artifact."
            ))[-6000:]
            db.commit()
            continue
        filtered.append({
            "id":          u.id,
            "update_type": u.update_type,
            "version":     u.version,
            "status":      u.status,
            "environment": u.environment,
            "severity":    u.severity,
            "artifact":    _artifact_for_edge_policy(db, artifact),
        })

    return {**policy, "pending_updates": filtered}

@app.post("/api/updates/report")
def report_update(payload: dict, db: Session = Depends(get_db)):
    """Edge rapporterer resultat af deployment (deployed/rolled_back/blocked)."""
    from database import PendingUpdate
    update_id = payload.get("update_id")
    status    = payload.get("status")
    reason    = str(payload.get("reason") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    final_statuses = {"deployed", "rolled_back", "blocked"}
    progress_statuses = {"queued", "downloading", "verifying", "backing_up", "installing"}
    if not update_id or status not in (final_statuses | progress_statuses):
        raise HTTPException(status_code=400)
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if status in final_statuses:
        u.status = status
        if status == "deployed":
            u.deployed_at = now_utc()
        elif status == "rolled_back":
            u.rollback_at = now_utc()
            u.failed_count = (u.failed_count or 0) + 1
        elif status == "blocked":
            u.failed_count = (u.failed_count or 0) + 1
    if reason and status in final_statuses:
        u.description = ((u.description or "").rstrip() + f"\n\nEdge report {now_utc().isoformat()}: {status}; reason={reason[:700]}")[-6000:]
    if device_id:
        ticket = db.query(ChangeTicket).filter_by(pending_update_id=u.id).order_by(ChangeTicket.created_at.desc()).first()
        target = (
            db.query(UpdateTarget)
            .filter_by(pending_update_id=u.id, device_id=device_id)
            .order_by(UpdateTarget.id.desc())
            .first()
        )
        if not target:
            target = UpdateTarget(
                pending_update_id=u.id,
                ticket_id=ticket.ticket_id if ticket else None,
                artifact_id=ticket.artifact_id if ticket else None,
                device_id=device_id,
                target_version=u.version,
                status="pending",
                started_at=now_utc(),
            )
            db.add(target)
        target.ticket_id = ticket.ticket_id if ticket and ticket.ticket_id else target.ticket_id
        target.artifact_id = ticket.artifact_id if ticket and ticket.artifact_id else target.artifact_id
        target.target_version = u.version
        target.status = "failed" if status == "blocked" else status
        target.attempt_count = (target.attempt_count or 0) + (1 if status == "installing" else 0)
        target.last_error = reason[:1000] if reason else None
        target.started_at = target.started_at or now_utc()
        target.completed_at = now_utc() if status in final_statuses else target.completed_at
        target.rollback_at = now_utc() if status == "rolled_back" else target.rollback_at
        target.last_report_at = now_utc()
        target.report_json = json.dumps(payload, ensure_ascii=False)
    db.commit()
    log.info("Update %d rapporteret som %s fra device", update_id, status)
    return {"ok": True}





# ════════════════════════════════════════════════════════════════════════

@app.post("/api/updates/available")
def report_available_updates(
    payload: dict,
    db: Session = Depends(get_db),
):
    """Edge rapporterer app-update hints.

    OS updates maa ikke oprettes fra Edge-reported "available" counts. Edge er
    kun installed-state reporter; Headend reconciler OS-mangler fra CMDB mod et
    Headend-ejet lab/mirror-katalog.
    """
    from database import PendingUpdate

    device_id          = payload.get("device_id", "unknown")
    os_security_count  = int(payload.get("os_security_count", 0))
    os_updates_count   = int(payload.get("os_updates_count", 0))
    app_version        = payload.get("app_version", "")
    app_behind_commits = int(payload.get("app_behind_commits", 0))
    app_security       = bool(payload.get("app_security", False))

    created = []

    def _active_update(update_type: str) -> PendingUpdate | None:
        from sqlalchemy import or_
        return db.query(PendingUpdate).filter(
            PendingUpdate.update_type == update_type,
            PendingUpdate.scope == "device",
            PendingUpdate.scope_id == device_id,
            PendingUpdate.status.in_(["pending", "approved", "blocked"]),
        ).order_by(PendingUpdate.created_at.desc()).first()

    def _refresh_active_update(update: PendingUpdate | None, version: str, description: str, severity: str) -> bool:
        if not update:
            return False
        changed = False
        if update.version != version:
            update.version = version
            changed = True
        if update.description and "Blocked:" in update.description:
            base, blocked_note = update.description.split("Blocked:", 1)
            description = description.rstrip() + "\n\nBlocked:" + blocked_note
        if update.description != description:
            update.description = description
            changed = True
        if update.severity != severity:
            update.severity = severity
            changed = True
        if changed:
            db.query(UpdateTarget).filter_by(pending_update_id=update.id).update({
                "target_version": version,
            })
        return changed

    if os_security_count > 0:
        created.append("os_security_ignored_cmdb_catalog_required")
    if os_updates_count > 0:
        created.append("os_updates_ignored_cmdb_catalog_required")

    if app_security and not _active_update("app_security"):
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

    if app_behind_commits > 0 and not _active_update("app_updates"):
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


def _headend_api_url(db: Session, explicit_url: str | None = None) -> str:
    """Return the Edge-facing API URL used in bootstrap.yaml."""
    raw = (
        explicit_url
        or os.getenv("EDGE_PUBLIC_HEADEND_URL")
        or _get_setting(db, "edge_public_headend_url", "")
        or _get_setting(db, "base_url", "")
        or os.getenv("BASE_URL", "")
        or "http://127.0.0.1:8000/api"
    ).strip().rstrip("/")
    if not raw.endswith("/api"):
        raw = raw + "/api"
    return raw


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
    headend_url = _get_setting(db, "base_url", os.getenv("BASE_URL", "http://127.0.0.1:8000"))

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
    _ensure_capture_device_access(db, _user, device_id)
    for field in ["customer_name", "site_name", "camera_name", "location_name"]:
        if field in info:
            setattr(device, field, info[field])
    db.commit()
    log.info("Updated device info for %s", device_id)
    return {"status": "ok", "device_id": device_id}


@app.get("/api/admin/devices")
def list_devices(_user=require_role("viewer"), db: Session = Depends(get_db)):
    """List all devices with latest status."""
    devices = _visible_device_query(db, _user).order_by(Device.last_seen.desc()).all()
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
    camera_id: Optional[str] = None,
    limit: int = 50,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    """List recent captures, optionally filtered by device og/eller kamera-lokation.

    camera_id (2026-07-03, additivt, se Claude_Kritisk_Statusgennemgang_2026-07-03.md
    §2.4/§2.5): filtrerer på den logiske kamera-lokation frem for det fysiske
    device. Nyttigt til at se fuld billedhistorik på tværs af Edge-udskiftninger.
    Kun captures skrevet efter v12-migrationen (eller backfillet, se
    tools/backfill_capture_camera_customer.py) har camera_id sat.
    """
    q = db.query(Capture).order_by(Capture.captured_at.desc())
    allowed_device_ids = _allowed_capture_device_ids(db, _user)
    if allowed_device_ids is not None:
        # NB (Fase 3, 2026-07-03): ingen "tomt device-sæt -> return []"-genvej her
        # længere — en kunde skal fortsat kunne se sine EGNE historiske billeder
        # (via Capture.customer_id) selvom det device, der tog dem, sidenhen er
        # blevet omtildelt væk fra kunden og derfor ikke længere er i det aktuelle
        # device-sæt. _capture_tenant_clause() matcher korrekt "ingenting" i sig selv,
        # hvis brugeren hverken har customer_id-match eller device-match.
        q = q.filter(_capture_tenant_clause(_user, allowed_device_ids))
    if device_id:
        _ensure_capture_device_access(db, _user, device_id)
        q = q.filter_by(device_id=device_id)
    if camera_id:
        cam = db.query(Camera).filter_by(id=camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Kamera ikke fundet")
        if cam.site_id:
            _ensure_site_access(db, _user, cam.site_id)
        elif cam.customer_id:
            _ensure_customer_access(_user, cam.customer_id)
        q = q.filter(Capture.camera_id == camera_id)
    captures = q.limit(limit).all()
    return [
        {
            "id":            c.id,
            "device_id":     c.device_id,
            "camera_id":     c.camera_id if hasattr(c, 'camera_id') else None,
            "customer_id":   c.customer_id if hasattr(c, 'customer_id') else None,
            "site_id":       c.site_id if hasattr(c, 'site_id') else None,
            "filename":      c.filename,
            "captured_at":   c.captured_at.isoformat() if c.captured_at else None,
            "quality_flag":  c.quality_flag,
            "quality_passed":c.quality_passed,
            "blur_score":    round(c.blur_score, 1) if c.blur_score else None,
            "brightness":    round(c.brightness_mean, 1) if c.brightness_mean else None,
            "filesize_mb":   round(c.filesize / 1e6, 1) if c.filesize else None,
            "uploaded":      c.uploaded,
            "camera_model":  c.camera_model,
            "iso":           c.iso,
            "aperture":      c.aperture,
            "shutter_speed": c.exposure_time,
            "exposure_time": c.exposure_time,
            "gps_lat":       c.gps_lat if hasattr(c, 'gps_lat') else None,
            "gps_lon":       c.gps_lon if hasattr(c, 'gps_lon') else None,
            "gps_alt_m":     c.gps_alt_m if hasattr(c, 'gps_alt_m') else None,
            "gps_source":    c.gps_source if hasattr(c, 'gps_source') else None,
            "azimuth_deg":   c.azimuth_deg if hasattr(c, 'azimuth_deg') else None,
            "tilt_deg":      c.tilt_deg if hasattr(c, 'tilt_deg') else None,
            "mount_height_m": c.mount_height_m if hasattr(c, 'mount_height_m') else None,
            "fov_horizontal_deg": c.fov_horizontal_deg if hasattr(c, 'fov_horizontal_deg') else None,
            "fov_vertical_deg": c.fov_vertical_deg if hasattr(c, 'fov_vertical_deg') else None,
            "perspective":   c.perspective if hasattr(c, 'perspective') else None,
            "xmp_written":   c.xmp_written if hasattr(c, 'xmp_written') else None,
            "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
            "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
            "ai_tags":        json.loads(c.ai_tags) if hasattr(c, 'ai_tags') and c.ai_tags else None,
        }
        for c in captures
    ]


@app.get("/api/admin/stats")
def stats(_user=require_role("viewer"), db: Session = Depends(get_db)):
    """Overall system statistics."""
    visible_devices = _visible_device_query(db, _user)
    total_devices  = visible_devices.count()
    cq = db.query(Capture)
    allowed_device_ids = _allowed_capture_device_ids(db, _user)
    if allowed_device_ids is not None:
        # NB (Fase 3, 2026-07-03): se tilsvarende note i list_captures() — ingen
        # "tomt device-sæt" genvej, da egne historiske billeder skal tælles med
        # via Capture.customer_id selv efter en device-omtildeling.
        cq = cq.filter(_capture_tenant_clause(_user, allowed_device_ids))
        total_captures = cq.count()
        passed         = cq.filter(Capture.quality_passed.is_(True)).count()
        uploaded       = cq.filter(Capture.uploaded.is_(True)).count()
    else:
        total_captures = cq.count()
        passed         = cq.filter(Capture.quality_passed.is_(True)).count()
        uploaded       = cq.filter(Capture.uploaded.is_(True)).count()

    return {
        "total_devices":   total_devices,
        "total_captures":  total_captures,
        "quality_pass_pct": round(100 * passed / total_captures, 1) if total_captures else 0,
        "upload_pct":       round(100 * uploaded / total_captures, 1) if total_captures else 0,
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/sidecar/{device_id}/{filename}")
def get_sidecar(
    device_id: str,
    filename: str,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    """Returner sidecar JSON metadata for et billede."""
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    image_filename = _re.sub(r"\.json$", ".jpg", filename, flags=_re.IGNORECASE)
    capture = _ensure_capture_file_access(db, _user, device_id, image_filename)
    image_path = _find_image(device_id, image_filename)
    if not image_path and capture.sidecar_path:
        sidecar_path = _Path(capture.sidecar_path)
        if sidecar_path.exists():
            return JSONResponse(
                _json.loads(sidecar_path.read_text(encoding="utf-8")),
                headers={"Cache-Control": "no-store"},
            )
    if image_path:
        sidecar_path = image_path.with_suffix(".json")
        if sidecar_path.exists():
            return JSONResponse(
                _json.loads(sidecar_path.read_text(encoding="utf-8")),
                headers={"Cache-Control": "no-store"},
            )
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
                f"text='%{{pts\\:hms}}':box=1:boxcolor=black@0.4:boxborderw=5:{pos}"
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



# ── CMDB ──────────────────────────────────────────────────────────────────
app.include_router(import_router, prefix="/api/import")
app.include_router(siem_router, prefix="/api/siem")
app.include_router(cmdb_router, prefix="/api/cmdb")
app.include_router(itim_router, prefix="/api/itim")
app.include_router(settings_router)

@app.post("/api/inventory/{device_id}")
def edge_report_inventory(
    device_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    _auth: None = Depends(_verify_device_token),
):
    return _cmdb_report_inventory(device_id=device_id, payload=payload, db=db)


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "time": now_utc().isoformat()}


@app.post("/api/admin/restart-headend")
def restart_headend(_auth=require_role("admin", "super_admin")):
    """Genstart headend-processen via launchd. Kræver admin-rolle."""
    import subprocess, threading
    def _do_restart():
        import time; time.sleep(1)
        subprocess.run(["/bin/launchctl", "kickstart", "-k",
                        "system/dk.froekjaer.timelapse-headend"], check=False)
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"status": "restarting", "message": "Headend genstarter om ~1 sekund"}


@app.get("/api/time")
def api_time():
    """Tidssynkronisering for edge-noder uden GPS eller internetadgang.
    Returnerer headendens UTC-tid — bruges af edge som NTP-fallback.
    Ingen autentificering krævet (tid er ikke fortrolig).
    """
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(),
        "unix": now.timestamp(),
        "source": "headend",
    }

from pathlib import Path as _Path
from fastapi.responses import FileResponse
def _sftp_base_path(db: Session | None = None) -> _Path:
    """Canonical image root. DB setting wins, so NAS mount changes do not require restart."""
    fallback = os.getenv("SFTP_BASE", "/Volumes/data-fast")
    if db is not None:
        return _Path(_get_setting(db, "sftp_base", fallback)).expanduser()
    local_db = SessionLocal()
    try:
        return _Path(_get_setting(local_db, "sftp_base", fallback)).expanduser()
    finally:
        local_db.close()


def _configured_storage_roots(db: Session | None = None) -> list[_Path]:
    """Primary image root plus optional legacy/search roots for NAS migrations."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        roots = [_sftp_base_path(db)]
        raw = _get_setting(db, "sftp_legacy_roots", os.getenv("SFTP_LEGACY_ROOTS", ""))
        for item in _re.split(r"[\n,]+", raw or ""):
            item = item.strip()
            if item:
                roots.append(_Path(item).expanduser())
        deduped: list[_Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root)
            if key not in seen:
                seen.add(key)
                deduped.append(root)
        return deduped
    finally:
        if close_db:
            db.close()

#Peter import re as _re

@_functools.lru_cache(maxsize=100_000)
def _find_image_cached(device_id: str, filename: str, roots_key: tuple[str, ...]) -> str:
    """
    Find image — håndterer flere strukturer:
      1. Canonical data root: SFTP_BASE/{customer}/{site}/{camera}/YYYY/MM/DD/filename
      2. Legacy chroot:      SFTP_BASE/timelapse-incoming/{sftp_user}/data/{customer}/{site}/{camera}/YYYY/MM/DD/filename
      3. Legacy site:        SFTP_BASE/{customer}/{site}/YYYY/MM/DD/filename
      4. Flad/device:        SFTP_BASE/{device_id}/filename eller SFTP_BASE/{device_id}/YYYY/MM/DD/filename
    """
    m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    for root in roots_key:
        sftp_base = _Path(root)
        if m:
            yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
            date_parts = [(yyyy, mm, dd)]
            try:
                filename_day = datetime(int(yyyy), int(mm), int(dd))
                for delta_days in (-1, 1):
                    adjacent = filename_day + timedelta(days=delta_days)
                    adjacent_parts = (f"{adjacent.year:04d}", f"{adjacent.month:02d}", f"{adjacent.day:02d}")
                    if adjacent_parts not in date_parts:
                        date_parts.append(adjacent_parts)
            except Exception:
                pass

            for yyyy, mm, dd in date_parts:

                # Struktur 1 — canonical: customer/site/camera/YYYY/MM/DD/
                canonical_glob = f"*/*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(canonical_glob))
                if matches:
                    return str(matches[0])

                # Struktur 2 — legacy chroot under timelapse-incoming/sftp_user/data/
                legacy_chroot_glob = f"timelapse-incoming/*/data/*/*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(legacy_chroot_glob))
                if matches:
                    return str(matches[0])

                legacy_site_chroot_glob = f"timelapse-incoming/*/data/*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(legacy_site_chroot_glob))
                if matches:
                    return str(matches[0])

                # Struktur 3 — gammel hierarkisk: customer/site/YYYY/MM/DD/
                old_glob = f"*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(old_glob))
                if matches:
                    return str(matches[0])

                # Struktur 4 — device_id/YYYY/MM/DD/
                p = sftp_base / device_id / yyyy / mm / dd / filename
                if p.exists():
                    return str(p)

        # Flad struktur sftp_base/device_id/filename
        flat = sftp_base / device_id / filename
        if flat.exists():
            return str(flat)

    # Sidste udvej. Rekursiv søgning på NAS-roots er dyr og kan gøre
    # thumbnail-grids meget langsomme, så den er opt-in når strukturerne ovenfor
    # ikke dækker en særlig import.
    if os.getenv("TIMELAPSE_IMAGE_R_GLOB_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}:
        for root in roots_key:
            matches = list(_Path(root).rglob(filename))
            if matches:
                return str(matches[0])

    return ""


def _find_image(device_id: str, filename: str) -> Optional[_Path]:
    roots_key = tuple(str(root) for root in _configured_storage_roots())
    found = _find_image_cached(device_id, filename, roots_key)
    return _Path(found) if found else None

def _thumbs_dir_for(image_path: _Path) -> _Path:
    """Return .thumbs directory next to the image."""
    return image_path.parent / ".thumbs"


def _generated_thumbs_dir_for(image_path: _Path) -> _Path:
    """Return headend-owned fallback thumbnail directory."""
    return image_path.parent / ".headend-thumbs"


_thumbnail_generation_lock = _threading.Lock()
_thumbnail_generation_active: set[str] = set()


def _is_valid_jpeg(path: _Path) -> bool:
    try:
        if not path.exists() or path.stat().st_size < 256:
            return False
        if os.getenv("TIMELAPSE_STRICT_THUMBNAIL_VERIFY", "0").lower() in {"1", "true", "yes"}:
            from PIL import Image
            with Image.open(path) as existing:
                existing.verify()
        return True
    except Exception:
        return False


def _thumbnail_candidates_for(image_path: _Path) -> list[_Path]:
    stem = image_path.stem
    suffix = image_path.suffix or ".jpg"
    return [
        image_path.parent / ".thumbs" / image_path.name,
        image_path.parent / ".headend-thumbs" / image_path.name,
        image_path.parent / "thumbs" / image_path.name,
        image_path.parent / "thumbnails" / image_path.name,
        image_path.parent / f"thumb_{image_path.name}",
        image_path.parent / f"thumbnail_{image_path.name}",
        image_path.parent / f"{stem}_thumb{suffix}",
        image_path.parent / f"{stem}.thumb{suffix}",
    ]


def _find_existing_thumbnail(image_path: _Path) -> _Path | None:
    for candidate in _thumbnail_candidates_for(image_path):
        if _is_valid_jpeg(candidate):
            return candidate
    return None


def _generate_edge_thumbnail(src: _Path, thumb: _Path) -> tuple[bool, str | None]:
    key = str(thumb)
    try:
        from PIL import Image, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = os.getenv("TIMELAPSE_THUMBNAIL_ALLOW_TRUNCATED", "true").lower() in {"1", "true", "yes", "on"}
        thumb.parent.mkdir(parents=True, exist_ok=True)
        tmp_thumb = thumb.parent / f".{thumb.name}.{_secrets.token_hex(8)}.tmp"
        try:
            with Image.open(src) as original:
                img = original.convert("RGB")
                img.thumbnail((320, 180), Image.LANCZOS)
                canvas = Image.new("RGB", (320, 180), (15, 15, 15))
                offset = ((320 - img.width) // 2, (180 - img.height) // 2)
                canvas.paste(img, offset)
                canvas.save(str(tmp_thumb), "JPEG", quality=78)
            os.replace(tmp_thumb, thumb)
            log.info("Thumbnail repair generated: %s", thumb)
            return True, None
        finally:
            tmp_thumb.unlink(missing_ok=True)
    except Exception as exc:
        error = str(exc)
        log.warning("Thumbnail repair failed for %s: %s", src, error)
        return False, error
    finally:
        with _thumbnail_generation_lock:
            _thumbnail_generation_active.discard(key)


# Global samtidigheds-grænse for thumbnail-generering. Beskytter data-fast mod
# "thundering herd": et galleri med mange manglende thumbnails fyrede før 100+
# samtidige genereringer (hver læser et fuldopløst billede) → volumenet druknede
# og de fleste timeout'ede. Nu serialiseres de til N ad gangen.
_thumb_gen_semaphore = _threading.BoundedSemaphore(
    int(os.getenv("TIMELAPSE_THUMBNAIL_GEN_CONCURRENCY", "3")))


def _bounded_generate_thumbnail(src: _Path, thumb: _Path) -> tuple[bool, str | None]:
    """_generate_edge_thumbnail med global samtidigheds-grænse."""
    acquired = _thumb_gen_semaphore.acquire(
        timeout=float(os.getenv("TIMELAPSE_THUMBNAIL_GEN_TIMEOUT_S", "20")))
    if not acquired:
        with _thumbnail_generation_lock:
            _thumbnail_generation_active.discard(str(thumb))
        return False, "concurrency_limit"
    try:
        return _generate_edge_thumbnail(src, thumb)
    finally:
        _thumb_gen_semaphore.release()


def _lazy_generate_thumbnail(src: _Path) -> _Path | None:
    """Generér en manglende thumbnail synkront (cachet i .headend-thumbs/) når
    galleriet beder om den — så `get_thumbnail` kan returnere 200 i stedet for 404.
    Samtidigheds-begrænset, så en stor side ikke presser data-fast."""
    target = _generated_thumbs_dir_for(src) / src.name
    if _is_valid_jpeg(target):
        return target
    ok, _err = _bounded_generate_thumbnail(src, target)
    return target if (ok and _is_valid_jpeg(target)) else None


def _unlink_thumbnail_variants(image_path: _Path, filename: str) -> bool:
    deleted = False
    for directory in (_thumbs_dir_for(image_path), _generated_thumbs_dir_for(image_path)):
        try:
            thumb = directory / filename
            if thumb.exists():
                thumb.unlink(missing_ok=True)
                deleted = True
        except Exception as exc:
            log.warning("Kunne ikke slette thumbnail i %s: %s", directory, exc)
    return deleted


def _xaccel_redirect(path: _Path, media_type: str, cache_control: str = ""):
    """X-Accel-Redirect: lad NGINX selv sende filen, så uvicorn-workeren frigøres
    straks (fjerner thumbnail-serverings-loftet — billeder streames ikke længere
    gennem Python pr. request). Auth + sti-resolution bliver i Python; kun selve
    fil-leveringen flyttes til nginx.

    DEFAULT SLÅET FRA. Aktiveres kun når BÅDE:
      - nginx har en intern location der matcher TIMELAPSE_XACCEL_PREFIX → alias mod
        TIMELAPSE_XACCEL_ROOT (se Codex_Thumbnail_503_Analyse_2026-06-30.md), OG
      - TIMELAPSE_THUMBNAIL_XACCEL=on
    Returnerer None hvis ikke konfigureret/anvendelig → kalderen falder tilbage til
    FileResponse (uændret adfærd), så Python-koden kan deployes FØR nginx er klar."""
    if os.getenv("TIMELAPSE_THUMBNAIL_XACCEL", "false").lower() not in {"1", "true", "yes", "on"}:
        return None
    root = os.getenv("TIMELAPSE_XACCEL_ROOT", "").rstrip("/")
    if not root:
        return None
    prefix = os.getenv("TIMELAPSE_XACCEL_PREFIX", "/_protected_media").rstrip("/")
    try:
        rel = path.resolve().relative_to(_Path(root).resolve())
    except (ValueError, OSError):
        return None
    from urllib.parse import quote
    from starlette.responses import Response as _Resp
    headers = {
        "X-Accel-Redirect": f"{prefix}/{quote(str(rel))}",
        "Content-Type": media_type,
    }
    if cache_control:
        headers["Cache-Control"] = cache_control
    return _Resp(status_code=200, headers=headers)


@app.get("/api/images/{device_id}/{filename}")
def get_image(
    device_id: str,
    filename: str,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    _ensure_capture_file_access(db, _user, device_id, filename)
    path = _find_image(device_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="Image not found")
    xr = _xaccel_redirect(path, "image/jpeg")
    if xr is not None:
        return xr
    return FileResponse(str(path), media_type="image/jpeg")

@app.get("/api/thumbnails/{device_id}/{filename}")
def get_thumbnail(
    device_id: str,
    filename: str,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    _ensure_capture_file_access(db, _user, device_id, filename)
    src = _find_image(device_id, filename)
    if not src:
        raise HTTPException(status_code=404, detail="Image not found")
    _thumb_cache = "public, max-age=604800, immutable"
    thumb = _find_existing_thumbnail(src)
    if thumb:
        xr = _xaccel_redirect(thumb, "image/jpeg", _thumb_cache)
        if xr is not None:
            return xr
        return FileResponse(
            str(thumb),
            media_type="image/jpeg",
            headers={
                "Cache-Control": _thumb_cache,
                "X-Thumbnail-Source": "edge",
            },
        )

    # Generér-ved-miss (selvhelende, samtidigheds-begrænset). Gated by flag, så
    # den kan slås fra hvis den nogensinde presser data-fast for hårdt.
    if os.getenv("TIMELAPSE_THUMBNAIL_LAZY_GENERATE", "true").lower() in {"1", "true", "yes", "on"}:
        generated = _lazy_generate_thumbnail(src)
        if generated:
            xr = _xaccel_redirect(generated, "image/jpeg", _thumb_cache)
            if xr is not None:
                return xr
            return FileResponse(
                str(generated),
                media_type="image/jpeg",
                headers={
                    "Cache-Control": _thumb_cache,
                    "X-Thumbnail-Source": "headend-lazy",
                },
            )

    raise HTTPException(
        status_code=404,
        detail="Thumbnail missing; Edge/backfill must generate and upload thumbnails",
    )


@app.post("/api/thumbnails/{device_id}/{filename}/generate")
def request_thumbnail_generation(
    device_id: str,
    filename: str,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    _ensure_capture_file_access(db, _user, device_id, filename)
    src = _find_image(device_id, filename)
    if not src:
        raise HTTPException(status_code=404, detail="Image not found")

    existing = _find_existing_thumbnail(src)
    if existing:
        return {"status": "ready", "source": "edge", "thumbnail": str(existing)}

    thumb = _thumbs_dir_for(src) / src.name
    key = str(thumb)
    with _thumbnail_generation_lock:
        if key in _thumbnail_generation_active:
            return {"status": "queued", "thumbnail": str(thumb)}
        _thumbnail_generation_active.add(key)

    _threading.Thread(target=_bounded_generate_thumbnail, args=(src, thumb), daemon=True).start()
    return {"status": "queued", "thumbnail": str(thumb)}


_post_processing_lock = _threading.Lock()
_post_processing_status: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "requested_by": None,
    "options": {},
    "total": 0,
    "processed": 0,
    "thumbnails_generated": 0,
    "thumbnails_existing": 0,
    "ai_queued": 0,
    "files_missing": 0,
    "errors": 0,
    "error_samples": [],
    "last_message": "Ingen kørsel startet",
    "ollama_warning": None,
    "ai_strategy": None,
}


def _post_processing_snapshot() -> dict:
    with _post_processing_lock:
        return dict(_post_processing_status)


def _post_processing_update(**values) -> None:
    with _post_processing_lock:
        _post_processing_status.update(values)


def _post_processing_error(message: str) -> None:
    with _post_processing_lock:
        _post_processing_status["errors"] = int(_post_processing_status.get("errors") or 0) + 1
        samples = list(_post_processing_status.get("error_samples") or [])
        if len(samples) < 25:
            samples.append(message)
        _post_processing_status["error_samples"] = samples


def _run_post_processing_job(options: dict, allowed_device_ids: list[str] | None, requested_by: str) -> None:
    from ai.integration import queue_capture_for_analysis

    db = SessionLocal()
    try:
        query = db.query(Capture.id).filter(Capture.filename.isnot(None))
        if allowed_device_ids is not None:
            if not allowed_device_ids:
                _post_processing_update(running=False, finished_at=now_utc().isoformat(), last_message="Ingen synlige enheder")
                return
            query = query.filter(Capture.device_id.in_(allowed_device_ids))
        if options.get("device_id"):
            query = query.filter(Capture.device_id == options["device_id"])
        query = query.order_by(Capture.captured_at.desc(), Capture.id.desc())
        if options.get("limit"):
            query = query.limit(int(options["limit"]))
        capture_ids = [row[0] for row in query.all()]
        _post_processing_update(total=len(capture_ids), last_message=f"Starter post-processing af {len(capture_ids)} billeder")

        for index, capture_id in enumerate(capture_ids, start=1):
            capture = db.query(Capture).filter(Capture.id == capture_id).first()
            if not capture:
                continue

            try:
                image_path = _find_image(capture.device_id, capture.filename)
                if not image_path:
                    _post_processing_status["files_missing"] += 1
                    _post_processing_update(processed=index, last_message=f"Mangler fil: {capture.filename}")
                    continue

                if options.get("thumbnails"):
                    thumb = _find_existing_thumbnail(image_path)
                    if thumb:
                        _post_processing_status["thumbnails_existing"] += 1
                    else:
                        target = _thumbs_dir_for(image_path) / image_path.name
                        ok, error = _generate_edge_thumbnail(image_path, target)
                        if ok and _is_valid_jpeg(target):
                            _post_processing_status["thumbnails_generated"] += 1
                        else:
                            _post_processing_error(f"Thumbnail fejlede for {capture.filename}: {error or 'ukendt fejl'}")

                if options.get("ai"):
                    should_queue = options.get("force_ai") or not capture.ai_result or not capture.ai_tags
                    if should_queue:
                        if options.get("force_ai"):
                            capture.ai_result = None
                            capture.ai_tags = None
                            capture.ai_analyzed_at = None
                            # Commit ØJEBLIKKELIGT — ikke kun hver 25. — fordi
                            # AI-workeren bruger en separat DB-forbindelse og
                            # tjekker "if capture.ai_result: skip" når den
                            # behandler køen. Uden dette commit her ser workeren
                            # stadig det GAMLE (ikke-nulstillede) resultat og
                            # springer billedet over, selvom force_ai er valgt.
                            db.commit()
                        queued_ok = queue_capture_for_analysis(capture.id)
                        if queued_ok:
                            _post_processing_status["ai_queued"] += 1
                        else:
                            _post_processing_error(f"AI-kø fuld: {capture.filename}")
                            _post_processing_update(last_message=f"AI-kø fuld — {capture.filename} sprunget over")

                if index % 25 == 0:
                    db.commit()
                _post_processing_update(processed=index, last_message=f"Behandler {index}/{len(capture_ids)}")
            except Exception as exc:
                db.rollback()
                _post_processing_error(f"Fejl ved {capture.filename}: {exc}")
                _post_processing_update(processed=index, last_message=f"Fejl ved {capture.filename}: {exc}")

        db.commit()
        _post_processing_update(
            running=False,
            finished_at=now_utc().isoformat(),
            processed=len(capture_ids),
            last_message="Post-processing færdig",
        )
    except Exception as exc:
        db.rollback()
        _post_processing_update(
            running=False,
            finished_at=now_utc().isoformat(),
            errors=_post_processing_status.get("errors", 0) + 1,
            last_message=f"Post-processing stoppede med fejl: {exc}",
        )
    finally:
        db.close()


@app.get("/api/admin/post-processing/status")
def post_processing_status(_user=require_role("admin")):
    return _post_processing_snapshot()


@app.post("/api/admin/post-processing/start")
def start_post_processing(payload: dict, current_user=require_role("admin"), db: Session = Depends(get_db)):
    thumbnails = bool(payload.get("thumbnails", True))
    ai = bool(payload.get("ai", False))
    force_ai = bool(payload.get("force_ai", False))
    limit_raw = payload.get("limit")
    limit = None
    if limit_raw not in (None, "", 0, "0"):
        limit = max(1, int(limit_raw))  # ingen øvre grænse — "0"/tom = alle billeder
    device_id = str(payload.get("device_id") or "").strip() or None
    if device_id:
        _ensure_capture_device_access(db, current_user, device_id)

    if not thumbnails and not ai:
        raise HTTPException(status_code=400, detail="Vælg thumbnails og/eller AI")

    # Advar synligt hvis AI er valgt, men den konfigurerede strategi reelt ikke
    # kan analysere noget lige nu — fx Ollama nede (når strategien bruger lokal
    # model) eller manglende Gemini-credentials (når strategien bruger cloud).
    # cloud_only kræver IKKE Ollama — kun Open WebUI-prioritet og selve
    # strategien afgør om Ollama-status er relevant.
    ollama_warning = None
    ai_strategy = None
    if ai:
        try:
            from ai.integration import _open_webui_priority_enabled
            from ai.ai_strategy import AIConfigManager
            from ai.settings_helper import get_setting as _ai_get_setting

            default_cfg = AIConfigManager(db).get_config(customer_id=None, site_id=None)
            ai_strategy = default_cfg.strategy

            if _open_webui_priority_enabled(get_db):
                ollama_warning = "⚠ Open WebUI-prioritet er aktiveret — AI-analyse er PAUSET indtil den slås fra"
            elif default_cfg.strategy == "local_only":
                from ai.ollama_service import OllamaVisionService
                if not OllamaVisionService().health_check():
                    ollama_warning = "⚠ Ollama svarer ikke (strategi: local_only) — billeder bliver køet, men ikke analyseret"
            elif default_cfg.strategy == "cloud_only":
                has_gemini = bool(_ai_get_setting(db, "gemini_api_key") or _ai_get_setting(db, "gemini_service_account_path"))
                if not has_gemini:
                    ollama_warning = "⚠ Strategi er cloud_only, men ingen Gemini API-nøgle er konfigureret — billeder bliver køet, men ikke analyseret"
            elif default_cfg.strategy == "local_then_cloud":
                from ai.ollama_service import OllamaVisionService
                if not OllamaVisionService().health_check():
                    ollama_warning = "⚠ Ollama svarer ikke (strategi: local_then_cloud) — kun cloud-eskalering vil virke"
        except Exception:
            pass

    with _post_processing_lock:
        if _post_processing_status.get("running"):
            raise HTTPException(status_code=409, detail="Post-processing kører allerede")
        _post_processing_status.update({
            "running": True,
            "started_at": now_utc().isoformat(),
            "finished_at": None,
            "requested_by": current_user.username,
            "options": {
                "thumbnails": thumbnails,
                "ai": ai,
                "force_ai": force_ai,
                "limit": limit,
                "device_id": device_id,
            },
            "total": 0,
            "processed": 0,
            "thumbnails_generated": 0,
            "thumbnails_existing": 0,
            "ai_queued": 0,
            "files_missing": 0,
            "errors": 0,
            "error_samples": [],
            "last_message": "Kø starter",
            "ollama_warning": ollama_warning,
            "ai_strategy": ai_strategy,
        })

    # NB (Fase 3, 2026-07-03): denne liste bruges kun til at afgrænse HVILKE devices
    # baggrundsjobbet må behandle (postprocessing/AI-kø), ikke til at eksponere
    # billeddata direkte til brugeren. customer_id-først-tenant-filtret fra
    # _capture_tenant_clause()/_capture_is_allowed() er bevidst IKKE rullet ind i selve
    # baggrundsjobbet i denne omgang — se Claude_Kritisk_Statusgennemgang_2026-07-03.md
    # §6 for scope-begrundelse (lav konfidentialitetsrisiko: jobbet skriver kun
    # afledte metadata/tags tilbage på egne synlige devices, eksponerer intet billede).
    allowed_device_ids = _allowed_capture_device_ids(db, current_user)
    allowed_list = list(allowed_device_ids) if allowed_device_ids is not None else None
    options = {
        "thumbnails": thumbnails,
        "ai": ai,
        "force_ai": force_ai,
        "limit": limit,
        "device_id": device_id,
    }
    _threading.Thread(
        target=_run_post_processing_job,
        args=(options, allowed_list, current_user.username),
        daemon=True,
    ).start()
    return _post_processing_snapshot()


# ── Gemini Batch API — bulk AI-genanalyse til ~50% af normal pris ────────────
# Asynkront spor, separat fra den synkrone post-processing-kø ovenfor.
# Bruges KUN ved eksplicit anmodning — aldrig automatisk, og påvirker ikke
# den løbende live capture-pipeline.

@app.post("/api/admin/ai-batch/start")
def start_ai_batch_job(
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Start et Gemini Batch-job — vælger captures efter samme kriterier som
    post-processing (device_id, limit, force_ai), men sender dem som ÉT
    asynkront batch-job til Google i stedet for den synkrone live-kø.
    """
    force_ai = bool(payload.get("force_ai", False))
    limit_raw = payload.get("limit")
    limit = max(1, int(limit_raw)) if limit_raw not in (None, "", 0, "0") else None
    device_id = str(payload.get("device_id") or "").strip() or None
    notify_on_complete = bool(payload.get("notify_on_complete", True))

    if device_id:
        _ensure_capture_device_access(db, current_user, device_id)

    from ai.ai_strategy import AIConfigManager
    cfg = AIConfigManager(db).get_config(customer_id=None, site_id=None)
    if not cfg.use_cloud:
        raise HTTPException(
            status_code=400,
            detail="Batch-mode kræver cloud_only eller local_then_cloud strategi (Gemini) — nuværende strategi bruger ikke cloud"
        )

    from ai.integration import _build_gemini_service
    svc = _build_gemini_service(get_db, cfg.cloud_model)
    if not svc:
        raise HTTPException(status_code=400, detail="Ingen Gemini API-nøgle konfigureret (Indstillinger → AI)")

    gcs_bucket = ""
    if getattr(svc, "is_vertex", False):
        gcs_bucket = _get_setting(db, "gemini_gcs_bucket", "").strip()
        if not gcs_bucket:
            raise HTTPException(
                status_code=400,
                detail="Vertex AI batch kræver et GCS-bucket — sæt 'gemini_gcs_bucket' i Indstillinger → AI"
            )
        # GDPR: bucket SKAL ligge i samme EU-region som Vertex-endpointet, ellers
        # brydes databehandlings-garantien på data-at-rest under batch-kørslen.
        bucket_region = _get_setting(db, "gemini_gcs_bucket_region", "").strip().lower()
        vertex_region = (svc.location or "").lower()
        if bucket_region and vertex_region and not bucket_region.startswith(vertex_region.split("-")[0]):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"GCS-bucket region ({bucket_region}) matcher ikke Vertex AI region ({vertex_region}) — "
                    "stoppet for at undgå databehandling uden for EU. Bekræft 'gemini_gcs_bucket_region' i Indstillinger → AI."
                )
            )

    # NB (Fase 3, 2026-07-03): samme scope-afgrænsning som post-processing-jobbet
    # ovenfor — se den note for begrundelse.
    allowed_device_ids = _allowed_capture_device_ids(db, current_user)
    if allowed_device_ids is not None and not allowed_device_ids:
        raise HTTPException(status_code=400, detail="Ingen synlige enheder")
    allowed_list = list(allowed_device_ids) if allowed_device_ids is not None else None

    # Opret job-rækken med det samme (status=submitting) og returnér STRAKS.
    # Det tunge arbejde — find filer, byg kontekst pr. billede, base64-encode og
    # upload hele JSONL'en til Google — kan tage minutter for 26.000 billeder og
    # ville ellers ramme nginx' 60s timeout (504). Det kører nu i en baggrundstråd,
    # og UI'et følger status via /api/admin/ai-batch/jobs.
    job_id = str(_uuid.uuid4())
    db.add(AiBatchJob(
        id=job_id, gemini_job_name=None, status="submitting",
        capture_ids="[]", cloud_model=cfg.cloud_model, total_count=0,
        requested_by=current_user.username, notify_on_complete=notify_on_complete,
        submitted_at=now_utc(),
    ))
    db.commit()

    _cloud_model = cfg.cloud_model
    _username = current_user.username

    def _submit_ai_batch_bg():
        from database import Capture as _Cap, Device as _Dev
        from ai.capture_context import build_capture_context, format_context_block
        from ai.tag_vocabulary import TagVocabulary
        bg_gen = get_db(); bg = next(bg_gen)
        try:
            svc2 = _build_gemini_service(get_db, _cloud_model)
            if not svc2:
                raise RuntimeError("Ingen Gemini-credentials")
            q = bg.query(_Cap).filter(_Cap.filename.isnot(None))
            if allowed_list is not None:
                q = q.filter(_Cap.device_id.in_(allowed_list))
            if device_id:
                q = q.filter(_Cap.device_id == device_id)
            if not force_ai:
                q = q.filter(or_(_Cap.ai_result.is_(None), _Cap.ai_tags.is_(None)))
            q = q.order_by(_Cap.captured_at.desc(), _Cap.id.desc())
            if limit:
                q = q.limit(limit)
            caps = q.all()

            items = []; missing = 0; ctx_by_key = {}; dev_cache = {}
            for cap in caps:
                path = _find_image(cap.device_id, cap.filename)
                if not path:
                    missing += 1; continue
                key = f"cap-{cap.id}"
                items.append((key, path, cap.id))
                try:
                    dev = dev_cache.get(cap.device_id)
                    if dev is None:
                        dev = bg.query(_Dev).filter_by(device_id=cap.device_id).first()
                        dev_cache[cap.device_id] = dev
                    ctx_by_key[key] = format_context_block(build_capture_context(bg, cap, dev))
                except Exception:
                    ctx_by_key[key] = ""

            if not items:
                bg.query(AiBatchJob).filter_by(id=job_id).update(
                    {"status": "failed", "error_message": "Ingen af billederne findes på disk"})
                bg.commit(); return

            vocab_by_cat = TagVocabulary(get_db).get_approved_by_category()
            job_name = svc2.submit_batch_job(
                items=[(k, p) for k, p, _c in items],
                vocabulary_by_cat=vocab_by_cat,
                display_name=f"timelapse-batch-{job_id[:8]}",
                gcs_bucket=gcs_bucket,
                context_by_key=ctx_by_key,
            )
            bg.query(AiBatchJob).filter_by(id=job_id).update({
                "gemini_job_name": job_name, "status": "submitted",
                "capture_ids": _json.dumps([c for _k, _p, c in items]),
                "total_count": len(items),
            })
            bg.commit()
            log.info("AI batch-job startet (baggrund): %s (%d billeder, %d manglede) af %s",
                     job_name, len(items), missing, _username)
        except Exception as exc:
            log.exception("AI batch-job (baggrund) fejlede")
            try:
                bg.query(AiBatchJob).filter_by(id=job_id).update(
                    {"status": "failed", "error_message": str(exc)[:500]})
                bg.commit()
            except Exception:
                pass
        finally:
            bg_gen.close()

    _threading.Thread(target=_submit_ai_batch_bg, daemon=True,
                      name=f"ai-batch-submit-{job_id[:8]}").start()
    return {
        "id": job_id, "status": "submitting",
        "message": "Batch-job oprettes i baggrunden — følg status under AI-batch jobs.",
    }


@app.get("/api/admin/ai-batch/jobs")
def list_ai_batch_jobs(
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db),
):
    """List de seneste 50 batch-jobs — til UI-oversigt."""
    jobs = db.query(AiBatchJob).order_by(AiBatchJob.created_at.desc()).limit(50).all()
    return [{
        "id": j.id,
        "gemini_job_name": j.gemini_job_name,
        "status": j.status,
        "total_count": j.total_count,
        "success_count": j.success_count,
        "error_count": j.error_count,
        "requested_by": j.requested_by,
        "cloud_model": j.cloud_model,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "submitted_at": j.submitted_at.isoformat() if j.submitted_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "error_message": j.error_message,
    } for j in jobs]


_BATCH_RUNNING_STATES = {"PENDING", "RUNNING", "JOB_STATE_PENDING", "JOB_STATE_RUNNING"}
_BATCH_SUCCESS_STATES = {"SUCCEEDED", "JOB_STATE_SUCCEEDED"}
_BATCH_FAILED_STATES  = {"FAILED", "JOB_STATE_FAILED"}
_BATCH_CANCELLED_STATES = {"CANCELLED", "JOB_STATE_CANCELLED"}
_BATCH_EXPIRED_STATES = {"EXPIRED", "JOB_STATE_EXPIRED"}


def _notify_batch_job(db, job: "AiBatchJob", status: str) -> None:
    if not job.notify_on_complete:
        return
    try:
        from ai.notify import notify_batch_complete
        duration_min = 0.0
        if job.submitted_at and job.completed_at:
            duration_min = (job.completed_at - job.submitted_at).total_seconds() / 60
        notify_batch_complete(db, {
            "status": status,
            "total": job.total_count,
            "success": job.success_count,
            "errors": job.error_count,
            "model": job.cloud_model,
            "requested_by": job.requested_by,
            "duration_min": duration_min,
        })
    except Exception as exc:
        log.debug("Batch notifikation fejl (ikke kritisk): %s", exc)


def _finalize_ai_batch_job(db, job: "AiBatchJob", svc, gemini_job) -> None:
    """Download og skriv resultater fra et succeeded batch-job tilbage til captures."""
    from ai.tag_vocabulary import TagVocabulary
    vocab = TagVocabulary(get_db)
    approved_set = set(vocab.get_approved_tags())

    try:
        results = svc.download_batch_results(gemini_job)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Resultat-download fejlede: {exc}"
        job.completed_at = now_utc()
        db.commit()
        _notify_batch_job(db, job, "failed")
        log.warning("Batch-job %s: download fejlede: %s", job.gemini_job_name, exc)
        return

    # AI Studio-jobs har "key" (fx "cap-123") i hvert resultat — match direkte.
    # Vertex-jobs har INGEN key (Vertex-konventionen er anderledes) — match i
    # stedet POSITIONELT mod capture_ids i den rækkefølge de blev submittet i,
    # da Vertex AI batch garanteret bevarer input-rækkefølgen i output.
    job_capture_ids = json.loads(job.capture_ids or "[]")
    uses_positional_matching = bool(results) and all(r.get("key") is None for r in results)
    if uses_positional_matching and len(results) != len(job_capture_ids):
        log.warning(
            "Batch-job %s: antal resultater (%d) matcher ikke antal submittede billeder (%d) — "
            "positionel matching kan være forskudt. Springer over for at undgå fejlmatch.",
            job.gemini_job_name, len(results), len(job_capture_ids),
        )

    success_count = 0
    error_count = 0
    for index, r in enumerate(results):
        if uses_positional_matching:
            if len(results) != len(job_capture_ids) or index >= len(job_capture_ids):
                error_count += 1
                continue
            capture_id = job_capture_ids[index]
        else:
            key = r.get("key") or ""
            if not key.startswith("cap-"):
                continue
            try:
                capture_id = int(key[len("cap-"):])
            except ValueError:
                continue
        capture = db.query(Capture).filter_by(id=capture_id).first()
        if not capture:
            continue
        if r.get("error") or not r.get("text"):
            error_count += 1
            continue
        try:
            result = svc.parse_batch_result_text(r["text"], approved_set)
            ai_payload = {
                "scene_dk": result.scene_dk,
                "tags": result.approved_tags,
                "new_tags": result.new_tags,
                "new_tags_da": getattr(result, "new_tags_da", {}),
                "change_detected": result.change_detected,
                "change_summary": result.change_summary,
                "change_tags": result.change_tags,
                "quality_flag": result.quality_flag,
                "quality_ok": result.quality_ok,
                "has_gdpr_data": result.has_gdpr_data,
                "gdpr_detections": [
                    {"type": g.detection_type, "detail": g.detail, "bbox": g.bounding_box}
                    for g in result.gdpr_detections
                ],
                "model": job.cloud_model,
                "duration_ms": result.duration_ms,
                "raw_response": result.raw_response,
            }
            # Bevar evt. eksisterende edge-QA under 'edge_ai', så batch-Gemini ikke
            # sletter den (samme som live-workeren gør).
            if capture.ai_result and "edge_ai" not in ai_payload:
                try:
                    _prev = _json.loads(capture.ai_result)
                    _edge_prev = _prev.get("edge_ai") if isinstance(_prev.get("edge_ai"), dict) else None
                    if _edge_prev:
                        ai_payload["edge_ai"] = _edge_prev
                    elif _prev.get("source") == "edge":
                        ai_payload["edge_ai"] = _prev
                except Exception:
                    pass
            tags = result.approved_tags + result.new_tags
            capture.ai_result = _json.dumps(ai_payload, ensure_ascii=False)
            capture.ai_tags = _json.dumps(tags, ensure_ascii=False)
            capture.ai_analyzed_at = now_utc()
            # Registrér brug + nye tags til godkendelse — manglede helt før denne fix,
            # så batch-opdagede tags forsvandt i stedet for at lande i Tag Review.
            vocab.record_usage(result.approved_tags, result.new_tags, getattr(result, "new_tags_da", None))
            success_count += 1
        except Exception as exc:
            log.warning("Batch resultat-parse fejl for capture %d: %s", capture_id, exc)
            error_count += 1

    db.commit()
    job.status = "succeeded"
    job.success_count = success_count
    job.error_count = error_count
    job.completed_at = now_utc()
    db.commit()
    log.info("AI batch-job %s færdig: %d ok, %d fejl", job.gemini_job_name, success_count, error_count)
    _notify_batch_job(db, job, "succeeded")


def _poll_one_ai_batch_job(db, job: "AiBatchJob") -> None:
    from ai.integration import _build_gemini_service
    svc = _build_gemini_service(get_db, job.cloud_model or "gemini-2.5-flash")
    if not svc:
        return
    try:
        status = svc.get_batch_status(job.gemini_job_name)
    except Exception as exc:
        log.warning("Kunne ikke hente batch-status %s: %s", job.gemini_job_name, exc)
        return

    state = status["state"]
    if state in _BATCH_RUNNING_STATES:
        changed = False
        if job.status != "running":
            job.status = "running"
            changed = True
        # Skriv løbende fremdrift hjem (Vertex completion_stats) → UI viser X/total %.
        prog = status.get("progress") or {}
        if prog:
            s = int(prog.get("success") or 0)
            e = int(prog.get("error") or 0)
            if job.success_count != s:
                job.success_count = s; changed = True
            if job.error_count != e:
                job.error_count = e; changed = True
        if changed:
            db.commit()
        return
    if state in _BATCH_SUCCESS_STATES:
        _finalize_ai_batch_job(db, job, svc, status["job"])
    elif state in _BATCH_FAILED_STATES:
        job.status = "failed"
        job.error_message = str(getattr(status["job"], "error", "ukendt fejl"))
        job.completed_at = now_utc()
        db.commit()
        _notify_batch_job(db, job, "failed")
    elif state in _BATCH_CANCELLED_STATES:
        job.status = "cancelled"
        job.completed_at = now_utc()
        db.commit()
    elif state in _BATCH_EXPIRED_STATES:
        job.status = "expired"
        job.error_message = "Job udløb efter 48 timer hos Google"
        job.completed_at = now_utc()
        db.commit()
        _notify_batch_job(db, job, "failed")


def _ai_batch_poller_loop(interval_minutes: float = 5.0) -> None:
    """Baggrundstråd — poller alle igangværende batch-jobs periodisk.
    Et job kan tage op til 24 timer hos Google, så hyppig polling er ufarlig
    (billig API-kald) men sjælden nok til ikke at spamme.
    """
    import time as _time_mod
    log.info("AI batch-job poller startet (interval=%.0fm)", interval_minutes)
    while True:
        try:
            db = SessionLocal()
            try:
                pending = db.query(AiBatchJob).filter(
                    AiBatchJob.status.in_(["submitted", "running"])
                ).all()
                for job in pending:
                    try:
                        _poll_one_ai_batch_job(db, job)
                    except Exception as exc:
                        log.warning("Fejl ved polling af batch-job %s: %s", job.gemini_job_name, exc)
            finally:
                db.close()
        except Exception as exc:
            log.warning("AI batch poller-loop fejl: %s", exc)
        _time_mod.sleep(interval_minutes * 60)


# ── Kamera-laboratorium endpoints ─────────────────────────────────────────────

@app.put("/api/admin/devices/{device_id}/debug")
def set_debug_mode(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Enable or disable debug/lab mode for a device."""
    _ensure_capture_device_access(db, _user, device_id)
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

    device.device_config = json.dumps(existing, ensure_ascii=False)
    device.config_version = hashlib.md5(device.device_config.encode()).hexdigest()
    db.commit()
    log.info("Debug mode %s for %s", "ENABLED" if enabled else "DISABLED", device_id)
    return {"status": "ok", "device_id": device_id, "debug_mode": existing["debug_mode"]}


@app.post("/api/lab/{device_id}/relay")
def toggle_relay(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Toggle relay TIL/FRA — bruges af SystemAdminPage til test."""
    _ensure_capture_device_access(db, _user, device_id)
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
def request_preview(device_id: str, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Request a preview capture from the device (no shutter count)."""
    _ensure_capture_device_access(db, _user, device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    # Set a pending_preview flag in device_config
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "preview", "requested_at": now_utc().isoformat()}
    existing.pop("lab_result", None)
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "preview"}


@app.post("/api/lab/{device_id}/capture")
def request_capture(device_id: str, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Request a full-resolution capture from the device."""
    _ensure_capture_device_access(db, _user, device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "capture", "requested_at": now_utc().isoformat()}
    existing.pop("lab_result", None)
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "capture"}


@app.post("/api/lab/{device_id}/set-param")
def set_camera_param(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Set a camera parameter on the device (queued for next poll)."""
    _ensure_capture_device_access(db, _user, device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    key   = payload.get("key")
    value = payload.get("value")
    if not key or value is None:
        raise HTTPException(status_code=400, detail="key and value required")
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {
        "type": "set_param",
        "key": str(key),
        "value": str(value),
        "requested_at": now_utc().isoformat(),
    }
    existing.pop("lab_result", None)
    device.device_config = json.dumps(existing, ensure_ascii=False)
    db.commit()
    return {"status": "ok", "key": key, "value": value}


def _queue_lab_command(device_id: str, command: dict, db: Session) -> dict:
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {
        **command,
        "requested_at": now_utc().isoformat(),
    }
    existing.pop("lab_result", None)
    device.device_config = json.dumps(existing, ensure_ascii=False)
    db.commit()
    return {"status": "ok", "command": existing["lab_command"]}


@app.post("/api/lab/{device_id}/focus-drive")
def lab_focus_drive(
    device_id: str,
    payload: dict,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Queue exact remote-focus motor command from camera choices."""
    _ensure_capture_device_access(db, _user, device_id)
    value = str(payload.get("value") or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="value required")
    return _queue_lab_command(device_id, {"type": "focus_drive", "value": value}, db)


@app.post("/api/lab/{device_id}/autofocus")
def lab_autofocus(
    device_id: str,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Queue autofocus and quality verification preview."""
    _ensure_capture_device_access(db, _user, device_id)
    return _queue_lab_command(device_id, {"type": "autofocus"}, db)


@app.post("/api/lab/{device_id}/focus-slice")
def lab_focus_slice(
    device_id: str,
    payload: dict,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Queue focus slicing test with local edge quality scoring."""
    _ensure_capture_device_access(db, _user, device_id)
    step_value = str(payload.get("step_value") or "").strip()
    count = max(1, min(12, int(payload.get("count", 5))))
    if not step_value:
        raise HTTPException(status_code=400, detail="step_value required")
    return _queue_lab_command(device_id, {
        "type": "focus_slice",
        "step_value": step_value,
        "count": count,
        "run_autofocus_first": bool(payload.get("run_autofocus_first", True)),
    }, db)


@app.post("/api/lab/{device_id}/edge-ai-focus-test")
def lab_edge_ai_focus_test(
    device_id: str,
    payload: dict,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Queue daily-style edge focus quality test. Uses local deterministic vision metrics first."""
    _ensure_capture_device_access(db, _user, device_id)
    step_value = str(payload.get("step_value") or "").strip()
    count = max(1, min(12, int(payload.get("count", 3))))
    if not step_value:
        raise HTTPException(status_code=400, detail="step_value required")
    return _queue_lab_command(device_id, {
        "type": "edge_ai_focus_test",
        "step_value": step_value,
        "count": count,
        "run_autofocus_first": True,
    }, db)


@app.post("/api/lab/{device_id}/result")
def lab_store_result(
    device_id: str,
    payload: dict,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    """Edge poster LAB command result to headend."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["lab_result"] = {
        **payload,
        "received_at": now_utc().isoformat(),
    }
    existing.pop("lab_command", None)
    device.device_config = json.dumps(existing, ensure_ascii=False)
    device.last_seen = now_utc()
    db.commit()
    return {"status": "ok"}


# ── Backup ────────────────────────────────────────────────────────────────────

#Peter import subprocess as _subprocess
#Peter import threading as _threading
import tempfile as _tempfile
import shutil as _shutil
from fastapi.responses import FileResponse as _FileResponse

# ── AI INTEGRATION ──────────────────────────────────────────────────────────
from ai.integration import (
    run_ai_migration,
    setup_ai,
    setup_ai_router,
    queue_capture_for_analysis,
    ai_router,
)


_backup_status = {"running": False, "progress": [], "file": None, "error": None}
_backup_lock = _threading.Lock()

def _run_backup_archive(reason: str = "manual", extra_paths: list[str] | None = None) -> str:
    """Kør Headend backup synkront og returner arkivsti."""
    global _backup_status
    if not _backup_lock.acquire(blocking=False):
        raise RuntimeError("Der kører allerede en backup")
    _backup_status = {"running": True, "progress": [], "file": None, "error": None}
    backup_dir = None
    try:
        import datetime, os, json
        date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nas_path = _get_nas_path()
        base_dir = nas_path if (nas_path and os.path.isdir(nas_path)) else "/tmp"
        backup_dir = f"{base_dir}/timelapse-backup-headend-{date}"
        os.makedirs(f"{backup_dir}/database", exist_ok=True)
        os.makedirs(f"{backup_dir}/configs", exist_ok=True)

        _backup_status["progress"].append(f"Backup reason: {reason}")
        _backup_status["progress"].append("Database backup (pg_dump)...")
        from urllib.parse import unquote, urlparse
        db_url = os.environ.get(
            "BACKUP_DATABASE_URL",
            os.environ.get("DATABASE_URL", "postgresql://timelapse@localhost/timelapse_db"),
        )
        parsed_db = urlparse(db_url)
        db_name = (parsed_db.path or "/timelapse_db").lstrip("/") or "timelapse_db"
        db_user = unquote(parsed_db.username or "timelapse")
        db_host = parsed_db.hostname or "localhost"
        db_port = str(parsed_db.port) if parsed_db.port else None
        sql_path = f"{backup_dir}/database/timelapse_db_{date}.sql"
        pg_dump_cmd = ["/opt/homebrew/bin/pg_dump", "-U", db_user, "-h", db_host, "--no-password", db_name]
        if db_port:
            pg_dump_cmd[5:5] = ["-p", db_port]
        r = _subprocess.run(pg_dump_cmd, capture_output=True, text=True)
        if r.returncode != 0 and "row-level security policy" in (r.stderr or ""):
            _backup_status["progress"].append("pg_dump ramte RLS; forsøger med --enable-row-security")
            r = _subprocess.run([*pg_dump_cmd, "--enable-row-security"], capture_output=True, text=True)
        if r.returncode == 0:
            with open(sql_path, "w") as f:
                f.write(r.stdout)
            _backup_status["progress"].append(f"Database OK ({len(r.stdout)//1024} KB SQL)")
        else:
            raise Exception(f"pg_dump fejlede: {r.stderr[:300]}")

        _backup_status["progress"].append("Config backup...")
        config_paths = [
            str(Path(HEADEND_LAUNCH_AGENTS) / "homebrew.mxcl.ollama.plist"),
            "/Library/LaunchDaemons/timelapse-headend.plist",
            "/Library/LaunchDaemons/timelapse-node-agent.plist",
            "/opt/homebrew/etc/nginx/nginx.conf",
            "/opt/timelapse/headend/.env",
            "/opt/timelapse/deploy/headend_poller.sh",
            "/home/peter/timelapse-pro/deploy/headend_poller.sh",
        ]
        config_paths.extend(extra_paths or [])
        for f in ["timelapse-headend.service", "timelapse-deploy.service", "timelapse-deploy.timer"]:
            config_paths.append(f"/etc/systemd/system/{f}")
        for f in ["timelapse-deploy", "timelapse-headend"]:
            config_paths.append(f"/etc/sudoers.d/{f}")
        copied: list[str] = []
        for src in dict.fromkeys(config_paths):
            if os.path.exists(src):
                dst = Path(backup_dir) / "configs" / src.lstrip("/").replace("/", "__")
                if os.path.isdir(src):
                    _shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    _shutil.copy2(src, dst)
                copied.append(src)
        with open(f"{backup_dir}/configs/MANIFEST.json", "w") as f:
            json.dump({"reason": reason, "copied": copied}, f, indent=2)
        _backup_status["progress"].append(f"Config OK ({len(copied)} filer)")

        _backup_status["progress"].append("System info...")
        import platform
        with open(f"{backup_dir}/SYSTEMINFO.txt", "w") as f:
            f.write(f"TimeLapse Pro — Headend Backup\nDato: {date}\n")
            f.write(f"Reason: {reason}\n")
            f.write(f"OS: {platform.platform()}\n")
        _backup_status["progress"].append("System info OK")

        _backup_status["progress"].append("Pakker backup...")
        archive = f"{base_dir}/timelapse-backup-headend-{date}.tar.gz"
        _subprocess.run(["tar", "czf", archive, "-C", base_dir, f"timelapse-backup-headend-{date}"],
                       check=True, capture_output=True)
        _shutil.rmtree(backup_dir, ignore_errors=True)
        backup_dir = None

        _backup_status["file"] = archive
        _backup_status["running"] = False
        _backup_status["progress"].append(f"✅ Backup komplet: {os.path.getsize(archive)//1024} KB")
        log.info("Backup komplet: %s", archive)
        return archive
    except Exception as e:
        _backup_status["error"] = str(e)
        _backup_status["running"] = False
        _backup_status["progress"].append(f"❌ Fejl: {e}")
        log.error("Backup fejl: %s", e)
        raise
    finally:
        if backup_dir:
            _shutil.rmtree(backup_dir, ignore_errors=True)
        _backup_lock.release()

def _run_backup():
    """Kør backup i baggrunden."""
    _run_backup_archive("manual")

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


def _path_status(path_value: str | None, *, label: str, required: bool = False, create_probe: bool = False) -> dict:
    path = _Path(path_value or "").expanduser() if path_value else None
    info = {
        "label": label,
        "path": str(path) if path else "",
        "configured": bool(path_value),
        "required": required,
        "exists": False,
        "is_dir": False,
        "writable": False,
        "free_bytes": None,
        "total_bytes": None,
        "error": "",
    }
    if not path:
        info["error"] = "not_configured" if required else ""
        return info
    try:
        info["exists"] = path.exists()
        info["is_dir"] = path.is_dir()
        if create_probe and not info["exists"]:
            path.mkdir(parents=True, exist_ok=True)
            info["exists"] = path.exists()
            info["is_dir"] = path.is_dir()
        if info["is_dir"]:
            usage = _shutil.disk_usage(path)
            info["free_bytes"] = usage.free
            info["total_bytes"] = usage.total
            probe = path / ".timelapse-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            info["writable"] = True
    except Exception as exc:
        info["error"] = str(exc)
    return info


@app.get("/api/admin/storage/status")
def storage_status(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Runtime status for mapped disks/NAS roots used by Headend."""
    settings = {r[0]: r[1] for r in db.execute(text(
        "SELECT key, value FROM settings WHERE key IN "
        "('sftp_base','sftp_legacy_roots','sftp_remote_base','backup_nas_path','edge_image_artifact_dir')"
    )).fetchall()}
    sftp_base = _sftp_base_path(db)
    edge_image_root = _edge_image_storage_dir(create=False)
    roots = [
        _path_status(str(sftp_base), label="Canonical image root", required=True),
        _path_status(settings.get("sftp_remote_base"), label="SFTP remote base", required=False),
        _path_status(settings.get("backup_nas_path"), label="Backup NAS", required=False),
        _path_status(str(edge_image_root), label="Edge image artifacts", required=True),
    ]
    for root in _configured_storage_roots(db)[1:]:
        roots.append(_path_status(str(root), label="Legacy/search image root", required=False))
    return {"roots": roots}



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


def _deep_merge_delete(base: dict, override: dict) -> dict:
    """Merge hvor None betyder 'fjern override og arv igen'."""
    result = dict(base or {})
    for key, value in (override or {}).items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            merged = _deep_merge_delete(result[key], value)
            if merged:
                result[key] = merged
            else:
                result.pop(key, None)
        elif isinstance(value, dict):
            cleaned = _deep_merge_delete({}, value)
            if cleaned:
                result[key] = cleaned
            else:
                result.pop(key, None)
        else:
            result[key] = value
    return result


def _json_dict(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _flatten_config(data: dict, prefix: str = "") -> dict[str, object]:
    rows: dict[str, object] = {}
    for key, value in (data or {}).items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.update(_flatten_config(value, path))
        else:
            rows[path] = value
    return rows


def _get_path(data: dict, path: str) -> object:
    current: object = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _defaults_dict(db: Session) -> dict:
    defaults = _get_or_create_defaults(db)
    result = {}
    for section in ["schedule", "camera", "quality", "storage", "diagnostics", "system", "session_policy"]:
        if hasattr(defaults, section):
            result[section] = _json_dict(getattr(defaults, section, None))
    return result


def _active_camera_for_device(db: Session, device_id: str) -> Camera | None:
    assignment = (
        db.query(DeviceAssignment)
        .filter_by(device_id=device_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .order_by(DeviceAssignment.assigned_at.desc())
        .first()
    )
    return db.query(Camera).filter_by(id=assignment.camera_id).first() if assignment else None


def _resolve_config_hierarchy(
    db: Session,
    *,
    customer_id: str | None = None,
    site_id: str | None = None,
    camera_id: str | None = None,
    device_id: str | None = None,
) -> dict:
    """Resolve global -> customer -> site -> camera config with per-field provenance."""
    device = db.query(Device).filter_by(device_id=device_id).first() if device_id else None
    camera = db.query(Camera).filter_by(id=camera_id).first() if camera_id else None
    if device and not camera:
        camera = _active_camera_for_device(db, device.device_id)
    if camera:
        camera_id = camera.id
        site_id = site_id or camera.site_id
        customer_id = customer_id or camera.customer_id
    if device:
        site_id = site_id or getattr(device, "site_id", None)
        customer_id = customer_id or getattr(device, "customer_id", None)

    site = db.query(Site).filter_by(id=site_id).first() if site_id else None
    if site:
        customer_id = customer_id or site.customer_id
    customer = db.query(Customer).filter_by(id=customer_id).first() if customer_id else None

    layers = [
        {"key": "global", "label": "Global", "entity_id": None, "entity_name": "Globale defaults", "config": _defaults_dict(db)},
        {
            "key": "customer",
            "label": "Kunde",
            "entity_id": customer.id if customer else None,
            "entity_name": customer.name if customer else None,
            "config": _json_dict(customer.config_overrides if customer else None),
        },
        {
            "key": "site",
            "label": "Site",
            "entity_id": site.id if site else None,
            "entity_name": site.name if site else None,
            "config": _json_dict(site.config_overrides if site else None),
        },
        {
            "key": "camera",
            "label": "Kamera",
            "entity_id": camera.id if camera else None,
            "entity_name": camera.camera_name if camera else None,
            "config": _json_dict(camera.config if camera else None),
        },
    ]

    effective: dict = {}
    field_sources: dict[str, str] = {}
    inherited_before_source: dict[str, object] = {}
    global_flat: dict[str, object] = {}

    for layer in layers:
        flat_before = _flatten_config(effective)
        layer_config = layer["config"]
        if layer["key"] == "global":
            global_flat = _flatten_config(layer_config)
        for path, value in _flatten_config(layer_config).items():
            if value is not None:
                field_sources[path] = layer["key"]
                inherited_before_source[path] = flat_before.get(path)
        effective = _deep_merge(effective, layer_config)

    all_paths = sorted({
        *global_flat.keys(),
        *field_sources.keys(),
        *_flatten_config(effective).keys(),
    })
    fields = []
    for path in all_paths:
        layer_values = {layer["key"]: _get_path(layer["config"], path) for layer in layers}
        effective_value = _get_path(effective, path)
        global_value = layer_values.get("global")
        source = field_sources.get(path, "global" if global_value is not None else "factory")
        fields.append({
            "path": path,
            "section": path.split(".", 1)[0],
            "key": path.split(".")[-1],
            "values": layer_values,
            "effective_value": effective_value,
            "source": source,
            "inherited_value": inherited_before_source.get(path),
            "changed_from_global": effective_value != global_value,
            "overridden": source != "global",
        })

    return {
        "context": {
            "device_id": device.device_id if device else device_id,
            "customer_id": customer.id if customer else customer_id,
            "customer_name": customer.name if customer else None,
            "site_id": site.id if site else site_id,
            "site_name": site.name if site else None,
            "camera_id": camera.id if camera else camera_id,
            "camera_name": camera.camera_name if camera else None,
        },
        "layers": [
            {
                "key": layer["key"],
                "label": layer["label"],
                "entity_id": layer["entity_id"],
                "entity_name": layer["entity_name"],
                "config": layer["config"],
            }
            for layer in layers
        ],
        "effective_config": effective,
        "fields": fields,
    }


# ── Customers ─────────────────────────────────────────────────────────────

@app.get("/api/admin/customers")
def list_customers(_user=require_role("viewer"), db: Session = Depends(get_db)):
    customers = _visible_customer_query(db, _user).order_by(Customer.name).all()
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
    if not _is_platform_admin(_user):
        raise HTTPException(status_code=403, detail="Kun platform-admin kan oprette kunder")
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
    _ensure_customer_access(_user, c.id)
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
    _ensure_customer_access(_user, c.id)
    for f in ["name", "contact_name", "contact_email", "contact_phone", "address", "notes"]:
        if f in payload:
            setattr(c, f, payload[f])
    if "config_overrides" in payload:
        # Merge på top-niveau — bevarer øvrige nøgler (bt_totp m.fl.)
        existing = json.loads(c.config_overrides or "{}")
        existing.update(payload["config_overrides"])
        c.config_overrides = json.dumps(existing)
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
    sites = _visible_site_query(db, _user).all()
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
    _ensure_customer_access(_user, payload.get("customer_id"))
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
    s = _ensure_site_access(db, _user, site_id)
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
    s = _ensure_site_access(db, _user, site_id)
    for f in ["name", "address", "gps_lat", "gps_lon", "timezone", "notes"]:
        if f in payload:
            setattr(s, f, payload[f])
    if hasattr(s, "gps_alt") and "gps_alt" in payload:
        s.gps_alt = payload["gps_alt"]
    if "config_overrides" in payload:
        # Merge på top-niveau (ikke fuld overskrivning) — bevarer nøgler
        # sat af andre UI-flows, fx bt_totp sat fra CMDB hierarki-panelet.
        existing = json.loads(s.config_overrides or "{}")
        existing.update(payload["config_overrides"])
        s.config_overrides = json.dumps(existing)
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
    _ensure_capture_device_access(db, _user, device_id)
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
    _ensure_capture_device_access(db, _user, device_id)
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
def clear_update_flag(device_id: str, _auth: None = Depends(_verify_device_token), db: Session = Depends(get_db)):
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

_FACTORY_CONFIG_DEFAULTS = {
    "schedule": {"timezone": "Europe/Copenhagen", "capture_mode": "interval", "interval_minutes": 60, "active_hours": ["06:00", "21:00"], "capture_avoid_windows": []},
    "camera": {
        "power_mode": "relay",
        "relay_gpio_pin": 356,
        "relay_on_seconds_before": 10,
        "relay_off_seconds_after": 5,
        "delete_after_download": True,
        "gphoto2_port": "usb:",
    },
    "quality": {
        "check_enabled": True,
        "blur_threshold": 80,
        "dark_threshold": 25,
        "bright_threshold": 230,
        "adaptive_exposure": {
            "enabled": False,
            "target_brightness": 118,
            "brightness_tolerance": 32,
            "step_ev": 0.3,
            "min_ev": -2.0,
            "max_ev": 2.0,
        },
        "edge_ai": {
            "enabled": True,
            "mode": "assist",
            "prefer_npu": True,
            "runner": "/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py",
            "model_path": "",
            "vendor_binary": "",
            "timeout_s": 8,
            "lens_obstruction_enabled": True,
            "direct_sun_detection_enabled": True,
        },
    },
    "storage": {"local_path": "/data/captures", "circular_buffer_gb": 50, "db_path": "/data/timelapse_edge.db"},
    "diagnostics": {"heartbeat_interval_minutes": 60, "config_poll_interval_minutes": 5, "update_poll_interval_minutes": 5, "inventory_report_interval_hours": 24},
    "system": {"error_recovery_sleep_s": 30, "min_sleep_s": 60, "api_timeout_s": 15},
    "session_policy": {
        "session_duration_hours": 12,
        "remember_me_days": 30,
        "absolute_max_days": 90,
        "rolling_enabled": True,
        "remember_me_allowed": True,
        "mfa_required": False,
        "webauthn_required": False,
        "mfa_required_by_role": {
            "super_admin": True,
            "admin": True,
            "operator": False,
            "viewer": False,
        },
        "mfa_exempt_usernames": [],
    },
}


def _merge_missing_defaults(existing: dict, defaults: dict) -> dict:
    result = dict(existing or {})
    for key, value in (defaults or {}).items():
        if key not in result:
            result[key] = value
        elif isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _merge_missing_defaults(result[key], value)
    return result

def _get_or_create_defaults(db: Session) -> ConfigDefaults:
    d = db.query(ConfigDefaults).first()
    if not d:
        d = ConfigDefaults(
            schedule    = json.dumps(_FACTORY_CONFIG_DEFAULTS["schedule"]),
            camera      = json.dumps(_FACTORY_CONFIG_DEFAULTS["camera"]),
            quality     = json.dumps(_FACTORY_CONFIG_DEFAULTS["quality"]),
            storage     = json.dumps(_FACTORY_CONFIG_DEFAULTS["storage"]),
            diagnostics = json.dumps(_FACTORY_CONFIG_DEFAULTS["diagnostics"]),
            system      = json.dumps(_FACTORY_CONFIG_DEFAULTS["system"]),
            session_policy = json.dumps(_FACTORY_CONFIG_DEFAULTS["session_policy"]),
        )
        db.add(d); db.commit(); db.refresh(d)
    changed = False
    for section, defaults in _FACTORY_CONFIG_DEFAULTS.items():
        if not hasattr(d, section):
            continue
        current = _json_dict(getattr(d, section, None))
        merged = _merge_missing_defaults(current, defaults)
        if merged != current:
            setattr(d, section, json.dumps(merged, ensure_ascii=False))
            changed = True
    if changed:
        db.commit(); db.refresh(d)
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
        "session_policy": json.loads(d.session_policy or "{}") if hasattr(d, "session_policy") else {},
    }


@app.put("/api/admin/config-defaults")
def update_config_defaults(payload: dict, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    d = _get_or_create_defaults(db)
    for section in ["schedule", "camera", "quality", "storage", "diagnostics", "system", "session_policy"]:
        if section in payload and hasattr(d, section):
            setattr(d, section, json.dumps(payload[section]))
    db.commit()
    return {"status": "ok"}


@app.get("/api/admin/config-resolution")
def get_config_resolution(
    customer_id: Optional[str] = None,
    site_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    device_id: Optional[str] = None,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Returnerer effektiv config og provenance for global/kunde/site/kamera."""
    if customer_id:
        _ensure_customer_access(_user, customer_id)
    if site_id:
        _ensure_site_access(db, _user, site_id)
    if device_id:
        _ensure_capture_device_access(db, _user, device_id)
    if camera_id:
        cam = db.query(Camera).filter_by(id=camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Kamera ikke fundet")
        if cam.site_id:
            _ensure_site_access(db, _user, cam.site_id)
        elif cam.customer_id:
            _ensure_customer_access(_user, cam.customer_id)
    return _resolve_config_hierarchy(
        db,
        customer_id=customer_id,
        site_id=site_id,
        camera_id=camera_id,
        device_id=device_id,
    )


@app.put("/api/admin/config-overrides/{layer}/{entity_id}")
def update_config_layer_override(
    layer: str,
    entity_id: str,
    payload: dict,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Gem config på et bestemt lag. `null` i merge-mode fjerner et override."""
    config_payload = payload.get("config_overrides", payload.get("config", {}))
    if not isinstance(config_payload, dict):
        raise HTTPException(status_code=400, detail="config_overrides skal være et JSON object")
    mode = str(payload.get("mode") or "merge").lower()
    replace = mode == "replace"

    if layer == "global":
        if not _is_platform_admin(_user):
            raise HTTPException(status_code=403, detail="Kun platform-admin kan ændre globale defaults")
        defaults = _get_or_create_defaults(db)
        existing = _defaults_dict(db)
        new_config = config_payload if replace else _deep_merge_delete(existing, config_payload)
        for section in ["schedule", "camera", "quality", "storage", "diagnostics", "system", "session_policy"]:
            if section in new_config and hasattr(defaults, section):
                setattr(defaults, section, json.dumps(new_config[section], ensure_ascii=False))
        db.commit()
        return {"status": "ok", "layer": "global"}

    if layer == "customer":
        customer = db.query(Customer).filter_by(id=entity_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Kunde ikke fundet")
        _ensure_customer_access(_user, customer.id)
        existing = _json_dict(customer.config_overrides)
        customer.config_overrides = json.dumps(
            config_payload if replace else _deep_merge_delete(existing, config_payload),
            ensure_ascii=False,
        )
        db.commit()
        return {"status": "ok", "layer": "customer", "entity_id": customer.id}

    if layer == "site":
        site = _ensure_site_access(db, _user, entity_id)
        existing = _json_dict(site.config_overrides)
        site.config_overrides = json.dumps(
            config_payload if replace else _deep_merge_delete(existing, config_payload),
            ensure_ascii=False,
        )
        db.commit()
        return {"status": "ok", "layer": "site", "entity_id": site.id}

    if layer == "camera":
        camera = db.query(Camera).filter_by(id=entity_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Kamera ikke fundet")
        if camera.site_id:
            _ensure_site_access(db, _user, camera.site_id)
        elif camera.customer_id:
            _ensure_customer_access(_user, camera.customer_id)
        existing = _json_dict(camera.config)
        camera.config = json.dumps(
            config_payload if replace else _deep_merge_delete(existing, config_payload),
            ensure_ascii=False,
        )
        db.commit()
        return {"status": "ok", "layer": "camera", "entity_id": camera.id}

    raise HTTPException(status_code=400, detail="layer skal være global, customer, site eller camera")



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
                    """
                    INSERT INTO settings (key, value)
                    VALUES (:k, :v)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """
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


def _resilience_control(status: str, title: str, evidence: str, domains: list[str], recommendation: str = "") -> dict:
    return {
        "status": status,
        "title": title,
        "evidence": evidence,
        "domains": domains,
        "recommendation": recommendation,
    }


def _latest_headend_backup_file(nas_path: str | None) -> str | None:
    """Find latest persisted Headend backup archive, even after service restart."""
    candidates: list[Path] = []
    for base in [nas_path, "/tmp"]:
        if not base:
            continue
        try:
            root = Path(base)
            if root.is_dir():
                candidates.extend(root.glob("timelapse-backup-headend-*.tar.gz"))
        except Exception as exc:
            log.warning("Kunne ikke scanne backup-sti %s: %s", base, exc)
    existing = [p for p in candidates if p.is_file()]
    if not existing:
        return None
    return str(max(existing, key=lambda p: p.stat().st_mtime))


@app.get("/api/admin/resilience/assessment")
def resilience_assessment(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Backup, restore, provisioning and compliance readiness snapshot."""
    devices = db.query(Device).order_by(Device.device_id).all()
    inventory = db.query(DeviceInventory).order_by(DeviceInventory.device_id).all()
    device_ids = {d.device_id for d in devices}
    tickets = db.query(ChangeTicket).count()
    artifacts = db.query(UpdateArtifact).count()
    active_tokens = (
        db.query(BootstrapToken)
        .filter(BootstrapToken.revoked == False)  # noqa: E712
        .filter(BootstrapToken.used_at == None)  # noqa: E711
        .filter(BootstrapToken.expires_at > now_utc())
        .count()
    )
    latest_edge_image = (
        db.query(UpdateArtifact)
        .filter(UpdateArtifact.artifact_type == "edge_bootstrap_image")
        .order_by(UpdateArtifact.created_at.desc())
        .first()
    )

    settings = {}
    try:
        rows = db.execute(text(
            "SELECT key, value FROM settings WHERE key IN "
            "('backup_nas_path','backup_auto_interval','backup_include_images')"
        )).fetchall()
        settings = {r[0]: r[1] for r in rows}
    except Exception:
        settings = {}

    device_by_id = {d.device_id: d for d in devices}
    inventory_device_ids = {inv.device_id for inv in inventory}
    restore_inventory = []
    for inv in inventory:
        device = device_by_id.get(inv.device_id)
        device_status = (getattr(device, "status", "") or "").lower() if device else ""
        is_test = _is_placeholder_device(inv.device_id)
        is_import = device_status == "import" or inv.device_id.startswith("TL-IMPORT-")
        if is_test or is_import:
            continue
        if device or inv.hostname or inv.hardware_model:
            restore_inventory.append(inv)
    restore_devices_without_inventory = []
    for device in devices:
        device_status = (device.status or "").lower()
        is_test = _is_placeholder_device(device.device_id)
        is_import = device_status == "import" or device.device_id.startswith("TL-IMPORT-")
        if is_test or is_import or device.device_id in inventory_device_ids:
            continue
        if device_status in {"provisioning", "online", "offline", "unknown"}:
            restore_devices_without_inventory.append(device)

    cmdb_state_rows = [
        inv for inv in restore_inventory
        if getattr(inv, "os_packages", None) and inv.venv_packages and getattr(inv, "software_inventory", None)
    ]
    firmware_rows = [inv for inv in restore_inventory if getattr(inv, "firmware_version", None)]
    backup_complete = []
    backup_requested = []
    def _device_cfg(device: Device | None) -> dict:
        if not device:
            return {}
        try:
            cfg = json.loads(device.device_config or "{}")
            return cfg if isinstance(cfg, dict) else {}
        except Exception:
            return {}

    for device in devices:
        cfg = _device_cfg(device)
        if cfg.get("backup_complete"):
            backup_complete.append(device.device_id)
        if cfg.get("backup_requested"):
            backup_requested.append(device.device_id)

    nas_path = settings.get("backup_nas_path")
    latest_backup_file = _backup_status.get("file") or _latest_headend_backup_file(nas_path)
    latest_backup_exists = bool(latest_backup_file and os.path.exists(latest_backup_file))
    nas_ready = bool(nas_path and os.path.isdir(nas_path))

    controls = [
        _resilience_control(
            "pass" if latest_backup_exists else "warning",
            "Headend database/config backup",
            f"latest_file={os.path.basename(latest_backup_file) if latest_backup_file else 'none'}",
            ["ISO27000", "NIS2", "SABSA"],
            "Run and verify headend backup before approval." if not latest_backup_exists else "",
        ),
        _resilience_control(
            "pass" if nas_ready else "warning",
            "Off-host backup target",
            f"backup_nas_path={nas_path or 'not configured'}",
            ["ISO27000", "NIS2"],
            "Configure NAS/off-host target and restore test evidence." if not nas_ready else "",
        ),
        _resilience_control(
            "pass" if len(cmdb_state_rows) == len(restore_inventory) and restore_inventory else "fail",
            "Installed-state CMDB evidence",
            f"{len(cmdb_state_rows)}/{len(restore_inventory)} restore node(s) include OS packages, venv and software state",
            ["IEC62443", "CRA", "SABSA"],
            "All restore-relevant nodes must report hardware, firmware, OS packages, venv and software inventory." if len(cmdb_state_rows) < len(restore_inventory) else "",
        ),
        _resilience_control(
            "pass" if len(firmware_rows) == len(restore_inventory) and restore_inventory else "warning",
            "Firmware inventory",
            f"{len(firmware_rows)}/{len(restore_inventory)} restore node(s) include firmware state",
            ["IEC62443", "CRA"],
            "Firmware/bootloader state is needed for bare-metal restore and vulnerability governance." if len(firmware_rows) < len(restore_inventory) else "",
        ),
        _resilience_control(
            "pass" if artifacts else "fail",
            "Signed update/artifact catalog",
            f"{artifacts} update artifact(s) registered",
            ["CRA", "IEC62443", "ISO27000"],
            "Create signed update/ISO artifact catalog for Headend-driven decisions." if not artifacts else "",
        ),
        _resilience_control(
            "pass" if tickets else "warning",
            "Signed change workflow",
            f"{tickets} change ticket(s) registered",
            ["ISO27000", "NIS2", "SABSA"],
            "Bind backup, restore, update and ISO decisions to signed change tickets." if not tickets else "",
        ),
        _resilience_control(
            "pass" if latest_edge_image else "warning",
            "Bare-metal edge ISO pipeline",
            (
                f"signed manifest {latest_edge_image.artifact_id} ({latest_edge_image.signed_by}); "
                f"active_bootstrap_tokens={active_tokens}"
            ) if latest_edge_image else (
                f"bootstrap provisioning ready; active_bootstrap_tokens={active_tokens}; "
                "signed image manifest not yet generated"
            ),
            ["CRA", "IEC62443", "NIS2"],
            "" if latest_edge_image else "Generate signed edge bootstrap image manifest via Drift & Resilience → Edge ISO → Byg Image.",
        ),
        _resilience_control(
            "warning",
            "Automated restore and rollback tests",
            f"edge_backup_complete={len(backup_complete)}, edge_backup_requested={len(backup_requested)}",
            ["NIS2", "ISO27000", "IEC62443"],
            "Add periodic restore test and rollback test evidence.",
        ),
    ]

    counts = {"pass": 0, "warning": 0, "fail": 0}
    for control in controls:
        counts[control["status"]] = counts.get(control["status"], 0) + 1

    return {
        "generated_at": now_utc().isoformat(),
        "summary": {
            "devices": len(devices),
            "inventory_rows": len(inventory),
            "restore_inventory_rows": len(restore_inventory),
            "headend_backup_ready": latest_backup_exists,
            "nas_ready": nas_ready,
            "active_bootstrap_tokens": active_tokens,
            "update_artifacts": artifacts,
            "change_tickets": tickets,
            "counts": counts,
        },
        "headend_dr": {
            "latest_backup_file": latest_backup_file,
            "latest_backup_exists": latest_backup_exists,
            "nas_path": nas_path,
            "auto_interval": settings.get("backup_auto_interval", "manual"),
            "warm_standby_status": "not_configured",
        },
        "edge_restore": [
            {
                "device_id": inv.device_id,
                "hardware_model": inv.hardware_model,
                "firmware_version": getattr(inv, "firmware_version", None),
                "os_name": inv.os_name,
                "kernel_version": inv.kernel_version,
                "app_version": inv.app_version,
                "package_manager": getattr(inv, "package_manager", None),
                "has_os_packages": bool(getattr(inv, "os_packages", None)),
                "has_venv_packages": bool(inv.venv_packages),
                "has_software_inventory": bool(getattr(inv, "software_inventory", None)),
                "inventory_reported_at": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
                "device_exists": inv.device_id in device_ids,
                "backup_requested": _device_cfg(device_by_id.get(inv.device_id)).get("backup_requested", False),
                "backup_requested_at": _device_cfg(device_by_id.get(inv.device_id)).get("backup_requested_at"),
                "backup_complete": _device_cfg(device_by_id.get(inv.device_id)).get("backup_complete"),
            }
            for inv in restore_inventory
        ] + [
            {
                "device_id": device.device_id,
                "hardware_model": None,
                "firmware_version": None,
                "os_name": None,
                "kernel_version": None,
                "app_version": device.app_version,
                "package_manager": None,
                "has_os_packages": False,
                "has_venv_packages": False,
                "has_software_inventory": False,
                "inventory_reported_at": None,
                "device_exists": True,
                "backup_requested": _device_cfg(device).get("backup_requested", False),
                "backup_requested_at": _device_cfg(device).get("backup_requested_at"),
                "backup_complete": _device_cfg(device).get("backup_complete"),
            }
            for device in restore_devices_without_inventory
        ],
        "iso_blueprint": {
            "status": "image_signed" if latest_edge_image else "provisioning_ready",
            "call_home": "/api/bootstrap with short-lived bootstrap token",
            "ready_to_accept_new_edge": True,
            "active_bootstrap_tokens": active_tokens,
            "latest_image": _artifact_to_dict(latest_edge_image) if latest_edge_image else None,
            "hardening": [
                "disable password SSH for production profile",
                "only required users, services and packages",
                "firewall deny inbound except explicit debug profile",
                "signed agent, config and artifact verification",
                "audit logging to SIEM after first contact",
            ],
            "required_outputs": [
                "image file",
                "sha256",
                "signed manifest",
                "SBOM/package inventory",
                "hardening evidence",
                "restore/update test evidence",
            ],
        },
        "controls": controls,
    }


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


@app.post("/api/admin/edge-provisioning/prepare")
def prepare_edge_provisioning(
    payload: EdgeProvisioningPrepareRequest,
    current_user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Prepare Headend to receive a new Edge and return one-time bootstrap config."""
    import secrets
    from datetime import timedelta

    device_id = _sanitize_device_id(payload.device_id.strip())
    expires_hours = max(1, min(int(payload.expires_hours or 48), 24 * 14))
    headend_url = _headend_api_url(db, payload.headend_url)
    location_name = (
        payload.location_name
        or " / ".join([v for v in [payload.customer_name, payload.site_name, payload.camera_name] if v])
        or device_id
    )

    existing_open = (
        db.query(BootstrapToken)
        .filter_by(used_at=None, used_by_device=None, revoked=False)
        .filter(BootstrapToken.device_label == location_name)
        .order_by(BootstrapToken.created_at.desc())
        .first()
    )
    if existing_open and existing_open.expires_at and now_utc() <= existing_open.expires_at.replace(tzinfo=_tz.utc):
        existing_open.revoked = True

    token_str = f"tlp-{secrets.token_urlsafe(32)}"
    expires_at = now_utc() + timedelta(hours=expires_hours)

    # Opret Camera-entitet hvis camera_id ikke er angivet men camera_name + site_id er
    camera_id = payload.camera_id
    if not camera_id and payload.camera_name and payload.site_id:
        from database import Camera as _Camera
        import uuid as _cam_uuid
        new_cam = _Camera(
            id=str(_cam_uuid.uuid4()),
            site_id=payload.site_id,
            customer_id=payload.customer_id,
            camera_name=payload.camera_name,
        )
        db.add(new_cam)
        db.flush()
        camera_id = new_cam.id
        log.info("Kamera-lokation oprettet: %s (%s) for site %s", payload.camera_name, camera_id, payload.site_id)

    # Gem/opdater netværkskonfiguration på Camera-entiteten (v7)
    if camera_id and (payload.network_type or payload.wifi_ssid):
        from database import Camera as _Camera
        cam_rec = db.query(_Camera).filter_by(id=camera_id).first()
        if cam_rec:
            if payload.network_type:
                cam_rec.network_type = payload.network_type
            if payload.wifi_ssid is not None:
                cam_rec.wifi_ssid = payload.wifi_ssid or None
            if payload.wifi_password is not None:
                cam_rec.wifi_password = payload.wifi_password or None
            if payload.wifi_country:
                cam_rec.wifi_country = payload.wifi_country or "DK"
            log.info("Netværksconfig opdateret for kamera %s: %s", camera_id, payload.network_type)

    # Generér SSH keypair + tildel reverse tunnel port (v8)
    if camera_id:
        from database import Camera as _Camera
        cam_rec = db.query(_Camera).filter_by(id=camera_id).first()
        if cam_rec and not getattr(cam_rec, "ssh_private_key", None):
            # Generer unik Ed25519 nøgle til denne enhed
            import tempfile, subprocess as _sp, os as _os
            with tempfile.TemporaryDirectory() as _td:
                _kpath = _os.path.join(_td, "id_ed25519")
                _sp.run(
                    ["ssh-keygen", "-t", "ed25519", "-f", _kpath, "-N", "",
                     "-C", f"timelapse-{camera_id[:8]}"],
                    check=True, capture_output=True,
                )
                cam_rec.ssh_private_key = open(_kpath).read()
                cam_rec.ssh_public_key  = open(_kpath + ".pub").read().strip()
            log.info("SSH keypair genereret for kamera %s", camera_id)
        if cam_rec and not getattr(cam_rec, "reverse_tunnel_port", None):
            # Tildel næste ledige port fra 2201
            from database import Camera as _Camera2
            existing_ports = [
                r[0] for r in db.query(_Camera2.reverse_tunnel_port)
                .filter(_Camera2.reverse_tunnel_port.isnot(None)).all()
            ]
            cam_rec.reverse_tunnel_port = max(existing_ports, default=2200) + 1
            log.info("Reverse tunnel port tildelt: %d for kamera %s",
                     cam_rec.reverse_tunnel_port, camera_id)

    token_rec = BootstrapToken(
        token=token_str,
        device_label=location_name,
        site_id=payload.site_id,
        customer_id=payload.customer_id,
        camera_name=payload.camera_name,
        created_by=current_user.username,
        expires_at=expires_at,
    )
    # Gem camera_id hvis kolonnen eksisterer (v6 migration)
    if camera_id and hasattr(token_rec, "camera_id"):
        token_rec.camera_id = camera_id
    db.add(token_rec)

    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        device = Device(device_id=device_id, first_seen=now_utc())
        db.add(device)
    device.status = "provisioning"
    device.customer_id = payload.customer_id or device.customer_id
    device.customer_name = payload.customer_name or device.customer_name
    device.site_id = payload.site_id or device.site_id
    device.site_name = payload.site_name or device.site_name
    device.camera_name = payload.camera_name or device.camera_name
    device.location_name = payload.location_name or location_name
    try:
        cfg = json.loads(device.device_config or "{}")
    except Exception:
        cfg = {}
    cfg["provisioning"] = {
        "prepared_at": now_utc().isoformat(),
        "prepared_by": current_user.username,
        "expires_at": expires_at.isoformat(),
        "headend_url": headend_url,
        "note": payload.note or "",
        "status": "awaiting_bootstrap",
    }
    device.device_config = json.dumps(cfg, ensure_ascii=False)

    db.add(Event(
        device_id=device_id,
        level="INFO",
        category="provision",
        message="Edge provisioning prepared",
        extra=json.dumps({
            "created_by": current_user.username,
            "expires_at": expires_at.isoformat(),
            "headend_url": headend_url,
            "customer_id": payload.customer_id,
            "site_id": payload.site_id,
        }, ensure_ascii=False),
    ))
    db.commit()

    bootstrap_yaml = _build_bootstrap_yaml(device_id, headend_url, token_str, location_name)
    return {
        "status": "prepared",
        "device_id": device_id,
        "camera_id": camera_id,
        "headend_url": headend_url,
        "token": token_str,
        "expires_at": expires_at.isoformat(),
        "bootstrap_yaml": bootstrap_yaml,
        "next_steps": [
            "Kopier bootstrap.yaml til /opt/timelapse/edge/bootstrap.yaml på den nye Edge.",
            "Konfigurer lokal netværksadgang via Edge CLI, Ethernet, WiFi eller 4G.",
            "Start eller genstart Edge agenten, så den kalder /api/bootstrap på Headend.",
            "Kontroller CMDB, inventory heartbeat og baseline Edge backup i Drift & Resilience.",
        ],
    }


# ── Edge disk image build pipeline ────────────────────────────────────────────

_edge_disk_build_status: dict = {
    "running": False, "progress": [], "error": None, "result": None,
}
_edge_disk_build_lock = _threading.Lock()


class DiskImageBuildRequest(BaseModel):
    target: str = "orangepi4pro"
    mode: str = "rootfs"          # "rootfs" | "flashable"
    bootstrap_token: str = ""     # kun til "flashable" mode
    wifi_ssid: str = ""           # bages ind i image (valgfrit)
    wifi_password: str = ""       # WiFi adgangskode
    wifi_country: str = "DK"      # WiFi landekode
    camera_id: Optional[str] = None  # UUID til Camera → SSH keys + tunnel port hentes fra DB


def _edge_image_storage_dir(*, create: bool = True) -> Path:
    configured = os.getenv("TIMELAPSE_EDGE_IMAGE_DIR")
    if not configured:
        db = SessionLocal()
        try:
            configured = _get_setting(db, "edge_image_artifact_dir", "")
        finally:
            db.close()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        Path("/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images"),
        Path("/Volumes/data-fast/backup/timelapse-artifacts/edge-images"),
        _repo_root() / "headend" / "exports" / "edge-images",
    ])

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            if not create:
                return candidate
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception as exc:
            last_error = exc
            log.warning("Edge image storage %s er ikke skrivbar: %s", candidate, exc)
    raise RuntimeError(f"Ingen skrivbar Edge image artifact-mappe fundet: {last_error}")


def _edge_image_manifest_index(storage_dir: Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for manifest_path in storage_dir.glob("*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        image = manifest.get("image") if isinstance(manifest, dict) else None
        filename = image.get("filename") if isinstance(image, dict) else None
        if filename:
            index[str(filename)] = manifest
        artifact_id = manifest.get("artifact_id") if isinstance(manifest, dict) else None
        if artifact_id:
            index[str(artifact_id)] = manifest
    return index


def _edge_image_file_entries(storage_dir: Path) -> list[dict]:
    manifests = _edge_image_manifest_index(storage_dir)
    entries: list[dict] = []
    for file_path in sorted(
        list(storage_dir.glob("*.img.gz")) + list(storage_dir.glob("*.rootfs.tar.gz")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        manifest = manifests.get(file_path.name) or {}
        artifact_id = str(manifest.get("artifact_id") or file_path.name)
        image_meta = manifest.get("image") if isinstance(manifest.get("image"), dict) else {}
        created_at = manifest.get("created_at")
        artifact_type = str(
            manifest.get("artifact_type")
            or ("flashable_disk_image" if file_path.name.endswith(".img.gz") else "edge_disk_image")
        )
        entries.append({
            "artifact_id": artifact_id,
            "filename": file_path.name,
            "artifact_type": artifact_type,
            "size_bytes": int(image_meta.get("size_bytes") or file_path.stat().st_size),
            "sha256": image_meta.get("sha256"),
            "created_at": created_at,
            "exists_on_disk": True,
            "source": "filesystem",
            "storage_path": str(file_path),
        })
    return entries


def _resolve_edge_image_path(artifact_id: str, db: Session) -> tuple[Path, str]:
    artifact = db.query(UpdateArtifact).filter(
        UpdateArtifact.artifact_id == artifact_id,
        UpdateArtifact.artifact_type.in_(["edge_disk_image", "flashable_disk_image"]),
    ).first()
    if artifact:
        if not artifact.storage_path or not os.path.exists(artifact.storage_path):
            raise HTTPException(status_code=410, detail="Image-fil ikke tilgængelig (måske slettet fra disk)")
        return Path(artifact.storage_path), artifact.filename or f"{artifact_id}.img.gz"

    storage_dir = _edge_image_storage_dir()
    manifests = _edge_image_manifest_index(storage_dir)
    for entry in _edge_image_file_entries(storage_dir):
        if artifact_id in {entry["artifact_id"], entry["filename"]}:
            return Path(entry["storage_path"]), entry["filename"]
    manifest = manifests.get(artifact_id)
    if manifest and isinstance(manifest.get("image"), dict):
        filename = manifest["image"].get("filename")
        if filename:
            candidate = storage_dir / str(filename)
            if candidate.exists():
                return candidate, str(filename)
    raise HTTPException(status_code=404, detail="Artifact ikke fundet")


def _run_edge_disk_image_build(
    headend_url: str,
    gpg_key_id: str | None,
    output_dir: str,
    db_factory,
    target: str = "orangepi4pro",
    mode: str = "rootfs",
    bootstrap_token: str = "",
    wifi_ssid: str = "",
    wifi_password: str = "",
    wifi_country: str = "DK",
    camera_id: Optional[str] = None,
) -> None:
    """Background thread: bygger edge disk image og registrerer artifact.

    mode="rootfs"    → kun Docker buildx → rootfs.tar.gz (eksisterende adfærd)
    mode="flashable" → rootfs + injection → flashbart .img.gz klar til SD/NVMe
    """
    global _edge_disk_build_status
    try:
        from headend.tools.build_edge_disk_image import build_edge_image
    except ImportError:
        import sys
        sys.path.insert(0, str(_repo_root() / "headend"))
        from tools.build_edge_disk_image import build_edge_image  # type: ignore

    def progress(msg: str) -> None:
        _edge_disk_build_status["progress"].append(msg)
        log.info("[edge-image-build] %s", msg)

    try:
        # ── Trin 1: Byg rootfs via Docker buildx ──────────────────────────
        result = build_edge_image(
            target=target,
            headend_url=headend_url,
            gpg_key_id=gpg_key_id,
            progress_cb=progress,
            repo_root=str(_repo_root()),
            output_dir=output_dir,
        )

        # ── Trin 2 (valgfri): Injectér i base-image → flashbar .img.gz ───
        if mode == "flashable":
            # Brug importlib.reload for at sikre vi altid henter den nyeste
            # version af inject_edge_image.py fra disk — ikke en cachet version
            # fra sys.modules (som kan være gammel hvis headend kører --reload).
            import importlib
            try:
                import headend.tools.inject_edge_image as _inj_mod
                importlib.reload(_inj_mod)
                inject_edge_image = _inj_mod.inject_edge_image
            except (ImportError, ModuleNotFoundError):
                import sys
                sys.path.insert(0, str(_repo_root() / "headend"))
                import tools.inject_edge_image as _inj_mod  # type: ignore
                importlib.reload(_inj_mod)
                inject_edge_image = _inj_mod.inject_edge_image

            progress(f"\n💉 Mode=flashable — starter image injection...")

            # ── Hent SSH-nøgler fra kamera-DB ────────────────────────────────
            _headend_ssh_pubkey = ""
            _device_ssh_privkey = ""
            _ssh_tunnel_port    = 0
            if camera_id:
                try:
                    from database import Camera as _Camera
                    _db_ssh = db_factory()
                    try:
                        _cam = _db_ssh.query(_Camera).filter_by(id=camera_id).first()
                        if _cam:
                            _device_ssh_privkey = getattr(_cam, "ssh_private_key", "") or ""
                            _ssh_tunnel_port    = int(getattr(_cam, "reverse_tunnel_port", 0) or 0)
                            _cam_name = getattr(_cam, "camera_name", camera_id)
                            if _device_ssh_privkey:
                                progress(f"   📷 Kamera '{_cam_name}': SSH privkey hentet, tunnel port {_ssh_tunnel_port}")
                            else:
                                progress(f"   ⚠️  Kamera '{_cam_name}' har ingen SSH privkey — kald /prepare først")
                    finally:
                        _db_ssh.close()
                except Exception as _e:
                    progress(f"   ⚠️  Kunne ikke hente kamera SSH keys: {_e}")

            # Headend public key fra ~/.ssh/timelapse_headend_ed25519.pub
            # Auto-generer nøglen hvis den ikke findes — nødvendig for SSH adgang til device.
            _headend_key_path  = Path.home() / ".ssh" / "timelapse_headend_ed25519"
            _headend_pubkey_path = _headend_key_path.with_suffix(".pub")
            if not _headend_pubkey_path.exists():
                progress(f"   🔑 Headend SSH keypair mangler — genererer...")
                try:
                    _headend_key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    import subprocess as _ssh_sp
                    _ssh_sp.run(
                        [
                            "ssh-keygen", "-t", "ed25519",
                            "-f", str(_headend_key_path),
                            "-N", "",
                            "-C", "timelapse-headend",
                        ],
                        check=True, capture_output=True,
                    )
                    _headend_key_path.chmod(0o600)
                    progress(f"   ✅ Headend SSH keypair genereret: {_headend_key_path}")
                except Exception as _keygen_err:
                    raise RuntimeError(
                        f"Kunne ikke generere headend SSH keypair: {_keygen_err}\n"
                        f"Kør manuelt: ssh-keygen -t ed25519 -f ~/.ssh/timelapse_headend_ed25519 -N '' -C timelapse-headend"
                    ) from _keygen_err
            _headend_ssh_pubkey = _headend_pubkey_path.read_text().strip()
            progress(f"   🔑 Headend pubkey hentet: {_headend_pubkey_path.name}")

            inject_result = inject_edge_image(
                target=target,
                rootfs_tar=result["output_path"],
                headend_url=headend_url,
                bootstrap_token=bootstrap_token,
                gpg_key_id=gpg_key_id,
                progress_cb=progress,
                repo_root=str(_repo_root()),
                output_dir=output_dir,
                wifi_ssid=wifi_ssid,
                wifi_password=wifi_password,
                wifi_country=wifi_country,
                headend_ssh_pubkey=_headend_ssh_pubkey,
                device_ssh_privkey=_device_ssh_privkey,
                ssh_tunnel_port=_ssh_tunnel_port,
            )
            # Merge injection-resultater ind i result
            result.update({
                "filename":          inject_result["filename"],
                "output_path":       inject_result["output_path"],
                "sha256":            inject_result["sha256"],
                "size_bytes":        inject_result["size_bytes"],
                "token_baked_in":    inject_result["token_baked_in"],
                "flash_instructions": inject_result["flash_instructions"],
                "mode":              "flashable",
                "artifact_type":     "flashable_disk_image",
            })
        else:
            result["mode"] = "rootfs"
            result["artifact_type"] = "edge_disk_image"

        # ── Registrér artifact i database ─────────────────────────────────
        db = db_factory()
        try:
            created_at = now_utc()
            with open(result["manifest_path"], encoding="utf-8") as f:
                manifest_json = f.read()
            artifact = UpdateArtifact(
                artifact_id=result["artifact_id"],
                artifact_type=result.get("artifact_type", "edge_disk_image"),
                version=result.get("created_at", created_at.isoformat()),
                source_commit=_git_text(["rev-parse", "HEAD"]) or "unknown",
                source_ref=_git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "main",
                filename=result["filename"],
                storage_path=result["output_path"],
                size_bytes=result["size_bytes"],
                sha256=result["sha256"],
                manifest_json=manifest_json,
                sbom_ref=f"sbom:os={result.get('sbom_os_count',0)},venv={result.get('sbom_venv_count',0)}",
                signature=result["signature"],
                signed_by=result["signed_by"],
                signed_at=created_at,
                created_at=created_at,
            )
            db.add(artifact)
            db.commit()
            result["db_artifact_id"] = artifact.id
            progress(f"✅ Artifact registreret i database: {result['artifact_id']}")
        finally:
            db.close()

        _edge_disk_build_status["result"] = result
        _edge_disk_build_status["running"] = False
    except Exception as exc:
        _edge_disk_build_status["error"] = str(exc)
        _edge_disk_build_status["running"] = False
        _edge_disk_build_status["progress"].append(f"❌ Build fejlede: {exc}")
        log.error("Edge disk image build fejlede: %s", exc, exc_info=True)
    finally:
        _edge_disk_build_lock.release()


@app.post("/api/admin/edge-provisioning/build-disk-image")
def trigger_edge_disk_image_build(
    body: DiskImageBuildRequest = DiskImageBuildRequest(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """
    Start baggrunds-build af edge image.

    mode="rootfs"    → Docker buildx arm64/armhf → rootfs.tar.gz (hurtig, ~5 min)
    mode="flashable" → rootfs + injection → flashbart .img.gz klar til SSD (langsom, ~20 min)

    Angiv target for hardware-specifik build:
      orangepi4pro, orangepi-pc-plus, rpi4, rpi5
      (jetson-orin-nano understøttes ikke — brug install_timelapse_edge.sh)

    Poll GET /api/admin/edge-provisioning/disk-image-status for fremgang.
    """
    # Validér target
    hw_dir = _repo_root() / "headend" / "tools" / "hardware"
    available_targets = sorted(p.parent.name for p in hw_dir.glob("*/target.yaml"))
    if body.target not in available_targets:
        raise HTTPException(status_code=400, detail=f"Ukendt target '{body.target}'. Tilgængelige: {available_targets}")

    if not _edge_disk_build_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Et edge disk image build kører allerede")

    global _edge_disk_build_status
    _edge_disk_build_status = {
        "running": True, "progress": [], "error": None, "result": None,
        "target": body.target, "mode": body.mode,
    }

    headend_url = _headend_api_url(db, os.getenv("TIMELAPSE_HEADEND_URL"))
    gpg_key_id = os.getenv("CHANGE_TICKET_GPG_KEY") or os.getenv("TIMELAPSE_GPG_KEY")
    output_dir = str(_edge_image_storage_dir())
    os.makedirs(output_dir, exist_ok=True)

    from database import SessionLocal as _SessionLocal
    t = _threading.Thread(
        target=_run_edge_disk_image_build,
        args=(headend_url, gpg_key_id, output_dir, _SessionLocal),
        kwargs={
            "target": body.target,
            "mode": body.mode,
            "bootstrap_token": body.bootstrap_token,
            "wifi_ssid": body.wifi_ssid,
            "wifi_password": body.wifi_password,
            "wifi_country": body.wifi_country or "DK",
            "camera_id": body.camera_id,
        },
        daemon=True,
        name="edge-disk-image-build",
    )
    t.start()
    return {
        "status": "started",
        "target": body.target,
        "mode": body.mode,
        "message": f"Build startet [{body.target}, mode={body.mode}] — poll /api/admin/edge-provisioning/disk-image-status",
    }


@app.get("/api/admin/edge-provisioning/disk-image-status")
def edge_disk_image_status(_user=require_role("super_admin", "admin")):
    """Poll build-fremgang for edge disk image."""
    s = _edge_disk_build_status
    return {
        "running":  s["running"],
        "progress": s["progress"],
        "error":    s["error"],
        "result":   s["result"],
        "ready":    not s["running"] and s["result"] is not None,
        "target":   s.get("target"),
        "mode":     s.get("mode"),
    }


@app.get("/api/admin/edge-provisioning/targets")
def list_edge_targets(_user=require_role("super_admin", "admin")):
    """List tilgængelige hardware targets til edge image build."""
    import yaml as _yaml
    hw_dir = _repo_root() / "headend" / "tools" / "hardware"
    targets = []
    for target_yaml in sorted(hw_dir.glob("*/target.yaml")):
        try:
            tgt = _yaml.safe_load(target_yaml.read_text()) or {}
            targets.append({
                "id":           tgt.get("id", target_yaml.parent.name),
                "display_name": tgt.get("display_name", target_yaml.parent.name),
                "arch":         tgt.get("arch", "arm64"),
                "soc":          tgt.get("soc"),
                "hal_class":    tgt.get("hal_class"),
                "flashable":    tgt.get("base_image", {}).get("type") != "install_script",
                "install_script": tgt.get("base_image", {}).get("type") == "install_script",
            })
        except Exception as exc:
            log.warning("Kunne ikke læse %s: %s", target_yaml, exc)
    return {"targets": targets}


@app.get("/api/admin/edge-provisioning/disk-images")
def list_flashable_disk_images(_user=require_role("super_admin", "admin"), db: Session = Depends(get_db)):
    """List alle flashable disk images (klar til WiFi-injektion eller download)."""
    artifacts = (
        db.query(UpdateArtifact)
        .filter(UpdateArtifact.artifact_type.in_(["edge_disk_image", "flashable_disk_image"]))
        .order_by(UpdateArtifact.created_at.desc())
        .limit(50)
        .all()
    )
    entries = [
        {
            "artifact_id": a.artifact_id,
            "filename": a.filename,
            "artifact_type": a.artifact_type,
            "size_bytes": a.size_bytes,
            "sha256": a.sha256,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "exists_on_disk": bool(a.storage_path and os.path.exists(a.storage_path)),
            "source": "database",
        }
        for a in artifacts
    ]
    seen = {e["artifact_id"] for e in entries} | {e["filename"] for e in entries if e.get("filename")}
    for entry in _edge_image_file_entries(_edge_image_storage_dir()):
        if entry["artifact_id"] not in seen and entry["filename"] not in seen:
            entries.append({k: v for k, v in entry.items() if k != "storage_path"})
            seen.add(entry["artifact_id"])
            seen.add(entry["filename"])
    return sorted(entries, key=lambda e: e.get("created_at") or "", reverse=True)[:100]


@app.get("/api/admin/edge-provisioning/disk-image-download/{artifact_id}")
def download_edge_disk_image(artifact_id: str, _user=require_role("super_admin", "admin"), db: Session = Depends(get_db)):
    """Download færdigt edge disk image (rootfs tarball)."""
    from fastapi.responses import FileResponse
    image_path, filename = _resolve_edge_image_path(artifact_id, db)
    return FileResponse(
        str(image_path),
        media_type="application/octet-stream",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


class InjectWifiRequest(BaseModel):
    artifact_id: str
    wifi_ssid: str
    wifi_password: str
    wifi_country: str = "DK"
    wifi_method: str = "auto"   # "auto" | "netplan" | "wpa_supplicant"
    camera_id: Optional[str] = None  # bruges til at hente SSH-nøgler fra DB


_wifi_inject_status: dict = {
    "running": False, "progress": [], "error": None, "result": None,
}
_wifi_inject_lock = _threading.Lock()


def _run_wifi_inject(
    artifact_id: str,
    wifi_ssid: str,
    wifi_password: str,
    wifi_country: str,
    wifi_method: str,
    db_factory,
    camera_id: str | None = None,
) -> None:
    """Background thread: injectér WiFi i eksisterende flashbart image."""
    global _wifi_inject_status

    def progress(msg: str) -> None:
        _wifi_inject_status["progress"].append(msg)
        log.info("[wifi-inject] %s", msg)

    try:
        try:
            from headend.tools.inject_wifi_image import inject_wifi_image
        except ImportError:
            import sys
            sys.path.insert(0, str(_repo_root() / "headend"))
            from tools.inject_wifi_image import inject_wifi_image  # type: ignore

        # artifact_id kan enten være et TL-... ID (DB-opslag) eller en direkte filsti
        if artifact_id.startswith("/") or artifact_id.startswith("~"):
            # Direkte filsti — ingen DB-opslag
            gz_path = os.path.expanduser(artifact_id)
            if not os.path.exists(gz_path):
                raise FileNotFoundError(f"Fil ikke fundet: {gz_path}")
            fname = os.path.basename(gz_path)
            output_dir = os.path.dirname(gz_path)
            progress(f"   Direkte filsti: {gz_path}")
        else:
            # Hent artifact-info i kortlivet session — luk FØR lang operation
            # så PostgreSQL ikke dropper idle-forbindelsen.
            db_read = db_factory()
            try:
                artifact = db_read.query(UpdateArtifact).filter(
                    UpdateArtifact.artifact_id == artifact_id,
                    UpdateArtifact.artifact_type.in_(["edge_disk_image", "flashable_disk_image"]),
                ).first()
                if not artifact:
                    raise ValueError(f"Artifact ikke fundet: {artifact_id}")
                if not artifact.storage_path or not os.path.exists(artifact.storage_path):
                    raise FileNotFoundError(f"Image-fil ikke tilgængelig: {artifact.storage_path}")
                fname = artifact.filename or ""
                gz_path = artifact.storage_path
                output_dir = os.path.dirname(gz_path)
            finally:
                db_read.close()

        target_id: str | None = None
        for known in ["orangepi4pro", "orangepi-pc-plus", "rpi4", "rpi5", "jetson-orin-nano"]:
            if known in fname:
                target_id = known
                break

        # Hent SSH-parametre fra Camera hvis camera_id er angivet
        ssh_private_key: str | None = None
        headend_ssh_public_key: str | None = None
        reverse_tunnel_port: int | None = None
        if camera_id:
            db_ssh = db_factory()
            try:
                from database import Camera as _Camera
                cam_ssh = db_ssh.query(_Camera).filter_by(id=camera_id).first()
                if cam_ssh:
                    ssh_private_key    = getattr(cam_ssh, "ssh_private_key", None)
                    reverse_tunnel_port = getattr(cam_ssh, "reverse_tunnel_port", None)
            finally:
                db_ssh.close()
            # Hent headend public key
            try:
                import os as _os
                _pub = _os.path.expanduser("~/.ssh/timelapse_headend_ed25519.pub")
                if _os.path.exists(_pub):
                    headend_ssh_public_key = open(_pub).read().strip()
            except Exception:
                pass

        if ssh_private_key:
            progress(f"   🔑 SSH inject aktiveret (tunnel port {reverse_tunnel_port})")

        # Lang operation — ingen åben DB-session
        result = inject_wifi_image(
            gz_path=gz_path,
            wifi_ssid=wifi_ssid,
            wifi_password=wifi_password,
            wifi_country=wifi_country,
            wifi_method=wifi_method,
            target_id=target_id,
            output_dir=output_dir,
            progress_cb=progress,
            repo_root=str(_repo_root()),
            ssh_private_key=ssh_private_key,
            headend_ssh_public_key=headend_ssh_public_key,
            reverse_tunnel_port=reverse_tunnel_port,
        )

        # Ny DB-session til INSERT (den gamle er timed out)
        from datetime import datetime, timezone as _tz
        db_write = db_factory()
        try:
            new_artifact_id = f"TL-FLASH-WIFI-{artifact_id[-8:]}-{datetime.now(_tz.utc).strftime('%Y%m%d%H%M%S')}"
            new_artifact = UpdateArtifact(
                artifact_id=new_artifact_id,
                artifact_type="flashable_disk_image",
                filename=result["filename"],
                storage_path=result["output_path"],
                size_bytes=result["size_bytes"],
                sha256=result["sha256"],
                signed_by=None,
                created_at=datetime.now(_tz.utc),
                manifest_json=None,
            )
            db_write.add(new_artifact)
            db_write.commit()
            _wifi_inject_status.update({
                "running": False,
                "result": {
                    "artifact_id": new_artifact_id,
                    "filename": result["filename"],
                    "sha256": result["sha256"],
                    "size_bytes": result["size_bytes"],
                    "wifi_ssid": wifi_ssid,
                },
                "error": None,
            })
            progress(f"✅ WiFi-injiceret artifact registreret: {new_artifact_id}")
        finally:
            db_write.close()

    except Exception as exc:
        log.exception("[wifi-inject] Fejl")
        _wifi_inject_status["running"] = False
        _wifi_inject_status["error"] = str(exc)


@app.post("/api/admin/edge-provisioning/inject-wifi")
def inject_wifi_endpoint(
    body: InjectWifiRequest,
    _user=require_role("super_admin", "admin"),
):
    """Injectér WiFi-konfiguration i et eksisterende flashbart image."""
    with _wifi_inject_lock:
        if _wifi_inject_status.get("running"):
            raise HTTPException(status_code=409, detail="En WiFi-injektion kører allerede")

        _wifi_inject_status.update({
            "running": True, "progress": ["Starter WiFi-injektion..."],
            "error": None, "result": None,
            "artifact_id": body.artifact_id, "wifi_ssid": body.wifi_ssid,
        })

    from database import SessionLocal as _SessionLocal
    t = _threading.Thread(
        target=_run_wifi_inject,
        args=(body.artifact_id, body.wifi_ssid, body.wifi_password,
              body.wifi_country, body.wifi_method, _SessionLocal,
              body.camera_id),
        daemon=True,
        name="wifi-inject",
    )
    t.start()
    return {
        "status": "started",
        "artifact_id": body.artifact_id,
        "message": "WiFi-injektion startet — poll /api/admin/edge-provisioning/wifi-inject-status",
    }


@app.get("/api/admin/edge-provisioning/wifi-inject-status")
def wifi_inject_status(_user=require_role("super_admin", "admin")):
    """Hent status for igangværende WiFi-injektion."""
    return _wifi_inject_status


@app.post("/api/admin/edge-provisioning/build-image")
def build_edge_bootstrap_image(
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """
    Byg og registrer et signeret Edge Bootstrap Image manifest.

    Indeholder:
    - SBOM fra seneste kendte edge-inventory (os_packages, venv_packages)
    - Hardening-profil og call-home-konfiguration
    - GPG-signeret manifest registreret som UpdateArtifact (type: edge_bootstrap_image)

    Bemærk: selve SD-kort/disk-image build sker uden for headenden (cross-compilation).
    Dette endpoint producerer det signerede manifest som en ny edge verificerer mod.
    """
    created_at = now_utc()
    artifact_id = f"TL-EDGE-IMG-{created_at:%Y%m%d%H%M%S}"

    # Collect SBOM from most recently reporting real edge inventory
    inventories = (
        db.query(DeviceInventory)
        .order_by(DeviceInventory.inventory_reported_at.desc())
        .all()
    )
    sbom_source: DeviceInventory | None = None
    for inv in inventories:
        if _is_placeholder_device(inv.device_id):
            continue
        if inv.os_packages or inv.venv_packages:
            sbom_source = inv
            break

    os_sbom: list[dict] = []
    venv_sbom: list[dict] = []
    if sbom_source:
        try:
            raw_os = json.loads(sbom_source.os_packages or "[]")
            os_sbom = raw_os if isinstance(raw_os, list) else []
        except Exception:
            os_sbom = []
        try:
            raw_venv = json.loads(sbom_source.venv_packages or "[]")
            venv_sbom = raw_venv if isinstance(raw_venv, list) else []
        except Exception:
            venv_sbom = []

    # Determine headend URL and app version from current release
    root = _repo_root()
    commit = _git_text(["rev-parse", "HEAD"]) or "unknown"
    ref = _git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "main"
    headend_url = _headend_api_url(db, os.getenv("TIMELAPSE_HEADEND_URL"))

    manifest = {
        "schema": "timelapse.edge_bootstrap_image.v1",
        "artifact_id": artifact_id,
        "artifact_type": "edge_bootstrap_image",
        "headend_source_commit": commit,
        "headend_source_ref": ref,
        "call_home": {
            "endpoint": f"{headend_url}/bootstrap",
            "auth": "short-lived bootstrap token (BootstrapToken)",
            "tls": "required",
        },
        "hardening_profile": {
            "ssh_password_auth": "disabled_in_production",
            "allowed_users": ["timelapse"],
            "firewall": "deny_inbound_except_debug_profile",
            "agent_integrity": "sha256_verified_before_start",
            "artifact_verification": "gpg_signed_manifest_required",
            "audit_logging": "siem_after_first_contact",
        },
        "required_outputs": [
            "image file (arm64 Debian/Ubuntu base)",
            "sha256 checksum",
            "signed manifest (this file)",
            "SBOM / package inventory",
            "hardening evidence",
            "restore/update test evidence",
        ],
        "sbom": {
            "source_device": sbom_source.device_id if sbom_source else None,
            "reported_at": sbom_source.inventory_reported_at.isoformat() if sbom_source and sbom_source.inventory_reported_at else None,
            "os_package_count": len(os_sbom),
            "venv_package_count": len(venv_sbom),
            "os_packages": os_sbom,
            "venv_packages": venv_sbom,
        },
        "edge_constraints": {
            "edge_requires_direct_internet": False,
            "edge_requires_direct_github": False,
            "headend_is_update_authority": True,
        },
        "controls": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        "created": {
            "by": current_user.username,
            "at": created_at.isoformat(),
        },
    }
    manifest_json = _canonical_json(manifest)
    manifest_sha = _sha256_text(manifest_json)
    signature, signed_by = _sign_payload(manifest_json)

    artifact = UpdateArtifact(
        artifact_id=artifact_id,
        artifact_type="edge_bootstrap_image",
        version=commit,
        source_commit=commit,
        source_ref=ref,
        filename=f"{artifact_id}.manifest.json",
        storage_path=str(root),
        size_bytes=len(manifest_json.encode()),
        sha256=manifest_sha,
        manifest_json=manifest_json,
        sbom_ref=f"sbom:{sbom_source.device_id}:{sbom_source.inventory_reported_at.isoformat()}" if sbom_source and sbom_source.inventory_reported_at else None,
        signature=signature,
        signed_by=signed_by,
        signed_at=created_at,
        created_at=created_at,
    )
    db.add(artifact)
    db.commit()
    return {
        **_artifact_to_dict(artifact),
        "sbom_summary": {
            "source_device": sbom_source.device_id if sbom_source else None,
            "os_packages": len(os_sbom),
            "venv_packages": len(venv_sbom),
        },
        "next_steps": [
            f"Download manifest: GET /api/updates/artifacts/{artifact_id}",
            "Brug manifest SBOM til at reproducere SD-kort image med arm64 build pipeline.",
            "Verificer GPG-signatur inden image distribuertion til nye edges.",
            "Klik 'Klargør Edge' for at generere bootstrap token til første call-home.",
        ],
    }


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
    local_sftp_path = _os.path.join(SFTP_INCOMING, "_backups", _sanitize_device_id(device_id), filename)

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
        "sftp_path": local_sftp_path,
        "at":       now_utc().isoformat(),
    }
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("Edge backup komplet for %s: %s (%d KB)",
             device_id, filename, payload.get("size_kb", 0))
    return {"status": "ok", "path": final_path}


@app.post("/api/admin/backup/edge-upload/{device_id}")
async def upload_edge_backup(
    device_id: str,
    backup: UploadFile = File(...),
    sha256: str = Form(""),
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    """Modtag Edge backup-arkiv via API pull-model."""
    import os as _os
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)
    filename = _sanitize_filename(backup.filename or f"{_sanitize_device_id(device_id)}-edge-backup.tar.gz")
    if not filename.endswith((".tar.gz", ".tgz")):
        raise HTTPException(status_code=400, detail="Edge backup skal være tar.gz/tgz")
    nas = _get_nas_path()
    backup_root = nas if (nas and _os.path.isdir(nas)) else "/tmp"
    dest_dir = _os.path.join(backup_root, "edge-backups", _sanitize_device_id(device_id))
    _os.makedirs(dest_dir, exist_ok=True)
    dest = _os.path.join(dest_dir, filename)
    hasher = hashlib.sha256()
    size = 0
    with open(dest, "wb") as out:
        while True:
            chunk = await backup.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            hasher.update(chunk)
            out.write(chunk)
    actual_sha = hasher.hexdigest()
    if sha256 and actual_sha.lower() != sha256.lower():
        try:
            _os.unlink(dest)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="sha256 mismatch")

    existing = json.loads(device.device_config or "{}")
    existing["backup_requested"] = False
    existing["backup_complete"] = {
        "filename": filename,
        "size_kb": size // 1024,
        "path": dest,
        "sha256": actual_sha,
        "transport": "api",
        "at": now_utc().isoformat(),
    }
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("Edge backup upload komplet for %s: %s (%d KB)", device_id, filename, size // 1024)
    return {"status": "ok", "path": dest, "sha256": actual_sha, "size_kb": size // 1024}


@app.get("/api/admin/backup/edge-status/{device_id}")
def edge_backup_status(device_id: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    """Hent backup status for en edge enhed."""
    _ensure_capture_device_access(db, _user, device_id)
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
def lab_store_params(
    device_id: str,
    payload: dict,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    """Edge poster live kamera-parametre til headend efter get_params kommando."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["camera_params"] = payload.get("params", [])
    if "profile" in payload:
        existing["camera_profile"] = payload.get("profile") or {}
    existing.pop("lab_command", None)
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("LAB params stored for %s: %d params", device_id, len(existing["camera_params"]))
    return {"status": "ok"}


@app.post("/api/lab/{device_id}/get-params")
def lab_get_params(device_id: str, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Queue get-params kommando til edge."""
    _ensure_capture_device_access(db, _user, device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "get_params"}
    existing.pop("lab_result", None)
    device.device_config = json.dumps(existing)
    db.commit()
    log.info("LAB get-params queued for %s", device_id)
    return {"status": "ok"}


@app.get("/api/lab/{device_id}/previews")
def list_previews(device_id: str, limit: int = 20, _user=require_role("viewer"), db: Session = Depends(get_db)):
    """List recent preview images for a device."""
    _ensure_capture_device_access(db, _user, device_id)
#Peter     import re as _re
    preview_dir = _sftp_base_path() / "_lab" / device_id
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


@app.post("/api/lab/{device_id}/preview-file")
async def receive_lab_preview_file(
    device_id: str,
    preview: UploadFile = File(...),
    manifest: str = Form(default="{}"),
    _auth: None = Depends(_verify_device_token),
):
    """Receive a lab preview frame from an Edge device without creating a capture row."""
    filename = Path(preview.filename or "").name
    if not filename.startswith("preview_") or not filename.lower().endswith((".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="Invalid preview filename")
    preview_dir = _sftp_base_path() / "_lab" / device_id
    preview_dir.mkdir(parents=True, exist_ok=True)
    dest = preview_dir / filename
    with open(dest, "wb") as fh:
        while True:
            chunk = await preview.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    try:
        meta = json.loads(manifest or "{}")
    except Exception:
        meta = {}
    log.info("LAB preview uploaded for %s: %s (%d bytes)", device_id, filename, dest.stat().st_size)
    return {"status": "ok", "filename": filename, "size": dest.stat().st_size, "manifest": meta}


@app.get("/api/lab/{device_id}/preview-image/{filename}")
def get_preview_image(device_id: str, filename: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    """Serve a preview image."""
    _ensure_capture_device_access(db, _user, device_id)
    path = _sftp_base_path() / "_lab" / device_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(str(path), media_type="image/jpeg")


@app.get("/api/lab/{device_id}/preview-thumb/{filename}")
def get_preview_thumb(device_id: str, filename: str, _user=require_role("viewer"), db: Session = Depends(get_db)):
    """Serve a thumbnail of a preview image."""
    _ensure_capture_device_access(db, _user, device_id)
    sftp_base = _sftp_base_path()
    src = sftp_base / "_lab" / device_id / filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    thumbs_dir = sftp_base / "_lab" / device_id / ".thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    thumb = thumbs_dir / filename
    if not thumb.exists():
        from PIL import Image
        img = Image.open(src)
        img.thumbnail((400, 400), Image.LANCZOS)
        img.save(str(thumb), "JPEG", quality=75)
    return FileResponse(str(thumb), media_type="image/jpeg")

@app.post("/api/admin/devices/{device_id}/lab-clear-command")
def lab_clear_command(
    device_id: str,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    cfg = json.loads(device.device_config or "{}")
    cfg.pop("lab_command", None)
    device.device_config = json.dumps(cfg)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/devices/{device_id}/lab-clear-params")
def lab_clear_params(
    device_id: str,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    cfg = json.loads(device.device_config or "{}")
    cfg.pop("pending_params", None)
    device.device_config = json.dumps(cfg)
    db.commit()
    return {"status": "ok"}


@app.post("/api/lab/{device_id}/camera-ready")
def lab_camera_ready(
    device_id: str,
    payload: dict,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
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
def wifi_scan(device_id: str, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Request WiFi scan from device."""
    _ensure_capture_device_access(db, _user, device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {"type": "wifi_scan", "requested_at": now_utc().isoformat()}
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "wifi_scan"}

@app.post("/api/lab/{device_id}/wifi/connect")
def wifi_connect(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Request WiFi connection on device."""
    _ensure_capture_device_access(db, _user, device_id)
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device: raise HTTPException(status_code=404)
    ssid     = payload.get("ssid", "")
    password = payload.get("password", "")
    if not ssid: raise HTTPException(status_code=400, detail="ssid required")
    allow_plaintext_wifi = os.getenv(
        "TIMELAPSE_ALLOW_LAB_WIFI_PASSWORDS",
        "0",
    ).lower() in {"1", "true", "yes", "on"}
    if password and (TIMELAPSE_ENV in {"prod", "production"} or not allow_plaintext_wifi):
        raise HTTPException(
            status_code=403,
            detail=(
                "WiFi password transfer via lab_command is disabled. "
                "Use provisioning or set TIMELAPSE_ALLOW_LAB_WIFI_PASSWORDS=1 "
                "only in LAB/staging."
            ),
        )
    existing = json.loads(device.device_config or "{}")
    existing["lab_command"] = {
        "type": "wifi_connect",
        "ssid": ssid,
        "requested_at": now_utc().isoformat()
    }
    if password:
        existing["lab_command"]["password"] = password
    device.device_config = json.dumps(existing)
    db.commit()
    return {"status": "ok", "command": "wifi_connect", "ssid": ssid}

@app.post("/api/lab/{device_id}/wifi/forget")
def wifi_forget(device_id: str, payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Request removal of saved WiFi network."""
    _ensure_capture_device_access(db, _user, device_id)
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
def wifi_result(
    device_id: str,
    payload: dict,
    _auth: None = Depends(_verify_device_token),
    db: Session = Depends(get_db),
):
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
    _ensure_capture_device_access(db, _user, device_id)
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
                "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
                "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
                "ai_tags":        json.loads(c.ai_tags) if hasattr(c, 'ai_tags') and c.ai_tags else None,
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

@app.post("/api/captures/bulk-tags")
def bulk_update_tags(payload: dict, _user=require_role("operator"), db: Session = Depends(get_db)):
    """
    Bulk opdater tags på en liste af captures.
    Body: {"capture_ids": [1,2,3], "add_tags": ["tag1"], "remove_tags": ["tag2"]}
    """
    from database import Capture as _Cap
    import json as _j
    from ai.integration import update_sidecar_with_ai
    capture_ids = payload.get("capture_ids", [])
    add_tags    = [t.lower().strip() for t in payload.get("add_tags", [])]
    remove_tags = [t.lower().strip() for t in payload.get("remove_tags", [])]

    updated = 0
    for cid in capture_ids:
        cap = db.query(_Cap).filter_by(id=cid).first()
        if not cap:
            continue
        if not _capture_is_allowed(db, _user, cap):
            raise HTTPException(status_code=403, detail="Ingen adgang til et eller flere billeder")
        tags = _j.loads(cap.ai_tags) if cap.ai_tags else []
        tags = [t for t in tags if t not in remove_tags]
        tags = list(dict.fromkeys(tags + [t for t in add_tags if t not in tags]))
        cap.ai_tags = _j.dumps(tags, ensure_ascii=False)
        updated += 1
    db.commit()
    return {"updated": updated}

@app.put("/api/captures/{capture_id}/tags")
def update_capture_tags(capture_id: int, payload: dict, _user=require_role("operator"), db: Session = Depends(get_db)):
    """Opdater tags på ét capture. Body: {"tags": ["tag1", "tag2"]}"""
    from database import Capture as _Cap
    import json as _j
    cap = db.query(_Cap).filter_by(id=capture_id).first()
    if not cap:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")
    if not _capture_is_allowed(db, _user, cap):
        raise HTTPException(status_code=403, detail="Ingen adgang til dette billede")
    tags = [t.lower().strip() for t in payload.get("tags", [])]
    cap.ai_tags = _j.dumps(tags, ensure_ascii=False)
    db.commit()
    return {"status": "ok", "tags": tags}

@app.get("/api/ai/qa/search")
def qa_search(
    # QA_MULTI_FILTER_FIXED
    causes:         Optional[str] = None,
    cause:          Optional[str] = None,
    is_anomaly:     Optional[str] = None,
    alarm:          Optional[str] = None,
    min_confidence: Optional[float] = None,
    device_ids:     Optional[str] = None,
    device_id:      Optional[str] = None,
    date_from:      Optional[str] = None,
    date_to:        Optional[str] = None,
    limit:          int = 500,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    """
    Søg captures baseret på QA/AI-analyse resultater.
    ?cause=condensation_on_lens&is_anomaly=true&min_confidence=0.5
    """
    from database import Capture as _Cap
    import json as _j

    from datetime import datetime as _dt2, timedelta as _td2
    q = db.query(_Cap).filter(_Cap.ai_result.isnot(None))
    allowed_device_ids = _allowed_capture_device_ids(db, _user)
    if allowed_device_ids is not None:
        # NB (Fase 3, 2026-07-03): se tilsvarende note i list_captures() — ingen
        # "tomt device-sæt" genvej her heller.
        q = q.filter(_capture_tenant_clause(_user, allowed_device_ids))

    # Multi-device filter
    all_dev = []
    if device_ids:
        all_dev = [d.strip() for d in device_ids.split(",") if d.strip()]
    elif device_id:
        all_dev = [device_id]
    if all_dev:
        if allowed_device_ids is not None:
            forbidden = [d for d in all_dev if d not in allowed_device_ids]
            if forbidden:
                raise HTTPException(status_code=403, detail="Ingen adgang til en eller flere enheder")
        q = q.filter(_Cap.device_id.in_(all_dev))

    # Dato filter i SQL
    if date_from:
        try: q = q.filter(_Cap.captured_at >= _dt2.fromisoformat(date_from))
        except Exception: pass
    if date_to:
        try: q = q.filter(_Cap.captured_at < _dt2.fromisoformat(date_to) + _td2(days=1))
        except Exception: pass

    q = q.order_by(_Cap.captured_at.desc())

    # Multi-cause filter
    all_causes = []
    if causes:
        all_causes = [c.strip() for c in causes.split(",") if c.strip()]
    elif cause:
        all_causes = [cause]

    results = []
    for c in q.limit(limit * 3).all():
        try:
            ai = _j.loads(c.ai_result)
            qa = ai.get("edge_ai") if isinstance(ai.get("edge_ai"), dict) else ai
            if all_causes and qa.get("probable_cause") not in all_causes:
                continue
            if is_anomaly == "true" and not qa.get("is_anomaly"):
                continue
            if is_anomaly == "false" and qa.get("is_anomaly"):
                continue
            if alarm == "true" and not (qa.get("alarm") or qa.get("is_anomaly")):
                continue
            if alarm == "false" and (qa.get("alarm") or qa.get("is_anomaly")):
                continue
            if min_confidence is not None and float(qa.get("confidence", 0)) < min_confidence:
                continue
            results.append({
                "id":             c.id,
                "device_id":      c.device_id,
                "filename":       c.filename,
                "captured_at":    c.captured_at.isoformat() if c.captured_at else None,
                "quality_passed": c.quality_passed,
                "blur_score":     c.blur_score,
                "brightness":     c.brightness_mean,
                "filesize_mb":    round(c.filesize / 1e6, 1) if c.filesize else None,
                "uploaded":       c.uploaded,
                "ai_result":      c.ai_result,
                "edge_qa":        qa,
                "ai_tags":        _j.loads(c.ai_tags) if c.ai_tags else None,
            })
        except Exception:
            pass
        if len(results) >= limit:
            break

    return {"total": len(results), "results": results}

@app.get("/api/admin/notifications")
def get_notifications(_user=require_role("admin"), db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text as _t
        row = db.execute(_t("SELECT value FROM settings WHERE key='notifications'")).fetchone()
        if not row:
            return {}
        cfg = json.loads(row[0])
        if "email" in cfg and cfg["email"].get("password"):
            cfg["email"]["password"] = "••••••••••••••••"
        if "sms" in cfg and cfg["sms"].get("api_token"):
            cfg["sms"]["api_token"] = "••••••••"
        return cfg
    except Exception as e:
        return {}

@app.put("/api/admin/notifications")
def update_notifications(payload: dict, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text as _t
        row = db.execute(_t("SELECT value FROM settings WHERE key='notifications'")).fetchone()
        existing = json.loads(row[0]) if row else {}
        if "email" in payload and "•" in payload["email"].get("password",""):
            payload["email"]["password"] = existing.get("email",{}).get("password","")
        if "sms" in payload and "•" in payload["sms"].get("api_token",""):
            payload["sms"]["api_token"] = existing.get("sms",{}).get("api_token","")
        value = json.dumps(payload, ensure_ascii=False, indent=2)
        if row:
            db.execute(_t("UPDATE settings SET value=:v WHERE key='notifications'"), {"v": value})
        else:
            db.execute(_t("INSERT INTO settings (key, value) VALUES ('notifications', :v)"), {"v": value})
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/notifications/test")
def test_notification(payload: dict, _user=require_role("admin"), db: Session = Depends(get_db)):
    channel = payload.get("channel", "email")
    from sqlalchemy import text as _t
    row = db.execute(_t("SELECT value FROM settings WHERE key='notifications'")).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ingen notifikations-konfiguration")
    config = json.loads(row[0])
    config["min_severity"] = "info"
    test_alarm = {
        "rule_name": "Test notifikation", "rule_id": "test", "severity": "info",
        "device_id": "TL-TEST", "description": "Test fra TimeLapse Pro — systemet virker.",
        "matched_on": ["test:manual"], "confidence": 1.0,
        "triggered_at": datetime.now(timezone.utc).isoformat(), "capture_id": None,
    }
    try:
        from ai.notify import send_email, send_sms, send_teams
        result = False
        if channel == "email":   result = send_email(test_alarm, config)
        elif channel == "sms":   result = send_sms(test_alarm, config)
        elif channel == "teams": result = send_teams(test_alarm, config)
        return {"status": "ok" if result else "failed", "channel": channel}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    _ensure_capture_device_access(db, _user, device_id)
    site_id = payload.get("site_id")
    if site_id:
        site = _ensure_site_access(db, _user, site_id)
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
    device.customer_id = site.customer_id if site_id else None
    db.commit()
    return {"status": "ok"}


# ── Slet capture ──────────────────────────────────────────────────────────────

@app.delete("/api/admin/captures/{capture_id}")
def delete_capture(capture_id: int, _user=require_role("admin"), db: Session = Depends(get_db)):
    """Slet et billede: fil, thumbnail, sidecar JSON og DB-record."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")
    if not _capture_is_allowed(db, _user, capture):
        raise HTTPException(status_code=403, detail="Ingen adgang til dette billede")

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
        deleted["thumbnail"] = _unlink_thumbnail_variants(path, capture.filename)

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
            if not _capture_is_allowed(db, _user, capture):
                results.append({"id": cid, "status": "forbidden"})
                continue
            path = _find_image(capture.device_id, capture.filename)
            if path and path.exists():
                path.unlink(missing_ok=True)
                _unlink_thumbnail_variants(path, capture.filename)
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
def get_exif(
    device_id: str,
    filename: str,
    _user=require_role("viewer"),
    db: Session = Depends(get_db),
):
    """Læs komplet EXIF metadata fra billedfil via exifread."""
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    _ensure_capture_file_access(db, _user, device_id, filename)
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
    _ensure_capture_device_access(db, _user, device_id)
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
    _ensure_capture_device_access(db, _user, device_id)
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


from ai.vocabulary_routes import vocab_router; app.include_router(vocab_router)

from ai.review_api import review_router as _rev_router; app.include_router(_rev_router)


def _aiops_static_scan() -> dict:
    """Lightweight read-only SAST snapshot for AI Ops.

    This is intentionally conservative and produces review signals, not proof of
    vulnerability. It avoids reading generated exports and never returns secret
    values.
    """
    root = _repo_root()
    patterns = {
        "hardcoded_secret_terms": ["password=", "api_key=", "secret=", "token="],
        "shell_execution": ["subprocess.run", "subprocess.check_output", "os.system", "shell=True"],
        "dangerous_file_ops": ["unlink(", "rmtree(", "chmod 777", "chown "],
        "legacy_update_paths": ["git pull", "legacy_git_update", "TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE"],
    }
    skip_parts = {"dist", "exports", "__pycache__", ".git", "venv", "node_modules"}
    findings: list[dict] = []
    scanned = 0
    for path in root.rglob("*"):
        if len(findings) >= 80:
            break
        if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".js", ".sh", ".sql", ".yaml", ".yml"}:
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        try:
            rel = str(path.relative_to(root))
            text_value = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned += 1
        for idx, line in enumerate(text_value.splitlines(), start=1):
            lower = line.lower()
            for category, needles in patterns.items():
                if any(n.lower() in lower for n in needles):
                    snippet = line.strip()
                    for sensitive in ("password", "api_key", "secret", "token"):
                        snippet = _re.sub(rf"({sensitive}\s*[=:]\s*)['\"]?[^'\"\s,]+", rf"\1***", snippet, flags=_re.I)
                    findings.append({
                        "category": category,
                        "file": rel,
                        "line": idx,
                        "snippet": snippet[:180],
                    })
                    break
            if len(findings) >= 80:
                break
    return {"files_scanned": scanned, "findings": findings, "finding_count": len(findings)}


def _aiops_snapshot(db: Session) -> dict:
    device_counts = db.execute(text("""
        SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count
        FROM devices GROUP BY COALESCE(status, 'unknown') ORDER BY count DESC
    """)).fetchall()
    siem_counts = db.execute(text("""
        SELECT COALESCE(severity, 'unknown') AS severity, COUNT(*) AS count
        FROM security_events
        WHERE occurred_at >= now() - interval '24 hours'
        GROUP BY COALESCE(severity, 'unknown')
        ORDER BY count DESC
    """)).fetchall()
    update_counts = db.execute(text("""
        SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count
        FROM pending_updates GROUP BY COALESCE(status, 'unknown') ORDER BY count DESC
    """)).fetchall()
    latest_critical = db.execute(text("""
        SELECT device_id, event_type, severity, occurred_at
        FROM security_events
        WHERE severity IN ('critical', 'CRITICAL', 'ERROR')
        ORDER BY occurred_at DESC LIMIT 5
    """)).fetchall()
    key_data = list_key_management(_user=object(), db=db)
    resilience = resilience_assessment(_user=object(), db=db)
    return {
        "generated_at": now_utc().isoformat(),
        "scope": "read_only_aiops_snapshot",
        "guardrails": {
            "model_may_write_database": False,
            "model_may_execute_commands": False,
            "human_acceptance_required": True,
            "customer_data_minimized": True,
        },
        "cmdb": {
            "device_count_by_status": {r[0]: r[1] for r in device_counts},
            "inventory_rows": db.query(DeviceInventory).count(),
        },
        "siem": {
            "last_24h_by_severity": {r[0]: r[1] for r in siem_counts},
            "latest_critical": [
                {
                    "device_id": r[0],
                    "event_type": r[1],
                    "severity": r[2],
                    "occurred_at": r[3].isoformat() if r[3] else None,
                }
                for r in latest_critical
            ],
        },
        "updates": {
            "by_status": {r[0]: r[1] for r in update_counts},
            "artifact_count": db.query(UpdateArtifact).count(),
            "change_ticket_count": db.query(ChangeTicket).count(),
        },
        "keys": key_data["summary"],
        "resilience": resilience["summary"],
        "sast": _aiops_static_scan(),
    }


def _aiops_fallback(snapshot: dict) -> dict:
    recommendations = []
    if snapshot["keys"].get("missing_edge_api_key", 0):
        recommendations.append({
            "title": "Migrer Edge API credentials",
            "severity": "high",
            "domain": ["IEC62443", "ISO27000", "NIS2"],
            "rationale": f"{snapshot['keys']['missing_edge_api_key']} enheder mangler aktiv key-registry API credential.",
            "proposed_action": "Udsted og roter Edge API credentials via Nøglehåndtering. Fjern legacy tokens efter agent rollout.",
            "requires_acceptance": True,
        })
    if snapshot["keys"].get("missing_signing_key", 0):
        recommendations.append({
            "title": "Udsted Edge signing identities",
            "severity": "high",
            "domain": ["CRA", "IEC62443", "ISO27000"],
            "rationale": "Edge-signaler kan først attesteres stærkt når hver Edge har egen signing key.",
            "proposed_action": "Registrer public signing key per Edge og aktiver krævet request-signering efter migration.",
            "requires_acceptance": True,
        })
    if snapshot["sast"].get("finding_count", 0):
        recommendations.append({
            "title": "Review SAST findings",
            "severity": "medium",
            "domain": ["ISO27000", "CRA"],
            "rationale": f"Den statiske scanner fandt {snapshot['sast']['finding_count']} review-signaler.",
            "proposed_action": "Gennemgå findings og opret change tickets for reelle sårbarheder.",
            "requires_acceptance": True,
        })
    if not recommendations:
        recommendations.append({
            "title": "Ingen kritiske AI Ops fund i baseline",
            "severity": "low",
            "domain": ["SABSA", "ISO27000"],
            "rationale": "Read-only snapshot viser ingen umiddelbar højrisikoindikator.",
            "proposed_action": "Fortsæt overvågning og kør assessment igen efter næste deployment.",
            "requires_acceptance": False,
        })
    return {
        "mode": "deterministic_fallback",
        "summary": "Ollama var ikke tilgængelig eller returnerede ikke gyldigt JSON; anbefalinger er lavet deterministisk fra snapshot.",
        "risk_level": "high" if any(r["severity"] == "high" for r in recommendations) else "medium",
        "recommendations": recommendations,
        "next_checks": ["SAST review", "DAST smoke tests", "Edge signing key rollout", "artifact rollback drill"],
    }


def _call_ollama_text(prompt: str, model: str = "llama3.2:latest") -> dict | None:
    try:
        import httpx
        resp = httpx.post(
            f"{os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 1800},
            },
            timeout=90,
        )
        resp.raise_for_status()
        raw_text = resp.json().get("response", "")
        match = _re.search(r"(\{.*\})", raw_text, _re.DOTALL)
        return json.loads(match.group(1) if match else raw_text)
    except Exception as exc:
        log.warning("AI Ops Ollama analyse fejlede: %s", exc)
        return None


@app.get("/api/ai/ops/snapshot")
def aiops_snapshot(
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    return _aiops_snapshot(db)


@app.post("/api/ai/ops/analyze")
def aiops_analyze(
    payload: dict | None = None,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    snapshot = _aiops_snapshot(db)
    model = (payload or {}).get("model") or "llama3.2:latest"
    prompt = f"""
Du er TimeLapse Pro AI Ops co-pilot. Du må kun analysere read-only data.
Du må ikke foreslå direkte ændringer uden accept, og du må ikke bede om hemmeligheder.
Vurder CMDB, SIEM, updates, key management, resilience og SAST-signaler.

Returner KUN JSON:
{{
  "mode": "ollama",
  "summary": "kort dansk status",
  "risk_level": "low|medium|high|critical",
  "recommendations": [
    {{
      "title": "kort titel",
      "severity": "low|medium|high|critical",
      "domain": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
      "rationale": "hvorfor",
      "proposed_action": "hvad bør vi gøre",
      "requires_acceptance": true
    }}
  ],
  "next_checks": ["SAST/DAST/pentest/check"]
}}

SNAPSHOT:
{json.dumps(snapshot, ensure_ascii=False)[:24000]}
"""
    analysis = _call_ollama_text(prompt, model=model) or _aiops_fallback(snapshot)
    if not isinstance(analysis, dict) or "recommendations" not in analysis:
        analysis = _aiops_fallback(snapshot)
    return {"snapshot": snapshot, "analysis": analysis}


def _require_openwebui_loopback(request: Request) -> None:
    """Open WebUI tool calls must stay local to Headend."""
    client_host = request.client.host if request.client else ""
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    allowed = {"127.0.0.1", "::1", "localhost"}
    if client_host not in allowed or forwarded_for:
        raise HTTPException(status_code=403, detail="Open WebUI tool access is only allowed from Headend loopback")


def _validate_openwebui_access(request: Request, db: Session) -> User:
    token = request.cookies.get(OPENWEBUI_COOKIE_NAME)
    payload = _decode_token(token) if token else None
    if (
        not payload
        or payload.get("type") != "openwebui_access"
        or payload.get("target") != "openwebui"
        or not _session_is_mfa_verified(payload)
    ):
        raise HTTPException(status_code=401, detail="Open WebUI requires MFA-authenticated TimeLapse access")
    user = db.query(User).filter_by(username=payload.get("sub"), is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not active")
    if user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Open WebUI requires admin role")
    return user


def _openwebui_user_email(user: User) -> str:
    if user.email:
        return user.email.lower()
    return f"{user.username}@timelapse.local".lower()


def _openwebui_user_role(user: User) -> str:
    return "admin" if user.role in ("super_admin", "admin") else "user"


@app.get("/api/openwebui/access/status")
def openwebui_access_status(
    request: Request,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    payload = _session_payload(request)
    mfa_verified = _session_is_mfa_verified(payload)
    return {
        "enabled": True,
        "url": _openwebui_public_url(db),
        "allowed": bool(mfa_verified),
        "mfa_verified": bool(mfa_verified),
        "required_role": ["super_admin", "admin"],
        "expires_minutes": 30,
        "message": "Open WebUI kræver en MFA-verificeret TimeLapse Pro session.",
    }


@app.post("/api/openwebui/access/issue")
def issue_openwebui_access(
    request: Request,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    payload = _session_payload(request)
    if not _session_is_mfa_verified(payload):
        raise HTTPException(status_code=403, detail="Open WebUI kræver MFA-verificeret login")
    max_age = 30 * 60
    access_token = _create_token({
        "type": "openwebui_access",
        "target": "openwebui",
        "sub": current_user.username,
        "role": current_user.role,
        "amr": payload.get("amr", ["mfa"]) if payload else ["mfa"],
        "mfa_verified": True,
    }, expire_hours=0.5)
    resp = JSONResponse(content={
        "ok": True,
        "url": _openwebui_public_url(db),
        "expires_seconds": max_age,
    })
    cookie_domain = _openwebui_cookie_domain(db)
    resp.headers.append(
        "Set-Cookie",
        _cookie_header(OPENWEBUI_COOKIE_NAME, access_token, max_age, domain=cookie_domain),
    )
    log.info("Open WebUI access issued to %s (%s) via MFA-authenticated TimeLapse session", current_user.username, current_user.role)
    return resp


@app.get("/api/openwebui/access/check", include_in_schema=False)
def check_openwebui_access(request: Request, db: Session = Depends(get_db)):
    user = _validate_openwebui_access(request, db)
    return Response(
        status_code=204,
        headers={
            "X-Timelapse-User-Email": _openwebui_user_email(user),
            "X-Timelapse-User-Name": user.username,
            "X-Timelapse-User-Role": _openwebui_user_role(user),
        },
    )


def _openwebui_context(db: Session, area: str = "overview") -> dict:
    snapshot = _aiops_snapshot(db)
    compliance = compliance_cockpit(current_user=type("ToolUser", (), {
        "username": "open-webui-tool",
        "role": "super_admin",
        "customer_id": None,
    })(), db=db)
    device_rows = db.execute(text("""
        SELECT device_id, COALESCE(camera_name, device_id) AS name, COALESCE(status, 'unknown') AS status,
               customer_name, site_name, last_seen
        FROM devices
        ORDER BY last_seen DESC NULLS LAST
        LIMIT 20
    """)).fetchall()
    recent_updates = db.execute(text("""
        SELECT id, update_type, version, severity, status, scope, scope_id, created_at
        FROM pending_updates
        ORDER BY created_at DESC NULLS LAST
        LIMIT 10
    """)).fetchall()
    recent_events = db.execute(text("""
        SELECT device_id, event_type, severity, occurred_at
        FROM security_events
        ORDER BY occurred_at DESC NULLS LAST
        LIMIT 10
    """)).fetchall()
    return {
        "generated_at": now_utc().isoformat(),
        "scope": "open_webui_read_only_headend_tool",
        "area": area,
        "guardrails": {
            "read_only": True,
            "may_execute_commands": False,
            "may_write_database": False,
            "actions_require_signed_change_ticket_or_user_acceptance": True,
            "edge_is_pull_or_call_home_only": True,
            "edge_direct_internet_not_required": True,
            "standards": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        },
        "system": {
            "name": "TimeLapse Pro",
            "headend_role": "authoritative update, CMDB, SIEM, AI Ops and compliance node",
            "normal_edge_communication": "Edge calls home to Headend; Headend does not push directly to Edge except manual SSH debug tunnel.",
        },
        "summary": {
            "devices_by_status": snapshot["cmdb"]["device_count_by_status"],
            "siem_last_24h_by_severity": snapshot["siem"]["last_24h_by_severity"],
            "updates_by_status": snapshot["updates"]["by_status"],
            "approval_queue": compliance["summary"]["approval_queue"],
            "compliance_controls": compliance["summary"]["controls"],
            "sast_findings": snapshot["sast"]["finding_count"],
            "keys": snapshot["keys"],
            "resilience": snapshot["resilience"],
        },
        "devices": [
            {
                "device_id": r[0],
                "name": r[1],
                "status": r[2],
                "customer": r[3],
                "site": r[4],
                "last_seen": r[5].isoformat() if r[5] else None,
            }
            for r in device_rows
        ],
        "recent_updates": [
            {
                "id": r[0],
                "type": r[1],
                "version": r[2],
                "severity": r[3],
                "status": r[4],
                "scope": r[5],
                "scope_id": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in recent_updates
        ],
        "recent_security_events": [
            {
                "device_id": r[0],
                "event_type": r[1],
                "severity": r[2],
                "occurred_at": r[3].isoformat() if r[3] else None,
            }
            for r in recent_events
        ],
        "operator_guidance": [
            "Svar på dansk og forklar tydeligt om noget er observation, risiko eller anbefalet handling.",
            "Foreslå aldrig direkte ændringer uden at nævne at de skal accepteres i UI eller via signeret change ticket.",
            "Ved edge-opdateringer skal svaret respektere call-home/pull-modellen og manglende internetadgang på edge.",
            "Ved compliance-spørgsmål skal SABSA, IEC62443, ISO27000, NIS2 og CRA vurderes samlet.",
        ],
    }


def _openwebui_public_url(db: Session | None = None) -> str:
    fallback = (
        os.getenv("OPENWEBUI_PUBLIC_URL")
        or os.getenv("TIMELAPSE_PUBLIC_URL")
        or os.getenv("BASE_URL")
        or "http://127.0.0.1:8080"
    )
    if db is not None:
        return _get_setting(db, "openwebui_public_url", fallback).rstrip("/")
    local_db = SessionLocal()
    try:
        return _get_setting(local_db, "openwebui_public_url", fallback).rstrip("/")
    finally:
        local_db.close()


def _openwebui_cookie_domain(db: Session | None = None) -> str | None:
    fallback = os.getenv("OPENWEBUI_COOKIE_DOMAIN", "")
    if db is not None:
        value = _get_setting(db, "openwebui_cookie_domain", fallback).strip()
    else:
        local_db = SessionLocal()
        try:
            value = _get_setting(local_db, "openwebui_cookie_domain", fallback).strip()
        finally:
            local_db.close()
    return value or None


def _openwebui_public_base_url() -> str:
    return (
        os.getenv("TIMELAPSE_PUBLIC_URL")
        or os.getenv("BASE_URL")
        or _openwebui_public_url()
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _capture_openwebui_payload(capture: Capture) -> dict:
    from urllib.parse import quote

    device = quote(capture.device_id or "", safe="")
    filename = quote(capture.filename or "", safe="")
    base = _openwebui_public_base_url()
    ai = _json_dict(capture.ai_result)
    tags = _json_list(capture.ai_tags)
    image_url = f"{base}/api/images/{device}/{filename}"
    thumb_url = f"{base}/api/thumbnails/{device}/{filename}"
    return {
        "id": capture.id,
        "device_id": capture.device_id,
        "filename": capture.filename,
        "captured_at": capture.captured_at.isoformat() if capture.captured_at else None,
        "quality": {
            "passed": capture.quality_passed,
            "flag": capture.quality_flag,
            "blur_score": round(capture.blur_score, 1) if capture.blur_score is not None else None,
            "brightness": round(capture.brightness_mean, 1) if capture.brightness_mean is not None else None,
        },
        "ai": {
            "analyzed_at": capture.ai_analyzed_at.isoformat() if capture.ai_analyzed_at else None,
            "tags": tags,
            "scene_dk": ai.get("scene_dk") or ai.get("description"),
            "quality_flag": ai.get("quality_flag"),
            "probable_cause": ai.get("probable_cause"),
            "confidence": ai.get("confidence"),
        },
        "image_url": image_url,
        "thumbnail_url": thumb_url,
        "markdown": f"![{capture.filename}]({image_url})",
    }


def _capture_date_window(date_value: str | None, tz: str = "Europe/Copenhagen") -> tuple[str, str]:
    from datetime import timedelta as _td
    import zoneinfo

    zone = zoneinfo.ZoneInfo(tz)
    raw = (date_value or "today").strip().lower()
    today = datetime.now(zone).date()
    if raw in {"today", "i dag", "idag"}:
        day = today
    elif raw in {"yesterday", "i gaar", "i går", "igaar"}:
        day = today - _td(days=1)
    else:
        try:
            day = datetime.fromisoformat(raw[:10]).date()
        except Exception:
            day = today
    start = datetime(day.year, day.month, day.day, tzinfo=zone).astimezone(timezone.utc)
    end = start + _td(days=1)
    return start.isoformat(), end.isoformat()


def _query_captures_window(
    db: Session,
    date_value: str | None = "today",
    device_id: str | None = None,
    limit: int = 20,
    newest_first: bool = True,
) -> list[Capture]:
    start_iso, end_iso = _capture_date_window(date_value)
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    q = db.query(Capture).filter(
        Capture.captured_at >= start,
        Capture.captured_at < end,
        Capture.captured_at.isnot(None),
    )
    if device_id:
        q = q.filter(Capture.device_id == device_id)
    order = Capture.captured_at.desc() if newest_first else Capture.captured_at.asc()
    return q.order_by(order).limit(max(1, min(int(limit or 20), 200))).all()


def _known_capture_tags(db: Session, max_rows: int = 1000) -> set[str]:
    tags: set[str] = set()
    rows = (
        db.query(Capture.ai_tags)
        .filter(Capture.ai_tags.isnot(None))
        .order_by(Capture.captured_at.desc())
        .limit(max_rows)
        .all()
    )
    for (raw_tags,) in rows:
        tags.update(str(t).lower() for t in _json_list(raw_tags))
    return tags


def _parse_capture_natural_query(query: str, known_tags: set[str]) -> dict:
    text_value = (query or "").strip()
    lower = text_value.lower()
    explicit_tags = set(_re.findall(r"#([\wæøåÆØÅ-]+)", lower))
    explicit_tags.update(t.lower() for t in _re.findall(r'"([^"]+)"', lower))
    mentioned_tags = set()
    for tag in known_tags:
        if not tag:
            continue
        tag_text = tag.lower()
        phrase = tag_text.replace("_", " ")
        if _re.search(rf"(?<![\wæøå]){_re.escape(tag_text)}(?![\wæøå])", lower):
            mentioned_tags.add(tag_text)
        elif phrase != tag_text and _re.search(rf"(?<![\wæøå]){_re.escape(phrase)}(?![\wæøå])", lower):
            mentioned_tags.add(tag_text)
    include_tags = sorted(explicit_tags | mentioned_tags)

    exclude_tags: set[str] = set()
    for marker in ("uden ", "ekskluder ", "undtagen ", "ikke "):
        if marker in lower:
            tail = lower.split(marker, 1)[1][:120]
            exclude_tags.update(tag for tag in known_tags if tag and tag in tail)
            exclude_tags.update(_re.findall(r"#([\wæøåÆØÅ-]+)", tail))
    if any(term in lower for term in ("dagtimerne", "dagtimer", "i dagslys", "dagslys")):
        include_tags.append("dagslys")
    if any(term in lower for term in ("klart sollys", "klar sol", "solrig dag", "solskin")):
        include_tags.extend(["klart_sollys", "solrig_dag"])
    if any(term in lower for term in ("god timelapse belysning", "god belysning", "uden dårligt lys")):
        include_tags.append("god_timelapse_belysning")
    if any(term in lower for term in ("solen ikke skinner direkte", "ikke skinner direkte", "direkte ind i linsen", "sol i linsen", "modlys", "genskin", "refleks")):
        exclude_tags.update({
            "sol_i_linsen", "linse_refleks", "genskin", "irriterende_genskin",
            "flare", "overeksponeret", "udbrændte_højlys", "direkte_sollys", "modlys",
        })

    limit_match = _re.search(r"\b(\d{1,3})\b", lower)
    limit = int(limit_match.group(1)) if limit_match else 20
    if any(term in lower for term in ("jævnt", "jaevnt", "fordel", "spredt", "timelapse")):
        sort = "timelapse_even_spacing"
    elif any(term in lower for term in ("bedste", "skarpeste", "højeste kvalitet", "hoejeste kvalitet")):
        sort = "quality"
    elif "seneste" in lower or "nyeste" in lower:
        sort = "newest"
    elif "ældste" in lower or "aeldste" in lower:
        sort = "oldest"
    else:
        sort = "newest"

    if "i går" in lower or "igår" in lower or "i gaar" in lower or "igaar" in lower:
        date_value = "yesterday"
    elif "i dag" in lower or "idag" in lower:
        date_value = "today"
    else:
        iso_date = _re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", lower)
        date_value = iso_date.group(1) if iso_date else None

    quality_only = any(term in lower for term in ("skarpe", "klare billeder", "klart billede", "ikke slør", "ikke sloer", "quality ok", "gode billeder", "godt billede", "dårligt billede", "daarligt billede"))
    daily_sample = any(term in lower for term in ("billede om dagen", "et billede pr dag", "1 billede pr dag", "dagligt billede"))
    purpose = "timelapse" if "timelapse" in lower or "video" in lower else "search"
    return {
        "query": text_value,
        "date": date_value,
        "limit": max(1, min(limit, 200)),
        "sort": sort,
        "include_tags": include_tags,
        "exclude_tags": sorted(exclude_tags),
        "quality_only": quality_only,
        "daily_sample": daily_sample,
        "purpose": purpose,
    }


def _filter_captures_by_ai(captures: list[Capture], spec: dict) -> list[Capture]:
    include_tags = set(spec.get("include_tags") or [])
    exclude_tags = set(spec.get("exclude_tags") or [])
    filtered = []
    for capture in captures:
        tags = set(str(t).lower() for t in _json_list(capture.ai_tags))
        ai = _json_dict(capture.ai_result)
        haystack = " ".join([
            " ".join(tags),
            str(ai.get("scene_dk") or ""),
            str(ai.get("description") or ""),
            str(ai.get("probable_cause") or ""),
            str(capture.quality_flag or ""),
        ]).lower()
        if spec.get("quality_only") and capture.quality_passed is False:
            continue
        if include_tags and not all(tag in tags or tag in haystack for tag in include_tags):
            continue
        if exclude_tags and any(tag in tags or tag in haystack for tag in exclude_tags):
            continue
        filtered.append(capture)
    return filtered


def _normalise_capture_search_spec(spec: dict, fallback: dict, known_tags: set[str]) -> dict:
    safe = dict(fallback)
    if isinstance(spec, dict):
        safe.update({k: v for k, v in spec.items() if v is not None})

    def _tag_list(value) -> list[str]:
        if not isinstance(value, list):
            return []
        stopwords = {
            "billede", "billeder", "foto", "fotos", "seneste", "nyeste", "ældste", "aeldste",
            "skarpe", "skarp", "bedste", "gode", "godkendte", "i dag", "idag", "today",
            "timelapse", "video", "vælg", "vaelg", "find", "søg", "soeg",
        }
        cleaned = []
        for item in value[:20]:
            tag = str(item).strip().lower().replace("#", "")
            generic = tag in stopwords or any(part in stopwords for part in _re.split(r"[_\s-]+", tag))
            if tag and (tag in known_tags or not generic):
                cleaned.append(tag)
        return sorted(dict.fromkeys(cleaned))

    safe["include_tags"] = _tag_list(safe.get("include_tags"))
    safe["exclude_tags"] = _tag_list(safe.get("exclude_tags"))
    query_lower = str(safe.get("query") or fallback.get("query") or "").lower()
    fallback_include = set(fallback.get("include_tags") or [])
    fallback_exclude = set(fallback.get("exclude_tags") or [])

    def _mentioned(tag: str, fallback_tags: set[str]) -> bool:
        return tag in fallback_tags or tag in query_lower or tag.replace("_", " ") in query_lower

    safe["include_tags"] = [tag for tag in safe["include_tags"] if _mentioned(tag, fallback_include)]
    safe["exclude_tags"] = [tag for tag in safe["exclude_tags"] if _mentioned(tag, fallback_exclude)]
    safe["limit"] = max(1, min(int(safe.get("limit") or fallback.get("limit") or 20), 500))
    safe["sort"] = str(safe.get("sort") or fallback.get("sort") or "newest")
    if safe["sort"] not in {"newest", "oldest", "quality", "timelapse_even_spacing"}:
        safe["sort"] = "newest"
    safe["purpose"] = str(safe.get("purpose") or fallback.get("purpose") or "search")
    if safe["purpose"] not in {"timeline", "tag_search", "timelapse", "openwebui", "search"}:
        safe["purpose"] = "search"
    quality_raw = safe.get("quality_only")
    safe["quality_only"] = str(quality_raw).strip().lower() in {"1", "true", "yes", "ja"} if isinstance(quality_raw, str) else bool(quality_raw)
    if safe["quality_only"] and not fallback.get("quality_only"):
        safe["quality_only"] = False
    daily_raw = safe.get("daily_sample")
    safe["daily_sample"] = str(daily_raw).strip().lower() in {"1", "true", "yes", "ja"} if isinstance(daily_raw, str) else bool(daily_raw)
    if safe["daily_sample"] and not fallback.get("daily_sample"):
        safe["daily_sample"] = False
    if safe["include_tags"] or safe["exclude_tags"]:
        safe["known_tag_matches"] = sorted(set(safe["include_tags"] + safe["exclude_tags"]) & known_tags)
    return safe


def _capture_spec_from_ollama(query: str, known_tags: set[str], purpose: str = "search") -> dict:
    fallback = _parse_capture_natural_query(query, known_tags)
    fallback["purpose"] = purpose or fallback.get("purpose") or "search"
    prompt = f"""
Du er TimeLapse Pro billedsøgnings-parser. Du må kun returnere JSON.
Fortolk dansk/fritekst til sikre filtre. Brug kun tag-felter når brugeren faktisk efterspørger indhold.

Returner KUN JSON:
{{
  "date": "today|yesterday|YYYY-MM-DD|null",
  "date_from": "YYYY-MM-DD|null",
  "date_to": "YYYY-MM-DD|null",
  "include_tags": ["tag"],
  "exclude_tags": ["tag"],
  "quality_only": true,
  "daily_sample": false,
  "min_confidence": null,
  "sort": "newest|oldest|quality|timelapse_even_spacing",
  "limit": 20,
  "purpose": "timeline|tag_search|timelapse|search",
  "explanation": "kort dansk forklaring"
}}

Kendte tags:
{json.dumps(sorted(list(known_tags))[:250], ensure_ascii=False)}

Formål: {purpose}
Brugerforespørgsel: {query[:1000]}
"""
    parsed = _call_ollama_text(prompt, model=os.getenv("TIMELAPSE_QUERY_MODEL", "llama3.2:latest"))
    return _normalise_capture_search_spec(parsed or {}, fallback, known_tags)


def _parse_capture_range(payload: dict, spec: dict) -> tuple[datetime | None, datetime | None]:
    from datetime import timedelta as _td

    date_value = payload.get("date") or spec.get("date")
    if date_value and str(date_value).lower() not in {"null", "none"}:
        start_iso, end_iso = _capture_date_window(str(date_value))
        return datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso)

    start_raw = payload.get("date_from") or spec.get("date_from")
    end_raw = payload.get("date_to") or spec.get("date_to")
    start_dt = None
    end_dt = None
    if start_raw and str(start_raw).lower() not in {"null", "none"}:
        try:
            start_dt = datetime.fromisoformat(str(start_raw)[:10]).replace(tzinfo=timezone.utc)
        except Exception:
            start_dt = None
    if end_raw and str(end_raw).lower() not in {"null", "none"}:
        try:
            end_dt = datetime.fromisoformat(str(end_raw)[:10]).replace(tzinfo=timezone.utc) + _td(days=1)
        except Exception:
            end_dt = None
    return start_dt, end_dt


def _query_capture_candidates(db: Session, payload: dict, spec: dict) -> list[Capture]:
    q = db.query(Capture).filter(Capture.captured_at.isnot(None))
    candidate_ids = payload.get("candidate_ids")
    if isinstance(candidate_ids, list) and candidate_ids:
        ids = []
        for raw_id in candidate_ids[:5000]:
            try:
                ids.append(int(raw_id))
            except Exception:
                pass
        if ids:
            q = q.filter(Capture.id.in_(ids))
    else:
        start_dt, end_dt = _parse_capture_range(payload, spec)
        if start_dt:
            q = q.filter(Capture.captured_at >= start_dt)
        if end_dt:
            q = q.filter(Capture.captured_at < end_dt)

    device_ids = payload.get("device_ids") or payload.get("device_id")
    if isinstance(device_ids, str):
        device_ids = [d.strip() for d in device_ids.split(",") if d.strip()]
    if isinstance(device_ids, list) and device_ids:
        q = q.filter(Capture.device_id.in_([str(d) for d in device_ids[:100]]))

    sort = spec.get("sort")
    if sort == "oldest" or spec.get("purpose") == "timelapse":
        q = q.order_by(Capture.captured_at.asc())
    else:
        q = q.order_by(Capture.captured_at.desc())
    return q.limit(max(100, min(int(payload.get("candidate_limit") or 3000), 5000))).all()


def _allowed_capture_device_ids(db: Session, user: User | None) -> set[str] | None:
    if _is_platform_admin(user):
        return None
    if not user or not getattr(user, "customer_id", None):
        return set()
    site_ids = [row[0] for row in db.query(Site.id).filter(Site.customer_id == user.customer_id).all()]
    devices = db.query(Device.device_id).filter(
        (Device.customer_id == user.customer_id) | (Device.site_id.in_(site_ids))
    ).all()
    return {row[0] for row in devices}


def _capture_tenant_clause(user: User | None, allowed_device_ids: set[str]):
    """SQL-betingelse til brug i stedet for et rent `Capture.device_id.in_(...)`-filter,
    når man skal håndhæve tenant-isolation på Capture-rækker.

    Fase 3 (2026-07-03, Claude) — se Claude_Kritisk_Statusgennemgang_2026-07-03.md
    §2.4/§2.5: et rent device_id-baseret tjek er et LIVE opslag på "hvilke devices
    tilhører denne kunde LIGE NU". Hvis en fysisk Edge-enhed sidenhen genbruges og
    tildeles en ANDEN kunde, ville et rent device_id-filter fejlagtigt give den nye
    kunde adgang til alle gamle billeder taget mens enheden tilhørte den forrige kunde
    — en reel, konkret lækage på tværs af kunder over tid.

    Denne funktion foretrækker i stedet `Capture.customer_id`, som fryses på
    optagelsestidspunktet (v12-migration, `_resolve_capture_camera_customer()`), og
    falder kun tilbage til det gamle device-baserede opslag for rækker der endnu ikke
    er backfillet (`customer_id IS NULL`) — se
    `headend/tools/backfill_capture_camera_customer.py`. Denne fallback fjernes ikke
    aktivt, men bliver effektivt dødt, når backfillen er kørt komplet i produktion.

    Kald kun denne funktion når `allowed_device_ids` ikke er `None` (dvs. brugeren IKKE
    er platform-admin) — platform-admins skal fortsat se alt, uden filter.

    VIGTIGT: håndhæver eksplicit "ingen adgang" (`false()`) hvis brugeren mangler
    `customer_id` — ellers ville `Capture.customer_id == None` blive oversat til
    `IS NULL` af SQLAlchemy og fejlagtigt matche alle endnu ubackfillede rækker på
    tværs af ALLE kunder for sådan en bruger.
    """
    if not user or not getattr(user, "customer_id", None):
        return _sql_false()
    return or_(
        Capture.customer_id == user.customer_id,
        and_(Capture.customer_id.is_(None), Capture.device_id.in_(allowed_device_ids)),
    )


def _ensure_capture_device_access(db: Session, user: User | None, device_id: str) -> None:
    allowed = _allowed_capture_device_ids(db, user)
    if allowed is not None and device_id not in allowed:
        raise HTTPException(status_code=403, detail="Ingen adgang til denne enhed")


def _capture_is_allowed(db: Session, user: User | None, capture: Capture) -> bool:
    if _is_platform_admin(user):
        return True
    if not user or not getattr(user, "customer_id", None):
        return False
    # Fase 3 (2026-07-03): foretræk capture.customer_id (frosset ved optagelsestidspunkt)
    # frem for et live device→kunde-opslag — se _capture_tenant_clause() ovenfor for
    # den fulde begrundelse (gen-tildelte Edge-enheder må ikke "tage billedhistorikken
    # med sig" til en ny kunde).
    capture_customer_id = getattr(capture, "customer_id", None)
    if capture_customer_id:
        return capture_customer_id == user.customer_id
    allowed = _allowed_capture_device_ids(db, user)
    return allowed is None or capture.device_id in allowed


def _ensure_capture_file_access(db: Session, user: User | None, device_id: str, filename: str) -> Capture:
    """Require a DB capture row and enforce tenant access before serving files."""
    _ensure_capture_device_access(db, user, device_id)
    capture = db.query(Capture).filter_by(device_id=device_id, filename=filename).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    if not _capture_is_allowed(db, user, capture):
        raise HTTPException(status_code=403, detail="Ingen adgang til dette billede")
    return capture


def _capture_quality_score(capture: Capture) -> float:
    score = 0.0
    if capture.quality_passed is True:
        score += 40.0
    if capture.blur_score is not None:
        score += min(float(capture.blur_score), 100.0) * 0.35
    if capture.brightness_mean is not None:
        brightness = float(capture.brightness_mean)
        score += max(0.0, 30.0 - abs(128.0 - brightness) / 4.5)
    ai = _json_dict(capture.ai_result)
    try:
        score += float(ai.get("confidence") or 0) * 15.0
    except Exception:
        pass
    return score


def _select_evenly_spaced(captures: list[Capture], limit: int) -> list[Capture]:
    if len(captures) <= limit:
        return captures
    selected = []
    for idx in range(limit):
        source_idx = round(idx * (len(captures) - 1) / max(limit - 1, 1))
        selected.append(captures[source_idx])
    return selected


def _select_captures_for_spec(captures: list[Capture], spec: dict) -> list[Capture]:
    filtered = _filter_captures_by_ai(captures, spec)
    limit = max(1, min(int(spec.get("limit") or 20), 500))
    sort = spec.get("sort")
    if spec.get("daily_sample"):
        by_day: dict[str, list[Capture]] = {}
        for capture in sorted(filtered, key=lambda c: c.captured_at or datetime.min):
            if not capture.captured_at:
                continue
            by_day.setdefault(capture.captured_at.date().isoformat(), []).append(capture)
        selected = []
        for day in sorted(by_day):
            day_captures = by_day[day]
            selected.append(max(day_captures, key=_capture_quality_score))
        return selected[:limit]
    if sort == "quality":
        filtered = sorted(filtered, key=_capture_quality_score, reverse=True)
    elif sort == "timelapse_even_spacing":
        filtered = _select_evenly_spaced(filtered, limit)
    elif sort == "oldest" or spec.get("purpose") == "timelapse":
        filtered = sorted(filtered, key=lambda c: c.captured_at or datetime.min)
    else:
        filtered = sorted(filtered, key=lambda c: c.captured_at or datetime.min, reverse=True)
    return filtered[:limit]


@app.post("/api/ai/captures/natural-search")
def ai_capture_natural_search(
    payload: dict,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if _user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query mangler")
    purpose = str(payload.get("purpose") or "search")
    known_tags = _known_capture_tags(db)
    spec = _capture_spec_from_ollama(query, known_tags, purpose=purpose)
    if payload.get("limit"):
        try:
            spec["limit"] = max(1, min(int(payload.get("limit")), 500))
        except Exception:
            pass
    candidates = _query_capture_candidates(db, payload, spec)
    if not _is_platform_admin(_user):
        # Fase 3 (2026-07-03): genbrug _capture_is_allowed() i stedet for et rent
        # device_id-filter, så tenant-isolation her følger samme customer_id-først-logik
        # (med device-fallback for ubackfillede rækker) som resten af Capture-fladen.
        candidates = [c for c in candidates if _capture_is_allowed(db, _user, c)]
    selected = _select_captures_for_spec(candidates, spec)
    images = [_capture_openwebui_payload(c) for c in selected]
    selected_ids = [c.id for c in selected]
    candidate_ids = [c.id for c in candidates]
    return {
        "mode": "ollama" if spec.get("explanation") else "deterministic_fallback",
        "query": query,
        "selection": spec,
        "total_candidates": len(candidates),
        "total_matches": len(selected),
        "results": images,
        "capture_ids": selected_ids,
        "selected_ids": selected_ids,
        "excluded_ids": [cid for cid in candidate_ids if cid not in set(selected_ids)] if purpose == "timelapse" else [],
        "suggested_ui_filters": {
            "tag_search_include": spec.get("include_tags") or [],
            "tag_search_exclude": spec.get("exclude_tags") or [],
            "date": spec.get("date"),
            "date_from": spec.get("date_from"),
            "date_to": spec.get("date_to"),
            "quality_only": spec.get("quality_only"),
            "sort": spec.get("sort"),
        },
        "answer_hint": "Resultatet er read-only. Brug selected_ids til UI-udvalg, og kræv brugeraccept før ændringer eller render.",
    }


def _aiops_question_fallback(question: str, area: str, snapshot: dict) -> dict:
    recommendations = _aiops_fallback(snapshot).get("recommendations", [])
    risk_level = "high" if snapshot.get("siem", {}).get("latest_critical") else "medium"
    return {
        "mode": "deterministic_fallback",
        "answer": "Ollama returnerede ikke gyldigt JSON. Her er en deterministisk read-only vurdering baseret på seneste snapshot.",
        "risk_level": risk_level,
        "recommendations": recommendations[:5],
        "evidence": {
            "area": area,
            "question": question,
            "cmdb_summary": snapshot.get("cmdb"),
            "siem_summary": snapshot.get("siem"),
            "updates_summary": snapshot.get("updates"),
            "keys_summary": snapshot.get("keys"),
        },
        "suggested_filters": {},
    }


@app.post("/api/ai/ops/query")
def aiops_query(
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    question = str(payload.get("question") or "").strip()[:1200]
    if not question:
        raise HTTPException(status_code=400, detail="question mangler")
    area = str(payload.get("area") or "overview").strip()[:40] or "overview"
    snapshot = _aiops_snapshot(db)
    prompt = f"""
Du er TimeLapse Pro GRC/AI Ops co-pilot. Du må kun analysere read-only data.
Du må ikke foreslå shell-kommandoer som allerede udført, og du må ikke bede om hemmeligheder.
Vurder altid med SABSA, IEC 62443, ISO 27000, NIS2 og CRA i baghovedet.
Svar praktisk på dansk for en admin.

Returner KUN JSON:
{{
  "mode": "ollama",
  "answer": "kort, konkret svar",
  "risk_level": "low|medium|high|critical",
  "recommendations": [
    {{
      "title": "kort titel",
      "severity": "low|medium|high|critical",
      "domain": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
      "rationale": "hvorfor",
      "proposed_action": "næste handling",
      "requires_acceptance": true
    }}
  ],
  "evidence": {{"key": "kort evidens"}},
  "suggested_filters": {{"severity": "", "device_id": "", "event_type": ""}}
}}

Område: {area}
Spørgsmål: {question}
SNAPSHOT:
{json.dumps(snapshot, ensure_ascii=False, default=str)[:26000]}
"""
    analysis = _call_ollama_text(prompt, model=os.getenv("TIMELAPSE_OPS_MODEL", "llama3.2:latest"))
    if not isinstance(analysis, dict) or "answer" not in analysis:
        analysis = _aiops_question_fallback(question, area, snapshot)
    return {
        "question": question,
        "area": area,
        "analysis": analysis,
        "snapshot_excerpt": {
            "cmdb": snapshot.get("cmdb"),
            "siem": snapshot.get("siem"),
            "updates": snapshot.get("updates"),
            "keys": snapshot.get("keys"),
        },
    }


@app.get("/api/openwebui/tools/openapi.json", include_in_schema=False)
def openwebui_tools_openapi(request: Request):
    _require_openwebui_loopback(request)
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "TimeLapse Pro Read-only Operations Tools",
            "version": "1.0.0",
            "description": "Read-only tools for Open WebUI to answer questions about TimeLapse Pro status, operations, updates and compliance.",
        },
        "servers": [{"url": "http://127.0.0.1:8000"}],
        "paths": {
            "/api/openwebui/tools/system-context": {
                "get": {
                    "operationId": "timelapse_get_system_context",
                    "summary": "Get TimeLapse Pro status, drift and compliance context",
                    "description": "Use this before answering questions about TimeLapse Pro status, devices, failures, updates, compliance, AI Ops or operation.",
                    "parameters": [{
                        "name": "area",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": ["overview", "devices", "updates", "compliance", "aiops", "siem", "backup", "help"],
                            "default": "overview",
                        },
                    }],
                    "responses": {"200": {"description": "Read-only system context"}},
                }
            },
            "/api/openwebui/tools/ask": {
                "post": {
                    "operationId": "timelapse_ask_system_question",
                    "summary": "Ask for relevant TimeLapse Pro context for a user question",
                    "description": "Returns concise read-only context and guardrails for answering a TimeLapse Pro operational question.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "area": {"type": "string"},
                            },
                            "required": ["question"],
                        }}},
                    },
                    "responses": {"200": {"description": "Question-specific context"}},
                }
            },
            "/api/openwebui/tools/help-topics": {
                "get": {
                    "operationId": "timelapse_get_help_topics",
                    "summary": "List things Open WebUI can help with in TimeLapse Pro",
                    "description": "Use this when the user asks what the Timelapse assistant can help with.",
                    "responses": {"200": {"description": "Supported help topics and boundaries"}},
                }
            },
            "/api/openwebui/tools/latest-captures": {
                "get": {
                    "operationId": "timelapse_get_latest_captures",
                    "summary": "Get latest TimeLapse Pro images for a day",
                    "description": "Use this when the user asks to show latest images, newest pictures, today's captures or recent thumbnails. Returns markdown image URLs.",
                    "parameters": [
                        {"name": "date", "in": "query", "required": False, "schema": {"type": "string", "default": "today"}},
                        {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": 2, "minimum": 1, "maximum": 20}},
                        {"name": "device_id", "in": "query", "required": False, "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "Latest captures with image and thumbnail URLs"}},
                }
            },
            "/api/openwebui/tools/select-captures": {
                "post": {
                    "operationId": "timelapse_select_captures_from_text",
                    "summary": "Select TimeLapse Pro captures from natural language",
                    "description": "Use this for natural language image/tag/timelapse selection, e.g. latest two from today, images with crane but without rain, or timelapse frames without blurry images.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "device_id": {"type": "string"},
                                "date": {"type": "string"},
                                "limit": {"type": "integer", "default": 20},
                            },
                            "required": ["query"],
                        }}},
                    },
                    "responses": {"200": {"description": "Selected captures and suggested UI filters"}},
                }
            },
        },
    }


@app.get("/api/openwebui/tools/system-context", include_in_schema=False)
def openwebui_system_context(
    request: Request,
    area: str = "overview",
    db: Session = Depends(get_db),
):
    _require_openwebui_loopback(request)
    return _openwebui_context(db, area=area)


@app.post("/api/openwebui/tools/ask", include_in_schema=False)
def openwebui_ask_system_question(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
):
    _require_openwebui_loopback(request)
    question = str(payload.get("question") or "").strip()[:1000]
    area = str(payload.get("area") or "overview").strip()[:40] or "overview"
    context = _openwebui_context(db, area=area)
    return {
        "question": question,
        "context": context,
        "answer_contract": {
            "language": "da-DK",
            "style": "kort, praktisk og tydeligt",
            "must_state_uncertainty": True,
            "must_not_claim_to_have_changed_system": True,
            "for_action_requests": "Forklar trin eller foreslå change ticket; udfør ikke ændringer fra Open WebUI.",
        },
    }


@app.get("/api/openwebui/tools/latest-captures", include_in_schema=False)
def openwebui_latest_captures(
    request: Request,
    date: str = "today",
    limit: int = 2,
    device_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _require_openwebui_loopback(request)
    captures = _query_captures_window(db, date, device_id=device_id, limit=limit, newest_first=True)
    images = [_capture_openwebui_payload(c) for c in captures]
    return {
        "date": date,
        "count": len(images),
        "images": images,
        "markdown_gallery": "\n\n".join(image["markdown"] for image in images),
        "answer_hint": "Vis billederne med markdown_gallery og opsummer tidspunkt, device og QA/AI-status kort.",
    }


@app.post("/api/openwebui/tools/select-captures", include_in_schema=False)
def openwebui_select_captures(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
):
    _require_openwebui_loopback(request)
    known_tags = _known_capture_tags(db)
    spec = _parse_capture_natural_query(str(payload.get("query") or ""), known_tags)
    if payload.get("date"):
        spec["date"] = payload.get("date")
    if payload.get("limit"):
        try:
            spec["limit"] = max(1, min(int(payload.get("limit")), 200))
        except Exception:
            pass
    newest_first = spec["sort"] != "oldest"
    base_limit = max(100, spec["limit"] * 5)
    captures = _query_captures_window(
        db,
        spec.get("date") or "today",
        device_id=payload.get("device_id"),
        limit=base_limit,
        newest_first=newest_first,
    )
    selected = _filter_captures_by_ai(captures, spec)[:spec["limit"]]
    images = [_capture_openwebui_payload(c) for c in selected]
    return {
        "selection": spec,
        "count": len(images),
        "capture_ids": [image["id"] for image in images],
        "images": images,
        "markdown_gallery": "\n\n".join(image["markdown"] for image in images[:12]),
        "suggested_ui_filters": {
            "tag_search_include": spec["include_tags"],
            "tag_search_exclude": spec["exclude_tags"],
            "date": spec.get("date") or "today",
            "quality_only": spec["quality_only"],
            "timelapse_frame_ids": [image["id"] for image in images] if spec["purpose"] == "timelapse" else [],
        },
        "answer_hint": "Forklar hvilke filtre du brugte. Hvis count er 0, foreslå bredere søgning eller at AI-tags mangler.",
    }


@app.get("/api/openwebui/tools/help-topics", include_in_schema=False)
def openwebui_help_topics(request: Request):
    _require_openwebui_loopback(request)
    return {
        "topics": [
            "Aktuel driftstatus for Headend, Edge-enheder, kameraer og AI-analyse",
            "Visning af seneste billeder fra i dag eller en valgt dato",
            "Naturlig sprogudvælgelse af billeder til tagsøgning og timelapse-forvalg",
            "Forklaring af fejl, røde checks, manglende billeder, offline enheder og SIEM-events",
            "Update/patch status, approval-kø, signerede artifacts og change ticket-flow",
            "Compliance posture mod SABSA, IEC62443, ISO27000, NIS2 og CRA",
            "Backup/resilience, bare metal restore, edge-provisionering og call-home begrænsninger",
            "Praktisk hjælp til hvor i UI en handling normalt udføres",
        ],
        "boundaries": [
            "Read-only fra Open WebUI i første fase",
            "Ingen shell-kommandoer eller databaseændringer",
            "Ingen hemmeligheder eller tokens returneres",
            "Ændringer kræver UI-accept eller signeret change ticket",
        ],
    }
