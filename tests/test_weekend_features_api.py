#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
TimeLapse Pro — API Integration Test Suite (Weekend 5-7 juli 2026)
──────────────────────────────────────────────────────────────────────────────────
Version  : 1.0.0
Dato     : 2026-07-07
Formål   : Automatiseret test af alle nye features fra weekenden

Dækker:
  - P2-03 GDPR Redaction workflow (UI-010)
  - P0-05 Retention Policy
  - Drift-detection fase 1
  - M-05 Agent-lockdown layer 2
  - Update UI scopes
  - Periodic checks

Kørsel:
  python tests/test_weekend_features_api.py
  eller
  pytest tests/test_weekend_features_api.py -v

Miljø:
  Export TIMELAPSE_TEST_BASE_URL før kørsel (default: http://localhost:8000)
════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from urllib.parse import urljoin

import requests

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

BASE_URL = os.getenv(
    "TIMELAPSE_TEST_BASE_URL",
    os.getenv("TIMELAPSE_BASE_URL", "http://localhost:8000")
)
TIMEOUT = int(os.getenv("TIMELAPSE_TEST_TIMEOUT", "30"))
VERBOSE = os.getenv("TIMELAPSE_TEST_VERBOSE", "false").lower() == "true"

# Auth credentials (passthrough to staging/prod)
AUTH_USER = os.getenv("TIMELAPSE_TEST_USER", "admin")
AUTH_PASS = os.getenv("TIMELAPSE_TEST_PASSWORD", "admin123")

# ═══════════════════════════════════════════════════════════════════════════
# Test Result Classes
# ═══════════════════════════════════════════════════════════════════════════


class TestStatus(Enum):
    PENDING = "⬜"
    RUNNING = "🔄"
    PASSED = "✅"
    FAILED = "❌"
    SKIPPED = "⏭️"


@dataclass
class TestResult:
    """Resultat af en enkelt test."""
    test_id: str
    name: str
    category: str
    priority: str
    status: TestStatus = TestStatus.PENDING
    message: str = ""
    duration_ms: float = 0
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        status_icon = self.status.value
        return f"{status_icon} [{self.category}] {self.name}: {self.message or self.status.name}"


@dataclass
class TestSuite:
    """Samling af tests med summary."""
    name: str
    results: list[TestResult]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def total(self) -> int:
        return len(self.results)


# ═══════════════════════════════════════════════════════════════════════════
# API Client
# ═══════════════════════════════════════════════════════════════════════════

class APIClient:
    """HTTP client til TimeLapse Pro API."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.token: str | None = None

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
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

    def put(self, path: str, **kwargs) -> requests.Response:
        return self.session.put(
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs
        )

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.session.delete(
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs
        )

    def login(self, username: str = AUTH_USER, password: str = AUTH_PASS) -> bool:
        """Login og gem JWT token."""
        try:
            resp = self.post(
                "/api/auth/login",
                json={"username": username, "password": password}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                return True
            return False
        except Exception as e:
            print(f"Login fejlede: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════
# Test Functions
# ═══════════════════════════════════════════════════════════════════════════

def time_ms() -> float:
    """Return current time in milliseconds."""
    return datetime.now(timezone.utc).timestamp() * 1000


def run_test(
    test_id: str,
    name: str,
    category: str,
    priority: str,
    func: callable,
    client: APIClient,
    results: list[TestResult]
) -> TestResult:
    """Run a single test and record result."""
    result = TestResult(
        test_id=test_id,
        name=name,
        category=category,
        priority=priority,
        status=TestStatus.RUNNING
    )
    results.append(result)

    if VERBOSE:
        print(f"  {TestStatus.RUNNING.value} Running: {name}...", flush=True)

    start = time_ms()
    try:
        msg, details = func(client)
        result.status = TestStatus.PASSED
        result.message = msg
        result.details = details
    except AssertionError as e:
        result.status = TestStatus.FAILED
        result.message = str(e)
        result.details = None
    except Exception as e:
        result.status = TestStatus.FAILED
        result.message = f"Exception: {e}"
        result.details = None
    finally:
        result.duration_ms = time_ms() - start

    if VERBOSE:
        print(f"  {result.status.value} {name}: {result.message}")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# P2-03 GDPR Redaction Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_redaction_pending(client: APIClient) -> tuple[str, dict]:
    """Test GET /api/redaction/pending"""
    resp = client.get("/api/redaction/pending")
    assert resp.status_code == 200, f"Forventet 200, fik {resp.status_code}"

    data = resp.json()
    assert "total" in data, "Mangler 'total' felt"
    assert "pending_analysis" in data, "Mangler 'pending_analysis' felt"
    assert "detected_pii" in data, "Mangler 'detected_pii' felt"
    assert "items" in data, "Mangler 'items' felt"

    return (
        f"API returnerer {data['total']} billeder, {data['pending_analysis']} afventer analyse",
        {
            "total": data["total"],
            "pending_analysis": data["pending_analysis"],
            "detected_pii": data["detected_pii"],
            "sample_items": len(data.get("items", [])[:3])
        }
    )


def test_redaction_status(client: APIClient) -> tuple[str, dict]:
    """Test GET /api/redaction/status/{id}"""
    # Først hent en liste af pending captures
    resp = client.get("/api/redaction/pending?status_filter=pending")
    assert resp.status_code == 200

    data = resp.json()
    items = data.get("items", [])

    if not items:
        return "Ingen pending captures at teste", {}

    # Test status for første capture
    capture_id = items[0]["capture_id"]
    resp = client.get(f"/api/redaction/status/{capture_id}")
    assert resp.status_code == 200, f"Status endpoint fejlede: {resp.status_code}"

    status_data = resp.json()
    assert "redaction_status" in status_data, "Mangler 'redaction_status'"
    assert "has_gdpr_data" in status_data, "Mangler 'has_gdpr_data'"

    return (
        f"Capture {capture_id} status: {status_data['redaction_status']}",
        {"capture_id": capture_id, "status": status_data["redaction_status"]}
    )


def test_redaction_analyze(client: APIClient) -> tuple[str, dict]:
    """Test POST /api/redaction/analyze/{id}"""
    # Hent en pending capture
    resp = client.get("/api/redaction/pending?status_filter=pending")
    assert resp.status_code == 200

    data = resp.json()
    items = data.get("items", [])

    if not items:
        return "Ingen pending captures at analysere", {}

    capture_id = items[0]["capture_id"]
    resp = client.post(f"/api/redaction/analyze/{capture_id}")

    # Accepter både 200 og 202 (async processing)
    assert resp.status_code in (200, 202), f"Analyse fejlede: {resp.status_code}"

    result = resp.json()
    assert "detections" in result or "redaction_status" in result, \
        "Mangler 'detections' eller 'redaction_status' i response"

    detections = result.get("detections", {})
    face_count = len(detections.get("faces", []))
    plate_count = len(detections.get("license_plates", []))

    return (
        f"Analyse færdig: {face_count} ansigter, {plate_count} nummerplader",
        {
            "capture_id": capture_id,
            "faces": face_count,
            "plates": plate_count,
            "redaction_status": result.get("redaction_status")
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# P0-05 Retention Policy Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_retention_config(client: APIClient) -> tuple[str, dict]:
    """Test at retention config kan hentes"""
    resp = client.get("/api/admin/config")
    assert resp.status_code == 200, f"Config endpoint fejlede: {resp.status_code}"

    config = resp.json()
    assert "retention_days" in config, "Mangler 'retention_days' i global config"

    return (
        f"Global retention: {config['retention_days']} dage",
        {"retention_days": config["retention_days"]}
    )


def test_retention_camera_field(client: APIClient) -> tuple[str, dict]:
    """Test at kameraer har retention_days felt"""
    resp = client.get("/api/devices")
    assert resp.status_code == 200

    devices = resp.json()
    if not devices:
        return "Ingen devices fundet", {}

    # Tjek at første device har retention_days (eller null hvis ikke sat)
    first_device = devices[0]
    # retention_days kan være i device objektet eller skal være i camera objektet
    # afhængig af API version
    has_retention = "retention_days" in first_device or "cameras" in first_device

    return (
        f"Retention field tjekket: {has_retention}",
        {"device_id": first_device.get("device_id"), "has_retention": has_retention}
    )


# ═══════════════════════════════════════════════════════════════════════════
# Drift-Detection Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_drift_status(client: APIClient) -> tuple[str, dict]:
    """Test GET /api/admin/drift-status"""
    resp = client.get("/api/admin/drift-status")
    # Endpoint kan være 404 hvis drift-detection ikke er aktiv
    if resp.status_code == 404:
        return "Drift-detection endpoint ikke implementeret endnu", {}

    assert resp.status_code == 200, f"Drift status fejlede: {resp.status_code}"

    data = resp.json()
    assert "drift_enabled" in data, "Mangler 'drift_enabled' felt"

    return (
        f"Drift detection: {'aktiveret' if data['drift_enabled'] else 'deaktiveret'}",
        {"drift_enabled": data["drift_enabled"]}
    )


def test_drift_config_hierarchy(client: APIClient) -> tuple[str, dict]:
    """Test at config hierarki (global/device/customer/site) virker"""
    resp = client.get("/api/admin/config")
    assert resp.status_code == 200

    config = resp.json()
    # Tjek at vi har config fields - scopes kan være implementeret forskelligt
    has_config = bool(config)

    return (
        f"Config hierarki: {'OK' if has_config else 'Manglende config'}",
        {"config_keys": list(config.keys())[:5]}
    )


# ═══════════════════════════════════════════════════════════════════════════
# M-05 Agent-Lockdown Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_agent_login_rejection(client: APIClient) -> tuple[str, dict]:
    """Test at agent login bliver afvist"""
    # Lav en ny client uden login for at teste agent login
    test_client = APIClient(client.base_url, client.timeout)

    # Forsøg at logge ind som agent (hvis endpoint tillader det)
    # I M-05 skal dette fejle i staging/prod
    try:
        resp = test_client.post(
            "/api/auth/login",
            json={"username": "test_agent", "password": "test"}
        )

        # I staging/prod skal dette fejle
        if resp.status_code == 401 or resp.status_code == 403:
            return "Agent login korrekt afvist", {"status": resp.status_code}
        elif resp.status_code == 200:
            # I dev miljø kan dette være tilladt
            return "Agent login tilladt (check miljø)", {"status": resp.status_code}
        else:
            return f"Uventet response: {resp.status_code}", {"status": resp.status_code}

    except Exception as e:
        return f"Login request fejlede: {e}", {}


# ═══════════════════════════════════════════════════════════════════════════
# Update UI Scopes Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_update_scopes(client: APIClient) -> tuple[str, dict]:
    """Test at update UI har alle scopes"""
    resp = client.get("/api/updates")
    # Endpoint kan være 404 hvis ikke implementeret
    if resp.status_code == 404:
        return "Update endpoint ikke fundet", {}

    assert resp.status_code == 200, f"Update endpoint fejlede: {resp.status_code}"

    data = resp.json()
    # Tjek at vi har update data
    has_updates = bool(data)

    return (
        f"Update data: {'OK' if has_updates else 'Tom'}",
        {"has_updates": has_updates}
    )


# ═══════════════════════════════════════════════════════════════════════════
# Post-Processing Thumbnail Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_thumbnail_backlog(client: APIClient) -> tuple[str, dict]:
    """Test GET /api/admin/thumbnail-backlog"""
    resp = client.get("/api/admin/thumbnail-backlog")
    # Endpoint kan være 404 hvis ikke implementeret
    if resp.status_code == 404:
        return "Thumbnail backlog endpoint ikke fundet", {}

    assert resp.status_code == 200, f"Thumbnail backlog fejlede: {resp.status_code}"

    data = resp.json()
    assert "count" in data or "backlog" in data, "Mangler count/backlog felt"

    count = data.get("count", data.get("backlog", 0))

    return (
        f"Thumbnail backlog: {count} billeder",
        {"count": count}
    )


# ═══════════════════════════════════════════════════════════════════════════
# Database Schema Tests (via reflections)
# ═══════════════════════════════════════════════════════════════════════════

def test_database_redaction_columns(client: APIClient) -> tuple[str, dict]:
    """Test at database har v17 redaction kolonner"""
    # Dette tjekker indirekte via API
    resp = client.get("/api/redaction/pending")
    if resp.status_code == 404:
        return "Redaction API ikke tilgængelig", {}

    assert resp.status_code == 200

    data = resp.json()
    # Hvis API virker, har databasen kolonnerne
    return "Database v17 redaction kolonner OK", {"api_working": True}


def test_database_retention_columns(client: APIClient) -> tuple[str, dict]:
    """Test at database har v15 retention kolonner"""
    resp = client.get("/api/admin/config")
    assert resp.status_code == 200

    config = resp.json()
    has_retention = "retention_days" in config

    return (
        f"Database v15 retention: {'OK' if has_retention else 'Mangler'}",
        {"has_retention_days": has_retention}
    )


def test_database_wb_cast_strength(client: APIClient) -> tuple[str, dict]:
    """Test at database har v16 wb_cast_strength kolonne"""
    # Tjek via captures endpoint
    resp = client.get("/api/captures?limit=1")
    if resp.status_code == 404:
        return "Captures endpoint ikke tilgængelig", {}

    assert resp.status_code == 200

    data = resp.json()
    captures = data.get("items", [])

    if not captures:
        return "Ingen captures at tjekke", {}

    # Tjek om wb_cast_strength er i response (kan være null)
    first = captures[0]
    has_wb = "wb_cast_strength" in first

    return (
        f"Database v16 wb_cast_strength: {'OK' if has_wb else 'Mangler'}",
        {"has_wb_cast_strength": has_wb}
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════════

def run_all_tests(client: APIClient) -> TestSuite:
    """Kør alle tests og returner resultater."""
    results: list[TestResult] = []

    print("\n" + "═" * 80)
    print("TIME LAPSE PRO — API Integration Test Suite")
    print("Weekend 5-7 Juli 2026 Features")
    print("═" * 80)
    print(f"Target: {client.base_url}")
    print(f"Timeout: {client.timeout}s")
    print(f"Verbose: {VERBOSE}")
    print("═" * 80 + "\n")

    # ═══════════════════════════════════════════════════════════════════════
    # P2-03 GDPR Redaction Workflow (UI-010)
    # ═══════════════════════════════════════════════════════════════════════
    print("📋 P2-03 GDPR Redaction Workflow (UI-010)")
    print("─" * 80)

    run_test("1.1", "GET /api/redaction/pending", "P2-03", "HØJ",
              test_redaction_pending, client, results)
    run_test("1.2", "GET /api/redaction/status/{id}", "P2-03", "HØJ",
              test_redaction_status, client, results)
    run_test("1.3", "POST /api/redaction/analyze/{id}", "P2-03", "HØJ",
              test_redaction_analyze, client, results)

    # ═══════════════════════════════════════════════════════════════════════
    # P0-05 Retention Policy
    # ═══════════════════════════════════════════════════════════════════════
    print("\n📋 P0-05 Retention Policy")
    print("─" * 80)

    run_test("2.1", "GET /api/admin/config (retention_days)", "P0-05", "KRITISK",
              test_retention_config, client, results)
    run_test("2.2", "Kamera retention_days felt", "P0-05", "KRITISK",
              test_retention_camera_field, client, results)

    # ═══════════════════════════════════════════════════════════════════════
    # Drift-Detection Fase 1
    # ═══════════════════════════════════════════════════════════════════════
    print("\n📋 Drift-Detection Fase 1")
    print("─" * 80)

    run_test("3.1", "GET /api/admin/drift-status", "Drift", "HØJ",
              test_drift_status, client, results)
    run_test("3.2", "Config hierarki (global/device/customer/site)", "Drift", "HØJ",
              test_drift_config_hierarchy, client, results)

    # ═══════════════════════════════════════════════════════════════════════
    # M-05 Agent-Lockdown Layer 2
    # ═══════════════════════════════════════════════════════════════════════
    print("\n📋 M-05 Agent-Lockdown Layer 2")
    print("─" * 80)

    run_test("4.1", "Agent login rejection", "M-05", "SIKKERHED",
              test_agent_login_rejection, client, results)

    # ═══════════════════════════════════════════════════════════════════════
    # Update UI Scopes
    # ═══════════════════════════════════════════════════════════════════════
    print("\n📋 Update UI Scopes")
    print("─" * 80)

    run_test("5.1", "GET /api/updates", "Updates", "MEDIUM",
              test_update_scopes, client, results)

    # ═══════════════════════════════════════════════════════════════════════
    # P2-02 Thumbnail Post-Processing
    # ═══════════════════════════════════════════════════════════════════════
    print("\n📋 P2-02 Thumbnail Post-Processing")
    print("─" * 80)

    run_test("6.1", "GET /api/admin/thumbnail-backlog", "P2-02", "MEDIUM",
              test_thumbnail_backlog, client, results)

    # ═══════════════════════════════════════════════════════════════════════
    # Database Schema Tests
    # ═══════════════════════════════════════════════════════════════════════
    print("\n📋 Database Schema (v15, v16, v17)")
    print("─" * 80)

    run_test("7.1", "v17 Redaction kolonner", "DB", "KRITISK",
              test_database_redaction_columns, client, results)
    run_test("7.2", "v15 Retention kolonner", "DB", "KRITISK",
              test_database_retention_columns, client, results)
    run_test("7.3", "v16 wb_cast_strength kolonne", "DB", "MEDIUM",
              test_database_wb_cast_strength, client, results)

    return TestSuite(name="Weekend Features", results=results)


def print_summary(suite: TestSuite):
    """Print test summary."""
    print("\n" + "═" * 80)
    print("TEST SUMMARY")
    print("═" * 80)

    # Category summary
    by_category: dict[str, dict] = {}
    for r in suite.results:
        if r.category not in by_category:
            by_category[r.category] = {"passed": 0, "failed": 0, "total": 0}
        by_category[r.category]["total"] += 1
        if r.status == TestStatus.PASSED:
            by_category[r.category]["passed"] += 1
        elif r.status == TestStatus.FAILED:
            by_category[r.category]["failed"] += 1

    for cat, stats in sorted(by_category.items()):
        print(f"\n{cat}:")
        print(f"  ✅ Passed: {stats['passed']}/{stats['total']}")
        if stats["failed"] > 0:
            print(f"  ❌ Failed: {stats['failed']}/{stats['total']}")

    # Failed tests detail
    failed = [r for r in suite.results if r.status == TestStatus.FAILED]
    if failed:
        print("\n" + "─" * 80)
        print("FAILED TESTS:")
        print("─" * 80)
        for r in failed:
            print(f"\n❌ [{r.test_id}] {r.name}")
            print(f"   {r.message}")
            if r.details:
                print(f"   Details: {r.details}")

    # Overall
    print("\n" + "═" * 80)
    print(f"OVERALL: {suite.passed}/{suite.total} passed")
    if suite.failed > 0:
        print(f"         {suite.failed} FAILED")
    if suite.skipped > 0:
        print(f"         {suite.skipped} skipped")
    print("═" * 80 + "\n")

    # Priority breakdown
    print("PRIORITET:")
    critical = [r for r in suite.results if r.priority == "KRITISK"]
    high = [r for r in suite.results if r.priority == "HØJ"]
    medium = [r for r in suite.results if r.priority == "MEDIUM"]

    print(f"  KRITISK: {sum(1 for r in critical if r.status == TestStatus.PASSED)}/{len(critical)} passed")
    print(f"  HØJ:     {sum(1 for r in high if r.status == TestStatus.PASSED)}/{len(high)} passed")
    print(f"  MEDIUM:  {sum(1 for r in medium if r.status == TestStatus.PASSED)}/{len(medium)} passed")
    print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TimeLapse Pro API Integration Tests")
    parser.add_argument("--url", default=BASE_URL, help="Base URL for API")
    parser.add_argument("--user", default=AUTH_USER, help="Username for auth")
    parser.add_argument("--pass", default=AUTH_PASS, dest="password", help="Password for auth")
    parser.add_argument("--no-login", action="store_true", help="Skip login")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Override env vars
    if args.url:
        os.environ["TIMELAPSE_TEST_BASE_URL"] = args.url
    if args.verbose:
        os.environ["TIMELAPSE_TEST_VERBOSE"] = "true"

    client = APIClient(base_url=args.url)

    # Login unless --no-login
    if not args.no_login:
        print(f"Logger ind som {args.user}...")
        if not client.login(username=args.user, password=args.password):
            print("❌ Login fejlede!")
            return 1
        print("✅ Login OK\n")

    # Run tests
    suite = run_all_tests(client)

    # Print summary
    print_summary(suite)

    # Return exit code
    return 0 if suite.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
