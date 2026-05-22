#!/usr/bin/env python3
"""
TimeLapse Pro — AI Billedanalyse Testscript
============================================
Tester Ollama mod eksisterende billeder. Understøtter:
  - Thumbnail-præference (hurtigere analyse)
  - Sammenligning: thumbnail vs. original
  - Bulk thumbnail-generering (til Kirkbi og andre sites uden thumbs)

Brug:
  # Standard test — bruger thumbnails (genererer dem hvis de mangler)
  python ai/test_ai_images.py --dir /Volumes/data/timelapse-incoming --sample 20

  # Sammenlign thumbnail vs. original (validering)
  python ai/test_ai_images.py --dir /Volumes/data/... --sample 10 --compare

  # Generer thumbnails til Kirkbi uden at analysere
  python ai/test_ai_images.py --dir /Volumes/data/.../Kirkbi --generate-thumbs-only

  # Kun billeder der fejlede OpenCV
  python ai/test_ai_images.py --dir /Volumes/data/... --sample 30 --only-flagged

  # Gem rapport
  python ai/test_ai_images.py --dir /Volumes/data/... --sample 50 --report rapport.json

Krav:
  pip install requests pillow
  ollama pull llava-phi3
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ai.ollama_service import OllamaService, DEFAULT_MODEL, generate_thumbnail, find_thumbnail
except ImportError:
    from ollama_service import OllamaService, DEFAULT_MODEL, generate_thumbnail, find_thumbnail

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ── Ollama-tjek ───────────────────────────────────────────────────────────────

def check_ollama(svc: OllamaService) -> bool:
    print(f"\n{BOLD}── Tjekker Ollama ──{RESET}")
    models = svc.list_models()
    if not models:
        print(f"{RED}✗ Ollama kører ikke. Kør: brew services start ollama{RESET}")
        return False
    print(f"{GREEN}✓ Ollama kører{RESET}")
    for m in models:
        print(f"    - {m}")
    if not svc.is_available():
        print(f"{YELLOW}⚠ Model '{DEFAULT_MODEL}' ikke pulled. Kør: ollama pull {DEFAULT_MODEL}{RESET}")
        return False
    print(f"{GREEN}✓ Model '{DEFAULT_MODEL}' klar{RESET}")
    return True


# ── Thumbnail-generering ──────────────────────────────────────────────────────

def bulk_generate_thumbnails(directory: Path) -> None:
    """Generer thumbnails for alle JPEG i mappen — samme 320x180 format som headend."""
    images = list(directory.rglob("*.jpg")) + list(directory.rglob("*.jpeg"))
    images = [p for p in images if not p.name.startswith(".") and ".thumbs" not in str(p)]

    print(f"\n{BOLD}── Thumbnail-generering ──{RESET}")
    print(f"  Fandt {len(images)} billeder")

    existing = sum(1 for p in images if find_thumbnail(p))
    missing  = len(images) - existing
    print(f"  Eksisterende thumbnails: {existing}")
    print(f"  Mangler: {missing}")

    if missing == 0:
        print(f"  {GREEN}✓ Alle thumbnails er allerede genereret{RESET}")
        return

    print(f"  Genererer {missing} thumbnails...")
    ok = fail = 0
    for i, img in enumerate(images, 1):
        if find_thumbnail(img):
            continue
        if img.stat().st_size < 50_000:
            continue  # Skip korrupte
        result = generate_thumbnail(img)
        if result:
            ok += 1
        else:
            fail += 1
        if i % 100 == 0:
            print(f"    {i}/{len(images)} — {ok} ok, {fail} fejl")

    print(f"\n  {GREEN}✓ Genereret: {ok}{RESET}")
    if fail:
        print(f"  {YELLOW}⚠ Fejlet: {fail}{RESET}")


# ── Billedfinder ──────────────────────────────────────────────────────────────

def find_images(directory: Path, sample: int, only_flagged: bool) -> list[Path]:
    all_images = list(directory.rglob("*.jpg")) + list(directory.rglob("*.jpeg"))
    all_images = [p for p in all_images
                  if not p.name.startswith(".") and ".thumbs" not in str(p)]

    print(f"\n{BOLD}── Billeder fundet ──{RESET}")
    print(f"  Total: {len(all_images)} JPEG-filer")

    # Vis thumbnail-dækning
    with_thumbs = sum(1 for p in all_images[:200] if find_thumbnail(p))
    print(f"  Thumbnail-dækning (sample 200): {with_thumbs}/200")

    if only_flagged:
        all_images.sort(key=lambda p: p.stat().st_size)
        flagged = [p for p in all_images if p.stat().st_size < 2_000_000][:sample * 2]
        random.shuffle(flagged)
        print(f"  Filtreret til {min(len(flagged), sample)} potentielt flagged billeder")
        return flagged[:sample]

    if sample and len(all_images) > sample:
        selected = random.sample(all_images, sample)
        print(f"  Sample: {sample} tilfældige billeder")
        return selected

    return all_images


# ── Analyse af enkelt billede ─────────────────────────────────────────────────

def analyse_one(svc: OllamaService, path: Path, idx: int, total: int) -> dict:
    size_kb = path.stat().st_size // 1024
    thumb   = find_thumbnail(path)
    thumb_str = f"{CYAN}thumbnail{RESET}" if thumb else f"{YELLOW}original (ingen thumb){RESET}"

    print(f"\n  [{idx}/{total}] {path.name}")
    print(f"  {'─' * 60}")
    print(f"  Størrelse: {size_kb} KB  |  Kilde: {thumb_str}")

    result = svc.analyze_image(path)

    if result.error:
        status = f"{RED}✗ SKIP{RESET}"
    elif result.alarm:
        status = f"{RED}🚨 ALARM{RESET}"
    elif result.is_anomaly:
        status = f"{YELLOW}⚠ ANOMALI{RESET}"
    else:
        status = f"{GREEN}✓ OK{RESET}"

    print(f"  Status:       {status}")
    print(f"  Årsag:        {result.probable_cause}")
    print(f"  Beskrivelse:  {result.description}")
    print(f"  Konfidence:   {result.confidence:.0%}")
    if result.used_thumbnail:
        print(f"  {CYAN}↳ Analyseret via thumbnail (320x180){RESET}")
    print(f"  Handling:     {result.action}")
    print(f"  Latency:      {result.latency_ms} ms")

    return {
        "filename":      path.name,
        "size_kb":       size_kb,
        "had_thumbnail": thumb is not None,
        "used_thumbnail": result.used_thumbnail,
        **result.as_dict(),
    }


# ── Sammenligningstest ────────────────────────────────────────────────────────

def run_compare(svc: OllamaService, images: list[Path]) -> None:
    """Sammenlign thumbnail vs. original analyse for at validere thumbnail-pålidelighed."""
    print(f"\n{BOLD}── Thumbnail vs. Original sammenligning ──{RESET}")
    print(f"  {len(images)} billeder  |  2 API-kald per billede\n")

    agreements = 0
    results    = []

    for i, img in enumerate(images, 1):
        print(f"  [{i}/{len(images)}] {img.name}")
        cmp = svc.analyze_image_compare(img)

        match_str    = f"{GREEN}✓ Enig{RESET}" if cmp["agreement"] else f"{YELLOW}⚠ Uenig{RESET}"
        cause_match  = f"{GREEN}✓{RESET}" if cmp["cause_match"] else f"{RED}✗{RESET}"
        anomaly_match = f"{GREEN}✓{RESET}" if cmp["anomaly_match"] else f"{RED}✗{RESET}"

        t  = cmp["thumbnail"]
        o  = cmp["original"]
        print(f"    Thumbnail:  {t['probable_cause']} ({t['confidence']:.0%})  {t['latency_ms']}ms")
        print(f"    Original:   {o['probable_cause']} ({o['confidence']:.0%})  {o['latency_ms']}ms")
        print(f"    Årsag:  {cause_match}  Anomali:  {anomaly_match}  →  {match_str}")

        if cmp["agreement"]:
            agreements += 1
        results.append(cmp)

    pct = agreements / len(images) * 100
    color = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED

    print(f"\n{BOLD}{'═' * 60}")
    print(f"  SAMMENLIGNINGSRESULTAT")
    print(f"{'═' * 60}{RESET}")
    print(f"  Billeder testet:  {len(images)}")
    print(f"  Enighed:          {color}{agreements}/{len(images)} ({pct:.0f}%){RESET}")

    if pct >= 80:
        print(f"\n  {GREEN}✓ Thumbnails er pålidelige — brug dem i produktion{RESET}")
    elif pct >= 60:
        print(f"\n  {YELLOW}⚠ Rimelig enighed — overvej større thumbnails (640x360){RESET}")
    else:
        print(f"\n  {RED}✗ Lav enighed — analyser originalbilleder i stedet{RESET}")

    # Vis uenigheder
    disagreements = [r for r in results if not r["agreement"]]
    if disagreements:
        print(f"\n  {BOLD}Uenigheder:{RESET}")
        for d in disagreements:
            print(f"    {d['filename']}")
            print(f"      Thumb:    {d['thumbnail']['probable_cause']} / anomali={d['thumbnail']['is_anomaly']}")
            print(f"      Original: {d['original']['probable_cause']} / anomali={d['original']['is_anomaly']}")


# ── Opsummering ───────────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    total   = len(results)
    skipped = sum(1 for r in results if r.get("error"))
    ok      = sum(1 for r in results if not r.get("is_anomaly") and not r.get("error"))
    anomaly = sum(1 for r in results if r.get("is_anomaly") and not r.get("alarm"))
    alarm   = sum(1 for r in results if r.get("alarm"))
    thumbs  = sum(1 for r in results if r.get("used_thumbnail"))
    avg_lat = sum(r.get("latency_ms", 0) for r in results) // max(total, 1)

    causes: dict[str, int] = {}
    for r in results:
        c = r.get("probable_cause", "unknown")
        causes[c] = causes.get(c, 0) + 1

    print(f"\n{BOLD}{'═' * 60}")
    print(f"  OPSUMMERING — {total} billeder")
    print(f"{'═' * 60}{RESET}")
    print(f"  {GREEN}✓ OK:           {ok}{RESET}")
    print(f"  {YELLOW}⚠ Anomali:      {anomaly}{RESET}")
    print(f"  {RED}🚨 Alarm:        {alarm}{RESET}")
    if skipped:
        print(f"  ↷ Sprunget over: {skipped}  (korrupte/for små)")
    print(f"\n  Thumbnails brugt: {CYAN}{thumbs}/{total}{RESET}")
    print(f"  Gns. latency:     {avg_lat} ms")

    print(f"\n{BOLD}  Årsagsfordeling:{RESET}")
    for cause, count in sorted(causes.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        bar = "█" * int(pct / 4)
        print(f"  {cause:<30} {bar:<25} {count:3d} ({pct:.0f}%)")

    if alarm:
        print(f"\n{RED}{BOLD}  Kræver handling:{RESET}")
        for r in results:
            if r.get("alarm"):
                print(f"    - {r['filename']}: {r.get('description','')}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TimeLapse Pro AI Billedanalyse")
    parser.add_argument("--dir",                 type=Path, help="Mappe med billeder")
    parser.add_argument("--file",                type=Path, help="Enkelt billedfil")
    parser.add_argument("--sample",              type=int, default=10)
    parser.add_argument("--only-flagged",        action="store_true")
    parser.add_argument("--compare",             action="store_true",
                        help="Sammenlign thumbnail vs. original (validering)")
    parser.add_argument("--generate-thumbs-only", action="store_true",
                        help="Generer kun thumbnails, analysér ikke")
    parser.add_argument("--no-thumbnails",       action="store_true",
                        help="Brug altid original (deaktiverer thumbnail-præference)")
    parser.add_argument("--report",              type=Path)
    parser.add_argument("--model",               default=DEFAULT_MODEL)
    args = parser.parse_args()

    if not args.dir and not args.file:
        parser.error("Angiv --dir eller --file")

    print(f"\n{BOLD}TimeLapse Pro — AI Billedanalyse{RESET}")
    print(f"Model: {args.model}")

    # Thumbnail-generering uden analyse
    if args.generate_thumbs_only:
        bulk_generate_thumbnails(args.dir)
        return

    svc = OllamaService(model=args.model)
    if not check_ollama(svc):
        sys.exit(1)

    images = [args.file] if args.file else find_images(args.dir, args.sample, args.only_flagged)
    if not images:
        print(f"{RED}Ingen billeder fundet.{RESET}")
        sys.exit(1)

    # Sammenligningstest
    if args.compare:
        run_compare(svc, images)
        return

    # Standard analyse
    prefer_thumb = not args.no_thumbnails
    print(f"\n{BOLD}── Analyserer {len(images)} billeder ──{RESET}")
    print(f"  Thumbnail-præference: {'ja' if prefer_thumb else 'nej (--no-thumbnails)'}")

    results = []
    for i, img in enumerate(images, 1):
        svc_kwargs = {"prefer_thumbnail": prefer_thumb}
        size_kb = img.stat().st_size // 1024
        thumb   = find_thumbnail(img)
        thumb_str = f"{CYAN}thumbnail{RESET}" if thumb else f"{YELLOW}original{RESET}"
        print(f"\n  [{i}/{len(images)}] {img.name}")
        print(f"  {'─' * 60}")
        print(f"  Størrelse: {size_kb} KB  |  Kilde: {thumb_str}")

        result = svc.analyze_image(img, prefer_thumbnail=prefer_thumb)

        if result.error:
            status = f"{RED}✗ SKIP{RESET}"
        elif result.alarm:
            status = f"{RED}🚨 ALARM{RESET}"
        elif result.is_anomaly:
            status = f"{YELLOW}⚠ ANOMALI{RESET}"
        else:
            status = f"{GREEN}✓ OK{RESET}"

        print(f"  Status:       {status}")
        print(f"  Årsag:        {result.probable_cause}")
        print(f"  Beskrivelse:  {result.description}")
        print(f"  Konfidence:   {result.confidence:.0%}")
        if result.used_thumbnail:
            print(f"  {CYAN}↳ Thumbnail brugt (320x180){RESET}")
        print(f"  Latency:      {result.latency_ms} ms")

        results.append({
            "filename":       img.name,
            "size_kb":        size_kb,
            "had_thumbnail":  thumb is not None,
            "used_thumbnail": result.used_thumbnail,
            **result.as_dict(),
        })

    print_summary(results)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": args.model,
                "total": len(results),
                "results": results,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n{GREEN}✓ Rapport gemt: {args.report}{RESET}")


if __name__ == "__main__":
    main()
