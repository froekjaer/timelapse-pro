from pathlib import Path


def test_system_admin_uses_admin_safe_endpoints():
    source = Path("timelapse-ui/src/pages/SystemAdminPage.tsx").read_text()

    assert "/api/ai/settings" not in source
    assert "`/api/config/" not in source
    assert "/api/settings/ollama-runtime-control" in source
    assert "/api/admin/devices/${pathSegment(selectedDevice)}/config" in source
