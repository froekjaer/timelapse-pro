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
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID


CA_DIR_ENV = "TIMELAPSE_HEADEND_API_MTLS_CA_DIR"
KEYCHAIN_HELPER_ENV = "TIMELAPSE_HEADEND_API_MTLS_KEYCHAIN_HELPER"
DEFAULT_CA_DIR = Path(
    "/Library/Application Support/TimeLapse Pro/pki/headend-api-mtls-ca"
)
DEFAULT_KEYCHAIN_HELPER = Path("/usr/local/libexec/timelapse-ca-keychain")
CA_CERT_NAME = "headend-api-mtls-ca.crt"
CA_KEY_NAME = "headend-api-mtls-ca.key"
DEVICE_URI_PREFIX = "urn:timelapse:edge:"
DEFAULT_CERT_DAYS = 90
_MAX_PASSPHRASE_BYTES = 4096


class HeadendApiMtlsError(ValueError):
    """Fail-closed API mTLS trust-profile error."""


class HeadendApiMtlsUnavailableError(HeadendApiMtlsError):
    """Operational CA unavailability; callers should return service unavailable."""


def device_uri(device_id: str) -> str:
    value = (device_id or "").strip()
    if not value.startswith("TL-") or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for ch in value.upper()):
        raise HeadendApiMtlsError("invalid device identity")
    return f"{DEVICE_URI_PREFIX}{value}"


def _ca_dir() -> Path:
    return Path(os.getenv(CA_DIR_ENV, str(DEFAULT_CA_DIR))).expanduser()


def _keychain_helper() -> Path:
    return Path(
        os.getenv(KEYCHAIN_HELPER_ENV, str(DEFAULT_KEYCHAIN_HELPER))
    ).expanduser()


def ca_paths() -> tuple[Path, Path]:
    directory = _ca_dir()
    return directory / CA_CERT_NAME, directory / CA_KEY_NAME


def _ca_passphrase() -> bytes:
    """Retrieve the CA passphrase without exposing it through argv/env/logs."""
    helper = _keychain_helper()
    try:
        completed = subprocess.run(
            [str(helper), "--read"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA passphrase is unavailable"
        ) from exc

    secret = completed.stdout
    if completed.returncode != 0 or not secret or len(secret) > _MAX_PASSPHRASE_BYTES:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA passphrase is unavailable"
        )
    return secret


def _load_ca_private_key(key_path: Path) -> ec.EllipticCurvePrivateKey:
    mode = stat.S_IMODE(key_path.stat().st_mode)
    if mode != 0o600:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA key permissions are too broad"
        )

    password = _ca_passphrase()
    try:
        key = serialization.load_pem_private_key(
            key_path.read_bytes(),
            password=password,
        )
    except (TypeError, ValueError) as exc:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA private key cannot be unlocked"
        ) from exc

    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA key has invalid type"
        )
    if not isinstance(key.curve, ec.SECP256R1):
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA key has invalid curve"
        )
    return key


def _validate_ca_binding(
    cert: x509.Certificate,
    key: ec.EllipticCurvePrivateKey,
) -> None:
    if cert.public_key().public_numbers() != key.public_key().public_numbers():
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA certificate does not match its private key"
        )
    try:
        basic = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    except x509.ExtensionNotFound as exc:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA certificate is missing CA constraints"
        ) from exc
    if not basic.ca:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA certificate is not a CA"
        )


def ca_status() -> dict[str, object]:
    cert_path, key_path = ca_paths()
    if cert_path.exists() != key_path.exists():
        return {
            "initialized": False,
            "healthy": False,
            "detail": "API mTLS CA storage is inconsistent",
        }
    if not cert_path.exists():
        return {
            "initialized": False,
            "healthy": True,
            "detail": "API mTLS CA is not initialized",
        }

    metadata: dict[str, object] = {
        "initialized": True,
        "healthy": False,
        "certificate_path": str(cert_path),
    }
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        metadata.update(
            {
                "subject": cert.subject.rfc4514_string(),
                "serial_number": format(cert.serial_number, "x"),
                "not_after": cert.not_valid_after_utc.isoformat(),
            }
        )
        key = _load_ca_private_key(key_path)
        _validate_ca_binding(cert, key)
        metadata.update({"healthy": True, "detail": "API mTLS CA is ready"})
    except HeadendApiMtlsError as exc:
        metadata["detail"] = str(exc)
    except Exception:
        metadata["detail"] = "API mTLS CA cannot be read"
    return metadata


def _write_new_file(path: Path, data: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if fd >= 0:
            os.close(fd)
    path.chmod(mode)


def initialize_ca() -> tuple[Path, Path]:
    """Create the profile-specific CA once. This is an explicit admin ceremony."""
    cert_path, key_path = ca_paths()
    if cert_path.exists() and key_path.exists():
        require_ca()
        return cert_path, key_path
    if cert_path.exists() != key_path.exists():
        raise HeadendApiMtlsError("API mTLS CA storage is inconsistent")

    # Retrieve the passphrase before mutating CA storage. If Keychain access is
    # unavailable, initialization fails without leaving partial CA material.
    password = _ca_passphrase()

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
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    try:
        _write_new_file(key_path, key_pem, 0o600)
        _write_new_file(cert_path, cert_pem, 0o644)
    except FileExistsError as exc:
        raise HeadendApiMtlsError(
            "API mTLS CA initialization collided with existing storage"
        ) from exc

    return cert_path, key_path


def require_ca() -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey, Path]:
    cert_path, key_path = ca_paths()
    if cert_path.exists() != key_path.exists():
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA storage is inconsistent"
        )
    if not cert_path.exists():
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA is not initialized"
        )

    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except Exception as exc:
        raise HeadendApiMtlsUnavailableError(
            "Headend API mTLS CA certificate cannot be read"
        ) from exc

    key = _load_ca_private_key(key_path)
    _validate_ca_binding(cert, key)
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
