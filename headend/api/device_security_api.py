"""Per-device local-access security controls (factory-default TOTP toggle)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Device, Event, get_db


log = logging.getLogger(__name__)


def _sanitize_device_id(device_id: str) -> str:
    """Sanitér device_id — samme regel som headend/main.py::_sanitize_device_id."""
    if not device_id:
        raise HTTPException(status_code=400, detail="Ugyldigt device_id")
    device_id = device_id.strip().upper()
    if not re.match(r'^[A-Za-z0-9_-]{3,60}$', device_id):
        raise HTTPException(status_code=400, detail="Ugyldigt device_id format")
    if '..' in device_id or '/' in device_id or '\\' in device_id:
        raise HTTPException(status_code=400, detail="Ugyldigt device_id")
    return device_id


class FactoryTotpToggleRequest(BaseModel):
    disabled: bool


def create_device_security_router(require_role: Callable) -> APIRouter:
    """Build the router with the application's established auth hook."""
    router = APIRouter(prefix="/api/admin/devices", tags=["device-security"])

    @router.post("/{device_id}/factory-totp")
    def set_device_factory_totp_disabled(
        device_id: str,
        body: FactoryTotpToggleRequest,
        current_user=require_role("super_admin", "admin"),
        db: Session = Depends(get_db),
    ):
        """Slå den delte fabriksstandard-TOTP-fallback til/fra for én fysisk Edge.

        Fallback'en (JBSWY3DPEHPK3PXP) er enabled som default, så en enhed uden
        egen bt_totp_secret stadig kan nås under idriftsættelse. Sæt disabled=true
        når enheden er bekræftet konfigureret (har modtaget config fra headend),
        for at lukke den delte kode af for netop denne enhed — edge'ens lokale
        TOTP-service fejler allerede fail-closed på et tomt secret.
        """
        device = db.query(Device).filter_by(device_id=_sanitize_device_id(device_id)).first()
        if not device:
            raise HTTPException(status_code=404, detail="Edge ikke fundet")
        device.factory_totp_disabled = body.disabled
        db.add(Event(
            device_id=device.device_id,
            level="INFO",
            category="security",
            message=f"Fabriksstandard TOTP {'deaktiveret' if body.disabled else 'aktiveret'} for enhed",
            extra=json.dumps({"changed_by": current_user.username, "disabled": body.disabled}, ensure_ascii=False),
        ))
        db.commit()
        log.info("Factory TOTP disabled=%s for %s (af %s)", body.disabled, device.device_id, current_user.username)
        return {
            "device_id": device.device_id,
            "factory_totp_disabled": device.factory_totp_disabled,
        }

    return router
