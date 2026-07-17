"""
TimeLapse Pro — API Integration Tests
=======================================
Tester live API endpoints mod staging headend.
Kræver at headend kører på TIMELAPSE_TEST_BASE_URL.

Kør: pytest tests/test_api_integration.py -v
"""
import pytest
import requests
import os
from datetime import datetime, timezone

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")
DEVICE_ID = os.getenv("TIMELAPSE_TEST_DEVICE_ID", "TL-C87FF9587CA0")
SESSION = requests.Session()


@pytest.fixture(scope="module", autouse=True)
def authenticated_rnd_session():
    """Authenticate explicitly; never assume admin routes are public."""
    username = os.getenv("TIMELAPSE_TEST_USER")
    password = os.getenv("TIMELAPSE_TEST_PASSWORD")
    if not username or not password:
        pytest.skip("R&D credentials er ikke sat")
    response = SESSION.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    assert response.status_code == 200, f"R&D login fejlede: {response.status_code}"
    assert not response.json().get("mfa_required"), \
        "Brug en dedikeret, policy-godkendt testprincipal til automatiseret R&D QA"
    yield
    SESSION.post(f"{BASE_URL}/api/auth/logout", timeout=10)

def api(path, method="GET", **kwargs):
    url = f"{BASE_URL}/api{path}"
    return SESSION.request(method, url, timeout=10, **kwargs)


def age_since(value):
    """Handle both legacy naive timestamps and timezone-aware API values."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc) if parsed.tzinfo else datetime.now()
    return now - parsed

# ── Connectivity ──────────────────────────────────────────────────────────────

def test_headend_reachable():
    """Headend skal være tilgængelig."""
    r = api("/admin/devices")
    assert r.status_code == 200, f"Headend ikke tilgængelig: {r.status_code}"

# ── Device ────────────────────────────────────────────────────────────────────

def test_device_exists():
    """Test device skal eksistere i DB."""
    r = api(f"/admin/devices/{DEVICE_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["device"]["device_id"] == DEVICE_ID

def test_device_config_returned():
    """Device detail skal returnere config uden at blande den ind i device-felter."""
    r = api(f"/admin/devices/{DEVICE_ID}")
    assert r.status_code == 200
    data = r.json()
    assert "device_config" in data, \
        "FEJL: device_config mangler i device response!"
    assert isinstance(data["device_config"], dict)

def test_device_last_seen_recent():
    """Enheden skal have heartbeat inden for de seneste 24 timer."""
    from datetime import timedelta
    r = api(f"/admin/devices/{DEVICE_ID}")
    data = r.json()
    last_seen = data["device"]["last_seen"]
    assert last_seen is not None, "FEJL: last_seen er None!"
    age = age_since(last_seen)
    assert age < timedelta(hours=24), \
        f"FEJL: Ingen heartbeat i {age} — edge kører ikke!"

# ── Config ────────────────────────────────────────────────────────────────────

def test_config_endpoint():
    """Browserbrugere skal bruge den rollebeskyttede admin-config route."""
    r = api(f"/admin/devices/{DEVICE_ID}/config")
    assert r.status_code == 200
    cfg = r.json()
    assert "schedule" in cfg
    assert "camera" in cfg
    assert "sftp" in cfg

def test_config_has_device_id():
    """Config skal indeholde korrekt device_id."""
    r = api(f"/admin/devices/{DEVICE_ID}/config")
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["device"]["device_id"] == DEVICE_ID


def test_edge_config_rejects_browser_session():
    """Edge config må ikke kunne læses med en almindelig browsersession."""
    r = api(f"/config/{DEVICE_ID}")
    assert r.status_code in [401, 403]

# ── Captures ─────────────────────────────────────────────────────────────────

def test_captures_exist():
    """Der skal være captures i DB."""
    r = api(f"/admin/captures?device_id={DEVICE_ID}&limit=10")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0, "FEJL: Ingen captures i DB!"

def test_recent_captures():
    """Der skal være captures inden for de seneste 25 timer."""
    from datetime import timedelta
    r = api(f"/admin/captures?device_id={DEVICE_ID}&limit=1")
    data = r.json()
    assert len(data) > 0
    latest = data[0]["captured_at"]
    age = age_since(latest)
    assert age < timedelta(hours=25), \
        f"FEJL: Seneste capture er {age} gammel — sync fejler!"

# ── Lab endpoints ─────────────────────────────────────────────────────────────

def test_lab_set_param_endpoint():
    """set-param skal validere input uden at lægge en testkommando på Edge."""
    r = api(f"/lab/{DEVICE_ID}/set-param", method="POST",
            json={"value": "test"})
    assert r.status_code == 400, \
        f"FEJL: set-param endpoint mangler (HTTP {r.status_code})"

def test_lab_get_params_endpoint():
    """get-params endpoint skal eksistere."""
    r = api(f"/lab/{DEVICE_ID}/get-params", method="POST")
    assert r.status_code in [200, 409], \
        f"FEJL: get-params endpoint mangler (HTTP {r.status_code})"

def test_lab_params_store_endpoint():
    """Edge callback må afvise en almindelig browsersession."""
    r = api(f"/lab/{DEVICE_ID}/params", method="POST",
            json={"params": []})
    assert r.status_code in [401, 403], \
        f"FEJL: Edge-only endpoint accepterede forkert auth (HTTP {r.status_code})"

# ── Thumbnails ────────────────────────────────────────────────────────────────

def test_thumbnail_endpoint_exists():
    """Thumbnail endpoint skal eksistere."""
    r = api(f"/admin/captures?device_id={DEVICE_ID}&limit=1")
    captures = r.json()
    if captures:
        filename = captures[0]["filename"]
        r2 = SESSION.get(f"{BASE_URL}/api/thumbnails/{DEVICE_ID}/{filename}", timeout=10)
        assert r2.status_code in [200, 404], \
            f"FEJL: Thumbnail endpoint fejler med HTTP {r2.status_code}"
        if r2.status_code == 200:
            assert len(r2.content) > 1000, \
                f"FEJL: Thumbnail er for lille ({len(r2.content)} bytes) — sandsynligvis fejl!"
