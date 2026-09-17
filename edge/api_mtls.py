"""Edge-owned identity for mutual TLS to the Headend API.

The private key is created locally and is never returned to the Headend.  A
separate identity is used for this purpose so local-management TLS and SSH
support identities remain independently rotatable and revocable.
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


DEVICE_URI_PREFIX = "urn:timelapse:edge:"
DEFAULT_KEY_PATH = Path("/etc/timelapse/device_keys/headend-api.key")
DEFAULT_CERT_PATH = Path("/etc/timelapse/certs/headend-api.crt")
DEFAULT_CA_PATH = Path("/etc/timelapse/certs/headend-api-ca.crt")


def _secure_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.name == "device_keys":
        path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    finally:
        path.chmod(mode)


def ensure_key_and_csr(device_id: str, *, key_path: Path = DEFAULT_KEY_PATH) -> tuple[Path, str]:
    """Return a CSR for the stable Edge-owned API client key.

    Existing keys are reused for renewal; no private key bytes leave this
    module.  The exact device identity is carried both as CN and URI SAN.
    """
    if key_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey):
            raise RuntimeError("Headend API mTLS key has unexpected type")
    else:
        key = ec.generate_private_key(ec.SECP256R1())
        _secure_write(
            key_path,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            0o600,
        )

    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Edge Headend API Client"),
        x509.NameAttribute(NameOID.COMMON_NAME, device_id),
    ])
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.UniformResourceIdentifier(f"{DEVICE_URI_PREFIX}{device_id}"),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return key_path, csr.public_bytes(serialization.Encoding.PEM).decode("ascii")


def install_certificate_bundle(
    certificate_pem: str,
    ca_certificate_pem: str,
    *,
    cert_path: Path = DEFAULT_CERT_PATH,
    ca_path: Path = DEFAULT_CA_PATH,
) -> tuple[Path, Path]:
    """Validate purpose/device material structurally, then atomically-ish write public material."""
    cert = x509.load_pem_x509_certificate(certificate_pem.encode("ascii"))
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    if ExtendedKeyUsageOID.CLIENT_AUTH not in eku:
        raise RuntimeError("Headend API certificate lacks CLIENT_AUTH EKU")
    ca = x509.load_pem_x509_certificate(ca_certificate_pem.encode("ascii"))
    if cert.issuer != ca.subject:
        raise RuntimeError("Headend API certificate issuer does not match supplied CA")
    _secure_write(cert_path, certificate_pem.encode("ascii"), 0o644)
    _secure_write(ca_path, ca_certificate_pem.encode("ascii"), 0o644)
    return cert_path, ca_path


def client_certificate_paths(
    *,
    key_path: Path = DEFAULT_KEY_PATH,
    cert_path: Path = DEFAULT_CERT_PATH,
) -> tuple[str, str] | None:
    if not key_path.exists() or not cert_path.exists():
        return None
    if (key_path.stat().st_mode & 0o077) != 0:
        raise RuntimeError("Headend API mTLS private key permissions are too broad")
    return str(cert_path), str(key_path)
