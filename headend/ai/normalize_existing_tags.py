#!/usr/bin/env python3
"""
TimeLapse Pro — Engangs-normalisering af EKSISTERENDE tags
==========================================================
Anvender normalize_tag() (synonym-konsolidering + danske leaks → engelsk) på de
tags der allerede ligger på captures — UDEN at kalde Gemini. Rydder historikken
så søgning bliver ensartet (city_view i stedet for 10 varianter, danish_flag i
stedet for dannebrog osv.).

Sikkerhed:
  - DRY-RUN er default. Skriver intet før du tilføjer --apply.
  - Idempotent: anden kørsel er en no-op.
  - Rører kun ai_tags + tag-lister inde i ai_result. Ikke billeder, ikke scene-tekst.

Brug:
  python headend/ai/normalize_existing_tags.py                 # dry-run, alle
  python headend/ai/normalize_existing_tags.py --site Travbyen # dry-run, ét site
  python headend/ai/normalize_existing_tags.py --apply         # SKRIV ændringerne
  python headend/ai/normalize_existing_tags.py --apply --limit 100
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADEND   = REPO_ROOT / "headend"
sys.path.insert(0, str(HEADEND))
sys.path.insert(0, str(HEADEND / "ai"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://peter@localhost/timelapse_db")
os.environ["DATABASE_URL"] = DATABASE_URL

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tag_vocabulary import normalize_tag

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Tag-lister inde i ai_result-JSON der skal normaliseres med.
RESULT_LIST_KEYS = ("tags", "approved_tags", "new_tags", "change_tags")


def normalize_list(tags) -> list[str]:
    """Normalisér + dedupliker en tag-liste, bevar rækkefølge."""
    out = []
    for t in tags or []:
        nt = normalize_tag(t)
        if nt:
            out.append(nt)
    return list(dict.fromkeys(out))


def normalize_result(obj: dict) -> bool:
    """Normalisér tag-lister + new_tags_da-nøgler inde i ai_result. True hvis ændret."""
    changed = False
    for key in RESULT_LIST_KEYS:
        if isinstance(obj.get(key), list):
            nv = normalize_list(obj[key])
            if nv != list(obj[key]):
                obj[key] = nv
                changed = True
    nd = obj.get("new_tags_da")
    if isinstance(nd, dict):
        newd: dict[str, str] = {}
        for k, v in nd.items():
            nk = normalize_tag(k) or k
            newd.setdefault(nk, v)
        if newd != nd:
            obj["new_tags_da"] = newd
            changed = True
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Skriv ændringerne (ellers dry-run)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--site", type=str, default=None)
    ap.add_argument("--customer", type=str, default=None)
    args = ap.parse_args()

    mode = "APPLY (skriver)" if args.apply else "DRY-RUN (skriver intet)"
    print(f"\n{'='*60}\n  Normalisering af eksisterende tags — {mode}\n{'='*60}")
    print(f"  Database: {DATABASE_URL}\n")

    q = """
        SELECT c.id, c.ai_tags, c.ai_result
        FROM captures c
        LEFT JOIN devices d      ON d.device_id = c.device_id
        LEFT JOIN sites s        ON s.id = d.site_id
        LEFT JOIN customers cust ON cust.id = s.customer_id
        WHERE c.ai_tags IS NOT NULL
    """
    p = {}
    if args.site:
        q += " AND s.name ILIKE :s"; p["s"] = f"%{args.site}%"
    if args.customer:
        q += " AND (cust.name ILIKE :c OR cust.id ILIKE :c)"; p["c"] = f"%{args.customer}%"
    q += " ORDER BY c.id"
    if args.limit:
        q += f" LIMIT {args.limit}"

    db = SessionLocal()
    scanned = changed = 0
    collapses: Counter = Counter()   # (old -> new) hvor old != new
    try:
        rows = db.execute(text(q), p).mappings().all()
        print(f"── {len(rows)} captures med tags ──\n")
        for r in rows:
            scanned += 1
            try:
                old_tags = json.loads(r["ai_tags"]) if r["ai_tags"] else []
            except Exception:
                continue
            new_tags = normalize_list(old_tags)

            # tæl hvilke konkrete tags der ændrede sig
            for t in old_tags:
                nt = normalize_tag(t)
                if nt and nt != str(t).lower().strip().replace(" ", "_").replace("-", "_"):
                    collapses[f"{t} → {nt}"] += 1

            result_obj = None
            res_changed = False
            if r["ai_result"]:
                try:
                    result_obj = json.loads(r["ai_result"])
                    if isinstance(result_obj, dict):
                        res_changed = normalize_result(result_obj)
                except Exception:
                    result_obj = None

            if new_tags != old_tags or res_changed:
                changed += 1
                if args.apply:
                    params = {"id": r["id"], "t": json.dumps(new_tags, ensure_ascii=False)}
                    sql = "UPDATE captures SET ai_tags = :t"
                    if res_changed and result_obj is not None:
                        sql += ", ai_result = :r"
                        params["r"] = json.dumps(result_obj, ensure_ascii=False)
                    sql += " WHERE id = :id"
                    db.execute(text(sql), params)
        if args.apply:
            db.commit()
    finally:
        db.close()

    print(f"  Scannet:  {scanned}")
    print(f"  Ændrede:  {changed}  ({'skrevet' if args.apply else 'ville blive ændret'})")
    print(f"\n  Hyppigste konsolideringer:")
    for k, n in collapses.most_common(25):
        print(f"    {n:5}×  {k}")
    if not args.apply:
        print(f"\n  → Dette var DRY-RUN. Kør igen med --apply for at skrive ændringerne.")
    print()


if __name__ == "__main__":
    main()
