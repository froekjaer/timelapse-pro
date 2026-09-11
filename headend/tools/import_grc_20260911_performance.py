#!/usr/bin/env python3
"""Idempotent GRC-registrering af performance-hændelserne 2026-09-11.

Baggrund (verificeret via nginx-log, browser-diagnostik og live-tests):
1. Kl. 00:04 blev fem dashboard-kald afvist med HTTP 503 ("limiting requests"),
   fordi api_general-zonen (120 r/m + burst 60) er nøglet pr. IP, så faner og
   genindlæsninger deler én bucket. Dashboards Promise.all fejlede samlet, og
   data kom først ved 60 s auto-refresh.
2. Kl. 16:47 måltes 3,7 s forsinkelse på /users-API'et i browseren, mens nginx
   havde serveret svaret på 17–27 ms: linket var mættet af 5–6 MB fuldbilleder
   fra Lightbox-browsing (hairpin via offentlig IP forværrer det).

Begge hændelser er rettet (PR #218 og PR #220) og live-verificeret. Dette script
registrerer findings + actions i GRC-registeret, så hændelserne er spor bare.
Køres mod live-DB:  DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
  .venvs/timelapse-headend/bin/python3 headend/tools/import_grc_20260911_performance.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402

ACTOR = "kimi"

ITEMS = [
    {
        "item_type": "finding",
        "external_id": "FIND-API-RATELIMIT-503-LEGIT-UI-20260911",
        "title": "api_general rate-limit afviste legitim UI-trafik (503) — delt pr.-IP-bucket",
        "status": "closed",
        "priority": "medium",
        "description": (
            "2026-09-11 00:04: Fem dashboard-API-kald afvist med HTTP 503; nginx-fejllog "
            "bekræftede 'limiting requests'. Rodårsag: limit_req_zone api_general (120 r/m, "
            "burst 60) er nøglet på $binary_remote_addr, så alle faner/brugere bag samme IP "
            "deler én bucket — normale genindlæsninger + fem parallelle dashboard-kald overskred "
            "grænsen. Dashboards samlede Promise.all fejlede uden synlig fejl, og data kom først "
            "ved auto-refresh 60 s senere. Login-zonen (api_login, 10 r/m) var ikke involveret."
        ),
        "attributes": {
            "root_cause": "per-IP rate-limit zone sat for lavt til legitim UI-burst-adfærd",
            "first_observed": "2026-09-11T00:04:29+02:00",
            "detection": "browser-diagnostik + nginx error-log korrelation (Codex)",
            "fix_prs": ["#218"],
            "verified": "40-kalds burst gennem live nginx: 0 x 503, 0 nye 'limiting requests' (2026-09-11 17:55)",
        },
        "evidence": [
            ("https://github.com/froekjaer/timelapse-pro/pull/218", "PR #218: rate-limit 600 r/m + burst 100, dashboard-resiliens, diagnostik-præcision"),
            ("doc://Dokumentation/HANDOVER_LOG.md#2026-09-11-0045", "HANDOVER_LOG 2026-09-11 00:45 + 17:55: analyse, fix og live-verifikation"),
        ],
    },
    {
        "item_type": "action",
        "external_id": "ACT-API-RATELIMIT-DASHBOARD-RESILIENCE-20260911",
        "title": "Rate-limit hævet til legitim UI-trafik + Dashboard fejlhåndtering med backoff-retry",
        "status": "implemented",
        "priority": "medium",
        "description": (
            "Tre rettelser i PR #218: (1) api_general hævet til 600 r/m + burst 100 i kanonisk "
            "nginx-config (deploy/nginx/timelapse.froekjaer.dk.conf) og live; api_login uændret, "
            "misbrugsbeskyttelse bevaret. (2) Dashboard bruger Promise.allSettled pr. sektion, "
            "synligt fejl-banner med 'Prøv igen', og withRetry kun ved 429/502/503/504/netværksfejl "
            "(max 2 retries, backoff 800-1600 ms + jitter, Retry-After honoreres, aldrig 401/403). "
            "(3) Navigationsdiagnostik: første load målt fra dokument-navigationstart, auto-refresh "
            "registreres ikke som 60-120 s navigationer, load afsluttet med fejl registreres som fejl."
        ),
        "attributes": {
            "prs": ["#218", "#219"],
            "tests": "node --test 11/11 (inkl. simuleret 503/429/401/403); tsc rent; eslint 0 nye",
            "deployed": "2026-09-11 17:55 (UI-build + live nginx reload, homebrew.mxcl.nginx)",
        },
        "evidence": [
            ("https://github.com/froekjaer/timelapse-pro/pull/218", "PR #218 (squash-merget, main 0a7278f3)"),
            ("https://github.com/froekjaer/timelapse-pro/pull/219", "PR #219: handover + korrektion af nginx-servicenavn"),
        ],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-LIGHTBOX-FULLRES-BANDWIDTH-20260911",
        "title": "Lightbox-browsing med 5-6 MB fuldbilleder mættede linket — API-kald forsinket 3,7 s",
        "status": "closed",
        "priority": "medium",
        "description": (
            "2026-09-11 16:47 UTC: Browser-diagnostik viste /users-API-kald med 3.665 ms til "
            "første byte, mens nginx access-log viste samme svar serveret paa 17-27 ms og "
            "Server-Timing viste app=12 ms, sql=3 ms, loop_lag=0. Forsinkelsen sad i netvaerksvejen: "
            "fuldoploeste billeder (5-6 MB, rt 0,5-2 s stk.) mættede forbindelsen, saa sma API-svar "
            "kom i koe. Adgang via offentlig IP (backend.timelapse-pro.dk:8443) forværrer det "
            "(hairpin: 80-240 ms vs 5 ms via LAN, målt ubelastet). Separat undersoegt: index.html "
            "serveres altid paa <1 ms ifølge nginx-log — det tidligere '4-5 s til første byte' "
            "har samme netvaerksforklaring, ikke server."
        ),
        "attributes": {
            "root_cause": "båndbredde mættet af fuldopløste billeder + hairpin-netværksvej",
            "measured": "browser 3665 ms vs nginx rt=17-27 ms vs app=12 ms (samme requests)",
            "fix_prs": ["#220"],
            "user_guidance": "brug https://timelapse.froekjaer.dk (LAN) hjemme",
        },
        "evidence": [
            ("https://github.com/froekjaer/timelapse-pro/pull/220", "PR #220: progressiv Lightbox + idle baggrundsprefetch"),
            ("doc://Dokumentation/HANDOVER_LOG.md#2026-09-11-1905", "HANDOVER_LOG 2026-09-11 19:05 + 19:20: beviskæde og fix"),
        ],
    },
    {
        "item_type": "action",
        "external_id": "ACT-LIGHTBOX-PROGRESSIVE-PREFETCH-20260911",
        "title": "Progressiv Lightbox (thumbnail → fuld opløsning) + sekventiel idle-baggrundsprefetch",
        "status": "implemented",
        "priority": "medium",
        "description": (
            "PR #220: Lightbox viser thumbnail øjeblikkeligt (som regel cachet fra galleriet) og "
            "swapper fuld opløsning ind når den er hentet; badge 'Henter fuld opløsning...' mens "
            "der hentes; thumbnail-404 giver fallback til fuld URL. Ny prefetchQueue (ren fabrik + "
            "browser-singleton): nærmest-først (naboer derefter galleri), sekventiel én ad gangen, "
            "requestIdleCallback, udskydes mens fanen er skjult, annulleres når Lightbox lukkes. "
            "Race rettet: cancel under in-flight load kunne standse køen permanent."
        ),
        "attributes": {
            "prs": ["#220"],
            "tests": "node --test 15/15 (4 nye prefetch-queue inkl. cancel-race); tsc rent; build OK",
            "deployed": "2026-09-11 ~19:30 (UI-build i live-klonen, main a210d9b9)",
        },
        "evidence": [
            ("https://github.com/froekjaer/timelapse-pro/pull/220", "PR #220 (squash-merget, main a210d9b9)"),
        ],
    },
]


def upsert_item(db, spec: dict) -> tuple[GrcItem, bool]:
    item = db.query(GrcItem).filter_by(
        item_type=spec["item_type"], external_id=spec["external_id"]
    ).first()
    if item:
        return item, False
    item = GrcItem(
        item_type=spec["item_type"],
        external_id=spec["external_id"],
        title=spec["title"][:300],
        description=spec["description"],
        status=spec["status"],
        priority=spec["priority"],
        source="import_grc_20260911_performance.py",
        scope={"product": "timelapse-pro"},
        attributes=spec["attributes"],
        created_by=ACTOR,
        updated_by=ACTOR,
    )
    db.add(item)
    db.flush()
    return item, True


def add_evidence(db, item: GrcItem, uri: str, title: str) -> bool:
    if db.query(GrcEvidence).filter_by(item_id=item.id, uri=uri).first():
        return False
    db.add(GrcEvidence(
        item_id=item.id,
        evidence_type="closure_evidence",
        title=title[:300],
        uri=uri,
        collected_by=ACTOR,
        retention_class="grc_standard",
    ))
    return True


def main() -> None:
    db = SessionLocal()
    created = evidence_added = 0
    try:
        for spec in ITEMS:
            item, was_created = upsert_item(db, spec)
            created += was_created
            for uri, ev_title in spec["evidence"]:
                evidence_added += add_evidence(db, item, uri, ev_title)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"GRC 2026-09-11 performance: {created} nye items, {evidence_added} nye evidens-links "
          f"(af {len(ITEMS)} items i alt — idempotent)")


if __name__ == "__main__":
    main()
