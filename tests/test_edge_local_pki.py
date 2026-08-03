from __future__ import annotations

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtensionOID

from headend.services import edge_local_pki as pki


def test_ca_requires_explicit_initialization(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(pki.CA_DIR_ENV, str(tmp_path / "edge-ca"))

    assert pki.local_edge_ca_status()["initialized"] is False
    try:
        pki.issue_local_edge_server_certificate("TL-C87FF9587CA0")
    except RuntimeError as exc:
        assert "superadministrator" in str(exc)
    else:
        raise AssertionError("Certificate issuance must not silently create a CA")


def test_ca_issues_unique_hostname_bound_server_certificate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(pki.CA_DIR_ENV, str(tmp_path / "edge-ca"))
    cert_path, key_path = pki.ensure_local_edge_ca()
    issued = pki.issue_local_edge_server_certificate("TL-C87FF9587CA0")

    assert cert_path.exists()
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert issued["hostname"] == "tl-c87ff9587ca0.local"

    leaf = x509.load_pem_x509_certificate(issued["certificate_pem"].encode())
    ca = x509.load_pem_x509_certificate(issued["ca_certificate_pem"].encode())
    assert leaf.issuer == ca.subject
    san = leaf.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    assert "tl-c87ff9587ca0.local" in san.get_values_for_type(x509.DNSName)
    assert str(san.get_values_for_type(x509.IPAddress)[0]) == "192.168.42.1"
    assert isinstance(
        serialization.load_pem_private_key(issued["private_key_pem"].encode(), password=None),
        ec.EllipticCurvePrivateKey,
    )


def test_apple_profile_contains_the_initialized_ca(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(pki.CA_DIR_ENV, str(tmp_path / "edge-ca"))
    pki.ensure_local_edge_ca()

    profile = pki.build_apple_ca_profile()
    assert b"com.apple.security.root" in profile
    assert b"TimeLapse Pro lokal Edge-adgang" in profile


def test_ca_router_keeps_private_key_out_of_the_http_surface() -> None:
    source = (pki.Path(__file__).parents[1] / "headend" / "api" / "edge_local_pki_api.py").read_text()
    assert '"/initialize"' in source
    assert '"/apple-profile"' in source
    assert "require_role(\"super_admin\")" in source
    assert "private_key_pem" not in source


def test_default_ca_store_is_in_the_encrypted_project_snapshot_tree() -> None:
    assert str(pki.DEFAULT_CA_DIR).startswith("/data-fast/backup/timelapse-artifacts/")
