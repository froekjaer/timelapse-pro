"""Authoritative GRC register API.

Markdown and generated reports are exports. PostgreSQL rows are the source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import (
    GrcComment, GrcDocument, GrcDocumentItemLink, GrcDocumentRevision, GrcEvidence,
    GrcItem, GrcLink, GrcTestRun, get_db,
)


router = APIRouter(prefix="/api/grc/register", tags=["GRC Register"])
ITEM_TYPES = {"requirement", "control", "risk", "test", "finding", "action"}
WRITE_ROLES = {"admin", "super_admin"}


def _current_viewer(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    return user


def _require_platform_admin(user=Depends(_current_viewer)):
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
    item_type: str | None = None, status: str | None = None, search: str | None = None,
    _user=Depends(_current_viewer), db: Session = Depends(get_db),
):
    query = db.query(GrcItem)
    if item_type:
        if item_type not in ITEM_TYPES:
            raise HTTPException(status_code=422, detail="Ukendt GRC-objekttype")
        query = query.filter(GrcItem.item_type == item_type)
    if status:
        query = query.filter(GrcItem.status == status)
    if search and search.strip():
        needle = f"%{search.strip()[:200]}%"
        query = query.filter(or_(GrcItem.external_id.ilike(needle), GrcItem.title.ilike(needle),
                                 GrcItem.description.ilike(needle), GrcItem.source.ilike(needle)))
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
def create_item(payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
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


def _comment(row: GrcComment) -> dict:
    return {"id": row.id, "item_id": row.item_id, "body": row.body,
            "created_by": row.created_by, "created_at": row.created_at.isoformat()}


@router.get("/{item_id}/comments")
def list_comments(item_id: int, _user=Depends(_current_viewer), db: Session = Depends(get_db)):
    if not db.query(GrcItem).filter_by(id=item_id).first():
        raise HTTPException(status_code=404, detail="GRC-objekt ikke fundet")
    rows = db.query(GrcComment).filter_by(item_id=item_id).order_by(GrcComment.created_at).all()
    return {"comments": [_comment(row) for row in rows]}


@router.post("/{item_id}/comments")
def add_comment(item_id: int, payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    if not db.query(GrcItem).filter_by(id=item_id).first():
        raise HTTPException(status_code=404, detail="GRC-objekt ikke fundet")
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=422, detail="Kommentaren må ikke være tom")
    if len(body) > 10000:
        raise HTTPException(status_code=422, detail="Kommentaren er for lang")
    row = GrcComment(item_id=item_id, body=body, created_by=user.username)
    db.add(row); db.commit(); db.refresh(row)
    return _comment(row)


@router.patch("/{item_id}")
def update_item(item_id: int, payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
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
def record_test_run(item_id: int, payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
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
def add_evidence(item_id: int, payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
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
def bootstrap_canonical_v1(user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
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


@router.get("/reports/{report_type}")
def generate_report(report_type: str, _user=Depends(_current_viewer), db: Session = Depends(get_db)):
    allowed = {"full", "requirements", "tests", "risks", "findings"}
    if report_type not in allowed:
        raise HTTPException(status_code=404, detail="Ukendt GRC-rapport")
    type_map = {"requirements": "requirement", "tests": "test", "risks": "risk", "findings": "finding"}
    query = db.query(GrcItem)
    if report_type != "full":
        query = query.filter(GrcItem.item_type == type_map[report_type])
    items = query.order_by(GrcItem.item_type, GrcItem.external_id).all()
    now = datetime.now(timezone.utc)
    lines = [f"# TimeLapse Pro GRC report - {report_type}", "",
             f"Generated: {now.isoformat()}", "Source of truth: PostgreSQL", "",
             "| Type | ID | Title | Status | Priority | Owner | Version |", "|---|---|---|---|---|---|---|"]
    for row in items:
        title = (row.title or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.item_type} | {row.external_id} | {title} | {row.status} | {row.priority or '-'} | {row.owner or '-'} | {row.version} |")
    lines.extend(["", "## Control statement", "",
                  "This report is generated from the operational GRC register. It is not a certification claim."])
    content = "\n".join(lines) + "\n"
    return PlainTextResponse(content, media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="timelapse-grc-{report_type}-{now.date()}.md"'})


@router.get("/reports/standard/{standard}")
def generate_standard_report(standard: str, _user=Depends(_current_viewer), db: Session = Depends(get_db)):
    standard_id = standard.upper()
    allowed = {"SABSA", "COBIT", "ISO27001", "IEC62443", "NIS2", "CRA", "GDPR", "AI-ACT", "NIST", "ENISA"}
    if standard_id not in allowed:
        raise HTTPException(status_code=404, detail="Ukendt standardreference")
    requirements = [row for row in db.query(GrcItem).filter_by(item_type="requirement").all()
                    if standard_id in (row.attributes or {}).get("standard_refs", [])]
    controls = [row for row in db.query(GrcItem).filter_by(item_type="control").all()
                if standard_id in (row.attributes or {}).get("standard_refs", [])]
    now = datetime.now(timezone.utc)
    lines = [f"# TimeLapse Pro GRC mapping - {standard_id}", "",
             f"Generated: {now.isoformat()}", "Source of truth: PostgreSQL", "",
             "> Engineering mapping only. This is not a complete audit, legal opinion or certification claim.", "",
             f"Mapped requirements: {len(requirements)}", f"Mapped controls: {len(controls)}", "",
             "| ID | Type | Statement | Status | Source |", "|---|---|---|---|---|"]
    for row in sorted(requirements + controls, key=lambda value: value.external_id):
        title = (row.title or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.external_id} | {row.item_type} | {title} | {row.status} | {row.source or '-'} |")
    content = "\n".join(lines) + "\n"
    return PlainTextResponse(content, media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="timelapse-grc-{standard_id.lower()}-{now.date()}.md"'})


def _revision(row: GrcDocumentRevision) -> dict:
    return {
        "id": row.id, "revision": row.revision, "status": row.lifecycle_status,
        "content_sha256": row.content_sha256, "grc_snapshot_sha256": row.grc_snapshot_sha256,
        "generator": row.generator, "change_summary": row.change_summary,
        "created_by": row.created_by, "created_at": row.created_at.isoformat(),
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
    }


@router.get("/documents")
def list_documents(_user=Depends(_current_viewer), db: Session = Depends(get_db)):
    documents = []
    for document in db.query(GrcDocument).order_by(GrcDocument.document_id).all():
        revisions = (db.query(GrcDocumentRevision).filter_by(document_id=document.id)
                     .order_by(GrcDocumentRevision.revision.desc()).all())
        documents.append({
            "id": document.id, "document_id": document.document_id, "title": document.title,
            "document_type": document.document_type, "status": document.status,
            "owner": document.owner, "approver_role": document.approver_role,
            "classification": document.classification,
            "revisions": [_revision(row) for row in revisions],
        })
    return {"source_of_truth": "postgresql", "documents": documents}


@router.post("/documents/from-report/{report_type}")
def save_report_revision(
    report_type: str, payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db),
):
    if report_type not in {"full", "requirements", "tests", "risks", "findings"}:
        raise HTTPException(status_code=404, detail="Ukendt GRC-rapport")
    response = generate_report(report_type, _user=user, db=db)
    content = bytes(response.body).decode("utf-8")
    relevant_type = {"requirements": "requirement", "tests": "test", "risks": "risk", "findings": "finding"}.get(report_type)
    query = db.query(GrcItem)
    if relevant_type:
        query = query.filter(GrcItem.item_type == relevant_type)
    items = query.order_by(GrcItem.item_type, GrcItem.external_id).all()
    snapshot_material = [{"id": row.id, "version": row.version, "status": row.status} for row in items]
    snapshot_sha = hashlib.sha256(json.dumps(snapshot_material, sort_keys=True).encode()).hexdigest()
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    stable_id = f"TLP-GRC-{report_type.upper()}"
    document = db.query(GrcDocument).filter_by(document_id=stable_id).with_for_update().first()
    if not document:
        document = GrcDocument(
            document_id=stable_id, title=f"TimeLapse Pro GRC {report_type}",
            document_type=f"grc_{report_type}", status="draft", owner=user.username,
            created_by=user.username,
        )
        db.add(document); db.flush()
    latest = db.query(func.max(GrcDocumentRevision.revision)).filter_by(document_id=document.id).scalar() or 0
    # Rendered reports include a generation timestamp, so their content hash
    # changes even when the authoritative GRC data has not changed. Revision
    # identity follows the snapshot; content_sha256 still proves exact bytes.
    existing = db.query(GrcDocumentRevision).filter_by(
        document_id=document.id, grc_snapshot_sha256=snapshot_sha,
    ).first()
    if existing:
        return {"status": "unchanged", "document_id": stable_id, "revision": _revision(existing)}
    revision = GrcDocumentRevision(
        document_id=document.id, revision=latest + 1, lifecycle_status="draft",
        content_sha256=content_sha, content=content,
        source_uri=f"grc://reports/{report_type}", generator="timelapse.grc.report.v1",
        grc_snapshot_sha256=snapshot_sha,
        change_summary=str(payload.get("change_summary") or "Generated from current GRC snapshot")[:4000],
        created_by=user.username,
    )
    db.add(revision); db.flush()
    for item in items:
        db.add(GrcDocumentItemLink(revision_id=revision.id, item_id=item.id, relationship="included"))
    document.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(revision)
    return {"status": "created", "document_id": stable_id, "revision": _revision(revision)}


@router.post("/documents/{document_id}/revisions/{revision_id}/approve")
def approve_revision(
    document_id: str, revision_id: int, user=Depends(_require_platform_admin), db: Session = Depends(get_db),
):
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Dokumentgodkendelse kræver super_admin")
    document = db.query(GrcDocument).filter_by(document_id=document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Dokument ikke fundet")
    revision = db.query(GrcDocumentRevision).filter_by(id=revision_id, document_id=document.id).with_for_update().first()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision ikke fundet")
    if revision.lifecycle_status == "approved":
        return {"status": "unchanged", "revision": _revision(revision)}
    revision.lifecycle_status = "approved"
    revision.approved_by = user.username
    revision.approved_at = datetime.now(timezone.utc)
    document.status = "approved"
    document.updated_at = revision.approved_at
    db.commit(); db.refresh(revision)
    return {"status": "approved", "revision": _revision(revision)}
