#!/usr/bin/env python3
"""
TimeLapse Pro — backfill danske tag-labels (display_name_da)
============================================================
Fylder `ai_tag_vocabulary.display_name_da` fra `PREDEFINED_DA_LABELS` (via
`normalize_tag`) for tags der mangler et dansk visningsnavn — så UI'et (Tag
søgning, AI Styring, result-kort) viser DANSKE labels i stedet for at falde
tilbage til de rå engelske tag-nøgler.

Endpointet `/api/ai/vocabulary/translations` returnerer kun tags MED et
`display_name_da`; derfor så alt engelsk ud når kolonnen var tom for de nye tags
fra bulk-re-taggen. Dette script lukker hullet for de ~386 predefinerede tags.

  - DRY-RUN er default. Skriver intet før du tilføjer --apply.
  - Idempotent: kun rækker med tom display_name_da røres.
  - Tags uden en predefineret dansk oversættelse listes til sidst (kan oversættes
    manuelt i Tag Review eller via en senere AI-oversættelses-pass).

Brug:
  ~/.venvs/timelapse-headend/bin/python headend/ai/backfill_tag_translations.py           # dry-run
  ~/.venvs/timelapse-headend/bin/python headend/ai/backfill_tag_translations.py --apply    # gem
"""
from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "headend"))
sys.path.insert(0, str(REPO / "headend" / "ai"))
os.environ.setdefault("DATABASE_URL", "postgresql://peter@localhost/timelapse_db")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tag_vocabulary import PREDEFINED_DA_LABELS, normalize_tag

engine = create_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine)


def danish_for(tag: str) -> str | None:
    """Predefineret dansk label for et tag (direkte eller via kanonisk form)."""
    return PREDEFINED_DA_LABELS.get(tag) or PREDEFINED_DA_LABELS.get(normalize_tag(tag))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Skriv ændringerne (ellers dry-run)")
    ap.add_argument("--ai", action="store_true",
                    help="Oversæt også de tags UDEN predefineret dansk via den lokale tekst-model "
                         "(gemmes med translation_source='ai' — kan rettes i Tag Review)")
    args = ap.parse_args()

    db = Session()
    mode = "APPLY (gemmer)" if args.apply else "DRY-RUN"
    print(f"\n{'='*60}\n  Backfill danske tag-labels — {mode}\n{'='*60}")

    rows = db.execute(text("""
        SELECT id, tag FROM ai_tag_vocabulary
        WHERE display_name_da IS NULL OR display_name_da = ''
        ORDER BY tag
    """)).fetchall()
    print(f"  {len(rows)} tags uden dansk label\n")

    def store(rid: int, da: str, source: str) -> None:
        db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET display_name_da = :da, translation_source = :src,
                translation_status = 'auto', translation_updated_at = :ts
            WHERE id = :id
        """), {"da": da, "src": source, "ts": datetime.now(timezone.utc), "id": rid})

    # 1) Predefineret dansk (hurtigt, kurateret)
    filled = 0
    missing: list[tuple[int, str]] = []
    for rid, tag in rows:
        da = danish_for(tag)
        if not da:
            missing.append((rid, tag))
            continue
        filled += 1
        if args.apply:
            store(rid, da, "predefined")
    if args.apply:
        db.commit()
    print(f"  {'✅ gemt' if args.apply else 'ville fylde'} (predefineret): {filled}")
    print(f"  Uden predefineret dansk: {len(missing)}")

    # 2) AI-oversættelse af resten (lokal tekst-model) — kan rettes i Tag Review
    ai_filled = 0
    if args.ai and missing:
        translations = ai_translate([t for _rid, t in missing])
        for rid, tag in missing:
            da = translations.get(tag)
            if da:
                ai_filled += 1
                if args.apply:
                    store(rid, da, "ai")
        if args.apply:
            db.commit()
        print(f"  {'✅ gemt' if args.apply else 'ville fylde'} (AI): {ai_filled}")
        still = len(missing) - ai_filled
        if still:
            print(f"  Stadig uden dansk (AI kunne ikke oversætte): {still}")
    elif missing:
        print("  (kør med --ai for at oversætte resten via den lokale tekst-model)")

    print()
    db.close()
    return 0


def ai_translate(tags: list[str]) -> dict[str, str]:
    """Oversæt engelske tags til korte danske labels via den lokale Ollama-tekstmodel.
    Batches for at holde prompten kort. Returnerer {engelsk_tag: dansk}."""
    from text_services import _OllamaTextBase
    svc = _OllamaTextBase()
    system = ("Du oversætter korte engelske billed-/byggeplads-tags til KORTE danske labels "
              "(1-3 ord, små bogstaver, ingen forklaring). Returnér KUN et JSON-objekt "
              "{\"engelsk_tag\": \"dansk\"} med præcis de tags du får.")
    out: dict[str, str] = {}
    BATCH = 40
    total_batches = (len(tags) + BATCH - 1) // BATCH
    for i in range(0, len(tags), BATCH):
        batch = tags[i:i + BATCH]
        prompt = "Oversæt disse tags til dansk:\n" + "\n".join(batch)
        try:
            data = svc._parse_json(svc._call(prompt, system=system))
        except Exception as exc:
            print(f"     ⚠️ AI-bid {i // BATCH + 1}/{total_batches} fejlede: {exc}")
            continue
        batch_set = set(batch)
        for k, v in (data or {}).items():
            kk = str(k).strip().lower().replace(" ", "_").replace("-", "_")
            if kk in batch_set and isinstance(v, str) and v.strip():
                out[kk] = v.strip()
        print(f"     AI-bid {i // BATCH + 1}/{total_batches}: {len(batch)} tags → {len([k for k in batch if k in out])} oversat")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
