from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "deploy" / "install" / "bootstrap_headend_macos.sh"
INSTALLER = ROOT / "deploy" / "install" / "install_headend.sh"
ORCHESTRATOR = ROOT / "deploy" / "install" / "headend_generator.sh"
NODE_AGENT_INSTALLER = ROOT / "node-agent" / "install" / "macos.sh"


def test_bootstrap_is_pinned_and_verifies_signed_tag() -> None:
    source = SCRIPT.read_text()
    assert "verify-tag" in source
    assert "expected-commit" in source
    assert "rev-list -n1" in source
    assert "checkout --detach" in source


def test_bootstrap_preserves_existing_software() -> None:
    source = SCRIPT.read_text()
    assert "brew upgrade" not in source
    assert "brew install" not in source
    assert "softwareupdate" not in source
    assert "--dry-run" in source
    for port in ("21", "22", "80", "443"):
        assert port in source


def test_bootstrap_collects_coexistence_evidence() -> None:
    source = SCRIPT.read_text()
    assert "LaunchDaemons" in source
    assert "lsof" in source
    assert "homebrew_inventory" in source
    assert "backend_port_free" in source


def test_installer_uses_dedicated_least_privilege_identity() -> None:
    source = INSTALLER.read_text()
    assert "TL_SERVICE_USER:=_timelapse" in source
    assert "UserShell /usr/bin/false" in source
    assert "IsHidden 1" in source
    assert "<string>${TL_SERVICE_USER}</string>" in source
    assert "<key>UserName</key><string>$(whoami)</string>" not in source


def test_installer_does_not_replace_or_reload_global_nginx() -> None:
    source = INSTALLER.read_text()
    assert 'NGINX_CONF="$ENV_DIR/nginx-headend.conf"' in source
    assert "dk.froekjaer.timelapse-nginx" in source
    assert 'NGINX_CONF="$NGINX_CONF_DIR/nginx.conf"' not in source
    assert "pgrep -x nginx" not in source
    assert "nginx -s reload" not in source


def test_mutating_phases_reverify_tag_commit_and_destination() -> None:
    source = ORCHESTRATOR.read_text()
    assert 'git -C "$DESTINATION" verify-tag "$RELEASE_TAG"' in source
    assert '"${TL_REPO_DIR:A}" == "${DESTINATION:A}"' in source
    assert 'tag_commit="$(git -C "$DESTINATION" rev-list -n1 "$RELEASE_TAG"' in source


def test_node_agent_uses_explicit_non_root_service_identity() -> None:
    source = NODE_AGENT_INSTALLER.read_text()
    assert "--service-user" in source
    assert '"$(id -u "$SERVICE_USER")" != "0"' in source
    assert "<string>$SERVICE_USER</string>" in source
    assert "pip\" install --quiet --upgrade pip" not in source


def test_new_headend_uses_unique_initial_admin_secret() -> None:
    source = INSTALLER.read_text()
    assert "TIMELAPSE_INITIAL_ADMIN_PASSWORD" in source
    assert "openssl rand -base64" in source
    assert "admin / changeme" not in source


def test_installer_configures_non_reserved_tunnel_ingress() -> None:
    source = INSTALLER.read_text()
    assert "TL_TUNNEL_PORT:=22222" in source
    assert "TIMELAPSE_TUNNEL_USER=${TL_TUNNEL_USER}" in source
    assert "SFTP_PORT=22222" in source


def test_installer_validation_is_bash_syntax_check_compatible() -> None:
    source = INSTALLER.read_text()
    assert "<->" not in source
    assert r"=~ ^[0-9]+$" in source
