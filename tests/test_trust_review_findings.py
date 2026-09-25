import json
from types import SimpleNamespace

from headend.trust import grants
from headend.trust.policy import evaluate_legacy_role_capability_check


def _grant_row():
    return SimpleNamespace(metadata_json="{}", last_challenge_id=None)


def _admin_user():
    return SimpleNamespace(
        username="review-user",
        role="admin",
        id=1,
        customer_id=None,
        on_site_service=False,
    )


def test_challenge_replay_set_rejects_non_adjacent_replay():
    row = _grant_row()

    assert grants._consume_challenge(row, "challenge-a") is None
    assert grants._consume_challenge(row, "challenge-b") is None
    assert grants._consume_challenge(row, "challenge-a") == (
        "replayed technician challenge denied"
    )

    metadata = json.loads(row.metadata_json)
    assert metadata["used_challenge_ids"] == ["challenge-a", "challenge-b"]


def test_challenge_budget_fails_closed_instead_of_evicting(monkeypatch):
    monkeypatch.setattr(grants, "MAX_CHALLENGES_PER_GRANT", 2)
    row = _grant_row()

    assert grants._consume_challenge(row, "challenge-a") is None
    assert grants._consume_challenge(row, "challenge-b") is None
    assert grants._consume_challenge(row, "challenge-c") == (
        "grant challenge budget exhausted"
    )
    assert grants._consume_challenge(row, "challenge-a") == (
        "replayed technician challenge denied"
    )


def test_grant_validation_uses_database_row_lock():
    source = open("headend/trust/grants.py", encoding="utf-8").read()
    assert "query.with_for_update().first()" in source


def test_legacy_policy_requires_mfa_independently_of_evidence():
    denied = evaluate_legacy_role_capability_check(
        _admin_user(),
        action="grant.issue",
        resource="edge:TL-C87FF9587CA0:local-service",
        capability="edge.service.local_view",
        mfa_verified=False,
    )
    allowed = evaluate_legacy_role_capability_check(
        _admin_user(),
        action="grant.issue",
        resource="edge:TL-C87FF9587CA0:local-service",
        capability="edge.service.local_view",
        mfa_verified=True,
    )

    assert denied.allowed is False
    assert "MFA" in denied.reason
    assert allowed.allowed is True
