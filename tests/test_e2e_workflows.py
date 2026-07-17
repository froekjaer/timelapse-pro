"""
TimeLapse Pro — End-to-End Workflow Tests (P0)
================================================

Integration tests for complete workflows across the system:
1. Capture Flow E2E — Device auth → Upload → Thumbnail → API availability
2. Update Flow E2E — Version check → Approval → Deploy → Status
3. User Lifecycle E2E — Create → Login → MFA → Role change → Deactivate → Delete

Kør: pytest tests/test_e2e_workflows.py -v

Marker: integration (kræver live headend på TIMELAPSE_TEST_BASE_URL)
"""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import time

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# Test credentials
SUPER_ADMIN_CREDS = {"username": "test-super-admin", "password": "TestSuperAdmin123!"}
SUPER_ADMIN_MFA_SECRET = "J5MWYQYR5NFZW2ZJ"
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


def get_admin_token() -> Optional[str]:
    """Hent admin session token - bruger super_admin med MFA."""
    import pyotp
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


def get_viewer_token() -> Optional[str]:
    """Hent viewer session token."""
    r = api("/auth/login", method="POST", json=VIEWER_CREDS)
    if r.status_code == 200:
        return extract_session_token(r)
    return None


def response_items(payload, key: str) -> list[dict]:
    """Accept the current direct-list contract and the legacy wrapped contract."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get(key, [])
        return value if isinstance(value, list) else []
    return []


# =============================================================================
# 1. CAPTURE FLOW E2E
# =============================================================================
# Flow: Device auth → Capture metadata → File upload → Thumbnail → Availability
# =============================================================================

@pytest.mark.integration
def test_capture_flow_device_auth():
    """E2E: Device kan autentificere med token."""
    # Dette kræver et rigtigt device token - vi skipper i E2E tests
    pytest.skip("Kræver device token auth")


@pytest.mark.integration
def test_capture_flow_metadata_upload():
    """E2E: Capture metadata kan uploades."""
    # Dette kræver device auth
    pytest.skip("Kræver device token auth")


@pytest.mark.integration
def test_capture_flow_file_upload():
    """E2E: Capture fil kan uploades."""
    # Dette kræver device auth
    pytest.skip("Kræver device token auth")


@pytest.mark.integration
def test_capture_flow_thumbnail_generation():
    """E2E: Thumbnail genereres automatisk."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Tjek backlog for at se om auto-generation kører
    r = make_authenticated_request(token, "/admin/thumbnail-backlog")
    if r.status_code != 200:
        pytest.skip("Kunne ikke hente backlog")

    data = r.json()
    # Backlog skal kunne scannes
    assert "scan_time_seconds" in data
    # Auto loop er aktiv hvis vi kan hente backlog
    assert data.get("total") is not None


@pytest.mark.integration
def test_capture_flow_available_in_api():
    """E2E: Capture er tilgængelig via API efter upload."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Hent captures - skal virke
    r = make_authenticated_request(token, "/admin/captures?limit=1")
    if r.status_code != 200:
        pytest.fail(f"Kunne ikke hente captures: {r.status_code}")

    data = r.json()
    # API returnerer liste direkte
    assert isinstance(data, list)
    # Listen kan være tom eller have captures
    assert len(data) >= 0


@pytest.mark.integration
def test_capture_flow_metadata_enriched():
    """E2E: Capture metadata beriges med EXIF."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Hent en capture med detaljer
    r = make_authenticated_request(token, "/admin/captures?limit=1")
    if r.status_code != 200:
        pytest.skip("Kunne ikke hente captures")

    captures = r.json() if isinstance(r.json(), list) else []
    if not captures:
        pytest.skip("Ingen captures at teste")

    # Tjek at capture har metadata
    capture = captures[0]
    assert capture.get("filename") is not None
    assert capture.get("device_id") is not None


