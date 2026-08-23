"""Regression tests for the edge side of the break-glass/RBAC redesign's
first slice (2026-08-19, per Peter): technician SSH key caching
(edge/agent.py::_apply_technician_keys) and the sshd AuthorizedKeysCommand
backend (edge/scripts/technician_authorized_keys.py) that reads it.
"""
import importlib.util
import json
import sys
from pathlib import Path

import agent as edge_agent

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "edge" / "scripts" / "technician_authorized_keys.py"


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
