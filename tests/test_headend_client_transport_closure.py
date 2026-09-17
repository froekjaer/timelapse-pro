from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EDGE_ROOT = ROOT / "edge"
if str(EDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(EDGE_ROOT))


def _method_slice(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}(")
    end = source.index(f"    def {next_name}(", start)
    return source[start:end]


def test_edge_backup_upload_uses_retry_aware_session():
    source = Path("edge/upload/headend_client.py").read_text(encoding="utf-8")
    method = _method_slice(source, "upload_edge_backup", "notify_tunnel_ready")
    assert "session = _build_session(self._cfg_mgr.api_token)" in method
    assert "session = requests.Session()" not in method
    assert 'session.headers.pop("Content-Type", None)' in method


def test_ping_does_not_duplicate_api_prefix():
    source = Path("edge/upload/headend_client.py").read_text(encoding="utf-8")
    method = _method_slice(source, "ping", "_post")
    assert 'f"{self._base_url}/health"' in method
    assert 'f"{self._base_url}/api/health"' not in method


def test_api_mtls_enrollment_uses_existing_authenticated_transport(monkeypatch):
    from edge.upload import headend_client

    class ConfigManager:
        api_token = "test-device-token"
        base_dir = Path("/tmp")

    client = headend_client.HeadendClient(
        {
            "device": {
                "device_id": "TL-C87FF9587CA0",
                "headend_url": "https://backend.timelapse-pro.dk:8443/api",
            }
        },
        ConfigManager(),
    )

    monkeypatch.setattr(
        headend_client,
        "certificate_renewal_needed",
        lambda device_id: True,
    )
    monkeypatch.setattr(
        headend_client,
        "ensure_key_and_csr",
        lambda device_id: (Path("/tmp/headend-api.key"), "CSR-PEM"),
    )

    installed = {}

    def fake_install(device_id, certificate_pem, ca_certificate_pem, *, key_path):
        installed.update(
            device_id=device_id,
            certificate_pem=certificate_pem,
            ca_certificate_pem=ca_certificate_pem,
            key_path=key_path,
        )

    monkeypatch.setattr(
        headend_client,
        "install_certificate_bundle",
        fake_install,
    )

    request = {}

    def fake_post(path, payload):
        request["path"] = path
        request["payload"] = payload
        return True, {
            "certificate_pem": "CERT-PEM",
            "ca_certificate_pem": "CA-PEM",
            "serial_number": "12345",
        }

    monkeypatch.setattr(client, "_post", fake_post)

    ok, data = client.ensure_api_mtls_enrolled()

    assert ok is True
    assert request == {
        "path": "/trust/headend-api-mtls/TL-C87FF9587CA0/enroll",
        "payload": {"csr_pem": "CSR-PEM"},
    }
    assert installed["device_id"] == "TL-C87FF9587CA0"
    assert installed["certificate_pem"] == "CERT-PEM"
    assert installed["ca_certificate_pem"] == "CA-PEM"
    assert installed["key_path"] == Path("/tmp/headend-api.key")
    assert data["serial_number"] == "12345"


def test_api_mtls_enrollment_skips_when_certificate_is_current(monkeypatch):
    from edge.upload import headend_client

    class ConfigManager:
        api_token = "test-device-token"
        base_dir = Path("/tmp")

    client = headend_client.HeadendClient(
        {
            "device": {
                "device_id": "TL-C87FF9587CA0",
                "headend_url": "https://backend.timelapse-pro.dk:8443/api",
            }
        },
        ConfigManager(),
    )

    monkeypatch.setattr(
        headend_client,
        "certificate_renewal_needed",
        lambda device_id: False,
    )

    def unexpected_post(*args, **kwargs):
        pytest.fail("current certificate must not trigger enrollment")

    monkeypatch.setattr(client, "_post", unexpected_post)

    ok, data = client.ensure_api_mtls_enrolled()

    assert ok is True
    assert data == {"status": "certificate_current"}


def test_edge_startup_attempts_api_mtls_after_config_pull():
    source = Path("edge/agent.py").read_text(encoding="utf-8")
    startup = _method_slice(source, "_startup", "_auto_bootstrap_cameras")

    config_pull = startup.index("self._pull_config()")
    mtls_enrollment = startup.index("self._ensure_api_mtls_enrollment()")

    assert config_pull < mtls_enrollment


def test_edge_api_mtls_startup_boundary_is_fail_open():
    source = Path("edge/agent.py").read_text(encoding="utf-8")
    method = _method_slice(
        source,
        "_ensure_api_mtls_enrollment",
        "_startup",
    )

    assert "self._api.ensure_api_mtls_enrolled()" in method
    assert "except Exception as exc:" in method
    assert "continuing normal startup" in method
