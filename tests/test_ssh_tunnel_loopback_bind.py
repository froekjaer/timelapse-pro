"""Reverse forwards must request the explicit loopback bind address.

The headend tunnel sshd allowlists each Edge key with
permitlisten="127.0.0.1:<port>". A bare "-R <port>:localhost:22" request does
not match that entry and sshd refuses the forward. This fix lived only on the
#259 branch, so the 2026-10-03 lab.56 release from main broke Edge1's tunnel.
"""
from pathlib import Path

import edge.tunnel.ssh_manager as ssh_manager
from edge.tunnel.ssh_manager import SshTunnelManager


class _Api:
    _device_id = "TL-TEST"

    def ping(self):
        return True

    def _post(self, *_args, **_kwargs):
        return True, {}


class _Proc:
    stderr = None

    def poll(self):
        return None


def test_every_reverse_forward_binds_explicit_loopback(monkeypatch, tmp_path):
    key = tmp_path / "id_ed25519"
    key.write_text("k")
    seen = []
    monkeypatch.setattr(ssh_manager.subprocess, "Popen", lambda cmd, **_kw: seen.append(cmd) or _Proc())
    monkeypatch.setattr(ssh_manager.time, "sleep", lambda _s: None)
    manager = SshTunnelManager(
        {"ssh_tunnel": {"remote_port": 2201, "extra_forwards": [{"remote_port": 2301, "local_port": 8080, "name": "ui"}]}},
        _Api(),
    )
    monkeypatch.setattr(manager, "_key_file", lambda: key)
    monkeypatch.setattr(manager, "_start_stderr_drain", lambda _p: None)

    assert manager._try_connect("timelapse_tunnel@backend.timelapse-pro.dk:9222") is True
    cmd = seen[0]
    forwards = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-R"]
    assert forwards == ["127.0.0.1:2201:localhost:22", "127.0.0.1:2301:localhost:8080"]
    assert cmd[cmd.index("-p") + 1] == "9222"


def test_source_never_requests_unbound_reverse_forward():
    source = Path("edge/tunnel/ssh_manager.py").read_text(encoding="utf-8")
    assert '"-R", f"127.0.0.1:{remote_port}:localhost:{local_port}"' in source
    assert '"-R", f"{remote_port}:localhost:{local_port}"' not in source
