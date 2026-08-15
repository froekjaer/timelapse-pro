"""EdgeServiceGrant issuance and validation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import uuid
from datetime import timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from database import EdgeServiceGrant, now_utc
from .models import GrantRequest, GrantValidation, PolicyRequest
from .policy import evaluate_policy


class GrantDenied(ValueError):
    pass


class TrustServiceConfigurationError(RuntimeError):
    """Raised when a Trust Service authority is missing in a fail-closed environment."""


def _is_explicit_test_or_lab_environment() -> bool:
    env = (os.getenv("TIMELAPSE_ENV") or "").strip().lower()
    if env in {"prod", "production", "staging"}:
        return False
    return env in {"test", "testing", "lab", "development", "dev", "rd"} or "pytest" in sys.modules


def _secret() -> bytes:
    """Return a Trust-Service-specific signing secret.

    Grant signing is a separate trust purpose from Headend browser sessions. It
    must therefore not silently reuse JWT_SECRET. Production/staging fail
    closed when no dedicated signer secret exists. A deterministic development
    secret is available only when the process is explicitly running as test/LAB.
    """
    configured = os.getenv("TIMELAPSE_TRUST_SERVICE_SIGNING_SECRET")
    if configured:
        if len(configured.encode()) < 32:
            raise TrustServiceConfigurationError(
                "TIMELAPSE_TRUST_SERVICE_SIGNING_SECRET must be at least 32 bytes"
            )
        return configured.encode()

    if _is_explicit_test_or_lab_environment():
        return b"timelapse-test-only-trust-service-secret-v1"

    raise TrustServiceConfigurationError(
        "TIMELAPSE_TRUST_SERVICE_SIGNING_SECRET is required outside explicit test/LAB environments"
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _signature(payload: dict[str, Any]) -> str:
    return _b64(hmac.new(_secret(), _canonical(payload).encode(), hashlib.sha256).digest())


def _token(payload: dict[str, Any]) -> str:
    return f"{_b64(_canonical(payload).encode())}.{_signature(payload)}"


def _decode_token(token: str) -> tuple[dict[str, Any], str]:
    try:
        payload_part, signature = token.split(".", 1)
        padded = payload_part + "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception as exc:
        raise GrantDenied("invalid grant token format") from exc
    if not hmac.compare_digest(_signature(payload), signature):
        raise GrantDenied("invalid grant signature")
    return payload, signature


def issue_edge_service_grant(db: Session, request: GrantRequest) -> tuple[str, EdgeServiceGrant]:
    if request.ttl_seconds <= 0 or request.ttl_seconds > 3600:
        raise GrantDenied("grant ttl must be between 1 and 3600 seconds")
    if not request.capabilities:
        raise GrantDenied("grant requires at least one capability")

    # Every requested capability must independently pass the PDP. Validating
    # only the lexicographically first capability would let additional scopes be
    # smuggled into the signed grant without policy evidence.
    decisions = []
    for capability in sorted(request.capabilities):
        decision = evaluate_policy(
            PolicyRequest(
                principal=request.principal,
                action="grant.issue",
                resource=request.resource,
                tenant_id=request.tenant_id,
                capability=capability,
                mfa_required=request.mfa_required,
                context=request.context,
            )
        )
        decisions.append(decision)
        if not decision.allowed:
            raise GrantDenied(decision.reason)

    issued_at = now_utc()
    expires_at = issued_at + timedelta(seconds=request.ttl_seconds)
    grant_id = f"TLP-GRANT-{uuid.uuid4().hex[:16]}"
    jti = uuid.uuid4().hex
    payload = {
        "typ": "EdgeServiceGrant",
        "grant_id": grant_id,
        "jti": jti,
        "edge_id": request.edge_id,
        "sub": request.principal.username,
        "uid": request.principal.user_id,
        "role": request.principal.role,
        "tenant_id": request.tenant_id,
        "resource": request.resource,
        "purpose": request.purpose,
        "capabilities": sorted(request.capabilities),
        "mfa_verified": bool(request.principal.mfa_verified),
        "iat": issued_at.replace(tzinfo=timezone.utc).timestamp(),
        "exp": expires_at.replace(tzinfo=timezone.utc).timestamp(),
    }
    token = _token(payload)
    row = EdgeServiceGrant(
        grant_id=grant_id,
        jti=jti,
        edge_id=request.edge_id,
        user_id=request.principal.user_id,
        username=request.principal.username,
        role=request.principal.role,
        tenant_id=request.tenant_id,
        resource=request.resource,
        purpose=request.purpose,
        capabilities_json=_canonical(sorted(request.capabilities)),
        context_json=_canonical(request.context or {}),
        mfa_required=bool(request.mfa_required),
        mfa_verified=bool(request.principal.mfa_verified),
        status="active",
        issued_at=issued_at,
        expires_at=expires_at,
        signature=token,
        metadata_json=_canonical({"decision_ids": [decision.decision_id for decision in decisions]}),
    )
    db.add(row)
    return token, row


def revoke_edge_service_grant(db: Session, grant_id: str, *, actor: str, reason: str) -> EdgeServiceGrant:
    row = db.query(EdgeServiceGrant).filter_by(grant_id=grant_id).first()
    if not row:
        raise GrantDenied("grant not found")
    row.status = "revoked"
    row.revoked_at = now_utc()
    row.revoked_by = actor
    row.revoke_reason = reason
    return row


def validate_edge_service_grant(
    db: Session,
    token: str,
    *,
    edge_id: str,
    tenant_id: str | None,
    capability: str,
    resource: str,
    challenge_id: str,
) -> GrantValidation:
    try:
        payload, _sig = _decode_token(token)
    except (GrantDenied, TrustServiceConfigurationError) as exc:
        return GrantValidation(False, str(exc))
    if payload.get("typ") != "EdgeServiceGrant":
        return GrantValidation(False, "normal Headend session token rejected")
    row = db.query(EdgeServiceGrant).filter_by(
        grant_id=payload.get("grant_id"), jti=payload.get("jti")
    ).first()
    if not row:
        return GrantValidation(False, "grant record not found")
    if row.status != "active":
        return GrantValidation(False, f"grant status denied: {row.status}", row.grant_id)
    if row.expires_at and row.expires_at.replace(tzinfo=timezone.utc) < now_utc():
        row.status = "expired"
        return GrantValidation(False, "grant expired", row.grant_id)
    if row.edge_id != edge_id or payload.get("edge_id") != edge_id:
        return GrantValidation(False, "grant edge binding denied", row.grant_id)
    if tenant_id and row.tenant_id and row.tenant_id != tenant_id:
        return GrantValidation(False, "grant tenant boundary denied", row.grant_id)
    capabilities = set(json.loads(row.capabilities_json or "[]"))
    if capability not in capabilities:
        return GrantValidation(False, "grant capability scope denied", row.grant_id)
    if row.resource != resource:
        return GrantValidation(False, "grant resource scope denied", row.grant_id)
    if row.mfa_required and not row.mfa_verified:
        return GrantValidation(False, "grant missing required MFA", row.grant_id)
    if not challenge_id:
        return GrantValidation(False, "challenge required", row.grant_id)
    if row.last_challenge_id == challenge_id:
        return GrantValidation(False, "replayed technician challenge denied", row.grant_id)
    row.last_challenge_id = challenge_id
    row.last_used_at = now_utc()
    row.use_count = (row.use_count or 0) + 1
    return GrantValidation(True, "grant accepted", row.grant_id, row.username, row.expires_at)
