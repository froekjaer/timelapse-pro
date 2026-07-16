#!/usr/bin/env python3
"""Idempotently migrate current risk, health finding and ADR sources to GRC."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "headend"))

from database import GrcEvidence, GrcItem, SessionLocal  # noqa: E402


def source(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes()
    return raw.decode("utf-8", errors="replace").splitlines(), hashlib.sha256(raw).hexdigest()


def upsert(db, *, item_type: str, external_id: str, title: str, status: str,
           priority: str | None, source_path: Path, line: int, attributes: dict, actor: str) -> tuple[GrcItem, bool]:
    item = db.query(GrcItem).filter_by(item_type=item_type, external_id=external_id).first()
    created = False
    if not item:
        item = GrcItem(item_type=item_type, external_id=external_id, title=title[:300],
                       status=status, priority=priority, source=f"{source_path.name}:{line}",
                       scope={"product": "timelapse-pro"}, attributes=attributes,
                       created_by=actor, updated_by=actor)
        db.add(item); db.flush(); created = True
    return item, created


def evidence(db, item: GrcItem, path: Path, line: int, digest: str, excerpt: str, actor: str) -> bool:
    uri = f"doc://Dokumentation/{path.relative_to(ROOT / 'Dokumentation')}#L{line}"
    if db.query(GrcEvidence).filter_by(item_id=item.id, uri=uri, sha256=digest).first():
        return False
    db.add(GrcEvidence(item_id=item.id, evidence_type="governance_source", title="Governance source",
                       uri=uri, sha256=digest, content={"line": line, "excerpt": excerpt},
                       collected_by=actor, retention_class="grc_source_permanent"))
    return True


def migrate(actor: str) -> dict:
    docs = ROOT / "Dokumentation"
    db = SessionLocal()
    created = evidence_count = 0
    try:
        for filename in ("RISK_ASSESSMENT_v10.md", "RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md"):
            path = docs / filename
            lines, digest = source(path)
            for idx, line in enumerate(lines, 1):
                match = re.match(r"^### (R\d+)\s+[—-]\s+(.+)$", line)
                if not match:
                    continue
                risk_id, title = match.groups()
                title = re.sub(r"\s*\((?:NY|new).*", "", title, flags=re.I).strip()
                nearby = " ".join(lines[idx - 1:min(idx + 12, len(lines))])
                score_match = re.search(r"(?:residual|score|risiko)[^0-9]{0,20}(\d{1,2})", nearby, re.I)
                score = int(score_match.group(1)) if score_match else None
                closed = bool(re.search(r"rettet|løst|closed", nearby, re.I)) and not bool(re.search(r"mangler|åben", nearby, re.I))
                inferred_state = "historically_mitigated" if closed else "historically_open"
                status = "candidate_review"
                priority = "P0" if score and score >= 12 else "P1" if score and score >= 8 else "P2"
                item, was_created = upsert(db, item_type="risk", external_id=risk_id, title=title,
                    status=status, priority=priority, source_path=path, line=idx,
                    attributes={"residual_score": score, "assessment_version": filename,
                                "inferred_historical_state": inferred_state,
                                "method": "document_migration_requires_owner_validation"}, actor=actor)
                if not was_created and item.source and item.source.startswith("RISK_ASSESSMENT_"):
                    attributes = dict(item.attributes or {})
                    attributes.update(residual_score=score, assessment_version=filename,
                                      inferred_historical_state=inferred_state,
                                      method="document_migration_requires_owner_validation")
                    item.attributes = attributes
                    item.status = "candidate_review"
                created += was_created
                evidence_count += evidence(db, item, path, idx, digest, line, actor)

        health = docs / "SYSTEM_HEALTH_REGISTER.md"
        lines, digest = source(health)
        for idx, line in enumerate(lines, 1):
            match = re.match(r"^### (HLTH-\d+)\s+-\s+(.+)$", line)
            if not match:
                continue
            finding_id, title = match.groups()
            nearby = " ".join(lines[idx - 1:min(idx + 14, len(lines))])
            severity = re.search(r"\*\*(?:Severity|Alvorlighed):\*\*\s*([^\n*]+)", nearby, re.I)
            severity_text = severity.group(1).strip() if severity else "unknown"
            status = "candidate_review"
            item, was_created = upsert(db, item_type="finding", external_id=finding_id, title=title,
                status=status, priority="P1", source_path=health, line=idx,
                attributes={"legacy_severity": severity_text, "decision_state": "validate_current_runtime"}, actor=actor)
            created += was_created
            evidence_count += evidence(db, item, health, idx, digest, line, actor)

        adr = docs / "ADR/ADR-001-platform-payload-split.md"
        lines, digest = source(adr)
        title = lines[0].removeprefix("# ").strip()
        item, was_created = upsert(db, item_type="control", external_id="ADR-001", title=title,
            status="accepted", priority="P0", source_path=adr, line=1,
            attributes={"control_type": "architecture_decision", "decision": "platform_payload_split",
                        "accepted_at": "2026-07-16", "supersession_policy": "new_ADR_required",
                        "trace_note": "Marks the explicit shift from single-purpose product architecture to modular platform/payload architecture."},
            actor=actor)
        created += was_created
        evidence_count += evidence(db, item, adr, 1, digest, lines[0], actor)
        db.commit()
        return {"created": created, "evidence_created": evidence_count}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--actor", default="grc-importer")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Dry-run only: pass --apply after reviewing this versioned importer")
    print(migrate(args.actor))
