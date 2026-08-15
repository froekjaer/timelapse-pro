import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(ROOT / "headend"))

from database import Base, EdgeServiceGrant, TrustPolicyDecisionAudit, now_utc  # noqa: E402
from trust.audit import record_policy_decision  # noqa: E402
from trust.dmz import SECURE_SERVICE_DMZ_SPEC, dmz_can_issue_trust_material, is_conduit_allowed  # noqa: E402
from trust.grants import GrantDenied, issue_edge_service_grant, revoke_edge_service_grant, validate_edge_service_grant  # noqa: E402
from trust.models import GrantRequest, PolicyRequest, Principal  # noqa: E402
from trust.policy import evaluate_legacy_role_capability_check, evaluate_policy  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def admin(mfa=True):
    return Principal("alice", "admin", user_id=1, tenant_id="cust-a", mfa_verified=mfa)


def technician(mfa=True):
    return Principal(
        "tech",
        "viewer",
        user_id=2,
        tenant_id="cust-a",
        capabilities=frozenset({"edge.service.local_view"}),
        mfa_verified=mfa,
    )


def grant_request(principal=None, **overrides):
    data = {
        "principal": principal or admin(),
        "edge_id": "TL-EDGE-A",
        "tenant_id": "cust-a",
        "resource": "edge:TL-EDGE-A:local-service",
        "purpose": "site commissioning",
        "capabilities": frozenset({"edge.service.local_view"}),
        "ttl_seconds": 300,
        "mfa_required": True,
    }
    data.update(overrides)
    return GrantRequest(**data)


def issue(db, **overrides):
    token, row = issue_edge_service_grant(db, grant_request(**overrides))
    db.flush()
    return token, row


def test_grant_cannot_be_used_on_another_edge(db):
    token, _row = issue(db)
    result = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-B", tenant_id="cust-a",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="c1",
    )
    assert result.allowed is False
    assert "edge binding" in result.reason


def test_grant_cannot_cross_tenant_boundary(db):
    token, _row = issue(db)
    result = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-A", tenant_id="cust-b",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="c1",
    )
    assert result.allowed is False
    assert "tenant boundary" in result.reason


def test_grant_cannot_exceed_capability_scope(db):
    token, _row = issue(db)
    result = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-A", tenant_id="cust-a",
        capability="edge.service.break_glass", resource="edge:TL-EDGE-A:local-service", challenge_id="c1",
    )
    assert result.allowed is False
    assert "capability scope" in result.reason


def test_grant_expires_and_is_denied(db):
    token, row = issue(db)
    row.expires_at = now_utc() - timedelta(seconds=1)
    result = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-A", tenant_id="cust-a",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="c1",
    )
    assert result.allowed is False
    assert "expired" in result.reason


def test_revoked_grant_denied(db):
    token, row = issue(db)
    revoke_edge_service_grant(db, row.grant_id, actor="alice", reason="test revoke")
    result = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-A", tenant_id="cust-a",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="c1",
    )
    assert result.allowed is False
    assert "revoked" in result.reason


def test_missing_required_mfa_denied():
    decision = evaluate_policy(PolicyRequest(
        principal=admin(mfa=False),
        action="grant.issue",
        resource="edge:TL-EDGE-A:local-service",
        tenant_id="cust-a",
        capability="edge.service.local_view",
        mfa_required=True,
    ))
    assert decision.allowed is False
    assert "MFA" in decision.reason


def test_normal_headend_session_token_rejected_as_local_service_grant(db):
    result = validate_edge_service_grant(
        db, "not.an.edge.service.grant", edge_id="TL-EDGE-A", tenant_id="cust-a",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="c1",
    )
    assert result.allowed is False


def test_replayed_technician_challenge_denied(db):
    token, _row = issue(db)
    first = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-A", tenant_id="cust-a",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="same",
    )
    second = validate_edge_service_grant(
        db, token, edge_id="TL-EDGE-A", tenant_id="cust-a",
        capability="edge.service.local_view", resource="edge:TL-EDGE-A:local-service", challenge_id="same",
    )
    assert first.allowed is True
    assert second.allowed is False
    assert "replayed" in second.reason


