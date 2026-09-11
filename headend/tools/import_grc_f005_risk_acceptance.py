#!/usr/bin/env python3
"""Idempotent GRC-registrering af F-005 formel risikoaccept (2026-09-11).

Peter Frøkjær besluttede 2026-09-11 at acceptere risikoen ved headends
`system-hash` fallback for artifact-signatur formelt (jf.
Dokumentation/RISIKOACCEPT_F-005_SYSTEM_HASH_2026-09-11.md).

Registrerer:
- RISK-ARTIFACT-SYSTEM-HASH-FALLBACK (risk, status: accepted)
- FIND-ARTIFACT-SYSTEM-HASH-FALLBACK-F005 (finding, status: closed —
  dispositioneret via risikoaccepten)

Køres mod live-DB:  DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
  .venvs/timelapse-headend/bin/python3 headend/tools/import_grc_f005_risk_acceptance.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402

ACTOR = "kimi"
DOC = "Dokumentation/RISIKOACCEPT_F-005_SYSTEM_HASH_2026-09-11.md"

ITEMS = [
    {
        "item_type": "risk",
        "external_id": "RISK-ARTIFACT-SYSTEM-HASH-FALLBACK",
        "title": "Accepteret risiko: headend system-hash fallback for artifact-signatur (F-005)",
        "status": "accepted",
        "priority": "P1",
        "description": (
            "Headend accepterer sha256 hash-binding (system-hash) som signaturgrundlag, når ingen "
            "GPG-signeringsnøgle er konfigureret (main.py:5997, 6019, 6283-6288). Hash-binding beviser "
            "integritet men ikke ophav/autenticitet: en angriber med skriveadgang til artifact-lageret "
            "kan genberegne hashes. Risikoen er FORMELT ACCEPTERET af Peter Frøkjær 2026-09-11 for "
            "pre-produktionsfasen. Kompenserende kontroller: Edge afviser hash-only artifacts (PR #41, "
            "fail-closed OpenPGP), ingen ubegrænset produktionsrelease, UI-UPD-06 som RC1-gate. "
            "Genbesøges ved RC1, ved GPG-nøgle-ibrugtagning, ved ændret trusselsbillede — og senest 2027-03-11."
        ),
        "attributes": {
            "accepted_at": "2026-09-11",
            "accepted_by": "Peter Frøkjær",
            "decision": "formal_risk_acceptance",
            "scope": "pre-production only; drift uden konfigureret GPG-signeringsnøgle",
            "compensating_controls": [
                "Edge afviser hash-only artifacts (PR #41, fail-closed OpenPGP-verifikation)",
                "Ingen ubegrænset produktionsrelease (MASTER_REVIEW_CLOSURE §1)",
                "UI-UPD-06 signeret offline OS-bundle E2E som RC1-gate",
                "Update-audit-log på headend",
            ],
            "review_triggers": ["RC1/release-godkendelse", "GPG-nøgle ibrugtaget", "ændret trusselsbillede"],
            "review_deadline": "2027-03-11",
            "residual_risk": "moderate — acceptabel i pre-produktion",
            "source_findings": ["kimi-2026-08-15.md F-005"],
        },
        "evidence": [
            (f"doc://{DOC}", "Formel risikoaccept underskrevet af ejer 2026-09-11"),
            ("https://github.com/froekjaer/timelapse-pro/pull/41", "PR #41: Edge fail-closed OpenPGP-verifikation (kompenserende kontrol)"),
        ],
    },
    {
        "item_type": "finding",
        "external_id": "FIND-ARTIFACT-SYSTEM-HASH-FALLBACK-F005",
        "title": "F-005: Artefakt-signering falder tilbage til hash-binding uden GPG — dispositioneret via risikoaccept",
        "status": "closed",
        "priority": "medium",
        "description": (
            "Oprindeligt fund: kimi-2026-08-15.md F-005 (Major). Edge-side lukket af PR #41 "
            "(hash-only afvises ved installation). Headend-delen (system-hash som signaturgrundlag "
            "uden GPG-nøgle) er verificeret stadig aktiv på main, men er 2026-09-11 dispositioneret "
            "via FORMEL RISIKOACCEPT — se RISK-ARTIFACT-SYSTEM-HASH-FALLBACK (accepted) og "
            f"{DOC}. Lukket som fund; risikoen lever videre som accepteret risiko med "
            "genbesøgskriterier (RC1 / GPG-ibrugtagning / senest 2027-03-11)."
        ),
        "attributes": {
            "original_finding": "kimi-2026-08-15.md F-005",
            "disposition": "risk_accepted",
            "disposition_ref": "RISK-ARTIFACT-SYSTEM-HASH-FALLBACK",
            "dispositioned_at": "2026-09-11",
            "dispositioned_by": "Peter Frøkjær",
            "edge_side": "closed by PR #41",
        },
        "evidence": [
            (f"doc://{DOC}", "Formel risikoaccept 2026-09-11"),
            ("doc://Dokumentation/kimi-2026-08-15-AFSTEMNING-2026-09-11.md", "Afstemning: F-005 verificeret aktiv på main før disposition"),
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
        source="import_grc_f005_risk_acceptance.py",
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
        evidence_type="governance_source",
        title=title[:300],
        uri=uri,
        collected_by=ACTOR,
        retention_class="grc_source_permanent",
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
    print(f"GRC F-005 risikoaccept: {created} nye items, {evidence_added} nye evidens-links "
          f"(af {len(ITEMS)} items i alt — idempotent)")


if __name__ == "__main__":
    main()
