from __future__ import annotations

from pathlib import Path

import pytest
from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from edge.api_mtls import ensure_key_and_csr, install_certificate_bundle
from headend.services import headend_api_mtls


DEVICE_1 = "TL-C87FF9587CA0"
DEVICE_2 = "TL-043EB9E72EFD"


def _issue(monkeypatch, tmp_path: Path, device_id: str, key_name: str = "device.key"):
    ca_dir = tmp_path / "ca"
    monkeypatch.setenv(headend_api_mtls.CA_DIR_ENV, str(ca_dir))
    headend_api_mtls.initialize_ca()
    key_path = tmp_path / key_name
    _, csr = ensure_key_and_csr(device_id, key_path=key_path)
    issued = headend_api_mtls.issue_client_certificate(device_id, csr)
    return key_path, issued


def test_edge_owned_key_and_csr_are_bound_to_exact_device(monkeypatch, tmp_path):
    key_path, issued = _issue(monkeypatch, tmp_path, DEVICE_1)

    cert_path = tmp_path / "headend-api.crt"
    ca_path = tmp_path / "headend-api-ca.crt"
    installed = install_certificate_bundle(
        DEVICE_1,
        str(issued["certificate_pem"]),
        str(issued["ca_certificate_pem"]),
        key_path=key_path,
        cert_path=cert_path,
        ca_path=ca_path,
    )

    assert installed == (cert_path, ca_path)
    assert key_path.stat().st_mode & 0o077 == 0
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    assert san.get_values_for_type(x509.UniformResourceIdentifier) == [
        f"urn:timelapse:edge:{DEVICE_1}"
    ]


def test_headend_rejects_csr_for_different_device_identity(monkeypatch, tmp_path):
    ca_dir = tmp_path / "ca"
    monkeypatch.setenv(headend_api_mtls.CA_DIR_ENV, str(ca_dir))
    headend_api_mtls.initialize_ca()
    _, csr = ensure_key_and_csr(DEVICE_1, key_path=tmp_path / "edge1.key")

    with pytest.raises(headend_api_mtls.HeadendApiMtlsError, match="device URI SAN"):
        headend_api_mtls.issue_client_certificate(DEVICE_2, csr)


def test_edge_rejects_certificate_for_wrong_device(monkeypatch, tmp_path):
    key_path, issued = _issue(monkeypatch, tmp_path, DEVICE_1)

    with pytest.raises(RuntimeError, match="device URI SAN mismatch"):
        install_certificate_bundle(
            DEVICE_2,
            str(issued["certificate_pem"]),
            str(issued["ca_certificate_pem"]),
            key_path=key_path,
            cert_path=tmp_path / "bad.crt",
            ca_path=tmp_path / "bad-ca.crt",
        )


def test_edge_rejects_certificate_that_does_not_match_private_key(monkeypatch, tmp_path):
    key_path_1, issued_1 = _issue(monkeypatch, tmp_path, DEVICE_1, "edge1.key")
    _, csr_2 = ensure_key_and_csr(DEVICE_1, key_path=tmp_path / "edge1-other.key")
    issued_for_other_key = headend_api_mtls.issue_client_certificate(DEVICE_1, csr_2)

    with pytest.raises(RuntimeError, match="does not match the Edge-owned private key"):
        install_certificate_bundle(
            DEVICE_1,
            str(issued_for_other_key["certificate_pem"]),
            str(issued_for_other_key["ca_certificate_pem"]),
            key_path=key_path_1,
            cert_path=tmp_path / "bad.crt",
            ca_path=tmp_path / "bad-ca.crt",
        )

    # The certificate issued for the original key remains acceptable.
    install_certificate_bundle(
        DEVICE_1,
        str(issued_1["certificate_pem"]),
        str(issued_1["ca_certificate_pem"]),
        key_path=key_path_1,
        cert_path=tmp_path / "good.crt",
        ca_path=tmp_path / "good-ca.crt",
    )


def test_ca_initialization_fails_closed_on_inconsistent_storage(monkeypatch, tmp_path):
    ca_dir = tmp_path / "ca"
    monkeypatch.setenv(headend_api_mtls.CA_DIR_ENV, str(ca_dir))
    ca_dir.mkdir()
    (ca_dir / headend_api_mtls.CA_CERT_NAME).write_text("partial", encoding="utf-8")

    with pytest.raises(headend_api_mtls.HeadendApiMtlsError, match="inconsistent"):
        headend_api_mtls.initialize_ca()
