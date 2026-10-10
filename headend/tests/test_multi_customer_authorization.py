"""Central authorization with many-to-many customers (2026-10-10).

super_admin: global. admin/operator/viewer: their role for every attached
customer. Any non-super_admin user without customers: no customer data.
Real User rows and memberships against sqlite, so the actual relationship
loading and tenant SQL run.
"""
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text

import main
import tenant_scope
from database import (
    Base, Capture, Customer, Device, PendingUpdate, SessionLocal, Site, User, UserCustomer, engine,
)
from services import update_tenant_authority as uta
from services.user_customers import backfill_user_customers, set_user_customers

C1, C2, C3 = "mc-cust-1", "mc-cust-2", "mc-cust-3"
D1, D2, D3, DSITE, DNONE = "TL-MC-D1", "TL-MC-D2", "TL-MC-D3", "TL-MC-DSITE", "TL-MC-DNONE"
SITE2 = "mc-site-2"
DEVICES = (D1, D2, D3, DSITE, DNONE)
PREFIX = "mc-user-"


def _clean(s):
    ids = [u.id for u in s.query(User).filter(User.username.like(f"{PREFIX}%")).all()]
    if ids:
        s.query(UserCustomer).filter(UserCustomer.user_id.in_(ids)).delete(synchronize_session=False)
    s.query(User).filter(User.username.like(f"{PREFIX}%")).delete(synchronize_session=False)
    s.query(PendingUpdate).filter_by(version="mc-test").delete(synchronize_session=False)
    s.query(Capture).filter(Capture.device_id.in_(DEVICES)).delete(synchronize_session=False)
    s.query(Device).filter(Device.device_id.in_(DEVICES)).delete(synchronize_session=False)
    s.query(Site).filter_by(id=SITE2).delete()
    s.query(Customer).filter(Customer.id.in_((C1, C2, C3))).delete(synchronize_session=False)
    s.commit()


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    _clean(s)
    for cid in (C1, C2, C3):
        s.add(Customer(id=cid, name=cid))
    s.add(Site(id=SITE2, customer_id=C2, name="site 2"))
    s.add_all([Device(device_id=D1, customer_id=C1), Device(device_id=D2, customer_id=C2),
               Device(device_id=D3, customer_id=C3), Device(device_id=DSITE, site_id=SITE2),
               Device(device_id=DNONE)])
    s.commit()
    try:
        yield s
    finally:
        s.rollback()
        _clean(s)
        s.close()


def _user(db, role, *customers, name=None):
    u = User(username=f"{PREFIX}{name or role}-{len(customers)}-{'-'.join(customers)}",
             password_hash="x", role=role)
    db.add(u)
    db.flush()
    set_user_customers(db, u, list(customers), actor="test")
    db.commit()
    db.refresh(u)
    return u


def _visible(db, user):
    ids = tenant_scope._visible_device_ids(db, user)
    return None if ids is None else ids & set(DEVICES)


# --- 0 / 1 / 2 / several customers, every role ---------------------------------------

@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_customer_count_drives_visibility_for_every_role(db, role):
    assert _visible(db, _user(db, role)) == set()
    assert _visible(db, _user(db, role, C1)) == {D1}
    assert _visible(db, _user(db, role, C1, C2)) == {D1, D2, DSITE}
    assert _visible(db, _user(db, role, C1, C2, C3)) == {D1, D2, D3, DSITE}


def test_super_admin_is_global_with_or_without_customers(db):
    assert tenant_scope._visible_device_ids(db, _user(db, "super_admin")) is None
    assert tenant_scope._visible_device_ids(db, _user(db, "super_admin", C1)) is None


def test_admin_without_customer_has_no_implicit_global_access(db):
    admin = _user(db, "admin")
    assert not tenant_scope._is_platform_admin(admin)
    assert tenant_scope._allowed_customer_ids(db, admin) == set()
    assert tenant_scope._visible_customer_query(db, admin).filter(Customer.id.in_((C1, C2, C3))).count() == 0
    assert tenant_scope._visible_site_query(db, admin).filter(Site.id == SITE2).count() == 0
    with pytest.raises(HTTPException):
        tenant_scope._ensure_customer_access(admin, C1)


def test_unauthorized_customer_is_refused_for_multi_customer_user(db):
    user = _user(db, "admin", C1, C2)
    tenant_scope._ensure_customer_access(user, C1)
    tenant_scope._ensure_customer_access(user, C2)
    with pytest.raises(HTTPException) as exc:
        tenant_scope._ensure_customer_access(user, C3)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        tenant_scope._ensure_device_access(db, user, D3)
    tenant_scope._ensure_device_access(db, user, DSITE)


