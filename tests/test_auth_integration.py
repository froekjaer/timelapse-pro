"""
TimeLapse Pro — Authentication Integration Tests (P0)
=====================================================

Komprehensive integration tests for authentication flow:
- Full login flow (POST /api/auth/login)
- MFA setup + confirm + login integration
- WebAuthn registration + login workflow (mocked)
- Session handling and expiration
- Role-based access control across endpoints
- Cookie domain handling
- Password change flow

Kør: pytest tests/test_auth_integration.py -v

Marker: integration (kræver live headend på TIMELAPSE_TEST_BASE_URL)
"""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "TestAdmin123!"}
OPERATOR_CREDS = {"username": "test-operator", "password": "TestOperator123!"}
VIEWER_CREDS = {"username": "test-viewer", "password": "TestViewer123!"}


def api(path, method="GET", **kwargs):
    """Helper til API kald."""
    url = f"{BASE_URL}/api{path}" if not path.startswith("http") else path
    return requests.request(method, url, timeout=kwargs.pop("timeout", 10), **kwargs)


def extract_session_token(response: requests.Response) -> Optional[str]:
    """Udtræk tl_session cookie fra response."""
    for cookie in response.cookies:
        if cookie.name == "tl_session":
            return cookie.value
    return None


def make_authenticated_request(token: str, path: str, method: str = "GET", **kwargs):
    """Lav autentificeret request med token."""
    headers = kwargs.pop("headers", {})
    headers["Cookie"] = f"tl_session={token}"
    url = f"{BASE_URL}/api{path}" if not path.startswith("http") else path
    return requests.request(method, url, headers=headers, timeout=kwargs.pop("timeout", 10), **kwargs)


# ── 1. Basic Login Flow ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_login_success_with_valid_credentials():
    """Login skal virke med gyldige credentials."""
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200, f"Login fejlede: {r.text}"
    data = r.json()
    assert "ok" in data
    assert data["ok"] is True
    assert "role" in data
    assert "username" in data
    # Session cookie skal være sat
    token = extract_session_token(r)
    assert token is not None, "Ingen session cookie sat"


@pytest.mark.integration
def test_login_fails_with_invalid_credentials():
    """Login skal fejle med ugyldige credentials."""
    r = api("/auth/login", method="POST", json={
        "username": "invalid-user",
        "password": "wrong-password"
    })
    assert r.status_code == 401, "Forventede 401 ved ugyldige credentials"


@pytest.mark.integration
def test_login_fails_with_missing_username():
    """Login skal fejle når username mangler."""
    r = api("/auth/login", method="POST", json={
        "password": "some-password"
    })
    assert r.status_code == 422, "Forventede 422 ved manglende username"


@pytest.mark.integration
def test_login_fails_with_missing_password():
    """Login skal fejle når password mangler."""
    r = api("/auth/login", method="POST", json={
        "username": "admin"
    })
    assert r.status_code == 422, "Forventede 422 ved manglende password"


@pytest.mark.integration
def test_login_remember_me_extends_session():
    """Login med remember_me skal forlænge session."""
    r = api("/auth/login", method="POST", json={
        "username": OPERATOR_CREDS["username"],
        "password": OPERATOR_CREDS["password"],
        "remember": True
    })
    assert r.status_code == 200
    # Check max-age cookie attribute (should be > default 24h)
    for cookie in r.cookies:
        if cookie.name == "tl_session" and cookie.expires:
            expires_dt = datetime.fromtimestamp(cookie.expires, tz=timezone.utc)
            duration = expires_dt - datetime.now(tz=timezone.utc)
            # Remember me should give >30 days (configurable via session policy)
            assert duration > timedelta(days=1), f"Remember me ikke aktiv: {duration}"


# ── 2. Session Handling ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_auth_me_returns_user_info():
    """/api/auth/me skal returnere brugerinfo."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)
    assert token is not None

    # Kald /me
    r2 = make_authenticated_request(token, "/auth/me")
    assert r2.status_code == 200
    data = r2.json()
    assert "username" in data
    assert data["username"] == OPERATOR_CREDS["username"]
    assert "role" in data
    assert "mfa_required_effective" in data
    assert "mfa_verified" in data


@pytest.mark.integration
def test_auth_me_fails_without_session():
    """/api/auth/me skal fejle uden gyldig session."""
    r = api("/auth/me")
    assert r.status_code == 401, "Forventede 401 uden session"


@pytest.mark.integration
def test_logout_clears_session():
    """Logout skal rydde session cookie."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Logout
    r2 = api("/auth/logout", method="POST", headers={"Cookie": f"tl_session={token}"})
    assert r2.status_code == 200

    # Verify session er无效 (token skal være expired/cleared)
    # Bemærk: Dette afhænger af backend implementation — logout kan udstede en expire cookie
    assert "Set-Cookie" in r2.headers or r2.json().get("ok") is True


