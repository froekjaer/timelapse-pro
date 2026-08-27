# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — cameras_api.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Camera / Pi coupling — logical camera CRUD, BT-PAN TOTP local-access
provisioning, and device-assignment lifecycle.

Montér i main.py:
    from api.cameras_api import router as cameras_router
    app.include_router(cameras_router)

Endpoints:
    GET  /api/admin/cameras
    GET  /api/admin/cameras/{camera_id}/ssh-key           (retired legacy stub)
    POST /api/admin/cameras
    PUT  /api/admin/cameras/{camera_id}
    GET  /api/admin/cameras/{camera_id}/bt-totp-qr
    POST /api/admin/cameras/{camera_id}/bt-totp-regenerate
    POST /api/admin/cameras/{camera_id}/assign
    GET  /api/admin/cameras/{camera_id}/history

Extracted from main.py (2026-08-27, Phase 2 of the main.py modularization
plan — see Dokumentation/Arkitektur/Headend_Main_Modularisering_Status_
2026-08-26.md). GET /api/admin/headend/ssh-public-key, which sat physically
interleaved between two of these routes in main.py, is NOT part of this
domain (headend's own SSH keypair, unrelated to camera resources) and
stayed in main.py.

require_role/get_current_user come from auth.py; _is_platform_admin,
_ensure_site_access, _ensure_customer_access, _has_field_access, and
_visible_camera_query come from tenant_scope.py — both module-scope
imports, no lazy import or factory-argument threading needed (Phase 0/2.0
already retired those patterns for anything auth- or tenant-scope-related).
_resolve_camera_bt_totp lives here now (moved with the rest of the Camera
domain) — local_access.py's admin overview page imports it from here
instead of main.py. The one main.py-wide utility this domain still needs
(_get_setting) is lazy-imported at its one call site, same idiom as the
previous extractions.
"""
from __future__ import annotations

import json as _json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import Camera, Customer, Device, DeviceAssignment, Site, User, get_db, now_utc
from auth import get_current_user, require_role
from tenant_scope import (
    _is_platform_admin, _has_field_access,
    _ensure_customer_access, _ensure_site_access,
    _visible_camera_query,
)

log = logging.getLogger("headend")

router = APIRouter(tags=["Cameras"])


@router.get("/api/admin/cameras")
def list_cameras(
    site_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """List alle logiske kameraer. Filtreres med ?site_id= eller ?customer_id="""
    from database import Camera, DeviceAssignment
    q = db.query(Camera).filter(Camera.retired_at.is_(None))
    if site_id:
        q = q.filter(Camera.site_id == site_id)
    if customer_id:
        q = q.filter(Camera.customer_id == customer_id)
    cameras = q.order_by(Camera.camera_name).all()
    result = []
    for cam in cameras:
        site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
        customer = db.query(Customer).filter_by(id=cam.customer_id or (site.customer_id if site else None)).first() if (cam.customer_id or site) else None
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
            "site_name":     site.name if site else None,
            "customer_name": customer.name if customer else None,
            "camera_name":   cam.camera_name,
            "serial_number": cam.serial_number,
            "model":         cam.model,
            "notes":         cam.notes,
            "baseline_description": getattr(cam, "baseline_description", None),
            "context_notes":        getattr(cam, "context_notes", None),
            "current_device_id": assignment.device_id if assignment else None,
            "assigned_at":   assignment.assigned_at.isoformat() if assignment and assignment.assigned_at else None,
            "created_at":    cam.created_at.isoformat() if cam.created_at else None,
            # Netværkskonfiguration (v7)
            "network_type":  getattr(cam, "network_type", "ethernet") or "ethernet",
            "wifi_ssid":     getattr(cam, "wifi_ssid", None),
            "wifi_country":  getattr(cam, "wifi_country", "DK") or "DK",
            # wifi_password + ssh_private_key returneres IKKE her af sikkerhedshensyn
            # SSH / reverse tunnel (v8)
            "ssh_public_key":      getattr(cam, "ssh_public_key", None),
            "reverse_tunnel_port": getattr(cam, "reverse_tunnel_port", None),
        })
    return result


@router.get("/api/admin/cameras/{camera_id}/ssh-key")
def download_camera_ssh_key(
    camera_id: str,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Retired legacy escrow path: operational Edge private keys are Edge-owned."""
    from database import Camera as _Camera
    cam = db.query(_Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    if cam.site_id:
        _ensure_site_access(db, current_user, cam.site_id)
    elif cam.customer_id:
        _ensure_customer_access(current_user, cam.customer_id)
    elif not _is_platform_admin(current_user):
        raise HTTPException(status_code=403, detail="Ingen adgang til dette kamera")
    raise HTTPException(
        status_code=410,
        detail="Legacy SSH private-key download er pensioneret. Edge ejer og genererer operationelle private nøgler lokalt.",
    )


@router.post("/api/admin/cameras")
def create_camera(
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Opret et nyt logisk kamera."""
    from database import Camera
    import uuid as _u
    site = db.query(Site).filter_by(id=payload.get("site_id")).first() if payload.get("site_id") else None
    customer_id = payload.get("customer_id") or (site.customer_id if site else None)
    if site:
        _ensure_site_access(db, _user, site.id)
    elif customer_id:
        _ensure_customer_access(_user, customer_id)
    cam = Camera(
        id          = str(_u.uuid4()),
        site_id     = site.id if site else payload.get("site_id"),
        customer_id = customer_id,
        camera_name = payload.get("camera_name", "Nyt kamera"),
        serial_number = payload.get("serial_number"),
        model       = payload.get("model"),
        notes       = payload.get("notes"),
        config      = _json.dumps(payload.get("config", {})),
        # bt_totp_secret + bt_totp_sid: NULL = fabriksstandard JBSWY3DPEHPK3PXP
    )
    db.add(cam); db.commit()
    log.info("Kamera oprettet: %s (%s)", cam.camera_name, cam.id)
    return {"id": cam.id}


@router.put("/api/admin/cameras/{camera_id}")
def update_camera(
    camera_id: str,
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Opdater metadata på et logisk kamera uden at ændre device-binding."""
    from database import Camera, Device, DeviceAssignment
    cam = db.query(Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    if cam.site_id:
        _ensure_site_access(db, _user, cam.site_id)
    elif cam.customer_id:
        _ensure_customer_access(_user, cam.customer_id)

    if "site_id" in payload:
        new_site = _ensure_site_access(db, _user, payload.get("site_id")) if payload.get("site_id") else None
        cam.site_id = new_site.id if new_site else None
        cam.customer_id = payload.get("customer_id") or (new_site.customer_id if new_site else cam.customer_id)
    elif "customer_id" in payload:
        _ensure_customer_access(_user, payload.get("customer_id"))
        cam.customer_id = payload.get("customer_id")

    for field in ["camera_name", "serial_number", "model", "notes", "baseline_description", "context_notes", "network_type", "wifi_ssid", "wifi_country", "retention_days"]:
        if field in payload:
            setattr(cam, field, payload[field])
    if "wifi_password" in payload and payload.get("wifi_password"):
        cam.wifi_password = payload["wifi_password"]
    if "config" in payload and isinstance(payload["config"], dict):
        cam.config = _json.dumps(payload["config"], ensure_ascii=False)

    # Hold aktiv device metadata læsbar for gamle views og captures.
    active = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=cam.id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .first()
    )
    if active:
        dev = db.query(Device).filter_by(device_id=active.device_id).first()
        if dev:
            dev.camera_name = cam.camera_name
            dev.site_id = cam.site_id
            dev.customer_id = cam.customer_id
            site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
            customer = db.query(Customer).filter_by(id=cam.customer_id).first() if cam.customer_id else None
            if site:
                dev.site_name = site.name
            if customer:
                dev.customer_name = customer.name

    db.commit()
    return {"status": "ok", "id": cam.id}


def _resolve_camera_bt_totp(db: Session, cam) -> tuple[str, str, str]:
    """Beregn det gældende BT-TOTP secret/sid/source for et kamera ved at gå
    op i hierarkiet: global (Settings) → kunde.config_overrides.bt_totp →
    site.config_overrides.bt_totp → kamera.bt_totp_secret (højeste prioritet).
    Returnerer ("", "", "") hvis intet lag har et secret. Delt mellem
    get_camera_bt_totp_qr() og list_local_access() (admin-oversigten,
    2026-08-19) så resolutionslogikken kun findes ét sted.
    """
    from main import _get_setting
    from database import Site, Customer

    secret = ""
    sid = ""
    source = ""

    # Lag 1: global override (Settings-tabel)
    _g_secret = _get_setting(db, "bt_totp_secret", "")
    _g_sid    = _get_setting(db, "bt_totp_sid", "")
    if _g_secret:
        secret, sid, source = _g_secret, _g_sid or "global", "global"

    # Lag 2: customer.config_overrides
    site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
    customer = db.query(Customer).filter_by(id=site.customer_id).first() if site else None
    if customer and customer.config_overrides:
        _co = _json.loads(customer.config_overrides).get("bt_totp", {})
        if _co.get("secret"):
            secret, sid, source = _co["secret"], _co.get("sid", "kunde"), "kunde"

    # Lag 3: site.config_overrides
    if site and site.config_overrides:
        _so = _json.loads(site.config_overrides).get("bt_totp", {})
        if _so.get("secret"):
            secret, sid, source = _so["secret"], _so.get("sid", "site"), "site"

    # Lag 4: camera-specifik override (bt_totp_secret kolonne)
    if cam.bt_totp_secret:
        secret, sid, source = cam.bt_totp_secret, cam.bt_totp_sid or "kamera", "kamera"

    return secret, sid, source



@router.get("/api/admin/cameras/{camera_id}/bt-totp-qr")
def get_camera_bt_totp_qr(
    camera_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returner QR-kode (data-URI) til BT PAN TOTP for dette kamera.
    Beregner det gældende secret via _resolve_camera_bt_totp() (hierarkiet:
    global → kunde → site → kamera, se den funktion for detaljer).
    """
    import pyotp as _pyotp, qrcode as _qrcode, io as _io, base64 as _b64
    from database import Camera, Site, Customer, Device, DeviceAssignment

    cam = db.query(Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    if current_user is None or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Aktiv TimeLapse Pro-konto kræves")
    if cam.site_id:
        _ensure_site_access(db, current_user, cam.site_id)
    elif cam.customer_id:
        _ensure_customer_access(current_user, cam.customer_id)
    elif not _is_platform_admin(current_user):
        raise HTTPException(status_code=403, detail="Ingen adgang til dette kamera")
    is_admin = current_user.role in {"super_admin", "admin"}
    if not is_admin:
        if not _has_field_access(current_user):
            raise HTTPException(status_code=403, detail="On-site idriftsættelse og service kræves")
        if current_user.customer_id and str(cam.customer_id) != str(current_user.customer_id):
            raise HTTPException(status_code=403, detail="Kameraet ligger uden for din kundeafgrænsning")

    secret, sid, source = _resolve_camera_bt_totp(db, cam)
    if not secret:
        raise HTTPException(
            status_code=409,
            detail="Lokal adgang er ikke provisioneret for dette kamera. En administrator skal oprette den før brug.",
        )

    assignment = (
        db.query(DeviceAssignment)
        .filter_by(camera_id=cam.id, unassigned_at=None)
        .first()
    )
    device = db.query(Device).filter_by(device_id=assignment.device_id).first() if assignment else None
    device_label = (device.device_id if device else "ikke-tildelt Edge")
    camera_label = cam.camera_name or str(camera_id)
    # Authenticator apps display the account name more reliably than an issuer.
    # The device ID must therefore be part of the account label, never just a
    # generic product name.
    issuer = "TimeLapse Pro Local Edge"
    account_name = f"{device_label} - {camera_label}"
    totp = _pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=account_name, issuer_name=issuer)

    buf = _io.BytesIO()
    _qrcode.make(uri).save(buf, format="PNG")
    qr_b64 = _b64.b64encode(buf.getvalue()).decode()
    # Live code alongside the QR — a technician standing at the device can
    # type it in directly without an authenticator app. Removed at some point
    # during a large refactor without a documented rationale; rebuilt as a
    # computed rotating code (not the old raw-secret text) per Peter,
    # 2026-08-19. Same pyotp already used for user MFA elsewhere in this file.
    return {
        "secret":   secret,
        "sid":      sid,
        "source":   source,    # hvilket lag der gælder: factory-default|global|kunde|site|kamera
        "account_name": account_name,
        "device_id": device.device_id if device else None,
        "uri":      uri,
        "qr_code":  f"data:image/png;base64,{qr_b64}",
        "is_factory_default": False,
        "current_code": totp.now(),
        "seconds_remaining": totp.interval - (int(time.time()) % totp.interval),
    }


@router.post("/api/admin/cameras/{camera_id}/bt-totp-regenerate")
def regenerate_camera_bt_totp(
    camera_id: str,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Opret eller rotér et kamera-specifikt TOTP secret (kamera-laget — højeste prioritet
    i hierarkiet). Overrider eventuelle global/kunde/site-lag for dette kamera.
    Edge skal eksplicit synkronisere (knappen 'Opdater TOTP fra CMDB' i mgmt-UI)
    før det træder i kraft — sker ALDRIG automatisk.
    """
    import pyotp as _pyotp
    import uuid as _u
    from database import Camera
    cam = db.query(Camera).filter_by(id=camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera ikke fundet")
    cam.bt_totp_secret = _pyotp.random_base32()
    cam.bt_totp_sid    = f"cam-{str(_u.uuid4())[:8]}"
    db.commit()
    log.info("BT TOTP (kamera-lag) regenereret for kamera %s sid=%s", camera_id, cam.bt_totp_sid)
    return {"sid": cam.bt_totp_sid, "message": "Nyt kamera-specifikt TOTP secret genereret — kræver eksplicit sync på edge"}


@router.post("/api/admin/cameras/{camera_id}/assign")
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
        # site_name/customer_name er separate fritekstfelter der ellers ville stå forældede (HANDOVER_LOG 2026-08-16)
        site = db.query(Site).filter_by(id=camera.site_id).first() if camera.site_id else None; device.site_name = site.name if site else None
        cust = db.query(Customer).filter_by(id=camera.customer_id).first() if camera.customer_id else None; device.customer_name = cust.name if cust else None

    db.commit()
    log.info("Kamera %s tildelt device %s", camera_id, device_id)
    return {"ok": True, "camera_id": camera_id, "device_id": device_id}

@router.get("/api/admin/cameras/{camera_id}/history")
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
            "assignment_type": getattr(e, "assignment_type", "manual"),
            "notes":         e.notes,
            "active":        e.unassigned_at is None,
        }
        for e in entries
    ]
