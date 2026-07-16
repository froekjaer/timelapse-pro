#!/usr/bin/env python3
"""Extract requirement candidates from reviewed product documentation.

Dry-run is the default. --apply writes candidates and source evidence to PostgreSQL.
The extractor deliberately excludes handover logs, generated reports and old versions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, GrcLink, SessionLocal  # noqa: E402


SOURCES = (
    "AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md",
    "KRAVREGISTER_og_STATUS_v10.md",
    "Timelapse_pro_full_documentation_v10.md",
    "TIMELAPSE_BILLEDKVALITET_OG_VIDEOARKITEKTUR_v1.md",
    "Claude_AI_Tagging_Redesign_2026-06-23.md",
    "Global_Config_og_Kamera_Binding_2026-06-22.md",
    "Nikon_Z30_LAB_Profil_og_Fokus_2026-06-22.md",
    "TimeLapse_Configuration_Guide_v10.md",
    "TimeLapse_Roadmap_v10.md",
    "PROVISIONERING_EDGE_OG_MAC_HEADEND_v1.md",
    "MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md",
    "Arkitektur/Modularisering_Platform_Payload_Plan.md",
    "ADR/ADR-001-platform-payload-split.md",
    "REGULATORISK_OG_STANDARD_REFERENCE_v1.md",
    "LICENS_COMPLIANCE_OG_SBOM_EVIDENS_v1.md",
    "GO_LIVE_CHECKLIST_v10.md",
)
MODAL = re.compile(r"\b(skal|må ikke|maa ikke|bør|boer|kræves|kraeves|ønskes|oenskes)\b", re.I)
LEGACY_ID = re.compile(
    r"^(?:REQ|FR|NFR|SEC|UI|CFG|CAM|UPD|OPS|BKP|GDPR|AI|PROV)[:_ -]?\d[A-Z0-9.-]*$",
    re.I,
)


def classify(text: str) -> tuple[str, list[str]]:
    lower = text.casefold()
    domains = []
    rules = {
        "security": ("sikker", "security", "auth", "rbac", "kryp", "signatur", "certifikat", "mfa"),
        "privacy": ("gdpr", "persondata", "privacy", "retention", "slet"),
        "availability": ("tilgæng", "oppetid", "offline", "failover", "backup", "restore", "autonom"),
        "performance": ("performance", "latency", "sekund", "hurtig", "throughput", "kapacitet"),
        "usability": ("brugerven", "ui", "menu", "vises", "tilgængelig via"),
        "maintainability": ("modul", "vedligehold", "test", "log", "diagnost", "opdater"),
        "interoperability": ("api", "integration", "eksport", "import", "standard"),
        "compliance": ("iso", "iec", "cra", "nis2", "sabsa", "cobit", "audit", "compliance"),
    }
    for domain, words in rules.items():
        if any(word in lower for word in words):
            domains.append(domain)
    nonfunctional = any(domain in domains for domain in (
        "security", "privacy", "availability", "performance", "usability",
        "maintainability", "interoperability", "compliance",
    ))
    return ("non_functional" if nonfunctional else "functional"), domains


def standard_refs(text: str) -> list[str]:
    patterns = {
        "SABSA": r"\bsabsa\b", "COBIT": r"\bcobit\b",
        "ISO27001": r"\biso(?:/iec)?\s*2700[12]\b|\biso\s*27000\b",
        "IEC62443": r"\biec\s*62443\b", "NIS2": r"\bnis\s*2\b|\bnis2\b",
        "CRA": r"\bcyber resilience act\b|\bcra\b", "GDPR": r"\bgdpr\b",
        "AI-ACT": r"\bai act\b|\bai-forord", "NIST": r"\bnist\b", "ENISA": r"\benisa\b",
    }
    lower = text.casefold()
    return [name for name, pattern in patterns.items() if re.search(pattern, lower, re.I)]


def clean(value: str) -> str:
    value = re.sub(r"[`*_✅🟡🔴]", "", value)
    return re.sub(r"\s+", " ", value).strip(" -|:")


def candidates(doc_dir: Path) -> list[dict]:
    found: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for source_name in SOURCES:
        path = doc_dir / source_name
        if not path.exists():
            continue
        raw = path.read_bytes()
        source_sha = hashlib.sha256(raw).hexdigest()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        slug = re.sub(r"[^A-Z0-9]+", "-", path.stem.upper()).strip("-")[:45]
        for line_no, line in enumerate(lines, 1):
            text = ""
            legacy_id = None
            if line.lstrip().startswith("|"):
                cells = [clean(cell) for cell in line.strip().strip("|").split("|")]
                if cells and LEGACY_ID.match(cells[0]) and len(cells) > 1:
                    legacy_id, text = cells[0].upper(), cells[1]
            elif re.match(r"^\s*[-*]\s+", line) and MODAL.search(line):
                text = clean(re.sub(r"^\s*[-*]\s+", "", line))
            if len(text) < 12:
                continue
            key = (source_name, line_no, text.casefold())
            if key in seen:
                continue
            seen.add(key)
            requirement_class, quality_domains = classify(text)
            token = legacy_id or hashlib.sha256(text.casefold().encode()).hexdigest()[:12].upper()
            found.append({
                "external_id": f"REQ-{slug}-{token}"[:100],
                "legacy_id": legacy_id,
                "title": text[:300],
                "description": text,
                "requirement_class": requirement_class,
                "quality_domains": quality_domains,
                "standard_refs": standard_refs(text),
                "source": source_name,
                "source_line": line_no,
                "source_sha256": source_sha,
            })
    return found


def apply(rows: list[dict], actor: str) -> dict:
    db = SessionLocal()
    created = evidence_created = conflict_links = 0
    try:
        by_legacy: dict[str, list[GrcItem]] = {}
        for row in rows:
            item = db.query(GrcItem).filter_by(item_type="requirement", external_id=row["external_id"]).first()
            if not item:
                item = GrcItem(
                    item_type="requirement", external_id=row["external_id"], title=row["title"],
                    description=row["description"], status="candidate_review", priority=None,
                    source=f'{row["source"]}:{row["source_line"]}', scope={"product": "timelapse-pro"},
                    attributes={"requirement_class": row["requirement_class"],
                                "quality_domains": row["quality_domains"], "legacy_id": row["legacy_id"],
                                "standard_refs": row["standard_refs"],
                                "decision_state": "unreviewed"},
                    created_by=actor, updated_by=actor,
                )
                db.add(item); db.flush(); created += 1
            elif item.status == "candidate_review":
                attributes = dict(item.attributes or {})
                attributes.update(requirement_class=row["requirement_class"],
                                  quality_domains=row["quality_domains"],
                                  standard_refs=row["standard_refs"], legacy_id=row["legacy_id"])
                item.attributes = attributes
            if row["legacy_id"]:
                by_legacy.setdefault(row["legacy_id"], []).append(item)
            evidence_uri = f'doc://Dokumentation/{row["source"]}#L{row["source_line"]}'
            exists = db.query(GrcEvidence).filter_by(item_id=item.id, uri=evidence_uri, sha256=row["source_sha256"]).first()
            if not exists:
                db.add(GrcEvidence(
                    item_id=item.id, evidence_type="requirement_source", title="Kravkilde",
                    uri=evidence_uri, sha256=row["source_sha256"],
                    content={"line": row["source_line"], "excerpt": row["description"]},
                    collected_by=actor, retention_class="grc_source_permanent",
                )); evidence_created += 1
        for legacy_id, items in by_legacy.items():
            unique = {item.id: item for item in items}
            variants = list(unique.values())
            if len(variants) < 2 or len({clean(item.title).casefold() for item in variants}) < 2:
                continue
            for left, right in zip(variants, variants[1:]):
                if not db.query(GrcLink).filter_by(source_item_id=left.id, target_item_id=right.id,
                                                   relationship="requires_decision_review").first():
                    db.add(GrcLink(source_item_id=left.id, target_item_id=right.id,
                                   relationship="requires_decision_review",
                                   rationale=f"Genbrugt legacy-ID {legacy_id} med forskellig formulering",
                                   created_by=actor)); conflict_links += 1
        db.commit()
        return {"created": created, "evidence_created": evidence_created,
                "decision_review_links": conflict_links, "candidates": len(rows)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=Path, default=ROOT / "Dokumentation")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--actor", default="grc-importer")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = candidates(args.documents)
    summary = apply(rows, args.actor) if args.apply else {
        "mode": "dry_run", "candidates": len(rows),
        "functional": sum(row["requirement_class"] == "functional" for row in rows),
        "non_functional": sum(row["requirement_class"] == "non_functional" for row in rows),
        "sources": sorted({row["source"] for row in rows}),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else summary)


if __name__ == "__main__":
    main()
