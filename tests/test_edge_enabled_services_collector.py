"""Regression tests for edge/utils/inventory.py's enabled-service collector.

Needed for CMDB baseline drift (both directions) — the previously-existing
_systemd_services() only reported an allowlist-filtered subset, which cannot
detect a service that's enabled but shouldn't be.
"""
from unittest.mock import MagicMock, patch

from utils import inventory


def test_apt_sources_parses_classic_one_line_list_files(tmp_path):
    (tmp_path / "docker.list").write_text(
        "# comment, should be skipped\n"
        "deb https://repo.huaweicloud.com/docker-ce/linux/ubuntu jammy stable\n"
    )
    assert inventory._apt_sources(tmp_path) == ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"]


def test_apt_sources_skips_bracketed_options_before_the_uri(tmp_path):
    # Real production format (TL-043EB9E72EFD, verified 2026-08-19): the
    # [arch=arm64] options token sits between "deb" and the URI and must not
    # be mistaken for the URI itself.
    (tmp_path / "docker.list").write_text(
        "deb [arch=arm64] https://repo.huaweicloud.com/docker-ce/linux/ubuntu jammy stable\n"
    )
    assert inventory._apt_sources(tmp_path) == ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"]


def test_apt_sources_parses_deb822_sources_files(tmp_path):
    (tmp_path / "docker.sources").write_text(
        "Types: deb\n"
        "URIs: https://repo.huaweicloud.com/docker-ce/linux/ubuntu\n"
        "Suites: noble\n"
        "Components: stable\n"
    )
    assert inventory._apt_sources(tmp_path) == ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"]


def test_apt_sources_deduplicates_and_sorts_across_files(tmp_path):
    (tmp_path / "a.list").write_text("deb https://b.example.com/repo jammy main\n")
    (tmp_path / "b.list").write_text("deb https://a.example.com/repo jammy main\n")
    (tmp_path / "c.sources").write_text("URIs: https://b.example.com/repo\n")
    assert inventory._apt_sources(tmp_path) == ["https://a.example.com/repo", "https://b.example.com/repo"]


def test_apt_sources_ignores_dist_upgrade_backup_files(tmp_path):
    # apt-get's do-release-upgrade leaves *.list.distUpgrade backups behind —
    # not an active source, must not be picked up by the *.list glob.
    (tmp_path / "docker.list.distUpgrade").write_text("deb https://old.example.com/repo focal main\n")
    assert inventory._apt_sources(tmp_path) == []


def test_apt_sources_returns_empty_list_when_directory_missing(tmp_path):
    assert inventory._apt_sources(tmp_path / "does-not-exist") == []


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
    monkeypatch.setattr(inventory, "_apt_sources", lambda: ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"])
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
    assert result["apt_sources"] == ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"]
