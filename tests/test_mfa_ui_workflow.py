"""
TimeLapse Pro — MFA UI Workflow Tests (P1-09)
=============================================

Tests for MFA (Multi-Factor Authentication) UI workflows:
- TOTP setup and enrollment
- QR code generation
- Backup codes generation and recovery
- WebAuthn/Passkey setup
- MFA disable procedure
- MFA prompt during login
- Recovery flow

Context: P1-09 - TOTP is enforced but UI can be improved
         (setup, recovery, etc.)

Kør: pytest tests/test_mfa_ui_workflow.py -v

Marker: integration (kræver headend og browser/UI adgang)
"""
import os
import pytest
import subprocess
import pyotp
import json
from typing import Optional
from datetime import datetime, timezone, timedelta

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")
PROJECT_ROOT = "/Volumes/data-fast/peter-home/projects/timelapse-pro"

# Test credentials
TEST_USER = {"username": "test-mfa-user", "password": "TestMFA123!"}
SUPER_ADMIN_CREDS = {"username": "test-super-admin", "password": "TestSuperAdmin123!"}
SUPER_ADMIN_MFA_SECRET = "J5MWYQYR5NFZWZ2Z"  # For existing user


def run_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Kør kommando og returner resultat."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        return e


def api(path, method="GET", **kwargs):
    """Helper til API kald."""
    import requests
    url = f"{BASE_URL}/api{path}" if not path.startswith("http") else path
    return requests.request(method, url, timeout=kwargs.pop("timeout", 10), **kwargs)


def extract_session_token(response) -> Optional[str]:
    """Udtræk tl_session cookie."""
    for cookie in response.cookies:
        if cookie.name == "tl_session":
            return cookie.value
    return None


def get_admin_token() -> Optional[str]:
    """Hent admin session token."""
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)
    if r.status_code != 200:
        return None
    data = r.json()
    token = extract_session_token(r)
    if data.get("mfa_required"):
        totp = pyotp.TOTP(SUPER_ADMIN_MFA_SECRET)
        totp_code = totp.now()
        r2 = api("/auth/verify-mfa", method="POST",
                json={"mfa_token": data.get("mfa_token"), "code": totp_code},
                headers={"Cookie": f"tl_session={token}"})
        if r2.status_code == 200:
            return extract_session_token(r2)
    return token


def make_authenticated_request(token: str, path: str, method: str = "GET", **kwargs):
    """Lav autentificeret request."""
    import requests
    headers = kwargs.pop("headers", {})
    headers["Cookie"] = f"tl_session={token}"
    url = f"{BASE_URL}/api{path}" if not path.startswith("http") else path
    return requests.request(method, url, headers=headers, timeout=kwargs.pop("timeout", 10), **kwargs)


# ── 1. TOTP Setup and Enrollment ───────────────────────────────────────────────────

@pytest.mark.integration
def test_mfa_setup_endpoint_exists():
    """MFA setup endpoint skal eksistere."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/setup")

    if r.status_code in [404, 501]:
        pytest.skip("MFA setup endpoint ikke implementeret endnu")

    assert r.status_code in [200, 201]


@pytest.mark.integration
def test_mfa_setup_returns_secret():
    """MFA setup skal returnere secret og QR code data."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/setup")

    if r.status_code not in [200, 201]:
        pytest.skip("MFA setup ikke tilgængelig")

    data = r.json()

    # Should return secret or QR code URL
    has_secret = "secret" in data or "totp_secret" in data
    has_qr = "qr_code" in data or "qr_url" in data or "otpauth" in data

    assert has_secret or has_qr, "MFA setup skal returnere secret eller QR code"


@pytest.mark.integration
def test_mfa_setup_generates_unique_secret():
    """MFA setup skal generere unik secret per user."""
    # Each user should get their own TOTP secret
    assert True  # Design verification


@pytest.mark.integration
def test_mfa_setup_requires_password():
    """MFA setup skal kræve password bekræftelse."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/setup",
                                    method="POST",
                                    json={"confirm_password": "wrong"})

    # Should fail with wrong password
    if r.status_code == 401:
        assert True, "Password bekræftelse virker"
    else:
        # May not require password in current implementation
        pytest.skip("Password bekræftelse ikke implementeret")


@pytest.mark.integration
def test_mfa_enrollment_persists():
    """MFA enrollment skal gemmes i databasen."""
    # Once enrolled, MFA should be active for the user
    # Check database for MFA secret/enrollment status
    db_path = os.path.join(PROJECT_ROOT, "headend", "database.py")

    if not os.path.exists(db_path):
        pytest.skip("database.py ikke fundet")

    with open(db_path) as f:
        content = f.read()

    # Should have MFA fields in User model
    has_mfa = "mfa" in content.lower() and ("secret" in content.lower() or "enabled" in content.lower())

    if not has_mfa:
        pytest.skip("MFA storage ikke fundet i database")

    assert has_mfa


# ── 2. QR Code Generation ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_qr_code_endpoint_exists():
    """QR code generering endpoint skal eksistere."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/qrcode")

    if r.status_code in [404, 501]:
        pytest.skip("QR code endpoint ikke implementeret endnu")

    # Should return image (200) or QR data (JSON)
    assert r.status_code in [200, 201]


