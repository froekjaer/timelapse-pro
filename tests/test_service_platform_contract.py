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


def test_normal_technician_session_requires_edge_service_grant(tmp_path):
    platform = _platform(tmp_path)

    with pytest.raises(PermissionError, match="EdgeServiceGrant-backed"):
        platform.shared_or_lab_session("technician")

    session = platform.start_session_from_edge_service_grant(
        username="tech",
        role="technician",
        grant_id="grant-real-1",
        expires_at=time.time() + 600,
        capabilities=TECHNICIAN_CAPABILITIES,
    )

    assert session.grant.grant_id == "grant-real-1"
    assert platform.current_session().principal.username == "tech"


def test_lab_and_offline_recovery_are_explicit_authority_adapters(tmp_path):
    lab = _platform(tmp_path / "lab").shared_or_lab_session("lab")
    offline = _platform(tmp_path / "offline").start_offline_recovery_session()

    assert lab.grant.grant_id.startswith("lab-")
    assert offline.grant.grant_id.startswith("offline-recovery-")
    assert offline.principal.role == "offline_recovery"


def test_operation_handlers_execute_hardware_callbacks(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform)
    calls = []

    def handler(_platform, _session, kwargs):
        calls.append(kwargs["operation"])
        return {"ok": True, "from_handler": True}

    platform.register_handler("camera.capture.test", handler)

    result = platform.call("camera.capture.test", session=session, release_after=True)

    assert result == {"ok": True, "from_handler": True}
    assert calls == ["camera.capture.test"]
    assert platform.status()["camera_relay_on"] is False


def test_invalidate_runs_handler_aware_release_all(tmp_path):
    platform = _platform(tmp_path)
    session = _session(platform)
    cleanup = []
    platform.register_cleanup_handler(
        "LiveViewLease",
        lambda _platform, _session, reason: cleanup.append(("live", reason)),
    )
    platform.register_cleanup_handler(
        "CameraPowerLease",
        lambda _platform, _session, reason: cleanup.append(("camera", reason)),
    )

    platform.call("camera.live.start", session=session)
    platform.invalidate(session, reason="grant_revoked")

    assert cleanup == [("live", "grant_revoked"), ("camera", "grant_revoked")]
    assert platform.status()["camera_relay_on"] is False
    assert platform.status()["live_view"] == "OFF"
