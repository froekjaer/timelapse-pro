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

import logging

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Device, BreakGlassAccount, now_utc
from cmdb import report_inventory as _cmdb_report_inventory, _decrypt as _bg_decrypt
from siem import ingest_events as _siem_ingest_events
from technician_keys import resolve_authorized_technician_keys

log = logging.getLogger(__name__)
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
    break_glass_payload = []
    if device:
        security = req.diagnostics.get("security") if isinstance(req.diagnostics, dict) else None
        if isinstance(security, dict) and security.get("servicetekniker_login_seen"):
            device.servicetekniker_verified_at = now_utc()

        # Break-glass password delivery (2026-08-25): the circularity Peter
        # accepted — a password can't be pushed to an unreachable device, so
        # it's delivered on the device's own next successful sync instead of
        # an out-of-band push. See headend/cmdb.py::checkout_break_glass()
        # and edge/agent.py::_apply_break_glass_password().
        #
        # 2026-08-25 incident: an undecryptable account.password_enc (pre-
        # dating the currently-configured BREAK_GLASS_ENC_KEY, likely from a
        # long-ago key rotation) took down sync for every device for ~10
        # minutes — one bad row, no try/except, crashed the whole endpoint.
        # Never again: every account is handled independently; one failure
        # is logged and skipped, not fatal to this device's sync or anyone
        # else's.
        try:
            pending_accounts = db.query(BreakGlassAccount).filter_by(
                device_id=device_id, is_active=True, applied_at=None,
            ).all()
        except Exception as exc:
            log.error("Break-glass konto-opslag fejlede for %s: %s", device_id, exc)
            pending_accounts = []

        decrypted = {}
        for account in pending_accounts:
            try:
                decrypted[account.id] = _bg_decrypt(account.password_enc)
            except Exception as exc:
                log.error(
                    "Break-glass password kunne ikke dekrypteres (id=%s device=%s) — "
                    "springer over, sync fortsætter: %s", account.id, device_id, exc,
                )
        break_glass_payload = [
            {"username": a.ssh_username or "emergency", "password": decrypted[a.id]}
            for a in pending_accounts if a.id in decrypted
        ]

        applied_reports = (
            security.get("break_glass_applied") if isinstance(security, dict) else None
        ) or []
        if applied_reports and decrypted:
            import hashlib
            reported = {
                (str(r.get("username") or ""), str(r.get("password_sha256") or ""))
                for r in applied_reports if isinstance(r, dict)
            }
            for account in pending_accounts:
                if account.id not in decrypted:
                    continue
                digest = hashlib.sha256(decrypted[account.id].encode("utf-8")).hexdigest()
                if (account.ssh_username or "emergency", digest) in reported:
                    account.applied_at = now_utc()

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
        "break_glass": break_glass_payload,
    }
