#!/usr/bin/env python3
"""Audit and migrate TimeLapse Pro capture storage layout.

Canonical layout:
  <storage_root>/<customer>/<site>/<camera>/<YYYY>/<MM>/<DD>/<filename>

The tool is conservative:
  - dry-run by default
  - writes a JSONL manifest
  - moves image, JSON sidecar, Edge thumbnail and Headend fallback thumbnail together
  - never deletes empty legacy directories
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Capture, Customer, Device, SessionLocal, Site  # noqa: E402


DATE_RE = re.compile(r"_(20\d{2})(\d{2})(\d{2})_\d{6}\.\w+$")


def safe(value: str | None, fallback: str = "unknown") -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[^A-Za-z0-9æøåÆØÅ_-]+", "_", text).strip("_")
    return text or fallback


def split_filename(filename: str) -> tuple[str | None, str | None, str | None]:
    stem = Path(filename).stem
    parts = stem.split("_")
    date_idx = next((idx for idx, part in enumerate(parts) if re.fullmatch(r"20\d{6}", part)), -1)
    if date_idx <= 0:
        return None, None, None
    prefix = parts[:date_idx]
    if len(prefix) >= 3:
        return prefix[0], "_".join(prefix[1:-2]) or None, "_".join(prefix[-2:]) or None
    return None, None, None


def capture_date_parts(capture: Capture) -> tuple[str, str, str]:
    if capture.captured_at:
        return capture.captured_at.strftime("%Y"), capture.captured_at.strftime("%m"), capture.captured_at.strftime("%d")
    match = DATE_RE.search(capture.filename or "")
    if match:
        return match.group(1), match.group(2), match.group(3)
    now = datetime.utcnow()
    return now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".arw", ".cr2", ".nef"}


def build_file_index(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    ignored_parts = {"_backups", ".thumbs", ".headend-thumbs"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ignored_parts.intersection(path.parts):
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        index[path.name].append(path)
    return index


def find_image(root: Path, capture: Capture, file_index: dict[str, list[Path]]) -> Path | None:
    filename = capture.filename or ""
    yyyy, mm, dd = capture_date_parts(capture)
    patterns = [
        root / capture.device_id / yyyy / mm / dd / filename,
        root / capture.device_id / filename,
    ]
    for path in patterns:
        if path.exists():
            return path
    matches = file_index.get(filename, [])
    return matches[0] if matches else None


def target_for(root: Path, capture: Capture, device: Device | None, site: Site | None, customer: Customer | None) -> Path:
    file_customer, file_site, file_camera = split_filename(capture.filename or "")
    customer_name = customer.name if customer else (device.customer_name if device else None) or file_customer
    site_name = site.name if site else (device.site_name if device else None) or file_site
    camera_name = (device.camera_name if device else None) or file_camera or capture.device_id
    yyyy, mm, dd = capture_date_parts(capture)
    return (
        root
        / safe(customer_name)
        / safe(site_name)
        / safe(camera_name)
        / yyyy
        / mm
        / dd
        / (capture.filename or "")
    )


def move_one(src: Path, dst: Path, apply: bool) -> dict:
    result = {"src": str(src), "dst": str(dst), "status": "planned"}
    if src == dst:
        result["status"] = "already_canonical"
        return result
    if dst.exists():
        result["status"] = "target_exists"
        return result
    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        result["status"] = "moved"
    return result


def companion_moves(src: Path, dst: Path, apply: bool) -> list[dict]:
    moves = [move_one(src, dst, apply)]
    sidecar = src.with_suffix(".json")
    if sidecar.exists():
        moves.append(move_one(sidecar, dst.with_suffix(".json"), apply))
    for thumb_dir in (".thumbs", ".headend-thumbs"):
        thumb = src.parent / thumb_dir / src.name
        if thumb.exists():
            moves.append(move_one(thumb, dst.parent / thumb_dir / dst.name, apply))
    return moves


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.getenv("SFTP_BASE", "/Volumes/data"))
    parser.add_argument("--manifest", default="/private/tmp/timelapse-storage-migration.jsonl")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--device-id", help="Only migrate captures for this device id")
    parser.add_argument("--filename-contains", help="Only migrate captures where filename contains this text")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"SFTP root findes ikke: {root}")
    file_index = build_file_index(root)
    db = SessionLocal()
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    processed = 0
    try:
        query = db.query(Capture).order_by(Capture.captured_at.asc().nullslast(), Capture.id.asc())
        if args.device_id:
            query = query.filter(Capture.device_id == args.device_id)
        if args.filename_contains:
            query = query.filter(Capture.filename.contains(args.filename_contains))
        if args.limit:
            query = query.limit(args.limit)
        with manifest.open("w", encoding="utf-8") as fh:
            for capture in query:
                processed += 1
                device = db.query(Device).filter_by(device_id=capture.device_id).first()
                site = db.query(Site).filter_by(id=device.site_id).first() if device and device.site_id else None
                customer_id = site.customer_id if site else (device.customer_id if device else None)
                customer = db.query(Customer).filter_by(id=customer_id).first() if customer_id else None
                src = find_image(root, capture, file_index)
                if not src:
                    record = {"capture_id": capture.id, "filename": capture.filename, "status": "missing_source"}
                    counts["missing_source"] = counts.get("missing_source", 0) + 1
                else:
                    dst = target_for(root, capture, device, site, customer)
                    moves = companion_moves(src, dst, args.apply)
                    status = moves[0]["status"]
                    counts[status] = counts.get(status, 0) + 1
                    record = {"capture_id": capture.id, "device_id": capture.device_id, "moves": moves, "status": status}
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        db.close()
    print(json.dumps({
        "processed": processed,
        "apply": args.apply,
        "indexed_files": sum(len(v) for v in file_index.values()),
        "counts": counts,
        "manifest": str(manifest),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
