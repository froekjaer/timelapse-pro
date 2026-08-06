# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — importer.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.0.0
# Dato     : 2026-05-11
# ═══════════════════════════════════════════════════════════════════════════
"""
Import af historiske billeder til TimeLapse Pro.

Flow:
  1. UI poster POST /api/import/start med kunde/site/kamera + sti eller ZIP
  2. Baggrunds-thread behandler hvert billede:
     - Læser EXIF fra original (exifread + PIL fallback)
     - Beregner SHA-256
     - Omdøber til standard format: Kunde_Site_Kamera_YYYYMMDD_HHMMSS.jpg
     - Kopierer til SFTP_BASE/Kunde/Site/Kamera/YYYY/MM/DD/
     - Kører kvalitetstjek (blur + lysstyrke via PIL)
     - Skriver sidecar JSON
     - Skriver XMP metadata via exiftool (hvis tilgængeligt)
     - Opretter capture-record i PostgreSQL
  3. UI poller GET /api/import/status/<job_id> for progress
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from database import Camera, Capture, Customer, Device, DeviceAssignment, Site, get_db, now_utc

log = logging.getLogger(__name__)

def _to_local(dt) -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Copenhagen")).isoformat()
    except Exception:
        return dt.isoformat()


router = APIRouter(tags=["Import"])

# ── Job registry ──────────────────────────────────────────────────────────────
# { job_id: { status, total, processed, errors, log, started_at, finished_at } }
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize(s: str) -> str:
    """Omdanner streng til filnavn-sikkert format."""
    return re.sub(r"[^A-Za-z0-9æøåÆØÅ]", "_", str(s)).strip("_") if s else ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_exif(path: Path) -> dict:
    """Læser EXIF fra billede. Returnerer dict med tilgængelige felter."""
    exif = {}
    try:
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="UNDEF", details=False)

        def get(key: str):
            v = tags.get(key)
            return str(v) if v else None

        exif["model"]        = get("Image Model") or get("Image Make")
        exif["iso"]          = get("EXIF ISOSpeedRatings")
        exif["aperture"]     = get("EXIF FNumber") or get("EXIF ApertureValue")
        exif["shutter"]      = get("EXIF ExposureTime") or get("EXIF ShutterSpeedValue")
        exif["focal_length"] = get("EXIF FocalLength")
        exif["flash"]        = get("EXIF Flash")

        # Forsøg at parse dato fra EXIF
        dt_str = get("EXIF DateTimeOriginal") or get("Image DateTime")
        if dt_str:
            try:
                dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                exif["datetime_utc"] = dt.replace(tzinfo=timezone.utc).isoformat()
                exif["datetime_obj"] = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    except Exception as e:
        log.debug("EXIF læsning fejlede for %s: %s", path.name, e)
    if not exif.get("model") or not exif.get("iso") or not exif.get("aperture") or not exif.get("shutter"):
        try:
            from PIL import Image, ExifTags

            def _rat(value):
                if value is None:
                    return None
                try:
                    if isinstance(value, tuple) and len(value) == 2 and value[1]:
                        return float(value[0]) / float(value[1])
                    return float(value)
                except Exception:
                    return None

            with Image.open(path) as img:
                raw = img.getexif() or {}
                named = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
                model = named.get("Model")
                make = named.get("Make")
                if model and not exif.get("model"):
                    exif["model"] = f"{make} {model}".strip() if make and str(make) not in str(model) else str(model)
                if named.get("ISOSpeedRatings") is not None and not exif.get("iso"):
                    exif["iso"] = str(named.get("ISOSpeedRatings"))
                fnum = _rat(named.get("FNumber"))
                if fnum is not None and not exif.get("aperture"):
                    exif["aperture"] = f"f/{fnum:.1f}".replace(".0", "")
                shutter = _rat(named.get("ExposureTime"))
                if shutter is not None and not exif.get("shutter"):
                    exif["shutter"] = f"{shutter:.4f}s" if shutter < 1 else f"{shutter:.1f}s"
                focal = _rat(named.get("FocalLength"))
                if focal is not None and not exif.get("focal_length"):
                    exif["focal_length"] = f"{focal:.1f} mm".replace(".0 mm", " mm")
                dt_str = named.get("DateTimeOriginal") or named.get("DateTime")
                if dt_str and not exif.get("datetime_obj"):
                    try:
                        dt = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                        exif["datetime_utc"] = dt.replace(tzinfo=timezone.utc).isoformat()
                        exif["datetime_obj"] = dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
        except Exception as e:
            log.debug("PIL EXIF fallback fejlede for %s: %s", path.name, e)
    return exif


def _parse_datetime_from_filename(filename: str) -> Optional[datetime]:
    """Parser timestamp fra filnavn: YYYYMMDD_HHMMSS eller YYYY-MM-DD_HH-MM-SS."""
    patterns = [
        r"(\d{4})(\d{2})(\d{2})[_T](\d{2})(\d{2})(\d{2})",
        r"(\d{4})-(\d{2})-(\d{2})[_T](\d{2})-(\d{2})-(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            try:
                g = [int(x) for x in m.groups()]
                return datetime(g[0], g[1], g[2], g[3], g[4], g[5], tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _quality_check(path: Path) -> dict:
    result = {"flag": "ok", "passed": True, "blur_score": None, "brightness_mean": None}
    try:
        import cv2
        import numpy as np
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Kunne ikke læse billede")
        # Downscale
        h, w = img.shape
        if max(h, w) > 800:
            scale = 800 / max(h, w)
            img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
        # Blur: Laplacian variance (identisk med edge/capture/quality.py)
        lap = cv2.Laplacian(img, cv2.CV_64F)
        blur_score = float(lap.var())
        brightness = float(img.mean())
        result["blur_score"]      = round(blur_score, 1)
        result["brightness_mean"] = round(brightness, 1)
        BLUR_THRESHOLD   = 80.0
        DARK_THRESHOLD   = 25.0
        BRIGHT_THRESHOLD = 230.0
        if blur_score < BLUR_THRESHOLD:
            result["flag"] = "blurry";      result["passed"] = False
        elif brightness < DARK_THRESHOLD:
            result["flag"] = "underexposed"; result["passed"] = False
        elif brightness > BRIGHT_THRESHOLD:
            result["flag"] = "overexposed";  result["passed"] = False
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("Kvalitetstjek fejl: %s", e)
        result["flag"] = "error"
    return result

def _write_sidecar(
    image_path: Path,
    sha256: str,
    timestamp: datetime,
    exif: dict,
    original_filename: str,
    device_id: str,
    customer: str,
    site: str,
    camera_name: str,
    xmp_written: bool = False,
) -> Path:
    """Skriver sidecar JSON identisk med edge-format."""
    sidecar = {
        "timelapse_pro": {
            "version":      "2.2.0",
            "generated_at": now_utc().isoformat(),
            "source":       "import",
        },
        "integrity": {
            "sha256_original":     sha256,
            "captured_at_utc":     timestamp.isoformat(),
            "captured_at_local":   _to_local(timestamp),
            "timezone":            "Europe/Copenhagen",
            "image_file":          image_path.name,
            "original_unmodified": True,
            "xmp_written":         xmp_written,
            "xmp_note":            "XMP skrevet via exiftool" if xmp_written else "XMP ikke skrevet",
            "note":                "Importeret via TimeLapse Pro Import — SHA-256 af original fil",
        },
        "project": {
            "customer":     customer,
            "site":         site,
            "camera_name":  camera_name,
            "device_id":    device_id,
        },
        "location":        {},
        "camera": {
            "model":         exif.get("model", "Ukendt"),
            "iso":           exif.get("iso"),
            "aperture":      exif.get("aperture"),
            "shutter_speed": exif.get("shutter"),
            "focal_length":  exif.get("focal_length"),
        },
        "added_metadata": {
            "source":            "import",
            "original_filename": original_filename,
            "import_date":       now_utc().isoformat(),
            "fields_added":      [],
        },
    }

    sidecar_path = image_path.with_suffix(".json")
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False, default=str)
    return sidecar_path


def _write_xmp(image_path: Path, sha256: str, customer: str, site: str,
               camera_name: str, device_id: str) -> bool:
    """Skriver XMP metadata via exiftool. Returnerer True ved succes."""
    try:
        cmd = [
            "exiftool", "-overwrite_original",
            f"-XMP-xmpMM:OriginalDocumentID={sha256}",
            f"-XMP-dc:Source=TimeLapse Pro Import v2.2.0",
            f"-XMP-dc:Publisher={customer}",
            f"-XMP-dc:Title={site} — {camera_name}",
            f"-IPTC:By-line={customer}",
            f"-IPTC:CaptionAbstract=TimeLapse Pro Import | {customer} | {site}",
            str(image_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_dest_dir(sftp_base: Path, sftp_user: str, customer: str,
                  site: str, camera_name: str, timestamp: datetime) -> Path:
    """Bygger destinationssti: sftp_base/customer/site/camera/YYYY/MM/DD/.

    sftp_user bevares i API'et som adgangs-/site-attribut, men må ikke indgå i
    canonical datastien.
    """
    return (
        sftp_base
        / _sanitize(customer)
        / _sanitize(site)
        / _sanitize(camera_name)
        / timestamp.strftime("%Y")
        / timestamp.strftime("%m")
        / timestamp.strftime("%d")
    )


# ── Import worker ─────────────────────────────────────────────────────────────

def _run_import(
    job_id: str,
    image_files: list[Path],
    device_id: str,
    customer: str,
    site: str,
    camera_name: str,
    sftp_base: Path,
    sftp_user: str,
    db_url: str,
) -> None:
    """Kører i baggrunds-thread. Behandler alle billeder."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)

    cust_san   = _sanitize(customer)
    site_san   = _sanitize(site)
    camera_san = _sanitize(camera_name)

    def update(processed: int, errors: int, msg: str = ""):
        with _jobs_lock:
            _jobs[job_id]["processed"] = processed
            _jobs[job_id]["errors"]    = errors
            if msg:
                _jobs[job_id]["log"].append(msg)

    processed = 0
    errors    = 0

    for img_path in image_files:
        try:
            # 1. EXIF
            exif = _read_exif(img_path)

            # 2. Timestamp — EXIF → filnavn → nu
            timestamp = (
                exif.get("datetime_obj")
                or _parse_datetime_from_filename(img_path.name)
                or datetime.fromtimestamp(img_path.stat().st_mtime, tz=timezone.utc)
            )

            # 3. SHA-256 af original
            sha256 = _sha256(img_path)

            # 4. Nyt filnavn
            ts_str    = timestamp.strftime("%Y%m%d_%H%M%S")
            new_name  = f"{cust_san}_{site_san}_{camera_san}_{ts_str}.jpg"
            dest_dir  = _get_dest_dir(sftp_base, sftp_user, customer, site, camera_name, timestamp)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / new_name

            # Undgå duplikater
            if dest_path.exists():
                stem = dest_path.stem
                dest_path = dest_dir / f"{stem}_dup{uuid.uuid4().hex[:4]}.jpg"

            # 5. Kopiér
            shutil.copy2(str(img_path), str(dest_path))

            # 5b. Generér thumbnail med det samme (samme format/placering som
            #     galleriet forventer: .headend-thumbs/{navn}, 320×180 JPEG q78).
            #     Ellers skal galleriet generere alle on-demand ved kun 3 ad
            #     gangen → meget langsomt for store historiske imports.
            try:
                from main import _generate_edge_thumbnail, _generated_thumbs_dir_for
                _generate_edge_thumbnail(
                    dest_path, _generated_thumbs_dir_for(dest_path) / dest_path.name)
            except Exception as _te:
                log.debug("Import-thumbnail fejl for %s: %s", dest_path.name, _te)

            # 6. Kvalitetstjek
            quality = _quality_check(dest_path)

            # 7. Sidecar (uden XMP)
            _write_sidecar(
                dest_path, sha256, timestamp, exif,
                img_path.name, device_id, customer, site, camera_name,
                xmp_written=False
            )

            # 8. XMP
            xmp_ok = _write_xmp(dest_path, sha256, customer, site, camera_name, device_id)
            if xmp_ok:
                _write_sidecar(
                    dest_path, sha256, timestamp, exif,
                    img_path.name, device_id, customer, site, camera_name,
                    xmp_written=True
                )

            # 9. DB record
            db = SessionLocal()
            try:
                # Tjek om capture allerede eksisterer
                existing = db.query(Capture).filter_by(
                    device_id=device_id,
                    filename=new_name
                ).first()

                if not existing:
                    capture = Capture(
                        device_id       = device_id,
                        filename        = new_name,
                        captured_at     = timestamp,
                        filesize        = dest_path.stat().st_size,
                        sha256          = sha256,
                        quality_flag    = quality["flag"],
                        quality_passed  = quality["passed"],
                        blur_score      = quality["blur_score"],
                        brightness_mean = quality["brightness_mean"],
                        camera_model    = exif.get("model"),
                        exposure_time   = exif.get("shutter"),
                        iso             = int(exif["iso"]) if exif.get("iso") and str(exif.get("iso","")).isdigit() else None,
                        aperture        = exif.get("aperture"),
                        uploaded        = True,
                        xmp_written     = xmp_ok,
                    )
                    # camera_id/customer_id/site_id (2026-07-03, additivt) — se
                    # Claude_Kritisk_Statusgennemgang_2026-07-03.md §2.4/§2.5 (fase 4
                    # tilføjede site_id, 2026-07-03).
                    # Bulk-importerede devices er sjældent bundet til en logisk
                    # kamera-lokation, så camera_id/site_id forbliver ofte NULL her —
                    # customer_id dækker bredere via Device.customer_id.
                    try:
                        from main import _resolve_capture_camera_customer
                        cam_id, cust_id, site_id = _resolve_capture_camera_customer(db, device_id, timestamp)
                        capture.camera_id = cam_id
                        capture.customer_id = cust_id
                        capture.site_id = site_id
                    except Exception as _res_exc:
                        log.debug("Import camera/customer/site-resolution sprunget over: %s", _res_exc)
                    db.add(capture)
                    db.commit()
                    try:
                        from ai.integration import queue_capture_for_analysis
                        queue_capture_for_analysis(capture.id)
                    except Exception:
                        pass  # AI er valgfri — blokerer aldrig import
            finally:
                db.close()

            processed += 1
            if processed % 50 == 0 or processed == len(image_files):
                update(processed, errors, f"✅ {processed}/{len(image_files)} behandlet")

        except Exception as e:
            errors += 1
            log.warning("Import fejl for %s: %s", img_path.name, e)
            update(processed, errors, f"⚠️ Fejl: {img_path.name}: {e}")

    with _jobs_lock:
        _jobs[job_id]["status"]      = "done"
        _jobs[job_id]["finished_at"] = now_utc().isoformat()
        _jobs[job_id]["log"].append(
            f"🎉 Import færdig: {processed} billeder, {errors} fejl"
        )

    log.info("Import job %s færdig: %d/%d", job_id, processed, len(image_files))


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("/start")
async def start_import(
    request:      Request,
    customer_id:  str           = Form(...),
    site_id:      str           = Form(...),
    camera_name:  str           = Form(...),
    sftp_user:    str           = Form("sftp_nvj17c"),
    local_path:   Optional[str] = Form(None),
    zip_file:     Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Starter import job i baggrunden.

    Enten `local_path` (sti på Mac Mini) eller `zip_file` (upload fra browser).
    """
    # 2026-08-06 (Claude, Peter — fuld hierarki-gennemgang): routeren er kun
    # gated af `require_role("admin")` ved include_router() i main.py — det
    # dækker IKKE kunde-skoperede admin-brugere (role="admin" MED customer_id
    # sat, se _is_platform_admin()). Uden dette tjek kunne en kunde-admin for
    # Kunde A importere billeder ind under Kunde B's site, blot ved at sende
    # Kunde B's customer_id/site_id — samme sårbarhedsklasse som Peter fangede
    # på timelapse-generering tidligere i dag, blot skrive- i stedet for
    # læse-vejen. Deferred import for at undgå cirkulær import med main.py
    # (samme mønster som _sftp_base_path/_resolve_capture_camera_customer
    # nedenfor).
    from main import _ensure_customer_access, get_current_user
    current_user = get_current_user(request, db)
    _ensure_customer_access(current_user, customer_id)

    # Hent kunde og site
    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde ikke fundet")
    site = db.query(Site).filter_by(id=site_id, customer_id=customer_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site ikke fundet")

    # Byg device_id
    cust_slug   = _sanitize(customer.name)[:20]
    site_slug   = _sanitize(site.name)[:20]
    camera_slug = _sanitize(camera_name)[:20]
    device_id   = f"TL-IMPORT-{cust_slug}-{site_slug}-{camera_slug}"

    # Opret Device hvis ikke eksisterer
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        # Tæl eksisterende kameraer på site for camera_index
        existing_count = db.query(Device).filter(
            Device.site_id == site_id
        ).count()

        device = Device(
            device_id     = device_id,
            customer_id   = str(customer_id),   # SKAL sættes — ellers opløser AI-strategien
                                                # (site→kunde→global) til GLOBAL, så en
                                                # kunde-/site-specifik Ollama-strategi ikke
                                                # rammer importerede kameraer.
            customer_name = customer.name,
            site_name     = site.name,
            camera_name   = camera_name,
            site_id       = site_id,
            camera_index  = existing_count,
            status        = "import",
            first_seen    = now_utc(),
            last_seen     = now_utc(),
        )
        db.add(device)
        db.commit()
        log.info("Import device oprettet: %s", device_id)

    # 2026-08-06 (Claude, Peter — fuld hierarki-gennemgang): historisk manglede
    # importen en Camera-lokation + DeviceAssignment-binding for det virtuelle
    # import-device. Uden det forbliver capture.camera_id NULL for hver eneste
    # importeret billede (_resolve_capture_camera_customer() finder ingen aktiv
    # DeviceAssignment) — nøjagtig det gab der krævede en manuel backfill for
    # Kamera 1 (Nordre Villavej) tidligere i dag, se HANDOVER_LOG.md 2026-08-06.
    # Find-eller-opret begge dele her, så hvert importeret billede får camera_id
    # sat med det samme, uden at afhænge af en efterfølgende backfill-kørsel.
    camera = db.query(Camera).filter_by(site_id=site_id, camera_name=camera_name).first()
    if not camera:
        camera = Camera(
            id=str(uuid.uuid4()), site_id=site_id, customer_id=customer_id,
            camera_name=camera_name,
        )
        db.add(camera)
        db.commit()
        log.info("Import kamera-lokation oprettet: %s (%s)", camera_name, camera.id)

    active_assignment = (
        db.query(DeviceAssignment)
        .filter_by(device_id=device_id, camera_id=camera.id)
        .filter(DeviceAssignment.unassigned_at.is_(None))
        .first()
    )
    if not active_assignment:
        # Sat langt før enhver plausibel optagelse i en historisk import — modsat
        # "nu" (som ville gentage nøjagtig samme retroaktive-assigned_at-bug som
        # blev rettet for Kamera 1 i dag: assigned_at skal aldrig postdatere de
        # billeder den er ment at dække).
        db.add(DeviceAssignment(
            device_id=device_id, camera_id=camera.id,
            assigned_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
            assigned_by="import",
        ))
        db.commit()
        log.info("Import device-assignment oprettet: %s -> %s", device_id, camera.id)

    # Find billeder
    image_files: list[Path] = []
    tmp_dir = None

    if local_path:
        src = Path(local_path)
        # macOS TCC: mapper som ~/Downloads, ~/Desktop og ~/Documents er beskyttede.
        # Uden Full Disk Access kaster Path.exists() PermissionError (EPERM), som i
        # Python 3.12 gen-kastes (ikke "findes ikke") → ellers ubehandlet 500.
        try:
            exists = src.exists()
        except OSError as e:
            raise HTTPException(status_code=403, detail=(
                f"Ingen adgang til stien ({e.strerror or e}). macOS blokerer sandsynligvis "
                f"headend-processens adgang til en beskyttet mappe (Downloads/Skrivebord/"
                f"Dokumenter/eksternt volume). Giv headend-processen 'Fuld diskadgang' i "
                f"Systemindstillinger → Privatliv & Sikkerhed, eller flyt billederne til en "
                f"ikke-beskyttet placering, fx /Volumes/data-fast/import/ eller ~/projects/."))
        if not exists:
            raise HTTPException(status_code=400, detail=f"Sti ikke fundet: {local_path}")
        try:
            for root, _, files in os.walk(src, onerror=lambda err: (_ for _ in ()).throw(err)):
                for f in files:
                    if Path(f).suffix in SUPPORTED_EXTENSIONS:
                        image_files.append(Path(root) / f)
        except OSError as e:
            raise HTTPException(status_code=403, detail=(
                f"Kunne ikke læse mappen ({e.strerror or e}). Tjek at headend-processen har "
                f"'Fuld diskadgang', eller flyt billederne til fx /Volumes/data-fast/import/."))

    elif zip_file:
        tmp_dir = tempfile.mkdtemp(prefix="timelapse_import_")
        zip_path = Path(tmp_dir) / "upload.zip"
        content = await zip_file.read()
        zip_path.write_bytes(content)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                if Path(f).suffix in SUPPORTED_EXTENSIONS:
                    image_files.append(Path(root) / f)
    else:
        raise HTTPException(status_code=400, detail="Angiv enten local_path eller zip_file")

    if not image_files:
        raise HTTPException(status_code=400, detail="Ingen JPG-billeder fundet")

    image_files.sort()

    # Hent canonical billed-rod. main.py's gamle globale `SFTP_BASE` blev fjernet ved
    # refaktorering til `_sftp_base_path(db)` (DB-setting vinder, env som fallback);
    # den gamle `from main import SFTP_BASE` gav ImportError → 500 uanset billedsti.
    from main import _sftp_base_path
    sftp_base = _sftp_base_path(db)

    # Opret job
    job_id = str(uuid.uuid4())[:8]
    with _jobs_lock:
        _jobs[job_id] = {
            "status":      "running",
            "total":       len(image_files),
            "processed":   0,
            "errors":      0,
            "log":         [f"🚀 Starter import af {len(image_files)} billeder..."],
            "started_at":  now_utc().isoformat(),
            "finished_at": None,
            "device_id":   device_id,
            "customer":    customer.name,
            "customer_id": customer_id,
            "site":        site.name,
            "camera_name": camera_name,
        }

    # Start baggrunds-thread
    from sqlalchemy import create_engine
    import os as _os
    db_url = _os.environ.get("DATABASE_URL", "sqlite:///timelapse_headend.db")

    thread = threading.Thread(
        target=_run_import,
        args=(
            job_id, image_files, device_id,
            customer.name, site.name, camera_name,
            sftp_base, sftp_user, db_url,
        ),
        daemon=True,
    )
    thread.start()

    log.info("Import job %s startet: %d billeder, device=%s", job_id, len(image_files), device_id)

    return {
        "job_id":    job_id,
        "total":     len(image_files),
        "device_id": device_id,
        "status":    "running",
    }


@router.get("/status/{job_id}")
def get_import_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    """Hent status for import job — polles af UI."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    # 2026-08-06 (Claude, Peter — fuld hierarki-gennemgang): se begrundelse i
    # start_import() ovenfor — samme kunde-skopering skal håndhæves når status
    # slås op, ellers kan en kunde-admin gætte/observere et andet kunde-jobs
    # 8-tegns job_id og se dets fremdrift/kunde-/site-/kameranavn.
    from main import _ensure_customer_access, get_current_user
    current_user = get_current_user(request, db)
    _ensure_customer_access(current_user, job.get("customer_id"))
    pct = round(job["processed"] / job["total"] * 100) if job["total"] else 0
    # job_id SKAL med — UI'et poller /status/{activeJob.job_id}, og _jobs-dicten
    # indeholder ikke selv job_id. Uden dette bliver activeJob.job_id undefined
    # efter første poll → /status/undefined (404) → progress-baren fryser.
    return {**job, "job_id": job_id, "pct": pct}


@router.get("/jobs")
def list_import_jobs(request: Request, db: Session = Depends(get_db)):
    """Liste alle import jobs (seneste først), skoperet til brugerens kunde."""
    # 2026-08-06 (Claude, Peter — fuld hierarki-gennemgang): uden dette tjek
    # returnerede endpointet ALLE kunders import-jobs (kundenavn, site, kamera)
    # til enhver admin-bruger, uanset kunde-skopering — samme klasse tenant-leak
    # som start_import()/get_import_status() ovenfor.
    from main import _is_platform_admin, get_current_user
    current_user = get_current_user(request, db)
    with _jobs_lock:
        jobs = list(_jobs.items())
    if not _is_platform_admin(current_user):
        user_customer_id = getattr(current_user, "customer_id", None)
        jobs = [(jid, j) for jid, j in jobs if j.get("customer_id") == user_customer_id]
    return [
        {"job_id": jid, **{k: v for k, v in j.items() if k != "log"}}
        for jid, j in reversed(jobs)
    ]
