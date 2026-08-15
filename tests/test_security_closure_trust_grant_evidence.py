from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from headend.api.trust_service_api import _resolve_edge_tenant, _validate_edge_resource
from headend.trust import grants
from headend.trust.models import GrantRequest, PolicyDecision, Principal


class _Query:
    def __init__(self, row):
        self.row = row

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row
        self.added = []

    def query(self, _model):
        return _Query(self.row)

    def add(self, row):
        self.added.append(row)


def test_trust_signing_derives_separate_migration_key_from_jwt_root(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "production")
    monkeypatch.delenv("TIMELAPSE_TRUST_SERVICE_SIGNING_SECRET", raising=False)
    jwt = "this-is-a-strong-jwt-root-secret-used-only-as-migration-root"
    monkeypatch.setenv("JWT_SECRET", jwt)
    first = grants._secret()
    second = grants._secret()
    assert first == second
    assert first != jwt.encode()
    assert len(first) == 32


def test_trust_signing_fails_closed_without_any_strong_authority(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "production")
    monkeypatch.delenv("TIMELAPSE_TRUST_SERVICE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(grants.TrustServiceConfigurationError):
        grants._secret()


def test_trust_signing_accepts_dedicated_strong_secret(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_ENV", "production")
    value = "x" * 48
    monkeypatch.setenv("TIMELAPSE_TRUST_SERVICE_SIGNING_SECRET", value)
    assert grants._secret() == value.encode()


def test_all_requested_capabilities_are_checked(monkeypatch):
    checked = []

    def fake_policy(request):
        checked.append(request.capability)
        allowed = request.capability != "edge.shell.remote"
        return PolicyDecision(allowed, "allowed" if allowed else "shell denied", f"d-{len(checked)}")

    monkeypatch.setattr(grants, "evaluate_policy", fake_policy)
    request = GrantRequest(
        principal=Principal(username="u", role="admin", mfa_verified=True),
        edge_id="TL-1", tenant_id="customer-a",
        resource="edge:TL-1:local-service", purpose="test",
        capabilities=frozenset({"edge.service.diagnostics", "edge.shell.remote"}),
        ttl_seconds=60, mfa_required=True,
    )
    with pytest.raises(grants.GrantDenied, match="shell denied"):
        grants.issue_edge_service_grant(_Db(None), request)
    assert checked == ["edge.service.diagnostics", "edge.shell.remote"]


def test_edge_tenant_binding_rejects_cross_tenant_admin():
    db = _Db(SimpleNamespace(customer_id="customer-b"))
    user = SimpleNamespace(customer_id="customer-a")
    with pytest.raises(HTTPException) as exc:
        _resolve_edge_tenant(db, edge_id="TL-1", requested_tenant=None, user=user)
    assert exc.value.status_code == 403


def test_edge_tenant_binding_uses_actual_edge_owner_for_global_admin():
    db = _Db(SimpleNamespace(customer_id="customer-b"))
    user = SimpleNamespace(customer_id=None)
    assert _resolve_edge_tenant(db, edge_id="TL-1", requested_tenant=None, user=user) == "customer-b"


def test_edge_resource_must_match_edge_id():
    _validate_edge_resource("TL-1", "edge:TL-1:local-service")
    with pytest.raises(HTTPException) as exc:
        _validate_edge_resource("TL-1", "edge:TL-2:local-service")
    assert exc.value.status_code == 400


def test_admin_grant_api_uses_real_session_mfa_not_constant_true():
    import inspect
    import headend.api.trust_service_api as module

    source = inspect.getsource(module.create_trust_service_router)
    assert "_session_is_mfa_verified(_session_payload(request))" in source
    assert "mfa_verified=True" not in source
