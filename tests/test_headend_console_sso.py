"""Headend console passkey SSO (Peter, 2026-10-03): a fresh passkey assertion
when opening the console mints a one-off SSH certificate (~2 min, principal =
admin user, source-address 127.0.0.1, pty only) that the admin sshd accepts
ONLY from 127.0.0.1; from the internet 9122 stays password + TOTP."""
import shutil
import subprocess
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

needs_keygen = pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="ssh-keygen missing")


@pytest.fixture
def ca(tmp_path, monkeypatch):
    key = tmp_path / "ca"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    monkeypatch.setattr(hc, "CONSOLE_CA_KEY", key)
    monkeypatch.setattr(hc, "SSH_KEYGEN", shutil.which("ssh-keygen"))
    monkeypatch.setattr(hc, "admin_ssh_user", lambda: "peter")
    hc._stepup.clear()
    hc._pending.clear()
    return key


def _client(monkeypatch, creds=()):
    cred_rows = [SimpleNamespace(credential_id=b"cred1", public_key=b"pk", sign_count=1, rp_id="backend.example")] if creds else []

    class _Q:
        def filter_by(self, **_):
            return self

        def all(self):
            return cred_rows

    db = SimpleNamespace(commit=lambda: None, query=lambda _m: _Q())
    user = SimpleNamespace(id=1, username="peter", role="super_admin", is_active=True)
    audits = []
    app = FastAPI()
    app.include_router(hc.create_headend_console_router(
        lambda _r, _d: user, lambda _r: {"m": 1}, lambda p: True,
        lambda _db, _dev, ev: audits.extend(ev),
        lambda _db, _req: ("backend.example", "TimeLapse", "https://backend.example"),
    ))
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr("services.webauthn_origin.credential_descriptors",
                        lambda rows, rp: [object()] if rows else [])
    return TestClient(app), audits, cred_rows


def test_stepup_unavailable_without_ca(monkeypatch, tmp_path):
    monkeypatch.setattr(hc, "CONSOLE_CA_KEY", tmp_path / "missing")
    client, _, _ = _client(monkeypatch, creds=True)
    r = client.post("/api/admin/headend-console/stepup/begin").json()
    assert r["available"] is False


@needs_keygen
def test_stepup_unavailable_without_passkey(monkeypatch, ca):
    client, _, _ = _client(monkeypatch, creds=False)
    assert client.post("/api/admin/headend-console/stepup/begin").json()["available"] is False


@needs_keygen
def test_assertion_without_challenge_is_rejected(monkeypatch, ca):
    client, _, _ = _client(monkeypatch, creds=True)
    r = client.post("/api/admin/headend-console/sessions", json={"assertion": {"rawId": "Y3JlZDE"}})
    assert r.status_code == 403


@needs_keygen
def test_passkey_session_mints_restricted_certificate_and_cleans_up(monkeypatch, ca, tmp_path):
    import webauthn

    client, audits, rows = _client(monkeypatch, creds=True)
    monkeypatch.setattr(webauthn, "generate_authentication_options",
                        lambda **kw: SimpleNamespace(challenge=b"chal", **kw))
    monkeypatch.setattr(webauthn, "options_to_json", lambda o: '{"challenge": "Y2hhbA"}')
    seen = {}

    def verify(**kw):
        seen.update(kw)
        return SimpleNamespace(new_sign_count=2)

    monkeypatch.setattr(webauthn, "verify_authentication_response", verify)
    begin = client.post("/api/admin/headend-console/stepup/begin").json()
    assert begin["available"] is True
    r = client.post("/api/admin/headend-console/sessions", json={"assertion": {"rawId": "Y3JlZDE"}}).json()
    assert r["login"] == "passkey"
    assert seen["require_user_verification"] is True and seen["expected_challenge"] == b"chal"
    assert rows[0].sign_count == 2
    workdir = Path(hc._pending[r["session_id"]]["workdir"])
    cert = subprocess.run(["ssh-keygen", "-L", "-f", str(workdir / "id_ed25519-cert.pub")], capture_output=True, text=True).stdout
    assert "peter" in cert and "source-address 127.0.0.1" in cert and "permit-pty" in cert
    assert "permit-port-forwarding" not in cert and "permit-agent-forwarding" not in cert
    # challenge is single use
    assert client.post("/api/admin/headend-console/sessions", json={"assertion": {"rawId": "Y3JlZDE"}}).status_code == 403
    # websocket uses the certificate and removes the one-off key afterwards
    pub = tmp_path / "host.pub"
    pub.write_text("ssh-ed25519 AAAAKEY\n")
    monkeypatch.setattr(hc, "ADMIN_HOST_KEY_PUB", pub)
    used = {}
    monkeypatch.setattr(hc, "ssh_command", lambda kh, ident=None: (used.setdefault("ident", ident), ["/bin/echo", "SSO"])[1])
    with client.websocket_connect(r["websocket_path"]) as ws:
        assert "SSO" in ws.receive_text()
    import time
    for _ in range(50):
        if not workdir.exists():
            break
        time.sleep(0.05)
    assert used["ident"] == workdir / "id_ed25519" and not workdir.exists()