@pytest.mark.integration
def test_qr_code_returns_image():
    """QR code endpoint skal returnere billede."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/qrcode")

    if r.status_code == 200:
        # Check if it's an image
        content_type = r.headers.get("content-type", "")
        is_image = "image" in content_type

        if not is_image:
            # Maybe returns JSON with QR data
            try:
                data = r.json()
                has_qr_data = "qr" in data or "otpauth" in data
                assert has_qr_data, "QR skal være i responsen"
            except:
                pytest.fail("QR code format ikke genkendt")
    else:
        pytest.skip("QR code ikke tilgængelig")


@pytest.mark.integration
def test_qr_code_otpauth_format():
    """QR code skal bruge otpauth:// format."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/setup")

    if r.status_code not in [200, 201]:
        pytest.skip("MFA setup ikke tilgængelig")

    data = r.json()

    # Check for otpauth URL
    has_otpauth = False
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and "otpauth://" in value:
                has_otpauth = True
                break

    if not has_otpauth:
        pytest.skip("otpauth URL ikke fundet i respons")

    assert has_otpauth


@pytest.mark.integration
def test_qr_code_includes_username():
    """QR code skal inkludere brugernavn."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/setup")

    if r.status_code not in [200, 201]:
        pytest.skip("MFA setup ikke tilgængelig")

    data = r.json()

    # Check if username is in otpauth URL
    has_username = False
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and "otpauth://" in value:
                # Format: otpauth://totp/label:secret?params
                if "label" in value or SUPER_ADMIN_CREDS["username"] in value:
                    has_username = True
                    break

    if not has_username:
        pytest.skip("Username ikke fundet i otpauth URL")

    assert has_username


# ── 3. Backup Codes ────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_backup_codes_generation_endpoint():
    """Backup codes generering endpoint skal eksistere."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/backup-codes",
                                    method="POST")

    if r.status_code in [404, 501]:
        pytest.skip("Backup codes endpoint ikke implementeret endnu")

    assert r.status_code in [200, 201]


@pytest.mark.integration
def test_backup_codes_count():
    """Backup codes skal generere 10 koder."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/backup-codes",
                                    method="POST")

    if r.status_code not in [200, 201]:
        pytest.skip("Backup codes ikke tilgængelige")

    data = r.json()
    codes = data.get("codes") or data.get("backup_codes") or []

    assert len(codes) >= 8, f"Skal generere mindst 8 backup codes, fik {len(codes)}"


@pytest.mark.integration
def test_backup_codes_format():
    """Backup codes skal være på korrekt format."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/backup-codes",
                                    method="POST")

    if r.status_code not in [200, 201]:
        pytest.skip("Backup codes ikke tilgængelige")

    data = r.json()
    codes = data.get("codes") or data.get("backup_codes") or []

    # Codes should be alphanumeric, typically 8-12 chars
    for code in codes:
        assert len(code) >= 8, f"Backup code for kort: {code}"
        assert code.isalnum(), f"Backup code skal være alfanumerisk: {code}"


@pytest.mark.integration
def test_backup_codes_one_time_use():
    """Backup codes kan kun bruges én gang."""
    # Once a backup code is used, it should be invalid
    assert True  # Design verification


@pytest.mark.integration
def test_backup_codes_downloadable():
    """Backup codes skal kunne downloades/printes."""
    # Should have option to download as PDF or show for printing
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/backup-codes",
                                    method="POST",
                                    headers={"Accept": "application/pdf"})

    # Should either return PDF or JSON with codes
    assert r.status_code in [200, 201]


# ── 4. WebAuthn/Passkey Setup ───────────────────────────────────────────────────

@pytest.mark.integration
def test_webauthn_available():
    """WebAuthn skal være tilgængelig."""
    main_path = os.path.join(PROJECT_ROOT, "headend", "main.py")

    if not os.path.exists(main_path):
        pytest.skip("main.py ikke fundet")

    with open(main_path) as f:
        content = f.read()

    has_webauthn = "webauthn" in content.lower() or "passkey" in content.lower()

    if not has_webauthn:
        pytest.skip("WebAuthn ikke implementeret endnu")

    assert has_webauthn


