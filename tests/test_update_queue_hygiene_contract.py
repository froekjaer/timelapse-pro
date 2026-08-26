"""Contracts that keep stale update candidates out of the approval queue."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_heartbeat_app_update_requires_signed_artifact():
    source = _source("headend/main.py")
    block = source[source.index("def _process_update_report("):source.index("# ── Heartbeat")]

    assert "UpdateArtifact.artifact_type == \"app\"" in block
    assert "UpdateArtifact.source_commit == version" in block
    assert "UpdateArtifact.signature.isnot(None)" in block
    assert "if not _has_signed_app_artifact(headend_version):" in block
    assert "intet signeret Edge app-artifact" in block


def test_edge_available_update_hints_do_not_create_app_candidates():
    source = _source("headend/main.py")
    block = source[source.index("def report_available_updates("):source.index("# ── PROVISION PACKAGE")]

    assert "app_security_ignored_signed_artifact_required" in block
    assert "app_updates_ignored_signed_artifact_required" in block
    assert 'update_type = "app_security"' not in block
    assert 'update_type = "app_updates"' not in block


def test_homebrew_inventory_candidates_are_blocked_until_signed_artifact_flow_exists():
    source = _source("headend/cmdb.py")
    block = source[
        source.index("def _sync_managed_application_updates("):source.index("def _sync_edge_os_updates(")
    ]

    assert 'PendingUpdate.status.in_(["pending", "approved", "blocked"])' in block
    assert '"\\n\\nBlocked: kræver signeret dependency-artifact og rollback-plan før godkendelse."' in block
    assert 'exists.status = "blocked"' in block
    assert 'status="blocked"' in block


def test_deployed_history_requires_explicit_promotion_eligibility():
    backend = _source("headend/services/update_promotion.py")
    ui = _source("timelapse-ui/src/pages/UpdatesPage.tsx")

    assert '"promotion_eligible": promotion.eligible' in backend
    assert '"promotion_blocked_reason": promotion.blocked_reason' in backend
    assert 'getattr(update, "environment", None) not in {"test", "staging"}' in backend
    assert "Mangler deploybart signeret artifact." in backend
    assert "Target-enhed rapporterer ikke længere denne app-version." in backend
    assert "u.promotion_eligible ? (" in ui
    assert "Historisk deploy" in ui


def test_device_matrix_excludes_historical_update_statuses_from_current_state():
    source = _source("headend/main.py")
    start = source.index("def _update_is_matrix_candidate(")
    end = source.index("\ndef _installed_value(", start)
    block = source[start:end]

    assert '"superseded"' in block
    assert '"rolled_back"' in block
    assert '"rejected"' in block
    assert '"cancelled"' in block
