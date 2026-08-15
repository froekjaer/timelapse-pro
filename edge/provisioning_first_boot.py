"""Edge-side WP-4 first-boot key generation.

Only public material and CSRs leave the Edge.  Permanent operational private
keys are written locally and never returned from these functions.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID


def generate_ssh_identity(private_key_path: Path) -> dict[str, str]:
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    key = ed25519.Ed25519PrivateKey.generate()
    private_key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    private_key_path.chmod(0o600)
    public_key = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    ).decode("ascii")
    return {
        "public_key": public_key,
        "private_key_path": str(private_key_path),
        "private_key_exported": "false",
    }


def generate_tls_key_and_csr(
    *,
    device_id: str,
    hostname: str,
    private_key_path: Path,
    ip_address: str = "192.168.42.1",
) -> dict[str, str]:
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    private_key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    private_key_path.chmod(0o600)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TimeLapse Pro"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Edge Local Management"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName(hostname),
            x509.DNSName(device_id.lower()),
            x509.IPAddress(ipaddress.ip_address(ip_address)),
        ]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return {
        "csr_pem": csr.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        "private_key_path": str(private_key_path),
        "private_key_exported": "false",
    }


def build_first_boot_enrollment_payload(
    *,
    device_id: str,
    envelope_id: str,
    ssh_public_key: str,
    tls_csr_pem: str,
    hardware_evidence: dict,
) -> dict:
    return {
        "device_id": device_id,
        "envelope_id": envelope_id,
        "ssh_public_key": ssh_public_key,
        "tls_csr_pem": tls_csr_pem,
        "hardware_evidence": hardware_evidence,
        "private_keys_included": False,
    }
