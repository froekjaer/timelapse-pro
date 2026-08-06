"""
TimeLapse Pro — Cold-backup export (browser download / USB / fixed path)
==========================================================================
2026-08-06 (Claude): extracted from headend/main.py (module ratchet — see
tests/test_architecture_ratchet.py and api/camera_locations_api.py's
module docstring for the fuller "why extract, not just raise the baseline"
rationale).

Exports selected captures, or an entire camera location, to a ZIP — either
streamed as a browser download or written directly to a filesystem path
(a mounted USB drive under /Volumes, or any other fixed configured path —
same admin-trust model as headend/importer.py's existing `local_path`
import feature). The ZIP is always built directly to disk, never held in
memory — some camera locations have 20,000+ captures.

Auth/access-control helpers (_ensure_site_access, _ensure_customer_access,
_capture_is_allowed) are imported lazily from `main` inside each function
body — see api/thumbnails_api.py for the full rationale (main.py imports
this router near the END of its own definition).
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from database import Camera, Capture, get_db, now_utc
from media_paths import _find_image

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


def _capture_is_allowed(db: Session, user, capture: Capture) -> bool:
    from main import _capture_is_allowed as _impl
    return _impl(db, user, capture)


@router.get("/api/admin/export/volumes")
def list_export_volumes(_user=_require_role("admin")):
    """List tilsluttede eksterne diske (macOS /Volumes) til brug som eksport-
    destination i UI'et — udelader boot-volumet."""
    base = Path("/Volumes")
    volumes = []
    if base.is_dir():
        for entry in sorted(base.iterdir()):
            try:
                resolved = entry.resolve()
                if resolved == Path("/"):
                    continue  # Boot-volumet — aldrig et gyldigt eksportmål
                if not entry.is_dir():
                    continue
                st = os.statvfs(str(entry))
                volumes.append({
                    "path":     str(entry),
                    "name":     entry.name,
                    "free_gb":  round(st.f_bavail * st.f_frsize / 1e9, 1),
                    "total_gb": round(st.f_blocks * st.f_frsize / 1e9, 1),
                })
            except OSError:
                continue
    return volumes


def _export_zip_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "export"
    return f"{safe}_{now_utc().strftime('%Y%m%d_%H%M%S')}.zip"


def _write_export_zip(captures: list, zip_path: Path) -> int:
    """Skriver billeder + sidecar-JSON for hver capture til en ZIP-fil.
    Streamer til disk løbende (ikke i hukommelsen) — nogle kamera-lokationer
    har 20.000+ billeder, og en fuld in-memory ZIP ville kunne fylde flere GB."""
    written = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for capture in captures:
            src = _find_image(capture.device_id, capture.filename)
            if not src or not src.exists():
                continue
            arcname = f"{capture.captured_at.strftime('%Y%m%d_%H%M%S') if capture.captured_at else capture.id}_{capture.filename}"
            zf.write(str(src), arcname)
            sidecar = src.with_suffix(".json")
            if sidecar.exists():
                zf.write(str(sidecar), Path(arcname).with_suffix(".json").name)
            written += 1
    return written


@router.post("/api/admin/export/captures")
def export_captures(
    payload: dict,
    current_user=_require_role("admin"),
    db: Session = Depends(get_db),
):
    """Eksportér valgte billeder — eller en hel kamera-lokation — til en ZIP.

    2026-08-06 (Claude, Peter — koldt backup til USB): tre destinationer i ét
    endpoint, samme underliggende ZIP-bygning:
      - destination="download": streames som browser-download (temp-fil, ryddet
        op efter afsendelse via BackgroundTask — undgår at holde hele ZIP'en i
        RAM for store kamera-lokationer).
      - destination="path": skrives direkte til en sti på headend-serverens
        filsystem (en tilsluttet USB-disk under /Volumes, ELLER enhver anden
        fast konfigureret sti — samme tillidsmodel som headend/importer.py's
        allerede eksisterende `local_path`-import: admin-gated, ingen yderligere
        sti-begrænsning, fordi begge dele allerede kræver admin-rettigheder).
    """
    camera_id    = payload.get("camera_id")
    capture_ids  = payload.get("capture_ids")
    destination  = payload.get("destination", "download")
    dest_path    = payload.get("path")

    if camera_id:
        camera = db.query(Camera).filter_by(id=camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Kameralokation ikke fundet")
        if camera.site_id:
            _ensure_site_access(db, current_user, camera.site_id)
        elif camera.customer_id:
            _ensure_customer_access(current_user, camera.customer_id)
        captures = db.query(Capture).filter(Capture.camera_id == camera_id).order_by(Capture.captured_at).all()
        zip_name_base = camera.camera_name or camera_id
    elif capture_ids:
        captures = db.query(Capture).filter(Capture.id.in_(capture_ids)).all()
        for c in captures:
            if not _capture_is_allowed(db, current_user, c):
                raise HTTPException(status_code=403, detail="Ingen adgang til et eller flere billeder")
        zip_name_base = "billeder"
    else:
        raise HTTPException(status_code=400, detail="camera_id eller capture_ids skal angives")

    if not captures:
        raise HTTPException(status_code=404, detail="Ingen billeder fundet")

    if destination == "path":
        if not dest_path:
            raise HTTPException(status_code=400, detail="path påkrævet for destination=path")
        target_dir = Path(dest_path)
        if not target_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"Stien findes ikke eller er ikke en mappe: {dest_path}")
        zip_path = target_dir / _export_zip_filename(zip_name_base)
        written = _write_export_zip(captures, zip_path)
        log.info("Eksport: %d billeder skrevet til %s af %s", written, zip_path, current_user.username)
        return {"ok": True, "written_to": str(zip_path), "count": written}

    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip", prefix="tl_export_")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    written = _write_export_zip(captures, tmp_path)
    log.info("Eksport: %d billeder pakket til download af %s", written, current_user.username)
    filename = _export_zip_filename(zip_name_base)
    return FileResponse(
        str(tmp_path), media_type="application/zip", filename=filename,
        background=BackgroundTask(lambda: tmp_path.unlink(missing_ok=True)),
    )