@pytest.mark.parametrize("value", [None, "", C3, f"{C1},{C3}", "*", "%"])
def test_manipulated_customer_id_values_are_refused(db, value):
    user = _user(db, "operator", C1)
    with pytest.raises(HTTPException):
        tenant_scope._ensure_customer_access(user, value)


@pytest.mark.parametrize("device_id", [D3, DNONE, "TL-MC-UNKNOWN", f"{D1}' OR '1'='1", ""])
def test_manipulated_device_id_values_are_refused(db, device_id):
    user = _user(db, "admin", C1)
    with pytest.raises(HTTPException) as exc:
        main._ensure_capture_device_access(db, user, device_id)
    assert exc.value.status_code == 403


# --- membership changes ----------------------------------------------------------------

def test_revoking_a_membership_removes_access_immediately(db):
    user = _user(db, "admin", C1, C2)
    assert _visible(db, user) == {D1, D2, DSITE}
    set_user_customers(db, user, [C1], actor="test")
    db.commit()
    db.refresh(user)
    assert _visible(db, user) == {D1}
    assert user.customer_id == C1                   # legacy mirror = sole membership
    set_user_customers(db, user, [], actor="test")
    db.commit()
    db.refresh(user)
    assert _visible(db, user) == set()
    assert user.customer_id is None


def test_mirror_is_null_for_several_customers_and_never_global(db):
    user = _user(db, "admin", C1, C2)
    assert user.customer_id is None
    assert tenant_scope._allowed_customer_ids(db, user) == {C1, C2}


def test_role_change_keeps_customer_bound_and_super_admin_is_global(db):
    user = _user(db, "viewer", C1)
    user.role = "admin"
    db.commit()
    assert _visible(db, user) == {D1}
    user.role = "super_admin"
    db.commit()
    assert tenant_scope._visible_device_ids(db, user) is None
    user.role = "operator"
    db.commit()
    assert _visible(db, user) == {D1}


def test_unknown_customer_in_membership_is_refused(db):
    user = _user(db, "admin", C1)
    with pytest.raises(HTTPException) as exc:
        set_user_customers(db, user, [C1, "mc-does-not-exist"], actor="test")
    assert exc.value.status_code == 400


# --- user API ----------------------------------------------------------------------------

def test_create_and_update_user_api_with_several_customers(db):
    actor = SimpleNamespace(username="mc-actor", role="super_admin")
    created = main.create_user(main.UserCreateRequest(username=f"{PREFIX}api", password="longenough1",
                                                      role="operator", customer_ids=[C1, C2]), _user=actor, db=db)
    user = db.query(User).filter_by(id=created["id"]).one()
    assert tenant_scope.user_customer_ids(user) == {C1, C2}
    main.update_user(user.id, main.UserUpdateRequest(customer_ids=[C3]), _user=actor, db=db)
    db.refresh(user)
    assert tenant_scope.user_customer_ids(user) == {C3}
    main.update_user(user.id, main.UserUpdateRequest(customer_id=None), _user=actor, db=db)
    db.refresh(user)
    assert tenant_scope.user_customer_ids(user) == set()
    main.update_user(user.id, main.UserUpdateRequest(role="viewer"), _user=actor, db=db)
    db.refresh(user)
    assert user.role == "viewer" and tenant_scope.user_customer_ids(user) == set()
    listed = next(u for u in main.list_users(_user=actor, db=db) if u["id"] == user.id)
    assert listed["customer_ids"] == []


def test_legacy_single_customer_create_still_works(db):
    actor = SimpleNamespace(username="mc-actor", role="super_admin")
    created = main.create_user(main.UserCreateRequest(username=f"{PREFIX}legacy", password="longenough1",
                                                      role="viewer", customer_id=C2), _user=actor, db=db)
    user = db.query(User).filter_by(id=created["id"]).one()
    assert tenant_scope.user_customer_ids(user) == {C2} and user.customer_id == C2


# --- migration ---------------------------------------------------------------------------

def test_backfill_is_idempotent_and_never_resurrects_a_removed_membership(db):
    user = User(username=f"{PREFIX}legacy-row", password_hash="x", role="admin", customer_id=C1)
    db.add(user)
    db.commit()
    db.execute(text("DELETE FROM user_customers WHERE user_id = :u"), {"u": user.id})
    db.commit()
    assert backfill_user_customers(engine) >= 1
    assert backfill_user_customers(engine) == 0
    db.expire_all()
    assert tenant_scope.user_customer_ids(db.query(User).filter_by(id=user.id).one()) == {C1}
    set_user_customers(db, user, [], actor="test")
    db.commit()
    backfill_user_customers(engine)
    db.expire_all()
    assert tenant_scope.user_customer_ids(db.query(User).filter_by(id=user.id).one()) == set()


