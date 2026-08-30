"""Post-restart update health reconciliation."""
from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from database import PendingUpdate, UpdateTarget, now_utc


def sweep_stale_post_restart_update_handshakes(db: Session, *, timeout_s: int = 1800) -> int:
    """Mark updates failed when an Edge disappears after requesting restart."""
    cutoff = now_utc() - timedelta(seconds=max(60, int(timeout_s)))
    stale_targets = (
        db.query(UpdateTarget)
        .filter(UpdateTarget.status == "installing")
        .filter(UpdateTarget.last_report_at.isnot(None))
        .filter(UpdateTarget.last_report_at < cutoff)
        .all()
    )
    changed = 0
    for target in stale_targets:
        try:
            report = json.loads(target.report_json or "{}")
        except Exception:
            report = {}
        reason = str(report.get("reason") or "")
        health = report.get("post_restart_health") if isinstance(report, dict) else None
        if "awaiting_post_restart_health" not in reason and not isinstance(health, dict):
            continue

        update = db.query(PendingUpdate).filter_by(id=target.pending_update_id).first()
        if not update or update.status not in {"approved", "pending"}:
            continue

        message = "post_restart_health_handshake_missing"
        detected_at = now_utc()
        target.status = "failed"
        target.last_error = message
        target.completed_at = detected_at
        target.report_json = json.dumps(
            {
                **report,
                "status": "failed",
                "reason": message,
                "headend_detected_at": detected_at.isoformat(),
            },
            ensure_ascii=False,
        )
        update.failed_count = (update.failed_count or 0) + 1
        if (update.scope or "device") == "device":
            update.status = "blocked"
        update.description = ((update.description or "").rstrip() + (
            f"\n\nHeadend {detected_at.isoformat()}: {message} for {target.device_id}"
        ))[-6000:]
        changed += 1

    if changed:
        db.commit()
    return changed
