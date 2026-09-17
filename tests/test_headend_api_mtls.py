from __future__ import annotations

from pathlib import Path

import pytest
from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from edge.api_mtls import ensure_key_and_csr, install_certificate_bundle
from headend.services import headend_api_mtls
from headend.api.edge_api_mtls_api import (
    create_headend_api_mtls_admin_router,
    create_headend_api_mtls_edge_router,
)


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


def test_headend_api_mtls_routers_are_registered_in_runtime():
    """Both mTLS router factories must be wired into the production app."""
    root = Path(__file__).resolve().parents[1]

    admin_bundle = (
        root / "headend" / "api" / "admin_route_bundle.py"
    ).read_text(encoding="utf-8")
    main = (
        root / "headend" / "main.py"
    ).read_text(encoding="utf-8")

    assert "create_headend_api_mtls_admin_router" in admin_bundle
    assert "create_headend_api_mtls_edge_router" in admin_bundle
    assert (
        "app.include_router("
        "create_headend_api_mtls_admin_router(require_role)"
        ")"
        in admin_bundle
    )

    assert (
        "create_headend_api_mtls_edge_router(verify_device_token)"
        in admin_bundle
    )
    assert (
        "_reconcile_edge_lifecycle, _verify_device_token)"
        in main
    )


def test_headend_api_mtls_router_contracts_and_auth_dependencies():
    """Router factories expose the intended methods and preserve auth boundaries."""
    requested_roles = []

    def fake_require_role(role):
        requested_roles.append(role)
        return None

    admin_router = create_headend_api_mtls_admin_router(fake_require_role)
    admin_routes = {
        (route.path, method)
        for route in admin_router.routes
        for method in getattr(route, "methods", set())
    }

    assert (
        "/api/admin/trust/headend-api-mtls/status",
        "GET",
    ) in admin_routes
    assert (
        "/api/admin/trust/headend-api-mtls/initialize",
        "POST",
    ) in admin_routes
    assert requested_roles == ["admin", "super_admin"]

    async def fake_verify_device_token():
        return None

    edge_router = create_headend_api_mtls_edge_router(
        fake_verify_device_token
    )

    enroll = next(
        route
        for route in edge_router.routes
        if route.path == "/api/trust/headend-api-mtls/{device_id}/enroll"
    )

    assert "POST" in enroll.methods
    assert any(
        dependency.call is fake_verify_device_token
        for dependency in enroll.dependant.dependencies
    )
