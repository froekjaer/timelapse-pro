"""Regression tests for edge/utils/inventory.py's enabled-service collector.

Needed for CMDB baseline drift (both directions) — the previously-existing
_systemd_services() only reported an allowlist-filtered subset, which cannot
detect a service that's enabled but shouldn't be.
"""
from unittest.mock import MagicMock, patch

from utils import inventory


def test_enabled_service_names_parses_list_unit_files_output():
    fake = MagicMock(returncode=0, stdout=(
        "timelapse-edge.service         enabled\n"
        "timelapse-totp.service         enabled\n"
        "dnsmasq.service                enabled\n"
    ))
    with patch.object(inventory.subprocess, "run", return_value=fake) as run_mock:
        names = inventory._enabled_service_names()

    assert names == ["dnsmasq.service", "timelapse-edge.service", "timelapse-totp.service"]
    args = run_mock.call_args.args[0]
    assert args[:2] == ["systemctl", "list-unit-files"]
    assert "--state=enabled" in args


def test_enabled_service_names_returns_empty_list_on_nonzero_exit():
    fake = MagicMock(returncode=1, stdout="")
    with patch.object(inventory.subprocess, "run", return_value=fake):
        assert inventory._enabled_service_names() == []


def test_enabled_service_names_returns_empty_list_on_exception():
    with patch.object(inventory.subprocess, "run", side_effect=OSError("no systemctl")):
        assert inventory._enabled_service_names() == []


def test_enabled_service_names_deduplicates_and_sorts():
    fake = MagicMock(returncode=0, stdout=(
        "b.service enabled\n"
        "a.service enabled\n"
        "a.service enabled\n"
    ))
    with patch.object(inventory.subprocess, "run", return_value=fake):
        assert inventory._enabled_service_names() == ["a.service", "b.service"]


def test_collect_inventory_includes_enabled_services_key(monkeypatch):
    monkeypatch.setattr(inventory, "_enabled_service_names", lambda: ["timelapse-edge.service"])
    monkeypatch.setattr(inventory, "_local_users", lambda: [])
    monkeypatch.setattr(inventory, "_sudo_users", lambda: [])
    monkeypatch.setattr(inventory, "_systemd_services", lambda: [])
    monkeypatch.setattr(inventory, "_apt_updates_available", lambda: {})
    monkeypatch.setattr(inventory, "_os_packages", lambda: ("apt/dpkg", {}))
    monkeypatch.setattr(inventory, "_detect_hardware_model", lambda: ("unknown", "unknown"))
    monkeypatch.setattr(inventory, "_primary_interface", lambda: None)
    monkeypatch.setattr(inventory, "_primary_mac", lambda iface: None)
    monkeypatch.setattr(inventory, "_primary_ip", lambda iface: None)
    monkeypatch.setattr(inventory, "_wifi_info", lambda: (False, None))
    monkeypatch.setattr(inventory, "_storage_info", lambda path: (None, None, None))
    monkeypatch.setattr(inventory, "_artifact_release_metadata", lambda: {})
    monkeypatch.setattr(inventory, "_git_app_version", lambda: "")
    monkeypatch.setattr(inventory, "_git_app_tag", lambda: "")
    monkeypatch.setattr(inventory, "_venv_packages", lambda: {})
    monkeypatch.setattr(inventory, "_software_inventory", lambda: {})
    monkeypatch.setattr(inventory, "_ip_addresses", lambda: [])
    monkeypatch.setattr(inventory, "_serial_number", lambda: None)
    monkeypatch.setattr(inventory, "_os_name", lambda: "Ubuntu")
    monkeypatch.setattr(inventory, "_firmware_version", lambda: None)
    monkeypatch.setattr(inventory, "_cpu_cores", lambda: 4)
    monkeypatch.setattr(inventory, "_ram_mb", lambda: 4096)

    result = inventory.collect_inventory({})

    assert result["enabled_services"] == ["timelapse-edge.service"]
