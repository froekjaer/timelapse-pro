"""
TimeLapse Pro — Captures timeline navigation
==============================================================================
2026-08-06/07 (Claude): extracted from headend/main.py (module ratchet — see
tests/test_architecture_ratchet.py; Peter's standing correction applies: the
baseline exists to force extraction into domain modules, not to be raised
again instead of it).

Single endpoint: day-bucketed capture counts / per-day capture lists for the
Tidslinje UI, scoped by either a physical device_id or a logical camera_id
(the latter added same day so a camera location without an active Edge can
still show its own timeline — see api/camera_locations_api.py's docstring
for the broader camera_id-vs-device_id context).

Auth/access-control helpers are imported lazily from `main` inside the
function body — the established pattern in this codebase (see
api/thumbnails_api.py) — main.py imports this router near the END of its own
definition, so a top-level `from main import ...` here would fail (main
isn't finished executing yet), but a function-body import resolves fine at
call time.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Camera, Capture, get_db

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


def _ensure_capture_device_access(db: Session, user, device_id: str) -> None:
    from main import _ensure_capture_device_access as _impl
    return _impl(db, user, device_id)


def _ensure_site_access(db: Session, user, site_id: str | None):
    from main import _ensure_site_access as _impl
    return _impl(db, user, site_id)


def _ensure_customer_access(user, customer_id: str | None) -> None:
    from main import _ensure_customer_access as _impl
    _impl(user, customer_id)


@router.get("/api/admin/captures/timeline")
def captures_timeline(
    device_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    year:  Optional[int] = None,
    month: Optional[int] = None,
    day:   Optional[int] = None,
    _user=_require_role("viewer"),
    db: Session = Depends(get_db),
):
    """
    Hent captures til timeline navigation.
    - Uden parametre: returner antal captures per dag (alle tider)
    - Med year+month+day: returner alle captures den dag

    camera_id er et alternativ til device_id — Tidslinje-fanen krævede
    indtil nu altid et fysisk device, hvilket gjorde den permanent
    utilgængelig for en kamera-lokation uden en aktiv Edge (netop det
    tilfælde camera_id-arkitekturen findes for). Samme adgangskontrol-mønster
    som main.py's list_captures().
    """
    if not device_id and not camera_id:
        raise HTTPException(status_code=400, detail="device_id eller camera_id påkrævet")
    if device_id:
        _ensure_capture_device_access(db, _user, device_id)
        base_filter = Capture.device_id == device_id
    else:
        cam = db.query(Camera).filter_by(id=camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Kamera ikke fundet")
        if cam.site_id:
            _ensure_site_access(db, _user, cam.site_id)
        elif cam.customer_id:
            _ensure_customer_access(_user, cam.customer_id)
        base_filter = Capture.camera_id == camera_id

    q = db.query(Capture).filter(base_filter, Capture.captured_at.isnot(None))

    if year and month and day:
        # Hent alle captures på en specifik dag
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
        tz = "Europe/Copenhagen"
        local_ts = func.timezone(tz, Capture.captured_at)
        rows = db.query(
            func.extract("year",  local_ts).label("year"),
            func.extract("month", local_ts).label("month"),
            func.extract("day",   local_ts).label("day"),
            func.count(Capture.id).label("count")
        ).filter(base_filter, Capture.captured_at.isnot(None)
        ).group_by("year", "month", "day").order_by("year", "month", "day").all()
        return [
            {"year": int(r.year), "month": int(r.month), "day": int(r.day), "count": r.count}
            for r in rows
        ]
