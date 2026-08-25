# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — edge_sync.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Consolidated Edge<->Headend poll.

Montér i main.py:
    from edge_sync import router as edge_sync_router
    app.include_router(edge_sync_router, prefix="/api/edge")

Endpoints:
    POST /api/edge/sync/{device_id}

Before 2026-08-19, Edge ran three independently-timed loops that each made
their own HTTP round-trip: a 5-minute config/update-check poll, a 60-minute
heartbeat, and a 5-minute SIEM-log forward — plus a 24-hour inventory report
nested inside the heartbeat. Each grew in isolation and none of them talked
to each other; the heartbeat in particular never even carried an app_version,
so Headend's own app-update auto-detection could never fire from real device
traffic (see Dokumentation/HANDOVER_LOG.md 2026-08-19).

This endpoint replaces all of the above with one request/response per poll
cycle. It does not reimplement any of their business logic — it composes the
existing, already-tested handlers (heartbeat, get_config, get_update_policy,
siem.ingest_events, cmdb.report_inventory) by calling them directly as plain
functions, after verifying the device token exactly once. The old endpoints
are left in place unchanged as a rollback path: a device that has to roll
back to a pre-2026-08-19 artifact must keep working against them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Device, now_utc
from cmdb import report_inventory as _cmdb_report_inventory
from siem import ingest_events as _siem_ingest_events
from technician_keys import resolve_authorized_technician_keys

router = APIRouter(tags=["Edge Sync"])


class EdgeSyncRequest(BaseModel):
    timestamp: str
    diagnostics: dict
    capture_stats: dict = {}
    ip_address: str | None = None
    siem_events: list = []
    inventory: dict | None = None


async def _require_edge_sync_auth(
    device_id: str,
    request: Request,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    """Reuses the same device-Bearer-token verification as every other
    edge-vendte endpoint (main._verify_device_token) — same HMAC/attestation
    chain, no separate trust model for the consolidated sync poll. Lazy
    import: main.py imports this module at load time, so importing main at
    module scope here would be circular. Same idiom as siem._require_device_auth.
    """
    from main import _verify_device_token

    await _verify_device_token(device_id=device_id, request=request, authorization=authorization, db=db)


@router.post("/sync/{device_id}")
async def edge_sync(
    device_id: str,
    req: EdgeSyncRequest,
    _auth: None = Depends(_require_edge_sync_auth),
    db: Session = Depends(get_db),
):
    # Lazy import: main.py imports this module at load time, so importing
    # main here at module scope would be a circular import.
    from main import HeartbeatRequest, get_config, get_update_policy, heartbeat

    hb_result = heartbeat(
        device_id,
        HeartbeatRequest(
            device_id=device_id,
            timestamp=req.timestamp,
            diagnostics=req.diagnostics,
            capture_stats=req.capture_stats,
            ip_address=req.ip_address,
        ),
        _auth=None,
        db=db,
    )

    if req.siem_events:
        await _siem_ingest_events(device_id, {"events": req.siem_events}, _auth=None, db=db)

    if req.inventory:
        _cmdb_report_inventory(device_id=device_id, payload=req.inventory, db=db)

    cfg = get_config(device_id, _auth=None, db=db)
    policy = get_update_policy(device_id, _auth=None, db=db)
    device = db.query(Device).filter_by(device_id=device_id).first()
    technician_keys = resolve_authorized_technician_keys(db, device) if device else []

    # Commissioning-key disable lifecycle (2026-08-24): the edge reports
    # whether it just saw a successful servicetekniker publickey login in
    # its own sshd journal — that's the verify-before-disable evidence the
    # admin UI's "disable commissioning key" action gates on. See
    # Dokumentation/HANDOVER_LOG.md and headend/main.py's
    # /api/admin/devices/{device_id}/commissioning-key endpoints.
    if device:
        security = req.diagnostics.get("security") if isinstance(req.diagnostics, dict) else None
        if isinstance(security, dict) and security.get("servicetekniker_login_seen"):
            device.servicetekniker_verified_at = now_utc()
            db.commit()

    return {
        "server_time": hb_result["server_time"],
        "config_version": hb_result["config_version"],
        "config": cfg,
        "pending_updates": policy.get("pending_updates", []),
        "app_security": policy.get("app_security"),
        "app_updates": policy.get("app_updates"),
        "technician_keys": technician_keys,
        "commissioning_key_disabled": bool(device.commissioning_key_disabled) if device else False,
    }
