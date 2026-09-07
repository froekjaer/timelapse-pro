from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_capture_api_returns_authoritative_assignment_names():
    source = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    assert "_capture_display.names(db, captures)" in source
    assert '"customer_name": display_names.get(c.id' in source
    assert '"site_name":     display_names.get(c.id' in source
    assert '"camera_name":   display_names.get(c.id' in source


def test_thumbnail_prefers_api_assignment_names_over_filename_parsing():
    source = (ROOT / "timelapse-ui/src/components/CaptureThumbnailCard.tsx").read_text(encoding="utf-8")
    assert "capture.customer_name || filenameFallback.customer" in source
    assert "capture.site_name || filenameFallback.site" in source
    assert "capture.camera_name || filenameFallback.camera" in source
