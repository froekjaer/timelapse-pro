#!/usr/bin/env python3
"""
TimeLapse Pro — AI Tag Backfill
================================
Kører objekt-genkendelse på alle eksisterende billeder og gemmer
tags i ai_tags-kolonnen (JSON-array) i PostgreSQL.

Tags bruges til søgning: #kran, #bil, #røg, #person osv.

Brug:
  python ai/backfill_tags.py                          # Alle billeder uden tags
  python ai/backfill_tags.py --device-id TL-xxx       # Kun én enhed
  python ai/backfill_tags.py --limit 100              # Test med 100 billeder
  python ai/backfill_tags.py --rerun                  # Genanalyser alle (inkl. eksisterende)
  python ai/backfill_tags.py --dry-run                # Se hvad der ville ske

Krav:
  DATABASE_URL og SFTP_BASE som environment-variabler.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./timelapse_headend.db")
SFTP_BASE    = Path(os.getenv("SFTP_BASE", "/Users/Shared/timelapse/incoming"))

GREEN  = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"
CYAN   = "\033[96m"; BOLD   = "\033[1m";  RESET = "\033[0m"

MIN_FILE_BYTES = 50_000


def get_sftp_base(session) -> Path:
    try:
        result = session.execute(text("SELECT value FROM settings WHERE key='sftp_base'")).fetchone()
        if result:
            return Path(result[0])
    except Exception:
        pass
    return SFTP_BASE


def find_image(sftp_base: Path, device_id: str, filename: str) -> Path | None:
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
        matches = list(sftp_base.glob(f"*/data/*/*/{yyyy}/{mm}/{dd}/{filename}"))
        if matches:
            return matches[0]
    flat = sftp_base / device_id / filename
    if flat.exists():
        return flat
    return None


def run_migration(engine) -> None:
    """Tilføj ai_tags-kolonne hvis den ikke findes."""
    # Kolonne allerede tilføjet via psql
    print(f"  · ai_tags kolonne klar")


def update_sidecar_tags(image_path: Path, tags: list[str]) -> None:
    """Tilføj tags til eksisterende sidecar JSON."""
    sidecar = image_path.with_suffix(".json")
    if not sidecar.exists():
        return
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if "ai_analysis" in data:
            data["ai_analysis"]["tags"] = tags
        else:
            data["ai_tags"] = tags
        sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        pass  # Sidecar-fejl er ikke kritisk


def main():
    parser = argparse.ArgumentParser(description="TimeLapse Pro AI Tag Backfill")
    parser.add_argument("--device-id",  help="Kun denne device")
    parser.add_argument("--limit",      type=int, default=0, help="Max antal (0=alle)")
    parser.add_argument("--rerun",      action="store_true", help="Genanalyser alle, inkl. eksisterende tags")
    parser.add_argument("--dry-run",    action="store_true", help="Vis uden at køre")
    parser.add_argument("--batch-size", type=int, default=10, help="Pause-interval")
    args = parser.parse_args()

    print(f"\n{BOLD}TimeLapse Pro — AI Tag Backfill{RESET}")
    print(f"Database: {DATABASE_URL}")
    print(f"Tilstand: {'dry-run' if args.dry_run else 'rerun alle' if args.rerun else 'kun nye'}\n")

    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}
                           if DATABASE_URL.startswith("sqlite") else {})
    Session = sessionmaker(bind=engine)
    db = Session()

    # Migration
    print(f"{BOLD}── DB Migration ──{RESET}")
    run_migration(engine)

    sftp_base = get_sftp_base(db)
    print(f"\nSFTP base: {sftp_base}")

    # Hent captures
    from database import Capture
    query = db.query(Capture)
    if not args.rerun:
        query = query.filter(Capture.ai_tags.is_(None))
    if args.device_id:
        query = query.filter_by(device_id=args.device_id)
    # Prioritér billeder med eksisterende ai_result (quality allerede analyseret)
    query = query.order_by(Capture.ai_result.desc(), Capture.id.desc())
    if args.limit:
        query = query.limit(args.limit)

    captures = query.all()
    total = len(captures)

    print(f"\n{BOLD}── {total} billeder til tag-analyse ──{RESET}\n")

    if total == 0:
        print(f"{GREEN}✓ Alle billeder har allerede tags{RESET}")
        return

    if args.dry_run:
        print(f"{YELLOW}Dry-run — viser de første 10:{RESET}")
        for c in captures[:10]:
            path = find_image(sftp_base, c.device_id, c.filename)
            print(f"  [{c.id}] {c.filename[:60]}  {'✓' if path else '✗ mangler'}")
        if total > 10:
            print(f"  ... og {total - 10} flere")
        return

    # Ollama check
    from ai.ollama_service import get_ollama_service
    svc = get_ollama_service()
    if not svc.is_available():
        print(f"{RED}✗ Ollama ikke tilgængelig{RESET}")
        sys.exit(1)
    print(f"{GREEN}✓ Ollama klar — bruger {svc._model} med ORIGINALBILLEDER{RESET}\n")

    ok = skipped = errors = 0
    all_tags: dict[str, int] = {}
    t_start = time.monotonic()

    for i, capture in enumerate(captures, 1):
        image_path = find_image(sftp_base, capture.device_id, capture.filename)

        if not image_path:
            print(f"  [{i}/{total}] {YELLOW}↷ Fil ikke fundet:{RESET} {capture.filename[:50]}")
            skipped += 1
            continue

        if image_path.stat().st_size < MIN_FILE_BYTES:
            skipped += 1
            continue

        print(f"  [{i}/{total}] {capture.filename[:55]}", end="", flush=True)

        result = svc.extract_tags(image_path)

        if result.error:
            print(f"  {RED}✗ {result.error[:40]}{RESET}")
            errors += 1
            continue

        # Gem i DB
        capture.ai_tags = json.dumps(result.tags, ensure_ascii=False)
        db.commit()

        # Opdater sidecar
        update_sidecar_tags(image_path, result.tags)

        # Tæl tags til statistik
        for t in result.tags:
            all_tags[t] = all_tags.get(t, 0) + 1

        tag_str = " ".join(f"#{t}" for t in result.tags[:5])
        if len(result.tags) > 5:
            tag_str += f" +{len(result.tags)-5}"
        print(f"  {CYAN}{tag_str}{RESET}  {result.latency_ms}ms")
        ok += 1

        if i % args.batch_size == 0:
            elapsed = time.monotonic() - t_start
            rate    = i / elapsed
            eta_min = int((total - i) / rate / 60) if rate > 0 else 0
            print(f"\n  {BOLD}── {i}/{total} — ETA ~{eta_min} min ──{RESET}\n")

    # ── Opsummering ───────────────────────────────────────────────────────────
    elapsed = time.monotonic() - t_start
    print(f"\n{BOLD}{'═' * 55}")
    print(f"  TAG BACKFILL FÆRDIG — {total} billeder")
    print(f"{'═' * 55}{RESET}")
    print(f"  {GREEN}✓ Taggede:       {ok}{RESET}")
    print(f"  {YELLOW}↷ Sprunget over: {skipped}{RESET}")
    if errors:
        print(f"  {RED}✗ Fejl:          {errors}{RESET}")
    print(f"  Tid:             {int(elapsed/60)} min {int(elapsed%60)} sek")

    if all_tags:
        print(f"\n{BOLD}  Top 20 tags:{RESET}")
        for tag, count in sorted(all_tags.items(), key=lambda x: -x[1])[:20]:
            pct = count / ok * 100
            bar = "█" * int(pct / 3)
            print(f"  #{tag:<25} {bar:<20} {count:4d} ({pct:.0f}%)")


if __name__ == "__main__":
    main()
