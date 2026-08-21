"""_sync_totp_from_headend() (the web UI's "Synkroniser TOTP fra CMDB" button,
edge/scripts/totp-service.py) must delegate to the same
utils.bt_totp_sync.sync_bt_totp_config() that edge/agent.py's automatic sync
and bootstrap_cli.py --totp-sync use, rather than maintaining its own copy
of the fetch/compare/write/restart logic. Three independent implementations
of the same operation is exactly what made the 2026-08-21 incident (device
stuck on a stale secret for hours) invisible for so long — see
Dokumentation/HANDOVER_LOG.md.
"""
import importlib.util
import sys
from pathlib import Path
from unittest import mock

_MODULE_PATH = Path(__file__).resolve().parents[1] / "edge" / "scripts" / "totp-service.py"
_spec = importlib.util.spec_from_file_location("totp_service_under_test", _MODULE_PATH)
totp_service = importlib.util.module_from_spec(_spec)
sys.modules["totp_service_under_test"] = totp_service
_spec.loader.exec_module(totp_service)


def test_sync_button_delegates_to_shared_bt_totp_sync(monkeypatch):
    monkeypatch.setattr(
        totp_service, "_fetch_headend_config",
        lambda cfg: {"bt_totp": {"secret": "S", "sid": "cam-1"}},
    )
    with mock.patch("utils.bt_totp_sync.sync_bt_totp_config", return_value="synced") as sync_mock:
        msg = totp_service._sync_totp_from_headend()

    sync_mock.assert_called_once()
    call_args = sync_mock.call_args.args
    assert call_args[0] == {"secret": "S", "sid": "cam-1"}
    assert "cam-1" in msg


def test_sync_button_reports_no_secret_without_writing(monkeypatch):
    monkeypatch.setattr(
        totp_service, "_fetch_headend_config",
        lambda cfg: {"bt_totp": {}},
    )
    with mock.patch("utils.bt_totp_sync.sync_bt_totp_config", return_value="no-secret") as sync_mock:
        msg = totp_service._sync_totp_from_headend()

    sync_mock.assert_called_once()
    assert "intet" in msg.lower()


def test_sync_button_reports_unreachable_headend_without_calling_sync(monkeypatch):
    monkeypatch.setattr(totp_service, "_fetch_headend_config", lambda cfg: {})
    with mock.patch("utils.bt_totp_sync.sync_bt_totp_config") as sync_mock:
        msg = totp_service._sync_totp_from_headend()

    sync_mock.assert_not_called()
    assert "cmdb" in msg.lower()
