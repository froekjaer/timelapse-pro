from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATT = ROOT / "edge/scripts/ble-technician-gatt.py"
SERVICE = ROOT / "edge/scripts/timelapse-ble-technician.service"
TOTP = ROOT / "edge/totp_verifier.py"


def test_gatt_adapter_is_transport_only_and_has_no_shell_or_private_key_path():
    source = GATT.read_text(encoding="utf-8")
    assert "BleTechnicianSession" in source
    assert "systemctl" not in source
    assert "subprocess" not in source
    assert "private key" not in source.lower()
    assert "AUTH_UUID" in source
    assert "REQUEST_UUID" in source
    assert "totp_verifier" in source


def test_gatt_service_is_separate_and_hardened():
    source = SERVICE.read_text(encoding="utf-8")
    assert "ble-technician-gatt.py" in source
    assert "NoNewPrivileges=true" in source
    assert "Restart=on-failure" in source


def test_gatt_adapter_is_injected_and_started_by_image_flow():
    injector = (ROOT / "headend/tools/inject_edge_image.py").read_text(encoding="utf-8")
    dockerfile = (ROOT / "headend/tools/Dockerfile.edge").read_text(encoding="utf-8")
    target = (ROOT / "headend/tools/hardware/orangepi4pro/target.yaml").read_text(encoding="utf-8")
    assert "timelapse-ble-technician.service" in injector
    assert "timelapse-ble-technician.service" in dockerfile
    assert "timelapse-ble-technician.service" in target


def test_gatt_runtime_uses_system_dbus_and_edge_venv_dependencies():
    source = GATT.read_text(encoding="utf-8")
    assert "/opt/timelapse/venv/lib/python*/site-packages" in source
    assert TOTP.exists()
