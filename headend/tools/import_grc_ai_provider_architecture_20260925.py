#!/usr/bin/env python3
"""Idempotent GRC-import for TimeLapse AI provider architecture, 2026-09-25.

Records implementation evidence separately from still-open physical/scale gates.
Run against the authoritative Headend DB after PR #258 acceptance.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402

ACTOR = "chatgpt-ai-provider-architecture-20260925"
DOC = "doc://Dokumentation/AI_PROVIDER_ARCHITECTURE_2026-09-24.md"
PR = "https://github.com/froekjaer/timelapse-pro/pull/258"

ITEMS = [
    {
        "item_type": "requirement",
        "external_id": "REQ-AI-PROVIDER-CAPABILITY-ROUTER-20260925",
        "title": "AI product functions must route through capability-based provider layer",
        "status": "implemented",
        "priority": "high",
        "description": (
            "Image AI, AI Search, AI-assisted SIEM/CMDB and AI Ops request capabilities "
            "from the TimeLapse capability router instead of constructing Apple, Ollama or "
            "Gemini clients in product business logic. Legacy image strategies are translated "
            "centrally for compatibility."
        ),
        "attributes": {
            "capabilities": ["vision", "text", "structured"],
            "providers": ["apple", "ollama", "gemini"],
            "deterministic_siem_authority": True,
            "tenant_rbac_remains_timelapse_owned": True,
        },
    },
    {
        "item_type": "control",
        "external_id": "CTRL-AI-PROVIDER-PROVENANCE-POLICY-20260925",
        "title": "Provider output is observational; TimeLapse owns policy, normalization and provenance",
        "status": "implemented",
        "priority": "high",
        "description": (
            "Provider/model/capability/latency provenance is retained. Image observations are "
            "normalized against TimeLapse canonical vocabulary and privacy policy. Raw Apple "
            "provider output is separated from adapter output. Provider confidence does not "
            "become verified truth."
        ),
        "attributes": {
            "raw_vs_adapter_boundary": True,
            "canonical_vocabulary_authority": "timelapse",
            "provider_confidence_is_ground_truth": False,
        },
    },
    {
        "item_type": "control",
        "external_id": "CTRL-AI-SIEM-DETERMINISTIC-AUTHORITY-20260925",
        "title": "Deterministic SIEM remains independent of AI provider judgement",
        "status": "implemented",
        "priority": "high",
        "description": (
            "headend/siem.py remains the deterministic event/rule authority and does not depend "
            "on the AI capability router. AI-assisted SIEM correlation/summarisation is routed "
            "through the provider layer and cannot silently suppress deterministic alarms."
        ),
        "attributes": {
            "authoritative_module": "headend/siem.py",
            "ai_module": "headend/ai/text_services.py",
        },
    },
    {
        "item_type": "finding",
        "external_id": "FIND-AI-PROVIDER-RESOURCE-ACCEPTANCE-PENDING-20260925",
        "title": "AI provider architecture still requires representative resource/concurrency acceptance",
        "status": "open",
        "priority": "medium",
        "description": (
            "The capability architecture can be code-complete while production-scale enablement "
            "remains gated. Representative 10-20 capture ground truth, provider text/structured "
            "physical checks, concurrency/RAM/thermal behaviour and configured fallback behaviour "
            "must be measured on the Headend before provider defaults are changed."
        ),
        "attributes": {
            "required_evidence": [
                "10-20 reviewed captures",
                "Apple/Ollama/Gemini capability smoke tests",
                "RAM/concurrency/thermal observation",
                "fallback behaviour",
            ],
            "must_not_change_default_from_single_capture": True,
        },
    },
]

EVIDENCE = [
    (PR, "PR #258 — AI provider capability architecture implementation"),
    (DOC, "AI provider architecture, invariants and acceptance gates"),
    ("doc://Dokumentation/HANDOVER_LOG.md", "Physical benchmark, provenance and implementation handovers"),
]


def upsert_item(db, spec: dict) -> tuple[GrcItem, bool]:
    item = db.query(GrcItem).filter_by(
        item_type=spec["item_type"],
        external_id=spec["external_id"],
    ).first()
    if item:
        # Keep the import idempotent but update implementation metadata when rerun.
        item.title = spec["title"][:300]
        item.description = spec["description"]
        item.status = spec["status"]
        item.priority = spec["priority"]
        item.attributes = spec["attributes"]
        item.updated_by = ACTOR
        return item, False

    item = GrcItem(
        item_type=spec["item_type"],
        external_id=spec["external_id"],
        title=spec["title"][:300],
        description=spec["description"],
        status=spec["status"],
        priority=spec["priority"],
        source=Path(__file__).name,
        scope={"product": "timelapse-pro", "domain": "ai-provider-architecture"},
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
        evidence_type="implementation_evidence",
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
            created += int(was_created)
            for uri, title in EVIDENCE:
                evidence_added += int(add_evidence(db, item, uri, title))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        f"AI provider architecture GRC: {created} nye items, "
        f"{evidence_added} nye evidens-links ({len(ITEMS)} items, idempotent)"
    )


if __name__ == "__main__":
    main()
