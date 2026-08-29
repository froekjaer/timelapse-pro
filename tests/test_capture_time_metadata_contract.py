from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_capture_list_returns_explicit_local_capture_time_contract():
    source = _source("headend/main.py")
    helper = _source("headend/capture_api_helpers.py")
    list_endpoint = source.split("def list_captures(", 1)[1].split('@app.get("/api/admin/stats")', 1)[0]
    timeline_endpoint = source.split("def captures_timeline(", 1)[1].split("# ── EXIF", 1)[0]

    assert "def capture_timestamp_fields" in helper
    assert "def capture_timezone_from_config" in helper
    assert '"captured_at_local"' in helper
    assert '"captured_at_utc"' in helper
    assert '"captured_timezone"' in helper
    assert "**capture_timestamp_fields(c.captured_at" in list_endpoint
    assert "**capture_timestamp_fields(c.captured_at" in timeline_endpoint


def test_thumbnail_display_prefers_local_capture_time_without_browser_timezone_guessing():
    source = _source("timelapse-ui/src/components/CaptureThumbnailCard.tsx")
    helper = _source("timelapse-ui/src/lib/captureTime.ts")

    assert "capture.captured_at_local ?? capture.captured_at" in helper
    assert "LOCAL_CAPTURE_RE" in helper
    assert "EXPLICIT_TZ_RE" in helper
    assert "export function formatCaptureTimestamp" in helper
    assert "captureTimestampParts" in source
    assert "new Date(capture.captured_at).toLocaleString" not in source


def test_device_lightbox_reuses_shared_capture_time_formatter():
    source = _source("timelapse-ui/src/pages/DevicePage.tsx")
    lightbox_section = source.split("function Lightbox", 1)[1].split("function StatsTab", 1)[0]

    assert "formatCaptureTimestamp" in source
    assert "const time = formatCaptureTimestamp(c, { includeYear: true })" in lightbox_section
    assert "new Date(c.captured_at).toLocaleString" not in lightbox_section


def test_exifread_is_declared_for_headend_runtime():
    requirements = _source("headend/requirements.txt")

    assert "exifread==3.5.1" in requirements
