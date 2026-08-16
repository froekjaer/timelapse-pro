"""bootstrap_cli.py must not crash the Servicetekniker menu when a config
file (e.g. root-only bootstrap.yaml) can't be read by the current user.

Regression test for a PermissionError crash reported on TL-043EB9E72EFD:
running `python3 bootstrap_cli.py` as the non-root `orangepi` user and
picking menu option "1. Overblik / status" raised an unhandled
PermissionError instead of degrading gracefully.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "edge" / "tools" / "bootstrap_cli.py"
_spec = importlib.util.spec_from_file_location("bootstrap_cli_under_test", _MODULE_PATH)
bootstrap_cli = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_cli_under_test"] = bootstrap_cli
_spec.loader.exec_module(bootstrap_cli)


@pytest.fixture
def unreadable_yaml_file():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "bootstrap.yaml"
        path.write_text("device_id: TEST-DEVICE\n")
        os.chmod(path, 0o000)
        try:
            yield path
        finally:
            os.chmod(path, 0o600)


def test_read_yaml_falls_back_to_sudo_cat_when_permission_denied(unreadable_yaml_file):
    class FakeSudoResult:
        returncode = 0
        stdout = "device_id: TEST-DEVICE\n"

    with mock.patch.object(bootstrap_cli, "command_exists", return_value=True), \
         mock.patch.object(bootstrap_cli.os, "geteuid", return_value=1000), \
         mock.patch.object(bootstrap_cli.subprocess, "run", return_value=FakeSudoResult()) as run_mock:
        result = bootstrap_cli.read_yaml(unreadable_yaml_file)

    assert result == {"device_id": "TEST-DEVICE"}
    args = run_mock.call_args.args[0]
    assert args[:2] == ["sudo", "-n"]


def test_read_yaml_degrades_to_empty_dict_when_sudo_unavailable(unreadable_yaml_file, capsys):
    with mock.patch.object(bootstrap_cli, "command_exists", return_value=False), \
         mock.patch.object(bootstrap_cli.os, "geteuid", return_value=1000):
        result = bootstrap_cli.read_yaml(unreadable_yaml_file)

    assert result == {}
    assert "sudo" in capsys.readouterr().out


def test_read_yaml_degrades_to_empty_dict_when_sudo_prompts_for_password(unreadable_yaml_file, capsys):
    class FakeSudoResult:
        returncode = 1
        stdout = ""

    with mock.patch.object(bootstrap_cli, "command_exists", return_value=True), \
         mock.patch.object(bootstrap_cli.os, "geteuid", return_value=1000), \
         mock.patch.object(bootstrap_cli.subprocess, "run", return_value=FakeSudoResult()):
        result = bootstrap_cli.read_yaml(unreadable_yaml_file)

    assert result == {}
    assert "sudo" in capsys.readouterr().out


def test_read_yaml_still_works_normally_for_readable_files():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "local_network.yaml"
        path.write_text("connectivity:\n  preferred_order: [ethernet, wifi]\n")
        assert bootstrap_cli.read_yaml(path) == {
            "connectivity": {"preferred_order": ["ethernet", "wifi"]}
        }
