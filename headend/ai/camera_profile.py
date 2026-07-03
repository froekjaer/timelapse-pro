#!/usr/bin/env python3
"""
TimeLapse Pro — Selvlærende kamera-baseline
===========================================
Udleder automatisk "hvad er normalt for dette kamera" af kameraets egen
tag-historik, i stedet for at et menneske skal skrive det. Resultatet fodres
til vision-prompten som kontekst, så modellen kan vurdere AFVIGELSER.

Princip:
  - Glidende vindue (seneste N dage) = "den aktuelle normal". For en byggeplads
    følger det dermed byggefasen; for et statisk kamera er det bare det stabile
    mønster.
  - Persistente tags  = ses på ≥ min_freq af billederne → det normale billede.
  - Dag/nat-opdeling  = hvad er normalt om natten (så aktivitet om natten kan
    flagges som usædvanligt på et datagrundlag, ikke kun en regel).
  - Sæson             = hvilke måneder vinduet dækker.
  - Udvikling         = tags der er NYE i vinduet vs. tidligere, og tags der er
    FORSVUNDET → fanger hvordan en byggeplads udvikler sig (dynamisk vs statisk).

"Selvlærende": kør compute igen (eller på skema) når der er kommet nye billeder,
så opdaterer profilen sig selv.

CLI:
  python headend/ai/camera_profile.py --all                 # vis profiler (dry-run)
  python headend/ai/camera_profile.py --device TL-XXXX      # ét kamera
  python headend/ai/camera_profile.py --all --apply         # gem på cameras.auto_baseline
  python headend/ai/camera_profile.py --all --apply --window-days 30
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import Counter
from datetime import timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADEND   = REPO_ROOT / "headend"
sys.path.insert(0, str(HEADEND))
sys.path.insert(0, str(HEADEND / "ai"))

DEFAULT_TZ = "Europe/Copenhagen"

# normalize_tag + kategorier til at skelne "scene-udvikling" fra vejr/sæson-støj.
try:
    from tag_vocabulary import normalize_tag as _norm, PREDEFINED_TAGS as _PT
except Exception:  # pragma: no cover
    try:
        from .tag_vocabulary import normalize_tag as _norm, PREDEFINED_TAGS as _PT
    except Exception:
        _norm = lambda t: str(t).lower().strip()
        _PT = {}

# Flygtige tags (vejr, lys, kvalitet, sæson) tæller IKKE som byggeplads-udvikling —
# ellers ser et statisk kamera "dynamisk" ud bare fordi foråret bliver til sommer.
_VOLATILE_TAGS: set[str] = set()
for _cat in ("weather", "light_and_time", "camera_quality", "change_detection"):
    _VOLATILE_TAGS.update(_PT.get(_cat, []))
_VOLATILE_TAGS.update({
    "summer", "winter", "spring", "autumn", "summer_season", "winter_season",
    "spring_season", "autumn_season", "day", "night", "daylight", "season",
})

# Ændrings-/byggeplads-domæne: stærke indikatorer på AKTIV bygge-aktivitet.
# "dynamic" (= aktiv byggeplads) kræver mindst ét af disse i scenen — ellers er
# en stabil villa-/byudsigt med blot synonym-drift (house↔apartment_building,
# bushes↔vegetation) IKKE en byggeplads. Bevidst kun stærke indikatorer; tvetydige
# (truck, fence, traffic_cones, plywood) udeladt for ikke at fejludløse på en
# beboelsesscene med en parkeret lastbil.
_CHANGE_DOMAIN_TAGS: set[str] = {
    "construction_site", "building_site", "scaffolding", "scaffold",
    "tower_crane", "crane", "mobile_crane", "excavator", "digger", "bulldozer",
    "wheel_loader", "dumper", "dump_truck", "concrete_mixer", "concrete_pump",
    "cement_mixer", "pile_driver", "scissor_lift", "boom_lift", "cherry_picker",
    "telehandler", "formwork", "formwork_panels", "rebar", "rebar_cage",
    "reinforcement", "shell_construction", "building_under_construction",
    "under_construction", "earthworks", "excavation", "foundation",
    "foundation_work", "groundworks", "insulation_panels", "facade_cladding",
    "cladding", "brickwork", "masonry", "roof_construction", "building_materials",
    "construction_materials", "construction_machinery", "construction_vehicle",
    "site_hut", "site_office", "portacabin", "window_installation",
}


# ── Ren beregning (kan testes uden DB) ────────────────────────────────────────

def _local(dt, tz_name: str):
    try:
        from zoneinfo import ZoneInfo
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo(tz_name or DEFAULT_TZ))
    except Exception:
        return dt


def _season(month: int) -> str:
    return {12: "vinter", 1: "vinter", 2: "vinter", 3: "forår", 4: "forår", 5: "forår",
            6: "sommer", 7: "sommer", 8: "sommer", 9: "efterår", 10: "efterår", 11: "efterår"}[month]


def compute_profile(samples: list[tuple], window_days: int = 21,
                    min_freq: float = 0.30, tz_name: str = DEFAULT_TZ,
                    min_samples: int = 200) -> dict | None:
    """samples = [(captured_at: datetime, tags: list[str]), ...] (vilkårlig orden).

    Returnerer en profil-dict, eller None hvis for lidt data.
    """
    # Normalisér tags (synonym-konsolidering) så profilen er ren uanset data-alder.
    parsed = [(t, [n for n in (_norm(x) for x in tags) if n]) for t, tags in samples
              if t is not None and isinstance(tags, list) and tags]
    parsed = [(t, tags) for t, tags in parsed if tags]
    if len(parsed) < 5:
        return None
    parsed.sort(key=lambda x: x[0], reverse=True)
    latest = parsed[0][0]
    # Adaptivt vindue: et fast 21-dages vindue er rigtigt for et TÆT, aktivt kamera
    # (Frøkjær ~192 billeder/dag), men spild for et kamera med lang, tyndt-fordelt
    # historik (Travbyen: 5029 billeder over 4 år, men kun 51 i sidste 21 dage).
    # Udvid vinduet trinvist indtil mindst `min_samples` billeder — så de mange
    # billeder rent faktisk bruges — op til en øvre grænse. Tætte kameraer rammer
    # min_samples straks og beholder det korte, aktuelle vindue.
    eff_window = window_days
    cutoff = latest - timedelta(days=eff_window)
    recent = [(t, tags) for t, tags in parsed if t >= cutoff]
    if len(recent) < min_samples and len(parsed) > len(recent):
        for wd in (45, 90, 180, 365, 730):
            if wd <= eff_window:
                continue
            c2 = latest - timedelta(days=wd)
            r2 = [(t, tags) for t, tags in parsed if t >= c2]
            recent, eff_window, cutoff = r2, wd, c2
            if len(r2) >= min_samples:
                break
    window_days = eff_window
    recent = recent or parsed
    older  = [(t, tags) for t, tags in parsed if t < cutoff]

    n = len(recent)
    freq, day_freq, night_freq = Counter(), Counter(), Counter()
    day_n = night_n = 0
    months: Counter = Counter()
    for t, tags in recent:
        lt = _local(t, tz_name)
        months[lt.month] += 1
        is_night = lt.hour >= 22 or lt.hour < 5
        if is_night:
            night_n += 1
        else:
            day_n += 1
        for tag in set(tags):
            freq[tag] += 1
            (night_freq if is_night else day_freq)[tag] += 1

    persistent = [tag for tag, c in freq.most_common() if c / n >= min_freq]
    night_normal = [tag for tag, c in night_freq.most_common()
                    if night_n and c / night_n >= 0.30][:12]
    occasional = [tag for tag, c in freq.most_common()
                  if 0 < c / n < 0.10 and tag not in persistent][:12]

    # Progression/udvikling kræver nok HISTORIK at sammenligne mod — ellers
    # påstår vi ikke noget om "nyt siden sidst" (undgår falske dynamiske profiler
    # på tyndt datagrundlag).
    has_older = len(older) >= 10
    older_freq = Counter()
    for t, tags in older:
        for tag in set(tags):
            older_freq[tag] += 1
    on = len(older) or 1
    # Kun SUBSTANTIELLE tags (ikke vejr/lys/sæson) tæller som udvikling.
    if has_older:
        new_since = [tag for tag in persistent
                     if tag not in _VOLATILE_TAGS and older_freq.get(tag, 0) / on < 0.10][:12]
        gone_since = [tag for tag, c in older_freq.most_common()
                      if tag not in _VOLATILE_TAGS and c / on >= 0.30
                      and freq.get(tag, 0) / n < 0.10][:12]
    else:
        new_since, gone_since = [], []
    # "dynamic" = AKTIV BYGGEPLADS, afgjort af om scenen PERSISTENT indeholder
    # bygge-domæne-tags (scaffolding/crane/shell_construction/…). Det er det
    # robuste signal — uafhængigt af datatæthed: sparsomme byggeplads-kameraer
    # (fx Travbyen, 51 billeder) klassificeres korrekt, OG en stabil villa-/by-
    # udsigt med kun synonym-drift forbliver 'static' (ingen byggetags).
    # new_since/gone_since bruges KUN til progressions-teksten (vises når dynamic),
    # ikke til selve beslutningen — så få overgange gør ikke en byggeplads 'static'.
    dynamic = any(t in _CHANGE_DOMAIN_TAGS for t in persistent)

    return {
        "n_recent": n, "n_older": len(older), "window_days": window_days,
        "persistent": persistent[:18], "night_normal": night_normal,
        "occasional": occasional, "new_since": new_since, "gone_since": gone_since,
        "seasons": [s for s, _ in Counter(_season(m) for m in months.elements()).most_common()],
        "kind": "dynamic" if dynamic else "static",
    }


def generate_baseline_text(p: dict) -> str:
    """Dansk baseline-tekst til prompten. Engelske tag-tokens bevares (modellen
    tagger på engelsk, så den kan matche direkte)."""
    if not p:
        return ""
    seasons = ", ".join(p["seasons"]) or "ukendt"
    lines = [f"(Auto-baseline lært af {p['n_recent']} billeder, seneste {p['window_days']} dage. Årstid: {seasons}.)"]
    if p["persistent"]:
        lines.append("Normalt på næsten alle billeder: " + ", ".join(p["persistent"]) + ".")
    if p["night_normal"]:
        lines.append("Om natten ses normalt: " + ", ".join(p["night_normal"]) + ".")
    else:
        lines.append("Om natten: normalt mørke og ingen aktivitet.")
    if p["occasional"]:
        lines.append("Forekommer kun lejlighedsvis (bemærkelsesværdigt hvis fremtrædende): " + ", ".join(p["occasional"]) + ".")
    if p["kind"] == "dynamic":
        lines.append("DETTE ER EN AKTIV BYGGEPLADS I UDVIKLING — forvent løbende fremskridt.")
        if p["new_since"]:
            lines.append("Nyt i den seneste periode: " + ", ".join(p["new_since"]) + ".")
        if p["gone_since"]:
            lines.append("Forsvundet siden tidligere fase: " + ", ".join(p["gone_since"]) + ".")
        lines.append("Markér nye/fjernede maskiner, materialer og byggefaser, og fremskridt siden sidst.")
    else:
        lines.append("Forholdsvis statisk udsigt — det er primært årstid og småting der ændrer sig.")
    lines.append("Vurdér derfor som USÆDVANLIGT: objekter eller aktivitet udenfor dette mønster — fx køretøjer eller personer om natten, røg/ild, ukendte køretøjer, eller ting der normalt ikke er her.")
    return " ".join(lines)


# ── DB-integration ─────────────────────────────────────────────────────────────

def _build_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql://peter@localhost/timelapse_db")
    os.environ["DATABASE_URL"] = db_url
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    return db_url, sessionmaker(bind=create_engine(db_url))


def _site_tz(db, device_id: str) -> str:
    from sqlalchemy import text
    try:
        row = db.execute(text("""
            SELECT s.timezone FROM devices d LEFT JOIN sites s ON s.id = d.site_id
            WHERE d.device_id = :d
        """), {"d": device_id}).first()
        return (row[0] if row and row[0] else DEFAULT_TZ)
    except Exception:
        return DEFAULT_TZ


def load_samples(db, device_id: str) -> list[tuple]:
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT captured_at, ai_tags FROM captures
        WHERE device_id = :d AND ai_tags IS NOT NULL AND captured_at IS NOT NULL
        ORDER BY captured_at DESC
    """), {"d": device_id}).mappings().all()
    out = []
    for r in rows:
        try:
            tags = json.loads(r["ai_tags"])
        except Exception:
            continue
        if isinstance(tags, list):
            out.append((r["captured_at"], tags))
    return out


