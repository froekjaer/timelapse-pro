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


def test_deploy_uses_dedicated_worktree_not_the_interactive_checkout():
    deploy_job = CI[CI.index('deploy-macmini:'):]
    assert '~/projects/timelapse-pro-deploy' in deploy_job
    assert '~/projects/timelapse-pro/' not in deploy_job
    assert 'timelapse-pro-deploy"' in deploy_job  # REPO="$HOME/projects/timelapse-pro-deploy"


def test_deploy_is_manual_only_pending_headend_env_cutover():
    """Temporary gate (2026-09-08): the running Headend process still reads
    its code from the OLD checkout path unless/until TIMELAPSE_HEADEND_WORKDIR
    is set in /etc/timelapse/headend.env. Automatic push-triggered deploy
    must stay off until that live cutover is done, or a merge could deploy
    into the new checkout while the live process keeps serving code from the
    old one. Update this test in the same follow-up PR that flips the gate
    back to automatic — don't just delete it."""
    assert 'workflow_dispatch' in CI[:CI.index('jobs:')]
    deploy_job = CI[CI.index('deploy-macmini:'):]
    condition = deploy_job[deploy_job.index('if:'):deploy_job.index('steps:')]
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "github.event_name == 'push'" not in condition
