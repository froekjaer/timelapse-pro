"""Regression test (2026-08-06): Peter asked for GDPR-compliant deletion of
specific images or an entire camera location, plus export to cold backup
(USB disk / browser download / a fixed configured path).

Per-image GDPR deletion already existed (services/capture_deletion_service.py
via /api/admin/captures/bulk-delete, already wired in TimelineNavigator.tsx —
deletes the file, thumbnail, sidecar, and DB row, with an independent
CaptureDeletionLog audit record). What was missing: a whole-camera-location
variant, and any export capability at all.

gdpr_delete_camera_captures() (headend/api/camera_locations_api.py) must
reuse that SAME audited, file-deleting delete_capture() service (not a raw
bulk SQL delete like force_delete_camera_location() intentionally uses for
the "wrong location, right images" cleanup case) — a real GDPR erasure
request must remove the files, not just the catalog row.

export_captures() (headend/api/export_api.py) must support both delivery
modes Peter asked for: a streamed download and a direct filesystem write
(covers both "USB drive mounted under /Volumes" and "any other fixed
configured path" — same mechanism, different destination), and must never
build the whole ZIP in memory (some camera locations have 20,000+ captures).

Both modules were extracted from headend/main.py same day (see their
docstrings and Peter's reminder that the architecture-ratchet baseline
exists to force extraction, not to be raised indefinitely instead of it).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMERA_LOCATIONS_API = (ROOT / "headend" / "api" / "camera_locations_api.py").read_text(encoding="utf-8")
EXPORT_API = (ROOT / "headend" / "api" / "export_api.py").read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    start = source.index(f"def {name}(")
    try:
        end = source.index("\n@router.", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


def test_gdpr_delete_reuses_the_file_deleting_capture_service() -> None:
    section = _function_source(CAMERA_LOCATIONS_API, "gdpr_delete_camera_captures")
    assert "from services.capture_deletion_service import delete_capture" in section
    assert 'deletion_reason="gdpr_request"' in section
    assert "find_image=_find_image" in section
    assert "unlink_thumbnails=_unlink_thumbnail_variants" in section


def test_gdpr_delete_does_not_touch_the_camera_row_itself() -> None:
    section = _function_source(CAMERA_LOCATIONS_API, "gdpr_delete_camera_captures")
    assert "db.delete(camera)" not in section, (
        "gdpr_delete_camera_captures must only erase historical image data — the "
        "camera location itself must stay intact so the site can keep capturing "
        "new images afterward. Removing the location is a separate, structural "
        "decision (force_delete_camera_location / retire_empty_camera_location)."
    )


def test_export_supports_download_and_direct_path_destinations() -> None:
    section = _function_source(EXPORT_API, "export_captures")
    assert 'destination == "path"' in section
    assert "FileResponse(" in section
    assert "BackgroundTask(" in section, (
        "the download path must clean up its temp zip file after the response is "
        "sent, or repeated exports would leak temp files to disk."
    )


def test_export_streams_to_disk_instead_of_building_in_memory() -> None:
    section = _function_source(EXPORT_API, "_write_export_zip")
    assert "ZipFile(zip_path" in section, (
        "must write the zip directly to a file path (streaming), not accumulate it "
        "in an in-memory buffer — some camera locations have 20,000+ captures."
    )


def test_export_enforces_tenant_access_for_both_lookup_modes() -> None:
    section = _function_source(EXPORT_API, "export_captures")
    assert "_ensure_site_access(db, current_user, camera.site_id)" in section
    assert "_capture_is_allowed(db, current_user, c)" in section


def test_export_router_is_included_from_main() -> None:
    main_source = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
    assert "from api.export_api import router as _export_router" in main_source
    assert "app.include_router(_export_router)" in main_source