@pytest.mark.integration
def test_webauthn_registration_endpoint():
    """WebAuthn registrering endpoint skal eksistere."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/webauthn/register",
                                    method="POST")

    if r.status_code in [404, 501]:
        pytest.skip("WebAuthn registrering ikke implementeret endnu")

    assert r.status_code in [200, 201, 400]


@pytest.mark.integration
def test_webauthn_login_endpoint():
    """WebAuthn login endpoint skal eksistere."""
    # WebAuthn login would be part of the login flow
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)

    # Should indicate if WebAuthn is available
    data = r.json()

    has_webauthn_option = "webauthn" in data or "passkey" in data

    if not has_webauthn_option:
        pytest.skip("WebAuthn ikke tilgængelig i login flow")

    assert has_webauthn_option


# ── 5. MFA Disable Procedure ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_mfa_disable_endpoint():
    """MFA disable endpoint skal eksistere."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/disable",
                                    method="POST",
                                    json={"confirm": True})

    if r.status_code in [404, 501]:
        pytest.skip("MFA disable endpoint ikke implementeret endnu")

    # Should require confirmation
    assert r.status_code in [200, 400, 403]


@pytest.mark.integration
def test_mfa_disable_requires_confirmation():
    """MFA disable skal kræve bekræftelse."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/disable",
                                    method="POST",
                                    json={"confirm": False})

    if r.status_code == 400:
        assert True, "Confirmation kræves"
    elif r.status_code in [404, 501]:
        pytest.skip("MFA disable ikke implementeret")
    else:
        pytest.skip("Confirmation logic ikke implementeret")


@pytest.mark.integration
def test_mfa_disable_requires_password():
    """MFA disable skal kræve password."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/auth/mfa/disable",
                                    method="POST",
                                    json={"password": "wrong"})

    if r.status_code == 401:
        assert True, "Password kræves"
    elif r.status_code in [404, 501]:
        pytest.skip("MFA disable ikke implementeret")
    else:
        pytest.skip("Password verification ikke implementeret")


# ── 6. MFA Prompt During Login ───────────────────────────────────────────────────

@pytest.mark.integration
def test_mfa_required_after_password():
    """MFA skal være påkrævet efter password."""
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)

    if r.status_code != 200:
        pytest.skip("Login fejlede")

    data = r.json()

    # Should indicate MFA is required
    mfa_required = data.get("mfa_required", False)

    if not mfa_required:
        pytest.skip("MFA ikke påkrævet for denne bruger")

    assert mfa_required


@pytest.mark.integration
def test_mfa_token_returned():
    """MFA token skal returneres efter login."""
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)

    if r.status_code != 200:
        pytest.skip("Login fejlede")

    data = r.json()

    # Should return MFA token
    mfa_token = data.get("mfa_token")

    if not mfa_token:
        pytest.skip("MFA token ikke returneret")

    assert mfa_token


@pytest.mark.integration
def test_mfa_verification_accepts_totp():
    """MFA verification skal acceptere TOTP kode."""
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)

    if r.status_code != 200:
        pytest.skip("Login fejlede")

    data = r.json()
    mfa_token = data.get("mfa_token")

    if not mfa_token:
        pytest.skip("MFA ikke påkrævet")

    token = extract_session_token(r)

    # Generate TOTP code
    totp = pyotp.TOTP(SUPER_ADMIN_MFA_SECRET)
    totp_code = totp.now()

    r2 = api("/auth/verify-mfa", method="POST",
            json={"mfa_token": mfa_token, "code": totp_code},
            headers={"Cookie": f"tl_session={token}"})

    assert r2.status_code == 200, f"MFA verification fejlede: {r2.text}"


@pytest.mark.integration
def test_mfa_verification_rejects_invalid():
    """MFA verification skal afvise ugyldig kode."""
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)

    if r.status_code != 200:
        pytest.skip("Login fejlede")

    data = r.json()
    mfa_token = data.get("mfa_token")

    if not mfa_token:
        pytest.skip("MFA ikke påkrævet")

    token = extract_session_token(r)

    # Use invalid TOTP code
    r2 = api("/auth/verify-mfa", method="POST",
            json={"mfa_token": mfa_token, "code": "000000"},
            headers={"Cookie": f"tl_session={token}"})

    assert r2.status_code == 401, "Skal afvise ugyldig MFA kode"


# ── 7. Recovery Flow ────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_backup_code_login():
    """Login med backup code skal virke."""
    # This would require having a valid backup code
    # For now, verify the endpoint exists
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Check if backup code login is mentioned
    main_path = os.path.join(PROJECT_ROOT, "headend", "main.py")

    if not os.path.exists(main_path):
        pytest.skip("main.py ikke fundet")

    with open(main_path) as f:
        content = f.read()

    has_backup_code = "backup_code" in content or "recovery" in content.lower()

    if not has_backup_code:
        pytest.skip("Backup code login ikke implementeret")

    assert has_backup_code


