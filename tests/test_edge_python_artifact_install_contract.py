"""Contract tests for edge/agent.py's _run_artifact_python_update(): the same
safety properties already contract-tested for _run_artifact_os_update() (see
test_edge_release_contract.py) — offline-only, sha256-verified, no network
commands baked into the install path, and (specific to Python) always targets
Edge's own venv interpreter explicitly rather than a bare "python3"/"pip3"
resolved via PATH (the exact bug class fixed 2026-09-04 in
edge/utils/inventory.py's _venv_packages()).
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _python_install_block() -> str:
    source = _source("edge/agent.py")
    start = source.index("def _run_artifact_python_update(")
    end = source.index("\n    def _run_rollback(", start)
    return source[start:end]


def test_python_install_validates_artifact_schema_and_distribution_model():
    block = _python_install_block()
    assert '"timelapse.python_update_artifact.v1"' in block
    assert '"headend_signed_offline_python_bundle_edge_pull"' in block


def test_python_install_verifies_sha256_per_downloaded_file():
    block = _python_install_block()
    assert "actual = _hashlib.sha256(content).hexdigest()" in block
    assert 'raise RuntimeError(f"sha256 mismatch: {rel}")' in block


def test_python_install_rejects_unsafe_artifact_paths():
    block = _python_install_block()
    assert 'rel.startswith("/")' in block
    assert '".." in Path(rel).parts' in block


def test_python_install_forbids_network_commands_in_bundle_scripts():
    block = _python_install_block()
    assert r"curl|wget|scp|rsync" in block
    assert r"git\s+(clone|pull|fetch)" in block
    assert "--index-url" in block


def test_python_install_requires_no_index_and_venv_python_for_pip_install_lines():
    block = _python_install_block()
    assert '"--no-index" not in stripped' in block
    assert "EDGE_VENV_PYTHON = \"/opt/timelapse/venv/bin/python3\"" in block
    assert "EDGE_VENV_PYTHON not in stripped" in block


def test_python_install_takes_a_pre_update_backup_before_installing():
    block = _python_install_block()
    assert '_create_edge_backup_archive(f"pre-python-update-{update_id}")' in block
    assert "upload_edge_backup" in block


def test_python_install_runs_via_systemd_run_isolation():
    block = _python_install_block()
    assert "/usr/bin/systemd-run" in block
    assert 'f"--unit=timelapse-python-update-{update_id}"' in block


def test_python_install_reports_terminal_status_on_success_and_failure():
    block = _python_install_block()
    assert 'self._report_update(update_id, "deployed")' in block
    assert 'self._report_update(update_id, "blocked", str(exc)[:700])' in block


def test_dispatch_routes_dependency_types_to_python_installer():
    source = _source("edge/agent.py")
    dispatch = source[source.index("def _run_update("):source.index("def _report_update(")]
    assert 'update_type in ("dependency_security", "dependency_updates")' in dispatch
    assert "self._run_artifact_python_update(update_id, artifact)" in dispatch


def test_rollback_explicitly_blocks_dependency_updates():
    source = _source("edge/agent.py")
    rollback = source[source.index("def _run_rollback("):source.index("def _run_rollback(") + 1500]
    assert 'update_type in ("dependency_security", "dependency_updates")' in rollback
    assert "python_forced_rollback_not_supported" in rollback
