"""
TimeLapse Pro — Thumbnail Serving, Repair & Backlog
======================================================
2026-08-06 (Claude): extracted from headend/main.py (module ratchet — see
tests/test_architecture_ratchet.py). Handles everything specific to
thumbnails: locating an existing edge-generated thumbnail, on-demand repair
generation (bounded, rate-limited), the backlog status endpoint, and the
background auto-repair loop.

Image LOCATION resolution (_find_image et al.) lives in headend/media_paths.py
instead — it's used well beyond thumbnails (image download, export, retention),
so it stays a separate, lower-level module both this file and main.py import
from, avoiding a false thumbnails->main.py dependency for something main.py
itself also needs.

Auth/access-control helpers (_ensure_capture_file_access,
_log_capture_access_deduplicated, _xaccel_redirect, require_role, get_db) are
imported lazily from `main` inside each function body — the established
pattern in this codebase (see api/storage_api.py) for the same reason: main.py
imports this module's router near the END of its own definition, so a
top-level `from main import ...` here would fail (main isn't finished
executing yet), but a function-body import resolves fine at call time.
"""

from __future__ import annotations

import logging
import os
import threading as _threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import Capture, get_db
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
    """Local re-implementation of main.require_role(), same rationale as
    api/storage_api.py's _current_viewer: main.py imports this router near
    the END of its own module body, so a top-level `from main import
    require_role` would need `main` fully initialised at IMPORT time — it
    isn't, yet, at that point. The underlying pieces (get_current_user,
    MFA checks) are imported lazily inside `_check`, which only runs at
    REQUEST time, by which point main.py has long finished loading."""
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


def _sanitize_device_id(device_id: str) -> None:
    from main import _sanitize_device_id as _impl
    _impl(device_id)


# ── Thumbnail location + generation ─────────────────────────────────────────

def _thumbs_dir_for(image_path) -> "os.PathLike":
    """Return .thumbs directory next to the image."""
    return image_path.parent / ".thumbs"


def _generated_thumbs_dir_for(image_path):
    """Return headend-owned fallback thumbnail directory."""
    return image_path.parent / ".headend-thumbs"


_thumbnail_generation_lock = _threading.Lock()
_thumbnail_generation_active: set[str] = set()


def _is_valid_jpeg(path) -> bool:
    try:
        if not path.exists() or path.stat().st_size < 256:
            return False
        if os.getenv("TIMELAPSE_STRICT_THUMBNAIL_VERIFY", "0").lower() in {"1", "true", "yes"}:
            from PIL import Image
            with Image.open(path) as existing:
                existing.verify()
        return True
    except Exception:
        return False


def _thumbnail_candidates_for(image_path):
    stem = image_path.stem
    suffix = image_path.suffix or ".jpg"
    return [
        image_path.parent / ".thumbs" / image_path.name,
        image_path.parent / ".headend-thumbs" / image_path.name,
        image_path.parent / "thumbs" / image_path.name,
        image_path.parent / "thumbnails" / image_path.name,
        image_path.parent / f"thumb_{image_path.name}",
        image_path.parent / f"thumbnail_{image_path.name}",
        image_path.parent / f"{stem}_thumb{suffix}",
        image_path.parent / f"{stem}.thumb{suffix}",
    ]


def _find_existing_thumbnail(image_path):
    for candidate in _thumbnail_candidates_for(image_path):
        if _is_valid_jpeg(candidate):
            return candidate
    return None


