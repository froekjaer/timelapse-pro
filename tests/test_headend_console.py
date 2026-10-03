"""Headend console in the UI (Peter, 2026-10-03): only super admin with an
MFA-verified session, and only through the admin SSH door (password + TOTP on
127.0.0.1:9122, host key pinned) — never a second way in."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from api import headend_console_api as hc  # noqa: E402
from database import get_db  # noqa: E402


def _app(role="super_admin", mfa=True):
    audits = []
    user = SimpleNamespace(username="peter", role=role, is_active=True)
    app = FastAPI()
    app.include_router(hc.create_headend_console_router(
        lambda _req, _db: user,
        lambda _req: {"mfa": mfa},
        lambda payload: bool(payload and payload.get("mfa")),
        lambda _db, _dev, events: audits.extend(events),
    ))
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(commit=lambda: None)
    return TestClient(app), audits


@pytest.mark.parametrize("role,mfa,code", [("admin", True, 403), ("operator", True, 403), ("super_admin", False, 403)])
def test_only_mfa_verified_super_admin(role, mfa, code):
    client, _ = _app(role, mfa)
    assert client.post("/api/admin/headend-console/sessions").status_code == code


def test_ssh_command_uses_admin_door_with_pinned_host_key(tmp_path):
    cmd = hc.ssh_command(tmp_path / "kh")
    joined = " ".join(cmd)
    assert cmd[0] == hc.SSH_BIN and "-p 9122" in joined and cmd[-1].endswith("@127.0.0.1")
    assert "StrictHostKeyChecking=yes" in joined and f"UserKnownHostsFile={tmp_path / 'kh'}" in joined
    assert "PubkeyAuthentication=no" in joined and "PreferredAuthentications=keyboard-interactive" in joined


def test_pinned_known_hosts(tmp_path, monkeypatch):
    pub = tmp_path / "host.pub"
    pub.write_text("ssh-ed25519 AAAAKEY root@host\n")
    monkeypatch.setattr(hc, "ADMIN_HOST_KEY_PUB", pub)
    kh = hc.pinned_known_hosts()
    try:
        assert kh.read_text() == "[127.0.0.1]:9122 ssh-ed25519 AAAAKEY\n"
        assert oct(kh.stat().st_mode & 0o777) == "0o600"
    finally:
        kh.unlink()


def test_session_flow_single_use_and_audited(tmp_path, monkeypatch):
    pub = tmp_path / "host.pub"
    pub.write_text("ssh-ed25519 AAAAKEY\n")
    monkeypatch.setattr(hc, "ADMIN_HOST_KEY_PUB", pub)
    monkeypatch.setattr(hc, "SSH_BIN", "/bin/echo")
    monkeypatch.setattr(hc, "ssh_command", lambda _kh, _ident=None: ["/bin/echo", "Password:"])
    client, audits = _app()
    started = client.post("/api/admin/headend-console/sessions").json()
    assert started["target"].endswith("@127.0.0.1:9122")
    with client.websocket_connect(started["websocket_path"]) as ws:
        # ssh's output must arrive even though the process has already exited
        assert "Password:" in ws.receive_text()
    import time
    for _ in range(50):   # the server side closes in its own thread
        if audits and audits[-1]["event_type"] == "headend_console_closed":
            break
        time.sleep(0.05)
    types = [a["event_type"] for a in audits]
    assert types[:2] == ["headend_console_requested", "headend_console_opened"] and types[-1] == "headend_console_closed"
    with pytest.raises(Exception):
        with client.websocket_connect(started["websocket_path"]) as ws:   # single use
            ws.receive_text()


def test_registered_in_main_without_new_direct_route():
    src = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    assert "create_headend_console_router(get_current_user, _session_payload, _session_is_mfa_verified, _siem_record_events, _webauthn_settings)" in src
    assert "@app.websocket(\"/api/admin/headend-console" not in src
