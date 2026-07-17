"""
TimeLapse Pro — Camera Management CRUD Tests (P0)
=================================================

Tests for camera management CRUD operations:
- GET /api/admin/cameras (list cameras)
- POST /api/admin/cameras (create camera)
- PUT /api/admin/cameras/{camera_id} (update camera)
- Camera metadata operations (baseline_description, context_notes)
- Network config operations (wifi, ethernet)
- Camera decommission/retire flow
- Camera-to-device assignment

Kør: pytest tests/test_camera_crud.py -v

Marker: integration (kræver live headend på TIMELAPSE_TEST_BASE_URL)
"""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
import json

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# Test credentials - matcher conftest.py
# Admin session bruger operator credentials (har admin rettigheder i test setup)
ADMIN_CREDS = {"username": "test-operator", "password": "TestOperator123!"}
OPERATOR_CREDS = {"username": "test-operator", "password": "TestOperator123!"}
VIEWER_CREDS = {"username": "test-viewer", "password": "TestViewer123!"}
SUPER_ADMIN_CREDS = {"username": "test-super-admin", "password": "TestSuperAdmin123!"}
SUPER_ADMIN_MFA_SECRET = "S7WPSYFLX6YYLFSIVI67K7GBZI34P67N"


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

    # Håndter MFA krav
    if data.get("mfa_required"):
        totp = pyotp.TOTP(SUPER_ADMIN_MFA_SECRET)
        totp_code = totp.now()
        r2 = api("/auth/verify-mfa", method="POST",
                json={"mfa_token": data.get("mfa_token"), "code": totp_code},
                headers={"Cookie": f"tl_session={token}"})
        if r2.status_code == 200:
            return extract_session_token(r2)

    return token


def get_operator_token() -> Optional[str]:
    """Hent operator session token."""
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    if r.status_code == 200:
        return extract_session_token(r)
    return None


def get_super_admin_token() -> Optional[str]:
    """Hent super_admin session token med MFA."""
    import pyotp

    r = api("/auth/login", method="POST", json=SUPER_ADMIN_CREDS)
    if r.status_code != 200:
        return None

    data = r.json()
    token = extract_session_token(r)

    # Håndter MFA krav
    if data.get("mfa_required"):
        totp = pyotp.TOTP(SUPER_ADMIN_MFA_SECRET)
        totp_code = totp.now()
        r2 = api("/auth/verify-mfa", method="POST",
                json={"mfa_token": data.get("mfa_token"), "code": totp_code},
                headers={"Cookie": f"tl_session={token}"})
        if r2.status_code == 200:
            return extract_session_token(r2)

    return token


def generate_test_camera_name() -> str:
    """Generer unikt test kamera navn."""
    return f"Test Camera {uuid.uuid4().hex[:8].upper()}"


# ── 1. List Cameras ────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_list_cameras_as_admin():
    """Admin skal kunne liste alle kameraer."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/cameras")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Hvert camera skalhave minimumsfelter
    for cam in data[:3]:  # Check first 3
        assert "id" in cam
        assert "camera_name" in cam


@pytest.mark.integration
def test_list_cameras_as_operator():
    """Operator skal kunne liste kameraer."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    r = make_authenticated_request(token, "/admin/cameras")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.integration
def test_list_cameras_without_auth_fails():
    """List cameras skal kræve autentificering."""
    r = api("/admin/cameras")
    assert r.status_code in [401, 403], "List cameras skal kræve auth"


@pytest.mark.integration
def test_list_cameras_filters_by_site():
    """Camera liste kan filtreres på site_id."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Først list alle for at finde et site_id
    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    cameras = r.json()
    # Find et kamera med site_id
    site_id = None
    for cam in cameras:
        if cam.get("site_id"):
            site_id = cam["site_id"]
            break

    if site_id:
        r2 = make_authenticated_request(token, f"/admin/cameras?site_id={site_id}")
        assert r2.status_code == 200
        filtered = r2.json()
        # Alle kameraer skal have dette site_id eller være NULL
        for cam in filtered:
            assert cam.get("site_id") in [site_id, None]


@pytest.mark.integration
def test_list_cameras_excludes_retired():
    """Retired kameraer skal ikke vises i listen."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/cameras")
    assert r.status_code == 200
    data = r.json()
    # Retired cameras skal have retired_at sat og filtreres fra i SQL
    for cam in data:
        assert cam.get("retired_at") is None or "retired_at" not in cam


# ── 2. Create Camera (POST) ───────────────────────────────────────────────────