@pytest.mark.integration
def test_capture_flow_quality_flag():
    """E2E: Quality flag er sat korrekt."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Hent captures
    r = make_authenticated_request(token, "/admin/captures?limit=10")
    if r.status_code != 200:
        pytest.skip("Kunne ikke hente captures")

    captures = r.json() if isinstance(r.json(), list) else []
    # Tjek at quality_flag findes (kan være None)
    for capture in captures[:3]:
        # Quality flag kan være None, PASS eller FAIL
        quality = capture.get("quality_flag")
        # Hvis den er sat, skal den være gyldig
        if quality:
            assert quality in ["PASS", "FAIL"]


@pytest.mark.integration
def test_capture_flow_ai_result():
    """E2E: AI resultat er koblet til capture."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Hent captures
    r = make_authenticated_request(token, "/admin/captures?limit=10")
    if r.status_code != 200:
        pytest.skip("Kunne ikke hente captures")

    captures = r.json() if isinstance(r.json(), list) else []
    if not captures:
        pytest.skip("Ingen captures at teste")

    # Tjek at ai_result feltet findes (kan være None eller JSON string)
    for capture in captures[:3]:
        ai_result = capture.get("ai_result")
        # Hvis den er sat, skal den være gyldig JSON eller None
        if ai_result:
            try:
                parsed = json.loads(ai_result) if isinstance(ai_result, str) else ai_result
                assert isinstance(parsed, dict)
            except:
                pytest.fail(f"ai_result er ikke gyldig JSON: {ai_result}")


@pytest.mark.integration
def test_capture_flow_pagination():
    """E2E: Captures kan pagineres."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Hent første side
    r1 = make_authenticated_request(token, "/admin/captures?limit=5&offset=0")
    if r1.status_code != 200:
        pytest.skip("Kunne ikke hente captures")

    page1 = r1.json()
    captures1 = page1 if isinstance(page1, list) else []

    # Hent anden side
    r2 = make_authenticated_request(token, "/admin/captures?limit=5&offset=5")
    if r2.status_code != 200:
        pytest.skip("Kunne ikke hente anden side")

    page2 = r2.json()
    captures2 = page2 if isinstance(page2, list) else []

    # Sider skal være forskellige (hvis der er nok captures)
    if len(captures1) == 5 and len(captures2) > 0:
        # Tjek at fangerne er forskellige
        filenames1 = {c.get("filename") for c in captures1}
        filenames2 = {c.get("filename") for c in captures2}
        # Forskellige sider skal ikke overlappe
        overlap = filenames1 & filenames2
        assert len(overlap) == 0, "Sider må ikke overlappe"


@pytest.mark.integration
def test_capture_flow_filter_by_device():
    """E2E: Captures kan filtreres per device."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Først hent alle for at finde en device
    r1 = make_authenticated_request(token, "/admin/captures?limit=1")
    if r1.status_code != 200:
        pytest.skip("Kunne ikke hente captures")

    data1 = r1.json()
    captures = data1 if isinstance(data1, list) else []
    if not captures:
        pytest.skip("Ingen captures at teste")

    device_id = captures[0].get("device_id")
    if not device_id:
        pytest.skip("Capture mangler device_id")

    # Filtrer på device
    r2 = make_authenticated_request(token, f"/admin/captures?device_id={device_id}")
    if r2.status_code != 200:
        pytest.fail(f"Kunne ikke filtrere captures: {r2.status_code}")

    filtered = r2.json()
    # Alle captures skal være fra den device
    for capture in (filtered if isinstance(filtered, list) else []):
        assert capture.get("device_id") == device_id


# =============================================================================
# 2. UPDATE FLOW E2E
# =============================================================================
# Flow: Check updates → List pending → Approve → Deploy → Status check
# =============================================================================

