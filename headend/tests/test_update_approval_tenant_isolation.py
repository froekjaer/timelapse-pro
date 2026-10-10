"""Update decisions are tenant-bound (security remediation, 2026-10-10).

super_admin decides across all customers; admin and operator only within
their own customers. An update row is shared by every device it targets, so
ALL affected devices — and the scope itself — must be within the caller's
customers. One allowed target never grants the others, and a refused
approval writes nothing.
"""
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import main
from database import (
    Base, ChangeApproval, ChangeTicket, Device, DeviceInventory, PendingUpdate, SessionLocal, Site,
    UpdateArtifact, UpdateTarget, engine,
)
from services import update_tenant_authority as uta

CUST_A, CUST_B = "cust-upd-a", "cust-upd-b"
SITE_A = "site-upd-a"
A1, A2, B1, ORPHAN, SITE_ONLY = "TL-UPD-A1", "TL-UPD-A2", "TL-UPD-B1", "TL-UPD-ORPHAN", "TL-UPD-SITE-A"
DEVICES = (A1, A2, B1, ORPHAN, SITE_ONLY)
VERSION = "tenant-approval-v1"


def _clean(s):
    ids = [u.id for u in s.query(PendingUpdate).filter_by(version=VERSION).all()]
    if ids:
        tickets = [t.ticket_id for t in s.query(ChangeTicket).filter(ChangeTicket.pending_update_id.in_(ids)).all()]
        s.query(ChangeApproval).filter(ChangeApproval.ticket_id.in_(tickets)).delete(synchronize_session=False)
        s.query(ChangeTicket).filter(ChangeTicket.pending_update_id.in_(ids)).delete(synchronize_session=False)
        s.query(UpdateTarget).filter(UpdateTarget.pending_update_id.in_(ids)).delete(synchronize_session=False)
    s.query(PendingUpdate).filter_by(version=VERSION).delete(synchronize_session=False)
    s.query(UpdateArtifact).filter_by(artifact_id="art-tenant-approval").delete()
    s.query(DeviceInventory).filter(DeviceInventory.device_id.in_(DEVICES)).delete(synchronize_session=False)
    s.query(Device).filter(Device.device_id.in_(DEVICES)).delete(synchronize_session=False)
    s.query(Site).filter_by(id=SITE_A).delete()
    s.commit()


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    _clean(s)
    s.add(Site(id=SITE_A, customer_id=CUST_A, name="Site A"))
    for device_id, customer, site in ((A1, CUST_A, None), (A2, CUST_A, None), (B1, CUST_B, None),
                                      (ORPHAN, None, None), (SITE_ONLY, None, SITE_A)):
        s.add(Device(device_id=device_id, customer_id=customer, site_id=site))
        s.add(DeviceInventory(device_id=device_id, environment="production"))
    s.commit()
    try:
        yield s
    finally:
        _clean(s)
        s.close()


def _user(role, *customers):
    return SimpleNamespace(username=f"{role}-user", role=role, customer_id=customers[0] if customers else None)


SUPER = _user("super_admin")
ADMIN_A = _user("admin", CUST_A)
OPERATOR_A = _user("operator", CUST_A)
VIEWER_A = _user("viewer", CUST_A)
ADMIN_NO_CUSTOMER = _user("admin")
OPERATOR_NO_CUSTOMER = _user("operator")


def _update(db, scope="device", scope_id=A1, target_ids=None, status="pending"):
    u = PendingUpdate(update_type="app_updates", version=VERSION, description="t", severity="low",
                      scope=scope, scope_id=scope_id, status=status, environment="production",
                      target_device_ids=json.dumps(target_ids) if target_ids else None)
    db.add(u)
    db.commit()
    return u


def _may(db, user, update):
    return uta.user_may_decide_update(db, user, update, main._resolve_update_targets)


# --- the rule itself -----------------------------------------------------------------

