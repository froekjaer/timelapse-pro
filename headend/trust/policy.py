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
        "edge.shell.remote",
    },
    "admin": {
        "edge.service.grant.issue",
        "edge.service.grant.revoke",
        "edge.service.diagnostics",
        "edge.service.local_view",
        "edge.shell.remote",
    },
    "engineer": {
        "edge.service.grant.issue",
        "edge.service.grant.revoke",
        "edge.service.diagnostics",
        "edge.service.local_view",
        "edge.shell.remote",
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


def principal_from_legacy_user(user, *, mfa_verified: bool = False, capabilities: set[str] | None = None) -> Principal:
    """Build a Trust Service principal from the existing Headend user model."""
    derived_capabilities = set(capabilities or set())
    if bool(getattr(user, "on_site_service", False)):
        derived_capabilities.add("edge.service.local_view")
        derived_capabilities.add("edge.service.diagnostics")
    return Principal(
        username=getattr(user, "username", ""),
        role=getattr(user, "role", ""),
        user_id=getattr(user, "id", None),
        tenant_id=getattr(user, "customer_id", None),
        capabilities=frozenset(derived_capabilities),
        mfa_verified=mfa_verified,
    )


def evaluate_legacy_role_capability_check(
    user,
    *,
    action: str,
    resource: str,
    capability: str | None,
    tenant_id: str | None = None,
    mfa_verified: bool = False,
    context: dict | None = None,
) -> PolicyDecision:
    """Compatibility entrypoint for old role/capability checks during WP-2 migration."""
    return evaluate_policy(PolicyRequest(
        principal=principal_from_legacy_user(user, mfa_verified=mfa_verified),
        action=action,
        resource=resource,
        tenant_id=tenant_id,
        capability=capability,
        mfa_required=mfa_verified,
        context={"compatibility_layer": "legacy_role_capability", **(context or {})},
    ))
