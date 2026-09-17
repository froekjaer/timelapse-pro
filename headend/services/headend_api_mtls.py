"""Dedicated mTLS trust profile for Edge -> Headend API traffic.

This CA is deliberately separate from:
- the public TLS certificate presented by backend.timelapse-pro.dk;
- the Edge-local management/server certificate CA;
- SSH tunnel identities.

Private client keys are generated on the physical Edge and never cross this
boundary.  The Headend receives and signs only a CSR that is bound to the exact
device identity through a URI SAN.
"""
from __future__ import annotations

import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID


CA_DIR_ENV = "TIMELAPSE_HEADEND_API_MTLS_CA_DIR"
DEFAULT_CA_DIR = Path("/data-fast/backup/timelapse-artifacts/pki/headend-api-mtls-ca")
CA_CERT_NAME = "headend-api-mtls-ca.crt"
CA_KEY_NAME = "headend-api-mtls-ca.key"
DEVICE_URI_PREFIX = "urn:timelapse:edge:"
DEFAULT_CERT_DAYS = 90


class HeadendApiMtlsError(ValueError):
    """Fail-closed API mTLS trust-profile error."""


def device_uri(device_id: str) -> str:
    value = (device_id or "").strip()
    if not value.startswith("TL-") or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for ch in value.upper()):
        raise HeadendApiMtlsError("invalid device identity")
    return f"{DEVICE_URI_PREFIX}{value}"


def _ca_dir() -> Path:
    return Path(os.getenv(CA_DIR_ENV, str(DEFAULT_CA_DIR))).expanduser()


def ca_paths() -> tuple[Path, Path]:
    directory = _ca_dir()
    return directory / CA_CERT_NAME, directory / CA_KEY_NAME


def ca_status() -> dict[str, object]:
    cert_path, key_path = ca_paths()
    if cert_path.exists() != key_path.exists():
        return {"initialized": False, "healthy": False, "detail": "API mTLS CA storage is inconsistent"}
    if not cert_path.exists():
        return {"initialized": False, "healthy": True, "detail": "API mTLS CA is not initialized"}
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        mode = stat.S_IMODE(key_path.stat().st_mode)
        return {
            "initialized": True,
            "healthy": mode == 0o600,
            "subject": cert.subject.rfc4514_string(),
            "serial_number": format(cert.serial_number, "x"),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "certificate_path": str(cert_path),
            "detail": "API mTLS CA is ready" if mode == 0o600 else "API mTLS CA key permissions are too broad",
        }
    except Exception as exc:
        return {"initialized": False, "healthy": False, "detail": f"API mTLS CA cannot be read: {exc}"}


def initialize_ca() -> tuple[Path, Path]:
    """Create the profile-specific CA once.  This is an explicit admin ceremony."""
    cert_path, key_path = ca_paths()
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path
    if cert_path.exists() != key_path.exists():
        raise HeadendApiMtlsError("API mTLS CA storage is inconsistent")
    cert_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cert_path.parent.chmod(0o700)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Trust Service"),
        x509.NameAttribute(NameOID.COMMON_NAME, "TimeLapse Pro Headend API mTLS CA"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    key_path.chmod(0o600)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert_path.chmod(0o644)
    return cert_path, key_path


def require_ca() -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey, Path]:
    cert_path, key_path = ca_paths()
    status = ca_status()
    if not status.get("initialized") or not status.get("healthy"):
        raise HeadendApiMtlsError("Headend API mTLS CA is not initialized and healthy")
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise HeadendApiMtlsError("Headend API mTLS CA key has invalid type")
    return cert, key, cert_path


def _csr_device_uris(csr: x509.CertificateSigningRequest) -> set[str]:
    try:
        san = csr.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound:
        return set()
    return {str(uri) for uri in san.get_values_for_type(x509.UniformResourceIdentifier)}


def issue_client_certificate(device_id: str, csr_pem: str, *, days: int = DEFAULT_CERT_DAYS) -> dict[str, object]:
    """Sign an Edge-generated CSR for Headend API client authentication only."""
    if days < 1 or days > 180:
        raise HeadendApiMtlsError("API mTLS certificate lifetime outside allowed range")
    try:
        csr = x509.load_pem_x509_csr(csr_pem.encode("ascii"))
    except Exception as exc:
        raise HeadendApiMtlsError("invalid CSR") from exc
    if not csr.is_signature_valid:
        raise HeadendApiMtlsError("CSR signature invalid")
    expected_uri = device_uri(device_id)
    uris = _csr_device_uris(csr)
    if uris != {expected_uri}:
        raise HeadendApiMtlsError("CSR must contain exactly the requested device URI SAN")

    common_names = [a.value for a in csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)]
    if common_names != [device_id]:
        raise HeadendApiMtlsError("CSR common name must equal device identity")

    ca_cert, ca_key, ca_cert_path = require_ca()
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=True, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(expected_uri)]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return {
        "certificate_pem": certificate.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        "ca_certificate_pem": ca_cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        "serial_number": format(certificate.serial_number, "x"),
        "fingerprint_sha256": certificate.fingerprint(hashes.SHA256()).hex(),
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "device_uri": expected_uri,
        "not_after": certificate.not_valid_after_utc.isoformat(),
        "ca_certificate_path": str(ca_cert_path),
    }