@pytest.mark.parametrize("user", [ADMIN_A, OPERATOR_A])
def test_own_device_customer_and_site_scopes_are_allowed(db, user):
    assert _may(db, user, _update(db, "device", A1))
    assert _may(db, user, _update(db, "customer", CUST_A))
    assert _may(db, user, _update(db, "site", SITE_A))
    assert _may(db, user, _update(db, "device", None, target_ids=[A1, A2]))


@pytest.mark.parametrize("user", [ADMIN_A, OPERATOR_A])
def test_other_customer_and_global_scopes_are_refused(db, user):
    assert not _may(db, user, _update(db, "device", B1))
    assert not _may(db, user, _update(db, "customer", CUST_B))
    assert not _may(db, user, _update(db, "global", None))


@pytest.mark.parametrize("user", [ADMIN_A, OPERATOR_A])
def test_mixed_target_list_is_refused_even_with_one_own_target(db, user):
    assert not _may(db, user, _update(db, "device", None, target_ids=[A1, B1]))
    assert not _may(db, user, _update(db, "device", None, target_ids=[B1, A1, A2]))


@pytest.mark.parametrize("user", [ADMIN_A, OPERATOR_A])
def test_unknown_or_unassigned_targets_are_refused(db, user):
    assert not _may(db, user, _update(db, "device", None, target_ids=[A1, "TL-DOES-NOT-EXIST"]))
    assert not _may(db, user, _update(db, "device", ORPHAN))


def test_device_bound_only_through_its_site_counts_as_that_customer(db):
    assert _may(db, ADMIN_A, _update(db, "device", SITE_ONLY))


def test_stale_target_row_of_another_customer_refuses_the_update(db):
    u = _update(db, "device", A1)
    db.add(UpdateTarget(pending_update_id=u.id, device_id=B1, status="queued"))
    db.commit()
    assert not _may(db, ADMIN_A, u)
    assert _may(db, SUPER, u)


@pytest.mark.parametrize("user", [ADMIN_NO_CUSTOMER, OPERATOR_NO_CUSTOMER, VIEWER_A])
def test_no_customer_or_viewer_gets_nothing(db, user):
    assert not _may(db, user, _update(db, "device", A1))
    assert not _may(db, user, _update(db, "global", None))


def test_super_admin_decides_across_customers(db):
    assert _may(db, SUPER, _update(db, "global", None))
    assert _may(db, SUPER, _update(db, "device", None, target_ids=[A1, B1, ORPHAN]))


# --- endpoints -------------------------------------------------------------------------

def _status(fn, *args, **kwargs):
    with pytest.raises(HTTPException) as exc:
        fn(*args, **kwargs)
    return exc.value.status_code


def _approvals(db):
    return db.query(ChangeApproval).join(ChangeTicket, ChangeTicket.ticket_id == ChangeApproval.ticket_id) \
        .join(PendingUpdate, PendingUpdate.id == ChangeTicket.pending_update_id) \
        .filter(PendingUpdate.version == VERSION).count()


@pytest.mark.parametrize("payload", [
    dict(scope="global"),
    dict(scope="customer", scope_id=CUST_B),
    dict(scope="device", scope_id=B1),
    dict(scope="device", target_device_ids=[A1, B1]),
])
def test_approve_cannot_be_widened_beyond_own_customer_and_writes_nothing(db, payload):
    u = _update(db, "device", A1)
    assert _status(main.approve_update, u.id, main.ApprovePayload(environment="production", **payload),
                   current_user=ADMIN_A, db=db) == 403
    db.expire_all()
    assert db.query(PendingUpdate).filter_by(id=u.id).one().status == "pending"
    assert db.query(PendingUpdate).filter_by(id=u.id).one().scope == "device"
    assert _approvals(db) == 0


def test_approve_other_customers_update_is_refused(db):
    u = _update(db, "device", B1)
    assert _status(main.approve_update, u.id, main.ApprovePayload(environment="production"),
                   current_user=ADMIN_A, db=db) == 403


