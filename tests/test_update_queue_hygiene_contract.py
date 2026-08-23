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


def test_homebrew_inventory_candidates_are_blocked_until_signed_artifact_flow_exists():
    source = _source("headend/cmdb.py")
    block = source[
        source.index("def _sync_managed_application_updates("):source.index("def _sync_edge_os_updates(")
    ]

    assert 'PendingUpdate.status.in_(["pending", "approved", "blocked"])' in block
    assert '"\\n\\nBlocked: kræver signeret dependency-artifact og rollback-plan før godkendelse."' in block
    assert 'exists.status = "blocked"' in block
    assert 'status="blocked"' in block
