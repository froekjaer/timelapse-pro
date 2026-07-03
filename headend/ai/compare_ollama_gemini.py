#!/usr/bin/env python3
"""
Side-om-side: Ollama (lokal) vs Gemini (cloud) på SAMME billeder.
================================================================
READ-ONLY — skriver IKKE til captures. Kører begge modeller på et udsnit af
billeder pr. site (spredt over perioden), med samme vokabular + kontekst/baseline,
og gemmer en sammenligning (JSON + markdown) du kan kigge i.

Brug:
  SFTP_BASE=$(psql -U timelapse timelapse_db -tA -c \
    "SELECT COALESCE((SELECT value FROM settings WHERE key='sftp_base'),'/Volumes/data')") \
  ~/.venvs/timelapse-headend/bin/python headend/ai/compare_ollama_gemini.py \
    --sites "Nordre Villavej 17c,Travbyen" --per-site 5 \
    --out ~/Claude/Projects/Timelaps/compare_ollama_vs_gemini
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
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
from repositories     import TagRepository
from settings_helper  import get_setting
from ai_strategy      import GLOBAL_DEFAULTS as GD
from capture_context  import build_capture_context, format_context_block
from ollama_service   import OllamaVisionService, VISION_MODEL
from gemini_service   import GeminiVisionService

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

_PRIORITY = ("anomalies_and_events", "camera_quality", "change_detection", "vehicles",
             "workers_and_activity", "weather", "light_and_time", "site_condition")


def limited_vocab(vocab_by_cat, limit=45):
    out, used = {}, 0
    for cat in _PRIORITY:
        if vocab_by_cat.get(cat):
            out[cat] = list(vocab_by_cat[cat]); used += len(out[cat])
    for cat, tags in vocab_by_cat.items():
        if cat in out or used >= limit:
            continue
        take = tags[:max(3, limit - used)]
        if take:
            out[cat] = take; used += len(take)
    return out


def find_image(filename):
    p = Path(filename)
    if p.is_absolute() and p.exists():
        return p
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if m:
        y, mo, d = m.groups()
        for pat in (f"*/*/*/{y}/{mo}/{d}/{p.name}", f"timelapse-incoming/*/data/*/*/*/{y}/{mo}/{d}/{p.name}",
                    f"*/*/{y}/{mo}/{d}/{p.name}", f"*/*/*/*/{y}/{mo}/{d}/{p.name}"):
            hits = list(SFTP_BASE.glob(pat))
            if hits:
                return hits[0]
    if os.getenv("TIMELAPSE_BACKFILL_ALLOW_DEEP_SCAN", "").lower() in ("1", "true", "yes"):
        hits = list(SFTP_BASE.rglob(p.name))
        return hits[0] if hits else None
    return None


def pick_for_site(db, site, n):
    rows = db.execute(text("""
        SELECT c.id, c.filename, c.device_id, c.captured_at, s.name AS site_name,
               cust.name AS customer_name
        FROM captures c
        LEFT JOIN devices d   ON d.device_id = c.device_id
        LEFT JOIN sites s     ON s.id = d.site_id
        LEFT JOIN customers cust ON cust.id = s.customer_id
        WHERE c.filename IS NOT NULL AND s.name ILIKE :s
        ORDER BY c.captured_at ASC
    """), {"s": f"%{site}%"}).mappings().all()
    rows = list(rows)
    if len(rows) <= n:
        return rows
    step = len(rows) / float(n)
    return [rows[int(i * step)] for i in range(n)]


def build_gemini(db):
    key = os.getenv("GEMINI_API_KEY", "") or get_setting(db, "gemini_api_key")
    sa  = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "") or get_setting(db, "gemini_service_account_path")
    proj = os.getenv("GOOGLE_CLOUD_PROJECT", "") or get_setting(db, "gemini_project_id")
    loc  = os.getenv("GOOGLE_CLOUD_LOCATION", "") or get_setting(db, "gemini_location", "europe-west1")
    model = get_setting(db, "gemini_model", "gemini-2.5-flash")
    if not key and not sa:
        return None, None
    return GeminiVisionService(service_account_path=sa, project_id=proj, location=loc, api_key=key, model=model), model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", type=str, default="Nordre Villavej 17c,Travbyen")
    ap.add_argument("--per-site", type=int, default=5)
    ap.add_argument("--out", type=str, default="compare_ollama_vs_gemini")
    ap.add_argument("--local-model", dest="local_model", type=str, default=None,
                    help="Override Ollama-model, fx qwen3-vl:8b (ingen fallback → ren måling)")
    args = ap.parse_args()

    print(f"\n{'='*64}\n  Ollama vs Gemini — side om side\n{'='*64}\n  DB: {DATABASE_URL}\n  SFTP: {SFTP_BASE}\n")

    db = Session()
    tag_repo = TagRepository(db)
    vocab_full = tag_repo.get_approved_by_category()
    approved   = set(tag_repo.get_approved_tags())
    vocab_local = limited_vocab(vocab_full)

    local_model = args.local_model or get_setting(db, "local_model", VISION_MODEL)
    # Ved eksplicit --local-model: ingen fallback, så vi måler netop DEN model rent.
    ollama = OllamaVisionService(vision_model=local_model,
                                 fallback_models=[] if args.local_model else None)
    ollama_ok = ollama.health_check()
    gemini, gmodel = build_gemini(db)
    print(f"  Lokal:  {local_model}  ({'klar' if ollama_ok else 'IKKE tilgængelig'})")
    print(f"  Cloud:  {gmodel or 'ingen credentials'}\n")
    if not ollama_ok or not gemini:
        print("  ⚠️  Begge modeller kræves for sammenligning. Tjek Ollama / Gemini-credentials.")
        db.close(); return

    results = []
    for site in [s.strip() for s in args.sites.split(",") if s.strip()]:
        caps = pick_for_site(db, site, args.per_site)
        print(f"── {site}: {len(caps)} billeder ──")
        for cap in caps:
            img = find_image(cap["filename"])
            name = Path(cap["filename"]).name
            if not img:
                print(f"   {name}  ❌ ikke fundet"); continue
            shim_cap = SimpleNamespace(device_id=cap["device_id"], captured_at=cap["captured_at"], perspective=None)
            shim_dev = SimpleNamespace(device_id=cap["device_id"], customer_name=cap.get("customer_name"),
                                       site_name=cap.get("site_name"), camera_name=None)
            ctx = format_context_block(build_capture_context(db, shim_cap, shim_dev))

            t0 = time.monotonic()
            try:
                o = ollama.analyse(img, vocab_local, approved, context_block=ctx)
                o_tags = list(dict.fromkeys(o.approved_tags + o.new_tags)); o_ms = int((time.monotonic()-t0)*1000); o_err = None
            except Exception as e:
                o_tags, o_ms, o_err, o = [], 0, str(e), None
            t1 = time.monotonic()
            try:
                g = gemini.analyse(img, vocab_full, approved, context_block=ctx)
                g_tags = list(dict.fromkeys(g.approved_tags + g.new_tags)); g_ms = int((time.monotonic()-t1)*1000); g_err = None
            except Exception as e:
                g_tags, g_ms, g_err, g = [], 0, str(e), None

            shared = sorted(set(o_tags) & set(g_tags))
            results.append({
                "site": site, "filename": name, "captured_at": str(cap["captured_at"]),
                "ollama": {"model": local_model, "ms": o_ms, "n": len(o_tags), "tags": o_tags,
                           "scene": getattr(o, "scene_dk", None), "error": o_err},
                "gemini": {"model": gmodel, "ms": g_ms, "n": len(g_tags), "tags": g_tags,
                           "scene": getattr(g, "scene_dk", None), "error": g_err},
                "shared": shared, "n_shared": len(shared),
            })
            print(f"   {name}")
            print(f"      Ollama ({len(o_tags):2}, {o_ms:5}ms): {', '.join(o_tags) or o_err}")
            print(f"      Gemini ({len(g_tags):2}, {g_ms:5}ms): {', '.join(g_tags) or g_err}")
            print(f"      Fælles: {len(shared)}\n")
    db.close()

    # Skriv JSON + markdown
    out = args.out
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Path(out + ".json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Ollama vs Gemini — sammenligning\n"]
    for r in results:
        md.append(f"## {r['site']} — {r['filename']}")
        md.append(f"- **Ollama** ({r['ollama']['model']}, {r['ollama']['n']} tags, {r['ollama']['ms']}ms): {', '.join(r['ollama']['tags'])}")
        md.append(f"- **Gemini** ({r['gemini']['model']}, {r['gemini']['n']} tags, {r['gemini']['ms']}ms): {', '.join(r['gemini']['tags'])}")
        md.append(f"- Fælles: {r['n_shared']}")
        if r['ollama']['scene']: md.append(f"- Ollama-scene: {r['ollama']['scene']}")
        if r['gemini']['scene']: md.append(f"- Gemini-scene: {r['gemini']['scene']}")
        md.append("")
    Path(out + ".md").write_text("\n".join(md), encoding="utf-8")

    if results:
        avg = lambda k1, k2: sum(r[k1][k2] for r in results) / len(results)
        print(f"{'─'*60}")
        print(f"  Billeder: {len(results)}")
        print(f"  Gns tags  — Ollama: {avg('ollama','n'):.1f} | Gemini: {avg('gemini','n'):.1f}")
        print(f"  Gns tid   — Ollama: {avg('ollama','ms'):.0f}ms | Gemini: {avg('gemini','ms'):.0f}ms")
        print(f"  → {out}.json  +  {out}.md\n")


if __name__ == "__main__":
    main()
