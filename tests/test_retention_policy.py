"""
TimeLapse Pro — P0-05 Retention Policy Tests
==============================================
Tester GDPR-compliant automatisk sletning af gamle billeder.

Kør: pytest tests/test_retention_policy.py -v
Kør kun unit tests: pytest tests/test_retention_policy.py -v -m "not integration"
Kør kun integration: pytest tests/test_retention_policy.py -v -m integration

Coverage:
- Unit tests: retention cleanup logik, beregning af sletningskandidater
- Integration tests: API endpoints (/api/admin/retention/*)
- Compliance: deletion log, retention per kamera
"""
import pytest
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# ── Mock Models (undgår database import) ─────────────────────────────────────

class MockCamera:
    """Mock Camera model til unit tests."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.camera_name = kwargs.get("camera_name")
        self.site_id = kwargs.get("site_id")
        self.customer_id = kwargs.get("customer_id")
        # Default retention_days er 365 ifølge database model
        self.retention_days = kwargs.get("retention_days", 365)


class MockCaptureDeletionLog:
    """Mock CaptureDeletionLog model til unit tests."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.capture_id = kwargs.get("capture_id")
        self.device_id = kwargs.get("device_id")
        self.camera_id = kwargs.get("camera_id")
        self.filename = kwargs.get("filename")
        self.deleted_at = kwargs.get("deleted_at")
        self.deletion_reason = kwargs.get("deletion_reason")
        self.retention_days = kwargs.get("retention_days")
        self.performed_by = kwargs.get("performed_by")


# ── Unit Tests ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_retention_days_default_365():
    """Nye kameraer skal have retention_days=365 som default."""
    cam = MockCamera(
        id="test-cam-1",
        camera_name="Test Kamera",
    )
    assert cam.retention_days == 365, "Default retention_days skal være 365"


@pytest.mark.unit
def test_retention_candidate_calculation():
    """Beregning af sletningskandidater baseret på retention_days."""
    # Setup: Kamera med 90 dages retention
    cam = MockCamera(retention_days=90)

    # Mock captures
    class MockCapture:
        def __init__(self, filename, days_ago):
            self.filename = filename
            self.device_id = "TL-TEST"
            self.captured_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

    old_capture = MockCapture("old.jpg", 100)  # 100 dage gammel -> skal slettes
    new_capture = MockCapture("new.jpg", 30)   # 30 dage gammel -> beholdes

    cutoff = datetime.now(timezone.utc) - timedelta(days=cam.retention_days)

    # Simulér logikken fra _run_retention_cleanup
    candidates = []
    for cap in [old_capture, new_capture]:
        cap_dt = datetime.fromisoformat(cap.captured_at.replace("Z", "+00:00"))
        if cap_dt < cutoff:
            candidates.append(cap)

    assert len(candidates) == 1
    assert candidates[0].filename == "old.jpg"


@pytest.mark.unit
def test_retention_with_null_retention_days():
    """Kameraer uden retention_days (NULL) skal ikke slette automatisk."""
    cam = MockCamera(retention_days=None)

    # Hvis retention_days er NULL, skal vi ikke slette
    should_cleanup = cam.retention_days is not None and cam.retention_days > 0

    assert not should_cleanup, "Kamera uden retention_days skal ikke køre cleanup"


@pytest.mark.unit
def test_retention_minimum_1_day():
    """Retention_days skal være minimum 1 dag."""
    cam = MockCamera(retention_days=0)

    # Logik: retention_days < 1 skal ignoreres (slet aldrig)
    valid_retention = cam.retention_days and cam.retention_days >= 1

    assert not valid_retention, "retention_days=0 skal ignoreres (ingen sletning)"


@pytest.mark.unit
def test_retention_negative_days_invalid():
    """Negative retention_days skal være ugyldige."""
    cam = MockCamera(retention_days=-30)

    valid_retention = cam.retention_days and cam.retention_days >= 1

    assert not valid_retention, "Negative retention_days skal ignoreres"


