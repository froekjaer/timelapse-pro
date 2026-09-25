"""Bind nginx-verified Edge API client certificates to device identity.

The public TLS terminator remains nginx. During migration nginx may request
client certificates optionally; when enforcement is enabled it becomes the
network-level mTLS gate. This module is the application-level binding layer:
it maps nginx's verified client-certificate serial to the active
EdgeCredentialInventory record for the exact device.

The verifier never replaces the existing bearer, request-signature or Edge
attestation controls. It is an additional identity factor.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from database import EdgeCredentialInventory


MODE_ENV = "TIMELAPSE_EDGE_API_MTLS_MODE"
VALID_MODES = {"off", "optional", "required"}
VERIFY_HEADER = "x-tlp-mtls-verify"
SERIAL_HEADER = "x-tlp-mtls-serial"


class EdgeApiMtlsIdentityError(ValueError):
    """Raised when a presented/required mTLS identity cannot be trusted."""


@dataclass(frozen=True)
class EdgeApiMtlsIdentity:
    mode: str
    presented: bool
    verified: bool
    device_id: str
    credential_id: str | None = None


def enforcement_mode(value: str | None = None) -> str:
    """Resolve the migration mode, failing closed on invalid configuration."""
    raw = value if value is not None else os.getenv(MODE_ENV, "off")
    mode = str(raw).strip().lower()
    if mode not in VALID_MODES:
        raise EdgeApiMtlsIdentityError(
            f"invalid {MODE_ENV}: expected off, optional or required"
        )
    return mode


def canonical_certificate_serial(value: str) -> str:
    """Return the same lower-case hex form used by certificate enrollment."""
    cleaned = str(value or "").strip().replace(":", "")
    if not cleaned:
        raise EdgeApiMtlsIdentityError("mTLS client certificate serial is missing")
    try:
        number = int(cleaned, 16)
    except ValueError as exc:
        raise EdgeApiMtlsIdentityError(
            "mTLS client certificate serial is invalid"
        ) from exc
    if number <= 0:
        raise EdgeApiMtlsIdentityError("mTLS client certificate serial is invalid")
    return format(number, "x")


def verify_edge_api_mtls_identity(
    db,
    *,
    device_id: str,
    headers,
    mode: str | None = None,
    allow_legacy_enrollment: bool = False,
) -> EdgeApiMtlsIdentity:
    """Verify a proxy-authenticated certificate against active inventory.

    In optional mode absence is allowed for migration, but a certificate that
    nginx reports as present-and-invalid is never downgraded to bearer-only.
    Required mode rejects absence except on the explicitly controlled
    enrollment/recovery path.
    """
    resolved_mode = enforcement_mode(mode)
    if resolved_mode == "off":
        return EdgeApiMtlsIdentity(
            mode=resolved_mode,
            presented=False,
            verified=False,
            device_id=device_id,
        )

    verify_status = str(headers.get(VERIFY_HEADER, "") or "").strip()
    serial_raw = str(headers.get(SERIAL_HEADER, "") or "").strip()
    presented = bool(verify_status or serial_raw)

    if not presented:
        if resolved_mode == "required" and not allow_legacy_enrollment:
            raise EdgeApiMtlsIdentityError("mTLS client certificate is required")
        return EdgeApiMtlsIdentity(
            mode=resolved_mode,
            presented=False,
            verified=False,
            device_id=device_id,
        )

    if verify_status != "SUCCESS":
        raise EdgeApiMtlsIdentityError(
            "mTLS client certificate was not verified by the TLS terminator"
        )

    serial = canonical_certificate_serial(serial_raw)
    credential_id = f"headend-api-mtls:{serial}"
    credential = (
        db.query(EdgeCredentialInventory)
        .filter_by(
            device_id=device_id,
            trust_path="headend_api_mtls",
            key_type="mtls_device_cert",
            credential_id=credential_id,
            status="active",
        )
        .first()
    )
    if credential is None:
        raise EdgeApiMtlsIdentityError(
            "mTLS client certificate is not active for this device"
        )

    return EdgeApiMtlsIdentity(
        mode=resolved_mode,
        presented=True,
        verified=True,
        device_id=device_id,
        credential_id=credential_id,
    )
