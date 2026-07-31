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


# The specific high-risk admin paths below MUST carry reviewed role auth. This
# is a targeted canary on top of the dynamic all-routes sweep above.
#
# TPA-01 fix: the previous form indexed route_by_path[path] directly, which threw
# a KeyError (not a clear failure) if a listed route was ever absent — e.g. when
# a router fails to mount because a dependency is missing. We now assert the path
# is present with an explicit, actionable message BEFORE checking auth, so a
# genuinely missing high-risk router fails loudly instead of with a KeyError, and
# a correctly-provisioned app still exercises the full check.
HIGH_RISK_PATHS = {
    "/api/settings",
    "/api/settings/config",
    "/api/import/start",
    "/api/import/jobs",
    "/api/timelapse/create",
    "/api/timelapse/jobs",
    "/api/review/escalation/approve",
    "/api/ai/vocabulary/merge",
}


def test_high_risk_admin_surfaces_use_role_authentication():
    route_by_path = {route.path: route for route in main.app.routes if hasattr(route, "path")}

    missing = sorted(p for p in HIGH_RISK_PATHS if p not in route_by_path)
    assert not missing, (
        "High-risk admin route(s) not registered — a router failed to mount or a "
        "path was renamed. Ensure all dependencies are installed (this is the CI "
        "environment contract) and update HIGH_RISK_PATHS if a surface was "
        "intentionally removed:\n" + "\n".join(missing))

    unauthed = sorted(
        path for path in HIGH_RISK_PATHS
        if "_check" not in _dependency_names(route_by_path[path].dependant))
    assert not unauthed, (
        "High-risk admin routes without role authentication (_check):\n"
        + "\n".join(unauthed))