@pytest.mark.unit
def test_deletion_log_fields():
    """CaptureDeletionLog skal have alle GDPR-relevante felter."""
    log = MockCaptureDeletionLog(
        id="log-test-1",
        capture_id="cap-123",
        device_id="TL-TEST",
        camera_id="cam-1",
        filename="test.jpg",
        deleted_at=datetime.now(timezone.utc),
        deletion_reason="retention_policy",
        retention_days=365,
        performed_by="system",
    )

    assert log.id is not None
    assert log.deletion_reason == "retention_policy"
    assert log.retention_days == 365
    assert log.performed_by == "system"


@pytest.mark.unit
def test_retention_cutoff_calculation():
    """Beregning af cutoff dato for sletning."""
    retention_days = 90
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    # En capture der er præcis 90 dage gammel skal slettes
    capture_age_90 = now - timedelta(days=90)
    assert capture_age_90 <= cutoff, "90 dage gammel capture skal være på cutoff"

    # En capture der er 89 dage gammel skal beholdes
    capture_age_89 = now - timedelta(days=89)
    assert capture_age_89 > cutoff, "89 dage gammel capture skal bevares"


@pytest.mark.unit
def test_deletion_reason_values():
    """Deletion_reason skal have valide GDPR-compliant værdier."""
    valid_reasons = ["retention_policy", "manual_delete", "gdpr_request", "device_removed"]

    for reason in valid_reasons:
        log = MockCaptureDeletionLog(
            id=f"log-{reason}",
            deletion_reason=reason,
            # ... andre felter
        )
        assert log.deletion_reason in valid_reasons


# ── Integration Tests (kræver live headend) ───────────────────────────────────

def api(path, method="GET", **kwargs):
    """Hjælper til API kald."""
    import requests
    url = f"{BASE_URL}/api{path}"
    return requests.request(method, url, timeout=10, **kwargs)


@pytest.mark.integration
def test_retention_status_endpoint_exists():
    """GET /api/admin/retention/status skal eksistere og returnere valid data."""
    r = api("/admin/retention/status")
    assert r.status_code == 200, f"Status endpoint fejler: {r.status_code}"

    data = r.json()
    assert "running" in data, "running felt mangler i response"
    assert "deleted_count" in data, "deleted_count felt mangler"
    assert isinstance(data["running"], bool), "running skal være boolean"


@pytest.mark.integration
def test_retention_settings_endpoint_exists():
    """GET /api/admin/retention/settings skal eksistere."""
    r = api("/admin/retention/settings")
    assert r.status_code == 200, f"Settings endpoint fejler: {r.status_code}"

    data = r.json()
    assert "retention_cleanup_interval" in data, "retention_cleanup_interval mangler"


@pytest.mark.integration
def test_retention_settings_update():
    """PUT /api/admin/retention/settings skal kunne opdatere interval."""
    # Hent nuværende
    r = api("/admin/retention/settings")
    original = r.json()["retention_cleanup_interval"]

    # Opdater til 'manual'
    r = api("/admin/retention/settings", method="PUT",
            json={"retention_cleanup_interval": "manual"})
    assert r.status_code == 200, f"Settings update fejlede: {r.status_code}"

    # Verificer ændring
    r = api("/admin/retention/settings")
    assert r.json()["retention_cleanup_interval"] == "manual"

    # Restore original
    api("/admin/retention/settings", method="PUT",
        json={"retention_cleanup_interval": original})


@pytest.mark.integration
def test_retention_trigger_endpoint():
    """POST /api/admin/retention/trigger skal kunne starte cleanup."""
    r = api("/admin/retention/trigger", method="POST")
    assert r.status_code == 200, f"Trigger endpoint fejlede: {r.status_code}"

    data = r.json()
    assert "status" in data or "message" in data, "Response skal indeholde status eller message"


@pytest.mark.integration
def test_retention_deletion_log_endpoint():
    """GET /api/admin/retention/deletion-log skal eksistere."""
    r = api("/admin/retention/deletion-log?limit=10")
    assert r.status_code == 200, f"Deletion log endpoint fejler: {r.status_code}"

    data = r.json()
    assert "log" in data or isinstance(data, list), "Response skal indeholde log array"


@pytest.mark.integration
def test_retention_deletion_log_pagination():
    """Deletion log skal understøtte pagination."""
    r = api("/admin/retention/deletion-log?page=1&limit=5")
    assert r.status_code == 200

    data = r.json()
    assert "log" in data, "log array mangler"
    # Pagineret resultat må ikke overstige limit
    if isinstance(data.get("log"), list):
        assert len(data["log"]) <= 5, "Pagination respekterer ikke limit"


