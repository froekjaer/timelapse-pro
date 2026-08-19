"""Regression tests for CMDB baseline-drift reconciliation.

Closes FIND-CMDB-MISSING-PACKAGE-DETECTION and FIND-CMDB-UNTRACKED-DOCKER-CE-CHANNEL,
widened per Peter (2026-08-16) to packages+services+accounts, both directions.
"""
from services.cmdb_baseline_drift import (
    compute_account_drift,
    compute_apt_source_drift,
    compute_baseline_drift,
    compute_package_drift,
    compute_service_drift,
    drift_to_grc_finding_rows,
)


def test_package_drift_flags_missing_but_never_unexpected():
    result = compute_package_drift(
        expected_packages=["gpsd", "gpsd-clients", "python3-gps"],
        installed_packages={"gpsd-clients": "3.22-1", "vim": "9.0"},
    )
    assert result.missing == ["gpsd", "python3-gps"]
    assert result.unexpected == []
    assert result.has_drift is True


def test_package_drift_clean_when_everything_expected_is_installed():
    result = compute_package_drift(
        expected_packages=["gpsd"],
        installed_packages={"gpsd": "3.22-1"},
    )
    assert result.has_drift is False


def test_service_drift_detects_both_directions():
    result = compute_service_drift(
        expected_services=["timelapse-edge.service", "timelapse-totp.service", "ssh.service"],
        enabled_services=["timelapse-edge.service", "ssh.service", "dnsmasq.service"],
    )
    assert result.missing == ["timelapse-totp.service"]
    assert result.unexpected == ["dnsmasq.service"]


def test_account_drift_detects_both_directions():
    result = compute_account_drift(
        expected_users=["orangepi"],
        local_users=[{"username": "orangepi", "uid": 1000}, {"username": "mystery", "uid": 1001}],
    )
    assert result.missing == []
    assert result.unexpected == ["mystery"]


def test_account_drift_ignores_entries_without_a_username():
    result = compute_account_drift(
        expected_users=["orangepi"],
        local_users=[{"uid": 1002}],
    )
    assert result.missing == ["orangepi"]
    assert result.unexpected == []


def test_apt_source_drift_detects_both_directions():
    result = compute_apt_source_drift(
        expected_sources=["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"],
        configured_sources=["https://repo.huaweicloud.com/docker-ce/linux/ubuntu", "http://repo.huaweicloud.com/ubuntu-ports"],
    )
    assert result.missing == []
    assert result.unexpected == ["http://repo.huaweicloud.com/ubuntu-ports"]


def test_apt_source_drift_flags_a_missing_expected_channel():
    result = compute_apt_source_drift(
        expected_sources=["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"],
        configured_sources=[],
    )
    assert result.missing == ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"]
    assert result.unexpected == []


def test_compute_baseline_drift_reads_the_real_target_and_inventory_shapes():
    target = {
        "extra_packages": ["gpsd", "gpsd-clients"],
        "expected_enabled_services": ["timelapse-edge.service", "timelapse-totp.service"],
        "expected_local_users": ["orangepi"],
        "expected_apt_sources": ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"],
    }
    inventory = {
        "os_packages": {"gpsd-clients": "3.22-1"},
        "software_inventory": {
            "_enabled_services": ["timelapse-edge.service", "dnsmasq.service"],
            "_local_users": [{"username": "orangepi"}, {"username": "backdoor"}],
            "_apt_sources": ["http://repo.huaweicloud.com/ubuntu-ports"],
        },
    }

    drift = compute_baseline_drift(target, inventory)

    assert drift["packages"].missing == ["gpsd"]
    assert drift["services"].missing == ["timelapse-totp.service"]
    assert drift["services"].unexpected == ["dnsmasq.service"]
    assert drift["accounts"].unexpected == ["backdoor"]
    assert drift["apt_sources"].missing == ["https://repo.huaweicloud.com/docker-ce/linux/ubuntu"]
    assert drift["apt_sources"].unexpected == ["http://repo.huaweicloud.com/ubuntu-ports"]


def test_compute_baseline_drift_is_clean_when_nothing_reported_yet():
    drift = compute_baseline_drift({}, {})
    assert all(not result.has_drift for result in drift.values())


def test_drift_to_grc_finding_rows_only_emits_categories_with_real_drift():
    drift = {
        "packages": compute_package_drift(["gpsd"], {}),
        "services": compute_service_drift(["timelapse-edge.service"], ["timelapse-edge.service"]),
        "accounts": compute_account_drift(["orangepi"], [{"username": "orangepi"}, {"username": "x"}]),
    }

    rows = drift_to_grc_finding_rows("TL-TEST", drift)

    external_ids = {r["external_id"] for r in rows}
    assert "FIND-CMDB-DRIFT-TL-TEST-PACKAGES-MISSING" in external_ids
    assert "FIND-CMDB-DRIFT-TL-TEST-ACCOUNTS-UNEXPECTED" in external_ids
    # services had zero drift — must not produce a row
    assert not any("SERVICES" in eid for eid in external_ids)
    assert len(rows) == 2


def test_drift_to_grc_finding_rows_is_empty_when_device_is_clean():
    drift = compute_baseline_drift({}, {})
    assert drift_to_grc_finding_rows("TL-TEST", drift) == []
