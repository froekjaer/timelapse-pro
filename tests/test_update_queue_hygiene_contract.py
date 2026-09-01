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


def test_updates_endpoint_has_actionable_filter_and_action_first_ordering():
    source = _source("headend/main.py")
    block = source[source.index("def list_pending_updates("):source.index("UPDATE_CATEGORIES = [")]

    assert 'status == "actionable"' in block
    assert '"pending", "approved", "blocked", "rollback_requested"' in block
    assert 'status == "all"' in block
    assert "PendingUpdate.created_at.desc()" in block
    assert "PendingUpdate.id.desc()" in block


def test_updates_page_defaults_to_actionable_cards_before_reference_panels():
    source = _source("timelapse-ui/src/pages/UpdatesPage.tsx")

    assert "type Filter = 'actionable'" in source
    assert "{ key: 'actionable', label: 'Kræver handling' }" in source
    assert "useState<Filter>('actionable')" in source
    assert 'const params = `?status=${activeFilter}`' in source
    assert "sortUpdatesForDisplay(data as Update[])" in source
    assert source.index('<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">') < source.index("<DeviceUpdateMatrix matrix={matrix} />")


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


def test_headend_installer_persists_terminal_target_and_ticket_state():
    main_source = _source("headend/main.py")
    main_block = main_source[main_source.index("def _run_headend_platform_update("):main_source.index("\n\n@app.get(\"/api/updates/{update_id}/headend-deploy/status\")")]
    helper = _source("headend/services/headend_update_state.py")

    assert "mark_headend_update_deployed(db, update)" in main_block
    assert "mark_headend_update_failed(db, update, exc, failure_evidence)" in main_block
    assert 'ticket.status = "deployed"' in helper
    assert '"status": "deployed"' in helper
    assert 'update.status = "blocked"' in helper
    assert 'ticket.status = "cancelled"' in helper
    assert '"status": "failed"' in helper


def test_ollama_headend_postflight_uses_homebrew_runtime_and_api_version_match():
    source = _source("headend/main.py")
    allowlist = source[source.index("HEADEND_PLATFORM_BREW_ALLOWLIST = {"):source.index("\nHEADEND_PLATFORM_MANUAL_PROFILES")]
    runtime_block = source[source.index("def _validate_ollama_runtime("):source.index("\ndef _validate_headend_profile(", source.index("def _validate_ollama_runtime("))]
    profile_block = source[source.index("def _validate_headend_profile("):source.index("\ndef _run_headend_platform_update(")]

    assert '"/opt/homebrew/opt/ollama/libexec/ollama"' in allowlist
    assert "/Applications/Ollama.app/Contents/Resources/ollama" not in allowlist
    assert "Ollama API version mismatch" in runtime_block
    assert "update.version.rsplit(\"->\", 1)[1].strip()" in profile_block
