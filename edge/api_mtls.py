"""Edge-owned identity for mutual TLS to the Headend API.

The private key is created locally and is never returned to the Headend. A
separate identity is used for this purpose so local-management TLS and SSH
support identities remain independently rotatable and revocable.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID


DEVICE_URI_PREFIX = "urn:timelapse:edge:"
DEFAULT_KEY_PATH = Path("/etc/timelapse/device_keys/headend-api.key")
DEFAULT_CERT_PATH = Path("/etc/timelapse/certs/headend-api.crt")
DEFAULT_CA_PATH = Path("/etc/timelapse/certs/headend-api-ca.crt")


def _device_uri(device_id: str) -> str:
    value = (device_id or "").strip()
    if not value.startswith("TL-") or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for ch in value.upper()):
        raise RuntimeError("invalid device identity")
    return f"{DEVICE_URI_PREFIX}{value}"


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
    module. The exact device identity is carried both as CN and URI SAN.
    """
    expected_uri = _device_uri(device_id)
    if key_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey):
            raise RuntimeError("Headend API mTLS key has unexpected type")
        if (key_path.stat().st_mode & 0o077) != 0:
            raise RuntimeError("Headend API mTLS private key permissions are too broad")
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
                x509.UniformResourceIdentifier(expected_uri),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return key_path, csr.public_bytes(serialization.Encoding.PEM).decode("ascii")


def _validate_certificate_bundle(
    device_id: str,
    certificate_pem: str,
    ca_certificate_pem: str,
    *,
    key_path: Path,
) -> tuple[x509.Certificate, x509.Certificate]:
    """Fail closed unless the returned certificate is exactly ours.

    Enrollment is still authenticated by the legacy signed API credential, but
    that does not justify trusting arbitrary certificate material returned by a
    compromised/misconfigured endpoint. Before replacing public material on
    disk we bind the response back to the Edge-owned private key and device URI.
    """
    expected_uri = _device_uri(device_id)
    cert = x509.load_pem_x509_certificate(certificate_pem.encode("ascii"))
    ca = x509.load_pem_x509_certificate(ca_certificate_pem.encode("ascii"))

    try:
        basic = ca.extensions.get_extension_for_class(x509.BasicConstraints).value
    except x509.ExtensionNotFound as exc:
        raise RuntimeError("Headend API CA lacks BasicConstraints") from exc
    if not basic.ca:
        raise RuntimeError("Headend API CA certificate is not a CA")
    if cert.issuer != ca.subject:
        raise RuntimeError("Headend API certificate issuer does not match supplied CA")

    ca_public_key = ca.public_key()
    if not isinstance(ca_public_key, ec.EllipticCurvePublicKey):
        raise RuntimeError("Headend API CA public key has unexpected type")
    try:
        ca_public_key.verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            ec.ECDSA(cert.signature_hash_algorithm),
        )
    except InvalidSignature as exc:
        raise RuntimeError("Headend API certificate signature is invalid") from exc

    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    except x509.ExtensionNotFound as exc:
        raise RuntimeError("Headend API certificate lacks ExtendedKeyUsage") from exc
    if ExtendedKeyUsageOID.CLIENT_AUTH not in eku:
        raise RuntimeError("Headend API certificate lacks CLIENT_AUTH EKU")

    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound as exc:
        raise RuntimeError("Headend API certificate lacks device URI SAN") from exc
    uris = set(san.get_values_for_type(x509.UniformResourceIdentifier))
    if uris != {expected_uri}:
        raise RuntimeError("Headend API certificate device URI SAN mismatch")

    common_names = [a.value for a in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)]
    if common_names != [device_id]:
        raise RuntimeError("Headend API certificate common name mismatch")

    now = datetime.now(timezone.utc)
    if cert.not_valid_before_utc > now or cert.not_valid_after_utc <= now:
        raise RuntimeError("Headend API certificate is not currently valid")

    if not key_path.exists():
        raise RuntimeError("Headend API mTLS private key is missing")
    if (key_path.stat().st_mode & 0o077) != 0:
        raise RuntimeError("Headend API mTLS private key permissions are too broad")
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise RuntimeError("Headend API mTLS key has unexpected type")
    cert_public = cert.public_key()
    if not isinstance(cert_public, ec.EllipticCurvePublicKey):
        raise RuntimeError("Headend API certificate public key has unexpected type")
    if cert_public.public_numbers() != key.public_key().public_numbers():
        raise RuntimeError("Headend API certificate does not match the Edge-owned private key")

    return cert, ca


def install_certificate_bundle(
    device_id: str,
    certificate_pem: str,
    ca_certificate_pem: str,
    *,
    key_path: Path = DEFAULT_KEY_PATH,
    cert_path: Path = DEFAULT_CERT_PATH,
    ca_path: Path = DEFAULT_CA_PATH,
) -> tuple[Path, Path]:
    """Validate identity, signature and key binding before installing public material."""
    _validate_certificate_bundle(
        device_id,
        certificate_pem,
        ca_certificate_pem,
        key_path=key_path,
    )
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
