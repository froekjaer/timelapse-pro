import time

import pytest

from edge.service_platform import (
    OPERATION_CAPABILITIES,
    ServicePlatform,
    EdgeServiceGrantRef,
    Principal,
    TECHNICIAN_CAPABILITIES,
)


def _platform(tmp_path):
    return ServicePlatform(state_dir=tmp_path)


def _session(platform, *, caps=TECHNICIAN_CAPABILITIES, ttl=600):
    return platform.start_session(
        principal=Principal("tech", "technician", frozenset(caps)),
        grant=EdgeServiceGrantRef("grant-1", time.time() + ttl),
    )


def test_all_required_service_operations_are_registered(tmp_path):
    platform = _platform(tmp_path)

    assert set(OPERATION_CAPABILITIES).issubset(platform.operations)
    assert len(platform.operations) >= 28


def test_capabilities_are_enforced_by_service_operations(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform, caps={"camera.read"})

    with pytest.raises(PermissionError, match="missing capability"):
        platform.call("camera.power.acquire", session=session)


def test_camera_hardware_requires_lease_before_status_turns_on(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform)

    assert platform.status()["camera_relay_on"] is False
    platform.call("camera.power.acquire", session=session)
    assert platform.status()["camera_relay_on"] is True


def test_live_view_holds_live_and_camera_power_leases(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform)

    platform.call("camera.live.start", session=session)
    status = platform.status()

    assert status["live_view"] == "ON"
    assert status["camera_relay_on"] is True


def test_grant_revoke_invalidates_entire_service_session(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform)
    platform.call("camera.live.start", session=session)
    session.grant = EdgeServiceGrantRef(session.grant.grant_id, session.grant.expires_at, revoked=True)

    with pytest.raises(PermissionError):
        platform.call("camera.status", session=session)

    status = platform.status()
    assert status["logged_in"] is False
    assert status["camera_relay_on"] is False
    assert status["live_view"] == "OFF"


def test_shared_status_is_visible_across_platform_instances(tmp_path):
    ui_platform = _platform(tmp_path)
    session = _session(ui_platform)
    ui_platform.call("camera.power.acquire", session=session)

    cli_platform = _platform(tmp_path)
    status = cli_platform.status()

    assert status["logged_in"] is True
    assert status["camera_relay_on"] is True
    assert status["grant_id"] == "grant-1"


def test_expired_grant_fails_closed_and_releases_leases(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform, ttl=-1)

    with pytest.raises(PermissionError):
        platform.call("camera.status", session=session)

    assert platform.status()["logged_in"] is False
