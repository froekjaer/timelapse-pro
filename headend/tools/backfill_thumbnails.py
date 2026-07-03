#!/usr/bin/env python3
"""
TimeLapse Pro — Thumbnail-backfill (ren filsystem, ingen DB/UI)
==============================================================
Går et billed-træ igennem og genererer manglende thumbnails. Frisk proces →
ingen nginx-timeout/504, ingen genstart. Samme format som headenden
(320×180 letterboxed JPEG q78) og samme nabo-mappe (`.thumbs/<navn>`), så
`get_thumbnail` finder dem direkte bagefter.

Et billede springes over hvis der allerede findes en gyldig thumbnail i en af
de kendte kandidat-stier (samme liste som headendens `_find_existing_thumbnail`).

Brug:
  # Kun Travbyen (anbefalet til den nuværende oprydning):
  python headend/tools/backfill_thumbnails.py \
    --path /Volumes/data-fast/timelapse-incoming/canonical-images/Kirkbi_A_S/Travbyen

  # Alt (springer eksisterende over):
  python headend/tools/backfill_thumbnails.py

  python headend/tools/backfill_thumbnails.py --dry-run     # vis kun hvad der mangler
  python headend/tools/backfill_thumbnails.py --workers 2   # skån data-fast (default 3)
"""
from __future__ import annotations
import argparse, os, sys, time, secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEFAULT_ROOT = os.getenv("TIMELAPSE_IMAGE_ROOT",
                         "/Volumes/data-fast/timelapse-incoming/canonical-images")
THUMB_SIZE = (320, 180)
IMG_EXTS = {".jpg", ".jpeg"}
SKIP_DIRS = {".thumbs", ".headend-thumbs", "thumbs", "thumbnails", ".quarantine"}


def _candidates(image: Path) -> list[Path]:
    """Samme kandidat-liste som headendens _find_existing_thumbnail."""
    stem, suffix = image.stem, image.suffix or ".jpg"
    p = image.parent
    return [
        p / ".thumbs" / image.name,
        p / ".headend-thumbs" / image.name,
        p / "thumbs" / image.name,
        p / "thumbnails" / image.name,
        p / f"thumb_{image.name}",
        p / f"thumbnail_{image.name}",
        p / f"{stem}_thumb{suffix}",
        p / f"{stem}.thumb{suffix}",
    ]


def _valid_thumb(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size >= 256
    except OSError:
        return False


def _has_thumb(image: Path) -> bool:
    return any(_valid_thumb(c) for c in _candidates(image))


def _generate(image: Path) -> tuple[str, str | None]:
    """Generér thumbnail til image.parent/.thumbs/<navn>. Returnerer (status, fejl)."""
    from PIL import Image, ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    target = image.parent / ".thumbs" / image.name
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
        try:
            with Image.open(image) as original:
                img = original.convert("RGB")
                img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                canvas = Image.new("RGB", THUMB_SIZE, (15, 15, 15))
                canvas.paste(img, ((THUMB_SIZE[0] - img.width) // 2,
                                   (THUMB_SIZE[1] - img.height) // 2))
                canvas.save(str(tmp), "JPEG", quality=78)
            os.replace(tmp, target)
            return "generated", None
        finally:
            tmp.unlink(missing_ok=True)
    except Exception as exc:
        return "failed", str(exc)


def iter_images(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() in IMG_EXTS:
                yield Path(dirpath) / name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT, help="Billed-rod")
    ap.add_argument("--path", default=None, help="Begræns til denne understi (fx ét kamera)")
    ap.add_argument("--workers", type=int, default=3, help="Samtidige genereringer (skån data-fast)")
    ap.add_argument("--force", action="store_true", help="Regenerér selvom thumbnail findes")
    ap.add_argument("--dry-run", action="store_true", help="Vis kun hvad der mangler")
    ap.add_argument("--quarantine-broken", action="store_true",
                    help="Flyt ULÆSELIGE kilde-billeder (korrupte/trunkerede) til .quarantine/ (reversibelt) + udskriv SQL til at fjerne deres capture-rækker")
    args = ap.parse_args()

    base = Path(args.path) if args.path else Path(args.root)
    if not base.exists():
        print(f"❌ Stien findes ikke: {base}"); return 1

    print(f"\n{'='*64}\n  Thumbnail-backfill\n{'='*64}\n  Rod: {base}\n  Workers: {args.workers}  Force: {args.force}  Dry-run: {args.dry_run}\n")

    print("  Scanner billeder…")
    missing = []
    scanned = 0
    for img in iter_images(base):
        scanned += 1
        if args.force or not _has_thumb(img):
            missing.append(img)
        if scanned % 5000 == 0:
            print(f"    …{scanned} scannet, {len(missing)} mangler indtil videre")
    print(f"  {scanned} billeder scannet → {len(missing)} mangler thumbnail\n")

    if args.dry_run or not missing:
        for m in missing[:20]:
            print(f"    mangler: {m}")
        if len(missing) > 20:
            print(f"    … +{len(missing)-20} flere")
        print("\n  (dry-run — intet genereret)" if args.dry_run else "  ✅ Intet at gøre.")
        return 0

    gen = fail = 0
    failures: list[tuple[Path, str | None]] = []
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_generate, m): m for m in missing}
        for i, fut in enumerate(as_completed(futs), 1):
            status, err = fut.result()
            if status == "generated":
                gen += 1
            else:
                fail += 1
                failures.append((futs[fut], err))
                if fail <= 10:
                    print(f"    ⚠️  {futs[fut].name}: {err}")
            if i % 250 == 0 or i == len(missing):
                rate = i / max(0.001, time.monotonic() - t0)
                print(f"    {i}/{len(missing)}  ({gen} ok, {fail} fejl, {rate:.0f}/s)")

    print(f"\n{'─'*60}\n  Genereret: {gen}   Fejlet: {fail}   ({time.monotonic()-t0:.0f}s)")

    # Karantæne af ULÆSELIGE kilder (kun korrupte/trunkerede — ikke transiente I/O-fejl)
    if args.quarantine_broken and failures:
        _BROKEN = ("cannot identify", "truncated", "broken data")
        broken = [(p, e) for p, e in failures if e and any(s in e.lower() for s in _BROKEN)]
        transient = len(failures) - len(broken)
        moved = []
        for p, _e in broken:
            qdir = p.parent / ".quarantine"
            try:
                qdir.mkdir(parents=True, exist_ok=True)
                os.replace(str(p), str(qdir / p.name))   # samme volumen → atomisk flyt
                moved.append(p)
            except OSError as exc:
                print(f"    ⚠️  Kunne ikke flytte {p.name}: {exc}")
        print(f"\n  Karantæne: {len(moved)} ulæselige kilder flyttet til .quarantine/"
              + (f"  ({transient} transiente fejl rørt IKKE)" if transient else ""))
        if moved:
            names = ",".join("'" + p.name.replace("'", "''") + "'" for p in moved)
            print("\n  For også at fjerne deres rækker fra galleriet (kør selv i psql):")
            print(f"    DELETE FROM captures WHERE filename IN ({names});")
            print("\n  (Filerne ligger stadig i .quarantine/ og kan gendannes — intet er slettet permanent.)")

    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
