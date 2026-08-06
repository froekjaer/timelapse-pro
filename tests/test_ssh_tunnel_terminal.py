"""Regression test (2026-08-06): Peter asked for an in-browser SSH client in
Admin -> SSH Tunnels, mirroring the edge's own xterm.js break-glass terminal
(edge/scripts/totp-service.py) — a clickable terminal icon alongside the
existing copy-command option. headend/api/ssh_tunnel_terminal_api.py is
headend acting as the SSH client itself, connecting through the already-
established reverse tunnel (localhost:<device.reverse_tunnel_port>) with the
shared timelapse_headend_ed25519 key (same key/model as
api/device_ssh_access_api.py's break-glass fallback, which Peter separately
asked about the same day) via paramiko's invoke_shell().

New module from the start (not added to main.py) — same-day lesson from
Peter: the architecture-ratchet baseline exists to force this.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "headend" / "api" / "ssh_tunnel_terminal_api.py").read_text(encoding="utf-8")
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
NGINX_CONF = (ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")


def test_terminal_endpoint_requires_admin_role() -> None:
    assert 'user.role not in ("super_admin", "admin")' in SOURCE


def test_terminal_connects_through_the_reverse_tunnel_with_the_shared_key() -> None:
    assert '"localhost", port=int(device.reverse_tunnel_port)' in SOURCE
    assert '_HEADEND_KEY_PATH = Path.home() / ".ssh" / "timelapse_headend_ed25519"' in SOURCE


def test_terminal_session_open_and_close_are_audited() -> None:
    assert 'category="security"' in SOURCE
    assert "SSH-terminal åbnet" in SOURCE
    assert "SSH-terminal lukket" in SOURCE


def test_terminal_router_is_included_from_main() -> None:
    assert "from api.ssh_tunnel_terminal_api import router as _ssh_tunnel_terminal_router" in MAIN
    assert "app.include_router(_ssh_tunnel_terminal_router)" in MAIN


def test_nginx_proxies_websocket_upgrade_for_the_terminal_endpoint() -> None:
    # 2026-08-06: the general 'location /api/' blocks do not forward Upgrade/
    # Connection headers (only the openwebui :8080 blocks did) — without a
    # dedicated location for this path, the browser's WebSocket handshake
    # would fail silently through nginx. Must be present in BOTH server
    # blocks (:443 and :8443), matching /api/thumbnails//api/images/'s
    # existing dedicated-location pattern.
    assert NGINX_CONF.count("location ^~ /api/admin/ssh-tunnel/") == 2
    assert "proxy_set_header Upgrade    $http_upgrade;" in NGINX_CONF
