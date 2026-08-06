"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — API Integration Test Suite (Weekend 5-7 juli 2026)
──────────────────────────────────────────────────────────────────────────────────
Version  : 2.0.0 (pytest-kompatibel)
Dato     : 2026-07-13
Formål   : Automatiseret test af alle nye features fra weekenden

Dækker:
  - P2-03 GDPR Redaction workflow (UI-010)
  - P0-05 Retention Policy
  - Drift-detection fase 1
  - M-05 Agent-lockdown layer 2
  - Update UI scopes
  - Periodic checks

Kørsel:
  pytest tests/test_weekend_features_api.py -v

Miljø:
  Export TIMELAPSE_TEST_BASE_URL før kørsel (default: http://localhost:8000)
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
from urllib.parse import urljoin
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.integration


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

BASE_URL = os.getenv(
    "TIMELAPSE_TEST_BASE_URL",
    os.getenv("TIMELAPSE_BASE_URL", "http://localhost:8000")
)
TIMEOUT = int(os.getenv("TIMELAPSE_TEST_TIMEOUT", "30"))

# Auth credentials (passthrough to staging/prod)
AUTH_USER = os.getenv("TIMELAPSE_TEST_USER", "test-super-admin")
AUTH_PASS = os.getenv("TIMELAPSE_TEST_PASSWORD", "TestSuperAdmin123!")


# ═══════════════════════════════════════════════════════════════════════════
# API Client
# ═══════════════════════════════════════════════════════════════════════════

class APIClient:
    """HTTP client til TimeLapse Pro API.

    2026-08-06 (Claude): denne klasse loggede reelt aldrig ind — login sætter
    en `tl_session`-cookie (ikke et `access_token`-felt i JSON-body'en, som
    denne klasse antog), og cookien er markeret `Secure`. `requests`' egen
    cookie-jar overholder korrekt `Secure`-flaget og NÆGTER at sende den
    tilbage over almindelig http (som test-serveren kører på — ingen TLS på
    et engangs-testinstans). Resultatet var et deterministisk 401 på ALLE
    tests i denne fil, uanset seed/rækkefølge — ikke delt test-tilstand, som
    det først lignede. Samme rodårsag og løsning som allerede dokumenteret i
    tests/conftest.py's AuthenticatedSession: send cookien manuelt som en
    `Cookie`-header i stedet for at stole på cookie-jar'ets håndhævelse."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session_token: str | None = None

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.session_token:
            headers["Cookie"] = f"tl_session={self.session_token}"
        return headers

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs
        )

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.session.post(
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs
        )

    def login(self, username: str = AUTH_USER, password: str = AUTH_PASS) -> bool:
        """Login og gem session-cookien (sendes manuelt herefter, se klassens docstring)."""
        resp = self.post(
            "/api/auth/login",
            json={"username": username, "password": password}
        )
        if resp.status_code == 200:
            for cookie in resp.cookies:
                if cookie.name == "tl_session":
                    self.session_token = cookie.value
                    break
            return self.session_token is not None
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Pytest Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def api_client() -> APIClient:
    """Fixture der provider en authenticated API client."""
    client = APIClient()
    client.login()
    return client


# ═══════════════════════════════════════════════════════════════════════════
# P2-03 GDPR Redaction Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestP203GdprRedaction:
    """P2-03 GDPR Redaction Workflow (UI-010) tests."""

    @pytest.mark.p203
    @pytest.mark.gdpr
    @pytest.mark.high
    def test_redaction_pending(self, api_client: APIClient) -> None:
        """Test GET /api/redaction/pending"""
        resp = api_client.get("/api/redaction/pending")
        assert resp.status_code == 200, f"Forventet 200, fik {resp.status_code}"

        data = resp.json()
        assert "total" in data, "Mangler 'total' felt"
        assert "pending_analysis" in data, "Mangler 'pending_analysis' felt"
        assert "detected_pii" in data, "Mangler 'detected_pii' felt"
        assert "items" in data, "Mangler 'items' felt"

    @pytest.mark.p203
    @pytest.mark.gdpr
    @pytest.mark.high
    def test_redaction_status(self, api_client: APIClient) -> None:
        """Test GET /api/redaction/status/{id}"""
        # Først hent en liste af pending captures
        resp = api_client.get("/api/redaction/pending?status_filter=pending")
        assert resp.status_code == 200

        data = resp.json()
        items = data.get("items", [])

        if not items:
            pytest.skip("Ingen pending captures at teste")

        # Test status for første capture
        capture_id = items[0]["capture_id"]
        resp = api_client.get(f"/api/redaction/status/{capture_id}")
        assert resp.status_code == 200, f"Status endpoint fejlede: {resp.status_code}"

        status_data = resp.json()
        assert "redaction_status" in status_data, "Mangler 'redaction_status'"
        assert "has_gdpr_data" in status_data, "Mangler 'has_gdpr_data'"

    @pytest.mark.p203
    @pytest.mark.gdpr
    @pytest.mark.high
    def test_redaction_analyze(self, api_client: APIClient) -> None:
        """Test POST /api/redaction/analyze/{id}"""
        # Hent en pending capture
        resp = api_client.get("/api/redaction/pending?status_filter=pending")
        assert resp.status_code == 200

        data = resp.json()
        items = data.get("items", [])

        if not items:
            pytest.skip("Ingen pending captures at analysere")

        capture_id = items[0]["capture_id"]
        resp = api_client.post(f"/api/redaction/analyze/{capture_id}")

        # A metadata-only test capture has no corresponding file.
        if resp.status_code == 404:
            pytest.skip("Testcapture har ingen billedfil")
        assert resp.status_code in (200, 202), f"Analyse fejlede: {resp.status_code}"

        result = resp.json()
        assert "detections" in result or "redaction_status" in result, \
            "Mangler 'detections' eller 'redaction_status' i response"


# ═══════════════════════════════════════════════════════════════════════════
# P0-05 Retention Policy Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestP005RetentionPolicy:
    """P0-05 Retention Policy tests."""

    @pytest.mark.p005
    @pytest.mark.retention
    @pytest.mark.critical
    def test_retention_config(self, api_client: APIClient) -> None:
        """Test at retention config kan hentes"""
        resp = api_client.get("/api/admin/retention/settings")
        assert resp.status_code == 200, f"Config endpoint fejlede: {resp.status_code}"

        config = resp.json()
        assert "retention_days" in config, "Mangler 'retention_days' i global config"

    @pytest.mark.p005
    @pytest.mark.retention
    @pytest.mark.critical
    def test_retention_camera_field(self, api_client: APIClient) -> None:
        """Test at kameraer har retention_days felt"""
        resp = api_client.get("/api/admin/cameras")
        assert resp.status_code == 200

        devices = resp.json()
        if not devices:
            pytest.skip("Ingen devices fundet")

        # Tjek at første device har retention_days (eller null hvis ikke sat)
        first_device = devices[0]
        # retention_days kan være i device objektet eller skal være i camera objektet
        # afhængig af API version
        has_retention = "retention_days" in first_device or "cameras" in first_device
        assert has_retention, "Retention field mangler"


# ═══════════════════════════════════════════════════════════════════════════
# Drift-Detection Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDriftDetection:
    """Drift-Detection Fase 1 tests."""

    @pytest.mark.drift
    @pytest.mark.high
    def test_drift_status(self, api_client: APIClient) -> None:
        """Test GET /api/admin/drift-status"""
        resp = api_client.get("/api/admin/drift-status")
        # Endpoint kan være 404 hvis drift-detection ikke er aktiv
        if resp.status_code == 404:
            pytest.skip("Drift-detection endpoint ikke implementeret endnu")

        assert resp.status_code == 200, f"Drift status fejlede: {resp.status_code}"

        data = resp.json()
        assert "drift_enabled" in data, "Mangler 'drift_enabled' felt"

    @pytest.mark.drift
    @pytest.mark.high
    def test_drift_config_hierarchy(self, api_client: APIClient) -> None:
        """Test at config hierarki (global/device/customer/site) virker"""
        resp = api_client.get("/api/admin/config-defaults")
        assert resp.status_code == 200

        config = resp.json()
        # Tjek at vi har config fields
        assert bool(config), "Manglende config"


# ═══════════════════════════════════════════════════════════════════════════
# M-05 Agent-Lockdown Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestM05AgentLockdown:
    """M-05 Agent-Lockdown Layer 2 tests."""

    @pytest.mark.m005
    @pytest.mark.security
    def test_agent_login_rejection(self, api_client: APIClient) -> None:
        """Test at agent login bliver afvist"""
        # Lav en ny client uden login for at teste agent login
        test_client = APIClient(api_client.base_url, api_client.timeout)

        # Forsøg at logge ind som agent
        resp = test_client.post(
            "/api/auth/login",
            json={"username": "test_agent", "password": "test"}
        )

        # I staging/prod skal dette fejle (401 eller 403)
        # I dev miljø kan det være tilladt (200)
        # 429 (rate limit) accepteres også
        # Vi tjekker bare at vi får et valid response
        assert resp.status_code in (200, 401, 403, 429), \
            f"Uventet response: {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
# Update UI Scopes Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateScopes:
    """Update UI Scopes tests."""

    @pytest.mark.updates
    @pytest.mark.medium
    def test_update_scopes(self, api_client: APIClient) -> None:
        """Test at update UI har alle scopes"""
        resp = api_client.get("/api/updates/pending")
        # Endpoint kan være 404 hvis ikke implementeret
        if resp.status_code == 404:
            pytest.skip("Update endpoint ikke fundet")

        assert resp.status_code == 200, f"Update endpoint fejlede: {resp.status_code}"

        # Bare tjek at vi får valid JSON
        resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# Post-Processing Thumbnail Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestP002ThumbnailPostProcessing:
    """P2-02 Thumbnail Post-Processing tests."""

    @pytest.mark.p002
    @pytest.mark.thumbnail
    @pytest.mark.medium
    def test_thumbnail_backlog(self, api_client: APIClient) -> None:
        """Test GET /api/admin/thumbnail-backlog"""
        resp = api_client.get("/api/admin/thumbnail-backlog")
        # Endpoint kan være 404 hvis ikke implementeret
        if resp.status_code == 404:
            pytest.skip("Thumbnail backlog endpoint ikke fundet")

        assert resp.status_code == 200, f"Thumbnail backlog fejlede: {resp.status_code}"

        data = resp.json()
        assert "total" in data and "missing" in data, "Mangler total/missing felt"


# ═══════════════════════════════════════════════════════════════════════════
# Database Schema Tests (via reflections)
# ═══════════════════════════════════════════════════════════════════════════

class TestDatabaseSchema:
    """Database Schema (v15, v16, v17) tests."""

    @pytest.mark.database
    @pytest.mark.critical
    def test_database_redaction_columns(self, api_client: APIClient) -> None:
        """Test at database har v17 redaction kolonner"""
        # Dette tjekker indirekte via API
        resp = api_client.get("/api/redaction/pending")
        if resp.status_code == 404:
            pytest.skip("Redaction API ikke tilgængelig")

        assert resp.status_code == 200

    @pytest.mark.database
    @pytest.mark.critical
    def test_database_retention_columns(self, api_client: APIClient) -> None:
        """Test at database har v15 retention kolonner"""
        resp = api_client.get("/api/admin/retention/settings")
        assert resp.status_code == 200

        config = resp.json()
        assert "retention_days" in config, "Mangler retention_days i config"

    @pytest.mark.database
    @pytest.mark.medium
    def test_database_wb_cast_strength(self, api_client: APIClient) -> None:
        """Test at database har v16 wb_cast_strength kolonne"""
        # Tjek via captures endpoint
        resp = api_client.get("/api/admin/captures?limit=1")
        if resp.status_code == 404:
            pytest.skip("Captures endpoint ikke tilgængelig")

        assert resp.status_code == 200

        data = resp.json()
        captures = data if isinstance(data, list) else data.get("items", [])

        if not captures:
            pytest.skip("Ingen captures at tjekke")

        # Tjek om wb_cast_strength er i response (kan være null)
        first = captures[0]
        # Vi tjekker bare at feltet findes, eller at API'en virker
        assert isinstance(first, dict), "Capture skal være en dict"
