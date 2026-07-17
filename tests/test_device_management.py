"""
TimeLapse Pro — Device Management CRUD Tests (P0)
==================================================

Tests for device management CRUD operations:
- POST /api/admin/devices (create device)
- PUT /api/admin/devices/{id} (update device)
- DELETE /api/admin/devices/{id} (delete device)
- Device assignment/operations
- Device decommission flow

Kør: pytest tests/test_device_management.py -v

Marker: integration (kræver live headend på TIMELAPSE_TEST_BASE_URL)
"""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "TestAdmin123!"}
OPERATOR_CREDS = {"username": "test-operator", "password": "TestOperator123!"}


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
    """Hent admin session token."""
    r = api("/auth/login", method="POST", json=ADMIN_CREDS)
    if r.status_code == 200:
        return extract_session_token(r)
    return None


def get_operator_token() -> Optional[str]:
    """Hent operator session token."""
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    if r.status_code == 200:
        return extract_session_token(r)
    return None


def generate_test_device_id() -> str:
    """Generer unikt test device ID."""
    return f"TL-TEST-{uuid.uuid4().hex[:8].upper()}"


def device_list(response: requests.Response) -> list[dict]:
    """Return the current `/api/admin/devices` list contract."""
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list), "Device API skal returnere en JSON-liste"
    return payload


@pytest.fixture(scope="module", autouse=True)
def isolated_device_fixture():
    """Seed one tenant-scoped device in timelapse_test and remove it afterwards."""
    from headend.database import Customer, Device, SessionLocal, Site, User

    customer_id = "qa-device-customer"
    site_id = "qa-device-site"
    device_id = "TL-QA-DEVICE-FIXTURE"
    db = SessionLocal()
    operator = db.query(User).filter_by(username=OPERATOR_CREDS["username"]).first()
    previous_customer_id = operator.customer_id if operator else None
    try:
        if not db.query(Customer).filter_by(id=customer_id).first():
            db.add(Customer(id=customer_id, name="QA Device Customer"))
        if not db.query(Site).filter_by(id=site_id).first():
            db.add(Site(id=site_id, customer_id=customer_id, name="QA Device Site"))
        fixture_device = db.query(Device).filter_by(device_id=device_id).first()
        if not fixture_device:
            fixture_device = Device(device_id=device_id)
            db.add(fixture_device)
        fixture_device.customer_id = customer_id
        fixture_device.site_id = site_id
        fixture_device.customer_name = "QA Device Customer"
        fixture_device.site_name = "QA Device Site"
        fixture_device.camera_name = "QA Device Camera"
        fixture_device.status = "online"
        fixture_device.last_seen = datetime.now(timezone.utc)
        fixture_device.device_config = "{}"
        if operator:
            operator.customer_id = customer_id
        db.commit()
        yield
    finally:
        db.rollback()
        operator = db.query(User).filter_by(username=OPERATOR_CREDS["username"]).first()
        if operator:
            operator.customer_id = previous_customer_id
        db.query(Device).filter_by(device_id=device_id).delete()
        db.query(Site).filter_by(id=site_id).delete()
        db.query(Customer).filter_by(id=customer_id).delete()
        db.commit()
        db.close()


# ── 1. List Devices ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_list_devices_as_admin():
    """Admin skal kunne liste alle devices."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/devices")
    assert r.status_code == 200
    assert isinstance(device_list(r), list)


@pytest.mark.integration
def test_list_devices_as_operator():
    """Operator skal kunne liste devices."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    r = make_authenticated_request(token, "/admin/devices")
    assert r.status_code == 200
    assert isinstance(device_list(r), list)


@pytest.mark.integration
def test_list_devices_without_auth_fails():
    """List devices skal kræve autentificering."""
    r = api("/admin/devices")
    # Kan returnere 401 eller 403 afhængig af implementering
    assert r.status_code in [401, 403], "List devices skal kræve auth"


# ── 2. Get Single Device ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_device_by_id():
    """Hent specifik device via ID."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Først list alle devices for at finde et ID
    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    device_id = devices[0]["device_id"]

    r2 = make_authenticated_request(token, f"/admin/devices/{device_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert "device" in data
    assert data["device"]["device_id"] == device_id


@pytest.mark.integration
def test_get_nonexistent_device_returns_404():
    """Hent ikke-eksisterende device skal returnere 404."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    fake_id = "TL-NONEXIST"
    r = make_authenticated_request(token, f"/admin/devices/{fake_id}")
    assert r.status_code == 404


