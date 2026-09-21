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
TUNNEL_HELPER = (ROOT / "deploy/macos/timelapse-tunnel-control").read_text(encoding="utf-8")
INSTALLER = (ROOT / "deploy/install/install_headend.sh").read_text(encoding="utf-8")
TUNNEL_INSTALLER = (ROOT / "deploy/macos/install_tunnel_control.sh").read_text(encoding="utf-8")
EDGE_TUNNEL = (ROOT / "edge/tunnel/ssh_manager.py").read_text(encoding="utf-8")
EDGE_AGENT = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "edge/tools/bootstrap_cli.py").read_text(encoding="utf-8")
TOTP_SERVICE = (ROOT / "edge/scripts/totp-service.py").read_text(encoding="utf-8")


def test_external_ssh_command_includes_identity_key_path() -> None:
    assert "ssh -p {int(remote_port)} -i {key_path or ssh_identity_display_path()}" in API
    assert '"ssh_command"' in API
    assert "terminal_trust_status(db, row[0], tunnel_reachable=True)" in API
    assert "-i ${t.ssh_identity_path" in UI_PAGE
    assert "~/.ssh/timelapse_headend_ed25519" in UI_PAGE


def test_failed_reconnect_must_not_hide_a_live_tunnel() -> None:
    active_block = API.split("def active_reverse_tunnels", 1)[1].split("def _force_close_reverse_tunnel", 1)[0]
    assert 'WHERE event = \'connected\'' in active_block
    assert "_localhost_ssh_banner_reachable(int(row[1]))" in active_block


def test_active_tunnel_separates_connect_event_from_fresh_verification() -> None:
    active_block = API.split("def active_reverse_tunnels", 1)[1].split("def _force_close_reverse_tunnel", 1)[0]
    assert '"connected_at": row[3]' in active_block
    assert '"last_verified_at": verified_at' in active_block
    assert '"verification_method": "headend_ssh_banner_probe"' in active_block
    assert "(row, now_utc())" in active_block
    assert "Oprettet {fmt(t.connected_at)}" in UI_PAGE
    assert "Senest verificeret fra Headend {fmt(t.last_verified_at)}" in UI_PAGE


def test_tunnel_liveness_probes_localhost_ipv4_and_ipv6():
    helper = API.split("def _localhost_ssh_banner_reachable", 1)[1].split("def _active_reverse_tunnel", 1)[0]
    assert 'socket.getaddrinfo(\n        "localhost"' in helper
    assert "socket.socket(family, socktype, proto)" in helper
    assert '"127.0.0.1"' not in helper


def test_terminal_status_ignores_failed_retry_when_connected_event_is_reachable():
    helper = API.split("def _active_reverse_tunnel", 1)[1].split("def _deny_terminal", 1)[0]
    assert '.filter(SshTunnelLog.event == "connected")' in helper
    assert "latest.event != \"connected\"" not in helper


def test_private_key_material_is_never_returned_to_ssh_tunnel_ui() -> None:
    active_block = API.split("def active_reverse_tunnels", 1)[1].split("def _force_close_reverse_tunnel", 1)[0]
    assert "ssh_identity_path" in active_block
    assert "ssh_private_key" not in active_block
    assert "private_key" not in UI_PAGE


def test_servicetekniker_command_template_is_a_placeholder_not_a_real_key():
    """2026-08-25: the "login as servicetekniker" convenience command is a
    template the operator fills in themselves — headend never has their
    personal private key, so it must never emit anything but the literal
    placeholder token here."""
    active_block = API.split("def active_reverse_tunnels", 1)[1].split("def _force_close_reverse_tunnel", 1)[0]
    assert "servicetekniker_command" in active_block
    assert "device_ip" in active_block
    assert "<din-private-nøgle>" in active_block
    assert "servicetekniker_command" in UI_PAGE


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


def test_force_close_is_device_scoped_audited_and_least_privilege() -> None:
    assert '@router.post("/{device_id}/force-close")' in API
    assert '.filter(SshTunnelLog.device_id == device_id)' in API
    assert 'getattr(user, "role", "") not in {"super_admin", "admin"}' in API
    assert 'event="force_closed"' in API
    assert 'initiated_by=f"admin:{user.username}"' in API
    assert '["/usr/bin/sudo", "-n", TUNNEL_CONTROL_HELPER, "close", str(int(port))]' in API
    assert "verified_session_pid" in TUNNEL_HELPER
    assert 'arguments.startswith(f"sshd-session: {expected_user}")' in TUNNEL_HELPER
    assert "os.kill(pid, signal.SIGTERM)" in TUNNEL_HELPER
    assert "SIGKILL" not in TUNNEL_HELPER
    assert "install_tunnel_control.sh" in INSTALLER
    assert "NOPASSWD: %s close *" in TUNNEL_INSTALLER
    assert "visudo -cf" in TUNNEL_INSTALLER


def test_network_switch_closes_tunnel_before_wifi_mutation() -> None:
    assert "pause_for_network_change" in EDGE_TUNNEL
    assert "resume_after_network_change" in EDGE_TUNNEL
    request_connect = EDGE_TUNNEL.split("def request_connect", 1)[1].split("def pause_for_network_change", 1)[0]
    assert request_connect.index("with self._lock") < request_connect.index("if should_connect")
    assert "self._connect()" in request_connect.split("if should_connect", 1)[1]
    wifi_block = EDGE_AGENT.split('elif cmd_type == "wifi_connect":', 1)[1].split('elif cmd_type == "wifi_forget":', 1)[0]
    assert wifi_block.index("pause_for_network_change") < wifi_block.index("connect(ssid, password)")
    assert wifi_block.index("connect(ssid, password)") < wifi_block.index("resume_after_network_change")
    local_wifi = BOOTSTRAP.split("def connect_wifi", 1)[1].split("def configure_ipv4", 1)[0]
    assert local_wifi.index('"stop", "timelapse-edge.service"') < local_wifi.index("result = run(cmd")
    assert '"start", "timelapse-edge.service"' in local_wifi


def test_service_ui_listens_on_all_edge_network_interfaces() -> None:
    assert 'host="0.0.0.0"' in TOTP_SERVICE
    assert 'port=https_port' in TOTP_SERVICE
