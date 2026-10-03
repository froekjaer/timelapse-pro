"""Delete LAB preview images (Peter, 2026-10-02).

LAB previews are working images under <sftp_base>/_lab/<device_id>/ (plus
.thumbs/). They are not captures and have no capture row, so deleting them
only removes the files. Kept out of headend/main.py (architecture ratchet).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.path_security import UnsafePath, resolve_lab_preview_path

log = logging.getLogger(__name__)


def _unlink(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def create_lab_previews_router(
    require_role: Callable,
    ensure_device_access: Callable,
    sftp_base_path: Callable[[], Path],
) -> APIRouter:
    router = APIRouter(prefix="/api/lab", tags=["lab"])

    @router.delete("/{device_id}/previews/{filename}")
    def delete_lab_preview(
        device_id: str,
        filename: str,
        user=require_role("admin"),
        db: Session = Depends(get_db),
    ):
        ensure_device_access(db, user, device_id)
        if not filename.startswith("preview_") or not filename.lower().endswith((".jpg", ".jpeg")):
            raise HTTPException(status_code=400, detail="Invalid preview filename")
        try:
            image = resolve_lab_preview_path(sftp_base_path(), device_id, filename)
            thumb = resolve_lab_preview_path(sftp_base_path(), device_id, filename, thumbnail=True)
        except UnsafePath:
            raise HTTPException(status_code=400, detail="Invalid preview path")
        if not _unlink(image):
            raise HTTPException(status_code=404, detail="Preview not found")
        _unlink(thumb)
        log.info("LAB preview deleted for %s by %s: %s", device_id, getattr(user, "username", "?"), filename)
        return {"status": "ok", "deleted": 1}

    @router.delete("/{device_id}/previews")
    def delete_all_lab_previews(
        device_id: str,
        user=require_role("admin"),
        db: Session = Depends(get_db),
    ):
        ensure_device_access(db, user, device_id)
        deleted = 0
        try:
            root = resolve_lab_preview_path(sftp_base_path(), device_id, "preview_x.jpg").parent
        except UnsafePath:
            raise HTTPException(status_code=400, detail="Invalid device id")
        for image in root.glob("preview_*.jpg"):
            if _unlink(image):
                deleted += 1
            _unlink(root / ".thumbs" / image.name)
        log.info("LAB previews deleted for %s by %s: %d", device_id, getattr(user, "username", "?"), deleted)
        return {"status": "ok", "deleted": deleted}

    return router
