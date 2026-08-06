from pathlib import Path


ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text()
API = (ROOT / "headend" / "api" / "capture_access_api.py").read_text()
# 2026-08-06 (Claude): get_thumbnail() moved to its own module during the
# thumbnail-subsystem extraction (see tests/test_architecture_ratchet.py).
THUMBNAILS_API = (ROOT / "headend" / "api" / "thumbnails_api.py").read_text()


def test_thumbnail_views_are_audited_without_public_cache() -> None:
    start = THUMBNAILS_API.index('def get_thumbnail(')
    section = THUMBNAILS_API[start:start + 1800]
    assert "_log_capture_access_deduplicated" in section
    assert 'action="thumbnail_view"' in section
    assert '"private, max-age=' in section
    assert '"public, max-age=' not in section


def test_access_log_uses_capture_tenant() -> None:
    start = MAIN.index("def _log_capture_access(")
    section = MAIN[start:start + 1800]
    assert "capture.customer_id or user.customer_id" in section


def test_capture_access_search_is_tenant_scoped_and_filterable() -> None:
    assert "CaptureAccessLog.customer_id == user.customer_id" in API
    for field in ("username", "device_id", "filename", "action", "hours"):
        assert f"{field}:" in API