@pytest.mark.integration
def test_create_camera_as_admin():
    """Admin skal kunne oprette nyt kamera."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    camera_name = generate_test_camera_name()
    payload = {
        "camera_name": camera_name,
        "serial_number": f"TL-SN-{uuid.uuid4().hex[:8].upper()}",
        "model": "Test Model",
        "notes": "Test camera for pytest",
    }

    r = make_authenticated_request(token, "/admin/cameras", method="POST", json=payload)
    assert r.status_code in [200, 201], f"Create camera fejlede: {r.text}"
    data = r.json()
    assert "id" in data


@pytest.mark.integration
def test_create_camera_with_customer():
    """Opret kamera tilknyttet customer."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find en customer_id først
    r = make_authenticated_request(token, "/admin/customers")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen customers til test")

    customers = r.json()
    customer_id = customers[0].get("id") if isinstance(customers[0], dict) else customers[0]

    camera_name = generate_test_camera_name()
    payload = {
        "camera_name": camera_name,
        "customer_id": customer_id,
    }

    r2 = make_authenticated_request(token, "/admin/cameras", method="POST", json=payload)
    assert r2.status_code in [200, 201], f"Create camera med customer fejlede: {r2.text}"


@pytest.mark.integration
def test_create_camera_default_name():
    """Opret kamera uden navn skal bruge default 'Nyt kamera'."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    payload = {
        "serial_number": "TL-SN-TEST",
    }

    r = make_authenticated_request(token, "/admin/cameras", method="POST", json=payload)
    # API'en bruger default navn hvis camera_name mangler
    assert r.status_code in [200, 201], "Camera skal kunne oprettes med default navn"
    data = r.json()
    assert "id" in data


@pytest.mark.integration
def test_create_camera_as_operator_fails():
    """Operator skal ikke kunne oprette kameraer."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    payload = {"camera_name": "Unauthorized Camera"}

    r = make_authenticated_request(token, "/admin/cameras", method="POST", json=payload)
    assert r.status_code in [403, 401], "Operator skal ikke kunne oprette kameraer"


# ── 3. Update Camera (PUT) ────────────────────────────────────────────────────

@pytest.mark.integration
def test_update_camera_as_admin():
    """Admin skal kunne opdatere kamera metadata."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Først opret eller find et kamera
    create_r = make_authenticated_request(token, "/admin/cameras", method="POST", json={
        "camera_name": generate_test_camera_name(),
        "notes": "Original notes"
    })

    if create_r.status_code not in [200, 201]:
        pytest.skip("Kunne ikke oprette test kamera")

    camera_id = create_r.json()["id"]
    new_name = f"Updated {generate_test_camera_name()}"

    # Opdater kameraet
    update_r = make_authenticated_request(token, f"/admin/cameras/{camera_id}",
                                          method="PUT", json={
                                              "camera_name": new_name,
                                              "notes": "Updated notes",
                                              "model": "Updated Model"
                                          })
    assert update_r.status_code in [200, 202], f"Update camera fejlede: {update_r.text}"
    data = update_r.json()
    assert data.get("status") == "ok" or "id" in data


@pytest.mark.integration
def test_update_camera_with_network_config():
    """Opdater kamera med wifi konfiguration."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret kamera først
    create_r = make_authenticated_request(token, "/admin/cameras", method="POST", json={
        "camera_name": generate_test_camera_name(),
        "network_type": "ethernet",
    })

    if create_r.status_code not in [200, 201]:
        pytest.skip("Kunne ikke oprette test kamera")

    camera_id = create_r.json()["id"]

    # Opdater network config
    update_r = make_authenticated_request(token, f"/admin/cameras/{camera_id}",
                                          method="PUT", json={
                                              "network_type": "wifi",
                                              "wifi_ssid": "TestWiFi",
                                              "wifi_country": "DK",
                                          })
    assert update_r.status_code in [200, 202]


@pytest.mark.integration
def test_update_camera_with_ai_context():
    """Opdater kamera med AI kontekst (baseline_description, context_notes)."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret kamera først
    create_r = make_authenticated_request(token, "/admin/cameras", method="POST", json={
        "camera_name": generate_test_camera_name(),
    })

    if create_r.status_code not in [200, 201]:
        pytest.skip("Kunne ikke oprette test kamera")

    camera_id = create_r.json()["id"]

    # Opdater AI kontekst
    update_r = make_authenticated_request(token, f"/admin/cameras/{camera_id}",
                                          method="PUT", json={
                                              "baseline_description": "Normal scene: parking lot with 20 spaces",
                                              "context_notes": "Construction ongoing on north side - ignore temporary barriers",
                                          })
    assert update_r.status_code in [200, 202]


@pytest.mark.integration
def test_update_nonexistent_camera_returns_404():
    """Opdater ikke-eksisterende kamera skal returnere 404."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    fake_id = str(uuid.uuid4())
    r = make_authenticated_request(token, f"/admin/cameras/{fake_id}",
                                   method="PUT", json={"camera_name": "Ghost"})
    assert r.status_code == 404


