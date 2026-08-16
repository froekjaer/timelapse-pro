import json
from pathlib import Path

import pytest

from edge.update_lifecycle import release_receipt_matches_artifact, restore_previous_app_release


def _artifact(artifact_id="TL-ART-1", commit="abc123", version="1.2.3", outputs=None):
    return {
        "artifact_id": artifact_id,
        "source_commit": commit,
        "version": version,
        "manifest": {"outputs": outputs or []},
    }


def test_release_receipt_matches_exact_artifact(tmp_path: Path):
    receipt = tmp_path / ".timelapse-release.json"
    receipt.write_text(json.dumps({
        "schema": "timelapse.edge.release.v1",
        "artifact_id": "TL-ART-1",
        "source_commit": "abc123",
        "version": "1.2.3",
        "installed_at": "now",
    }))
    assert release_receipt_matches_artifact(receipt, _artifact()) is True
    assert release_receipt_matches_artifact(receipt, _artifact(artifact_id="other")) is False
    assert release_receipt_matches_artifact(receipt, _artifact(commit="different")) is False
    assert release_receipt_matches_artifact(receipt, _artifact(version="9.9.9")) is False


def test_invalid_or_missing_receipt_never_suppresses_install(tmp_path: Path):
    receipt = tmp_path / ".timelapse-release.json"
    assert release_receipt_matches_artifact(receipt, _artifact()) is False
    receipt.write_text("not json")
    assert release_receipt_matches_artifact(receipt, _artifact()) is False


def test_restore_previous_release_includes_dotfiles_removes_new_outputs_and_verifies_receipt(tmp_path: Path):
    repo = tmp_path / "timelapse"
    prev = repo / "prev"
    (prev / "edge").mkdir(parents=True)
    (repo / "edge").mkdir(parents=True)

    (prev / "edge" / "agent.py").write_text("old-agent")
    (prev / "edge" / ".hidden-config").write_text("old-hidden")
    (repo / "edge" / "agent.py").write_text("new-agent")
    (repo / "edge" / "new_feature.py").write_text("new-only")

    previous_receipt = {
        "schema": "timelapse.edge.release.v1",
        "artifact_id": "TL-ART-PREV",
        "source_commit": "prev",
        "version": "1.0",
    }
    (prev / "edge" / ".timelapse-release.json").write_text(json.dumps(previous_receipt))
    (repo / "edge" / ".timelapse-release.json").write_text(json.dumps({"artifact_id": "current"}))

    result = restore_previous_app_release(
        repo,
        _artifact(outputs=[
            {"path": "edge/agent.py"},
            {"path": "edge/new_feature.py"},
        ]),
    )

    assert (repo / "edge" / "agent.py").read_text() == "old-agent"
    assert (repo / "edge" / ".hidden-config").read_text() == "old-hidden"
    assert not (repo / "edge" / "new_feature.py").exists()
    assert json.loads((repo / "edge" / ".timelapse-release.json").read_text()) == previous_receipt
    assert result["removed_new_files"] == 1
    assert result["receipt"] == previous_receipt


def test_restore_without_previous_receipt_removes_current_receipt(tmp_path: Path):
    repo = tmp_path / "timelapse"
    (repo / "prev" / "edge").mkdir(parents=True)
    (repo / "edge").mkdir(parents=True)
    (repo / "prev" / "edge" / "agent.py").write_text("old")
    receipt = repo / "edge" / ".timelapse-release.json"
    receipt.write_text("{}")

    restore_previous_app_release(repo)
    assert not receipt.exists()


def test_unsafe_rollback_artifact_path_fails_closed(tmp_path: Path):
    repo = tmp_path / "timelapse"
    (repo / "prev").mkdir(parents=True)
    with pytest.raises(ValueError):
        restore_previous_app_release(repo, _artifact(outputs=[{"path": "edge/../../etc/passwd"}]))


def test_agent_uses_receipt_guard_and_safe_rollback_helper():
    source = Path("edge/agent.py").read_text(encoding="utf-8")
    assert "release_receipt_matches_artifact(" in source
    assert "restore_previous_app_release(" in source
    rollback_start = source.index("    def _run_rollback(")
    rollback_end = source.index("    def _send_heartbeat(", rollback_start)
    rollback = source[rollback_start:rollback_end]
    assert 'bash", "-c"' not in rollback
    assert "os_forced_rollback_not_supported" in rollback
    assert '"blocked", "rollback_source_missing"' in rollback
