"""
TimeLapse Pro — Physical camera hardware CMDB
==============================================================================
2026-08-08 (Claude, Peter): "det fysiske kamera mangler i vores CMDB" — the
`cameras` table already had `model`/`serial_number` columns but nothing ever
populated them. This module receives what the Edge reads live from the
camera itself over PTP/gphoto2 (see
edge/camera/drivers/gphoto2_driver.py::collect_hardware_inventory) and
compares the reported firmware against a small hand-maintained reference
table (headend/migrations/v27_camera_hardware_inventory.sql) so the UI can
show "opdatering tilgængelig" without any live internet lookup — there is no
reliable, stable firmware-version API from either Canon or Nikon.

Auth/access-control helpers are imported lazily from `main` inside function
bodies — the established pattern in this codebase (see
api/thumbnails_api.py) — main.py imports this router near the END of its own
definition, so a top-level `from main import ...` here would fail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Camera, CameraFirmwareReference, Capture, DeviceAssignment, get_db

router = APIRouter()

_ROLE_HIERARCHY = {
    "super_admin": {"super_admin", "admin", "operator", "viewer"},
    "admin":       {"admin", "operator", "viewer"},
    "operator":    {"operator", "viewer"},
    "viewer":      {"viewer"},
}


def _require_role(*roles: str):
    """Local re-implementation of main.require_role() — see
    api/thumbnails_api.py's identical helper for the full rationale."""
    def _check(request: Request, db: Session = Depends(get_db)):
        from main import get_current_user
        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        return user
    return Depends(_check)


def _active_camera_for_device(db: Session, device_id: str) -> Optional[Camera]:
    assignment = (
        db.query(DeviceAssignment)
        .filter_by(device_id=device_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .order_by(DeviceAssignment.assigned_at.desc())
        .first()
    )
    return db.query(Camera).filter_by(id=assignment.camera_id).first() if assignment else None


def _firmware_status(camera: Camera, db: Session) -> dict:
    """Compare a camera's reported firmware against the reference table.

    Exact-string comparison only — vendors don't format version strings
    consistently enough to safely order/compare numerically across brands,
    and a false "up to date" is worse than an occasional false "check this".
    """
    if not camera.model or not camera.firmware_version:
        return {"known": False, "update_available": None, "latest_version": None}
    ref = (
        db.query(CameraFirmwareReference)
        .filter(CameraFirmwareReference.model == camera.model)
        .first()
    )
    if not ref:
        return {"known": False, "update_available": None, "latest_version": None}
    return {
        "known": True,
        "update_available": camera.firmware_version.strip() != ref.latest_version.strip(),
        "latest_version": ref.latest_version,
        "rated_shutter_actuations": ref.rated_shutter_actuations,
        "notes": ref.notes,
        "source_url": ref.source_url,
    }


def report_camera_hardware_inventory(db: Session, device_id: str, payload: dict) -> dict:
    """Called by the Edge (device-token authenticated) after a capture that
    also collected hardware telemetry — see edge/agent.py::_report_inventory.
    """
    camera = _active_camera_for_device(db, device_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Intet kamera tildelt {device_id} lige nu")

    if payload.get("model"):
        camera.model = payload["model"]
    if payload.get("serial_number"):
        camera.serial_number = payload["serial_number"]
    for field in (
        "firmware_version", "battery_level_pct", "storage_free_mb",
        "storage_free_images_est", "shutter_count", "shutter_count_source",
    ):
        if payload.get(field) is not None:
            setattr(camera, field, payload[field])
    camera.hardware_inventory_at = datetime.now(timezone.utc)

    if isinstance(payload.get("observed_settings"), dict):
        import json as _json
        camera.observed_settings = _json.dumps(payload["observed_settings"], ensure_ascii=False)
        camera.observed_settings_at = datetime.now(timezone.utc)
    db.commit()

    return {"ok": True, "camera_id": camera.id, **_firmware_status(camera, db)}


def create_camera_hardware_router() -> APIRouter:
    @router.get("/api/admin/cameras/{camera_id}/hardware")
    def get_camera_hardware(
        camera_id: str,
        db: Session = Depends(get_db),
        _user=_require_role("viewer"),
    ):
        camera = db.query(Camera).filter_by(id=camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Kamera ikke fundet")
        known_capture_count = (
            db.query(func.count(Capture.id)).filter(Capture.camera_id == camera_id).scalar() or 0
        )
        observed_settings = None
        if camera.observed_settings:
            import json as _json
            try:
                observed_settings = _json.loads(camera.observed_settings)
            except (ValueError, TypeError):
                observed_settings = None
        return {
            "camera_id":                camera.id,
            "model":                    camera.model,
            "serial_number":            camera.serial_number,
            "firmware_version":         camera.firmware_version,
            "battery_level_pct":        camera.battery_level_pct,
            "storage_free_mb":          camera.storage_free_mb,
            "storage_free_images_est":  camera.storage_free_images_est,
            "shutter_count":            camera.shutter_count,
            "shutter_count_source":     camera.shutter_count_source,
            "hardware_inventory_at":    camera.hardware_inventory_at.isoformat() if camera.hardware_inventory_at else None,
            "known_capture_count":      known_capture_count,
            "firmware": _firmware_status(camera, db),
            # Hvad en tekniker-session sidst faktisk læste af kameraet — se
            # v28-migrationens docstring. Vises som reference, ikke anvendt
            # automatisk; sammenlign selv med kameraets gemte profil.
            "observed_settings":        observed_settings,
            "observed_settings_at":     camera.observed_settings_at.isoformat() if camera.observed_settings_at else None,
        }

    @router.get("/api/admin/camera-firmware-reference")
    def list_firmware_reference(
        db: Session = Depends(get_db),
        _user=_require_role("viewer"),
    ):
        rows = db.query(CameraFirmwareReference).order_by(CameraFirmwareReference.manufacturer, CameraFirmwareReference.model).all()
        return [
            {
                "id": r.id, "manufacturer": r.manufacturer, "model": r.model,
                "latest_version": r.latest_version, "rated_shutter_actuations": r.rated_shutter_actuations,
                "notes": r.notes, "source_url": r.source_url,
                "updated_by": r.updated_by, "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    @router.put("/api/admin/camera-firmware-reference")
    def upsert_firmware_reference(
        payload: dict,
        db: Session = Depends(get_db),
        user=_require_role("admin", "super_admin"),
    ):
        manufacturer = (payload.get("manufacturer") or "").strip()
        model = (payload.get("model") or "").strip()
        latest_version = (payload.get("latest_version") or "").strip()
        if not manufacturer or not model or not latest_version:
            raise HTTPException(status_code=400, detail="manufacturer, model og latest_version er påkrævet")
        ref = (
            db.query(CameraFirmwareReference)
            .filter_by(manufacturer=manufacturer, model=model)
            .first()
        )
        if not ref:
            ref = CameraFirmwareReference(manufacturer=manufacturer, model=model, latest_version=latest_version, updated_by=user.username)
            db.add(ref)
        ref.latest_version = latest_version
        ref.rated_shutter_actuations = payload.get("rated_shutter_actuations")
        ref.notes = payload.get("notes")
        ref.source_url = payload.get("source_url")
        ref.updated_by = user.username
        ref.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "id": ref.id}

    return router