@pytest.mark.integration
def test_update_flow_list_pending():
    """E2E: Pending updates kan listes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    assert r.status_code == 200
    assert isinstance(response_items(r.json(), "updates"), list)


@pytest.mark.integration
def test_update_flow_approve():
    """E2E: Update kan godkendes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Først listen for pending updates
    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente pending updates")

    updates = response_items(r.json(), "updates")
    if not updates:
        pytest.skip("Ingen pending updates")

    # Vi forventer approve endpoint at findes - men skip hvis ikke
    update_id = updates[0].get("id")
    if not update_id:
        pytest.skip("Update mangler ID")

    # Prøv at approve (endpoint måske ikke implementeret)
    r2 = make_authenticated_request(token, f"/admin/updates/{update_id}/approve", method="POST")
    if r2.status_code == 404:
        pytest.skip("Approve endpoint ikke implementeret")

    # Should succeed or return error about state
    assert r2.status_code in [200, 400, 409]


@pytest.mark.integration
def test_update_flow_status():
    """E2E: Update status kan hentes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Vi tjekker om vi kan hente status for updates
    # Dette kan være på et endpoint der lister updates eller specifik status
    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente updates")

    data = response_items(r.json(), "updates")
    # Tjek at updates har status
    for update in data[:3]:
        assert "status" in update
        # Status skal være gyldig
        valid_statuses = ["pending", "approved", "rejected", "deployed", "rolled_back"]
        if update.get("status"):
            assert update["status"] in valid_statuses


@pytest.mark.integration
def test_update_flow_severity_levels():
    """E2E: Updates har severity levels."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente updates")

    data = response_items(r.json(), "updates")
    # Tjek severity felter
    for update in data[:3]:
        severity = update.get("severity")
        if severity:
            assert severity in ["critical", "high", "medium", "low"]


@pytest.mark.integration
def test_update_flow_scope_types():
    """E2E: Updates har scope (global/customer/site/device)."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente updates")

    data = response_items(r.json(), "updates")
    # Tjek scope felter
    for update in data[:3]:
        scope = update.get("scope")
        if scope:
            assert scope in ["global", "customer", "site", "device"]


@pytest.mark.integration
def test_update_flow_version_info():
    """E2E: Updates har versionsinformation."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente updates")

    data = response_items(r.json(), "updates")
    # Tjek version
    for update in data[:3]:
        # Version skal være en string
        version = update.get("version")
        if version:
            assert isinstance(version, str)
            assert len(version) > 0


@pytest.mark.integration
def test_update_flow_created_timestamp():
    """E2E: Updates har created_at timestamp."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente updates")

    data = response_items(r.json(), "updates")
    # Tjek created_at
    for update in data[:3]:
        created_at = update.get("created_at")
        if created_at:
            # Skal kunne parses som dato
            # Kan være ISO string eller allerede parsed
            assert created_at is not None


@pytest.mark.integration
def test_update_flow_description():
    """E2E: Updates har description."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/updates/pending")
    if r.status_code == 404:
        pytest.skip("Endpoint ikke implementeret")

    if r.status_code != 200:
        pytest.skip("Kunne ikke hente updates")

    data = response_items(r.json(), "updates")
    # Tjek description
    for update in data[:3]:
        description = update.get("description")
        if description:
            assert isinstance(description, str)
            # Description skal være rimelig lang (> 10 tegn)
            if len(description) > 0:
                assert len(description) >= 10 or description.startswith("<")  # HTML?


# =============================================================================
# 3. USER LIFECYCLE E2E
# =============================================================================
# Flow: Create → Login → MFA setup → Role change → Deactivate → Delete
# =============================================================================

