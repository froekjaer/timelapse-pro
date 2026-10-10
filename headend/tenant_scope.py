# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — tenant_scope.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Tenant/multi-tenancy scoping primitives — "what can this user see or act on",
as distinct from auth.py's "who is this user, are they authenticated, what
role do they have".

Montér i main.py:
    from tenant_scope import (
        _is_platform_admin, FIELD_ROLES, _has_field_access,
        _ensure_customer_access, _ensure_site_access,
        _visible_customer_query, _visible_site_query, _visible_device_query,
        _visible_camera_query,
    )

Split out of main.py (2026-08-27, fast-follow to the auth.py extraction —
Phase 0's docstring explicitly deferred this cluster: "Different files
depend on different subsets of those, and they're a distinct 'tenant
scoping' concern from [auth.py's] scope — a fast-follow extraction once
this module has proven itself"). Triggered by the Cameras domain extraction
(headend/api/cameras_api.py), which needed _is_platform_admin,
_ensure_site_access, _ensure_customer_access, and _has_field_access at
module scope — at that point duplicating vs. properly extracting was no
longer a close call.

Like auth.py, this has no dependency on main.py or any router module (only
on database.py), so both main.py and every router module can import it at
module scope.

_visible_camera_query moved here from its physical location inside main.py's
old Camera section (it's the same "visible_X_query" family as the other
four, just camera-specific) — local_access.py already depended on it via a
lazy `from main import ...` for exactly this reason.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import Camera, Customer, Device, DeviceInventory, Site, User


def _is_platform_admin(user: User | None) -> bool:
    """Return True for users allowed to see all tenants."""
    if user is None:
        return False
    return user.role == "super_admin" or (user.role == "admin" and not user.customer_id)


FIELD_ROLES = ("none", "installer", "technician")


def _has_field_access(user: "User | None") -> bool:
    """True for users with an on-site field capability (installer or
    technician) — orthogonal to the UI RBAC role. Replaces the old
    on_site_service boolean (2026-08-19)."""
    if user is None:
        return False
    return getattr(user, "field_role", "none") in ("installer", "technician")


def _ensure_customer_access(user: User | None, customer_id: str | None) -> None:
    """Enforce tenant boundary for customer scoped records."""
    if _is_platform_admin(user):
        return
    if not user or not user.customer_id or customer_id != user.customer_id:
        raise HTTPException(status_code=403, detail="Ingen adgang til denne kunde")


def _ensure_site_access(db: Session, user: User | None, site_id: str | None) -> Site:
    site = db.query(Site).filter_by(id=site_id).first()
    if not site:
        raise HTTPException(status_code=404)
    _ensure_customer_access(user, site.customer_id)
    return site


def _visible_customer_query(db: Session, user: User | None):
    q = db.query(Customer)
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Customer.id == "__none__")
    return q.filter(Customer.id == user.customer_id)


def _visible_site_query(db: Session, user: User | None):
    q = db.query(Site)
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Site.id == "__none__")
    return q.filter(Site.customer_id == user.customer_id)


def _visible_device_query(db: Session, user: User | None):
    q = db.query(Device)
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Device.device_id == "__none__")
    site_ids = db.query(Site.id).filter(Site.customer_id == user.customer_id)
    return q.filter(or_(Device.customer_id == user.customer_id, Device.site_id.in_(site_ids)))


def _visible_camera_query(db: Session, user: "User | None"):
    """Samme tenant-afgrænsning som _visible_device_query, for Camera."""
    q = db.query(Camera).filter(Camera.retired_at.is_(None))
    if _is_platform_admin(user):
        return q
    if not user or not user.customer_id:
        return q.filter(Camera.id == "__none__")
    site_ids = db.query(Site.id).filter(Site.customer_id == user.customer_id)
    return q.filter(or_(Camera.customer_id == user.customer_id, Camera.site_id.in_(site_ids)))


def _visible_device_ids(db: Session, user: User | None) -> set[str] | None:
    """Device ids this user may act on; None = platform admin (all devices).

    Same tenant resolution as _visible_device_query (customer-owned devices
    plus devices on the customer's sites), for routers that filter rows by
    device_id rather than querying Device itself.
    """
    if _is_platform_admin(user):
        return None
    return {row[0] for row in _visible_device_query(db, user).with_entities(Device.device_id).all()}


def _ensure_device_access(db: Session, user: User | None, device_id: str | None) -> None:
    """403 unless the user may act on device_id. Equivalent to main's
    _ensure_capture_device_access, importable from router modules."""
    allowed = _visible_device_ids(db, user)
    if allowed is not None and device_id not in allowed:
        raise HTTPException(status_code=403, detail="Ingen adgang til denne enhed")


def _ensure_platform_admin(user: User | None) -> None:
    """403 unless the user may see all tenants (platform-wide views/actions)."""
    if not _is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Kun platform-administratorer")


def _visible_only(db: Session, user: User | None, items: list, device_id_of) -> list:
    """Keep only items whose device the user may see (all for platform admins)."""
    allowed = _visible_device_ids(db, user)
    return items if allowed is None else [item for item in items if device_id_of(item) in allowed]


def _tenant_inventories(db: Session, user: User | None) -> list:
    """DeviceInventory rows the user may see, ordered by device_id."""
    q = db.query(DeviceInventory)
    allowed = _visible_device_ids(db, user)
    if allowed is not None:
        q = q.filter(DeviceInventory.device_id.in_(sorted(allowed) or ["__none__"]))
    return q.order_by(DeviceInventory.device_id).all()
