"""
TimeLapse Pro — Camera location lifecycle: retire, move captures, delete
==========================================================================
2026-08-06 (Claude): extracted from headend/main.py (module ratchet — see
tests/test_architecture_ratchet.py). Peter, correctly: the architecture
baseline exists to force extraction into domain modules as functionality
grows, not to be repeatedly raised as a substitute for it — this module
(plus api/export_api.py) is that extraction for the same-day camera-location
hierarchy work (see Dokumentation/HANDOVER_LOG.md 2026-08-06).

Covers the full lifecycle of a logical camera location independent of its
currently-assigned physical device: retiring an empty one, moving a mistaken
location's captures to the correct one, permanently deleting a location
(database rows only) or its images (database rows AND files, for GDPR
erasure requests), and reading its assignment history / a device's current
camera-location binding.

Auth/access-control helpers (_ensure_site_access, _ensure_customer_access)
are imported lazily from `main` inside each function body — the established
pattern in this codebase (see api/thumbnails_api.py) — main.py imports this
router near the END of its own definition, so a top-level `from main import
...` here would fail (main isn't finished executing yet), but a
function-body import resolves fine at call time.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import Camera, Capture, Customer, DeviceAssignment, Event, Site, get_db, now_utc
from media_paths import _find_image
from api.thumbnails_api import _unlink_thumbnail_variants

log = logging.getLogger("headend")

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
        from main import _mfa_required_for_user, _session_is_mfa_verified, _session_payload, get_current_user
        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
        return user
    return Depends(_check)


def _ensure_site_access(db: Session, user, site_id: str | None):
    from main import _ensure_site_access as _impl
    return _impl(db, user, site_id)


def _ensure_customer_access(user, customer_id: str | None) -> None:
    from main import _ensure_customer_access as _impl
    _impl(user, customer_id)


@router.delete("/api/admin/cameras/{camera_id}")
def retire_empty_camera_location(
    camera_id: str,
    current_user=_require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Retire an unused logical camera location without touching image data.

    A location with captures or a live physical Edge cannot be retired through
    the UI. This prevents accidental loss of historic image navigation.
    """
    camera = db.query(Camera).filter_by(id=camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Kameralokation ikke fundet")
    if camera.site_id:
        _ensure_site_access(db, current_user, camera.site_id)
    elif camera.customer_id:
        _ensure_customer_access(current_user, camera.customer_id)

    active_assignment = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=camera_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .first()
    )
    if active_assignment:
        raise HTTPException(
            status_code=409,
            detail="Kameralokationen har en aktiv Edge-binding og kan ikke slettes.",
        )
    capture_count = db.query(Capture).filter(Capture.camera_id == camera_id).count()
    if capture_count:
        raise HTTPException(
            status_code=409,
            detail=f"Kameralokationen har {capture_count} billeder og kan ikke slettes.",
        )

    camera.retired_at = now_utc()
    db.add(Event(
        device_id="HEADEND",
        level="INFO",
        category="camera_location_retired",
        message=f"Empty camera location retired: {camera.camera_name or camera_id}",
        extra=json.dumps({"camera_id": camera_id, "retired_by": current_user.username}),
    ))
    db.commit()
    return {"ok": True, "camera_id": camera_id, "message": "Tom kameralokation fjernet"}


