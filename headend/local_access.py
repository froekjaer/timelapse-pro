# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — local_access.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Admin-oversigt over BT PAN TOTP-status for alle kameraer.

Montér i main.py:
    from local_access import router as local_access_router
    app.include_router(local_access_router, prefix="/api/admin")

Endpoints:
    GET /api/admin/local-access

Bygget 2026-08-19 efter Peter: "alle enheder der er konfigureret en TOTP
kode til [skal være] tilgængelige, og kan ses (jfr. RBAC)." Lever i sit eget
APIRouter, ikke som direkte @app-route i main.py, fordi
tests/test_architecture_ratchet.py låser main.py's route-antal — se den
test og dens egen kommentar for hvorfor.

Returnerer IKKE selve secret/QR/kode — kun hvilket lag der resolver og en
SID, så en admin hurtigt kan finde det rigtige kamera og derfra åbne den
fulde visning (QR + live-kode) på /cameras/{deviceId}, hvor den logik
allerede findes og ikke er duplikeret her.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db, Camera, Site, Customer, Device, DeviceAssignment
from auth import _ROLE_HIERARCHY, _mfa_required_for_user, _session_is_mfa_verified, _session_payload, get_current_user

router = APIRouter(tags=["Local Access"])


async def _require_local_access_admin(request: Request, db: Session = Depends(get_db)):
    """Samme rolle- og MFA-håndhævelse som auth.require_role("super_admin",
    "admin") — reviewed wrapper, ikke en separat tillidsmodel. Auth-primitiver
    hentes fra auth.py på modul-scope (2026-08-26) — ikke længere en lazy
    import af main, siden auth.py ikke afhænger af main.py.
    """
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
    if not allowed.intersection({"super_admin", "admin"}):
        raise HTTPException(status_code=403, detail="Kræver rolle: super_admin, admin")
    if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
        raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
    return user


@router.get("/local-access")
def list_local_access(
    current_user=Depends(_require_local_access_admin),
    db: Session = Depends(get_db),
):
    from main import _resolve_camera_bt_totp, _visible_camera_query

    rows = []
    for cam in _visible_camera_query(db, current_user).order_by(Camera.camera_name).all():
        secret, sid, source = _resolve_camera_bt_totp(db, cam)
        site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
        customer = db.query(Customer).filter_by(
            id=cam.customer_id or (site.customer_id if site else None)
        ).first() if (cam.customer_id or site) else None
        assignment = db.query(DeviceAssignment).filter_by(camera_id=cam.id, unassigned_at=None).first()
        device = db.query(Device).filter_by(device_id=assignment.device_id).first() if assignment else None
        rows.append({
            "camera_id":     cam.id,
            "camera_name":   cam.camera_name,
            "device_id":     device.device_id if device else None,
            "customer_name": customer.name if customer else None,
            "site_name":     site.name if site else None,
            "sid":           sid or None,
            "source":        source or "unprovisioned",
        })
    return rows