def test_approve_own_update_still_works_for_tenant_admin(db):
    db.add(UpdateArtifact(
        artifact_id="art-tenant-approval", artifact_type="app", version=VERSION, source_commit="deadbeef",
        source_ref="ci", sha256="a" * 64,
        signature="-----BEGIN PGP SIGNATURE-----\nci\n-----END PGP SIGNATURE-----", signed_by="ci",
        manifest_json=json.dumps({"schema": "timelapse.update_artifact.v1",
                                  "source": {"commit": "deadbeef", "dirty_worktree": False}})))
    db.commit()
    u = _update(db, "device", A1)
    result = main.approve_update(u.id, main.ApprovePayload(environment="production", scope="device", scope_id=A1),
                                 current_user=ADMIN_A, db=db)
    assert result["ok"] is True


def test_reject_stop_rollback_promote_and_ticket_refuse_other_customer(db):
    u = _update(db, "device", B1)
    assert _status(main.reject_update, u.id, current_user=ADMIN_A, db=db) == 403
    assert _status(main.force_rollback, u.id, current_user=ADMIN_A, db=db) == 403
    assert _status(main.promote_update, u.id, SimpleNamespace(target_environment="production"),
                   current_user=ADMIN_A, db=db) == 403
    assert _status(main.create_change_ticket_for_update, u.id, main.ChangeTicketPayload(),
                   current_user=ADMIN_A, db=db) == 403
    approved = _update(db, "device", B1, status="approved")
    assert _status(main.stop_update_approval, approved.id, current_user=ADMIN_A, db=db) == 403
    db.expire_all()
    assert db.query(PendingUpdate).filter_by(id=u.id).one().status == "pending"


def test_change_ticket_decisions_refuse_other_customer(db):
    u = _update(db, "device", None, target_ids=[A1, B1])
    ticket = main.create_change_ticket_for_update(u.id, main.ChangeTicketPayload(), current_user=SUPER, db=db)
    payload = main.ChangeDecisionPayload(notes="t")
    assert _status(main.approve_change_ticket, ticket["ticket_id"], payload, current_user=ADMIN_A, db=db) == 403
    assert _status(main.reject_change_ticket, ticket["ticket_id"], payload, current_user=ADMIN_A, db=db) == 403


def test_operator_compliance_accept_refuses_mixed_targets(db):
    u = _update(db, "device", None, target_ids=[A1, B1])
    assert _status(main.compliance_accept_update, u.id, current_user=OPERATOR_A, db=db) == 403


def test_approval_queue_only_lists_fully_authorized_updates(db):
    own = _update(db, "device", A1)
    mixed = _update(db, "device", None, target_ids=[A1, B1])
    ids = {item["id"] for item in main._approval_queue(db, OPERATOR_A)}
    assert own.id in ids and mixed.id not in ids
    assert {own.id, mixed.id} <= {item["id"] for item in main._approval_queue(db, SUPER)}


@pytest.mark.parametrize("path", [
    "/api/updates/{update_id}/headend-deploy",
    "/api/updates/auto-deploy/evaluate",
    "/api/updates/os-catalog/import-apt-list",
    "/api/updates/os-catalog/refresh-from-builder",
    "/api/updates/os-catalog/refresh-from-builder-job",
    "/api/updates/artifacts/catalog-current",
    "/api/updates/artifacts/catalog-from-git-tag",
    "/api/updates/artifacts/catalog-os-bundle",
    "/api/updates/artifacts/catalog-python-bundle",
    "/api/updates/{update_id}/os-bundle/build-bind",
    "/api/updates/{update_id}/os-bundle/build-bind-job",
    "/api/updates/{update_id}/bind-artifact",
])
def test_platform_release_actions_are_super_admin_only(db, path):
    route = next(r for r in main.app.routes if getattr(r, "path", None) == path and "POST" in r.methods)
    check = next(d.call for d in route.dependant.dependencies if d.call.__name__ == "_check")
    for user in (ADMIN_A, ADMIN_NO_CUSTOMER):
        with pytest.raises(HTTPException) as exc:
            check(request=None, user=user, db=db)
        assert exc.value.status_code == 403
