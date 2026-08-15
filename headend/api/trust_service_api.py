"""WP-2 TimeLapse Trust Service admin API."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Device, get_db
from trust.dmz import SECURE_SERVICE_DMZ_SPEC
from trust.grants import (
    GrantDenied,
    TrustServiceConfigurationError,
    issue_edge_service_grant,
    revoke_edge_service_grant,
)
from trust.models import GrantRequest
from trust.policy import principal_from_legacy_user


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


def _resolve_edge_tenant(db: Session, *, edge_id: str, requested_tenant: str | None, user) -> str | None:
    """Bind a grant request to the actual Edge owner and caller tenant."""
    edge = db.query(Device).filter_by(device_id=edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")

    edge_tenant = str(edge.customer_id) if getattr(edge, "customer_id", None) else None
    caller_tenant = str(user.customer_id) if getattr(user, "customer_id", None) else None
    requested = str(requested_tenant) if requested_tenant else caller_tenant or edge_tenant

    if caller_tenant and edge_tenant and caller_tenant != edge_tenant:
        raise HTTPException(status_code=403, detail="Edge tenant boundary denied")
    if requested and edge_tenant and requested != edge_tenant:
        raise HTTPException(status_code=403, detail="Requested tenant does not own Edge")
    if caller_tenant and requested and caller_tenant != requested:
        raise HTTPException(status_code=403, detail="Caller tenant boundary denied")
    return requested


def _validate_edge_resource(edge_id: str, resource: str) -> None:
    """A grant for one Edge cannot carry a resource string for another Edge."""
    if not resource.startswith(f"edge:{edge_id}:"):
        raise HTTPException(status_code=400, detail="Grant resource must be bound to requested Edge")


def create_trust_service_router(require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/admin/trust", tags=["trust-service"])

    @router.get("/dmz-spec")
    def get_dmz_spec(_user=require_role("admin")):
        return SECURE_SERVICE_DMZ_SPEC

    @router.post("/edge-service-grants")
    def create_edge_service_grant(
        payload: EdgeServiceGrantPayload,
        request: Request,
        user=require_role("admin"),
        db: Session = Depends(get_db),
    ):
        # Use the actual authenticated session's AMR/MFA evidence. Never claim
        # MFA merely because the endpoint requires an admin role.
        from main import _session_is_mfa_verified, _session_payload

        mfa_verified = _session_is_mfa_verified(_session_payload(request))
        tenant_id = _resolve_edge_tenant(
            db,
            edge_id=payload.edge_id,
            requested_tenant=payload.tenant_id,
            user=user,
        )
        _validate_edge_resource(payload.edge_id, payload.resource)
        principal = principal_from_legacy_user(user, mfa_verified=mfa_verified)
        try:
            token, row = issue_edge_service_grant(
                db,
                GrantRequest(
                    principal=principal,
                    edge_id=payload.edge_id,
                    tenant_id=tenant_id,
                    resource=payload.resource,
                    purpose=payload.purpose,
                    capabilities=frozenset(payload.capabilities),
                    ttl_seconds=payload.ttl_seconds,
                    mfa_required=payload.mfa_required,
                    context={"mfa_evidence": "headend_session_amr" if mfa_verified else "not_verified"},
                ),
            )
        except GrantDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except TrustServiceConfigurationError as exc:
            # Missing signing authority is an operational/configuration failure,
            # not an authorization denial. Fail closed without issuing a token.
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        db.commit()
        return {
            "grant_id": row.grant_id,
            # Compatibility field; this is a short-lived bearer grant, not a
            # mathematically one-use token. Replay protection applies to each
            # technician challenge during validation.
            "token_once": token,
            "expires_at": row.expires_at.isoformat(),
            "mfa_verified": row.mfa_verified,
        }

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