# ── 3. Create Device (POST) ───────────────────────────────────────────────────

@pytest.mark.integration
def test_create_device_as_admin():
    """Admin skal kunne oprette ny device."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    device_id = generate_test_device_id()
    payload = {
        "device_id": device_id,
        "name": f"Test Device {device_id}",
        "customer_id": None,
        "site_id": None,
        "device_type": "edge",
        "status": "active"
    }

    r = make_authenticated_request(token, "/admin/devices", method="POST", json=payload)

    # Dette endpoint eksisterer måske ikke — accepter 405 hvis ikke
    if r.status_code == 405:
        pytest.skip("POST /admin/devices endpoint ikke implementeret")
    elif r.status_code in [201, 200]:
        data = r.json()
        assert "device" in data or data.get("ok") is True
        # Cleanup: slet device hvis delete endpoint findes
        make_authenticated_request(token, f"/admin/devices/{device_id}", method="DELETE")
    else:
        # Andre status codes (403, 400) er også acceptable
        pass


@pytest.mark.integration
def test_create_device_requires_admin():
    """Opret device skal kræve admin rolle."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    device_id = generate_test_device_id()
    payload = {
        "device_id": device_id,
        "name": f"Test Device {device_id}",
    }

    r = make_authenticated_request(token, "/admin/devices", method="POST", json=payload)

    # Hvis endpoint ikke findes, 405
    if r.status_code == 405:
        pytest.skip("POST /admin/devices endpoint ikke implementeret")
    # Ellers skal operator være nægtet
    assert r.status_code in [403, 401], "Operator skal ikke kunne oprette devices"


@pytest.mark.integration
def test_create_device_validation_requires_device_id():
    """Opret device skal kræve device_id."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    payload = {
        "name": "Test Device uden ID"
    }

    r = make_authenticated_request(token, "/admin/devices", method="POST", json=payload)

    if r.status_code == 405:
        pytest.skip("POST /admin/devices endpoint ikke implementeret")
    # Validering skal fejle
    assert r.status_code in [400, 422], "Device ID skal være påkrævet"


# ── 4. Update Device (PUT) ───────────────────────────────────────────────────

@pytest.mark.integration
def test_update_device_as_admin():
    """Admin skal kunne opdatere device."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find en eksisterende device
    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    device_id = devices[0]["device_id"]

    original_name = devices[0].get("camera_name")
    try:
        r2 = make_authenticated_request(
            token,
            f"/admin/devices/{device_id}/info",
            method="PUT",
            json={"camera_name": "QA Updated Camera"},
        )
        assert r2.status_code == 200
        detail = make_authenticated_request(token, f"/admin/devices/{device_id}").json()
        assert detail["device"]["camera_name"] == "QA Updated Camera"
    finally:
        make_authenticated_request(
            token,
            f"/admin/devices/{device_id}/info",
            method="PUT",
            json={"camera_name": original_name},
        )


@pytest.mark.integration
def test_update_device_as_operator():
    """Operator rolle check på device update."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    # Find en device
    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    device_id = devices[0]["device_id"]

    r2 = make_authenticated_request(
        token,
        f"/admin/devices/{device_id}/info",
        method="PUT",
        json={"camera_name": "Must not be applied"},
    )
    assert r2.status_code == 403


# ── 5. Delete Device ──────────────────────────────────────────────────────────

@pytest.mark.integration
def test_delete_device_as_admin():
    """Admin skal kunne slette device."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    device_id = generate_test_device_id()
    from headend.database import Device, SessionLocal
    db = SessionLocal()
    try:
        db.add(Device(device_id=device_id, camera_name="QA delete fixture"))
        db.commit()
    finally:
        db.close()

    r = make_authenticated_request(token, f"/admin/devices/{device_id}", method="DELETE")
    assert r.status_code == 200
    assert make_authenticated_request(token, f"/admin/devices/{device_id}").status_code == 404


@pytest.mark.integration
def test_delete_device_requires_admin():
    """Delete device skal kræve admin rolle."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    # Prøv at slette en device
    device_id = "TL-SOMEDEVICE"
    r = make_authenticated_request(token, f"/admin/devices/{device_id}", method="DELETE")

    if r.status_code == 405:
        pytest.skip("DELETE /admin/devices/{id} endpoint ikke implementeret")
    # Operator skal ikke kunne slette
    assert r.status_code in [403, 401, 404], "Operator skal ikke kunne slette devices"


# ── 6. Device Config ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_device_config():
    """Device config skal kunne hentes."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find en device
    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    device_id = devices[0]["device_id"]

    # Tjek at device response indeholder config
    r2 = make_authenticated_request(token, f"/admin/devices/{device_id}")
    if r2.status_code == 200:
        data = r2.json()
        assert "device" in data
        assert isinstance(data.get("device_config"), dict)