def _generate_edge_thumbnail(src, thumb) -> tuple[bool, str | None]:
    import secrets as _secrets
    key = str(thumb)
    try:
        from PIL import Image, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = os.getenv("TIMELAPSE_THUMBNAIL_ALLOW_TRUNCATED", "true").lower() in {"1", "true", "yes", "on"}
        thumb.parent.mkdir(parents=True, exist_ok=True)
        tmp_thumb = thumb.parent / f".{thumb.name}.{_secrets.token_hex(8)}.tmp"
        try:
            with Image.open(src) as original:
                img = original.convert("RGB")
                img.thumbnail((320, 180), Image.LANCZOS)
                canvas = Image.new("RGB", (320, 180), (15, 15, 15))
                offset = ((320 - img.width) // 2, (180 - img.height) // 2)
                canvas.paste(img, offset)
                canvas.save(str(tmp_thumb), "JPEG", quality=78)
            os.replace(tmp_thumb, thumb)
            log.info("Thumbnail repair generated: %s", thumb)
            return True, None
        finally:
            tmp_thumb.unlink(missing_ok=True)
    except Exception as exc:
        error = str(exc)
        log.warning("Thumbnail repair failed for %s: %s", src, error)
        return False, error
    finally:
        with _thumbnail_generation_lock:
            _thumbnail_generation_active.discard(key)


# Global samtidigheds-grænse for thumbnail-generering. Beskytter data-fast mod
# "thundering herd": et galleri med mange manglende thumbnails fyrede før 100+
# samtidige genereringer (hver læser et fuldopløst billede) → volumenet druknede
# og de fleste timeout'ede. Nu serialiseres de til N ad gangen.
_thumb_gen_semaphore = _threading.BoundedSemaphore(
    int(os.getenv("TIMELAPSE_THUMBNAIL_GEN_CONCURRENCY", "3")))


def _bounded_generate_thumbnail(src, thumb) -> tuple[bool, str | None]:
    """_generate_edge_thumbnail med global samtidigheds-grænse."""
    acquired = _thumb_gen_semaphore.acquire(
        timeout=float(os.getenv("TIMELAPSE_THUMBNAIL_GEN_TIMEOUT_S", "20")))
    if not acquired:
        with _thumbnail_generation_lock:
            _thumbnail_generation_active.discard(str(thumb))
        return False, "concurrency_limit"
    try:
        return _generate_edge_thumbnail(src, thumb)
    finally:
        _thumb_gen_semaphore.release()


def _unlink_thumbnail_variants(image_path, filename: str) -> bool:
    deleted = False
    for directory in (_thumbs_dir_for(image_path), _generated_thumbs_dir_for(image_path)):
        try:
            thumb = directory / filename
            if thumb.exists():
                thumb.unlink(missing_ok=True)
                deleted = True
        except Exception as exc:
            log.warning("Kunne ikke slette thumbnail i %s: %s", directory, exc)
    return deleted


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/api/thumbnails/{device_id}/{filename}")
def get_thumbnail(
    device_id: str,
    filename: str,
    _user=_require_role("viewer"),
    db: Session = Depends(get_db),
):
    from main import _ensure_capture_file_access, _log_capture_access_deduplicated, _xaccel_redirect
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    capture = _ensure_capture_file_access(db, _user, device_id, filename)
    src = _find_image(device_id, filename)
    if not src:
        raise HTTPException(status_code=404, detail="Image not found")
    _log_capture_access_deduplicated(db, _user, capture, action="thumbnail_view")
    _thumb_cache = "private, max-age=86400"
    thumb = _find_existing_thumbnail(src)
    if thumb:
        xr = _xaccel_redirect(thumb, "image/jpeg", _thumb_cache)
        if xr is not None:
            return xr
        return FileResponse(
            str(thumb),
            media_type="image/jpeg",
            headers={
                "Cache-Control": _thumb_cache,
                "X-Thumbnail-Source": "edge",
            },
        )

    # Never generate inside a display request. The UI queues a bounded
    # background repair after a 404, while normal uploads generate thumbnails
    # on the Edge before transfer.
    raise HTTPException(
        status_code=404,
        detail="Thumbnail missing; Edge/backfill must generate and upload thumbnails",
    )


@router.post("/api/thumbnails/{device_id}/{filename}/generate")
def request_thumbnail_generation(
    device_id: str,
    filename: str,
    _user=_require_role("viewer"),
    db: Session = Depends(get_db),
):
    from main import _ensure_capture_file_access
    from urllib.parse import unquote as _unquote
    _sanitize_device_id(device_id)
    filename = _unquote(filename)
    _ensure_capture_file_access(db, _user, device_id, filename)
    src = _find_image(device_id, filename)
    if not src:
        raise HTTPException(status_code=404, detail="Image not found")

    existing = _find_existing_thumbnail(src)
    if existing:
        return {"status": "ready", "source": "edge", "thumbnail": str(existing)}

    thumb = _thumbs_dir_for(src) / src.name
    key = str(thumb)
    with _thumbnail_generation_lock:
        if key in _thumbnail_generation_active:
            return {"status": "queued", "thumbnail": str(thumb)}
        _thumbnail_generation_active.add(key)

    _threading.Thread(target=_bounded_generate_thumbnail, args=(src, thumb), daemon=True).start()
    return {"status": "queued", "thumbnail": str(thumb)}


@router.get("/api/admin/thumbnail-backlog")
def get_thumbnail_backlog(
    scan_limit: int = Query(500, ge=50, le=5000),
    current_user=_require_role("admin"),
    db: Session = Depends(get_db),
):
    """Returner status på thumbnails der mangler.

    P2-02 (2026-07-07): API endpoint til thumbnail backlog.
    Beregner antal captures der mangler thumbnails (med device_id filter).
    Resultatet cachelives kort (5s) for at undgå tunge scans ved gentagne kald.
    """
    from main import _allowed_capture_device_ids
    from time import time as _t

    # Brug samme device-id filtrering som post-processing
    allowed_device_ids = _allowed_capture_device_ids(db, current_user)
    query = db.query(Capture.id, Capture.device_id, Capture.filename).filter(
        Capture.filename.isnot(None)
    )
    if allowed_device_ids is not None:
        if not allowed_device_ids:
            return {"total": 0, "missing": 0, "devices": {}}
        query = query.filter(Capture.device_id.in_(allowed_device_ids))

    t0 = _t()
    total_count = 0
    missing_count = 0
    device_missing: dict[str, int] = {}

    available_count = query.count()
    batch = query.order_by(Capture.captured_at.desc()).limit(scan_limit).all()
    for capture_id, device_id, filename in batch:
        total_count += 1
        image_path = _find_image(device_id, filename)
        if not image_path:
            continue  # Filen mangler — tæller ikke som "missing thumbnail"

        thumb = _find_existing_thumbnail(image_path)
        if not thumb:
            missing_count += 1
            device_missing[device_id] = device_missing.get(device_id, 0) + 1

    elapsed = _t() - t0
    log.info("Thumbnail backlog: %d/%d mangler (%.2fs)", missing_count, total_count, elapsed)

    return {
        "total": total_count,
        "missing": missing_count,
        "devices": device_missing,
        "scan_time_seconds": round(elapsed, 2),
        "partial": available_count > total_count,
        "available": available_count,
    }


# ── Background auto-repair loop ─────────────────────────────────────────────

def _thumbnail_auto_loop() -> None:
    """2026-07-06 (Claude, P2-02): Auto thumbnail generation loop.
    Løbende tjek for captures der mangler thumbnails og genererer dem automatisk.
    Tjekker hvert 15. minut for nye captures uden thumbnails.

    2026-08-06 (Claude, Peter fandt fejlen live): den oprindelige version
    scannede UDELUKKENDE de 500 globalt seneste captures (ORDER BY
    captured_at DESC LIMIT 500). Det virker fint for et system med kun
    aktive Edge-enheder (som selv genererer thumbnails FØR upload — de
    rammer sjældent dette loop), men en aktivt-capturende enhed (fx hvert
    ~95. sekund) fylder det vindue konstant op med nyere captures, så en
    kameralokation med ældre, bulk-importerede billeder (ingen Edge til at
    forudgenerere thumbnails — se camera_id for "Travbyen" i CMDB) ALDRIG
    kunne nås, uanset hvor længe loopet kørte. Rettet ved at TILFØJE en
    roterende baglæns-scanning (_backlog_offset), der over tid dækker HELE
    tabellen ældst-først, ved siden af det eksisterende hurtig-spor for
    nyeste captures (som stadig sikrer at helt nye uploads repareres hurtigt).
    """
    import time as _t

    CHECK_INTERVAL_SECONDS = 900  # 15 minutter
    MAX_THUMBNAILS_PER_RUN = 100  # Maksimalt antal thumbnails per run (for at undgå lange runs)
    RECENT_SCAN_LIMIT = 500       # Hurtig-spor: nyeste captures først
    BACKLOG_SCAN_LIMIT = 500      # Roterende spor: dækker HELE historikken over tid

    _t.sleep(180)  # 3 minutters forsinkelse efter opstart
    log.info("Thumbnail auto loop startet (tjekker hvert 15. min for manglende thumbnails)")

    _backlog_offset = 0

    while True:
        try:
            from database import SessionLocal as _SL

            db = _SL()
            try:
                # Find captures der mangler thumbnails
                # Vi tjekker om filen eksisterer og om .thumbs/{filename} mangler
                captures_missing_thumbs = []
                seen_ids: set = set()

                recent_query = db.query(Capture).filter(
                    Capture.filename.isnot(None)
                ).order_by(Capture.captured_at.desc()).limit(RECENT_SCAN_LIMIT)

                for capture in recent_query.all():
                    image_path = _find_image(capture.device_id, capture.filename)
                    if not image_path:
                        continue  # Filen mangler — spring over

                    thumb = _find_existing_thumbnail(image_path)
                    if not thumb:
                        seen_ids.add(capture.id)
                        captures_missing_thumbs.append((capture.id, capture.device_id, capture.filename, image_path))
                        if len(captures_missing_thumbs) >= MAX_THUMBNAILS_PER_RUN:
                            break

                # Baglæns-spor: roterer gennem HELE tabellen (ældst-først) via en
                # fremadskridende offset, så historiske/importerede captures uden
                # for det "seneste"-vindue ovenfor med tiden alle bliver dækket.
                if len(captures_missing_thumbs) < MAX_THUMBNAILS_PER_RUN:
                    total_with_filename = db.query(Capture).filter(Capture.filename.isnot(None)).count()
                    if total_with_filename > 0:
                        _backlog_offset %= total_with_filename
                        backlog_query = db.query(Capture).filter(
                            Capture.filename.isnot(None)
                        ).order_by(Capture.captured_at.asc()).offset(_backlog_offset).limit(BACKLOG_SCAN_LIMIT)
                        backlog_batch = backlog_query.all()

                        for capture in backlog_batch:
                            if capture.id in seen_ids:
                                continue
                            image_path = _find_image(capture.device_id, capture.filename)
                            if not image_path:
                                continue

                            thumb = _find_existing_thumbnail(image_path)
                            if not thumb:
                                captures_missing_thumbs.append((capture.id, capture.device_id, capture.filename, image_path))
                                if len(captures_missing_thumbs) >= MAX_THUMBNAILS_PER_RUN:
                                    break

                        _backlog_offset = (_backlog_offset + len(backlog_batch)) if backlog_batch else 0

                if captures_missing_thumbs:
                    log.info("Thumbnail auto loop: fundet %d captures uden thumbnails (max %d per run)",
                             len(captures_missing_thumbs), MAX_THUMBNAILS_PER_RUN)

                    generated = 0
                    failed = 0

                    for capture_id, device_id, filename, image_path in captures_missing_thumbs:
                        if _thumbnail_generation_lock.locked():
                            log.info("Thumbnail generation allerede i gang — springer resten over")
                            break

                        try:
                            target = _thumbs_dir_for(image_path) / filename
                            ok, error = _generate_edge_thumbnail(image_path, target)
                            if ok and _is_valid_jpeg(target):
                                generated += 1
                                if generated % 10 == 0:
                                    log.info("Thumbnail auto loop: genereret %d thumbnails så langt", generated)
                            else:
                                failed += 1
                                log.warning("Thumbnail auto loop: fejlede for %s: %s", filename, error)
                        except Exception as _thumb_err:
                            failed += 1
                            log.error("Thumbnail auto loop: exception for %s: %s", filename, _thumb_err)

                    log.info("Thumbnail auto loop: færdig — %d genereret, %d fejlet", generated, failed)
                else:
                    log.debug("Thumbnail auto loop: ingen manglende thumbnails (sampled 500 seneste captures)")

            finally:
                db.close()

        except Exception as _loop_err:
            log.warning("Thumbnail auto loop fejl: %s", _loop_err)

        _t.sleep(CHECK_INTERVAL_SECONDS)
