from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

API = (ROOT / "headend/api/ssh_tunnel_terminal_api.py").read_text(encoding="utf-8")
MAIN = (ROOT / "headend/main.py").read_text(encoding="utf-8")
DB = (ROOT / "headend/database.py").read_text(encoding="utf-8")
MIGRATION = (ROOT / "headend/migrations/v32_ssh_tunnel_terminal_trust.sql").read_text(encoding="utf-8")
UI_PAGE = (ROOT / "timelapse-ui/src/pages/SshTunnelPage.tsx").read_text(encoding="utf-8")
UI_MODAL = (ROOT / "timelapse-ui/src/components/SshTerminalModal.tsx").read_text(encoding="utf-8")


def test_external_ssh_command_includes_identity_key_path() -> None:
    assert "ssh -p {int(remote_port)} -i {key_path or ssh_identity_display_path()}" in API
    assert "ssh_command" in MAIN
    assert "terminal_trust_status(db, r[0])" in MAIN
    assert "-i ${t.ssh_identity_path" in UI_PAGE
    assert "~/.ssh/timelapse_headend_ed25519" in UI_PAGE


def test_private_key_material_is_never_returned_to_ssh_tunnel_ui() -> None:
    active_block = MAIN.split("@app.get(\"/api/ssh-tunnel/active\")", 1)[1].split("@app.get(\"/api/ssh-tunnel/log", 1)[0]
    assert "ssh_identity_path" in active_block
    assert "ssh_private_key" not in active_block
    assert "private_key" not in UI_PAGE


def test_terminal_uses_new_trust_and_service_model_not_auto_add_policy() -> None:
    assert "evaluate_legacy_role_capability_check" in API
    assert "issue_edge_service_grant" in API
    assert "validate_edge_service_grant" in API
    assert "CAPABILITY = \"edge.shell.remote\"" in API
    assert "mfa_required=True" in API
    assert "if not mfa_verified" in API
    assert "paramiko.RejectPolicy()" in API
    assert "AutoAddPolicy" not in API
    assert "StrictHostKeyChecking=no" not in API


def test_viewer_and_technician_without_shell_capability_are_denied_by_policy() -> None:
    from trust.models import PolicyRequest, Principal
    from trust.policy import evaluate_policy, principal_from_legacy_user

    viewer = Principal(username="viewer", role="viewer", mfa_verified=True)
    viewer_decision = evaluate_policy(PolicyRequest(
        principal=viewer,
        action="grant.issue",
        resource="edge:remote-shell",
        capability="edge.shell.remote",
        mfa_required=True,
    ))
    assert not viewer_decision.allowed

    class Technician:
        username = "tech"
        role = "operator"
        id = 7
        customer_id = None
        on_site_service = True

    technician = principal_from_legacy_user(Technician(), mfa_verified=True)
    technician_decision = evaluate_policy(PolicyRequest(
        principal=technician,
        action="grant.issue",
        resource="edge:remote-shell",
        capability="edge.shell.remote",
        mfa_required=True,
    ))
    assert not technician_decision.allowed


def test_authorized_admin_and_engineer_have_shell_capability() -> None:
    from trust.models import PolicyRequest, Principal
    from trust.policy import evaluate_policy

    for role in ("admin", "engineer", "super_admin"):
        decision = evaluate_policy(PolicyRequest(
            principal=Principal(username=role, role=role, mfa_verified=True),
            action="grant.issue",
            resource="edge:remote-shell",
            capability="edge.shell.remote",
            mfa_required=True,
        ))
        assert decision.allowed


def test_untrusted_or_mismatched_ssh_host_key_denies_terminal() -> None:
    assert "TRUSTED_HOST_STATES = {\"trusted\", \"verified\"}" in API
    assert "untrusted or mismatched SSH host key denied" in API
    assert "disabled={!t.terminal?.allowed}" in UI_PAGE
    assert "ssh_host_key_trust" in MIGRATION
    assert "trusted_state" in MIGRATION
    assert "must not update known_hosts" in MIGRATION
    assert "ssh-keygen -R" not in API
    assert "known_hosts =" not in API


def test_expired_or_revoked_grant_closes_or_denies_session() -> None:
    assert "grant.status != \"active\"" in API
    assert "EdgeServiceGrant revoked" in API
    assert "EdgeServiceGrant expired" in API
    assert "await asyncio.sleep(1.0)" in API


def test_session_is_bound_to_requested_edge_and_terminal_lifecycle_is_audited() -> None:
    assert "filter_by(session_id=session_id, device_id=device_id)" in API
    assert "edge_id=device_id" in API
    assert "resource=f\"edge:{device_id}:remote-shell\"" in API
    assert "SshTerminalSessionAudit" in DB
    assert "principal" in DB
    assert "grant_id" in DB
    assert "started_at" in DB
    assert "ended_at" in DB
    assert "SSH terminal opened" in API
    assert "SSH terminal closed" in API


def test_ui_has_browser_terminal_modal_bound_to_backend_session() -> None:
    assert "SshTerminalModal" in UI_PAGE
    assert "/terminal-sessions" in UI_MODAL
    assert "websocket_path" in UI_MODAL
    assert "credentials: 'include'" in UI_MODAL


def test_terminal_router_is_included_without_direct_main_route_growth() -> None:
    assert "create_ssh_tunnel_terminal_router" in MAIN
    assert "app.include_router(create_ssh_tunnel_terminal_router" in MAIN
    assert "@app.websocket(\"/api/admin/ssh-tunnel" not in MAIN
