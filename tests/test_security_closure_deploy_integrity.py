"""Kimi F-003 + Claude deploy safety contracts."""

from pathlib import Path


CI = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def test_deploy_is_bound_to_exact_workflow_sha():
    assert 'git checkout --detach "${{ github.sha }}"' in CI
    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in CI
    assert 'if [ "$ACTUAL_SHA" != "${{ github.sha }}" ]; then' in CI


def test_decorative_latest_tag_verification_is_removed():
    assert 'LATEST_TAG=$(git tag --sort=-version:refname | head -1)' not in CI
    assert 'springer signaturcheck over' not in CI


def test_ui_is_built_before_restart():
    build_pos = CI.index('name: Build UI for target revision before backend restart')
    restart_pos = CI.index('name: Restart Headend and verify health or rollback')
    assert build_pos < restart_pos
    assert 'npm ci --silent' in CI[build_pos:restart_pos]


def test_post_restart_health_and_automatic_rollback_are_mandatory():
    assert 'http://127.0.0.1:8000/api/health' in CI
    assert 'rolling back application code' in CI
    assert 'git checkout --detach "$PREVIOUS_SHA"' in CI
    assert 'exit 1' in CI[CI.index('name: Restart Headend and verify health or rollback'):]
