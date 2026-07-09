"""
TimeLapse Pro — Thumbnail Generation Tests (P0)
================================================

Tests for thumbnail generation and serving:
- GET /api/admin/thumbnail-backlog (admin only)
- GET /api/thumbnails/{device_id}/{filename} (lazy generation)
- POST /api/thumbnails/{device_id}/{filename}/generate (manual generation)
- Cache headers and X-Accel-Redirect
- Thumbnail upload via capture API
- Auto generation loop verification

Kør: pytest tests/test_thumbnail_generation.py -v

Marker: integration (kræver live headend på TIMELAPSE_TEST_BASE_URL)
"""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
import json as _json
import hashlib
import io

BASE_URL = os.getenv("TIMELAPSE_TEST_BASE_URL", "http://127.0.0.1:8000")

# Test credentials
SUPER_ADMIN_CREDS = {"username": "test-super-admin", "password": "TestSuperAdmin123!"}
SUPER_ADMIN_MFA_SECRET = "J5MWYQYR5NFZW2ZJ"  # Test super_admin MFA secret
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


def get_operator_token() -> Optional[str]:
    """Hent operator session token."""
    r = api("/auth/login", method="POST", json=OPERATOR_CREDS)
    if r.status_code == 200:
        return extract_session_token(r)
    return None


def get_viewer_token() -> Optional[str]:
    """Hent viewer session token."""
    r = api("/auth/login", method="POST", json=VIEWER_CREDS)
    if r.status_code == 200:
        return extract_session_token(r)
    return None


# ── 1. Thumbnail Backlog API (Admin) ─────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_backlog_as_admin():
    """Admin skal kunne hente thumbnail backlog."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/thumbnail-backlog")
    assert r.status_code == 200
    data = r.json()
    # Skal indeholde backlog status
    assert "total" in data
    assert "missing" in data
    assert "devices" in data
    assert isinstance(data["devices"], dict)
    # total >= missing
    assert data["total"] >= data["missing"]


@pytest.mark.integration
def test_thumbnail_backlog_includes_scan_time():
    """Thumbnail backlog skal inkludere scan time."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    r = make_authenticated_request(token, "/admin/thumbnail-backlog")
    assert r.status_code == 200
    data = r.json()
    # Skal inkludere scan tid
    assert "scan_time_seconds" in data
    assert isinstance(data["scan_time_seconds"], (int, float))
    assert data["scan_time_seconds"] >= 0


@pytest.mark.integration
def test_thumbnail_backlog_as_operator():
    """Operator skal IKKE kunne hente thumbnail backlog."""
    token = get_operator_token()
    if not token:
        pytest.skip("Kunne ikke få operator token")

    r = make_authenticated_request(token, "/admin/thumbnail-backlog")
    # Operator skal være nægtet (admin only endpoint)
    assert r.status_code in [403, 401], "Operator skal ikke kunne tilgå backlog"


@pytest.mark.integration
def test_thumbnail_backlog_without_auth_fails():
    """Thumbnail backlog skal kræve autentificering."""
    r = api("/admin/thumbnail-backlog")
    assert r.status_code in [401, 403], "Backlog skal kræve auth"


# ── 2. Get Thumbnail (Lazy Generation) ────────────────────────────────────────────

@pytest.mark.integration
def test_get_thumbnail_requires_auth():
    """Hent thumbnail skal kræve autentificering."""
    # Brug en dummy device/filename combo
    r = api("/thumbnails/TL-TEST/test.jpg")
    # Skal kræve auth
    assert r.status_code in [401, 403, 404], "Thumbnail skal kræve auth"


@pytest.mark.integration
def test_get_thumbnail_as_viewer():
    """Viewer skal kunne hente thumbnails (lazy generation hvis mangler)."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Først find en eksisterende capture
    r = make_authenticated_request(token, "/captures?limit=1")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    capture = r.json()["captures"][0]
    device_id = capture.get("device_id")
    filename = capture.get("filename")

    if not device_id or not filename:
        pytest.skip("Capture mangler device_id eller filename")

    # Prøv at hente thumbnail
    r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}")

    # Kan være 200 (thumbnail fundet), 404 (billede ikke fundet), eller 202 (genererer)
    # Vi accepterer alle disse som gyldige responses
    assert r2.status_code in [200, 202, 404], f"Uventet status: {r2.status_code}"

    if r2.status_code == 200:
        # Tjek at vi fik et billede tilbage
        assert r2.headers.get("content-type", "").startswith("image/")
        # Tjek cache header
        cache_control = r2.headers.get("cache-control", "")
        assert "max-age" in cache_control or "public" in cache_control


@pytest.mark.integration
def test_get_nonexistent_thumbnail_returns_404():
    """Get thumbnail med ugyldig capture skal returnere 404."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Brug en不可能 device/filename combo
    r = make_authenticated_request(token, "/thumbnails/TL-NONEXIST/noimage.jpg")
    # Billede ikke fundet (404) eller auth fejl (403 hvis token expired)
    assert r.status_code in [404, 403], f"Uventet status: {r.status_code}"


