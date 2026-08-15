from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cli_routes_camera_service_work_through_service_platform():
    cli = source("edge/tools/bootstrap_cli.py")

    assert "from service_platform import ServicePlatform" in cli
    assert "platform.call(operation_name" in cli
    assert "--service-status" in cli


def test_local_technician_ui_uses_unified_service_status():
    ui = source("edge/scripts/totp-service.py")

    assert "from service_platform import ServicePlatform" in ui
    assert "_service_session_panel()" in ui
    assert "camera.live.start" in ui
    assert "camera.live.stop" in ui


def test_lab_mode_acquires_service_platform_camera_lease():
    agent = source("edge/agent.py")

    assert "from service_platform import ServicePlatform" in agent
    assert 'self._service_platform.call("camera.power.acquire"' in agent
    assert 'self._service_platform.invalidate(reason="lab_disabled")' in agent


def test_no_ui_or_cli_gpio_writes_bypass_service_platform():
    for path in ("edge/tools/bootstrap_cli.py", "edge/scripts/totp-service.py"):
        text = source(path)
        assert "/sys/class/gpio" not in text
        assert "GPIO.output" not in text
