"""Fail closed when a new API route is added without an authentication contract."""

import main


AUTH_DEPENDENCIES = {
    "_check",  # require_role(...)
    "get_current_user",
    "get_required_user",
    "_verify_device_token",
    "_verify_payload_device_token",
    "_require_device_auth",
    # Reviewed wrappers that call get_current_user(), enforce role/tenant scope,
    # and require MFA when the effective user policy demands it.
    "_current_viewer",
    "_require_platform_admin",
    "_require_risk_admin",
}

# Routes here are intentionally pre-auth or use an explicit in-body token/loopback
# validator. Every entry needs a security rationale in this test before CI accepts it.
EXPLICIT_EXCEPTIONS = {
    ("GET", "/api/health"),
    ("GET", "/api/time"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/verify-mfa"),
    ("POST", "/api/auth/webauthn/login-begin"),
    ("POST", "/api/auth/webauthn/login-complete"),
    ("POST", "/api/bootstrap"),  # one-time bootstrap token is validated in body
    ("POST", "/api/api/devices/enroll"),  # one-time enrollment token in body
    ("POST", "/api/devices/enroll"),
    ("POST", "/api/technician/auth/start"),  # challenge/headend token protocol
    ("POST", "/api/technician/auth/callback"),
    ("GET", "/api/openwebui/access/check"),  # signed Open WebUI cookie in body helper
    ("GET", "/api/openwebui/tools/openapi.json"),  # loopback enforced in endpoint
    ("GET", "/api/openwebui/tools/system-context"),
    ("POST", "/api/openwebui/tools/ask"),
    ("GET", "/api/openwebui/tools/latest-captures"),
    ("POST", "/api/openwebui/tools/select-captures"),
    ("GET", "/api/openwebui/tools/help-topics"),
}


def _dependency_names(dependant) -> set[str]:
    names: set[str] = set()
    for dependency in getattr(dependant, "dependencies", []):
        names.add(getattr(dependency.call, "__name__", str(dependency.call)))
        names.update(_dependency_names(dependency))
    return names


def test_every_api_route_has_authentication_or_reviewed_exception():
    missing = []
    for route in main.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/"):
            continue
        dependency_names = _dependency_names(getattr(route, "dependant", None))
        for method in getattr(route, "methods", set()):
            key = (method, path)
            if not AUTH_DEPENDENCIES.intersection(dependency_names) and key not in EXPLICIT_EXCEPTIONS:
                missing.append(f"{method} {path} ({sorted(dependency_names)})")
    assert not missing, "API routes without reviewed authentication:\n" + "\n".join(sorted(missing))


# High-risk admin surfaces are declared by PREFIX so the check cannot rot when a
# concrete path is renamed (TPA-00/TPA-01 assessment: the old hardcoded-path form
# failed with KeyError when /api/settings/config was removed, silently disabling
# the gate). For each prefix we assert (a) at least one concrete route exists
# (catches drift), and (b) EVERY concrete route under it carries a reviewed auth
# dependency.
HIGH_RISK_PREFIXES = (
    "/api/settings",
    "/api/import",
    "/api/timelapse",
    "/api/review",
    "/api/ai/vocabulary",
    "/api/admin",
    "/api/commissioner",
)


def _concrete_api_routes():
    for route in main.app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/") and getattr(route, "methods", None):
            yield route


# Sentinel prefix: this MUST always be present. If it ever has zero routes the
# app failed to mount and the gate would silently pass — so we assert on it.
SENTINEL_PREFIX = "/api/admin"


def test_high_risk_admin_surfaces_use_role_authentication():
    routes = list(_concrete_api_routes())
    assert routes, "no /api routes registered — app did not mount (gate would no-op)"

    sentinel = [r for r in routes if r.path == SENTINEL_PREFIX or r.path.startswith(SENTINEL_PREFIX + "/")]
    assert sentinel, f"sentinel prefix {SENTINEL_PREFIX} has no routes — refuse to pass a no-op gate"

    unauthed = []
    checked = 0
    for prefix in HIGH_RISK_PREFIXES:
        for r in routes:
            if not (r.path == prefix or r.path.startswith(prefix + "/")):
                continue
            dep = _dependency_names(getattr(r, "dependant", None))
            for method in getattr(r, "methods", set()):
                if (method, r.path) in EXPLICIT_EXCEPTIONS:
                    continue
                checked += 1
                if not AUTH_DEPENDENCIES.intersection(dep):
                    unauthed.append(f"{method} {r.path} ({sorted(dep)})")

    assert checked, "no high-risk routes were checked — HIGH_RISK_PREFIXES is stale"
    assert not unauthed, (
        "High-risk admin routes without reviewed authentication:\n" + "\n".join(sorted(unauthed)))
