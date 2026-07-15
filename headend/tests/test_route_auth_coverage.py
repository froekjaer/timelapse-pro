"""Fail closed when a new API route is added without an authentication contract."""

import main


AUTH_DEPENDENCIES = {
    "_check",  # require_role(...)
    "get_current_user",
    "get_required_user",
    "_verify_device_token",
    "_verify_payload_device_token",
    "_require_device_auth",
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


def test_high_risk_admin_surfaces_use_role_authentication():
    paths = {
        "/api/settings",
        "/api/settings/config",
        "/api/import/start",
        "/api/import/jobs",
        "/api/timelapse/create",
        "/api/timelapse/jobs",
        "/api/review/escalation/approve",
        "/api/ai/vocabulary/merge",
    }
    route_by_path = {route.path: route for route in main.app.routes if hasattr(route, "path")}
    for path in paths:
        assert "_check" in _dependency_names(route_by_path[path].dependant), path
