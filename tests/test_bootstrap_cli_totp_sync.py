"""Tests for bootstrap_cli.py --totp-sync — the manual escape hatch for a
device stuck on a stale local BT-TOTP secret (see
tests/test_bt_totp_auto_sync.py for the automatic-path regression this
pairs with, and Dokumentation/HANDOVER_LOG.md 2026-08-21 for the incident).
"""
import importlib.util
import sys
from pathlib import Path
from unittest import mock

_MODULE_PATH = Path(__file__).resolve().parents[1] / "edge" / "tools" / "bootstrap_cli.py"
_spec = importlib.util.spec_from_file_location("bootstrap_cli_under_test_totp", _MODULE_PATH)
bootstrap_cli = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_cli_under_test_totp"] = bootstrap_cli
_spec.loader.exec_module(bootstrap_cli)


def test_totp_sync_refuses_without_root(capsys, tmp_path):
    with mock.patch.object(bootstrap_cli.os, "geteuid", return_value=1000):
        result = bootstrap_cli.run_totp_sync(tmp_path)

    assert result is False
    assert "root" in capsys.readouterr().out.lower()


def test_totp_sync_reports_synced_when_secret_changes(capsys, tmp_path, monkeypatch):
    fake_cfg_mgr = mock.MagicMock()
    fake_cfg_mgr.load.return_value = {"device": {"device_id": "TL-TEST"}}
    fake_client = mock.MagicMock()
    fake_client.fetch_config.return_value = (True, {"bt_totp": {"secret": "S3CR3T", "sid": "cam-1"}})

    with mock.patch.object(bootstrap_cli.os, "geteuid", return_value=0), \
         mock.patch("config.manager.ConfigManager", return_value=fake_cfg_mgr), \
         mock.patch("upload.headend_client.HeadendClient", return_value=fake_client), \
         mock.patch("utils.bt_totp_sync.sync_bt_totp_config", return_value="synced") as sync_mock:
        result = bootstrap_cli.run_totp_sync(tmp_path)

    assert result is True
    sync_mock.assert_called_once_with({"secret": "S3CR3T", "sid": "cam-1"})
    out = capsys.readouterr().out
    assert "synkroniseret" in out.lower()
    assert "cam-1" in out


def test_totp_sync_reports_unchanged_without_claiming_a_write(capsys, tmp_path):
    fake_cfg_mgr = mock.MagicMock()
    fake_cfg_mgr.load.return_value = {}
    fake_client = mock.MagicMock()
    fake_client.fetch_config.return_value = (True, {"bt_totp": {"secret": "S3CR3T", "sid": "cam-1"}})

    with mock.patch.object(bootstrap_cli.os, "geteuid", return_value=0), \
         mock.patch("config.manager.ConfigManager", return_value=fake_cfg_mgr), \
         mock.patch("upload.headend_client.HeadendClient", return_value=fake_client), \
         mock.patch("utils.bt_totp_sync.sync_bt_totp_config", return_value="unchanged"):
        result = bootstrap_cli.run_totp_sync(tmp_path)

    assert result is True
    assert "allerede" in capsys.readouterr().out.lower()


def test_totp_sync_reports_no_secret_as_failure(capsys, tmp_path):
    fake_cfg_mgr = mock.MagicMock()
    fake_cfg_mgr.load.return_value = {}
    fake_client = mock.MagicMock()
    fake_client.fetch_config.return_value = (True, {"bt_totp": {}})

    with mock.patch.object(bootstrap_cli.os, "geteuid", return_value=0), \
         mock.patch("config.manager.ConfigManager", return_value=fake_cfg_mgr), \
         mock.patch("upload.headend_client.HeadendClient", return_value=fake_client), \
         mock.patch("utils.bt_totp_sync.sync_bt_totp_config", return_value="no-secret"):
        result = bootstrap_cli.run_totp_sync(tmp_path)

    assert result is False
    assert "uprovisioneret" in capsys.readouterr().out.lower()


def test_totp_sync_reports_fetch_failure_without_calling_sync(capsys, tmp_path):
    fake_cfg_mgr = mock.MagicMock()
    fake_cfg_mgr.load.return_value = {}
    fake_client = mock.MagicMock()
    fake_client.fetch_config.return_value = (False, None)

    with mock.patch.object(bootstrap_cli.os, "geteuid", return_value=0), \
         mock.patch("config.manager.ConfigManager", return_value=fake_cfg_mgr), \
         mock.patch("upload.headend_client.HeadendClient", return_value=fake_client), \
         mock.patch("utils.bt_totp_sync.sync_bt_totp_config") as sync_mock:
        result = bootstrap_cli.run_totp_sync(tmp_path)

    assert result is False
    sync_mock.assert_not_called()
    assert "headend" in capsys.readouterr().out.lower()
