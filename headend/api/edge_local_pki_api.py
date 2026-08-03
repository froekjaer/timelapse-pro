"""RBAC-protected lifecycle endpoints for local Edge TLS trust."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from database import get_db
from services.edge_local_pki import (
    build_apple_ca_profile,
    ensure_local_edge_ca,
    local_edge_ca_status,
)


def create_edge_local_pki_router(
    require_role: Callable,
    record_siem_events: Callable,
    now_utc: Callable,
) -> APIRouter:
    """Expose a deliberately small CA lifecycle surface.

    Private keys never leave the Headend through this API. Issuing happens only
    in the privileged image builder, where the leaf key goes directly into the
    encrypted-at-rest Edge image artifact.
    """
    router = APIRouter(prefix="/api/admin/edge-local-ca", tags=["edge-local-ca"])

    @router.get("/status")
    def status(_user=require_role("admin")):
        return local_edge_ca_status()

    @router.post("/initialize")
    def initialize(
        user=require_role("super_admin"),
        db: Session = Depends(get_db),
    ):
        before = local_edge_ca_status()
        ensure_local_edge_ca()
        after = local_edge_ca_status()
        if not after.get("healthy"):
            raise HTTPException(status_code=500, detail=str(after.get("detail")))
        record_siem_events(db, "HEADEND", [{
            "event_type": "edge_local_ca_initialized" if not before.get("initialized") else "edge_local_ca_verified",
            "severity": "warning" if not before.get("initialized") else "info",
            "username": user.username,
            "source": "admin_api",
            "raw_message": "Edge Local CA initialiseret" if not before.get("initialized") else "Edge Local CA verificeret",
            "occurred_at": now_utc().isoformat(),
        }])
        db.commit()
        return after

    @router.get("/apple-profile")
    def apple_profile(user=require_role("viewer")):
        # A normal field technician may install the public CA profile only when
        # explicitly granted the on-site service capability. The root private
        # key and Edge leaf keys are never returned.
        if not bool(getattr(user, "on_site_service", False)) and user.role not in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="On-site idriftsættelse og service kræves")
        try:
            profile = build_apple_ca_profile()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(
            content=profile,
            media_type="application/x-apple-aspen-config",
            headers={
                "Content-Disposition": "attachment; filename=TimeLapse-Pro-Edge-Local-CA.mobileconfig",
                "Cache-Control": "no-store",
            },
        )

    return router