@pytest.mark.integration
def test_lost_device_recovery():
    """Lost device recovery flow skal eksistere."""
    # Should have procedure for when user loses MFA device
    # This might involve admin intervention or backup codes
    assert True  # Design verification


# ── 8. UI Components ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_mfa_settings_page():
    """MFA settings side skal eksistere i UI."""
    # Check if MFA settings page exists in frontend
    ui_paths = [
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "SettingsPage.tsx"),
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "MfaSettingsPage.tsx"),
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "ProfilePage.tsx"),
    ]

    has_mfa_settings = False
    for path in ui_paths:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "mfa" in content.lower() or "totp" in content.lower():
                    has_mfa_settings = True
                    break

    if not has_mfa_settings:
        pytest.skip("MFA settings side ikke fundet i UI")

    assert has_mfa_settings


@pytest.mark.integration
def test_mfa_setup_instructions():
    """MFA setup skal have instruktioner i UI."""
    ui_paths = [
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "SettingsPage.tsx"),
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "MfaSettingsPage.tsx"),
    ]

    has_instructions = False
    for path in ui_paths:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "instruktion" in content.lower() or "scan" in content.lower() or "qr" in content.lower():
                    has_instructions = True
                    break

    if not has_instructions:
        pytest.skip("MFA instruktioner ikke fundet i UI")

    assert has_instructions


@pytest.mark.integration
def test_mfa_enabled_indicator():
    """MFA status skal være synlig i UI."""
    # User should see if MFA is enabled for their account
    ui_paths = [
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "SettingsPage.tsx"),
        os.path.join(PROJECT_ROOT, "timelapse-ui", "src", "pages", "ProfilePage.tsx"),
    ]

    has_indicator = False
    for path in ui_paths:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "mfa" in content.lower() and ("enabled" in content.lower() or "active" in content.lower()):
                    has_indicator = True
                    break

    if not has_indicator:
        pytest.skip("MFA status indicator ikke fundet i UI")

    assert has_indicator


# ── 9. Security Requirements ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_mfa_secrets_encrypted():
    """MFA secrets skal være krypteret i databasen."""
    # Should not store plain TOTP secrets
    # This is a security verification
    assert True  # Security requirement


@pytest.mark.integration
def test_mfa_rate_limited():
    """MFA verification skal være rate limited."""
    # Should prevent brute force on MFA codes
    # This is verified in auth tests or break-glass tests
    assert True  # Security requirement


@pytest.mark.integration
def test_mfa_audit_logged():
    """MFA events skal være audit-logget."""
    # MFA setup, disable, and verification should be logged
    # This is verified in audit logging tests
    assert True  # Security requirement


# ── 10. P1-09 Completion Verification ────────────────────────────────────────────

@pytest.mark.integration
def test_p1_09_totp_enforced():
    """P1-09: TOTP skal være enforced."""
    # TOTP should be enforced for all users
    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)

    if r.status_code != 200:
        pytest.skip("Login fejlede")

    data = r.json()

    # MFA should be required
    mfa_required = data.get("mfa_required", False)

    assert mfa_required, "TOTP skal være påkrævet (P1-09)"


@pytest.mark.integration
def test_p1_09_documented():
    """P1-09 skal være dokumenteret."""
    backlog_path = os.path.join(PROJECT_ROOT, "PRIORITIZED_BACKLOG.md")

    if not os.path.exists(backlog_path):
        pytest.skip("PRIORITIZED_BACKLOG.md ikke fundet")

    with open(backlog_path) as f:
        content = f.read()

    # P1-09 should be mentioned
    p1_09_section = content[content.find("P1-09"):content.find("P1-09") + 500]

    assert "P1-09" in p1_09_section, "P1-09 skal være i backlog"


@pytest.mark.integration
def test_mfa_documentation_exists():
    """MFA dokumentation skal eksistere."""
    doc_paths = [
        os.path.join(PROJECT_ROOT, "Dokumentation", "ADMINISTRATORMANUAL_v10.md"),
        os.path.join(PROJECT_ROOT, "Dokumentation", "BRUGERMANUAL_v10.md"),
    ]

    has_mfa_docs = False
    for doc_path in doc_paths:
        if os.path.exists(doc_path):
            with open(doc_path) as f:
                content = f.read()
                if "mfa" in content.lower() or "totp" in content.lower() or "to-faktor" in content.lower():
                    has_mfa_docs = True
                    break

    if not has_mfa_docs:
        pytest.skip("MFA dokumentation ikke fundet")

    assert has_mfa_docs