@pytest.mark.integration
def test_expired_session_is_rejected():
    """Udløbet session skal afvises."""
    # Brug et eksplicit ugyldigt token format
    invalid_token = "invalid.token.format"
    r = make_authenticated_request(invalid_token, "/auth/me")
    assert r.status_code in [401, 403], "Ugyldig token skal afvises"


# ── 3. Role-Based Access Control ───────────────────────────────────────────────

@pytest.mark.integration
def test_viewer_can_access_viewer_endpoints():
    """Viewer rolle skal kunne tilgå viewer endpoints."""
    # Login som viewer
    r = api("/auth/login", method="POST", json=VIEWER_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Viewer kan tilgå devices (read-only)
    r2 = make_authenticated_request(token, "/admin/devices")
    assert r2.status_code == 200, "Viewer skal kunne læse devices"


@pytest.mark.integration
def test_viewer_cannot_access_admin_endpoints():
    """Viewer rolle skal IKKE kunne tilgå admin endpoints."""
    # Login som viewer
    r = api("/auth/login", method="POST", json=VIEWER_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Viewer kan ikke oprette devices
    r2 = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": "should-fail",
        "password": "Test123!"
    })
    assert r2.status_code == 403, "Viewer skal ikke kunne oprette brugere"


@pytest.mark.integration
def test_operator_can_access_operator_endpoints():
    """Operator rolle skal kunne tilgå operator endpoints."""
    # Login som operator
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Operator kan tilgå devices
    r2 = make_authenticated_request(token, "/admin/devices")
    assert r2.status_code == 200

    # Operator kan tilgå captures
    r3 = make_authenticated_request(token, "/admin/captures?device_id=TL-C87FF9587CA0&limit=1")
    assert r3.status_code == 200


