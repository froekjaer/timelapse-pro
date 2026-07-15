import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).parents[1] / "headend"))
service = importlib.import_module("services.timelapse_render_service")


def test_title_cannot_escape_render_directory() -> None:
    assert service.safe_title("../../customer/video") == "customer_video"
    assert "/" not in service.safe_title("Frøkjær sommer 2026")


@pytest.mark.parametrize("payload", [
    {"fps": 0}, {"fps": 61}, {"codec": "copy"}, {"resolution": "8k"},
    {"crop_ratio": "../../etc"}, {"timestamp_position": "center"},
    {"timestamp_format": "filename"}, {"stabilization": "magic"},
    {"denoise": "maximum"}, {"sharpen": "auto"},
])
def test_invalid_render_options_fail_closed(payload: dict) -> None:
    with pytest.raises(HTTPException) as exc:
        service.RenderOptions.from_payload(payload)
    assert exc.value.status_code == 422


def test_known_render_options_are_preserved() -> None:
    options = service.RenderOptions.from_payload({"fps": 30, "codec": "h265", "title": "Site A"})
    assert options.fps == 30
    assert options.codec == "h265"
    assert options.title == "Site_A"


def test_enhancement_filters_use_conservative_order() -> None:
    options = service.RenderOptions.from_payload({
        "stabilization": "light", "deflicker": True,
        "denoise": "light", "sharpen": "light",
    })
    filters = service.enhancement_filters(options)
    assert [item.split("=", 1)[0] for item in filters] == [
        "deshake", "deflicker", "nlmeans", "unsharp",
    ]
    assert "rx=16:ry=16" in filters[0]


def test_missing_ffmpeg_filter_fails_before_job_is_started() -> None:
    options = service.RenderOptions.from_payload({"stabilization": "light"})
    with pytest.raises(HTTPException) as exc:
        service.validate_filter_capabilities(options, {"deflicker"})
    assert exc.value.status_code == 422
    assert "deshake" in str(exc.value.detail)


def test_datetime_overlay_is_not_silently_rendered_as_elapsed_time() -> None:
    options = service.RenderOptions.from_payload({
        "timestamp_overlay": True, "timestamp_format": "datetime",
    })
    with pytest.raises(HTTPException) as exc:
        service.validate_filter_capabilities(options, {"drawtext"})
    assert "Dato/tid-overlay" in str(exc.value.detail)


def test_agent_does_not_bypass_unsafe_optimizer_plan() -> None:
    source = (Path(__file__).parents[1] / "edge" / "agent.py").read_text()
    start = source.index("def _maybe_update_adaptive_exposure")
    section = source[start:start + 3000]
    assert "optimizer marked plan unsafe" in section
    assert section.index("return") < section.index('cause = str(quality_report.get("probable_cause")')