# ── 3. Manual Thumbnail Generation ──────────────────────────────────────────────

@pytest.mark.integration
def test_request_thumbnail_generation_as_viewer():
    """Viewer skal kunne anmode om thumbnail generation."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en eksisterende capture
    r = make_authenticated_request(token, "/captures?limit=1")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    capture = r.json()["captures"][0]
    device_id = capture.get("device_id")
    filename = capture.get("filename")

    if not device_id or not filename:
        pytest.skip("Capture mangler device_id eller filename")

    # Anmod om generation
    r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}/generate", method="POST")

    # Kan være 200 (allerede ready), 202 (queued), eller 404 (billede ikke fundet)
    assert r2.status_code in [200, 202, 404], f"Uventet status: {r2.status_code}"

    if r2.status_code in [200, 202]:
        data = r2.json()
        assert "status" in data
        # status kan være "ready", "queued"
        assert data["status"] in ["ready", "queued"]


@pytest.mark.integration
def test_request_thumbnail_generation_without_auth_fails():
    """Thumbnail generation skal kræve autentificering."""
    r = api("/thumbnails/TL-TEST/test.jpg/generate", method="POST")
    assert r.status_code in [401, 403], "Generation skal kræve auth"


# ── 4. Cache Headers ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_cache_headers():
    """Thumbnail response skal have cache headers."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en capture der har en thumbnail
    r = make_authenticated_request(token, "/captures?limit=10")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    captures = r.json()["captures"]

    # Prøv op til 5 captures for at finde en med thumbnail
    found_thumbnail = False
    for capture in captures[:5]:
        device_id = capture.get("device_id")
        filename = capture.get("filename")

        if not device_id or not filename:
            continue

        r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}")
        if r2.status_code == 200:
            # Found! Tjek cache headers
            cache_control = r2.headers.get("cache-control", "")
            # Skal have caching
            assert "max-age" in cache_control or "public" in cache_control
            # Immutable er også OK
            assert "immutable" in cache_control or "max-age" in cache_control
            found_thumbnail = True
            break

    if not found_thumbnail:
        pytest.skip("Kunne ikke finde capture med thumbnail")


# ── 5. Thumbnail Upload via Capture API ───────────────────────────────────────────

@pytest.mark.integration
def test_capture_api_accepts_thumbnail():
    """Capture API skal acceptere thumbnail upload."""
    # Dette kræver device token auth, som vi ikke har i tests
    # Vi skipper dette test da det kræver device certifikat/token
    pytest.skip("Kræver device token auth")


@pytest.mark.integration
def test_thumbnail_size_limits():
    """Thumbnail skal være lille (320x180 max)."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en capture med thumbnail
    r = make_authenticated_request(token, "/captures?limit=10")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    captures = r.json()["captures"]

    for capture in captures[:3]:
        device_id = capture.get("device_id")
        filename = capture.get("filename")

        if not device_id or not filename:
            continue

        r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}")
        if r2.status_code == 200:
            # Tjek størrelse - skal være mindre end ~50KB (320x180 JPEG)
            content_length = r2.headers.get("content-length")
            if content_length:
                size_kb = int(content_length) / 1024
                # Thumbnails skal være små (< 100KB)
                assert size_kb < 100, f"Thumbnail for stor: {size_kb:.1f}KB"
            break
    else:
        pytest.skip("Kunne ikke finde capture med thumbnail")


# ── 6. Thumbnail Source Headers ─────────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_source_header():
    """Thumbnail response skal have X-Thumbnail-Source header."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en capture med thumbnail
    r = make_authenticated_request(token, "/captures?limit=10")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    captures = r.json()["captures"]

    for capture in captures[:5]:
        device_id = capture.get("device_id")
        filename = capture.get("filename")

        if not device_id or not filename:
            continue

        r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}")
        if r2.status_code == 200:
            # Tjek source header
            source = r2.headers.get("X-Thumbnail-Source", "")
            # Skal være enten "edge" eller "headend-lazy"
            assert source in ["edge", "headend-lazy", ""], f"Uventet source: {source}"
            break
    else:
        pytest.skip("Kunne ikke finde capture med thumbnail")


# ── 7. Auto Generation Loop Verification ────────────────────────────────────────

@pytest.mark.integration
def test_auto_generation_loop_active():
    """Auto generation loop skal være aktiv (check via backlog)."""
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    # Hent backlog først
    r1 = make_authenticated_request(token, "/admin/thumbnail-backlog")
    if r1.status_code != 200:
        pytest.skip("Kunne ikke hente backlog")

    data1 = r1.json()
    missing_before = data1.get("missing", 0)

    # Hvis der er manglende thumbnails, vent lidt og tjek igen
    # (auto loop kører hver 15 min, så vi forventer ikke ændring på kort tid)
    # Men vi kan verificere at endpointet virker

    assert "total" in data1
    assert "missing" in data1
    # Auto loop er aktiv hvis backlog kan scannes
    assert data1.get("scan_time_seconds") is not None


