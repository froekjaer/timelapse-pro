"""Remote admin SSH for the Headend (TCP/9122): macOS password + TOTP, both
during PAM keyboard-interactive auth; only forward = 127.0.0.1:5900.
Peter 2026-10-01; see Dokumentation/ADMIN_REMOTE_ACCESS_9122_2026-10-01.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = (ROOT / "deploy/ssh/timelapse-admin-sshd.conf").read_text(encoding="utf-8")
INSTALLER = (ROOT / "deploy/ssh/install_timelapse_admin_sshd.sh").read_text(encoding="utf-8")


def _d():
    out = {}
    for line in CONF.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            k, _, v = line.partition(" ")
            out.setdefault(k, []).append(v.strip())
    return out


def test_second_factor_is_part_of_authentication():
    d = _d()
    assert int(d["Port"][0]) < 10000
    assert d["AuthenticationMethods"] == ["keyboard-interactive"]
    assert d["KbdInteractiveAuthentication"] == ["yes"] and d["UsePAM"] == ["yes"]
    assert d["PasswordAuthentication"] == ["no"] and d["PubkeyAuthentication"] == ["no"]
    assert d["AllowUsers"] == ["__ADMIN_USER__"] and d["PermitRootLogin"] == ["no"]
    assert "ForceCommand" not in d


def test_only_forward_is_local_screen_sharing():
    d = _d()
    assert d["AllowTcpForwarding"] == ["local"]
    assert d["PermitOpen"] == ["127.0.0.1:5900 localhost:5900"]
    assert d["PermitListen"] == ["none"] and d["GatewayPorts"] == ["no"]
    assert d["AllowStreamLocalForwarding"] == ["no"] and d["PermitTunnel"] == ["no"]
    assert d["AllowAgentForwarding"] == ["no"] and d["X11Forwarding"] == ["no"]
    assert d["PermitUserEnvironment"] == ["no"] and "AcceptEnv" not in d


def test_installer_refuses_password_only_and_uses_root_owned_module():
    assert 'PAM_MODULE="/usr/local/lib/pam/pam_google_authenticator.so"' in INSTALLER
    assert "/opt/homebrew" not in INSTALLER.split("PAM_MODULE=", 1)[1].split("\n", 1)[0]
    assert 'check_totp_prereqs || die' in INSTALLER
    assert "8#022" in INSTALLER  # module must not be group/world-writable
