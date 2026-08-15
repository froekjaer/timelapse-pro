"""Technician EdgeServiceGrant helpers for WP-2."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from database import EdgeServiceGrant
from trust.grants import issue_edge_service_grant
from trust.models import GrantRequest
from trust.policy import principal_from_legacy_user


def issue_technician_service_grant(db: Session, *, user, edge_id: str, session_id: str, ttl_seconds: int):
    return issue_edge_service_grant(db, GrantRequest(
        principal=principal_from_legacy_user(user, mfa_verified=True),
        edge_id=edge_id,
        tenant_id=str(user.customer_id) if getattr(user, "customer_id", None) else None,
        resource=f"edge:{edge_id}:local-service",
        purpose="local technician service",
        capabilities=frozenset({"edge.service.local_view"}),
        ttl_seconds=ttl_seconds,
        mfa_required=True,
        context={"technician_auth_session_id": session_id},
    ))


def confirm_technician_auth_session(db: Session, *, user, session: dict, edge_id: str, session_id: str, callback_secret: str) -> dict:
    ttl_seconds = max(60, min(900, int(session.get("expires_at", time.time()) - time.time())))
    grant, row = issue_technician_service_grant(
        db, user=user, edge_id=edge_id, session_id=session_id, ttl_seconds=ttl_seconds,
    )
    session.update({
        "status": "confirmed",
        "technician_user_id": str(user.id),
        "technician_username": user.username,
        "technician_role": user.role,
        "technician_customer_id": str(user.customer_id) if getattr(user, "customer_id", None) else None,
        "confirmed_at": time.time(),
        "edge_token": callback_secret,
        "edge_service_grant": grant,
        "edge_service_grant_id": row.grant_id,
        "edge_service_grant_expires_at": row.expires_at.isoformat(),
    })
    return {
        "ok": True,
        "edge_token": callback_secret,
        "edge_service_grant_id": row.grant_id,
        "edge_service_grant_expires_at": row.expires_at.isoformat(),
        "edge_callback_url": "/api/technician/auth/callback",
    }


def edge_service_grant_status_snapshot(db: Session, edge_id: str) -> list[dict]:
    grants = (
        db.query(EdgeServiceGrant)
        .filter_by(edge_id=edge_id)
        .order_by(EdgeServiceGrant.issued_at.desc())
        .limit(25)
        .all()
    )
    return [
        {
            "grant_id": grant.grant_id,
            "status": grant.status,
            "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
            "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        }
        for grant in grants
    ]
