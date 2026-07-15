"""Controlled deletion of explicitly selected capture evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import Capture, CaptureDeletionLog


ALLOWED_REASONS = {"defective", "unwanted", "gdpr_request"}


def validate_deletion_reason(reason: object) -> str:
    value = str(reason or "").strip().lower()
    if value not in ALLOWED_REASONS:
        raise HTTPException(
            status_code=422,
            detail="deletion_reason skal være defective, unwanted eller gdpr_request",
        )
    return value


def delete_capture(
    db: Session,
    capture: Capture,
    *,
    deletion_reason: str,
    performed_by: str,
    find_image: Callable[[str, str], Path | None],
    unlink_thumbnails: Callable[[Path, str], bool],
) -> dict:
    """Delete one selected capture and retain an independent audit record."""
    reason = validate_deletion_reason(deletion_reason)
    path = find_image(capture.device_id, capture.filename)
    file_size = path.stat().st_size if path and path.is_file() else None
    audit = CaptureDeletionLog(
        capture_id=capture.id,
        camera_id=capture.camera_id or capture.device_id,
        customer_id=capture.customer_id,
        site_id=capture.site_id,
        filename=capture.filename,
        captured_at=capture.captured_at,
        deletion_reason=reason,
        performed_by=performed_by[:100],
        file_size=file_size,
    )
    deleted = {"file": False, "thumbnail": False, "sidecar": False, "db": False}
    try:
        if path and path.exists():
            path.unlink()
            deleted["file"] = True
            deleted["thumbnail"] = unlink_thumbnails(path, capture.filename)
            sidecar = path.with_suffix(".json")
            if sidecar.exists():
                sidecar.unlink()
                deleted["sidecar"] = True
        db.add(audit)
        db.delete(capture)
        db.commit()
        deleted["db"] = True
        return deleted
    except Exception:
        db.rollback()
        raise
