"""Regression test: edge/utils/inventory.py's _venv_packages() must invoke pip
via sys.executable, not bare "pip" on PATH.

Found live 2026-09-04 (HANDOVER_LOG): production venv_packages was permanently
empty ({}) for every device. Root cause: the edge agent runs under systemd
(ExecStart=/opt/timelapse/venv/bin/python), which uses systemd's default PATH —
that does not include /opt/timelapse/venv/bin. subprocess.run(["pip", ...])
therefore always raised FileNotFoundError, silently swallowed by the broad
except below it, so nothing ever surfaced the bug. sys.executable is always the
exact interpreter running the current process regardless of PATH.
"""
from unittest.mock import MagicMock, patch

from utils import inventory


def test_venv_packages_invokes_pip_via_sys_executable():
    fake_result = MagicMock()
    fake_result.stdout = '[{"name": "requests", "version": "2.31.0"}]'
    with patch("utils.inventory.subprocess.run", return_value=fake_result) as run:
        packages = inventory._venv_packages()

    assert packages == {"requests": "2.31.0"}
    called_argv = run.call_args[0][0]
    assert called_argv[0] == inventory.sys.executable
    assert called_argv[1:] == ["-m", "pip", "list", "--format=json"]
    assert "pip" not in called_argv[0]  # not a bare "pip" lookup on PATH


def test_venv_packages_returns_empty_dict_on_missing_interpreter(monkeypatch):
    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(inventory.subprocess, "run", raise_not_found)
    assert inventory._venv_packages() == {}
