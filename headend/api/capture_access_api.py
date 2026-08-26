"""Tenant-scoped GDPR capture access audit API."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from database import CaptureAccessLog, get_db
from auth import _ROLE_HIERARCHY, _mfa_required_for_user, _session_is_mfa_verified, _session_payload, get_current_user


router = APIRouter(prefix="/api/audit/capture-access", tags=["Audit"])


def _current_viewer(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if "viewer" not in _ROLE_HIERARCHY.get(user.role, {user.role}):
        raise HTTPException(status_code=403, detail="Viewer-rolle kræves")
    if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
        raise HTTPException(status_code=403, detail="MFA kræves")
    return user


@router.get("")
def search_capture_access(
    username: str | None = Query(None, max_length=100),
    device_id: str | None = Query(None, max_length=80),
    filename: str | None = Query(None, max_length=200),
    action: str | None = Query(None, max_length=30),
    hours: int = Query(168, ge=1, le=8760),
    limit: int = Query(500, ge=1, le=2000),
    user=Depends(_current_viewer),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(CaptureAccessLog).filter(CaptureAccessLog.accessed_at >= since)
    if user.role not in {"super_admin", "admin", "auditor"}:
        if not user.customer_id:
            return []
        query = query.filter(CaptureAccessLog.customer_id == user.customer_id)
    if username:
        query = query.filter(CaptureAccessLog.username.ilike(f"%{username}%"))
    if device_id:
        query = query.filter(CaptureAccessLog.device_id == device_id)
    if filename:
        query = query.filter(CaptureAccessLog.filename.ilike(f"%{filename}%"))
    if action:
        query = query.filter(CaptureAccessLog.action == action)
    rows = query.order_by(CaptureAccessLog.accessed_at.desc()).limit(limit).all()
    return [{
        "id": row.id,
        "capture_id": row.capture_id,
        "device_id": row.device_id,
        "filename": row.filename,
        "action": row.action,
        "user_id": row.user_id,
        "username": row.username,
        "role": row.role,
        "customer_id": row.customer_id,
        "accessed_at": row.accessed_at.isoformat() if row.accessed_at else None,
    } for row in rows]
