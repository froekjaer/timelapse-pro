"""Central Policy Decision Point for Trust Service."""

from __future__ import annotations

import uuid

from .models import PolicyDecision, PolicyRequest, Principal


ROLE_CAPABILITIES: dict[str, set[str]] = {
    "super_admin": {
        "edge.service.grant.issue",
        "edge.service.grant.revoke",
        "edge.service.diagnostics",
        "edge.service.local_view",
        "edge.service.break_glass",
    },
    "admin": {
        "edge.service.grant.issue",
        "edge.service.grant.revoke",
        "edge.service.diagnostics",
        "edge.service.local_view",
    },
    "operator": {
        "edge.service.diagnostics",
        "edge.service.local_view",
    },
    "viewer": set(),
}

KNOWN_ACTIONS = {"grant.issue", "grant.validate", "grant.revoke", "dmz.forward"}
KNOWN_RESOURCE_PREFIXES = ("edge:", "customer:", "site:", "dmz:", "trust:")


def capabilities_for_principal(principal: Principal) -> set[str]:
    return set(ROLE_CAPABILITIES.get(principal.role, set())).union(principal.capabilities)


def evaluate_policy(request: PolicyRequest) -> PolicyDecision:
    decision_id = f"TLP-PDP-{uuid.uuid4().hex[:16]}"
    principal = request.principal
    context = request.context or {}

    if request.action not in KNOWN_ACTIONS:
        return PolicyDecision(False, f"unknown action denied: {request.action}", decision_id)
    if not request.resource.startswith(KNOWN_RESOURCE_PREFIXES):
        return PolicyDecision(False, f"unknown resource denied: {request.resource}", decision_id)
    if request.tenant_id and principal.tenant_id and request.tenant_id != principal.tenant_id:
        return PolicyDecision(False, "tenant boundary denied", decision_id)
    if request.mfa_required and not principal.mfa_verified:
        return PolicyDecision(False, "required MFA not verified", decision_id)
    if context.get("headend_session_token") is True and request.action == "grant.validate":
        return PolicyDecision(False, "normal Headend session token is not an EdgeServiceGrant", decision_id)
    if request.capability:
        capabilities = capabilities_for_principal(principal)
        if request.capability not in capabilities:
            return PolicyDecision(False, f"missing capability: {request.capability}", decision_id)
    return PolicyDecision(True, "allowed by Trust Service PDP", decision_id)
