"""Tenant authority for update decisions (security remediation, 2026-10-10).

Role model (Peter, 2026-10-10): super_admin may decide across all customers;
admin and operator only for the customers they are attached to. An update row
is shared by every device it targets, so a decision on it is a decision for
all of them: every affected device — and the scope itself, which also covers
devices that appear later — must lie within the caller's customers. If any
part does not, the whole action is refused; there is no partial approval.

Customer membership comes from tenant_scope._allowed_customer_ids (the
central helper), never from a local reading of user.customer_id.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import Device, PendingUpdate, Site, UpdateTarget
from tenant_scope import _allowed_customer_ids

DECIDING_ROLES = {"admin", "operator"}
DENIED = "Opdateringen berører enheder eller kunder uden for din adgang"


def _site_customer(db: Session, site_id: str | None) -> str | None:
    if not site_id:
        return None
    site = db.query(Site).filter_by(id=site_id).first()
    return str(site.customer_id) if site and site.customer_id else None


def device_customer_ids(db: Session, device: Device) -> set[str]:
    """Every customer a device is bound to: its own and its site's."""
    found = {str(device.customer_id)} if device.customer_id else set()
    site_customer = _site_customer(db, device.site_id)
    if site_customer:
        found.add(site_customer)
    return found


def _device_allowed(db: Session, device: Device | None, allowed: set[str]) -> bool:
    if device is None:
        return False
    customers = device_customer_ids(db, device)
    return bool(customers) and customers <= allowed


def _scope_allowed(db: Session, update, allowed: set[str]) -> bool:
    """The scope covers future devices too, so it must itself be in bounds."""
    raw_ids = getattr(update, "target_device_ids", None)
    if raw_ids:
        try:
            ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids)
        except (TypeError, ValueError):
            return False
        devices = {d.device_id: d for d in db.query(Device).filter(Device.device_id.in_(ids)).all()}
        # An unknown id is refused: it could be another customer's future device.
        return bool(ids) and all(_device_allowed(db, devices.get(i), allowed) for i in ids)
    scope = str(getattr(update, "scope", None) or "device").strip().lower()
    scope_id = str(getattr(update, "scope_id", None) or "").strip()
    if scope == "customer":
        return scope_id in allowed
    if scope == "site":
        return _site_customer(db, scope_id) in allowed
    if scope == "device":
        return _device_allowed(db, db.query(Device).filter_by(device_id=scope_id).first(), allowed)
    return False   # "global" and anything unknown: super_admin only


def user_may_decide_update(db: Session, user, update, resolve_targets: Callable) -> bool:
    if user is None:
        return False
    if getattr(user, "role", None) == "super_admin":
        return True
    if getattr(user, "role", None) not in DECIDING_ROLES:
        return False
    allowed = _allowed_customer_ids(db, user)
    if allowed is None:
        return True
    if not allowed or not _scope_allowed(db, update, allowed):
        return False
    devices = list(resolve_targets(db, update))
    if getattr(update, "id", None) is not None:
        existing_ids = {t.device_id for t in db.query(UpdateTarget).filter_by(pending_update_id=update.id).all()}
        existing_ids -= {d.device_id for d in devices}
        if existing_ids:
            devices += db.query(Device).filter(Device.device_id.in_(existing_ids)).all()
            if len(devices) < len(existing_ids):   # a target row without a device record
                return False
    return all(_device_allowed(db, device, allowed) for device in devices)


def ensure_update_authority(db: Session, user, update, resolve_targets: Callable) -> None:
    if not user_may_decide_update(db, user, update, resolve_targets):
        raise HTTPException(status_code=403, detail=DENIED)


def ensure_ticket_authority(db: Session, user, ticket, resolve_targets: Callable) -> None:
    update = db.query(PendingUpdate).filter_by(id=ticket.pending_update_id).first() if ticket.pending_update_id else None
    if update is None:
        if getattr(user, "role", None) != "super_admin":
            raise HTTPException(status_code=403, detail=DENIED)
        return
    ensure_update_authority(db, user, update, resolve_targets)


def proposed_approval(update, scope: str | None, scope_id: str | None, target_ids, environment: str):
    """The update as approve_update() is about to rewrite it — checked before
    anything is written, so a refused approval leaves no trace."""
    fields = {c.name: getattr(update, c.name) for c in update.__table__.columns}
    shadow = SimpleNamespace(**fields)
    if scope:
        shadow.scope, shadow.scope_id = scope, (None if scope == "global" else scope_id)
    else:
        shadow.scope = shadow.scope or "device"
    shadow.environment = environment
    if target_ids is not None:
        shadow.target_device_ids = json.dumps(target_ids) if target_ids else None
    shadow.id = None   # targets are judged from the proposed scope; existing rows are checked separately
    return shadow


def approval_targets(db: Session, update, resolve_targets: Callable) -> list[dict]:
    """Moved from main.py unchanged (_approval_targets_for_update)."""
    device_map = {d.device_id: d for d in resolve_targets(db, update)}
    if not device_map and update.scope == "device" and update.scope_id:
        device = db.query(Device).filter_by(device_id=update.scope_id).first()
        if device:
            device_map[device.device_id] = device
    return [{
        "device_id": device.device_id,
        "customer_id": device.customer_id,
        "customer_name": device.customer_name,
        "site_id": device.site_id,
        "site_name": device.site_name,
        "camera_name": device.camera_name,
    } for device in device_map.values()]


def ensure_approval_authority(db: Session, user, update, payload, resolve_targets: Callable,
                              resolve_environment: Callable) -> None:
    """approve_update(): the caller must hold authority over the update as it
    is now (its existing targets) and as the approval would leave it."""
    shadow = proposed_approval(update, payload.scope, payload.scope_id, payload.target_device_ids,
                               payload.environment or "production")
    shadow.environment = resolve_environment(db, shadow.environment, shadow.scope, shadow.scope_id)
    ensure_update_authority(db, user, update, resolve_targets)
    ensure_update_authority(db, user, shadow, resolve_targets)
