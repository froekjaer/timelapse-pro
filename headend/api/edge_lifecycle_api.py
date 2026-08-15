"""WP-1 Edge lifecycle admin router.

The Trust Service boundary will absorb this surface during WP-2. Keeping the
routes outside ``main.py`` already enforces the architecture ratchet.
"""

from __future__ import annotations

from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Device, KeyCredential, get_db, now_utc
from services.edge_lifecycle import (
    LifecycleTransitionError,
    get_or_create_lifecycle_record,
    legacy_credential_paths_remaining,
    reconcile_all_devices,
    transition_lifecycle,
)


class EdgeLifecycleTransitionPayload(BaseModel):
    state: Literal[
        "manufactured", "prepared", "media_written", "bootstrap_pending",
        "bootstrap_authenticated", "hardware_verified", "enrolled",
        "credentialed", "assigned", "commissioned", "active", "degraded",
        "quarantined", "revoked", "retired",
    ]
    reason: str


def create_edge_lifecycle_router(
    require_role: Callable,
    sanitize_device_id: Callable[[str], str],
    audit_key_event: Callable,
    reconcile_edge_lifecycle: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/admin/edge-lifecycle", tags=["edge-lifecycle"])

    @router.post("/reconcile")
    def reconcile_edge_lifecycle_inventory(
        current_user=require_role("super_admin", "admin"),
        db: Session = Depends(get_db),
    ):
        summary = reconcile_all_devices(db, actor=current_user.username)
        db.commit()
        return {
            "ok": True,
            "summary": summary,
            "legacy_credential_paths_remaining": legacy_credential_paths_remaining(db),
        }

    @router.post("/{device_id}/transition")
    def transition_edge_lifecycle_state(
        device_id: str,
        payload: EdgeLifecycleTransitionPayload,
        current_user=require_role("super_admin", "admin"),
        db: Session = Depends(get_db),
    ):
        device_id = sanitize_device_id(device_id)
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Edge ikke fundet")
        record = get_or_create_lifecycle_record(db, device, actor=current_user.username)
        try:
            transition = transition_lifecycle(
                db,
                record,
                payload.state,
                actor=current_user.username,
                reason=payload.reason,
            )
        except LifecycleTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if payload.state in {"revoked", "retired"}:
            active = db.query(KeyCredential).filter_by(
                entity_type="edge",
                entity_id=device_id,
                status="active",
            )
            for credential in active.all():
                credential.status = "revoked"
                credential.revoked_at = now_utc()
                credential.revoked_by = current_user.username
                credential.revoke_reason = payload.reason
                audit_key_event(db, credential, "revoked_by_lifecycle", current_user.username, {
                    "device_id": device_id,
                    "lifecycle_state": payload.state,
                    "reason": payload.reason,
                })
            device.api_token = None
            device.status = payload.state
        reconcile_edge_lifecycle(db, device, actor=current_user.username, reason=payload.reason)
        db.commit()
        return {
            "ok": True,
            "device_id": device_id,
            "from_state": transition.from_state,
            "to_state": transition.to_state,
        }

    return router
