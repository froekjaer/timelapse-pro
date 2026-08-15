"""Trust Service audit helpers."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from database import TrustPolicyDecisionAudit, now_utc
from .models import PolicyDecision, PolicyRequest


def record_policy_decision(db: Session, request: PolicyRequest, decision: PolicyDecision) -> TrustPolicyDecisionAudit:
    row = TrustPolicyDecisionAudit(
        decision_id=decision.decision_id or f"TLP-PDP-{uuid.uuid4().hex[:16]}",
        principal=request.principal.username,
        role=request.principal.role,
        tenant_id=request.tenant_id,
        resource=request.resource,
        action=request.action,
        capability=request.capability,
        allowed=bool(decision.allowed),
        reason=decision.reason,
        context_json=json.dumps(request.context or {}, ensure_ascii=False, sort_keys=True),
        decided_at=now_utc(),
    )
    db.add(row)
    return row
