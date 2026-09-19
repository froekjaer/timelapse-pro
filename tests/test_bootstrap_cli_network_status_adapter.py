"""Tests that the technician CLI's --network-status output (also invoked by
the technician portal via `_run_tech_cli("--network-status")` in
edge/scripts/totp-service.py) is an adapter over the same canonical
edge.network_status.get_network_status() used for Bluetooth naming, not a
separate reimplementation. See Dokumentation/HANDOVER_LOG.md 2026-09-19 and
edge/network_status.py's module docstring for the divergence this closes.
"""

import importlib.util
import sys
from pathlib import Path
from unittest import mock

from edge.network_status import NetworkStatus

_MODULE_PATH = Path(__file__).resolve().parents[1] / "edge" / "tools" / "bootstrap_cli.py"
_spec = importlib.util.spec_from_file_location("bootstrap_cli_under_test_network_status", _MODULE_PATH)
bootstrap_cli = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_cli_under_test_network_status"] = bootstrap_cli
_spec.loader.exec_module(bootstrap_cli)


def test_network_management_summary_uses_canonical_get_network_status(capsys):
    fake_status = NetworkStatus(
        mode="wifi_client",
        interface="wlan0",
        ssid="KirkbiWiFi",
        ipv4="192.168.86.144",
        connected=True,
        checked_at=0.0,
    )
    with mock.patch("network_status.get_network_status", return_value=fake_status) as mocked:
        bootstrap_cli.print_network_management_summary()
        mocked.assert_called_once_with()

    out = capsys.readouterr().out
    assert "mode=wifi_client" in out
    assert "ssid=KirkbiWiFi" in out
    assert "ipv4=192.168.86.144" in out


def test_network_management_summary_never_raises_on_failure(capsys):
    with mock.patch("network_status.get_network_status", side_effect=RuntimeError("boom")):
        bootstrap_cli.print_network_management_summary()  # must not raise

    out = capsys.readouterr().out
    assert "kunne ikke beregne" in out


def test_print_network_status_includes_canonical_summary_before_raw_dump(capsys):
    fake_status = NetworkStatus(
        mode="ap", interface="wlan0", ssid="TL-C87FF9587CA0", ipv4="192.168.43.1", connected=True, checked_at=0.0
    )
    with mock.patch("network_status.get_network_status", return_value=fake_status), \
         mock.patch.object(bootstrap_cli, "command_exists", return_value=False):
        bootstrap_cli.print_network_status(detailed=True)

    out = capsys.readouterr().out
    assert "authoritative" in out.lower() or "authoritative" in out
    assert "mode=ap" in out
    assert "ssid=TL-C87FF9587CA0" in out
