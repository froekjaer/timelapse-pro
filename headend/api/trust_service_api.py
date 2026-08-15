"""WP-2 TimeLapse Trust Service admin API."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from trust.dmz import SECURE_SERVICE_DMZ_SPEC
from trust.grants import GrantDenied, issue_edge_service_grant, revoke_edge_service_grant
from trust.models import GrantRequest, Principal


class EdgeServiceGrantPayload(BaseModel):
    edge_id: str
    tenant_id: str | None = None
    resource: str
    purpose: str
    capabilities: list[str]
    ttl_seconds: int = 900
    mfa_required: bool = True


class RevokeGrantPayload(BaseModel):
    reason: str


def create_trust_service_router(require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/admin/trust", tags=["trust-service"])

    @router.get("/dmz-spec")
    def get_dmz_spec(_user=require_role("admin")):
        return SECURE_SERVICE_DMZ_SPEC

    @router.post("/edge-service-grants")
    def create_edge_service_grant(
        payload: EdgeServiceGrantPayload,
        user=require_role("admin"),
        db: Session = Depends(get_db),
    ):
        principal = Principal(
            username=user.username,
            role=user.role,
            user_id=user.id,
            tenant_id=user.customer_id,
            capabilities=frozenset({"edge.service.local_view"} if getattr(user, "on_site_service", False) else set()),
            mfa_verified=True,
        )
        try:
            token, row = issue_edge_service_grant(db, GrantRequest(
                principal=principal,
                edge_id=payload.edge_id,
                tenant_id=payload.tenant_id or user.customer_id,
                resource=payload.resource,
                purpose=payload.purpose,
                capabilities=frozenset(payload.capabilities),
                ttl_seconds=payload.ttl_seconds,
                mfa_required=payload.mfa_required,
            ))
        except GrantDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        db.commit()
        return {"grant_id": row.grant_id, "token_once": token, "expires_at": row.expires_at.isoformat()}

    @router.post("/edge-service-grants/{grant_id}/revoke")
    def revoke_grant(
        grant_id: str,
        payload: RevokeGrantPayload,
        user=require_role("admin"),
        db: Session = Depends(get_db),
    ):
        try:
            row = revoke_edge_service_grant(db, grant_id, actor=user.username, reason=payload.reason)
        except GrantDenied as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        db.commit()
        return {"grant_id": row.grant_id, "status": row.status}

    return router
