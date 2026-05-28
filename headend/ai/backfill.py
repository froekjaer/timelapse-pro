#!/usr/bin/env python3
"""
TimeLapse Pro — AI Backfill
Brug:
  python headend/ai/backfill.py --limit 10
  python headend/ai/backfill.py --limit 10 --strategy cloud_only
  python headend/ai/backfill.py --limit 100 --site Travbyen --random
  python headend/ai/backfill.py --date 2026-04-15
  python headend/ai/backfill.py --all --customer Kirkbi_A_S
  python headend/ai/backfill.py --all --dry-run
"""
from __future__ import annotations
import argparse, os, re, sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADEND   = REPO_ROOT / "headend"
sys.path.insert(0, str(HEADEND))
sys.path.insert(0, str(HEADEND / "ai"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://peter@localhost/timelapse_db")
SFTP_BASE    = Path(os.getenv("SFTP_BASE", "/Volumes/data/timelapse-incoming"))
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")
os.environ["DATABASE_URL"] = DATABASE_URL

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

from repositories    import TagRepository, AnalysisRepository
from ai_strategy     import AIConfigManager, AIConfig, VALID_STRATEGIES, GLOBAL_DEFAULTS as GD
from settings_helper import get_setting


def find_image(filename):
    p = Path(filename)
    if p.is_absolute() and p.exists(): return p
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
        for pat in [f"*/data/*/*/{yyyy}/{mm}/{dd}/{p.name}",
                    f"*/*/{yyyy}/{mm}/{dd}/{p.name}",
                    f"*/*/*/{yyyy}/{mm}/{dd}/{p.name}",
                    f"*/*/*/*/{yyyy}/{mm}/{dd}/{p.name}"]:
            hits = list(SFTP_BASE.glob(pat))
            if hits: return hits[0]
    if os.getenv("TIMELAPSE_BACKFILL_ALLOW_DEEP_SCAN", "").lower() in ("1", "true", "yes"):
        hits = list(SFTP_BASE.rglob(p.name))
        return hits[0] if hits else None
    return None


def get_captures(db, args):
    where = "WHERE (c.ai_result IS NULL OR c.ai_tags IS NULL)" if not args.force else "WHERE TRUE"
    q = f"""
        SELECT c.id, c.filename, c.device_id, c.captured_at,
               cust.name AS customer_name, cust.id AS customer_id,
               s.name AS site_name
        FROM captures c
        LEFT JOIN devices d      ON d.device_id  = c.device_id
        LEFT JOIN sites s        ON s.id          = d.site_id
        LEFT JOIN customers cust ON cust.id        = s.customer_id
        {where}
    """
    p = {}
    if args.date:
        q += " AND DATE(c.captured_at) = :dt"; p["dt"] = args.date
    if args.customer:
        q += " AND (cust.name ILIKE :c OR cust.id ILIKE :c)"; p["c"] = f"%{args.customer}%"
    if args.site:
        q += " AND s.name ILIKE :s"; p["s"] = f"%{args.site}%"

    if args.random:
        q += " ORDER BY RANDOM()"
    else:
        q += " ORDER BY c.captured_at DESC"

    if args.limit:
        q += f" LIMIT {args.limit}"

    try:
        return [dict(r) for r in db.execute(text(q), p).mappings().all()]
    except Exception:
        # Fallback uden sites/customers join
        q2 = "SELECT c.id, c.filename, c.device_id, c.captured_at, NULL::text AS customer_name, NULL::text AS customer_id, NULL::text AS site_name FROM captures c"
        if not args.force:
            q2 += " WHERE (c.ai_result IS NULL OR c.ai_tags IS NULL)"
        else:
            q2 += " WHERE TRUE"
        if args.date: q2 += " AND DATE(c.captured_at)=:dt"
        q2 += " ORDER BY RANDOM()" if args.random else " ORDER BY c.captured_at DESC"
        if args.limit: q2 += f" LIMIT {args.limit}"
        return [dict(r) for r in db.execute(text(q2), p).mappings().all()]


def run_analysis(img, config, vocab_by_cat, approved_set, local_svc, cloud_svc):
    limit = config.tag_vocabulary_limit or 80
    vocab = {}; count = 0
    for cat, tags in vocab_by_cat.items():
        if count >= limit: break
        take = tags[:max(3, limit - count)]
        vocab[cat] = take; count += len(take)

    if config.strategy == "cloud_only":
        return cloud_svc.analyse(img, vocab, approved_set), config.cloud_model

    if config.strategy == "local_only":
        return local_svc.analyse(img, vocab, approved_set), config.local_model

    if config.strategy == "local_then_cloud":
        result = local_svc.analyse(img, vocab, approved_set)
        esc, reasons = config.should_escalate(
            confidence=0.75, new_tags=result.new_tags, tags=result.approved_tags,
            change_detected=result.change_detected, quality_ok=result.quality_ok,
        )
        if esc and cloud_svc:
            r2 = cloud_svc.analyse(img, vocab, approved_set)
            return r2, f"{config.cloud_model}(esc)"
        return result, config.local_model

    from ollama_service import ImageAnalysisResult
    return ImageAnalysisResult(
        scene_dk="Teknisk QA kun", approved_tags=[], new_tags=[],
        change_detected=False, change_summary=None, change_tags=[],
        quality_flag="ukendt", quality_ok=True, has_gdpr_data=False,
        gdpr_detections=[], model="technical_only", duration_ms=0, raw_response={},
    ), "technical_only"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",    type=int,                default=None)
    parser.add_argument("--all",      action="store_true")
    parser.add_argument("--force",    action="store_true")
    parser.add_argument("--date",     type=date.fromisoformat, default=None)
    parser.add_argument("--customer", type=str,                default=None)
    parser.add_argument("--site",     type=str,                default=None, help="Filtrer på site-navn, fx 'Travbyen'")
    parser.add_argument("--random",   action="store_true",     help="Vælg tilfældige billeder fremfor nyeste")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--strategy", type=str,                default=None, choices=list(VALID_STRATEGIES))
    parser.add_argument("--model",    type=str,                default=None)
    args = parser.parse_args()
    if not args.all and not args.limit and not args.date:
        args.limit = 10

    print(f"\n{'='*60}\n  TimeLapse Pro — AI Backfill\n{'='*60}")
    print(f"  Database:  {DATABASE_URL}")
    print(f"  SFTP base: {SFTP_BASE}")
    if args.site:     print(f"  Site:      {args.site}")
    if args.random:   print(f"  Udvælgelse: tilfældig")
    if args.strategy: print(f"  Strategi:  {args.strategy} (override)")
    print()

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1 FROM ai_analyses LIMIT 1"))
    except Exception:
        print("  ❌ ai_analyses mangler — kør fix_schema.sh"); sys.exit(1)

    # Hent API-nøgle fra DB hvis ikke sat i env
    gemini_key = os.getenv("GEMINI_API_KEY", "") or get_setting(db, "gemini_api_key")
    gemini_sa_path = (
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        or get_setting(db, "gemini_service_account_path")
    )
    gemini_project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT", "")
        or get_setting(db, "gemini_project_id")
    )
    gemini_location = (
        os.getenv("GOOGLE_CLOUD_LOCATION", "")
        or get_setting(db, "gemini_location", "europe-west1")
    )
    ollama_url = os.getenv("OLLAMA_URL", "") or get_setting(db, "ollama_url", OLLAMA_URL)

    captures = get_captures(db, args)
    if not captures:
        print("  ✅ Ingen billeder at analysere"); db.close(); return

    total_in_db = db.execute(text(
        "SELECT COUNT(*) FROM captures c WHERE c.ai_result IS NULL OR c.ai_tags IS NULL"
    )).scalar()
    print(f"── {len(captures)} captures til analyse (af {total_in_db} uanalyserede i alt) ──\n")

    if args.dry_run:
        cfg_cache = {}
        for i, c in enumerate(captures[:20], 1):
            img = find_image(c["filename"])
            cid = c.get("customer_id")
            if cid not in cfg_cache:
                cfg_cache[cid] = AIConfigManager(db).get_config(cid).strategy
            site = c.get("site_name") or ""
            print(f"  [{i:3}] {Path(c['filename']).name[:42]:<42} {'✅' if img else '❌'} [{cfg_cache[cid]}] {site}")
        if len(captures) > 20: print(f"  ... og {len(captures)-20} mere")
        db.close(); return

    # Init services
    local_svc = cloud_svc = None
    strategy_hint = args.strategy or ""

    if strategy_hint not in ("cloud_only",):
        try:
            from ollama_service import OllamaVisionService
            model = args.model or get_setting(db, "local_model", "qwen2.5vl:7b")
            svc = OllamaVisionService(base_url=ollama_url, vision_model=model)
            if svc.health_check():
                local_svc = svc
                print(f"  ✅ Lokal model: {model}")
            else:
                print(f"  ⚠️  Lokal model ikke klar: {model}")
        except Exception as e:
            print(f"  ⚠️  Lokal model: {e}")

    if strategy_hint not in ("local_only", "technical_only"):
        if gemini_sa_path or gemini_key:
            try:
                from gemini_service import GeminiVisionService
                cloud_model = get_setting(db, "gemini_model", "gemini-2.5-flash")
                cloud_svc = GeminiVisionService(
                    service_account_path=gemini_sa_path,
                    project_id=gemini_project_id,
                    location=gemini_location,
                    api_key=gemini_key,
                    model=cloud_model,
                )
                provider = f"Vertex AI ({gemini_location})" if gemini_sa_path else "AI Studio"
                print(f"  Gemini provider: {provider}")
                print(f"  ✅ Gemini: {cloud_model}")
            except Exception as e:
                print(f"  ⚠️  Gemini: {e}")
        else:
            print("  ⚠️  Ingen Gemini API-nøgle — gem den i UI under Indstillinger → AI")
    print()

    tag_repo      = TagRepository(db)
    analysis_repo = AnalysisRepository(db)
    vocab_by_cat  = tag_repo.get_approved_by_category()
    approved_set  = set(tag_repo.get_approved_tags())

    if not approved_set:
        print("  ⚠️  Tomt vokabular — seeder...")
        from tag_vocabulary import TagVocabulary
        def _g():
            yield db
        TagVocabulary(_g)
        vocab_by_cat = tag_repo.get_approved_by_category()
        approved_set = set(tag_repo.get_approved_tags())

    print(f"  📚 {sum(len(v) for v in vocab_by_cat.values())} tags i vokabular\n")

    cfg_mgr  = AIConfigManager(db)
    last_cid = "___"
    cur_cfg  = None
    stats    = dict(ok=0, fejl=0, mangler=0, sky=0, lokal=0, ms=0)

    for i, cap in enumerate(captures, 1):
        name = Path(cap["filename"]).name
        cid  = cap.get("customer_id")
        site = cap.get("site_name") or ""

        if cid != last_cid:
            if args.strategy:
                cur_cfg = AIConfig(
                    strategy=args.strategy, local_model=args.model or GD["local_model"],
                    cloud_model=GD["cloud_model"],
                    escalation_threshold=GD["escalation_threshold"],
                    escalation_new_tags=GD["escalation_new_tags"],
                    always_escalate_tags=GD["always_escalate_tags"],
                    always_cloud_tags=GD["always_cloud_tags"],
                    tag_vocabulary_limit=GD["tag_vocabulary_limit"],
                    enabled=True, source="cli",
                )
            else:
                cur_cfg = cfg_mgr.get_config(cid)
            last_cid = cid
            cname = cap.get("customer_name") or cid or "ukendt"
            print(f"  📋 {cname} / {site}: {cur_cfg.strategy} (fra {cur_cfg.source})")

        if not cur_cfg.enabled: continue

        print(f"  [{i:3}/{len(captures)}] {name[:48]}", end="", flush=True)
        img = find_image(cap["filename"])
        if not img:
            print(f"\r  [{i:3}/{len(captures)}] {name[:48]} ❌ ikke fundet")
            stats["mangler"] += 1; continue

        try:
            result, model_used = run_analysis(img, cur_cfg, vocab_by_cat, approved_set, local_svc, cloud_svc)
            aid = analysis_repo.save_analysis(
                capture_id=cap["id"], location_id=None, model_vision=model_used,
                scene_dk=result.scene_dk, change_detected=result.change_detected,
                change_summary=result.change_summary, ai_quality_flag=result.quality_flag,
                ai_quality_ok=result.quality_ok, reference_capture_id=None,
                raw_response=result.raw_response if isinstance(result.raw_response, dict) else {},
                has_gdpr_data=result.has_gdpr_data, duration_ms=result.duration_ms,
            )
            tag_repo.upsert_capture_tags(
                capture_id=cap["id"], analysis_id=aid,
                approved_tags=result.approved_tags + result.change_tags,
                new_tags=result.new_tags,
            )
            payload = {
                "scene_dk": result.scene_dk,
                "approved_tags": result.approved_tags,
                "new_tags": result.new_tags,
                "change_detected": result.change_detected,
                "change_summary": result.change_summary,
                "change_tags": result.change_tags,
                "quality_flag": result.quality_flag,
                "quality_ok": result.quality_ok,
                "has_gdpr_data": result.has_gdpr_data,
                "gdpr_detections": [
                    {
                        "type": item.detection_type,
                        "detail": item.detail,
                        "bbox": item.bounding_box,
                    }
                    for item in result.gdpr_detections
                ],
                "model": model_used,
                "duration_ms": result.duration_ms,
                "raw_response": result.raw_response,
            }
            tags = result.approved_tags + result.new_tags + result.change_tags
            db.execute(text("""
                UPDATE captures
                SET ai_result = :ai_result,
                    ai_tags = :ai_tags,
                    ai_analyzed_at = :ai_analyzed_at
                WHERE id = :capture_id
            """), {
                "capture_id": cap["id"],
                "ai_result": json.dumps(payload, ensure_ascii=False),
                "ai_tags": json.dumps(list(dict.fromkeys(tags)), ensure_ascii=False),
                "ai_analyzed_at": datetime.now(timezone.utc),
            })
            db.commit()
            is_cloud = any(x in model_used for x in ["gemini","gpt","claude"])
            stats["sky" if is_cloud else "lokal"] += 1
            flags = ("☁️ " if is_cloud else "") + (f"+{len(result.new_tags)}ny " if result.new_tags else "")
            print(f"\r  [{i:3}/{len(captures)}] {name[:44]:<44} ✅ {len(result.approved_tags):2}tags {result.duration_ms:4}ms {flags}")
            stats["ok"] += 1; stats["ms"] += result.duration_ms
        except KeyboardInterrupt:
            print("\n\n  ⏸️  Afbrudt"); break
        except Exception as e:
            print(f"\r  [{i:3}/{len(captures)}] {name[:44]:<44} ❌ {e}")
            stats["fejl"] += 1
            try: db.rollback()
            except: pass

    db.close()
    print(f"\n{'─'*60}")
    print(f"  ✅ OK:      {stats['ok']}")
    if stats["sky"]:   print(f"  ☁️  Cloud:   {stats['sky']}")
    if stats["lokal"]: print(f"  🖥️  Lokal:   {stats['lokal']}")
    print(f"  ❌ Fejl:    {stats['fejl']}")
    print(f"  📂 Mangler: {stats['mangler']}")
    if stats["ok"]: print(f"  ⏱️  Gns/bil: {stats['ms']//stats['ok']}ms")
    print()

if __name__ == "__main__":
    main()
