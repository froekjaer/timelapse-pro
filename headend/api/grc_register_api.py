"""Authoritative GRC register API.

Markdown and generated reports are exports. PostgreSQL rows are the source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import GrcEvidence, GrcItem, GrcLink, GrcTestRun, get_db


router = APIRouter(prefix="/api/grc/register", tags=["GRC Register"])
ITEM_TYPES = {"requirement", "control", "risk", "test", "finding", "action"}
WRITE_ROLES = {"admin", "super_admin"}


def _current_user(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    return user


def _writer(user=Depends(_current_user)):
    if user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="GRC-ændringer kræver administrator")
    return user


def _item(row: GrcItem) -> dict:
    return {
        "id": row.id, "item_type": row.item_type, "external_id": row.external_id,
        "title": row.title, "description": row.description, "status": row.status,
        "priority": row.priority, "owner": row.owner,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "source": row.source, "scope": row.scope or {}, "attributes": row.attributes or {},
        "version": row.version, "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_by": row.updated_by, "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def list_register(
    item_type: str | None = None, status: str | None = None,
    _user=Depends(_current_user), db: Session = Depends(get_db),
):
    query = db.query(GrcItem)
    if item_type:
        if item_type not in ITEM_TYPES:
            raise HTTPException(status_code=422, detail="Ukendt GRC-objekttype")
        query = query.filter(GrcItem.item_type == item_type)
    if status:
        query = query.filter(GrcItem.status == status)
    rows = query.order_by(GrcItem.item_type, GrcItem.priority, GrcItem.external_id).all()
    counts = dict(db.query(GrcItem.item_type, func.count(GrcItem.id)).group_by(GrcItem.item_type).all())
    result_counts = dict(db.query(GrcTestRun.result, func.count(GrcTestRun.id)).group_by(GrcTestRun.result).all())
    open_findings = db.query(func.count(GrcItem.id)).filter(
        GrcItem.item_type == "finding", GrcItem.status.notin_(("closed", "accepted")),
    ).scalar() or 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_of_truth": "postgresql", "items": [_item(row) for row in rows],
        "summary": {"items": sum(counts.values()), "by_type": counts,
                    "test_results": result_counts, "open_findings": open_findings},
    }


@router.post("")
def create_item(payload: dict, user=Depends(_writer), db: Session = Depends(get_db)):
    item_type = str(payload.get("item_type") or "")
    if item_type not in ITEM_TYPES:
        raise HTTPException(status_code=422, detail="Ukendt GRC-objekttype")
    external_id = str(payload.get("external_id") or "").strip()[:100]
    title = str(payload.get("title") or "").strip()[:300]
    if not external_id or not title:
        raise HTTPException(status_code=422, detail="external_id og title er påkrævet")
    if db.query(GrcItem).filter_by(item_type=item_type, external_id=external_id).first():
        raise HTTPException(status_code=409, detail="GRC-ID findes allerede")
    row = GrcItem(
        item_type=item_type, external_id=external_id, title=title,
        description=str(payload.get("description") or "")[:10000] or None,
        status=str(payload.get("status") or "draft")[:30], priority=str(payload.get("priority") or "")[:10] or None,
        owner=str(payload.get("owner") or "")[:100] or None, source=str(payload.get("source") or "")[:300] or None,
        scope=payload.get("scope") if isinstance(payload.get("scope"), dict) else {},
        attributes=payload.get("attributes") if isinstance(payload.get("attributes"), dict) else {},
        created_by=user.username, updated_by=user.username,
    )
    db.add(row); db.commit(); db.refresh(row)
    return _item(row)


@router.patch("/{item_id}")
def update_item(item_id: int, payload: dict, user=Depends(_writer), db: Session = Depends(get_db)):
    row = db.query(GrcItem).filter_by(id=item_id).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="GRC-objekt ikke fundet")
    for field, limit in (("title", 300), ("description", 10000), ("status", 30),
                         ("priority", 10), ("owner", 100), ("source", 300)):
        if field in payload:
            setattr(row, field, str(payload[field] or "")[:limit] or None)
    for field in ("scope", "attributes"):
        if field in payload:
            if not isinstance(payload[field], dict):
                raise HTTPException(status_code=422, detail=f"{field} skal være et objekt")
            setattr(row, field, payload[field])
    row.version += 1; row.updated_by = user.username; row.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(row)
    return _item(row)


@router.post("/{item_id}/runs")
def record_test_run(item_id: int, payload: dict, user=Depends(_writer), db: Session = Depends(get_db)):
    test = db.query(GrcItem).filter_by(id=item_id, item_type="test").first()
    if not test:
        raise HTTPException(status_code=404, detail="Testcase ikke fundet")
    result = str(payload.get("result") or "").lower()
    if result not in {"pass", "fail", "blocked", "skipped"}:
        raise HTTPException(status_code=422, detail="Resultat skal være pass, fail, blocked eller skipped")
    now = datetime.now(timezone.utc)
    run = GrcTestRun(
        test_item_id=test.id, environment=str(payload.get("environment") or "test")[:30], result=result,
        started_at=now, completed_at=now, executed_by=user.username,
        release_ref=str(payload.get("release_ref") or "")[:150] or None,
        notes=str(payload.get("notes") or "")[:10000] or None,
        metrics=payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {},
    )
    db.add(run); test.status = "verified" if result == "pass" else result
    test.version += 1; test.updated_by = user.username; test.updated_at = now
    db.commit(); db.refresh(run)
    return {"id": run.id, "test_item_id": run.test_item_id, "result": run.result, "completed_at": run.completed_at.isoformat()}


@router.post("/{item_id}/evidence")
def add_evidence(item_id: int, payload: dict, user=Depends(_writer), db: Session = Depends(get_db)):
    if not db.query(GrcItem).filter_by(id=item_id).first():
        raise HTTPException(status_code=404, detail="GRC-objekt ikke fundet")
    content = payload.get("content") if isinstance(payload.get("content"), dict) else None
    digest = str(payload.get("sha256") or "").lower() or (
        hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest() if content else None
    )
    if digest and (len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)):
        raise HTTPException(status_code=422, detail="sha256 er ugyldig")
    row = GrcEvidence(
        item_id=item_id, evidence_type=str(payload.get("evidence_type") or "observation")[:40],
        title=str(payload.get("title") or "Evidens")[:300], uri=str(payload.get("uri") or "")[:1000] or None,
        sha256=digest, content=content, collected_by=user.username,
        retention_class=str(payload.get("retention_class") or "grc_standard")[:50],
    )
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "item_id": row.item_id, "sha256": row.sha256, "collected_at": row.collected_at.isoformat()}


SEED_ITEMS = (
    ("requirement", "GRC-REQ-001", "Alle tests, risici, fund og evidens skal have én autoritativ databasekilde", "implemented", "P0"),
    ("test", "TV-001", "CI-identisk unit og contract testgate", "verified", "P0"),
    ("test", "UI-ROUTES-001", "Alle beskyttede UI-routes renderer uden HTTP 500 eller login-loop", "verified", "P0"),
    ("test", "IT-G2", "Auth og RBAC integrationstest i isoleret testdatabase", "blocked", "P0"),
    ("test", "PROC-BKP-01", "Headend backup og scratch restore", "not_run", "P0"),
    ("test", "UI-UPD-06", "Signeret offline Edge OS update end-to-end", "not_run", "P0"),
    ("test", "UI-UPD-07", "Signeret Edge app rollback end-to-end", "not_run", "P1"),
    ("test", "UI-UPD-08", "Ollama update gennem Headend workflow", "not_run", "P1"),
    ("test", "TV-008", "mTLS, revocation og expiry policy", "not_run", "P1"),
    ("finding", "FIND-TEST-001", "Integration harness kan mutere operationel database", "open", "P0"),
    ("action", "ACT-TEST-001", "Gør integration harness fail-closed og kræv isoleret PostgreSQL", "in_progress", "P0"),
)


@router.post("/bootstrap/canonical-v1")
def bootstrap_canonical_v1(user=Depends(_writer), db: Session = Depends(get_db)):
    created = []
    for item_type, external_id, title, status, priority in SEED_ITEMS:
        row = db.query(GrcItem).filter_by(item_type=item_type, external_id=external_id).first()
        if row:
            continue
        row = GrcItem(item_type=item_type, external_id=external_id, title=title, status=status,
                      priority=priority, source="VERIFICATION_RISK_EVIDENCE_REGISTER_v1",
                      scope={"environment": "R&D"}, attributes={"import": "canonical-v1"},
                      created_by=user.username, updated_by=user.username)
        db.add(row); db.flush(); created.append(row.external_id)
    finding = db.query(GrcItem).filter_by(item_type="finding", external_id="FIND-TEST-001").first()
    action = db.query(GrcItem).filter_by(item_type="action", external_id="ACT-TEST-001").first()
    if finding and action and not db.query(GrcLink).filter_by(
        source_item_id=finding.id, target_item_id=action.id, relationship="remediated_by"
    ).first():
        db.add(GrcLink(source_item_id=finding.id, target_item_id=action.id,
                       relationship="remediated_by", created_by=user.username))
    db.commit()
    return {"status": "ok", "created": created, "existing": len(SEED_ITEMS) - len(created)}
