# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — commissioning_key.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Per-device disable lifecycle for the shared headend commissioning key.

Montér i main.py:
    from commissioning_key import router as commissioning_key_router
    app.include_router(commissioning_key_router, prefix="/api/admin")

Endpoints:
    GET  /api/admin/devices/{device_id}/commissioning-key
    POST /api/admin/devices/{device_id}/commissioning-key/disable

Background (2026-08-24, per Peter): ~/.ssh/timelapse_headend_ed25519 is a
single keypair shared across the whole fleet, injected into orangepi/pi/
ubuntu/timelapse's authorized_keys at provisioning time
(headend/tools/inject_edge_image.py). It stays as a legitimate commissioning
mechanism (initial device bring-up) — this module doesn't retire it — but
each device should be able to disable it once real, per-technician RBAC
access (edge/scripts/technician_authorized_keys.py, the servicetekniker
account) is proven to actually work on that specific device. Same safety
shape as MFA enrollment: prove the new method works before the old one can
be turned off, so an admin can never lock themselves out.

edge/agent.py::_check_servicetekniker_login_evidence() reports (via the
consolidated sync poll, headend/edge_sync.py) whenever it sees a successful
`Accepted publickey for servicetekniker` line in its own sshd journal; that
sets Device.servicetekniker_verified_at here. The disable action is refused
until that timestamp is set. Disabling itself is declarative: this module
only flips Device.commissioning_key_disabled — edge/agent.py's
_apply_commissioning_key_disabled() removes the key from authorized_keys on
the device's own next sync, the same "headend declares desired state, the
root-privileged agent applies it locally" shape as every other device-side
change in this codebase (never headend reaching in over its own SSH access
to edit the device that grants it, which would be circular and fragile).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Device, get_db, now_utc
from auth import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(tags=["Commissioning Key"])


def migrate_commissioning_key_columns(engine) -> None:
    """Additive migration for existing PostgreSQL data, called once from
    main.py::startup(). Same try/except-per-column idiom as
    technician_keys.py's migrations — Postgres has no ADD COLUMN IF NOT
    EXISTS, so a rerun on an already-migrated DB just no-ops per column."""
    columns = [
        ("commissioning_key_disabled", "BOOLEAN DEFAULT FALSE"),
        ("commissioning_key_disabled_at", "TIMESTAMP"),
        ("commissioning_key_disabled_by", "VARCHAR(100)"),
        ("servicetekniker_verified_at", "TIMESTAMP"),
    ]
    try:
        with engine.connect() as conn:
            for col, typ in columns:
                try:
                    conn.execute(text(f"ALTER TABLE devices ADD COLUMN {col} {typ}"))
                    conn.commit()
                    log.info("DB migration commissioning-key: devices.%s tilføjet", col)
                except Exception:
                    pass
    except Exception as exc:
        log.warning("DB migration commissioning-key fejl: %s", exc)


async def _require_admin(request: Request, db: Session = Depends(get_db)):
    """get_current_user comes from auth.py at module scope (2026-08-26) —
    auth.py doesn't depend on main.py, so this is no longer a circular-import
    concern."""
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Kræver admin- eller super_admin-rolle")
    return user


def _status_dict(device: Device) -> dict:
    disabled = bool(device.commissioning_key_disabled)
    verified_at = device.servicetekniker_verified_at
    return {
        "device_id": device.device_id,
        "disabled": disabled,
        "disabled_at": device.commissioning_key_disabled_at.isoformat() if device.commissioning_key_disabled_at else None,
        "disabled_by": device.commissioning_key_disabled_by,
        "servicetekniker_verified_at": verified_at.isoformat() if verified_at else None,
        "can_disable": (not disabled) and verified_at is not None,
    }


@router.get("/devices/{device_id}/commissioning-key")
def get_commissioning_key_status(device_id: str, _user=Depends(_require_admin), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device ikke fundet")
    return _status_dict(device)


@router.post("/devices/{device_id}/commissioning-key/disable")
def disable_commissioning_key(device_id: str, user=Depends(_require_admin), db: Session = Depends(get_db)):
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device ikke fundet")
    if device.commissioning_key_disabled:
        return _status_dict(device)
    if not device.servicetekniker_verified_at:
        raise HTTPException(
            status_code=409,
            detail="Kan ikke deaktivere: intet bekræftet servicetekniker-login registreret for denne enhed endnu",
        )
    device.commissioning_key_disabled = True
    device.commissioning_key_disabled_at = now_utc()
    device.commissioning_key_disabled_by = user.username
    db.commit()
    log.info(
        "Commissioning-nøgle deaktiveret for %s af %s (servicetekniker verificeret %s)",
        device_id, user.username, device.servicetekniker_verified_at,
    )
    return _status_dict(device)