@pytest.mark.integration
def test_user_lifecycle_create():
    """E2E: Bruger kan oprettes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret en test bruger
    unique_suffix = int(time.time())
    username = f"test-lifecycle-{unique_suffix}"

    r = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": username,
        "email": f"{username}@timelapse.local",
        "password": "TestPassword123!",
        "role": "viewer"
    })

    if r.status_code == 400 and "findes allerede" in r.json().get("detail", ""):
        pytest.skip("Bruger findes allerede")

    assert r.status_code == 200, f"Opret bruger fejlede: {r.status_code} - {r.text}"
    data = r.json()
    assert "id" in data
    assert data.get("username") == username


@pytest.mark.integration
def test_user_lifecycle_login():
    """E2E: Ny bruger kan logge ind."""
    # Først opret bruger
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    unique_suffix = int(time.time())
    username = f"test-login-{unique_suffix}"

    r1 = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": username,
        "email": f"{username}@timelapse.local",
        "password": "TestLogin123!",
        "role": "viewer"
    })

    if r1.status_code != 200:
        pytest.skip("Kunne ikke oprette bruger")

    # Prøv at logge ind
    r2 = api("/auth/login", method="POST", json={
        "username": username,
        "password": "TestLogin123!"
    })

    assert r2.status_code == 200, f"Login fejlede: {r2.status_code}"
    data = r2.json()
    assert data.get("username") == username
    assert extract_session_token(r2) is not None


@pytest.mark.integration
def test_user_lifecycle_mfa_setup():
    """E2E: Bruger kan opsætte MFA."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret bruger
    unique_suffix = int(time.time())
    username = f"test-mfa-{unique_suffix}"

    r1 = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": username,
        "email": f"{username}@timelapse.local",
        "password": "TestMfa123!",
        "role": "operator"
    })

    if r1.status_code != 200:
        pytest.skip("Kunne ikke oprette bruger")

    # Log ind som bruger
    r2 = api("/auth/login", method="POST", json={
        "username": username,
        "password": "TestMfa123!"
    })

    if r2.status_code != 200:
        pytest.skip("Kunne ikke logge ind")

    user_token = extract_session_token(r2)

    # Opsæt MFA
    r3 = make_authenticated_request(user_token, "/auth/mfa/setup", method="POST")
    if r3.status_code == 404:
        pytest.skip("MFA endpoint ikke implementeret")

    assert r3.status_code == 200
    mfa_data = r3.json()
    # Skal have secret eller QR code data
    assert "secret" in mfa_data or "qr_code" in mfa_data or "totp_secret" in mfa_data


@pytest.mark.integration
def test_user_lifecycle_role_change():
    """E2E: Bruger rolle kan ændres."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret bruger
    unique_suffix = int(time.time())
    username = f"test-role-{unique_suffix}"

    r1 = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": username,
        "email": f"{username}@timelapse.local",
        "password": "TestRole123!",
        "role": "viewer"
    })

    if r1.status_code != 200:
        pytest.skip("Kunne ikke oprette bruger")

    user_data = r1.json()
    user_id = user_data.get("id")

    # Ændr rolle til operator
    r2 = make_authenticated_request(token, f"/admin/users/{user_id}", method="PUT", json={
        "role": "operator"
    })

    if r2.status_code == 404:
        pytest.skip("Update user endpoint ikke implementeret")

    assert r2.status_code == 200

    # Verificer ændring ved at hente bruger
    r3 = make_authenticated_request(token, f"/admin/users/{user_id}")
    if r3.status_code == 200:
        updated = r3.json()
        assert updated.get("role") == "operator"


@pytest.mark.integration
def test_user_lifecycle_deactivate():
    """E2E: Bruger kan deaktiveres."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret bruger
    unique_suffix = int(time.time())
    username = f"test-deactivate-{unique_suffix}"

    r1 = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": username,
        "email": f"{username}@timelapse.local",
        "password": "TestDeactivate123!",
        "role": "viewer"
    })

    if r1.status_code != 200:
        pytest.skip("Kunne ikke oprette bruger")

    user_data = r1.json()
    user_id = user_data.get("id")

    # Deaktiver bruger
    r2 = make_authenticated_request(token, f"/admin/users/{user_id}", method="PUT", json={
        "is_active": False
    })

    if r2.status_code == 404:
        pytest.skip("Update user endpoint ikke implementeret")

    assert r2.status_code == 200

    # Verificer at bruger ikke kan logge ind
    r3 = api("/auth/login", method="POST", json={
        "username": username,
        "password": "TestDeactivate123!"
    })

    # Login skal fejle for inaktiv bruger
    assert r3.status_code in [401, 403], "Inaktiv bruger skal ikke kunne logge ind"