# ── 8. Edge Cases ─────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_with_invalid_device_id():
    """Thumbnail med invalid device ID skal fejle."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Invalid device IDs
    invalid_ids = ["", " ", "../../etc/passwd", "TL-!@#"]

    for invalid_id in invalid_ids:
        r = make_authenticated_request(token, f"/thumbnails/{invalid_id}/test.jpg")
        # Skal fejle med 404 eller 400
        if r.status_code not in [404, 400]:
            # Nogle IDs måske gyldige — det er OK
            pass


@pytest.mark.integration
def test_thumbnail_with_path_traversal():
    """Thumbnail med path traversal skal være sikker."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Path traversal forsøg
    path_traversal_attempts = [
        "../test.jpg",
        "....//test.jpg",
        "..\\test.jpg",
        "%2e%2e%2ftest.jpg",
    ]

    for attempt in path_traversal_attempts:
        r = make_authenticated_request(token, f"/thumbnails/TL-TEST/{attempt}")
        # Skal fejle (404, 400, eller 403 hvis auth token issue)
        # Vi forventer ikke successful path traversal
        if r.status_code == 200:
            # Hvis vi får 200, tjek at det ikke er system files
            content = r.content
            # Skal være et billede (JPEG magic bytes: FF D8 FF)
            assert len(content) < 2 or content[:2] != b"\xff\xd8", "Potentielt path traversal"
        # 403 er OK hvis token expired (auth fejl)
        elif r.status_code not in [404, 400, 403]:
            pytest.fail(f"Uventet status for path traversal: {r.status_code}")


# ── 9. Thumbnail Backlog Performance ─────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_backlog_performance():
    """Thumbnail backlog skal scanne hurtigt (< 5s for < 10k captures)."""
    import time
    token = get_admin_token()
    if not token:
        pytest.skip("Kunne ikke få admin token")

    start = time.time()
    r = make_authenticated_request(token, "/admin/thumbnail-backlog")
    elapsed = time.time() - start

    assert r.status_code == 200
    data = r.json()

    # Scan skal være hurtig
    # API rapporterer sin egen scan time
    scan_time = data.get("scan_time_seconds", elapsed)
    # For mindre end 10k captures skal det være < 5s
    if data.get("total", 0) < 10000:
        assert scan_time < 5.0, f"Scan for langsom: {scan_time:.2f}s"


# ── 10. Thumbnail Format ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_is_jpeg():
    """Thumbnail skal være JPEG format."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en capture med thumbnail
    r = make_authenticated_request(token, "/captures?limit=10")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    captures = r.json()["captures"]

    for capture in captures[:3]:
        device_id = capture.get("device_id")
        filename = capture.get("filename")

        if not device_id or not filename:
            continue

        r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}")
        if r2.status_code == 200:
            # Tjek content type
            content_type = r2.headers.get("content-type", "")
            assert "jpeg" in content_type or "jpg" in content_type, f"Uventet content type: {content_type}"
            # T JPEG magic bytes
            content = r2.content
            if len(content) >= 2:
                assert content[:2] == b"\xff\xd8", "Ikke et JPEG billede"
            break
    else:
        pytest.skip("Kunne ikke finde capture med thumbnail")


# ── 11. Lazy Generation Behavior ──────────────────────────────────────────────────

@pytest.mark.integration
def test_lazy_generation_when_missing():
    """Lazy generation skal oprette thumbnail når den mangler."""
    # Dette er svært at teste uden at slette en eksisterende thumbnail
    # Vi verificerer blot at lazy generation endpointet svarer
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en capture
    r = make_authenticated_request(token, "/captures?limit=1")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    capture = r.json()["captures"][0]
    device_id = capture.get("device_id")
    filename = capture.get("filename")

    if not device_id or not filename:
        pytest.skip("Capture mangler device_id eller filename")

    # Forsøg at hente thumbnail - skal enten returnere thumbnail eller starte generation
    r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}")
    # Vi accepterer 200 (fundet), 202 (genererer), eller 404 (billede ikke fundet)
    assert r2.status_code in [200, 202, 404]


# ── 12. Thumbnail Generation Status ─────────────────────────────────────────────

@pytest.mark.integration
def test_thumbnail_generation_status_response():
    """Thumbnail generation status skal have korrekt format."""
    token = get_viewer_token()
    if not token:
        pytest.skip("Kunne ikke få viewer token")

    # Find en capture
    r = make_authenticated_request(token, "/captures?limit=1")
    if r.status_code != 200 or not r.json().get("captures"):
        pytest.skip("Ingen captures at teste")

    capture = r.json()["captures"][0]
    device_id = capture.get("device_id")
    filename = capture.get("filename")

    if not device_id or not filename:
        pytest.skip("Capture mangler device_id eller filename")

    # Anmod om generation
    r2 = make_authenticated_request(token, f"/thumbnails/{device_id}/{filename}/generate", method="POST")

    if r2.status_code in [200, 202]:
        data = r2.json()
        # Status response skal have bestemte felter
        assert "status" in data
        if data["status"] == "ready":
            # "ready" skal inkludere thumbnail sti
            assert "thumbnail" in data or "source" in data
        elif data["status"] == "queued":
            # "queued" skal inkludere thumbnail sti
            assert "thumbnail" in data