@router.post("/api/admin/cameras/{camera_id}/move-captures")
def move_camera_captures(
    camera_id: str,
    payload: dict,
    current_user=_require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Flyt alle billeder fra én kamera-lokation til en anden.

    2026-08-06 (Claude, Peter): trygt oprydningsredskab for en fejlagtigt
    oprettet/tildelt kamera-lokation der allerede nåede at få nogle billeder
    (fx tastefejl eller forkert device-tildeling opdaget efter et par
    optagelser) — INGEN billeddata går tabt, kildens rækker flyttes blot. Når
    kilden er tom bagefter kan den fjernes trygt via den eksisterende
    retire_empty_camera_location(). Kilde og mål SKAL tilhøre samme kunde —
    at flytte billeder på tværs af kunder ville være en reel tenant-lækage,
    ikke en oprydning.
    """
    to_camera_id = str(payload.get("to_camera_id") or "").strip()
    if not to_camera_id:
        raise HTTPException(status_code=400, detail="to_camera_id påkrævet")
    if to_camera_id == camera_id:
        raise HTTPException(status_code=400, detail="Kilde og mål er samme kameralokation")

    source = db.query(Camera).filter_by(id=camera_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Kilde-kameralokation ikke fundet")
    target = db.query(Camera).filter_by(id=to_camera_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Mål-kameralokation ikke fundet")

    for cam in (source, target):
        if cam.site_id:
            _ensure_site_access(db, current_user, cam.site_id)
        elif cam.customer_id:
            _ensure_customer_access(current_user, cam.customer_id)
    if source.customer_id != target.customer_id:
        raise HTTPException(status_code=400, detail="Kilde og mål skal tilhøre samme kunde")

    moved = (
        db.query(Capture)
        .filter(Capture.camera_id == camera_id)
        .update(
            {
                Capture.camera_id: to_camera_id,
                Capture.customer_id: target.customer_id,
                Capture.site_id: target.site_id,
            },
            synchronize_session=False,
        )
    )
    db.add(Event(
        device_id="HEADEND",
        level="INFO",
        category="camera_location_captures_moved",
        message=f"{moved} billeder flyttet: {source.camera_name or camera_id} → {target.camera_name or to_camera_id}",
        extra=json.dumps({
            "from_camera_id": camera_id, "to_camera_id": to_camera_id,
            "moved_count": moved, "moved_by": current_user.username,
        }),
    ))
    db.commit()
    return {"ok": True, "moved": moved, "from_camera_id": camera_id, "to_camera_id": to_camera_id}


@router.delete("/api/admin/cameras/{camera_id}/force")
def force_delete_camera_location(
    camera_id: str,
    payload: dict,
    current_user=_require_role("super_admin"),
    db: Session = Depends(get_db),
):
    """Slet en kamera-lokation PERMANENT, inkl. dens billeder — undtagelsen,
    ikke reglen. Til det sjældne tilfælde hvor billederne selv også var en
    fejl (forkert kamera, testoptagelser), modsat move_camera_captures()
    ovenfor der er det trygge standardvalg når billederne er gyldige og bare
    sidder på den forkerte lokation.

    2026-08-06 (Claude, Peter): kun super_admin (ikke almindelig admin, i
    modsætning til de andre kamera-lokations-endpoints ovenfor — bevidst
    højere bjælke for en irreversibel handling). Kræver eksakt match af
    lokationens NUVÆRENDE navn i payload'en som bekræftelse, så et enkelt
    fejlklik ikke kan udløse den. Sletter kun database-rækker (Capture,
    DeviceAssignment, Camera) — billedfiler på disk røres IKKE, da blind
    sti-baseret filsletning drevet af en UI-knap er en markant større og
    separat risiko end at rydde op i kataloget.
    """
    camera = db.query(Camera).filter_by(id=camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Kameralokation ikke fundet")
    if camera.site_id:
        _ensure_site_access(db, current_user, camera.site_id)
    elif camera.customer_id:
        _ensure_customer_access(current_user, camera.customer_id)

    confirm_name = str(payload.get("confirm_name") or "")
    expected_name = camera.camera_name or camera_id
    if confirm_name != expected_name:
        raise HTTPException(
            status_code=400,
            detail=f"Bekræftelse matcher ikke. Indtast lokationens navn præcist: \"{expected_name}\"",
        )

    active_assignment = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=camera_id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .first()
    )
    if active_assignment:
        raise HTTPException(
            status_code=409,
            detail="Kameralokationen har en aktiv Edge-binding og kan ikke slettes.",
        )

    capture_count = db.query(Capture).filter(Capture.camera_id == camera_id).count()
    db.query(Capture).filter(Capture.camera_id == camera_id).delete(synchronize_session=False)
    db.query(DeviceAssignment).filter_by(camera_id=camera_id).delete(synchronize_session=False)
    db.add(Event(
        device_id="HEADEND",
        level="WARNING",
        category="camera_location_force_deleted",
        message=f"Kamera-lokation PERMANENT slettet inkl. {capture_count} billed-rækker: {expected_name}",
        extra=json.dumps({
            "camera_id": camera_id, "camera_name": expected_name,
            "deleted_capture_rows": capture_count, "deleted_by": current_user.username,
        }),
    ))
    db.delete(camera)
    db.commit()
    log.warning(
        "Kamera-lokation %s (%s) permanent slettet af %s inkl. %d billed-rækker",
        expected_name, camera_id, current_user.username, capture_count,
    )
    return {"ok": True, "camera_id": camera_id, "deleted_capture_rows": capture_count}


@router.delete("/api/admin/cameras/{camera_id}/gdpr-delete-captures")
def gdpr_delete_camera_captures(
    camera_id: str,
    payload: dict,
    current_user=_require_role("admin"),
    db: Session = Depends(get_db),
):
    """Slet ALLE billeder for en kamera-lokation som led i en GDPR-anmodning
    (retten til at blive glemt) — inkl. selve billedfilen, thumbnail og
    sidecar på disk, ikke kun database-rækken.

    2026-08-06 (Claude, Peter): adskilt fra force_delete_camera_location()
    ovenfor med vilje — den handling fjerner LOKATIONEN (struktur), denne
    handling sletter historisk BILLEDDATA og lader lokationen bestå (kameraet
    kan fortsætte med at tage nye billeder bagefter). Genbruger den allerede
    eksisterende, testede services/capture_deletion_service.py::delete_capture()
    — samme funktion der driver den manuelle enkelt-/bulk-sletning fra
    TimelineNavigator.tsx, med samme uafhængige CaptureDeletionLog-audit-spor.
    """
    from services.capture_deletion_service import delete_capture

    camera = db.query(Camera).filter_by(id=camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Kameralokation ikke fundet")
    if camera.site_id:
        _ensure_site_access(db, current_user, camera.site_id)
    elif camera.customer_id:
        _ensure_customer_access(current_user, camera.customer_id)

    deletion_details = payload.get("deletion_details")
    username = str(getattr(current_user, "username", None) or "unknown")
    captures = db.query(Capture).filter(Capture.camera_id == camera_id).all()

    deleted_count = 0
    errors = []
    for capture in captures:
        try:
            delete_capture(
                db, capture, deletion_reason="gdpr_request", deletion_details=deletion_details,
                performed_by=f"admin:{username}", find_image=_find_image,
                unlink_thumbnails=_unlink_thumbnail_variants,
            )
            deleted_count += 1
        except Exception as exc:
            log.exception("GDPR-sletning fejlede for capture %s (kamera %s)", capture.id, camera_id)
            errors.append({"capture_id": capture.id, "error": str(exc)})

    log.warning(
        "GDPR-sletning: %d/%d billeder slettet (fil+DB) for kamera-lokation %s (%s) af %s",
        deleted_count, len(captures), camera.camera_name or camera_id, camera_id, username,
    )
    return {"ok": True, "deleted": deleted_count, "total": len(captures), "errors": errors}


@router.get("/api/admin/cameras/{camera_id}/history")
def camera_assignment_history(
    camera_id: str,
    _user=_require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Historik over alle device-assignments for et kamera."""
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


@router.get("/api/admin/devices/{device_id}/camera-location")
def get_device_camera_location(
    device_id: str,
    _user=_require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """Returnerer den aktive kamera-lokation (Camera) som en device er tildelt."""
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
            "retention_days":       getattr(cam, "retention_days", 99999),
        },
    }