def store_baseline(db, device_id: str, text_value: str, kind: str) -> bool:
    """Skriv auto-baseline på det AKTIVE logiske kamera for enheden."""
    from sqlalchemy import text
    from datetime import datetime
    a = db.execute(text("""
        SELECT camera_id FROM device_assignments
        WHERE device_id = :d AND unassigned_at IS NULL
        ORDER BY assigned_at DESC LIMIT 1
    """), {"d": device_id}).first()
    if not a:
        return False
    db.execute(text("""
        UPDATE cameras SET auto_baseline = :b, auto_baseline_at = :ts, auto_baseline_kind = :k
        WHERE id = :cid
    """), {"b": text_value, "ts": datetime.now(timezone.utc), "k": kind, "cid": a[0]})
    return True


def recompute_all_baselines(db, apply: bool = True, window_days: int = 21,
                            min_freq: float = 0.30, min_samples: int = 200) -> dict:
    """Programmatisk genberegning af ALLE kamera-baselines på en eksisterende
    DB-session. Bruges af det natlige headend-job (og kan kaldes fra scripts).
    Returnerer et resumé. Idempotent: genberegner blot fra tag-historikken.

    min_samples styrer det adaptive vindue: et kamera udvider sit vindue indtil
    mindst så mange billeder. Tætte kameraer (Frøkjær) beholder 21 dage; tynde
    produktions-kameraer (~3-4/dag) udvider for at få en stabil baseline."""
    import os as _os
    try:
        min_samples = int(_os.getenv("TIMELAPSE_BASELINE_MIN_SAMPLES", str(min_samples)))
    except ValueError:
        pass
    from sqlalchemy import text as _text
    devices = [r[0] for r in db.execute(_text(
        "SELECT DISTINCT device_id FROM captures WHERE ai_tags IS NOT NULL"
    )).all()]
    updated = skipped = no_camera = 0
    for dev in devices:
        try:
            samples = load_samples(db, dev)
            prof = compute_profile(samples, window_days=window_days, min_freq=min_freq,
                                   tz_name=_site_tz(db, dev), min_samples=min_samples)
            if not prof:
                skipped += 1
                continue
            if apply:
                txt = generate_baseline_text(prof)
                if store_baseline(db, dev, txt, prof["kind"]):
                    updated += 1
                else:
                    no_camera += 1
        except Exception:
            skipped += 1
    if apply:
        db.commit()
    return {"devices": len(devices), "updated": updated,
            "skipped": skipped, "no_active_camera": no_camera}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=str, default=None, help="Ét device_id")
    ap.add_argument("--all", action="store_true", help="Alle enheder med billeder")
    ap.add_argument("--apply", action="store_true", help="Gem på cameras.auto_baseline (ellers dry-run)")
    ap.add_argument("--window-days", type=int, default=21,
                    help="Startvindue i dage (udvides adaptivt op til min-samples)")
    ap.add_argument("--min-freq", type=float, default=0.30)
    ap.add_argument("--min-samples", type=int, default=200,
                    help="Adaptivt vindue udvides indtil mindst så mange billeder (tæthed-robust)")
    args = ap.parse_args()

    db_url, Session = _build_engine()
    from sqlalchemy import text
    db = Session()
    mode = "APPLY (gemmer)" if args.apply else "DRY-RUN"
    print(f"\n{'='*64}\n  Selvlærende kamera-baseline — {mode}\n{'='*64}\n  DB: {db_url}\n")
    try:
        if args.device:
            devices = [args.device]
        else:
            devices = [r[0] for r in db.execute(text(
                "SELECT DISTINCT device_id FROM captures WHERE ai_tags IS NOT NULL"
            )).all()]
        for dev in devices:
            samples = load_samples(db, dev)
            prof = compute_profile(samples, window_days=args.window_days, min_freq=args.min_freq,
                                   tz_name=_site_tz(db, dev), min_samples=args.min_samples)
            if not prof:
                print(f"  [{dev}] for lidt data — sprunget over\n")
                continue
            txt = generate_baseline_text(prof)
            print(f"  ── {dev}  [{prof['kind']}, {prof['n_recent']} billeder/{prof['window_days']}d] ──")
            print(f"     {txt}\n")
            if args.apply:
                ok = store_baseline(db, dev, txt, prof["kind"])
                print(f"     {'✅ gemt på aktivt kamera' if ok else '⚠️  intet aktivt kamera — ikke gemt'}\n")
        if args.apply:
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
