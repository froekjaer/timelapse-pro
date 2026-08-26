# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — admin_settings_api.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Small admin-settings surfaces: password policy, notifications config, and
generic system settings CRUD.

Montér i main.py:
    from api.admin_settings_api import router as admin_settings_router
    app.include_router(admin_settings_router)

Endpoints:
    GET  /api/admin/password-policy
    PUT  /api/admin/password-policy
    GET  /api/admin/notifications
    PUT  /api/admin/notifications
    POST /api/admin/notifications/test
    GET  /api/admin/settings
    PUT  /api/admin/settings

Extracted from main.py (2026-08-26, Phase 1 of the main.py modularization
plan). Folds three small, previously-scattered route clusters into one
module rather than three near-empty files — the plan's guidance was to
avoid over-fragmenting into tiny domain files. Named admin_settings_api.py
(not settings_api.py) to disambiguate from the already-extracted
ai/settings_api.py, which mounts at /api/settings (AI/Ollama runtime
config) — a completely different path and concern from this module's
/api/admin/settings (generic system settings) and /api/admin/notifications.

Deliberately NOT folded in here: /api/admin/config-defaults and
/api/admin/config-resolution, despite living in the same "small admin
settings" mental bucket the plan originally grouped them under. Reading
their actual code revealed deep coupling to _resolve_config_hierarchy,
_merge_missing_defaults, _FACTORY_CONFIG_DEFAULTS and friends — the
broader device/customer/site config-resolution machinery this codebase
already tracks as its own, much larger cluster (~570 lines, shared with
backup/retention). Moving them here would have meant either duplicating
that machinery or reaching back into main.py for it, defeating the point.
They belong with that larger extraction instead, not this one.

require_role comes from auth.py at module scope (Phase 0). The one
main.py-wide utility this domain still needs (_get_setting, used broadly
across main.py, not specific to this domain) is lazy-imported at its one
call site, matching the same idiom used in the previous extractions.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Settings, get_db
from auth import require_role

router = APIRouter(tags=["Admin Settings"])


def _get_password_policy(db: Session) -> dict:
    """Hent password-politik fra settings."""
    from main import _get_setting
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


@router.get("/api/admin/password-policy")
def get_password_policy(
    _user=require_role("super_admin", "admin", "operator", "viewer"),
    db: Session = Depends(get_db)
):
    """Returner gældende password-politik."""
    return _get_password_policy(db)


@router.put("/api/admin/password-policy")
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


@router.get("/api/admin/notifications")
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

@router.put("/api/admin/notifications")
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

@router.post("/api/admin/notifications/test")
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

_SETTINGS_SECRET_MASK = "••••••••"
_SETTINGS_SECRET_KEY_MARKERS = ("password", "secret", "token", "api_key", "apikey", "private_key")


def _is_secret_setting_key(key: str) -> bool:
    """C-05: hvilke nøgler i den flade `settings`-tabel skal maskeres ved readback.
    Substring-baseret (ikke en fast liste) så nye password/secret/token/api_key-agtige
    nøgler også dækkes automatisk fremover, uden at kræve en kode-ændring hver gang."""
    lowered = key.lower()
    return any(marker in lowered for marker in _SETTINGS_SECRET_KEY_MARKERS)


@router.get("/api/admin/settings")
def get_settings(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Returner alle system settings. Secret-agtige nøgler (password/secret/token/api_key)
    maskeres til '••••••••' — enhver admin kunne før dette hente fx sftp_password og
    bt_totp_secret i klartekst (C-05). PUT nedenfor ignorerer masken hvis den sendes
    uændret tilbage, så UI'en kan redigere andre felter uden at nulstille secrets."""
    rows = db.execute(text("SELECT key, value FROM settings")).fetchall()
    return {
        row[0]: (_SETTINGS_SECRET_MASK if _is_secret_setting_key(row[0]) and row[1] else row[1])
        for row in rows
    }

@router.put("/api/admin/settings")
def update_settings(payload: dict, _user=require_role("super_admin"), db: Session = Depends(get_db)):
    """Opdater system settings. Secret-agtige nøgler springes over hvis værdien er den
    maskerede placeholder ('••••••••') — dvs. uændret siden GET — så et gemt formular-felt
    aldrig ved et uheld overskriver en eksisterende secret med selve masken."""
    for key, value in payload.items():
        if _is_secret_setting_key(key) and str(value) == _SETTINGS_SECRET_MASK:
            continue
        existing = db.execute(text("SELECT id FROM settings WHERE key = :k"), {"k": key}).fetchone()
        if existing:
            db.execute(text("UPDATE settings SET value = :v WHERE key = :k"), {"v": str(value), "k": key})
        else:
            db.execute(text("INSERT INTO settings (key, value) VALUES (:k, :v)"), {"k": key, "v": str(value)})
    db.commit()
    return {"ok": True}