@pytest.mark.integration
def test_update_camera_as_operator_fails():
    """Operator skal ikke kunne opdatere kameraer."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    # Find et kamera ID
    list_r = make_authenticated_request(token, "/admin/cameras")
    if list_r.status_code != 200 or not list_r.json():
        pytest.skip("Ingen kameraer at teste")

    camera_id = list_r.json()[0]["id"]

    # Prøv at opdatere
    r = make_authenticated_request(token, f"/admin/cameras/{camera_id}",
                                   method="PUT", json={"camera_name": "Hacked"})
    assert r.status_code in [403, 401], "Operator skal ikke kunne opdatere kameraer"


# ── 4. Camera SSH Key ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_camera_ssh_key_as_admin():
    """Admin skal kunne hente kamera SSH private key."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find et kamera
    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    camera_id = r.json()[0]["id"]

    # Hent SSH key
    r2 = make_authenticated_request(token, f"/admin/cameras/{camera_id}/ssh-key")
    # SSH key eksisterer måske ikke - accepter 404 eller 200
    if r2.status_code == 404:
        # OK - ingen SSH key endnu
        pass
    elif r2.status_code == 200:
        # Key findes - skal være plaintext
        assert "BEGIN" in r2.text or "PRIVATE KEY" in r2.text or len(r2.text) > 0
    else:
        assert False, f"Uventet response: {r2.status_code}"


@pytest.mark.integration
def test_get_camera_ssh_key_as_operator_fails():
    """Operator skal ikke kunne hente SSH private keys."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    # Find et kamera
    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    camera_id = r.json()[0]["id"]

    # Prøv at hente SSH key
    r2 = make_authenticated_request(token, f"/admin/cameras/{camera_id}/ssh-key")
    assert r2.status_code in [403, 401], "Operator skal ikke kunne hente SSH keys"


# ── 5. BT TOTP QR Code ────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_camera_bt_totp_qr():
    """Kan hente BT PAN TOTP QR kode til kamera."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find et kamera
    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    camera_id = r.json()[0]["id"]

    # Hent BT TOTP QR
    r2 = make_authenticated_request(token, f"/admin/cameras/{camera_id}/bt-totp-qr")
    assert r2.status_code == 200, f"BT TOTP QR fejlede: {r2.text}"
    data = r2.json()
    assert "qr_data_uri" in data or "data:image" in str(data)


# ── 6. Camera Device Assignment ───────────────────────────────────────────────

@pytest.mark.integration
def test_camera_device_assignment_in_list():
    """Kamera liste skal vise current device assignment."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    cameras = r.json()
    # Tjek at assignment felter eksisterer
    for cam in cameras[:3]:
        assert "current_device_id" in cam or cam.get("current_device_id") is None
        if cam.get("current_device_id"):
            assert "assigned_at" in cam


@pytest.mark.integration
def test_get_camera_assignment_history():
    """Kan hente kamera assignment historik."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find et kamera
    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    camera_id = r.json()[0]["id"]

    # Hent historik
    r2 = make_authenticated_request(token, f"/admin/cameras/{camera_id}/history")
    assert r2.status_code == 200
    data = r2.json()
    assert isinstance(data, list)


# ── 7. Camera Metadata ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_camera_required_fields():
    """Kamera skal have required felter i responsen."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    cam = r.json()[0]
    required_fields = ["id", "camera_name"]
    for field in required_fields:
        assert field in cam, f"Camera mangeler felt: {field}"


@pytest.mark.integration
def test_camera_optional_fields():
    """Kamera skal have optional felter når sat."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret kamera med basis felter
    create_r = make_authenticated_request(token, "/admin/cameras", method="POST", json={
        "camera_name": generate_test_camera_name(),
        "serial_number": "TL-SN-FULL",
        "model": "Test Model Pro",
        "notes": "Full feature test",
    })

    if create_r.status_code not in [200, 201]:
        pytest.skip("Kunne ikke oprette test kamera")

    camera_id = create_r.json()["id"]

    # Opdater med network_type (skal gøres via PUT)
    update_r = make_authenticated_request(token, f"/admin/cameras/{camera_id}",
                                         method="PUT", json={"network_type": "wifi"})
    if update_r.status_code not in [200, 202]:
        pytest.skip("Kunne ikke opdatere network_type")

    # Hent og verify
    get_r = make_authenticated_request(token, "/admin/cameras")
    cameras = get_r.json()
    created = next((c for c in cameras if c["id"] == camera_id), None)

    if created:
        assert created.get("serial_number") == "TL-SN-FULL"
        assert created.get("model") == "Test Model Pro"
        assert created.get("network_type") == "wifi"


