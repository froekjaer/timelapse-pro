"""Central policy for local Edge diagnostics and camera Live View."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Device, get_db


log = logging.getLogger(__name__)


def create_service_access_router(
    require_role: Callable,
    ensure_device_access: Callable,
    record_siem_events: Callable,
    now_utc: Callable,
) -> APIRouter:
    """Build the router with the application's established auth and audit hooks."""
    router = APIRouter(prefix="/api/admin/devices", tags=["service-access"])

    @router.put("/{device_id}/service-access")
    def set_service_access_policy(
        device_id: str,
        payload: dict,
        user=require_role("admin"),
        db: Session = Depends(get_db),
    ):
        ensure_device_access(db, user, device_id)
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        existing = json.loads(device.device_config or "{}")
        previous = existing.get("service_access") or {}
        try:
            max_duration_s = int(payload.get(
                "live_view_max_duration_s",
                previous.get("live_view_max_duration_s", 180),
            ))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="live_view_max_duration_s skal være et heltal")
        if not 30 <= max_duration_s <= 86400:
            raise HTTPException(status_code=400, detail="Live View maksimum skal være 30-86400 sekunder")

        enabled = bool(payload.get("enabled", previous.get("enabled", True)))
        policy = {
            "enabled": enabled,
            "live_view_enabled": bool(payload.get(
                "live_view_enabled", previous.get("live_view_enabled", True),
            )),
            "live_view_max_duration_s": max_duration_s,
            "allow_continuous_live_view": bool(payload.get(
                "allow_continuous_live_view",
                previous.get("allow_continuous_live_view", False),
            )),
            "interactive_shell_enabled": bool(payload.get(
                "interactive_shell_enabled",
                previous.get("interactive_shell_enabled", False),
            )),
            "updated_at": now_utc().isoformat(),
            "updated_by": user.username,
        }
        existing["service_access"] = policy

        if not enabled:
            debug_mode = existing.get("debug_mode") or {}
            debug_mode.update({
                "enabled": False,
                "disabled_at": now_utc().isoformat(),
                "disabled_reason": "central_service_access_disabled",
            })
            existing["debug_mode"] = debug_mode
            existing["lab_camera_ready"] = False

        device.device_config = json.dumps(existing, ensure_ascii=False)
        device.config_version = hashlib.md5(device.device_config.encode()).hexdigest()
        db.commit()

        try:
            record_siem_events(db, device_id, [{
                "event_type": "service_access_policy_change",
                "severity": "warning" if not enabled else "info",
                "username": user.username,
                "source": "admin_api",
                "raw_message": (
                    f"Lokal service-policy ændret for {device_id}: enabled={enabled}, "
                    f"live_view={policy['live_view_enabled']}, max={max_duration_s}s, "
                    f"continuous={policy['allow_continuous_live_view']}, "
                    f"interactive_shell={policy['interactive_shell_enabled']}"
                ),
                "occurred_at": now_utc().isoformat(),
            }])
            db.commit()
        except Exception as exc:
            log.warning("Kunne ikke logge service_access_policy_change for %s: %s", device_id, exc)

        return {"status": "ok", "device_id": device_id, "service_access": policy}

    return router
