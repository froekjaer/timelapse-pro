"""
TimeLapse Pro — API Integration Tests
=======================================
Tester live API endpoints mod staging headend.
Kræver at headend kører på 192.168.86.132:8000

Kør: pytest tests/test_api_integration.py -v
"""
import pytest
import requests

BASE_URL = "http://192.168.86.132:8000"
DEVICE_ID = "TL-C87FF9587CA0"

def api(path, method="GET", **kwargs):
    url = f"{BASE_URL}/api{path}"
    return requests.request(method, url, timeout=10, **kwargs)

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
    """device_config skal returneres i device response."""
    r = api(f"/admin/devices/{DEVICE_ID}")
    data = r.json()
    assert "device_config" in data["device"], \
        "FEJL: device_config mangler i device response!"
    assert data["device"]["device_config"] is not None

def test_device_last_seen_recent():
    """Enheden skal have heartbeat inden for de seneste 24 timer."""
    from datetime import datetime, timezone, timedelta
    r = api(f"/admin/devices/{DEVICE_ID}")
    data = r.json()
    last_seen = data["device"]["last_seen"]
    assert last_seen is not None, "FEJL: last_seen er None!"
    last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - last_seen_dt
    assert age < timedelta(hours=24), \
        f"FEJL: Ingen heartbeat i {age} — edge kører ikke!"

# ── Config ────────────────────────────────────────────────────────────────────

def test_config_endpoint():
    """Config endpoint skal returnere valid config."""
    r = api(f"/config/{DEVICE_ID}")
    assert r.status_code == 200
    cfg = r.json()
    assert "schedule" in cfg
    assert "camera" in cfg
    assert "sftp" in cfg

def test_config_has_device_id():
    """Config skal indeholde korrekt device_id."""
    r = api(f"/config/{DEVICE_ID}")
    cfg = r.json()
    assert cfg["device"]["device_id"] == DEVICE_ID

# ── Captures ─────────────────────────────────────────────────────────────────

def test_captures_exist():
    """Der skal være captures i DB."""
    r = api(f"/admin/captures?device_id={DEVICE_ID}&limit=10")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0, "FEJL: Ingen captures i DB!"

def test_recent_captures():
    """Der skal være captures inden for de seneste 25 timer."""
    from datetime import datetime, timezone, timedelta
    r = api(f"/admin/captures?device_id={DEVICE_ID}&limit=1")
    data = r.json()
    assert len(data) > 0
    latest = data[0]["captured_at"]
    latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - latest_dt
    assert age < timedelta(hours=25), \
        f"FEJL: Seneste capture er {age} gammel — sync fejler!"

# ── Lab endpoints ─────────────────────────────────────────────────────────────

def test_lab_set_param_endpoint():
    """set-param endpoint skal eksistere."""
    r = api(f"/lab/{DEVICE_ID}/set-param", method="POST",
            json={"key": "test", "value": "test"})
    assert r.status_code in [200, 400], \
        f"FEJL: set-param endpoint mangler (HTTP {r.status_code})"

def test_lab_get_params_endpoint():
    """get-params endpoint skal eksistere."""
    r = api(f"/lab/{DEVICE_ID}/get-params", method="POST")
    assert r.status_code == 200, \
        f"FEJL: get-params endpoint mangler (HTTP {r.status_code})"

def test_lab_params_store_endpoint():
    """params store endpoint skal eksistere."""
    r = api(f"/lab/{DEVICE_ID}/params", method="POST",
            json={"params": []})
    assert r.status_code == 200, \
        f"FEJL: /api/lab/params endpoint mangler (HTTP {r.status_code})"

# ── Thumbnails ────────────────────────────────────────────────────────────────

def test_thumbnail_endpoint_exists():
    """Thumbnail endpoint skal eksistere."""
    r = api(f"/admin/captures?device_id={DEVICE_ID}&limit=1")
    captures = r.json()
    if captures:
        filename = captures[0]["filename"]
        r2 = requests.get(f"{BASE_URL}/api/thumbnails/{DEVICE_ID}/{filename}", timeout=10)
        assert r2.status_code in [200, 404], \
            f"FEJL: Thumbnail endpoint fejler med HTTP {r2.status_code}"
        if r2.status_code == 200:
            assert len(r2.content) > 1000, \
                f"FEJL: Thumbnail er for lille ({len(r2.content)} bytes) — sandsynligvis fejl!"

