"""Internal PKI for local Edge management TLS.

The CA is deliberately separate from public Headend TLS and from future support
credentials.  It signs only local Edge server certificates for the stable mDNS
name ``tl-<device-id>.local``.
"""

from __future__ import annotations

import ipaddress
import os
import plistlib
import stat
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


CA_DIR_ENV = "TIMELAPSE_EDGE_LOCAL_CA_DIR"
# This path is included in the encrypted Restic project snapshot.  Do not move
# the CA private key into the ordinary Headend tar.gz backup, which is an
# operational restore archive rather than an encrypted key vault.
DEFAULT_CA_DIR = Path("/data-fast/backup/timelapse-artifacts/pki/edge-local-ca")
CA_CERT_NAME = "edge-local-ca.crt"
CA_KEY_NAME = "edge-local-ca.key"


def local_edge_hostname(device_id: str) -> str:
    normalized = "".join(ch for ch in device_id.lower() if ch.isalnum())
    if normalized.startswith("tl"):
        normalized = normalized[2:]
    if len(normalized) < 6:
        raise ValueError("Edge-ID er for kort til lokalt certifikatnavn")
    return f"tl-{normalized}.local"


def _ca_dir() -> Path:
    return Path(os.getenv(CA_DIR_ENV, str(DEFAULT_CA_DIR))).expanduser()


def _paths() -> tuple[Path, Path]:
    directory = _ca_dir()
    return directory / CA_CERT_NAME, directory / CA_KEY_NAME


def local_edge_ca_status() -> dict[str, str | bool]:
    """Return a non-sensitive CA status for the administrator UI."""
    cert_path, key_path = _paths()
    if cert_path.exists() != key_path.exists():
        return {
            "initialized": False,
            "healthy": False,
            "detail": "CA-lageret er inkonsistent; certifikat og nøgle skal gendannes samlet.",
        }
    if not cert_path.exists():
        return {
            "initialized": False,
            "healthy": True,
            "detail": "CA er ikke initialiseret endnu.",
        }
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        key_mode = stat.S_IMODE(key_path.stat().st_mode)
        return {
            "initialized": True,
            "healthy": key_mode == 0o600,
            "subject": cert.subject.rfc4514_string(),
            "serial_number": format(cert.serial_number, "x"),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "detail": "CA er klar." if key_mode == 0o600 else "CA-nøglen har for åbne filrettigheder.",
        }
    except Exception as exc:
        return {"initialized": False, "healthy": False, "detail": f"CA kan ikke læses: {exc}"}


def _write_private_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    path.chmod(0o600)


def ensure_local_edge_ca() -> tuple[Path, Path]:
    """Return the persistent Edge-local CA, generating it once when absent."""
    cert_path, key_path = _paths()
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path
    if cert_path.exists() != key_path.exists():
        raise RuntimeError("Edge-local CA er inkonsistent; certifikat og nøgle skal gendannes samlet")

    cert_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cert_path.parent.chmod(0o700)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.COMMON_NAME, "TimeLapse Pro Edge Local CA"),
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
    _write_private_key(key_path, key)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert_path.chmod(0o644)
    return cert_path, key_path


def require_local_edge_ca() -> tuple[Path, Path]:
    """Return the CA only when a privileged ceremony has initialized it."""
    cert_path, key_path = _paths()
    status = local_edge_ca_status()
    if not status.get("initialized") or not status.get("healthy"):
        raise RuntimeError(
            "Edge Local CA er ikke klar. En superadministrator skal initialisere eller gendanne den i Systemadministration."
        )
    return cert_path, key_path


def issue_local_edge_server_certificate(device_id: str) -> dict[str, str]:
    """Issue a unique local-management TLS certificate for a pre-verified Edge."""
    hostname = local_edge_hostname(device_id)
    ca_cert_path, ca_key_path = require_local_edge_ca()
    ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
    ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
    if not isinstance(ca_key, ec.EllipticCurvePrivateKey):
        raise RuntimeError("Edge-local CA-nøgle har ugyldig type")

    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Edge Local Management"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=True, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName(hostname),
            x509.IPAddress(ipaddress.ip_address("192.168.42.1")),
        ]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return {
        "hostname": hostname,
        "certificate_pem": cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        "private_key_pem": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii"),
        "ca_certificate_pem": ca_cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        "serial_number": format(cert.serial_number, "x"),
    }


def build_apple_ca_profile() -> bytes:
    """Create an installable Apple configuration profile for the local CA.

    Trusting a private root remains an explicit device-owner action in iOS/iPadOS.
    The profile avoids a raw-IP browser exception after it has been installed.
    """
    cert_path, _key_path = require_local_edge_ca()
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    profile_uuid = str(uuid.uuid4()).upper()
    payload_uuid = str(uuid.uuid4()).upper()
    profile = {
        "PayloadContent": [{
            "PayloadCertificateFileName": "TimeLapse-Pro-Edge-Local-CA.cer",
            "PayloadContent": cert.public_bytes(serialization.Encoding.DER),
            "PayloadDescription": "Stoler pa TimeLapse Pro Edge lokale administrationscertifikater.",
            "PayloadDisplayName": "TimeLapse Pro Edge Local CA",
            "PayloadIdentifier": "dk.froekjaer.timelapse.edge-local-ca.certificate",
            "PayloadOrganization": "TimeLapse Pro",
            "PayloadType": "com.apple.security.root",
            "PayloadUUID": payload_uuid,
            "PayloadVersion": 1,
        }],
        "PayloadDisplayName": "TimeLapse Pro lokal Edge-adgang",
        "PayloadDescription": "Gor lokal Edge-adgang sikker pa denne enhed.",
        "PayloadIdentifier": "dk.froekjaer.timelapse.edge-local-ca.profile",
        "PayloadOrganization": "TimeLapse Pro",
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": profile_uuid,
        "PayloadVersion": 1,
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=False)
