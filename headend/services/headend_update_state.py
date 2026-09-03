"""State helpers for Headend-managed update installs."""

from sqlalchemy.orm import Session

from database import ChangeTicket, PendingUpdate, UpdateTarget, now_utc


def mark_headend_update_deployed(db: Session, update: PendingUpdate) -> None:
    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).order_by(ChangeTicket.created_at.desc()).first()
    if ticket and ticket.status == "approved":
        ticket.status = "deployed"
        ticket.updated_at = now_utc()
    db.query(UpdateTarget).filter_by(pending_update_id=update.id).update({
        "status": "deployed",
        "completed_at": now_utc(),
        "last_report_at": now_utc(),
        "last_error": None,
    }, synchronize_session=False)


def mark_headend_update_failed(db: Session, update: PendingUpdate, error: Exception, failure_evidence: str) -> None:
    update.status = "blocked"
    update.resolution_reason = str(error)[:500]
    ticket = db.query(ChangeTicket).filter_by(pending_update_id=update.id).order_by(ChangeTicket.created_at.desc()).first()
    if ticket and ticket.status == "approved":
        ticket.status = "cancelled"
        ticket.updated_at = now_utc()
        ticket.summary = ((ticket.summary or "").rstrip() + failure_evidence)[-6000:]
    db.query(UpdateTarget).filter_by(pending_update_id=update.id).update({
        "status": "failed",
        "completed_at": now_utc(),
        "last_report_at": now_utc(),
        "last_error": str(error)[:1000],
    }, synchronize_session=False)