# --- downstream consumers -----------------------------------------------------------------

def test_capture_access_follows_memberships(db):
    user = _user(db, "viewer", C1, C2)
    for device_id, customer in ((D1, C1), (D3, C3)):
        db.add(Capture(device_id=device_id, filename=f"{device_id}.jpg", customer_id=customer))
    db.commit()
    own = db.query(Capture).filter_by(device_id=D1).one()
    other = db.query(Capture).filter_by(device_id=D3).one()
    assert main._capture_is_allowed(db, user, own)
    assert not main._capture_is_allowed(db, user, other)
    assert not main._capture_is_allowed(db, _user(db, "admin"), own)


def test_update_decisions_use_memberships(db):
    user = _user(db, "admin", C1, C2)
    both = PendingUpdate(update_type="app_updates", version="mc-test", scope="device", status="pending",
                         target_device_ids=json.dumps([D1, D2]), environment="production")
    mixed = PendingUpdate(update_type="app_updates", version="mc-test", scope="device", status="pending",
                          target_device_ids=json.dumps([D1, D3]), environment="production")
    db.add_all([both, mixed])
    db.commit()
    may = lambda u: uta.user_may_decide_update(db, user, u, lambda _db, _u: [])
    assert may(both)
    assert not may(mixed)


def test_mfa_requirement_is_the_strictest_attached_customer(db):
    from auth import _mfa_required_for_user
    db.query(Customer).filter_by(id=C2).update({"config_overrides": json.dumps({"session_policy": {"mfa_required": True}})})
    db.commit()
    lenient = _user(db, "viewer", C1)
    strict = _user(db, "viewer", C1, C2)
    assert _mfa_required_for_user(db, strict) is True
    assert _mfa_required_for_user(db, strict) or not _mfa_required_for_user(db, lenient)


def test_trust_policy_uses_customer_set():
    from trust.models import PolicyRequest
    from trust.policy import evaluate_policy, principal_from_legacy_user

    def decide(user, tenant):
        return evaluate_policy(PolicyRequest(principal=principal_from_legacy_user(user, mfa_verified=True),
                                             action="grant.issue", resource="edge:TL-X:local-service",
                                             tenant_id=tenant)).allowed
    multi = SimpleNamespace(username="m", role="admin", customer_id=None,
                            customer_links=[SimpleNamespace(customer_id=C1), SimpleNamespace(customer_id=C2)])
    assert decide(multi, C1) and decide(multi, C2)
    assert not decide(multi, C3)
    assert not decide(SimpleNamespace(username="n", role="admin", customer_id=None), C1)
    assert decide(SimpleNamespace(username="s", role="super_admin", customer_id=None), C3)


def test_admin_can_only_manage_ssh_keys_of_users_inside_own_customers(db):
    import technician_keys
    admin = _user(db, "admin", C1, C2)
    inside = _user(db, "operator", C1, name="inside")
    partly = _user(db, "operator", C1, C3, name="partly")
    nobody = _user(db, "operator", name="nobody")
    boss = _user(db, "super_admin", name="boss")
    assert technician_keys._may_manage_user_keys(db, admin, inside.id)
    assert not technician_keys._may_manage_user_keys(db, admin, partly.id)
    assert not technician_keys._may_manage_user_keys(db, admin, nobody.id)
    assert not technician_keys._may_manage_user_keys(db, admin, boss.id)
    assert technician_keys._may_manage_user_keys(db, boss, partly.id)
    assert not technician_keys._may_manage_user_keys(db, _user(db, "viewer", C1, C2, name="v"), inside.id)


def test_redaction_scope_query_follows_memberships(db):
    import redaction_api
    db.add_all([Capture(device_id=D1, filename="r1.jpg", customer_id=C1),
                Capture(device_id=D3, filename="r3.jpg", customer_id=C3)])
    db.commit()
    base = db.query(Capture).filter(Capture.device_id.in_(DEVICES))
    multi = _user(db, "viewer", C1, C2)
    assert {c.device_id for c in redaction_api._tenant_scope_query(base, multi).all()} == {D1}
    assert redaction_api._tenant_scope_query(base, _user(db, "operator")).count() == 0
    assert redaction_api._tenant_scope_query(base, _user(db, "super_admin")).count() == 2


def test_create_user_without_any_customer_is_allowed_and_gets_no_data(db):
    actor = SimpleNamespace(username="mc-actor", role="super_admin")
    created = main.create_user(main.UserCreateRequest(username=f"{PREFIX}nocust", password="longenough1",
                                                      role="admin"), _user=actor, db=db)
    user = db.query(User).filter_by(id=created["id"]).one()
    assert tenant_scope.user_customer_ids(user) == set()
    assert _visible(db, user) == set()
