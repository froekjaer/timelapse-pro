"""Dataclasses for Trust Service policy and grant contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    user_id: int | None = None
    tenant_id: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    mfa_verified: bool = False


@dataclass(frozen=True)
class PolicyRequest:
    principal: Principal
    action: str
    resource: str
    tenant_id: str | None = None
    capability: str | None = None
    mfa_required: bool = False
    context: dict | None = None


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    decision_id: str


@dataclass(frozen=True)
class GrantRequest:
    principal: Principal
    edge_id: str
    tenant_id: str | None
    resource: str
    purpose: str
    capabilities: frozenset[str]
    ttl_seconds: int
    mfa_required: bool = True
    context: dict | None = None


@dataclass(frozen=True)
class GrantValidation:
    allowed: bool
    reason: str
    grant_id: str | None = None
    username: str | None = None
    expires_at: datetime | None = None
