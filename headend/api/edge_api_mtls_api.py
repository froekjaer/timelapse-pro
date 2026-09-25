"""Enrollment and administration routes for Edge -> Headend API mTLS.

Existing deployed Edges authenticate the migration request with their current
bearer credential *and* request signature through ``_verify_device_token``.
That credential is only a migration authenticator here: it never authorizes
creation/export of a private key.  Fresh Edge enrollment remains governed by
WP-4 provisioning; both paths converge on an Edge-owned private key + CSR.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Device, EdgeCredentialInventory, EdgeLifecycleRecord, get_db, now_utc
from services.edge_api_mtls_identity import (
    EdgeApiMtlsIdentityError,
    verify_edge_api_mtls_identity,
)
from services.headend_api_mtls import (
    HeadendApiMtlsError,
    HeadendApiMtlsUnavailableError,
    ca_status,
    initialize_ca,
    issue_client_certificate,
)


class ApiMtlsEnrollPayload(BaseModel):
    csr_pem: str


def _metadata(row: EdgeCredentialInventory) -> dict:
    try:
        data = json.loads(row.metadata_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _record_inventory(db: Session, *, device_id: str, issued: dict[str, object]) -> EdgeCredentialInventory:
    now = now_utc()
    for old in db.query(EdgeCredentialInventory).filter_by(
        device_id=device_id,
        trust_path="headend_api_mtls",
        key_type="mtls_device_cert",
        status="active",
    ).all():
        old.status = "rotated"
        old.rotated_at = now
        meta = _metadata(old)
        meta["rotated_by"] = "headend-api-mtls-enrollment"
        old.metadata_json = json.dumps(meta, sort_keys=True)

    serial = str(issued["serial_number"])
    row = EdgeCredentialInventory(
        device_id=device_id,
        trust_path="headend_api_mtls",
        credential_id=f"headend-api-mtls:{serial}",
    )
    row.key_type = "mtls_device_cert"
    row.subject = str(issued["subject"])
    row.issuer = str(issued["issuer"])
    row.owner = "physical edge"
    row.private_key_location = "edge:/etc/timelapse/device_keys/headend-api.key"
    row.public_key_location = "edge:/etc/timelapse/certs/headend-api.crt"
    row.storage = "Edge-owned private key; Headend stores certificate metadata only"
    row.fingerprint = str(issued["fingerprint_sha256"])
    row.scope = '["headend-api:device"]'
    row.audience = "backend.timelapse-pro.dk:8443"
    row.rotation = "renew with a new CSR before expiry; private key rotation may be requested independently"
    row.revocation = "Trust Service inventory revocation + nginx CA/CRL policy"
    row.status = "active"
    row.legacy_path = False
    row.compromise_procedure = "revoke certificate, quarantine device when provenance is uncertain, generate new Edge key and re-enroll"
    row.lifecycle_state_created = "credentialed"
    row.issued_at = now
    row.activated_at = now
    try:
        row.expires_at = datetime.fromisoformat(str(issued["not_after"]))
    except ValueError:
        row.expires_at = None
    row.metadata_json = json.dumps({
        "device_uri": issued["device_uri"],
        "private_key_exported": False,
        "enrollment_auth": "existing signed device API credential",
        "transport_profile": "headend-api-mtls",
    }, sort_keys=True)
    db.add(row)
    return row


def enforce_edge_api_mtls_identity(db: Session, *, device_id: str, request) -> None:
    """Map the Edge mTLS identity verifier into the HTTP auth boundary."""
    enrollment_path = f"/api/trust/headend-api-mtls/{device_id}/enroll"
    try:
        verify_edge_api_mtls_identity(
            db,
            device_id=device_id,
            headers=request.headers,
            allow_legacy_enrollment=(request.url.path == enrollment_path),
        )
    except EdgeApiMtlsIdentityError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def create_headend_api_mtls_admin_router(require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/admin/trust/headend-api-mtls", tags=["headend-api-mtls"])

    @router.get("/status")
    def status(_user=require_role("admin")):
        return ca_status()

    @router.post("/initialize")
    def initialize(_user=require_role("super_admin")):
        try:
            initialize_ca()
        except HeadendApiMtlsUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HeadendApiMtlsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ca_status()

    return router


def create_headend_api_mtls_edge_router(verify_device_token: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/trust/headend-api-mtls", tags=["headend-api-mtls"])

    @router.post("/{device_id}/enroll")
    async def enroll(
        device_id: str,
        payload: ApiMtlsEnrollPayload,
        _verified=Depends(verify_device_token),
        db: Session = Depends(get_db),
    ):
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        lifecycle = db.query(EdgeLifecycleRecord).filter_by(device_id=device_id).first()
        if lifecycle and lifecycle.state in {"revoked", "retired", "quarantined"}:
            raise HTTPException(status_code=403, detail="Device lifecycle does not permit API certificate enrollment")
        if len(payload.csr_pem.encode("utf-8")) > 16384:
            raise HTTPException(status_code=413, detail="CSR too large")
        try:
            issued = issue_client_certificate(device_id, payload.csr_pem)
        except HeadendApiMtlsUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HeadendApiMtlsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        row = _record_inventory(db, device_id=device_id, issued=issued)
        db.commit()
        return {
            "device_id": device_id,
            "certificate_pem": issued["certificate_pem"],
            "ca_certificate_pem": issued["ca_certificate_pem"],
            "serial_number": issued["serial_number"],
            "fingerprint_sha256": issued["fingerprint_sha256"],
            "not_after": issued["not_after"],
            "trust_path": row.trust_path,
            "scope": ["headend-api:device"],
            "audience": "backend.timelapse-pro.dk:8443",
            "private_key_exported": False,
        }

    return router
