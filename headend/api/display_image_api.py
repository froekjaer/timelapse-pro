"""Display-resolution image serving (2026-09-20).

Full-resolution capture originals (typically 5-8 MB, camera-native) are
unnecessarily large for on-screen viewing — this, combined with bufferbloat
on constrained connections, was the root cause of slow image loading in the
device Lightbox (see Dokumentation/HANDOVER_LOG.md 2026-09-20). This module
serves a much smaller "display" variant (2048px longest edge, quality 85 —
typically 5-10x smaller than the original with no visible on-screen quality
loss), cached per-image next to the original in a `.display` sibling
directory, mirroring the existing `.thumbs`/`.headend-thumbs` convention.

The Download action and any other consumer of the true original continue to
use `/api/images/...` unchanged; only on-screen viewing uses this endpoint.

Deliberately different policy from thumbnails (`get_thumbnail` in
headend/main.py never generates inline — "aldrig generér i en display-
request", because a gallery grid can request 100+ thumbnails at once, a
thundering herd of concurrent generations). Display images are requested at
most 1-2 at a time (the Lightbox shows one image; neighbour prefetch is
already strictly sequential — see timelapse-ui/src/lib/prefetchQueue.ts) —
a fundamentally different concurrency profile. Generation is therefore
allowed inline here, bounded by a small semaphore with a short timeout, and
on any failure this endpoint falls back to serving the true original — so it
can only ever improve on today's behaviour, never regress or error where
/api/images would have succeeded.

This lives in its own module (not headend/main.py) per this repo's own
architecture ratchet (tests/architecture_baseline.json caps main.py's line
and route count) and the K2 convention from RISK_ASSESSMENT_v11_ADDENDUM
("nye ruter som APIRouter i domænemodul, ikke i main.py"). It needs several
of main.py's private helpers (capture access control, access logging,
X-Accel delivery, device-id sanitization) that aren't in a shared module, so
`setup_display_router()` takes them as callbacks — the same factory pattern
already used by `setup_ai_router` in headend/ai/integration.py.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
from collections.abc import Callable
from pathlib import Path

from auth import require_role
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

DISPLAY_MAX_DIMENSION = int(os.getenv("TIMELAPSE_DISPLAY_MAX_DIMENSION", "2048"))
DISPLAY_JPEG_QUALITY = int(os.getenv("TIMELAPSE_DISPLAY_JPEG_QUALITY", "85"))

# Independent from headend/main.py's thumbnail-repair semaphore: display
# generation has a different (much lower) concurrency profile, so it gets
# its own small, dedicated bound rather than competing for that one.
_display_gen_semaphore = threading.BoundedSemaphore(
    int(os.getenv("TIMELAPSE_DISPLAY_GEN_CONCURRENCY", "2")))


def display_dir_for(image_path: Path) -> Path:
    """Return the .display cache directory next to the image."""
    return image_path.parent / ".display"


def _is_valid_jpeg(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size >= 256
    except OSError:
        return False


def find_existing_display(image_path: Path) -> Path | None:
    candidate = display_dir_for(image_path) / image_path.name
    return candidate if _is_valid_jpeg(candidate) else None


def generate_display_image(src: Path, dest: Path) -> tuple[bool, str | None]:
    try:
        from PIL import Image, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = os.getenv("TIMELAPSE_THUMBNAIL_ALLOW_TRUNCATED", "true").lower() in {"1", "true", "yes", "on"}
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = dest.parent / f".{dest.name}.{secrets.token_hex(8)}.tmp"
        try:
            with Image.open(src) as original:
                img = original.convert("RGB")
                if max(img.width, img.height) > DISPLAY_MAX_DIMENSION:
                    img.thumbnail((DISPLAY_MAX_DIMENSION, DISPLAY_MAX_DIMENSION), Image.LANCZOS)
                img.save(str(tmp_dest), "JPEG", quality=DISPLAY_JPEG_QUALITY)
            os.replace(tmp_dest, dest)
            return True, None
        finally:
            tmp_dest.unlink(missing_ok=True)
    except Exception as exc:
        error = str(exc)
        log.warning("Display image generation failed for %s: %s", src, error)
        return False, error


def bounded_generate_display(src: Path, dest: Path) -> tuple[bool, str | None]:
    """generate_display_image() bound by a short timeout on the dedicated
    semaphore. On timeout/failure: return (False, ...) — the caller falls
    back to serving the true original, never an error to the user."""
    acquired = _display_gen_semaphore.acquire(
        timeout=float(os.getenv("TIMELAPSE_DISPLAY_GEN_TIMEOUT_S", "5")))
    if not acquired:
        return False, "concurrency_limit"
    try:
        return generate_display_image(src, dest)
    finally:
        _display_gen_semaphore.release()


FindImageFn = Callable[[str, str], Path | None]
EnsureAccessFn = Callable[..., object]
LogAccessFn = Callable[..., None]
XAccelFn = Callable[..., object | None]
SanitizeDeviceIdFn = Callable[[str], str]


def setup_display_router(
    find_image_fn: FindImageFn,
    ensure_access_fn: EnsureAccessFn,
    log_access_fn: LogAccessFn,
    xaccel_fn: XAccelFn,
    sanitize_device_id_fn: SanitizeDeviceIdFn,
) -> APIRouter:
    """Build the /api/display router. Called once, at import time, from
    headend/main.py (right after `_ensure_capture_file_access` is defined),
    passing in its private capture-access/logging/X-Accel helpers — see the
    module docstring for why this needs the callback indirection."""
    router = APIRouter()

    @router.get("/api/display/{device_id}/{filename}")
    def get_display_image(
        device_id: str,
        filename: str,
        _user=require_role("viewer"),
        db: Session = Depends(get_db),
    ):
        from urllib.parse import unquote

        sanitize_device_id_fn(device_id)
        filename = unquote(filename)
        capture = ensure_access_fn(db, _user, device_id, filename)
        src = find_image_fn(device_id, filename)
        if not src:
            raise HTTPException(status_code=404, detail="Image not found")
        log_access_fn(db, _user, capture, action="display_view")
        cache_control = "private, max-age=604800"

        display = find_existing_display(src)
        if not display:
            candidate = display_dir_for(src) / src.name
            ok, _err = bounded_generate_display(src, candidate)
            if ok:
                display = candidate

        served = display if display else src
        served_cache_control = cache_control if served is display else ""
        xr = xaccel_fn(served, "image/jpeg", served_cache_control)
        if xr is not None:
            return xr
        headers = {"Cache-Control": cache_control, "X-Image-Variant": "display"} if served is display else {}
        return FileResponse(str(served), media_type="image/jpeg", headers=headers)

    return router
