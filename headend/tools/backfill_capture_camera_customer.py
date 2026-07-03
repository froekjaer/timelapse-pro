#!/usr/bin/env python3
"""
TimeLapse Pro — Backfill af captures.camera_id / captures.customer_id

Baggrund: Capture var hidtil kun nøglet på device_id (fysisk Edge). Det betød
at billedhistorik ikke fulgte en logisk kamera-lokation ved Edge-udskiftning,
og at tenant-isolation for billeddata udelukkende hvilede på applikations-joins
mod device_id (se Claude_Kritisk_Statusgennemgang_2026-07-03.md §2.4/§2.5).

DB-migration v12 (headend/main.py, startup) tilføjer de to nye, nullable
kolonner. Nye captures får dem sat automatisk ved skrivning
(main._resolve_capture_camera_customer, kaldt fra _upsert_capture_record og
fra importer.py). Dette script backfilder EKSISTERENDE rækker.

Kilder:
  - customer_id: primært Device.customer_id (bred dækning — sat for alle
    devices, inkl. bulk-importerede, uanset kamera-lokations-binding).
  - camera_id:   den DeviceAssignment, der var aktiv på capture-tidspunktet
    (assigned_at <= captured_at < unassigned_at). Devices, der aldrig er
    bundet til en kamera-lokation, forbliver bevidst NULL her — IKKE gættet.

Sikkerhed: default er --dry-run (ingen DB-skrivning). Kør med --apply for
faktisk at skrive. Idempotent — kan køres igen uden effekt på allerede
udfyldte rækker (med mindre --force er angivet).
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import or_  # noqa: E402

from database import Camera, Capture, Device, DeviceAssignment, SessionLocal  # noqa: E402


def _resolve(db, device_id: str, captured_at, assignments_by_device: dict, devices_by_id: dict):
    """Samme logik som main._resolve_capture_camera_customer, men batch-venlig
    (undgår én DB-forespørgsel pr. capture ved at forudindlæse devices +
    assignments én gang og slå op i hukommelsen i stedet)."""
    camera_id = None
    customer_id = None
    device = devices_by_id.get(device_id)
    if device and device.customer_id:
        customer_id = device.customer_id
    for assignment in assignments_by_device.get(device_id, []):
        if assignment.assigned_at is None or captured_at is None:
            continue
        if assignment.assigned_at <= captured_at and (
            assignment.unassigned_at is None or assignment.unassigned_at > captured_at
        ):
            camera_id = assignment.camera_id
            break
    return camera_id, customer_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill captures.camera_id / captures.customer_id fra Device/DeviceAssignment"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Skriv faktisk til DB. Uden dette flag: kun dry-run/rapport.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Genberegn og overskriv også rækker, der allerede har camera_id/customer_id sat.",
    )
    parser.add_argument(
        "--device-id", default=None,
        help="Begræns til ét device_id (til test/verifikation før fuld kørsel).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maks antal rækker at behandle (til test).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        devices_by_id = {d.device_id: d for d in db.query(Device).all()}
        assignments_by_device: dict[str, list] = {}
        for a in db.query(DeviceAssignment).order_by(DeviceAssignment.assigned_at.desc()).all():
            assignments_by_device.setdefault(a.device_id, []).append(a)
        camera_customer_by_id = {c.id: c.customer_id for c in db.query(Camera).all()}

        q = db.query(Capture)
        if not args.force:
            q = q.filter(or_(Capture.camera_id.is_(None), Capture.customer_id.is_(None)))
        if args.device_id:
            q = q.filter(Capture.device_id == args.device_id)
        if args.limit:
            q = q.limit(args.limit)

        total = 0
        updated = 0
        camera_found = 0
        customer_found = 0
        unresolved_devices: Counter = Counter()

        for capture in q.all():
            total += 1
            camera_id, customer_id = _resolve(
                db, capture.device_id, capture.captured_at, assignments_by_device, devices_by_id
            )
            # Camera.customer_id vinder over Device.customer_id, hvis kamera-binding findes
            # (matcher main._resolve_capture_camera_customer).
            if camera_id and camera_customer_by_id.get(camera_id):
                customer_id = camera_customer_by_id[camera_id]

            if camera_id:
                camera_found += 1
            if customer_id:
                customer_found += 1
            if not camera_id and not customer_id:
                unresolved_devices[capture.device_id] += 1

            changed = False
            if args.force or not capture.camera_id:
                if capture.camera_id != camera_id:
                    capture.camera_id = camera_id
                    changed = True
            if args.force or not capture.customer_id:
                if capture.customer_id != customer_id:
                    capture.customer_id = customer_id
                    changed = True
            if changed:
                updated += 1
                if args.apply:
                    db.add(capture)

        print(f"Captures behandlet:        {total}")
        print(f"  camera_id resolvet:      {camera_found}")
        print(f"  customer_id resolvet:    {customer_found}")
        print(f"  ville blive opdateret:   {updated}")
        if unresolved_devices:
            print("Devices uden nogen resolution (hverken camera_id eller customer_id):")
            for device_id, count in unresolved_devices.most_common(20):
                print(f"  {device_id}: {count} captures")

        if args.apply:
            db.commit()
            print(f"APPLY: {updated} rækker skrevet til DB.")
        else:
            db.rollback()
            print("DRY-RUN: ingen DB-skrivning. Kør igen med --apply for at gemme.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