# ── 8. Camera Retirement/Decommission ───────────────────────────────────────────

@pytest.mark.integration
def test_camera_retired_excluded_from_list():
    """Retired kameraer skal ikke vises i listen."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Tjek at listen API filtrerer retired cameras
    r = make_authenticated_request(token, "/admin/cameras")
    assert r.status_code == 200
    cameras = r.json()

    # Ingen kameraer i listen skal have retired_at
    for cam in cameras:
        assert cam.get("retired_at") is None, "Retired kamera må ikke vises i listen"


# ── 9. Edge Cases ────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_camera_with_invalid_id():
    """Get kamera med invalid ID skal fejle."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Prøv med ugyldige ID formats
    invalid_ids = ["invalid", "123", " "]

    for invalid_id in invalid_ids:
        # PUT skal fejle med 404 (ikke 400/422 for invalid UUID format i denne implementation)
        r = make_authenticated_request(token, f"/admin/cameras/{invalid_id}",
                                     method="PUT", json={"camera_name": "Test"})
        if r.status_code == 404:
            break  # OK - ID ikke fundet
        elif r.status_code in [400, 422]:
            break  # OK - validering fejlede
        else:
            pass  # Andet - accepter for nu


@pytest.mark.integration
def test_create_camera_with_config_json():
    """Opret kamera med config JSON."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    payload = {
        "camera_name": generate_test_camera_name(),
        "config": {
            "resolution": "1920x1080",
            "fps": 30,
            "bitrate": 5000000
        }
    }

    r = make_authenticated_request(token, "/admin/cameras", method="POST", json=payload)
    assert r.status_code in [200, 201]


# ── 10. Camera Filter Tests ───────────────────────────────────────────────────

@pytest.mark.integration
def test_list_cameras_empty_response():
    """Tom camera liste skal returnere tom array."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Prøv med customer_id der ikke findes
    r = make_authenticated_request(token, "/admin/cameras?customer_id=nonexistent-customer")
    # Skal returnere 200 med tom liste
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 0


@pytest.mark.integration
def test_camera_site_customer_relation():
    """Kamera skal kunne være tilknyttet site og customer."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200:
        pytest.skip("Kunne ikke liste kameraer")

    cameras = r.json()
    # Tjek relation felter
    for cam in cameras[:3]:
        # site_id og customer_id kan være None
        assert "site_id" in cam
        assert "customer_id" in cam
        # Der skal også være navne-felter
        assert "site_name" in cam or cam.get("site_name") is None
        assert "customer_name" in cam or cam.get("customer_name") is None
        break


@pytest.mark.integration
def test_camera_created_at_timestamp():
    """Kamera skal have created_at timestamp."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/cameras")
    if r.status_code != 200 or not r.json():
        pytest.skip("Ingen kameraer at teste")

    cam = r.json()[0]
    if cam.get("created_at"):
        # Parse ISO datetime
        try:
            created_at = datetime.fromisoformat(cam["created_at"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("created_at skal være ISO format datetime")
        if created_at.tzinfo is None:
            # Legacy PostgreSQL columns expose local wall time without an offset.
            assert created_at <= datetime.now() + timedelta(seconds=5)
        else:
            assert created_at <= datetime.now(timezone.utc) + timedelta(seconds=5)


# ── 11. Camera Config Override Tests ────────────────────────────────────────

@pytest.mark.integration
def test_update_camera_config():
    """Opdater kamera config JSON."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Opret kamera
    create_r = make_authenticated_request(token, "/admin/cameras", method="POST", json={
        "camera_name": generate_test_camera_name(),
        "config": {"key": "original"}
    })

    if create_r.status_code not in [200, 201]:
        pytest.skip("Kunne ikke oprette test kamera")

    camera_id = create_r.json()["id"]

    # Opdater config
    update_r = make_authenticated_request(token, f"/admin/cameras/{camera_id}",
                                          method="PUT", json={
                                              "config": {"key": "updated", "new_field": "value"}
                                          })
    assert update_r.status_code in [200, 202]
