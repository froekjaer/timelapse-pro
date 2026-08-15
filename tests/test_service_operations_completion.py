import time

from edge.service_operations import ServiceOperations
from edge.service_platform import ServicePlatform, Principal, EdgeServiceGrantRef, SENIOR_TECHNICIAN_CAPABILITIES


EXPECTED_COMPLETION_OPERATIONS = {
    "camera.status",
    "camera.detect",
    "camera.ptp.diagnostics",
    "camera.power.acquire",
    "camera.power.release",
    "camera.power.cycle",
    "camera.hardware.inventory",
    "camera.live.start",
    "camera.live.stop",
    "camera.capture.test",
    "camera.config.read",
    "camera.config.set_temporary",
    "camera.config.diff",
    "camera.focus.auto",
    "camera.focus.manual",
    "camera.exposure.test",
    "image.quality.diagnostics",
    "modem.status",
    "modem.signal",
    "modem.registration",
    "modem.reconnect_history",
    "modem.power.cycle",
    "network.diagnostics",
    "storage.status",
    "system.status",
    "timelapse.service.status",
    "timelapse.service.restart",
    "certificate.trust.status",
    "software.update.status",
    "diagnostic.bundle",
    "system.reboot",
    "commissioning.run",
    "commissioning.validate",
}


def _session(platform):
    return platform.start_session(
        principal=Principal("senior", "senior_technician", SENIOR_TECHNICIAN_CAPABILITIES),
        grant=EdgeServiceGrantRef("grant-completion", time.time() + 600),
    )


def test_completion_operations_have_concrete_handlers(tmp_path):
    platform = ServicePlatform(state_dir=tmp_path)
    ServiceOperations(base_dir=tmp_path).register(platform)

    missing = EXPECTED_COMPLETION_OPERATIONS - set(platform.operations)
    defaulted = {
        name
        for name in EXPECTED_COMPLETION_OPERATIONS & set(platform.operations)
        if platform.operations[name].handler == platform._default_handler
    }

    assert missing == set()
    assert defaulted == set()


def test_camera_service_operation_acquires_and_cleans_physical_power(tmp_path, monkeypatch):
    events = []

    class Camera:
        def power_on(self):
            events.append("camera_on")

        def force_off(self):
            events.append("camera_off")

    class Relay:
        camera = Camera()

        def cleanup(self, camera=True, modem=False):
            events.append(f"cleanup:{camera}:{modem}")

    backend = ServiceOperations(base_dir=tmp_path)
    monkeypatch.setattr(backend, "_relay", lambda: Relay())
    monkeypatch.setattr(backend, "_gphoto", lambda *_args, **_kwargs: {"ok": True, "stdout": "usb: Nikon Z30", "stderr": "", "returncode": 0})
    monkeypatch.setattr(backend, "_read_gphoto_current", lambda path: "ok")
    platform = ServicePlatform(state_dir=tmp_path / "state")
    backend.register(platform)
    session = _session(platform)

    result = platform.call("camera.status", session=session, release_after=True)

    assert result["ok"] is True
    assert events == ["camera_on", "camera_off", "cleanup:True:False"]
    assert platform.status()["camera_relay_on"] is False


def test_commissioning_report_v1_shape_and_result(tmp_path, monkeypatch):
    backend = ServiceOperations(base_dir=tmp_path)
    monkeypatch.setattr(backend, "_relay", lambda: None)
    monkeypatch.setattr(backend, "system_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "camera_diagnostics", lambda *_args, **_kwargs: {"ok": True, "status": {"detected": True}})
    monkeypatch.setattr(backend, "modem_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "network_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "storage_status", lambda *_args, **_kwargs: {"ok": True, "backlog": 0})
    monkeypatch.setattr(backend, "certificate_trust_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "software_update_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "_identity_section", lambda: {"ok": True, "device_id": "TL-TEST"})
    monkeypatch.setattr(backend, "_gps_time_section", lambda: {"ok": True})
    monkeypatch.setattr(backend, "_headend_section", lambda: {"ok": True})
    platform = ServicePlatform(state_dir=tmp_path / "state")
    backend.register(platform)
    session = _session(platform)

    report = platform.call("commissioning.run", session=session)

    assert report["schema"] == "timelapse.edge.commissioning_report.v1"
    assert report["result"] == "PASS"
    assert set(report["sections"]) >= {
        "identity",
        "hardware",
        "camera",
        "test_capture",
        "image_quality",
        "modem_network",
        "gps_time",
        "storage",
        "certificates",
        "headend",
        "software",
        "technician",
    }


def test_ui_and_cli_route_through_shared_service_operations_backend():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    cli = (root / "edge/tools/bootstrap_cli.py").read_text(encoding="utf-8")
    ui = (root / "edge/scripts/totp-service.py").read_text(encoding="utf-8")

    assert "from service_operations import create_service_platform" in cli
    assert "from service_operations import create_service_platform" in ui
    assert "--service-operation" in cli
    assert "--service-operation" in ui
    assert "camera.config.set_temporary" in ui