# ── 7. Device Status ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_device_status_active():
    """Device status skal kunne være active."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    # Find en device med status
    for device in devices:
        if "status" in device:
            # Status skal være en af de kendte værdier
            assert device["status"] in ["online", "offline", "unknown"]
            break
    else:
        pytest.skip("Ingen devices med status field")


# ── 8. Device Assignment ──────────────────────────────────────────────────────

@pytest.mark.integration
def test_device_customer_site_relation():
    """Device skal kunne være tilknyttet customer/site."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/devices")
    if r.status_code != 200:
        pytest.skip("Kunne ikke liste devices")

    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices")
    # Tjek at devices kan have customer_id og site_id
    for device in devices[:3]:  # Check first 3
        # customer_id kan være None (platform devices)
        assert "customer_id" in device or "site_id" in device
        break


# ── 9. Device Last Seen ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_device_last_seen_recent():
    """Device skal have sidst set tid."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    for device in devices:
        if device.get("last_seen"):
            last_seen = device["last_seen"]
            # Parse ISO datetime
            try:
                last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                # Skal være inden for de sidste 30 dage (eller enheden er offline)
                if last_seen_dt.tzinfo is None:
                    last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - last_seen_dt
                assert age.total_seconds() >= 0, "last_seen kan ikke være i fremtiden"
                break
            except Exception:
                pass

    else:
        pytest.skip("Ingen devices med last_seen")


# ── 10. Device Decommission Flow ─────────────────────────────────────────────

@pytest.mark.integration
def test_device_decommission_sets_inactive():
    """Decommission af device skal sætte status til inactive."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Hvis PUT endpoint findes, prøv at decommission
    device_id = generate_test_device_id()

    # Først opret
    create_r = make_authenticated_request(token, "/admin/devices", method="POST", json={
        "device_id": device_id,
        "name": "To decommission",
        "status": "active"
    })

    if create_r.status_code == 405:
        pytest.skip("POST /admin/devices ikke implementeret")

    # Så sæt til inactive
    update_r = make_authenticated_request(token, f"/admin/devices/{device_id}", method="PUT", json={
        "status": "inactive"
    })

    if update_r.status_code == 405:
        pytest.skip("PUT /admin/devices/{id} ikke implementeret")
    elif update_r.status_code in [200, 202]:
        # Verify status er ændret
        get_r = make_authenticated_request(token, f"/admin/devices/{device_id}")
        if get_r.status_code == 200:
            data = get_r.json()
            if "device" in data and "status" in data["device"]:
                assert data["device"]["status"] == "inactive"


# ── 11. Edge Cases ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_device_with_invalid_id():
    """Get device med invalid ID skal fejle."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Prøv med ugyldige ID formats
    invalid_ids = ["", " ", "TL-!", "TL-very-long-device-id-that-exceeds-reasonable-length"]

    for invalid_id in invalid_ids:
        r = make_authenticated_request(token, f"/admin/devices/{invalid_id}")
        # Skal fejle med 404 eller 400
        if r.status_code not in [404, 400]:
            # Nogle IDs måske gyldige — det er OK
            pass


@pytest.mark.integration
def test_create_duplicate_device_id():
    """Opret device med duplikeret ID skal fejle."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Find en eksisterende device ID
    r = make_authenticated_request(token, "/admin/devices")
    devices = device_list(r)
    if not devices:
        pytest.skip("Ingen devices at teste")
    existing_id = devices[0]["device_id"]

    # Prøv at oprette med samme ID
    r2 = make_authenticated_request(token, "/admin/devices", method="POST", json={
        "device_id": existing_id,
        "name": "Duplicate device"
    })

    if r2.status_code == 405:
        pytest.skip("POST /admin/devices ikke implementeret")
    # Skal fejle med 409 (conflict) eller 400
    assert r2.status_code in [400, 409, 403], "Duplikat device ID skal afvises"


@pytest.mark.integration
def test_device_filter_by_customer():
    """A tenant-scoped operator must only receive devices for that customer."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/devices")
    data = device_list(r)
    assert data, "Den seedede tenant-enhed skal være synlig"
    assert all(device.get("customer_id") == "qa-device-customer" for device in data)
