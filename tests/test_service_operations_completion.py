import time
import base64
import hashlib
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest

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
    "trust.ssh_host_identity",
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


def _write_test_certificates(tmp_path, *, leaf_days=30):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.COMMON_NAME, "TimeLapse Pro Test CA"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.COMMON_NAME, "tl-test.local"),
    ])
    if leaf_days > 0:
        not_before = now - timedelta(minutes=5)
        not_after = now + timedelta(days=leaf_days)
    else:
        not_before = now - timedelta(days=10)
        not_after = now - timedelta(days=1)
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_subject)
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("tl-test.local")]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    cert_path = tmp_path / "mgmt.crt"
    ca_path = tmp_path / "edge-local-ca.crt"
    cert_path.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, ca_path


def _commissioning_report_with(tmp_path, monkeypatch, *, modem_ok=True, network_ok=True, backlog=0):
    backend = ServiceOperations(base_dir=tmp_path)
    monkeypatch.setattr(backend, "_relay", lambda: None)
    monkeypatch.setattr(backend, "system_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "camera_diagnostics", lambda *_args, **_kwargs: {"ok": True, "status": {"detected": True}})
    monkeypatch.setattr(backend, "modem_status", lambda *_args, **_kwargs: {"ok": modem_ok, "error": None if modem_ok else "modem failed"})
    monkeypatch.setattr(backend, "network_status", lambda *_args, **_kwargs: {"ok": network_ok, "error": None if network_ok else "network failed"})
    monkeypatch.setattr(backend, "storage_status", lambda *_args, **_kwargs: {"ok": True, "backlog": backlog})
    monkeypatch.setattr(backend, "certificate_trust_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "software_update_status", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(backend, "_identity_section", lambda: {"ok": True, "device_id": "TL-TEST"})
    monkeypatch.setattr(backend, "_gps_time_section", lambda: {"ok": True})
    monkeypatch.setattr(backend, "_headend_section", lambda: {"ok": True})
    platform = ServicePlatform(state_dir=tmp_path / "state")
    backend.register(platform)
    return platform.call("commissioning.run", session=_session(platform))


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


@pytest.mark.parametrize(
    ("modem_ok", "network_ok", "expected_sections"),
    [
        (False, True, {"modem_network.modem"}),
        (True, False, {"modem_network.network"}),
        (False, False, {"modem_network.modem", "modem_network.network"}),
    ],
)
def test_commissioning_nested_modem_network_failures_propagate_to_result(tmp_path, monkeypatch, modem_ok, network_ok, expected_sections):
    report = _commissioning_report_with(tmp_path, monkeypatch, modem_ok=modem_ok, network_ok=network_ok)

    assert report["result"] == "FAIL"
    assert expected_sections <= {item["section"] for item in report["deviations"]}


def test_commissioning_backlog_alone_is_pass_with_deviations(tmp_path, monkeypatch):
    report = _commissioning_report_with(tmp_path, monkeypatch, backlog=3)

    assert report["result"] == "PASS WITH DEVIATIONS"
    assert report["deviations"] == [{"section": "storage", "severity": "deviation", "message": "3 captures pending upload"}]


def test_certificate_trust_status_reports_valid_certificate_metadata(tmp_path):
    cert_path, ca_path = _write_test_certificates(tmp_path)
    backend = ServiceOperations(base_dir=tmp_path)

    status = backend.certificate_trust_status(None, None, {"cert_path": cert_path, "ca_path": ca_path})

    assert status["ok"] is True
    assert status["certificate"]["subject"].endswith("CN=tl-test.local,O=TimeLapse Pro")
    assert status["certificate"]["san"] == ["tl-test.local"]
    assert len(status["certificate"]["fingerprint_sha256"]) == 64
    assert status["chain"]["ok"] is True
    assert status["error"] is None


def test_certificate_trust_status_fails_expired_certificate(tmp_path):
    cert_path, ca_path = _write_test_certificates(tmp_path, leaf_days=-1)
    backend = ServiceOperations(base_dir=tmp_path)

    status = backend.certificate_trust_status(None, None, {"cert_path": cert_path, "ca_path": ca_path})

    assert status["ok"] is False
    assert status["certificate"]["expired"] is True
    assert status["error"] == "management certificate expired"


def test_certificate_trust_status_fails_invalid_certificate(tmp_path):
    cert_path = tmp_path / "mgmt.crt"
    cert_path.write_text("not a certificate", encoding="utf-8")
    _, ca_path = _write_test_certificates(tmp_path / "valid")
    backend = ServiceOperations(base_dir=tmp_path)

    status = backend.certificate_trust_status(None, None, {"cert_path": cert_path, "ca_path": ca_path})

    assert status["ok"] is False
    assert status["error"].startswith("management certificate invalid:")


def test_certificate_trust_status_fails_missing_certificate(tmp_path):
    backend = ServiceOperations(base_dir=tmp_path)

    status = backend.certificate_trust_status(None, None, {"cert_path": tmp_path / "missing.crt"})

    assert status["ok"] is False
    assert status["error"] == "management certificate missing"


def _openssh_ed25519_public_key(seed: bytes = b"a" * 32) -> tuple[str, str]:
    blob = (
        len(b"ssh-ed25519").to_bytes(4, "big")
        + b"ssh-ed25519"
        + len(seed).to_bytes(4, "big")
        + seed
    )
    public_key = f"ssh-ed25519 {base64.b64encode(blob).decode('ascii')} test-host"
    fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
    return public_key, f"SHA256:{fingerprint}"


def test_ssh_host_identity_reports_deterministic_public_fingerprint_only(tmp_path):
    public_key, expected = _openssh_ed25519_public_key()
    key_path = tmp_path / "ssh_host_ed25519_key.pub"
    key_path.write_text(public_key, encoding="utf-8")
    (tmp_path / "bootstrap.yaml").write_text("device_id: TL-TESTEDGE\n", encoding="utf-8")
    (tmp_path / ".timelapse-release.json").write_text(
        '{"artifact_id":"TL-ART-TEST","source_commit":"abc123","version":"v-test"}',
        encoding="utf-8",
    )
    backend = ServiceOperations(base_dir=tmp_path)

    result = backend.trust_ssh_host_identity(None, None, {"host_key_paths": [key_path]})

    assert result["ok"] is True
    assert result["device_id"] == "TL-TESTEDGE"
    assert result["software"]["artifact_id"] == "TL-ART-TEST"
    assert result["keys"] == [{
        "path": str(key_path),
        "status": "observed",
        "key_type": "ED25519",
        "fingerprint_sha256": expected,
    }]
    serialized = str(result)
    assert public_key not in serialized
    assert "PRIVATE" not in serialized


def test_ssh_host_identity_never_reads_private_host_keys(tmp_path):
    private_path = tmp_path / "ssh_host_ed25519_key"
    private_path.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n", encoding="utf-8")
    backend = ServiceOperations(base_dir=tmp_path)

    result = backend.trust_ssh_host_identity(None, None, {"host_key_paths": [private_path]})

    assert result["ok"] is False
    assert result["keys"][0]["status"] == "invalid"
    assert result["deviations"][0]["reason"] == "invalid_public_host_key"
    assert "private SSH host key paths are not allowed" in result["deviations"][0]["error"]
    assert "secret" not in str(result)


def test_ssh_host_identity_handles_missing_host_key_explicitly(tmp_path):
    missing = tmp_path / "ssh_host_ed25519_key.pub"
    backend = ServiceOperations(base_dir=tmp_path)

    result = backend.trust_ssh_host_identity(None, None, {"host_key_paths": [missing]})

    assert result["ok"] is False
    assert result["keys"] == [{"path": str(missing), "status": "missing"}]
    assert result["deviations"] == [{
        "path": str(missing),
        "severity": "deviation",
        "reason": "missing_public_host_key",
    }]


def test_ssh_host_identity_reports_malformed_public_key_as_failure(tmp_path):
    malformed = tmp_path / "ssh_host_ed25519_key.pub"
    malformed.write_text("ssh-ed25519 not-base64", encoding="utf-8")
    backend = ServiceOperations(base_dir=tmp_path)

    result = backend.trust_ssh_host_identity(None, None, {"host_key_paths": [malformed]})

    assert result["ok"] is False
    assert result["keys"][0]["status"] == "invalid"
    assert result["deviations"][0]["severity"] == "fail"
    assert result["deviations"][0]["reason"] == "invalid_public_host_key"


def test_ui_and_cli_route_through_shared_service_operations_backend():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    cli = (root / "edge/tools/bootstrap_cli.py").read_text(encoding="utf-8")
    ui = (root / "edge/scripts/totp-service.py").read_text(encoding="utf-8")

    assert "from service_operations import create_service_platform" in cli
    assert "from service_operations import create_service_platform" in ui
    assert "--service-operation" in cli
    assert "--service-operation" in ui
    assert "camera.config.set_temporary" in ui
