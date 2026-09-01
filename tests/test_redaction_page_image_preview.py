from pathlib import Path


def test_redaction_page_shows_image_with_bounding_box_overlay():
    """Peter (2026-09-01): "kan du gøre sådan at man kan klikke og se
    billederne, så man kan ved hvad man sløre eller godkender et billede,
    samt kan se hvor sløringen vil komme". Before this, the detail panel
    only listed bounding boxes as raw x/y/w/h text — no image was ever
    shown anywhere on the page."""
    source = Path("timelapse-ui/src/pages/RedactionPage.tsx").read_text(encoding="utf-8")

    # Renders the actual capture image, not just a thumbnail placeholder.
    assert 'import { getImageUrl } from "../api/client"' in source
    assert "getImageUrl(selectedCapture.device_id, selectedCapture.filename)" in source

    # Bounding boxes are drawn on top of the image in its own natural pixel
    # coordinate space (gdpr_detections x/y/w/h are absolute pixels on the
    # original file — see headend/redaction_api.py redact_capture()), via an
    # SVG viewBox so no manual scale-factor math is needed and no
    # thumbnail/full-image size mismatch can silently misplace a box.
    assert "viewBox={`0 0 ${imgDims.w} ${imgDims.h}`}" in source
    assert "naturalWidth" in source and "naturalHeight" in source
    assert "analysisResult.faces.map" in source
    assert "analysisResult.license_plates.map" in source

    # Overlay state resets when a different capture is selected, so a stale
    # box from the previous image can't flash on the new one before onLoad.
    assert "[selectedCapture?.capture_id]" in source


def test_redaction_page_still_has_the_analyze_redact_approve_workflow():
    """Guard against the image-preview change accidentally dropping the
    existing analyze/redact/approve action buttons."""
    source = Path("timelapse-ui/src/pages/RedactionPage.tsx").read_text(encoding="utf-8")
    assert "/api/redaction/analyze/" in source
    assert "/api/redaction/redact/" in source
    assert "/api/redaction/approve/" in source


def test_redaction_page_does_not_offer_approve_before_redaction():
    source = Path("timelapse-ui/src/pages/RedactionPage.tsx").read_text(encoding="utf-8")
    detected_block = source.split('selectedCapture.redaction_status === "detected"', 1)[1]
    detected_block = detected_block.split('selectedCapture.redaction_status === "redacted"', 1)[0]

    assert "redactCapture" in detected_block
    assert "approveCapture" not in detected_block
    assert "afventer endelig godkendelse" in source
    assert "sløret og godkendt" not in source
