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

from database import Camera, Customer, Device, Site, User


# ── Role model (Peter, 2026-10-10) ─────────────────────────────────────────
# super_admin: global access to every customer.
# admin / operator / viewer: their role applies to every customer they are
# attached to (users ↔ customers is many-to-many, table user_customers).
# A non-super_admin user with no customer gets no customer data — there is
# no implicit global access for any other role.

def _is_platform_admin(user: User | None) -> bool:
    """True only for super_admin — the one role with implicit global access."""
    return user is not None and getattr(user, "role", None) == "super_admin"


def user_customer_ids(user: User | None) -> set[str]:
    """The customers a user is attached to (memberships + legacy mirror).

    `users.customer_id` is kept as a mirror of a sole membership (see
    database.User); reading it too keeps rollback and not-yet-backfilled rows
    working. It can only ever add that one customer, never global access."""
    if user is None:
        return set()
    found = {str(link.customer_id) for link in (getattr(user, "customer_links", None) or []) if link.customer_id}
    legacy = getattr(user, "customer_id", None)
    if legacy:
        found.add(str(legacy))
    return found


def _allowed_customer_ids(db: Session | None, user: User | None) -> set[str] | None:
    """Customers the user may act for; None = all (super_admin only)."""
    if user is None:
        return set()
    if _is_platform_admin(user):
        return None
    return user_customer_ids(user)


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
    allowed = _allowed_customer_ids(None, user)
    if allowed is None:
        return
    if not customer_id or str(customer_id) not in allowed:
        raise HTTPException(status_code=403, detail="Ingen adgang til denne kunde")


def _ensure_site_access(db: Session, user: User | None, site_id: str | None) -> Site:
    site = db.query(Site).filter_by(id=site_id).first()
    if not site:
        raise HTTPException(status_code=404)
    _ensure_customer_access(user, site.customer_id)
    return site


def _visible_customer_query(db: Session, user: User | None):
    q = db.query(Customer)
    allowed = _allowed_customer_ids(db, user)
    if allowed is None:
        return q
    return q.filter(Customer.id.in_(sorted(allowed) or ["__none__"]))


def _visible_site_query(db: Session, user: User | None):
    q = db.query(Site)
    allowed = _allowed_customer_ids(db, user)
    if allowed is None:
        return q
    return q.filter(Site.customer_id.in_(sorted(allowed) or ["__none__"]))


def _visible_device_query(db: Session, user: User | None):
    q = db.query(Device)
    allowed = _allowed_customer_ids(db, user)
    if allowed is None:
        return q
    if not allowed:
        return q.filter(Device.device_id == "__none__")
    customers = sorted(allowed)
    site_ids = db.query(Site.id).filter(Site.customer_id.in_(customers))
    return q.filter(or_(Device.customer_id.in_(customers), Device.site_id.in_(site_ids)))


def _visible_camera_query(db: Session, user: "User | None"):
    """Samme tenant-afgrænsning som _visible_device_query, for Camera."""
    q = db.query(Camera).filter(Camera.retired_at.is_(None))
    allowed = _allowed_customer_ids(db, user)
    if allowed is None:
        return q
    if not allowed:
        return q.filter(Camera.id == "__none__")
    customers = sorted(allowed)
    site_ids = db.query(Site.id).filter(Site.customer_id.in_(customers))
    return q.filter(or_(Camera.customer_id.in_(customers), Camera.site_id.in_(site_ids)))


def _visible_device_ids(db: Session, user: User | None) -> set[str] | None:
    """device_ids the user may see; None = all (super_admin)."""
    if _allowed_customer_ids(db, user) is None:
        return None
    return {row[0] for row in _visible_device_query(db, user).with_entities(Device.device_id).all()}


def _ensure_device_access(db: Session, user: User | None, device_id: str | None) -> None:
    allowed = _visible_device_ids(db, user)
    if allowed is not None and device_id not in allowed:
        raise HTTPException(status_code=403, detail="Ingen adgang til denne enhed")
