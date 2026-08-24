"""Regression tests for the edge side of the break-glass/RBAC redesign's
first slice (2026-08-19, per Peter): technician SSH key caching
(edge/agent.py::_apply_technician_keys) and the sshd AuthorizedKeysCommand
backend (edge/scripts/technician_authorized_keys.py) that reads it.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import agent as edge_agent

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "edge" / "scripts" / "technician_authorized_keys.py"
INJECT_IMAGE_PATH = Path(__file__).resolve().parents[1] / "headend" / "tools" / "inject_edge_image.py"


def _make_agent():
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    return agent


def test_apply_technician_keys_writes_atomically(tmp_path):
    cache_path = tmp_path / "authorized_technicians.json"
    agent = _make_agent()
    agent.AUTHORIZED_TECHNICIANS_PATH = cache_path

    keys = [{"public_key": "ssh-ed25519 AAAA test", "identity": "tekniker1:laptop", "field_role": "technician"}]
    agent._apply_technician_keys(keys)

    assert json.loads(cache_path.read_text()) == keys
    assert list(cache_path.parent.glob(".*.tmp")) == []


def test_apply_technician_keys_is_idempotent_when_unchanged(tmp_path):
    cache_path = tmp_path / "authorized_technicians.json"
    keys = [{"public_key": "ssh-ed25519 AAAA test", "identity": "tekniker1:laptop", "field_role": "technician"}]
    cache_path.write_text(json.dumps(keys))
    mtime_before = cache_path.stat().st_mtime_ns

    agent = _make_agent()
    agent.AUTHORIZED_TECHNICIANS_PATH = cache_path
    agent._apply_technician_keys(keys)

    assert cache_path.stat().st_mtime_ns == mtime_before


def test_apply_technician_keys_recovers_from_corrupt_cache(tmp_path):
    cache_path = tmp_path / "authorized_technicians.json"
    cache_path.write_text("{not valid json")

    agent = _make_agent()
    agent.AUTHORIZED_TECHNICIANS_PATH = cache_path
    keys = [{"public_key": "ssh-ed25519 AAAA test", "identity": "tekniker1:laptop", "field_role": "technician"}]
    agent._apply_technician_keys(keys)

    assert json.loads(cache_path.read_text()) == keys


def _load_script_module():
    spec = importlib.util.spec_from_file_location("technician_authorized_keys", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_outputs_nothing_for_wrong_username(tmp_path, monkeypatch):
    module = _load_script_module()
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps([{"public_key": "ssh-ed25519 AAAA", "identity": "x"}]))
    monkeypatch.setattr(module, "CACHE_PATH", cache_path)
    monkeypatch.setattr(sys, "argv", ["technician_authorized_keys.py", "root"])

    printed = []
    monkeypatch.setattr("builtins.print", lambda *a: printed.append(" ".join(a)))
    module.main()

    assert printed == []


def test_script_outputs_active_keys_for_correct_username(tmp_path, monkeypatch):
    module = _load_script_module()
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps([
        {"public_key": "ssh-ed25519 AAAA1", "identity": "tekniker1:laptop"},
        {"public_key": "ssh-ed25519 AAAA2", "identity": "tekniker2:phone"},
    ]))
    monkeypatch.setattr(module, "CACHE_PATH", cache_path)
    monkeypatch.setattr(sys, "argv", ["technician_authorized_keys.py", "servicetekniker"])

    printed = []
    monkeypatch.setattr("builtins.print", lambda *a: printed.append(" ".join(a)))
    module.main()

    assert printed == [
        "ssh-ed25519 AAAA1 tekniker1:laptop",
        "ssh-ed25519 AAAA2 tekniker2:phone",
    ]


def test_script_fails_closed_on_missing_cache(tmp_path, monkeypatch):
    module = _load_script_module()
    monkeypatch.setattr(module, "CACHE_PATH", tmp_path / "does-not-exist.json")
    monkeypatch.setattr(sys, "argv", ["technician_authorized_keys.py", "servicetekniker"])

    printed = []
    monkeypatch.setattr("builtins.print", lambda *a: printed.append(" ".join(a)))
    module.main()

    assert printed == []


def test_provisioning_sshd_match_block_passes_username_token():
    """2026-08-24: inject_edge_image.py wrote AuthorizedKeysCommand without
    the %u token, so sshd never passed the requested username as argv[1] —
    confirmed live via debug trace that argv was always just the script path,
    so the script's own "only serve servicetekniker" guard never matched
    anything and it printed no keys for ANY login, ever, on every device
    provisioned before this fix. The script itself (tested above) was
    always correct; this is what actually broke every login."""
    source = INJECT_IMAGE_PATH.read_text(encoding="utf-8")
    heredoc_body_start = source.index("\n", source.index("<< 'SSHD_MATCH_EOF'")) + 1
    heredoc_end = source.index("\nSSHD_MATCH_EOF", heredoc_body_start)
    block = source[heredoc_body_start:heredoc_end]
    assert "technician_authorized_keys.py %u" in block


def _make_agent_with_sshd_path(tmp_path):
    agent = _make_agent()
    agent.SSHD_CONFIG_PATH = tmp_path / "sshd_config"
    return agent


def test_repair_sshd_patches_missing_u_token_and_reloads(tmp_path, monkeypatch):
    sshd_config = tmp_path / "sshd_config"
    sshd_config.write_text(
        "PermitRootLogin no\n\n"
        "Match User servicetekniker\n"
        "    AuthorizedKeysCommand /usr/bin/python3 /opt/timelapse/edge/scripts/technician_authorized_keys.py\n"
        "    AuthorizedKeysCommandUser nobody\n"
    )
    agent = _make_agent_with_sshd_path(tmp_path)
    agent.SSHD_CONFIG_PATH = sshd_config

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired))

    agent._repair_sshd_authorized_keys_command_missing_u_token()

    patched = sshd_config.read_text()
    assert "technician_authorized_keys.py %u\n" in patched
    assert any(c[0] == "/usr/sbin/sshd" and "-t" in c for c in calls)
    assert any("reload" in c for c in calls)


def test_repair_sshd_is_noop_when_already_fixed(tmp_path, monkeypatch):
    sshd_config = tmp_path / "sshd_config"
    original = (
        "Match User servicetekniker\n"
        "    AuthorizedKeysCommand /usr/bin/python3 /opt/timelapse/edge/scripts/technician_authorized_keys.py %u\n"
    )
    sshd_config.write_text(original)
    agent = _make_agent_with_sshd_path(tmp_path)

    fake_run = MagicMock()
    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired))

    agent._repair_sshd_authorized_keys_command_missing_u_token()

    assert sshd_config.read_text() == original
    fake_run.assert_not_called()


def test_repair_sshd_does_not_apply_when_syntax_check_fails(tmp_path, monkeypatch):
    sshd_config = tmp_path / "sshd_config"
    original = (
        "Match User servicetekniker\n"
        "    AuthorizedKeysCommand /usr/bin/python3 /opt/timelapse/edge/scripts/technician_authorized_keys.py\n"
    )
    sshd_config.write_text(original)
    agent = _make_agent_with_sshd_path(tmp_path)

    def fake_run(cmd, **kwargs):
        if cmd[0] == "/usr/sbin/sshd":
            return MagicMock(returncode=1, stdout="", stderr="bad config")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(edge_agent, "subprocess", MagicMock(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired))

    agent._repair_sshd_authorized_keys_command_missing_u_token()

    assert sshd_config.read_text() == original
    assert list(tmp_path.glob(".*.tmp")) == []
