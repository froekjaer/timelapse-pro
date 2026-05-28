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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datetime import timezone as _tz

#Peter:
import re as _re
from sqlalchemy import func, text
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
COOKIE_NAME   = "tl_session"
OPENWEBUI_COOKIE_NAME = "tl_openwebui_access"
OPENWEBUI_COOKIE_DOMAIN = os.getenv("OPENWEBUI_COOKIE_DOMAIN", ".froekjaer.dk")
OPENWEBUI_PUBLIC_URL = os.getenv("OPENWEBUI_PUBLIC_URL", "https://openwebui.froekjaer.dk/")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
def ensure_utc(dt):
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=_tz.utc)

from importer import router as import_router
from ai.settings_api import settings_router
from siem import router as siem_router
from cmdb import router as cmdb_router, report_inventory as _cmdb_report_inventory
from database import (
    BootstrapToken,
    ChangeApproval, ChangeTicket, UpdateArtifact, UpdateTarget,
    Capture, Camera, Customer, ConfigDefaults, Device, DeviceAssignment,
    DeviceInventory, Diagnostic, Event, KeyAuditEvent, KeyCredential,
    PendingUpdate, Settings, Site, SshTunnelLog, User,
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


app = FastAPI(
    title       = "TimeLapse Pro Headend",
    description = "Central control API for TimeLapse Pro edge nodes",
    version     = "1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://timelapse.froekjaer.dk")

app.add_middleware(
    CORSMiddleware,
    allow_origins      = [ALLOWED_ORIGIN],
    allow_methods      = ["*"],
    allow_headers      = ["*"],
    allow_credentials  = True,
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


    # ── AI SETUP ──────────────────────────────────────────────────────────
    try:
        run_ai_migration(engine)
        setup_ai(get_db, _find_image)
        setup_ai_router(get_db, _find_image)
        app.include_router(ai_router)
        log.info("AI integration klar — Ollama: http://localhost:11434")
    except Exception as _ai_err:
        log.warning("AI integration ikke tilgængelig: %s", _ai_err)
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
    def _check(user=Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        return user
    return Depends(_check)





@app.get("/api/auth/session-policy")
def get_session_policy(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Returnerer resolved session policy for den indloggede bruger."""
    if current_user is None:
        raise HTTPException(status_code=401)

    policy = {
        "session_duration_hours": 12,
        "remember_me_days":       30,
        "absolute_max_days":      90,
        "rolling_enabled":        True,
        "remember_me_allowed":    True,
        "mfa_required":           False,
        "webauthn_required":      False,
    }

    try:
        defaults = db.query(ConfigDefaults).first()
        if defaults and defaults.session_policy:
            policy.update(json.loads(defaults.session_policy))

        if current_user.customer_id:
            customer = db.query(Customer).filter_by(id=current_user.customer_id).first()
            if customer and customer.config_overrides:
                overrides = json.loads(customer.config_overrides)
                if "session_policy" in overrides:
                    policy.update(overrides["session_policy"])
    except Exception as e:
        log.warning("session_policy resolver fejl: %s", e)

    # Find godkendte opdateringer til denne enhed
    from database import PendingUpdate as _PU
    from sqlalchemy import or_

    approved = db.query(_PU).filter(
        _PU.status.in_(["approved", "rollback_requested"]),
        or_(
            _PU.scope == "global",
            _PU.scope_id == device_id,
        )
    ).all()

    # Filtrer target_device_ids hvis sat
    filtered = []
    for u in approved:
        if u.target_device_ids:
            targets = json.loads(u.target_device_ids)
            if device_id not in targets:
                continue
        artifact = _find_artifact_for_update(db, u)
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

# ── WebAuthn / FIDO2 ───────────────────────────────────────────────────────

WEBAUTHN_RP_ID   = os.getenv("WEBAUTHN_RP_ID",   "timelapse.froekjaer.dk")
WEBAUTHN_RP_NAME = os.getenv("WEBAUTHN_RP_NAME",  "TimeLapse Pro")
WEBAUTHN_ORIGIN  = os.getenv("WEBAUTHN_ORIGIN",   "https://timelapse.froekjaer.dk")

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

    options = webauthn.generate_registration_options(
        rp_id                    = WEBAUTHN_RP_ID,
        rp_name                  = WEBAUTHN_RP_NAME,
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
        verification = webauthn.verify_registration_response(
            credential          = payload,
            expected_challenge  = challenge,
            expected_rp_id      = WEBAUTHN_RP_ID,
            expected_origin     = WEBAUTHN_ORIGIN,
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
    options = webauthn.generate_authentication_options(
        rp_id             = WEBAUTHN_RP_ID,
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
        verification = webauthn.verify_authentication_response(
            credential          = payload,
            expected_challenge  = challenge,
            expected_rp_id      = WEBAUTHN_RP_ID,
            expected_origin     = WEBAUTHN_ORIGIN,
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
    return {"ok": True}

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
    # MFA check
    if user.mfa_enabled:
        mfa_token = _create_token({"sub": user.username, "type": "mfa_pending"}, expire_hours=5/60)
        log.info("Login MFA påkrævet: %s", user.username)
        return {"mfa_required": True, "mfa_token": mfa_token}
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
        defaults = db.query(ConfigDefaults).first()
        sp = json.loads(defaults.session_policy or "{}") if defaults and defaults.session_policy else {}
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
def logout():
    """Logout — ryd session cookie."""
    from fastapi.responses import JSONResponse as _JR
    _resp = _JR(content={"ok": True})
    _resp.headers.append("Set-Cookie", _delete_cookie_header(COOKIE_NAME))
    _resp.headers.append("Set-Cookie", _delete_cookie_header(OPENWEBUI_COOKIE_NAME, domain=OPENWEBUI_COOKIE_DOMAIN))
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
def me(request: Request, current_user=Depends(get_current_user)):
    """Returnerer brugerinfo og fornyr rolling session cookie."""
    if current_user is None:
        raise HTTPException(status_code=401)
    from fastapi.responses import JSONResponse as _JR
    data = {
        "username":    current_user.username,
        "email":       current_user.email,
        "role":        current_user.role,
        "customer_id": current_user.customer_id,
    }
    # Forny rolling session
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        token = existing
        payload_data = _decode_token(token)
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
            "webauthn_count": int(cred_counts.get(u.id, 0)),
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
        metadata_json=_canonical_json({"bootstrap_token_device_label": token_record.device_label if token_record else None}),
    )
    db.add(credential)
    _audit_key_event(db, credential, "created_by_bootstrap", "bootstrap", {"device_id": req.device_id})
    db.commit()

    base_url   = os.environ.get("BASE_URL", "http://192.168.86.132:8000")
    config_url = f"{base_url}/api/config/{req.device_id}"

    return BootstrapResponse(
        api_token  = api_token,
        config_url = config_url,
        device_id  = req.device_id,
    )



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
        .filter_by(entity_type="edge", entity_id=device_id, key_type="api", secret_hash=token_hash)
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
        await _verify_edge_request_signature(request, active_secret)
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


async def _verify_edge_request_signature(request: Request, secret: str) -> None:
    """Validate optional Edge request signature.

    Legacy devices may omit signatures for now. If signature headers are present,
    they must be correct. This gives immediate tamper/replay metadata without
    breaking existing LAB nodes.
    """
    signature = request.headers.get("X-TLP-Signature")
    if not signature:
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
    body = await request.body()
    body_text = ""
    if body:
        try:
            body_text = _canonical_json(json.loads(body.decode("utf-8")))
        except Exception:
            body_text = body.decode("utf-8", errors="replace")
    signed = "\n".join([request.method.upper(), request.url.path.removeprefix("/api"), timestamp, nonce, body_text])
    expected = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
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
        body = await request.body()
        body_text = ""
        if body:
            try:
                body_text = _canonical_json(json.loads(body.decode("utf-8")))
            except Exception:
                body_text = body.decode("utf-8", errors="replace")
        signed = "\n".join([request.method.upper(), request.url.path.removeprefix("/api"), timestamp, nonce, body_text])
        public_key.verify(base64.b64decode(signature), signed.encode("utf-8"))
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
        "has_secret": bool(credential.secret_hash),
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
        "trusted_release_signers": 0,
    }
    trusted_release_signers = _trusted_release_signers(db)
    counts["trusted_release_signers"] = len(trusted_release_signers)
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
            "status": "warning" if counts["missing_signing_key"] or counts["missing_edge_api_key"] else "pass",
            "title": "Signal mutual authentication",
            "evidence": "Edge API credentials autentificerer Edge til Headend; signing credentials skal bruges til attestation af Edge-signaler og update-resultater.",
            "domains": ["SABSA", "IEC62443", "ISO27000", "NIS2"],
            "recommendation": "Udvid agenten med request-signatures eller mTLS, så Headend validerer signeret payload og Edge validerer Headend-signeret policy/artifact.",
        },
    ]
    return {
        "credentials": rows,
        "devices": device_rows,
        "summary": counts,
        "controls": controls,
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
        metadata_json=_canonical_json(payload.metadata or {}),
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

    base_url = _get_setting(db, "base_url", os.environ.get("BASE_URL", "http://192.168.86.102:8000"))
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
            "environment": u.environment,
            "target_device_ids": json.loads(u.target_device_ids) if u.target_device_ids else None,
            "deployed_count": u.deployed_count or 0,
            "failed_count":   u.failed_count or 0,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
            "approved_by": u.approved_by,
            "deployed_at": u.deployed_at.isoformat() if u.deployed_at else None,
            "rollback_at": u.rollback_at.isoformat() if u.rollback_at else None,
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


def _status_rank(status: str | None) -> int:
    return {
        "pending": 0,
        "approved": 1,
        "rollback_requested": 2,
        "failed": 3,
        "rolled_back": 4,
        "deployed": 5,
        "rejected": 6,
    }.get(status or "", 7)


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
    if status in ("failed", "rolled_back", "rollback_requested"):
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
        device_updates = [u for u in updates if _update_applies_to_device(u, device, inv)]
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
                categories[category["key"]] = {
                    "state": state,
                    "installed": installed,
                    "available": update.version,
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


def _git_text(args: list[str]) -> str | None:
    try:
        result = _subprocess.run(
            ["git", *args],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=10,
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
        root / "edge" / "config",
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
    for signer in _trusted_release_signers(db):
        if artifact.signed_by and artifact.signed_by in {
            signer.get("credential_id"),
            signer.get("gpg_fingerprint"),
        }:
            signer_fingerprint = signer.get("fingerprint")
            break
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
    u.status            = "approved"
    u.approved_at       = now_utc()
    u.approved_by       = current_user.username
    u.environment       = payload.environment or "production"
    if payload.scope:
        u.scope    = payload.scope
        u.scope_id = None if payload.scope == "global" else payload.scope_id
    else:
        u.scope    = u.scope or "device"
    target_ids          = payload.target_device_ids
    u.target_device_ids = json.dumps(target_ids) if target_ids else None
    db.commit()
    log.info("Opdatering godkendt: %s v%s → %s/%s af %s",
             u.update_type, u.version, u.environment, u.scope, current_user.username)
    return {"ok": True}


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


def _approval_queue(db: Session, user: User) -> list[dict]:
    updates = (
        db.query(PendingUpdate)
        .filter(PendingUpdate.status.in_(["pending", "rejected"]))
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
    if update.status not in ("pending", "rejected"):
        raise HTTPException(status_code=400, detail=f"Kan ikke godkende update med status {update.status}")

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
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Promovér en test-godkendt opdatering til produktion."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if u.environment != "test":
        raise HTTPException(status_code=400, detail="Kan kun promovere test-opdateringer")
    if u.status not in ("deployed", "approved"):
        raise HTTPException(status_code=400, detail="Opdatering skal være deployet i test først")
    # Opret ny PendingUpdate til produktion
    prod_update = PendingUpdate(
        update_type       = u.update_type,
        version           = u.version,
        description       = f"[Promoveret fra test] {u.description or ''}",
        severity          = u.severity,
        scope             = u.scope,
        scope_id          = u.scope_id,
        status            = "approved",
        approved_at       = now_utc(),
        approved_by       = current_user.username,
        environment       = "production",
        target_device_ids = u.target_device_ids,
    )
    db.add(prod_update)
    db.commit()
    log.info("Opdatering %d promoveret til produktion af %s", update_id, current_user.username)
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
        from sqlalchemy import or_
        return db.query(PendingUpdate).filter(
            PendingUpdate.update_type == update_type,
            PendingUpdate.scope == "device",
            PendingUpdate.scope_id == device_id,
            or_(PendingUpdate.status == "pending", PendingUpdate.status == "approved"),
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
            "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
            "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
            "ai_tags":        json.loads(c.ai_tags) if hasattr(c, 'ai_tags') and c.ai_tags else None,
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
                return JSONResponse(
                    _json.loads(sidecar_path.read_text(encoding='utf-8')),
                    headers={"Cache-Control": "no-store"},
                )
    # Fallback: flat struktur
    flat = SFTP_BASE / device_id / filename
    if flat.exists():
#Peter        import json as _json
        return JSONResponse(
            _json.loads(flat.read_text(encoding='utf-8')),
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
app.include_router(settings_router)

@app.post("/api/inventory/{device_id}")
def edge_report_inventory(device_id: str, payload: dict, db: Session = Depends(get_db)):
    return _cmdb_report_inventory(device_id=device_id, payload=payload, db=db)


@app.get("/health")
def health():
    return {"status": "ok", "time": now_utc().isoformat()}

from pathlib import Path as _Path
from fastapi.responses import FileResponse
from PIL import Image
def _init_sftp_base():
    from sqlalchemy.orm import Session
    db_gen = get_db()
    db = next(db_gen)
    try:
        return _Path(_get_setting(db, "sftp_base", os.getenv("SFTP_BASE", "/Users/Shared/timelapse/incoming")))
    finally:
        db_gen.close()

SFTP_BASE = _init_sftp_base()

#Peter import re as _re

def _find_image(device_id: str, filename: str) -> Optional[_Path]:
    log.info("_find_image: device=%s filename=%r base=%s", device_id, filename, SFTP_BASE)
    try:
        top = list(SFTP_BASE.iterdir())
        log.info("SFTP_BASE contents: %s", [x.name for x in top])
    except Exception as e:
        log.error("SFTP_BASE iterdir fejl: %s", e)
    """
    Find image — håndterer tre strukturer:
      1. Ny chroot:   SFTP_BASE/{sftp_user}/data/{customer}/{site}/YYYY/MM/DD/filename
      2. Gammel:      SFTP_BASE/{customer}/{site}/YYYY/MM/DD/filename
      3. Flad:        SFTP_BASE/{device_id}/filename
    """
    m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)

        # Struktur 0 — device_id/YYYY/MM/DD/ (primær struktur)
        p = SFTP_BASE / device_id / yyyy / mm / dd / filename
        if p.exists():
            return p

        # Struktur 1 — chroot: sftp_user/data/customer/site/YYYY/MM/DD/
        chroot_glob = f"*/data/*/*/{yyyy}/{mm}/{dd}/{filename}"
        log.info("chroot_glob=%r", chroot_glob)
        matches = list(SFTP_BASE.glob(chroot_glob))
        log.info("chroot matches=%s", matches)
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
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    path = _find_image(device_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path), media_type="image/jpeg")

@app.get("/api/thumbnails/{device_id}/{filename}")
def get_thumbnail(device_id: str, filename: str):
    from urllib.parse import unquote as _unquote
    filename = _unquote(filename)
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

# ── AI INTEGRATION ──────────────────────────────────────────────────────────
from ai.integration import (
    run_ai_migration,
    setup_ai,
    setup_ai_router,
    queue_capture_for_analysis,
    ai_router,
)


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
            session_policy = json.dumps({"session_duration_hours": 12, "remember_me_days": 30, "absolute_max_days": 90, "rolling_enabled": True, "remember_me_allowed": True, "mfa_required": False, "webauthn_required": False}),
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


@app.get("/api/admin/resilience/assessment")
def resilience_assessment(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Backup, restore, provisioning and compliance readiness snapshot."""
    devices = db.query(Device).order_by(Device.device_id).all()
    inventory = db.query(DeviceInventory).order_by(DeviceInventory.device_id).all()
    device_ids = {d.device_id for d in devices}
    tickets = db.query(ChangeTicket).count()
    artifacts = db.query(UpdateArtifact).count()
    active_tokens = db.query(BootstrapToken).filter_by(revoked=False).count()

    settings = {}
    try:
        rows = db.execute(text(
            "SELECT key, value FROM settings WHERE key IN "
            "('backup_nas_path','backup_auto_interval','backup_include_images')"
        )).fetchall()
        settings = {r[0]: r[1] for r in rows}
    except Exception:
        settings = {}

    cmdb_state_rows = [
        inv for inv in inventory
        if getattr(inv, "os_packages", None) or inv.venv_packages or getattr(inv, "software_inventory", None)
    ]
    firmware_rows = [inv for inv in inventory if getattr(inv, "firmware_version", None)]
    backup_complete = []
    backup_requested = []
    for device in devices:
        try:
            cfg = json.loads(device.device_config or "{}")
        except Exception:
            cfg = {}
        if cfg.get("backup_complete"):
            backup_complete.append(device.device_id)
        if cfg.get("backup_requested"):
            backup_requested.append(device.device_id)

    latest_backup_file = _backup_status.get("file")
    latest_backup_exists = bool(latest_backup_file and os.path.exists(latest_backup_file))
    nas_path = settings.get("backup_nas_path")
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
            "pass" if len(cmdb_state_rows) == len(inventory) and inventory else "fail",
            "Installed-state CMDB evidence",
            f"{len(cmdb_state_rows)}/{len(inventory)} inventory rows include package/software state",
            ["IEC62443", "CRA", "SABSA"],
            "All nodes must report hardware, firmware, OS packages, venv and software inventory." if len(cmdb_state_rows) < len(inventory) else "",
        ),
        _resilience_control(
            "pass" if len(firmware_rows) == len(inventory) and inventory else "warning",
            "Firmware inventory",
            f"{len(firmware_rows)}/{len(inventory)} inventory rows include firmware state",
            ["IEC62443", "CRA"],
            "Firmware/bootloader state is needed for bare-metal restore and vulnerability governance." if len(firmware_rows) < len(inventory) else "",
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
            "warning",
            "Bare-metal edge ISO pipeline",
            "blueprint defined; image build/sign/verify pipeline not implemented",
            ["CRA", "IEC62443", "NIS2"],
            "Build ISO/image generator with hardening profile, call-home bootstrap and signed manifest.",
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
            }
            for inv in inventory
            if inv.device_id.lower() != "test"
        ],
        "iso_blueprint": {
            "status": "planned",
            "call_home": "/api/bootstrap with short-lived bootstrap token",
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
def bulk_update_tags(payload: dict, db: Session = Depends(get_db)):
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
        tags = _j.loads(cap.ai_tags) if cap.ai_tags else []
        tags = [t for t in tags if t not in remove_tags]
        tags = list(dict.fromkeys(tags + [t for t in add_tags if t not in tags]))
        cap.ai_tags = _j.dumps(tags, ensure_ascii=False)
        updated += 1
    db.commit()
    return {"updated": updated}

@app.put("/api/captures/{capture_id}/tags")
def update_capture_tags(capture_id: int, payload: dict, db: Session = Depends(get_db)):
    """Opdater tags på ét capture. Body: {"tags": ["tag1", "tag2"]}"""
    from database import Capture as _Cap
    import json as _j
    cap = db.query(_Cap).filter_by(id=capture_id).first()
    if not cap:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")
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

    # Multi-device filter
    all_dev = []
    if device_ids:
        all_dev = [d.strip() for d in device_ids.split(",") if d.strip()]
    elif device_id:
        all_dev = [device_id]
    if all_dev:
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
            if all_causes and ai.get("probable_cause") not in all_causes:
                continue
            if is_anomaly == "true" and not ai.get("is_anomaly"):
                continue
            if is_anomaly == "false" and ai.get("is_anomaly"):
                continue
            if alarm == "true" and not ai.get("alarm"):
                continue
            if alarm == "false" and ai.get("alarm"):
                continue
            if min_confidence is not None and float(ai.get("confidence", 0)) < min_confidence:
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
                "ai_tags":        _j.loads(c.ai_tags) if c.ai_tags else None,
            })
        except Exception:
            pass
        if len(results) >= limit:
            break

    return {"total": len(results), "results": results}

@app.get("/api/admin/notifications")
def get_notifications(db: Session = Depends(get_db)):
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
def update_notifications(payload: dict, db: Session = Depends(get_db)):
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
def test_notification(payload: dict, db: Session = Depends(get_db)):
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
):
    payload = _session_payload(request)
    mfa_verified = _session_is_mfa_verified(payload)
    return {
        "enabled": True,
        "url": OPENWEBUI_PUBLIC_URL,
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
        "url": OPENWEBUI_PUBLIC_URL,
        "expires_seconds": max_age,
    })
    resp.headers.append(
        "Set-Cookie",
        _cookie_header(OPENWEBUI_COOKIE_NAME, access_token, max_age, domain=OPENWEBUI_COOKIE_DOMAIN),
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


def _openwebui_public_base_url() -> str:
    return (
        os.getenv("TIMELAPSE_PUBLIC_URL")
        or os.getenv("BASE_URL")
        or ALLOWED_ORIGIN
        or "https://timelapse.froekjaer.dk"
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
    mentioned_tags = {tag for tag in known_tags if tag and tag in lower}
    include_tags = sorted(explicit_tags | mentioned_tags)

    exclude_tags: set[str] = set()
    for marker in ("uden ", "ekskluder ", "undtagen ", "ikke "):
        if marker in lower:
            tail = lower.split(marker, 1)[1][:120]
            exclude_tags.update(tag for tag in known_tags if tag and tag in tail)
            exclude_tags.update(_re.findall(r"#([\wæøåÆØÅ-]+)", tail))

    limit_match = _re.search(r"\b(\d{1,3})\b", lower)
    limit = int(limit_match.group(1)) if limit_match else 20
    if "seneste" in lower or "nyeste" in lower:
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

    quality_only = any(term in lower for term in ("skarpe", "ikke slør", "ikke sloer", "quality ok", "gode billeder"))
    purpose = "timelapse" if "timelapse" in lower or "video" in lower else "search"
    return {
        "query": text_value,
        "date": date_value,
        "limit": max(1, min(limit, 200)),
        "sort": sort,
        "include_tags": include_tags,
        "exclude_tags": sorted(exclude_tags),
        "quality_only": quality_only,
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