def test_viewer_cannot_obtain_privileged_service_grant(db):
    with pytest.raises(GrantDenied, match="missing capability"):
        issue_edge_service_grant(db, grant_request(principal=Principal("viewer", "viewer", tenant_id="cust-a", mfa_verified=True)))


def test_technician_without_required_capability_denied(db):
    no_cap = Principal("tech", "viewer", tenant_id="cust-a", mfa_verified=True)
    with pytest.raises(GrantDenied, match="missing capability"):
        issue_edge_service_grant(db, grant_request(principal=no_cap))


def test_admin_override_behavior_explicit_and_audited(db):
    req = PolicyRequest(
        principal=admin(),
        action="grant.issue",
        resource="edge:TL-EDGE-A:local-service",
        tenant_id="cust-a",
        capability="edge.service.local_view",
        mfa_required=True,
        context={"override": "admin_standard_issue"},
    )
    decision = evaluate_policy(req)
    row = record_policy_decision(db, req, decision)
    db.flush()
    assert decision.allowed is True
    assert row.reason == decision.reason
    assert db.query(TrustPolicyDecisionAudit).count() == 1


def test_unknown_action_resource_context_denied_with_reason():
    unknown_action = evaluate_policy(PolicyRequest(admin(), "shell.spawn", "edge:TL-EDGE-A", capability=None))
    unknown_resource = evaluate_policy(PolicyRequest(admin(), "grant.issue", "browser-terminal", capability=None))
    assert unknown_action.allowed is False and unknown_action.reason
    assert unknown_resource.allowed is False and unknown_resource.reason


def test_every_decision_includes_reason():
    decision = evaluate_policy(PolicyRequest(admin(), "grant.issue", "edge:TL-EDGE-A", capability="edge.service.local_view"))
    assert isinstance(decision.reason, str)
    assert decision.reason


def test_secure_service_dmz_is_not_trust_authority():
    assert dmz_can_issue_trust_material() is False
    assert is_conduit_allowed("dmz", "trust", "allowlisted_trust_api") is True
    assert {"from": "dmz", "to": "data", "reason": "DMZ must not have direct unrestricted data-zone access"} in SECURE_SERVICE_DMZ_SPEC["prohibited"]
    assert SECURE_SERVICE_DMZ_SPEC["trust_authority"] == "TimeLapse Trust Service"


def test_grant_record_is_persisted(db):
    _token, row = issue(db, principal=technician())
    assert row.grant_id
    assert db.query(EdgeServiceGrant).filter_by(grant_id=row.grant_id).count() == 1


def test_legacy_role_capability_checks_route_through_pdp_compatibility_layer():
    user = type("User", (), {
        "username": "legacy-admin",
        "role": "admin",
        "id": 10,
        "customer_id": "cust-a",
        "on_site_service": False,
    })()

    decision = evaluate_legacy_role_capability_check(
        user,
        action="grant.issue",
        resource="edge:TL-EDGE-A:local-service",
        capability="edge.service.local_view",
        tenant_id="cust-a",
        mfa_verified=True,
    )

    assert decision.allowed is True
    assert decision.reason == "allowed by Trust Service PDP"


def test_legacy_role_capability_compatibility_fails_closed_for_unknown_action():
    user = type("User", (), {
        "username": "legacy-admin",
        "role": "admin",
        "id": 10,
        "customer_id": "cust-a",
        "on_site_service": True,
    })()

    decision = evaluate_legacy_role_capability_check(
        user,
        action="browser-terminal.spawn",
        resource="edge:TL-EDGE-A:local-service",
        capability="edge.service.local_view",
        tenant_id="cust-a",
        mfa_verified=True,
    )

    assert decision.allowed is False
    assert "unknown action denied" in decision.reason
