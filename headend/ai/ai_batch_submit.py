#!/usr/bin/env python3
"""
TimeLapse Pro — Bulk AI re-tag via Gemini Batch API (auto-chunked)
==================================================================
Tager ALLE (eller filtrerede) billeder, deler dem i bidder, og indsender hver bid
som sit eget Gemini batch-job (~50% af normal pris). Headendens eksisterende
batch-poller (kører i headend-processen, hvert 5. min) finaliserer jobbene og
skriver tags tilbage på captures — dette script SKAL bare indsende.

Kører fra kommandolinjen (frisk proces → ingen nginx-timeout, ingen UI-blokering).
JSONL streames til disk pr. bid (lavt RAM-forbrug).

Brug:
  python headend/ai/ai_batch_submit.py --all --force --chunk-size 2000
  python headend/ai/ai_batch_submit.py --site Travbyen --force
  python headend/ai/ai_batch_submit.py --all --force --no-context   # hurtigere
  python headend/ai/ai_batch_submit.py --all --dry-run              # vis kun planen
"""
from __future__ import annotations
import argparse, json, os, re, sys, uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADEND   = REPO_ROOT / "headend"
sys.path.insert(0, str(HEADEND))
sys.path.insert(0, str(HEADEND / "ai"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://peter@localhost/timelapse_db")
SFTP_BASE    = Path(os.getenv("SFTP_BASE", "/Volumes/data"))
os.environ["DATABASE_URL"] = DATABASE_URL

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from settings_helper import get_setting
from repositories    import TagRepository
from capture_context import build_capture_context, format_context_block
from gemini_service  import GeminiVisionService, validate_batch_bucket_region
from database        import AiBatchJob

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def find_image(filename: str):
    p = Path(filename)
    if p.is_absolute() and p.exists():
        return p
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        y, mo, d = m.groups()
        for pat in (f"*/*/*/{y}/{mo}/{d}/{p.name}",
                    f"timelapse-incoming/*/data/*/*/*/{y}/{mo}/{d}/{p.name}",
                    f"*/*/{y}/{mo}/{d}/{p.name}",
                    f"*/*/*/*/{y}/{mo}/{d}/{p.name}"):
            hits = list(SFTP_BASE.glob(pat))
            if hits:
                return hits[0]
    if os.getenv("TIMELAPSE_BACKFILL_ALLOW_DEEP_SCAN", "").lower() in ("1", "true", "yes"):
        hits = list(SFTP_BASE.rglob(p.name))
        return hits[0] if hits else None
    return None


def select_captures(db, args):
    where = "WHERE c.filename IS NOT NULL"
    if not args.force:
        where += " AND (c.ai_result IS NULL OR c.ai_tags IS NULL)"
    q = f"""
        SELECT c.id, c.filename, c.device_id, c.captured_at,
               cust.name AS customer_name, s.name AS site_name
        FROM captures c
        LEFT JOIN devices d      ON d.device_id = c.device_id
        LEFT JOIN sites s        ON s.id = d.site_id
        LEFT JOIN customers cust ON cust.id = s.customer_id
        {where}
    """
    p = {}
    if args.device:
        q += " AND c.device_id = :dev"; p["dev"] = args.device
    if args.site:
        q += " AND s.name ILIKE :s"; p["s"] = f"%{args.site}%"
    if args.customer:
        q += " AND (cust.name ILIKE :c OR cust.id ILIKE :c)"; p["c"] = f"%{args.customer}%"
    if getattr(args, "since", None):
        q += " AND c.captured_at >= :since"; p["since"] = args.since
    if getattr(args, "until", None):
        q += " AND c.captured_at <= :until"; p["until"] = args.until
    q += " ORDER BY c.captured_at DESC, c.id DESC"
    # Stabil orden (captured_at DESC, id DESC) → --skip springer deterministisk de
    # første N billeder over, så man kan fortsætte hvor en testbid slap.
    if args.limit:
        q += f" LIMIT {args.limit}"
    if getattr(args, "skip", 0):
        q += f" OFFSET {int(args.skip)}"
    return [dict(r) for r in db.execute(text(q), p).mappings().all()]


def _setting(db, key: str, default: str = "") -> str:
    """Læs en indstilling robust på tværs af de TO settings-tabeller der findes i
    kodebasen: headenden/UI skriver til `settings` (via main._get_setting), mens
    `settings_helper` bruger `system_settings`. Prøv begge (settings først)."""
    for tbl in ("settings", "system_settings"):
        try:
            row = db.execute(text(f"SELECT value FROM {tbl} WHERE key = :k"), {"k": key}).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
    return default


def build_gemini(db, model_override=None):
    key  = os.getenv("GEMINI_API_KEY", "") or _setting(db, "gemini_api_key")
    sa   = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "") or _setting(db, "gemini_service_account_path")
    proj = os.getenv("GOOGLE_CLOUD_PROJECT", "") or _setting(db, "gemini_project_id")
    loc  = os.getenv("GOOGLE_CLOUD_LOCATION", "") or _setting(db, "gemini_location", "europe-west1")
    model = model_override or _setting(db, "gemini_model", "gemini-2.5-flash")
    if not key and not sa:
        return None, None, ""
    svc = GeminiVisionService(service_account_path=sa, project_id=proj, location=loc, api_key=key, model=model)
    gcs_bucket = ""
    if getattr(svc, "is_vertex", False):
        gcs_bucket = (_setting(db, "gemini_gcs_bucket", "") or "").strip()
        # GDPR-guard (samme som API-stien i headend/main.py — se
        # gemini_service.validate_batch_bucket_region() for begrundelse). Denne CLI
        # havde IKKE dette tjek før 2026-07-05 (Claude, periodisk tjek), selvom den
        # udfører præcis samme Vertex-batch-upload som API-endepunktet.
        bucket_region = (_setting(db, "gemini_gcs_bucket_region", "") or "").strip()
        validate_batch_bucket_region(svc.location, bucket_region)  # rejser ValueError ved mismatch
    return svc, model, gcs_bucket


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Alle billeder (ellers kun de uanalyserede)")
    ap.add_argument("--force", action="store_true", help="Re-tag også allerede taggede billeder")
    ap.add_argument("--limit", type=int, default=None, help="Maks antal billeder i alt")
    ap.add_argument("--skip", type=int, default=0, help="Spring de første N billeder over (fx --skip 2000 efter en testbid)")
    ap.add_argument("--chunk-size", type=int, default=2000, help="Billeder pr. batch-job (default 2000)")
    ap.add_argument("--site", type=str, default=None)
    ap.add_argument("--customer", type=str, default=None)
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument("--since", type=str, default=None,
                    help="Kun captures fra og med denne dato/tid (fx 2026-06-29 eller '2026-06-29 12:00')")
    ap.add_argument("--until", type=str, default=None,
                    help="Kun captures til og med denne dato/tid")
    ap.add_argument("--no-context", action="store_true", help="Spring kontekst/baseline over (hurtigere)")
    ap.add_argument("--model", type=str, default=None, help="Gemini-model override")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.all and not args.limit and not args.site and not args.customer and not args.device:
        args.force = args.force  # ingen filtre = kun uanalyserede medmindre --all/--force

    db = Session()

    # Resolv billed-roden robust: brug SFTP_BASE-env hvis sat, ellers `sftp_base`
    # fra DB-settings (så man ikke skal huske at sætte env — det var derfor
    # find_image fandt 0 filer under default /Volumes/data).
    global SFTP_BASE
    if not os.getenv("SFTP_BASE"):
        _base = _setting(db, "sftp_base", "").strip()
        if _base:
            SFTP_BASE = Path(_base)

    print(f"\n{'='*64}\n  Bulk AI re-tag via Gemini Batch (auto-chunked)\n{'='*64}")
    print(f"  DB: {DATABASE_URL}\n  SFTP: {SFTP_BASE}\n  Chunk: {args.chunk_size}  Force: {args.force}  Kontekst: {not args.no_context}\n")

    try:
        svc, model, gcs_bucket = build_gemini(db, args.model)
    except ValueError as exc:
        print(f"  ❌ {exc}"); db.close(); return
    if not svc:
        print("  ❌ Ingen Gemini-credentials (Indstillinger → AI)."); db.close(); return
    if getattr(svc, "is_vertex", False) and not gcs_bucket:
        print("  ❌ Vertex AI kræver et GCS-bucket — sæt 'gemini_gcs_bucket' i Indstillinger → AI."); db.close(); return
    print(f"  Gemini: {model} ({'Vertex/'+svc.location+' bucket='+gcs_bucket if getattr(svc,'is_vertex',False) else 'AI Studio'})")

    caps = select_captures(db, args)
    total = len(caps)
    if not total:
        print("  ✅ Ingen billeder matcher kriterierne."); db.close(); return
    chunks = [caps[i:i + args.chunk_size] for i in range(0, total, args.chunk_size)]
    print(f"  {total} billeder → {len(chunks)} batch-job(s) à op til {args.chunk_size}\n")

    vocab_by_cat = TagRepository(db).get_approved_by_category()
    submitted = 0; missing_total = 0
    for ci, chunk in enumerate(chunks, 1):
        items = []; ctx_by_key = {}; dev_cache = {}; missing = 0
        for cap in chunk:
            img = find_image(cap["filename"])
            if not img:
                missing += 1; continue
            key = f"cap-{cap['id']}"
            items.append((key, img))
            if not args.no_context:
                try:
                    dev = dev_cache.get(cap["device_id"])
                    if dev is None:
                        dev = SimpleNamespace(device_id=cap["device_id"], customer_name=cap.get("customer_name"),
                                              site_name=cap.get("site_name"), camera_name=None)
                        dev_cache[cap["device_id"]] = dev
                    cap_obj = SimpleNamespace(device_id=cap["device_id"], captured_at=cap.get("captured_at"), perspective=None)
                    ctx_by_key[key] = format_context_block(build_capture_context(db, cap_obj, dev))
                except Exception:
                    ctx_by_key[key] = ""
        missing_total += missing
        if not items:
            print(f"  [bid {ci}/{len(chunks)}] 0 billeder på disk ({missing} manglede) — sprunget over")
            continue
        if args.dry_run:
            print(f"  [bid {ci}/{len(chunks)}] {len(items)} billeder ({missing} manglede)  (dry-run, intet indsendt)")
            continue
        job_id = str(_uuid.uuid4())
        try:
            job_name = svc.submit_batch_job(
                items=items, vocabulary_by_cat=vocab_by_cat,
                display_name=f"bulk-{ci:03d}-{job_id[:6]}",
                gcs_bucket=gcs_bucket, context_by_key=ctx_by_key,
            )
        except Exception as exc:
            print(f"  [bid {ci}/{len(chunks)}] ❌ indsendelse fejlede: {exc}")
            continue
        db.add(AiBatchJob(
            id=job_id, gemini_job_name=job_name, status="submitted",
            capture_ids=json.dumps([c["id"] for c in chunk]),
            cloud_model=model, total_count=len(items),
            requested_by="cli", notify_on_complete=False,
            submitted_at=datetime.now(timezone.utc),
        ))
        db.commit()
        submitted += 1
        print(f"  [bid {ci}/{len(chunks)}] ✅ indsendt: {job_name}  ({len(items)} billeder, {missing} manglede)")

    db.close()
    print(f"\n{'─'*60}")
    print(f"  Batch-jobs indsendt: {submitted}/{len(chunks)}   (manglende filer: {missing_total})")
    if submitted:
        print("  Headendens poller (hvert 5. min) henter resultater hjem og skriver tags tilbage.")
        print("  Følg dem i UI'et under Post-processing → Gemini batch-jobs.")
    print()


if __name__ == "__main__":
    main()
