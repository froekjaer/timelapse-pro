"""
TimeLapse Pro — Sprint C: SSH Tunnel, Camera/Pi-kobling og Opdateringsstyring endpoints
=========================================================================================
Tilføjer til headend/main.py:
  - SSH tunnel event + status endpoints
  - Camera/Pi-kobling CRUD
  - Update policy + pending_updates endpoints

Kør fra roden af timelapse-pro repoet:
    python sprint_c/fix_sprint_c_endpoints.py
"""

from pathlib import Path

MAIN_PATH = Path("headend/main.py")
assert MAIN_PATH.exists(), "FEJL: Kør fra roden af repoet"

GUARD = "# ── SSH TUNNEL ENDPOINTS (Sprint C) ─"
content = MAIN_PATH.read_text()
if GUARD in content:
    print("✓ Sprint C endpoints allerede tilføjet — ingen ændringer")
    exit(0)

NEW_ENDPOINTS = '''

# ═══════════════════════════════════════════════════════════════════════════
# ── SSH TUNNEL ENDPOINTS (Sprint C) ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

class SshTunnelEventRequest(BaseModel):
    device_id:      str
    event:          str          # connected|disconnected|failed|denied
    remote_port:    Optional[int] = None
    local_port:     Optional[int] = 22
    duration_s:     Optional[int] = None
    using_fallback: Optional[bool] = False
    timestamp:      str

@app.post("/api/ssh-tunnel/event")
def ssh_tunnel_event(req: SshTunnelEventRequest, db: Session = Depends(get_db)):
    """Edge notificerer headend om SSH tunnel events (connect, disconnect, fail)."""
    from database import SshTunnelLog
    entry = SshTunnelLog(
        device_id    = req.device_id,
        event        = req.event,
        remote_port  = req.remote_port,
        local_port   = req.local_port,
        initiated_by = "edge_auto",
        duration_s   = req.duration_s,
        extra        = _json.dumps({"using_fallback": req.using_fallback}) if req.using_fallback else None,
    )
    db.add(entry); db.commit()
    log.info("SSH tunnel %s: device=%s port=%s", req.event, req.device_id, req.remote_port)
    return {"status": "ok"}

@app.get("/api/ssh-tunnel/active")
def ssh_tunnel_active(
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """Returnerer liste af devices med aktiv SSH tunnel."""
    from database import SshTunnelLog
    from sqlalchemy import text as _t

    # Find seneste event pr. device — aktiv = seneste event er "connected"
    rows = db.execute(_t("""
        SELECT s.device_id, s.remote_port, s.local_port, s.event_at, s.extra
        FROM ssh_tunnel_log s
        INNER JOIN (
            SELECT device_id, MAX(event_at) as max_at
            FROM ssh_tunnel_log
            GROUP BY device_id
        ) latest ON s.device_id = latest.device_id AND s.event_at = latest.max_at
        WHERE s.event = 'connected'
        ORDER BY s.event_at DESC
    """)).fetchall()

    return [
        {
            "device_id":   r[0],
            "remote_port": r[1],
            "local_port":  r[2],
            "connected_at": r[3],
        }
        for r in rows
    ]

@app.get("/api/ssh-tunnel/log/{device_id}")
def ssh_tunnel_log(
    device_id: str,
    limit: int = 50,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Audit log for SSH tunnel sessioner på en device."""
    from database import SshTunnelLog
    entries = (
        db.query(SshTunnelLog)
        .filter_by(device_id=device_id)
        .order_by(SshTunnelLog.event_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "event":       e.event,
            "remote_port": e.remote_port,
            "duration_s":  e.duration_s,
            "initiated_by":e.initiated_by,
            "event_at":    e.event_at.isoformat() if e.event_at else None,
        }
        for e in entries
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ── CAMERA / PI KOBLING (Sprint C) ────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/admin/cameras")
def list_cameras(
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db)
):
    """List alle logiske kameraer."""
    from database import Camera, DeviceAssignment
    cameras = db.query(Camera).filter(Camera.retired_at.is_(None)).all()
    result = []
    for cam in cameras:
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
            "camera_name":   cam.camera_name,
            "serial_number": cam.serial_number,
            "model":         cam.model,
            "notes":         cam.notes,
            "current_device_id": assignment.device_id if assignment else None,
            "assigned_at":   assignment.assigned_at.isoformat() if assignment and assignment.assigned_at else None,
            "created_at":    cam.created_at.isoformat() if cam.created_at else None,
        })
    return result

@app.post("/api/admin/cameras")
def create_camera(
    payload: dict,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Opret et nyt logisk kamera."""
    from database import Camera
    import uuid as _u
    cam = Camera(
        id          = str(_u.uuid4()),
        site_id     = payload.get("site_id"),
        customer_id = payload.get("customer_id"),
        camera_name = payload.get("camera_name", "Nyt kamera"),
        serial_number = payload.get("serial_number"),
        model       = payload.get("model"),
        notes       = payload.get("notes"),
        config      = _json.dumps(payload.get("config", {})),
    )
    db.add(cam); db.commit()
    log.info("Kamera oprettet: %s (%s)", cam.camera_name, cam.id)
    return {"id": cam.id}

@app.post("/api/admin/cameras/{camera_id}/assign")
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

    db.commit()
    log.info("Kamera %s tildelt device %s", camera_id, device_id)
    return {"ok": True, "camera_id": camera_id, "device_id": device_id}

@app.get("/api/admin/cameras/{camera_id}/history")
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
            "notes":         e.notes,
            "active":        e.unassigned_at is None,
        }
        for e in entries
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ── OPDATERINGSSTYRING (Sprint C) ─────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/updates/pending")
def list_pending_updates(
    status: Optional[str] = None,
    _user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """List opdateringer der afventer godkendelse eller deployment."""
    from database import PendingUpdate
    q = db.query(PendingUpdate)
    if status:
        q = q.filter_by(status=status)
    else:
        q = q.filter(PendingUpdate.status.in_(["pending", "approved"]))
    updates = q.order_by(PendingUpdate.created_at.desc()).all()
    return [
        {
            "id":          u.id,
            "update_type": u.update_type,
            "version":     u.version,
            "description": u.description,
            "severity":    u.severity,
            "scope":       u.scope,
            "scope_id":    u.scope_id,
            "status":      u.status,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
            "approved_by": u.approved_by,
        }
        for u in updates
    ]

@app.post("/api/updates/{update_id}/approve")
def approve_update(
    update_id: int,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Godkend en opdatering til deployment."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id, status="pending").first()
    if not u:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet eller ikke pending")
    u.status      = "approved"
    u.approved_at = now_utc()
    u.approved_by = current_user.username
    db.commit()
    log.info("Opdatering godkendt: %s v%s af %s", u.update_type, u.version, current_user.username)
    return {"ok": True}

@app.post("/api/updates/{update_id}/reject")
def reject_update(
    update_id: int,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db)
):
    """Afvis en opdatering."""
    from database import PendingUpdate
    u = db.query(PendingUpdate).filter_by(id=update_id, status="pending").first()
    if not u:
        raise HTTPException(status_code=404, detail="Opdatering ikke fundet")
    u.status      = "rejected"
    u.approved_by = current_user.username
    u.approved_at = now_utc()
    db.commit()
    return {"ok": True}

@app.get("/api/updates/policy/{device_id}")
def get_update_policy(
    device_id: str,
    db: Session = Depends(get_db)
):
    """Returnerer resolved update_policy for et device (bruges af edge)."""
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        raise HTTPException(status_code=404)

    # Default policy
    policy = {
        "app_security":  "auto",
        "os_security":   "auto",
        "app_updates":   "manual",
        "os_updates":    "manual",
        "maintenance_window": "02:00-04:00",
    }

    # Merge hierarki (global → customer → site → device)
    try:
        site     = db.query(Site).filter_by(id=device.site_id).first() if device.site_id else None
        customer = db.query(Customer).filter_by(id=site.customer_id).first() if site else None
        defaults = db.query(ConfigDefaults).first()

        if defaults and getattr(defaults, "system", None):
            sys_cfg = _json.loads(defaults.system)
            if "update_policy" in sys_cfg:
                policy.update(sys_cfg["update_policy"])

        for obj in [customer, site, device]:
            if not obj:
                continue
            overrides_raw = getattr(obj, "config_overrides", None) or getattr(obj, "device_config", None)
            if overrides_raw:
                try:
                    overrides = _json.loads(overrides_raw) if isinstance(overrides_raw, str) else overrides_raw
                    if "update_policy" in overrides:
                        # Mest restriktive vinder: manual > auto
                        for k, v in overrides["update_policy"].items():
                            if k in policy:
                                if v == "manual" or policy[k] == "auto":
                                    policy[k] = v
                except Exception:
                    pass
    except Exception as exc:
        log.warning("Update policy resolution fejl: %s", exc)

    return policy

@app.post("/api/updates/report")
def report_update(payload: dict, db: Session = Depends(get_db)):
    """Edge rapporterer resultat af deployment (deployed/rolled_back)."""
    from database import PendingUpdate
    update_id = payload.get("update_id")
    status    = payload.get("status")  # deployed|rolled_back
    if not update_id or status not in ("deployed", "rolled_back"):
        raise HTTPException(status_code=400)
    u = db.query(PendingUpdate).filter_by(id=update_id).first()
    if not u:
        raise HTTPException(status_code=404)
    u.status = status
    if status == "deployed":
        u.deployed_at = now_utc()
    elif status == "rolled_back":
        u.rollback_at = now_utc()
    db.commit()
    log.info("Update %d rapporteret som %s fra device", update_id, status)
    return {"ok": True}

'''

# ── Indsæt før reverse-ssh (eksisterende endpoint) ───────────────────────
ANCHOR = "# ── Reverse SSH ─"
if ANCHOR in content:
    content = content.replace(ANCHOR, NEW_ENDPOINTS + "\n\n" + ANCHOR, 1)
else:
    # Fallback: tilføj til sidst
    content = content.rstrip() + "\n" + NEW_ENDPOINTS

MAIN_PATH.write_text(content)
print(f"✓ {MAIN_PATH} opdateret med SSH tunnel, Camera/Pi-kobling og Update endpoints")
print("\nHusk: git add headend/main.py")