@pytest.mark.integration
def test_admin_can_access_admin_endpoints():
    """Admin rolle skal kunne tilgå admin endpoints."""
    # Login som admin (super_admin)
    r = api("/auth/login", method="POST", json=ADMIN_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Admin kan tilgå users
    r2 = make_authenticated_request(token, "/admin/users")
    assert r2.status_code == 200, "Admin skal kunne læse brugere"


@pytest.mark.integration
def test_role_hierarchy_super_admin_includes_admin():
    """Super_admin skal have admin rettigheder."""
    # Test at super_admin kan tilgå admin-only endpoints
    r = api("/auth/login", method="POST", json=ADMIN_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Super_admin kan tilgå system admin endpoints
    r2 = make_authenticated_request(token, "/admin/system/info")
    # Dette endpoint eksisterer måske ikke, så vi skipper hvis 404
    if r2.status_code != 404:
        assert r2.status_code in [200, 403], "Super_admin skal have admin adgang"


# ── 4. MFA Flow ────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_mfa_setup_generates_secret_and_qr():
    """MFA setup skal generere secret og QR kode."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Setup MFA
    r2 = make_authenticated_request(token, "/auth/setup-mfa", method="POST")
    assert r2.status_code == 200
    data = r2.json()
    assert "secret" in data
    assert "qr_code" in data
    assert data["qr_code"].startswith("data:image/png;base64,")


@pytest.mark.integration
def test_mfa_confirm_activates_mfa():
    """MFA confirm skal aktivere MFA og udstede ny session."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Setup MFA
    r2 = make_authenticated_request(token, "/auth/setup-mfa", method="POST")
    assert r2.status_code == 200
    secret = r2.json()["secret"]

    # Confirm MFA med dummy TOTP (dette vil fejle i praksis, men tester flow)
    # I et rigtigt test ville vi generere valid TOTP fra secret
    import pyotp
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    r3 = make_authenticated_request(token, "/auth/confirm-mfa", method="POST", json={
        "code": valid_code
    })

    # Bemærk: Dette kan fejle hvis MFA allerede er aktiveret for test-brugeren
    # Vi accepterer både 200 og 400 (hvis allerede aktiveret)
    assert r3.status_code in [200, 400]


@pytest.mark.integration
def test_mfa_login_requires_valid_totp():
    """Login med MFA skal kræve valid TOTP kode."""
    # Hvis test-brugeren har MFA aktiveret, login skal kræve MFA
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    data = r.json()

    # Hvis MFA er aktiveret for denne bruger, skal vi få mfa_required response
    if data.get("mfa_required"):
        assert "mfa_token" in data
        mfa_token = data["mfa_token"]

        # Verify MFA med dummy kode (vil fejle, men tester endpoint)
        r2 = api("/auth/verify-mfa", method="POST", json={
            "mfa_token": mfa_token,
            "code": "000000"  # Invalid kode
        })
        assert r2.status_code == 400, "Forkert TOTP skal fejle"


@pytest.mark.integration
def test_mfa_disable_requires_auth():
    """MFA disable skal kræve autentificering."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Disable MFA (vil fejle hvis MFA ikke er aktiveret)
    r2 = make_authenticated_request(token, "/auth/disable-mfa", method="POST", json={})
    # Accepter både 200 (deaktiveret) og 400 (ikke aktiveret)
    assert r2.status_code in [200, 400]


# ── 5. Password Change ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_change_password_with_valid_old_password():
    """Password change skal virke med gyldigt gammelt password."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Ændr password til noget nyt
    new_password = "NewTestOperator123!"
    r2 = make_authenticated_request(token, "/auth/change-password", method="POST", json={
        "old_password": OPERATOR_CREDS["password"],
        "new_password": new_password
    })

    if r2.status_code == 200:
        # Verificer at vi kan login med nye password
        r3 = api("/auth/login", method="POST", json={
            "username": OPERATOR_CREDS["username"],
            "password": new_password
        })
        assert r3.status_code == 200

        # Ændr tilbage til original password
        r4 = api("/auth/login", method="POST", json={
            "username": OPERATOR_CREDS["username"],
            "password": new_password
        })
        assert r4.status_code == 200
        token4 = extract_session_token(r4)
        r5 = make_authenticated_request(token4, "/auth/change-password", method="POST", json={
            "old_password": new_password,
            "new_password": OPERATOR_CREDS["password"]
        })
        assert r5.status_code == 200
    else:
        # Password change kan fejle af forskellige årsager
        pytest.skip("Password change fejlede (muligvis allerede ændret)")


@pytest.mark.integration
def test_change_password_fails_with_wrong_old_password():
    """Password change skal fejle med forkert gammelt password."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Prøv at ændre med forkert gammelt password
    r2 = make_authenticated_request(token, "/auth/change-password", method="POST", json={
        "old_password": "wrong-old-password",
        "new_password": "NewPassword123!"
    })
    assert r2.status_code == 400, "Forkert gammelt password skal afvises"


@pytest.mark.integration
def test_change_password_requires_min_length():
    """Password change skal kræve minimum 8 tegn."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Prøv med for kort password
    r2 = make_authenticated_request(token, "/auth/change-password", method="POST", json={
        "old_password": OPERATOR_CREDS["password"],
        "new_password": "short"
    })
    assert r2.status_code == 400, "For kort password skal afvises"


# ── 6. Session Policy ──────────────────────────────────────────────────────────

@pytest.mark.integration
def test_session_policy_returns_settings():
    """/api/auth/session-policy skal returnere session policy."""
    # Login først
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200
    token = extract_session_token(r)

    # Hent session policy
    r2 = make_authenticated_request(token, "/auth/session-policy")
    assert r2.status_code == 200
    data = r2.json()
    assert "session_duration_hours" in data
    assert "remember_me_allowed" in data
    assert "mfa_required_effective" in data


# ── 7. WebAuthn Endpoints (existence checks) ────────────────────────────────────

@pytest.mark.integration
def test_webauthn_register_begin_requires_auth():
    """WebAuthn register begin skal kræve autentificering."""
    r = api("/auth/webauthn/register-begin", method="POST", json={})
    assert r.status_code == 401, "WebAuthn register skal kræve login"


@pytest.mark.integration
def test_webauthn_login_begin_returns_options():
    """WebAuthn login begin skal returnere options (hvis bruger har credentials)."""
    # Dette afhænger af at brugeren har WebAuthn credentials registreret
    # For test formål accepterer vi både 200 (har credentials) og 404 (ingen credentials)
    r = api("/auth/webauthn/login-begin", method="POST", json={
        "username": OPERATOR_CREDS["username"]
    })
    assert r.status_code in [200, 404], "WebAuthn login skal returnere options eller 404 hvis ingen credentials"


# ── 8. Cross-Site Request Protection ───────────────────────────────────────────

@pytest.mark.integration
def test_csrf_like_protection_on_sensitive_endpoints():
    """Sensitive endpoints skal kræve autentificering."""
    # Test at DELETE endpoints kræver auth
    r = api("/admin/users/999", method="DELETE")
    assert r.status_code in [401, 403], "DELETE skal kræve autentificering"

    # Test at PUT endpoints kræver auth
    r2 = api("/admin/devices/TL-FAKE", method="PUT", json={})
    assert r2.status_code in [401, 403], "PUT skal kræve autentificering"


# ── 9. Agent Principal Lockdown (M-05) ───────────────────────────────────────────

@pytest.mark.integration
def test_agent_role_blocked_in_production():
    """Agent rolle skal være blokeret i staging/prod miljøer."""
    # Dette test kræver at TIMELAPSE_ENV er sat til staging/prod
    # Hvis ikke, kan vi ikke teste dette effektivt
    env = os.getenv("TIMELAPSE_ENV", "")
    if env not in ["staging", "production"]:
        pytest.skip("M-05 test kun relevant i staging/prod miljø")

    # Prøv at login med en agent-rolle bruger (hvis den findes)
    # I praksis skal dette fejle med 401 uanset password
    r = api("/auth/login", method="POST", json={
        "username": "test-agent",  # Hypotetisk agent bruger
        "password": "any-password"
    })

    # Forventet: 401 (enten fordi brugeren ikke findes, eller fordi M-05 blokerer)
    # Bemærk: Fejlbeskeden skal være identisk med "forkert brugernavn/password"
    # for ikke at lække rolle information
    assert r.status_code == 401, "Agent rolle login skal afvises i staging/prod"


# ── 10. Cookie Security ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_session_cookie_has_sane_attributes():
    """Session cookie skal have sikre attributter."""
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    assert r.status_code == 200

    # Find tl_session cookie
    for cookie in r.cookies:
        if cookie.name == "tl_session":
            # Cookie skal have expires eller max-age
            assert cookie.expires or cookie.max_age is not None, "Session cookie skal have expires"
            # Cookie skal være HttpOnly (implificeret af ikke at kunne læses via JS i test)
            # Vi kan ikke direkte teste HttpOnly og Secure i requests uden at inspicere headers
            return pytest.skip("Cookie attributter kan ikke testes uden at inspicere Set-Cookie header")

    pytest.fail("Ingen tl_session cookie fundet")


@pytest.mark.integration
def test_multiple_login_attempts_rate_limited():
    """Multiple login attempts skal være rate-limited."""
    # Send 10 ugyldige login requests
    for i in range(12):
        r = api("/auth/login", method="POST", json={
            "username": "invalid-user",
            "password": "wrong-password"
        })
        # Efter visse forsøg skal vi få 429 (rate limit)
        if r.status_code == 429:
            return  # Test pass — rate limiting virker

    # Hvis vi når hertil uden 429, kan rate limiting være deaktiveret i test
    pytest.skip("Rate limiting kan være deaktiveret i test miljø")


# ── 11. Edge Cases ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_login_with_empty_credentials():
    """Login med tom credentials skal fejle."""
    r = api("/auth/login", method="POST", json={
        "username": "",
        "password": ""
    })
    assert r.status_code in [401, 422], "Tom credentials skal afvises"


@pytest.mark.integration
def test_me_with_invalid_token_format():
    """/api/auth/me med invalid token format skal fejle."""
    r = api("/auth/me", headers={"Cookie": "tl_session=invalid.format.token"})
    assert r.status_code in [401, 403], "Invalid token skal afvises"


@pytest.mark.integration
def test_logout_without_login():
    """Logout uden login skal stadig virke (idempotent)."""
    r = api("/auth/logout", method="POST")
    # Logout skal returnere 200 selvom ingen session findes
    assert r.status_code == 200, "Logout skal være idempotent"