def test_ssh_command_identity_mode(tmp_path):
    cmd = " ".join(hc.ssh_command(tmp_path / "kh", tmp_path / "id"))
    assert "PreferredAuthentications=publickey" in cmd and "IdentitiesOnly=yes" in cmd
    assert f"CertificateFile={tmp_path / 'id'}-cert.pub" in cmd and "IdentityAgent=none" in cmd
    assert "keyboard-interactive" not in cmd


def test_sshd_config_trusts_ca_only_from_localhost():
    conf = (ROOT / "deploy/ssh/timelapse-admin-sshd.conf").read_text(encoding="utf-8")
    head, _, match = conf.partition("Match Address 127.0.0.1")
    assert "AuthenticationMethods keyboard-interactive\n" in head and "PubkeyAuthentication no" in head
    assert "PubkeyAuthentication yes" in match and "AuthorizedKeysFile none" in match
    assert "AuthenticationMethods publickey keyboard-interactive" in match
    assert "TrustedUserCAKeys /etc/ssh/timelapse-admin/console_user_ca.pub" in head


@pytest.mark.skipif(not Path("/usr/sbin/sshd").exists() or not shutil.which("ssh-keygen"), reason="sshd missing")
def test_sshd_effective_policy_local_vs_internet(tmp_path):
    for name in ("hk", "ca"):
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(tmp_path / name)], check=True)
    conf = (ROOT / "deploy/ssh/timelapse-admin-sshd.conf").read_text(encoding="utf-8")
    conf = conf.replace("__ADMIN_USER__", "peter")
    import re
    conf = re.sub(r"^HostKey .*", f"HostKey {tmp_path / 'hk'}", conf, flags=re.M)
    conf = re.sub(r"^TrustedUserCAKeys .*", f"TrustedUserCAKeys {tmp_path / 'ca.pub'}", conf, flags=re.M)
    conf = re.sub(r"^PidFile .*", f"PidFile {tmp_path / 'pid'}", conf, flags=re.M)
    (tmp_path / "c").write_text(conf)

    def effective(addr):
        out = subprocess.run(["/usr/sbin/sshd", "-T", "-f", str(tmp_path / "c"), "-C", f"user=peter,host=x,addr={addr}"],
                             capture_output=True, text=True).stdout
        return {l.split(" ", 1)[0]: l.split(" ", 1)[1] for l in out.splitlines() if " " in l}

    local, remote = effective("127.0.0.1"), effective("203.0.113.9")
    if not local:
        pytest.skip("sshd -T unavailable")
    assert local["authenticationmethods"] == "publickey keyboard-interactive" and local["authorizedkeysfile"] == "none"
    assert remote["authenticationmethods"] == "keyboard-interactive" and remote["pubkeyauthentication"] == "no"
