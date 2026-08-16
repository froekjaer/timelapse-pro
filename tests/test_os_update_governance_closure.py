from pathlib import Path


def test_cmdb_os_inventory_is_observation_only_not_deployable_pending_work():
    source = Path("headend/cmdb.py").read_text(encoding="utf-8")
    start = source.index("def _sync_edge_os_updates(")
    end = source.index("\n\n# ── Kryptering", start)
    section = source[start:end]
    assert 'status="blocked"' in section
    assert "CMDB observation" in section
    assert 'status="pending"' not in section
    assert 'PendingUpdate.status.in_(["blocked", "pending", "approved"])' in section
    assert 'PendingUpdate.status.in_(["pending", "approved"])' not in section


def test_existing_cmdb_observation_is_forced_back_to_blocked():
    source = Path("headend/cmdb.py").read_text(encoding="utf-8")
    start = source.index("def _sync_edge_os_updates(")
    end = source.index("\n\n# ── Kryptering", start)
    section = source[start:end]
    assert 'existing.status = "blocked"' in section


def test_auto_os_bundle_builder_requires_explicit_lab_plan_evidence():
    source = Path("headend/main.py").read_text(encoding="utf-8")
    start = source.index("def _os_bundle_auto_build_pending()")
    end = source.index("\ndef _auto_build_and_bind_os_bundle(", start)
    section = source[start:end]
    assert "_plan_path_for_update(update)" in section
    assert "mangler lab build-plan evidence" in section
    assert "continue" in section
