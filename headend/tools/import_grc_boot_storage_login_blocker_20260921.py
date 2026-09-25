#!/usr/bin/env python3
"""Idempotent GRC-registrering af det åbne macOS boot-storage/login-fund (2026-09-21).

Se Dokumentation/MACOS_BOOT_STORAGE_LOGIN_BLOCKER_2026-09.md for det fulde
fund og den midlertidige workaround (auto-login). Registreres nu i GRC fordi
findet 2026-09-21 skiftede fra "lejlighedsvis manuel test" til "load-bearing
for en daglig automatiseret proces" (nightly full-server-reboot rehearsal,
deploy/scripts/timelapse-nightly-maintenance) — Peter har eksplicit bedt om
at dette forbliver synligt sporet, ikke stiltiende accepteret ved gentagelse.

Køres mod live-DB:  DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
  .venv/bin/python3 headend/tools/import_grc_boot_storage_login_blocker_20260921.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402

ACTOR = "claude"
DOC = "Dokumentation/MACOS_BOOT_STORAGE_LOGIN_BLOCKER_2026-09.md"

ITEMS = [
    {
        "item_type": "finding",
        "external_id": "FIND-MACOS-BOOT-STORAGE-LOGIN-BLOCKER",
        "title": "macOS auto-login workaround for boot-storage/login blocker er nu load-bearing for nattens automatiske server-genstart",
        "status": "open",
        "priority": "P2",
        "description": (
            "Uden auto-login når Mac Mini'en login-vinduet før det eksterne data-fast-volume er "
            "monteret; Headend/Postgres bliver derfor kun tilgængelige efter konsol-login. Den "
            "midlertidige workaround (auto-login permanent aktiveret) blev accepteret 2026-09-07 "
            "som et dokumenteret, ikke-lukket fund med kendt fysisk-adgang-tradeoff. "
            "2026-09-21 blev dette load-bearing for en ny nattlig automatiseret proces: "
            "deploy/scripts/timelapse-nightly-maintenance kører nu en reel 'shutdown -r now' hver "
            "nat kl. 03:00 som del af genstarts-rehearsal før produktions-cutover, hvilket betyder "
            "workaroundet skal virke hver eneste nat, ikke kun under en enkeltstående manuel test. "
            "Peter har eksplicit godkendt at fortsætte på det nuværende workaround-grundlag "
            "('Yes, proceed as-is, but we need to investigate later. Please note!'), men den "
            "permanente løsning (UUID/device-valideret system-boot mount-flow uden krav om "
            "konsol-login) er fortsat ikke implementeret."
        ),
        "attributes": {
            "original_finding_date": "2026-09-07",
            "escalated_at": "2026-09-21",
            "escalation_reason": "nightly automated full-server-reboot now depends on this workaround succeeding every night",
            "workaround": "macOS auto-login permanently enabled",
            "workaround_tradeoff": "physical access to the console equals an unlocked desktop",
            "accepted_by": "Peter Frøkjær",
            "accepted_at": "2026-09-21",
            "acceptance_scope": "proceed as-is while nightly-reboot rehearsal runs; must keep investigating a permanent fix",
            "required_permanent_fix": "UUID/device-validated system-boot mount flow for data-fast that does not require console login, proven over a cold reboot with auto-login disabled",
            "related_change": "deploy/scripts/timelapse-nightly-maintenance, deploy/scripts/timelapse-post-reboot-verify",
        },
        "evidence": [
            (f"doc://{DOC}", "Fuldt fund + workaround-beslutning + krav til permanent løsning"),
            ("doc://Dokumentation/HANDOVER_LOG.md", "2026-09-21 handover: nightly full-server-reboot rehearsal + eksplicit note om fortsat åbent auto-login-workaround"),
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
        source="import_grc_boot_storage_login_blocker_20260921.py",
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
    print(f"GRC boot-storage/login blocker: {created} nye items, {evidence_added} nye evidens-links "
          f"(af {len(ITEMS)} items i alt — idempotent)")


if __name__ == "__main__":
    main()
