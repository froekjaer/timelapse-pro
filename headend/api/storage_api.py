"""Administrator API for logical storage bindings."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import Settings, StorageBinding, get_db
from storage_registry import VALID_BACKENDS, VALID_MODES, VALID_ROLES, binding_status

router = APIRouter(prefix="/api/admin/storage", tags=["Storage"])


def _current_viewer(request: Request, db: Session = Depends(get_db)):
    """Any authenticated user, with the same MFA-policy enforcement as
    main.require_role() — see grc_register_api.py's _current_viewer for the
    full rationale (HANDOVER_LOG 2026-08-05); _require_platform_admin below
    builds on this, so fixing it here is sufficient for both."""
    from main import _mfa_required_for_user, _session_is_mfa_verified, _session_payload, get_current_user
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
        raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
    return user


def _require_platform_admin(user=Depends(_current_viewer)):
    if user.role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Lagerændringer kræver administrator")
    return user


def _validate(payload: dict) -> dict:
    role = str(payload.get("logical_name") or "").strip()
    backend = str(payload.get("backend_type") or "local")
    mode = str(payload.get("access_mode") or "read_write")
    path = str(payload.get("path") or "").strip()
    if role not in VALID_ROLES or backend not in VALID_BACKENDS or mode not in VALID_MODES or not path.startswith("/"):
        raise HTTPException(status_code=422, detail="Ugyldig lagerrolle, backend, adgangstype eller sti")
    return {"logical_name": role, "backend_type": backend, "access_mode": mode, "path": path,
            "priority": max(0, int(payload.get("priority", 100))), "active": bool(payload.get("active", True)),
            "expected_volume_uuid": str(payload.get("expected_volume_uuid") or "")[:80] or None,
            "description": str(payload.get("description") or "")[:300] or None}


@router.get("/bindings")
def list_bindings(_user=Depends(_current_viewer), db: Session = Depends(get_db)):
    rows = db.query(StorageBinding).order_by(StorageBinding.logical_name, StorageBinding.priority).all()
    return {"bindings": [binding_status(row) for row in rows]}


@router.get("/status")
def storage_status(_user=Depends(_current_viewer), db: Session = Depends(get_db)):
    """Compatibility status endpoint for older deployed UI versions."""
    rows = db.query(StorageBinding).filter_by(active=True).order_by(StorageBinding.logical_name, StorageBinding.priority).all()
    statuses = [binding_status(row) for row in rows]
    return {"bindings": statuses, "roots": statuses}


@router.post("/bindings")
def create_binding(payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    values = _validate(payload)
    if db.query(StorageBinding).filter_by(logical_name=values["logical_name"], path=values["path"]).first():
        raise HTTPException(status_code=409, detail="Bindingen findes allerede")
    row = StorageBinding(**values, created_by=user.username, updated_by=user.username)
    db.add(row); db.commit(); db.refresh(row)
    return binding_status(row)


@router.put("/bindings/{binding_id}")
def update_binding(binding_id: int, payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    row = db.query(StorageBinding).filter_by(id=binding_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Lagerbinding ikke fundet")
    for key, value in _validate(payload).items():
        setattr(row, key, value)
    row.updated_by = user.username; row.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(row)
    return binding_status(row)


@router.post("/bootstrap")
def bootstrap_bindings(user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    settings = {row.key: row.value for row in db.query(Settings).filter(Settings.key.in_([
        "sftp_base", "backup_nas_path", "edge_image_artifact_dir"
    ])).all()}
    candidates = (("captures-primary", settings.get("sftp_base")),
                  ("backups-primary", settings.get("backup_nas_path")),
                  ("edge-artifacts", settings.get("edge_image_artifact_dir")))
    created = 0
    for role, path in candidates:
        if path and not db.query(StorageBinding).filter_by(logical_name=role, path=path).first():
            db.add(StorageBinding(logical_name=role, path=path, backend_type="local", access_mode="read_write",
                                  priority=10, active=True, created_by=user.username, updated_by=user.username))
            created += 1
    db.commit()
    return {"created": created}
