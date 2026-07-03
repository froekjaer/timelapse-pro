#!/usr/bin/env python3
"""Backfill normalized capture metadata from JPEG EXIF, sidecar and device config."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HEADEND = ROOT / "headend"
if str(HEADEND) not in sys.path:
    sys.path.insert(0, str(HEADEND))

from database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

CANONICAL_BASE = Path("/Volumes/data-fast/timelapse-incoming/canonical-images")


def _sanitize(value: str | None, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9æøåÆØÅ_-]", "_", str(value or fallback)).strip("_")
    return cleaned or fallback


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _ratio(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numerator = getattr(value, "numerator", None)
        denominator = getattr(value, "denominator", None)
        if numerator is not None and denominator:
            return float(numerator) / float(denominator)
        if isinstance(value, tuple) and len(value) == 2 and value[1]:
            return float(value[0]) / float(value[1])
        return float(value)
    except Exception:
        return None


def _fmt_shutter(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    if seconds < 1:
        return f"{seconds:.4f}s"
    return f"{seconds:.1f}s".replace(".0s", "s")


def _fmt_aperture(f_number: float | None) -> str | None:
    if f_number is None:
        return None
    return f"f/{f_number:.1f}".replace(".0", "")


def _fmt_focal(mm: float | None) -> str | None:
    if mm is None:
        return None
    return f"{mm:.1f} mm".replace(".0 mm", " mm")


def _read_jpeg_exif(path: Path) -> dict:
    try:
        from PIL import ExifTags, Image
    except Exception:
        return {}
    try:
        with Image.open(path) as img:
            exif = img.getexif() or {}
            exif_ifd = {}
            gps_ifd = {}
            try:
                exif_ifd = exif.get_ifd(34665) or {}
            except Exception:
                pass
            try:
                gps_ifd = exif.get_ifd(34853) or {}
            except Exception:
                pass
            named = {ExifTags.TAGS.get(k, k): v for k, v in dict(exif).items()}
            named.update({ExifTags.TAGS.get(k, k): v for k, v in dict(exif_ifd).items()})
            gps_named = {ExifTags.GPSTAGS.get(k, k): v for k, v in dict(gps_ifd).items()}
    except Exception:
        return {}

    make = str(named.get("Make") or "").strip()
    model = str(named.get("Model") or "").strip()
    camera_model = model
    if make and model and make.lower() not in model.lower():
        camera_model = f"{make} {model}"
    elif make and not model:
        camera_model = make
    return {
        "camera_model": camera_model or None,
        "iso": _int(named.get("ISOSpeedRatings") or named.get("PhotographicSensitivity")),
        "aperture": _fmt_aperture(_ratio(named.get("FNumber"))),
        "exposure_time": _fmt_shutter(_ratio(named.get("ExposureTime"))),
        "focal_length": _fmt_focal(_ratio(named.get("FocalLength"))),
        "lens_model": named.get("LensModel"),
        "gps_version": gps_named.get("GPSVersionID"),
    }


def _capture_image_path(capture: dict, device: dict | None) -> Path | None:
    if capture.get("sidecar_path"):
        sidecar = Path(capture["sidecar_path"])
        image = sidecar.with_suffix(".jpg")
        if image.exists():
            return image
        image = sidecar.with_suffix(".jpeg")
        if image.exists():
            return image
    if not device or not capture.get("captured_at") or not capture.get("filename"):
        return None
    dt = capture["captured_at"]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    candidate = (
        CANONICAL_BASE
        / _sanitize(device.get("customer_name"), "UnknownCustomer")
        / _sanitize(device.get("site_name"), "UnknownSite")
        / _sanitize(device.get("camera_name"), device.get("device_id") or "UnknownDevice")
        / f"{dt.year:04d}"
        / f"{dt.month:02d}"
        / f"{dt.day:02d}"
        / capture["filename"]
    )
    return candidate if candidate.exists() else None


def _device_metadata(device: dict | None) -> dict:
    if not device:
        return {}
    try:
        cfg = json.loads(device.get("device_config") or "{}")
    except Exception:
        cfg = {}
    loc = cfg.get("location") if isinstance(cfg.get("location"), dict) else {}
    cam = cfg.get("camera") if isinstance(cfg.get("camera"), dict) else {}
    return {
        "project": {
            "customer": device.get("customer_name"),
            "site": device.get("site_name"),
            "camera_name": device.get("camera_name"),
            "device_id": device.get("device_id"),
            "camera_index": device.get("camera_index"),
        },
        "location": {
            "gps_lat": loc.get("gps_lat"),
            "gps_lon": loc.get("gps_lon"),
            "gps_alt_m": loc.get("gps_alt_m", loc.get("gps_alt")),
            "gps_source": loc.get("gps_source"),
            "address": loc.get("address"),
            "azimuth_deg": cam.get("azimuth_deg"),
            "tilt_deg": cam.get("tilt_deg"),
            "mount_height_m": cam.get("mount_height_m"),
            "fov_horizontal_deg": cam.get("fov_horizontal_deg"),
            "fov_vertical_deg": cam.get("fov_vertical_deg"),
            "perspective": cam.get("perspective"),
        },
        "camera": {
            "gphoto2_port": cam.get("gphoto2_port"),
            "relay_gpio_pin": cam.get("relay_gpio_pin"),
        },
    }


def _merge_sidecar(sidecar_path: Path, exif: dict, device_meta: dict, commit: bool) -> dict:
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8")) if sidecar_path.exists() else {}
    except Exception:
        sidecar = {}
    sidecar.setdefault("camera", {})
    sidecar.setdefault("location", {})
    sidecar.setdefault("project", {})
    sidecar.setdefault("added_metadata", {}).setdefault("fields_added", [])

    if exif.get("camera_model"):
        sidecar["camera"]["model"] = exif["camera_model"]
    for src, dst in [
        ("iso", "iso"),
        ("aperture", "aperture"),
        ("exposure_time", "shutter_speed"),
        ("focal_length", "focal_length"),
        ("lens_model", "lens_model"),
    ]:
        if exif.get(src) is not None:
            sidecar["camera"][dst] = exif[src]

    for section in ("project", "location", "camera"):
        for key, value in (device_meta.get(section) or {}).items():
            if value is not None and sidecar.setdefault(section, {}).get(key) is None:
                sidecar[section][key] = value

    added = set(sidecar.get("added_metadata", {}).get("fields_added") or [])
    for key in ("gps_lat", "gps_lon", "gps_alt_m", "azimuth_deg", "tilt_deg", "mount_height_m", "fov_horizontal_deg"):
        if sidecar.get("location", {}).get(key) is not None:
            added.add(key)
    sidecar["added_metadata"]["fields_added"] = sorted(added)

    if commit:
        sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return sidecar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    updated = 0
    missing = 0
    try:
        capture_sql = """
            SELECT id, device_id, filename, captured_at, camera_model, iso, aperture,
                   exposure_time, gps_lat, gps_lon, gps_alt_m, gps_source,
                   azimuth_deg, tilt_deg, mount_height_m, fov_horizontal_deg,
                   fov_vertical_deg, perspective, sidecar_path
            FROM captures
        """
        params = {}
        if args.device_id:
            capture_sql += " WHERE device_id = :device_id"
            params["device_id"] = args.device_id
        capture_sql += " ORDER BY captured_at DESC"
        if args.limit:
            capture_sql += " LIMIT :limit"
            params["limit"] = args.limit
        captures = [dict(r._mapping) for r in db.execute(text(capture_sql), params).fetchall()]
        devices = {
            r._mapping["device_id"]: dict(r._mapping)
            for r in db.execute(text(
                "SELECT device_id, customer_name, site_name, camera_name, camera_index, device_config FROM devices"
            )).fetchall()
        }
        for capture in captures:
            device = devices.get(capture["device_id"])
            image_path = _capture_image_path(capture, device)
            if not image_path:
                missing += 1
                continue
            exif = _read_jpeg_exif(image_path)
            device_meta = _device_metadata(device)
            sidecar_path = Path(capture["sidecar_path"]) if capture.get("sidecar_path") else image_path.with_suffix(".json")
            sidecar = _merge_sidecar(sidecar_path, exif, device_meta, args.commit)
            loc = sidecar.get("location", {})

            changes = {
                "camera_model": exif.get("camera_model"),
                "iso": exif.get("iso"),
                "aperture": exif.get("aperture"),
                "exposure_time": exif.get("exposure_time"),
                "gps_lat": _float(loc.get("gps_lat")),
                "gps_lon": _float(loc.get("gps_lon")),
                "gps_alt_m": _float(loc.get("gps_alt_m")),
                "gps_source": loc.get("gps_source"),
                "azimuth_deg": _float(loc.get("azimuth_deg")),
                "tilt_deg": _float(loc.get("tilt_deg")),
                "mount_height_m": _float(loc.get("mount_height_m")),
                "fov_horizontal_deg": _float(loc.get("fov_horizontal_deg")),
                "fov_vertical_deg": _float(loc.get("fov_vertical_deg")),
                "perspective": loc.get("perspective"),
                "sidecar_path": str(sidecar_path),
            }
            changed = False
            updates = {}
            for key, value in changes.items():
                if value is None:
                    continue
                if args.overwrite or capture.get(key) in (None, ""):
                    if capture.get(key) != value:
                        updates[key] = value
                        changed = True
            if changed:
                updated += 1
                if args.commit:
                    assignments = ", ".join(f"{key} = :{key}" for key in updates)
                    db.execute(
                        text(f"UPDATE captures SET {assignments} WHERE id = :id"),
                        {**updates, "id": capture["id"]},
                    )
        if args.commit:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    mode = "committed" if args.commit else "dry-run"
    print(json.dumps({"mode": mode, "updated": updated, "missing_images": missing}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