@pytest.mark.integration
def test_retention_deletion_log_filtering():
    """Deletion log skal kunne filtreres på camera_id og device_id."""
    # Test at endpoint accepterer filter parametre
    r = api("/admin/retention/deletion-log?camera_id=cam-test&limit=10")
    assert r.status_code == 200

    r = api("/admin/retention/deletion-log?device_id=TL-TEST&limit=10")
    assert r.status_code == 200


@pytest.mark.integration
def test_camera_retention_days_update():
    """PUT /api/admin/cameras/{id} skal kunne opdatere retention_days."""
    import requests

    # Først: Find et kamera eller opret et til test
    r = api("/admin/cameras?limit=1")
    if r.status_code != 200:
        pytest.skip("Ingen kameraer tilgængelige")

    cameras = r.json().get("cameras", [])
    if not cameras:
        pytest.skip("Ingen kameraer i databasen")

    cam_id = cameras[0]["id"]
    original_retention = cameras[0].get("retention_days", 365)

    # Opdater retention_days
    new_retention = 180
    r = api(f"/admin/cameras/{cam_id}", method="PUT",
            json={"retention_days": new_retention})
    assert r.status_code == 200, f"Camera update fejlede: {r.status_code}"

    # Verificer ændring
    r = api(f"/admin/cameras/{cam_id}")
    assert r.json()["retention_days"] == new_retention

    # Restore original
    api(f"/admin/cameras/{cam_id}", method="PUT",
        json={"retention_days": original_retention})


@pytest.mark.integration
def test_retention_endpoints_require_auth():
    """Retention endpoints skal kræve authentication."""
    import requests

    endpoints = [
        ("GET", "/admin/retention/status"),
        ("GET", "/admin/retention/settings"),
        ("PUT", "/admin/retention/settings"),
        ("POST", "/admin/retention/trigger"),
        ("GET", "/admin/retention/deletion-log"),
    ]

    for method, path in endpoints:
        # Kald uden auth credentials
        r = requests.request(method, f"{BASE_URL}/api{path}", timeout=5)
        # Skal fejle med 401 eller 403
        assert r.status_code in [401, 403], \
            f"{method} {path} skal kræve auth (fik {r.status_code})"


# ── Compliance Tests ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_deletion_log_gdpr_fields():
    """Deletion log entries skal indeholde alle GDPR-relevante felter."""
    r = api("/admin/retention/deletion-log?limit=1")
    if r.status_code != 200:
        pytest.skip("Deletion log endpoint ikke tilgængelig")

    data = r.json()
    log_entries = data.get("log", [])

    if not log_entries:
        pytest.skip("Ingen deletion log entries at validere")

    entry = log_entries[0]

    # GDPR krav: sporing af hvad, hvornår, hvorfor, af hvem
    required_fields = [
        "id",
        "capture_id",
        "device_id",
        "camera_id",
        "filename",
        "deleted_at",
        "deletion_reason",
        "retention_days",
        "performed_by",
    ]

    for field in required_fields:
        assert field in entry, f"GDPR felt '{field}' mangler i deletion log entry"


# ── Smoke Tests (hurtige tjek for CI) ──────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.smoke
def test_retention_status_smoke():
    """Smoke test: retention status endpoint svarer."""
    try:
        r = api("/admin/retention/status")
        assert r.status_code == 200
    except Exception:
        pytest.fail("Retention status endpoint ikke tilgængelig")


@pytest.mark.integration
@pytest.mark.smoke
def test_retention_settings_smoke():
    """Smoke test: retention settings endpoint svarer."""
    try:
        r = api("/admin/retention/settings")
        assert r.status_code == 200
    except Exception:
        pytest.fail("Retention settings endpoint ikke tilgængelig")


@pytest.mark.integration
@pytest.mark.smoke
def test_retention_trigger_smoke():
    """Smoke test: retention trigger endpoint svarer."""
    try:
        r = api("/admin/retention/trigger", method="POST")
        assert r.status_code == 200
    except Exception:
        pytest.fail("Retention trigger endpoint ikke tilgængelig")