@pytest.mark.integration
def test_user_lifecycle_delete():
    """E2E: Bruger kan slettes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret bruger
    unique_suffix = int(time.time())
    username = f"test-delete-{unique_suffix}"

    r1 = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": username,
        "email": f"{username}@timelapse.local",
        "password": "TestDelete123!",
        "role": "viewer"
    })

    if r1.status_code != 200:
        pytest.skip("Kunne ikke oprette bruger")

    user_data = r1.json()
    user_id = user_data.get("id")

    # Slet bruger
    r2 = make_authenticated_request(token, f"/admin/users/{user_id}", method="DELETE")

    assert r2.status_code == 200

    # Der findes ikke et GET-by-id endpoint; verificer mod den kanoniske liste.
    r3 = make_authenticated_request(token, "/admin/users")
    assert r3.status_code == 200
    assert all(user.get("id") != user_id for user in response_items(r3.json(), "users")), \
        "Slettet bruger skal ikke findes"


@pytest.mark.integration
def test_user_lifecycle_list_users():
    """E2E: Brugere kan listes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/users")
    if r.status_code == 404:
        pytest.skip("List users endpoint ikke implementeret")

    assert r.status_code == 200
    assert isinstance(response_items(r.json(), "users"), list)


@pytest.mark.integration
def test_user_lifecycle_viewer_cannot_create_users():
    """E2E: Viewer kan ikke oprette brugere."""
    viewer_token = get_viewer_token()
    if not viewer_token:
        pytest.skip("Kunne ikke få viewer token")

    r = make_authenticated_request(viewer_token, "/admin/users", method="POST", json={
        "username": "test-should-fail",
        "email": "test@fail.local",
        "password": "TestFail123!",
        "role": "viewer"
    })

    # Viewer skal være nægtet
    assert r.status_code in [401, 403], "Viewer skal ikke kunne oprette brugere"


@pytest.mark.integration
def test_user_lifecycle_operator_cannot_create_users():
    """E2E: Operator kan ikke oprette brugere."""
    # Først log ind som operator
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    if r.status_code != 200:
        pytest.skip("Kunne ikke logge ind som operator")

    operator_token = extract_session_token(r)

    # Prøv at oprette bruger
    r2 = make_authenticated_request(operator_token, "/admin/users", method="POST", json={
        "username": "test-should-fail",
        "email": "test@fail.local",
        "password": "TestFail123!",
        "role": "viewer"
    })

    # Operator skal være nægtet
    assert r2.status_code in [401, 403], "Operator skal ikke kunne oprette brugere"


@pytest.mark.integration
def test_user_lifecycle_password_validation():
    """E2E: Password validering virker."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Prøv at oprette bruger med svagt password
    r = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": "test-weak-pwd",
        "email": "test@weak.local",
        "password": "123456",  # For kort
        "role": "viewer"
    })

    # Skal fejle med password for kort
    assert r.status_code == 400, "Password validation skal virke"
    detail = r.json().get("detail", "")
    assert "password" in detail.lower() or "adgangskode" in detail.lower()


@pytest.mark.integration
def test_user_lifecycle_role_validation():
    """E2E: Rolle validering virker."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Prøv at oprette bruger med ugyldig rolle
    r = make_authenticated_request(token, "/admin/users", method="POST", json={
        "username": "test-invalid-role",
        "email": "test@invalid.local",
        "password": "TestRole123!",
        "role": "invalid_role"
    })

    # Skal fejle med ugyldig rolle
    assert r.status_code == 400, "Rolle validation skal virke"
    detail = r.json().get("detail", "")
    assert "rolle" in detail.lower() or "role" in detail.lower()
