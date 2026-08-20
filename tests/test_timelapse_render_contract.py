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


def test_datetime_overlay_requires_subtitles_filter_not_drawtext() -> None:
    """"datetime" burns in each frame's REAL capture time via a generated
    libass subtitle track (build_datetime_subtitle_file), not ffmpeg's
    built-in %{pts} elapsed-time expression — so it needs the `subtitles`
    filter specifically, and having `drawtext` alone isn't enough."""
    options = service.RenderOptions.from_payload({
        "timestamp_overlay": True, "timestamp_format": "datetime",
    })
    with pytest.raises(HTTPException) as exc:
        service.validate_filter_capabilities(options, {"drawtext"})
    assert "subtitles" in str(exc.value.detail)

    # No exception when the actually-required filter is available.
    service.validate_filter_capabilities(options, {"subtitles"})


def test_pts_overlay_still_requires_drawtext_not_subtitles() -> None:
    options = service.RenderOptions.from_payload({
        "timestamp_overlay": True, "timestamp_format": "pts",
    })
    with pytest.raises(HTTPException) as exc:
        service.validate_filter_capabilities(options, {"subtitles"})
    assert "drawtext" in str(exc.value.detail)


def test_ass_timecode_formatting() -> None:
    assert service._ass_timecode(0) == "0:00:00.00"
    assert service._ass_timecode(1 / 25) == "0:00:00.04"
    assert service._ass_timecode(3661.5) == "1:01:01.50"


def test_datetime_subtitle_converts_utc_and_naive_timestamps_to_local_time(tmp_path) -> None:
    from datetime import datetime, timezone

    frames = [
        datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),  # winter -> CET (UTC+1) -> 13:00
        None,
        datetime(2026, 1, 15, 12, 5),  # naive -> assumed UTC -> 13:05 local
    ]
    output = tmp_path / "test.ass"
    service.build_datetime_subtitle_file(
        frame_timestamps=frames, fps=1, position="tl",
        play_res=(1920, 1080), output_path=output,
    )
    content = output.read_text()
    assert "PlayResX: 1920" in content
    assert "PlayResY: 1080" in content
    assert ",7,20,20,20,1" in content  # tl -> ASS alignment 7 (top-left)

    dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    assert dialogue_lines == [
        "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,2026-01-15 13:00",
        "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,?",
        "Dialogue: 0,0:00:02.00,0:00:03.00,Default,,0,0,0,,2026-01-15 13:05",
    ]


def test_datetime_subtitle_alignment_mapping(tmp_path) -> None:
    from datetime import datetime, timezone

    expected = {"tl": ",7,", "tr": ",9,", "bl": ",1,", "br": ",3,", "unknown": ",3,"}
    for position, marker in expected.items():
        output = tmp_path / f"{position}.ass"
        service.build_datetime_subtitle_file(
            frame_timestamps=[datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)],
            fps=25, position=position, play_res=(1920, 1080), output_path=output,
        )
        style_line = next(l for l in output.read_text().splitlines() if l.startswith("Style:"))
        assert marker in style_line, f"position={position}"


def test_ffmpeg_filter_path_escape_escapes_colons() -> None:
    assert service.ffmpeg_filter_path_escape("/tmp/render/job.ass") == "/tmp/render/job.ass"
    assert service.ffmpeg_filter_path_escape("/tmp/weird:path/job.ass") == "/tmp/weird\\:path/job.ass"


def test_agent_does_not_bypass_unsafe_optimizer_plan() -> None:
    source = (Path(__file__).parents[1] / "edge" / "agent.py").read_text()
    start = source.index("def _maybe_update_adaptive_exposure")
    section = source[start:start + 3000]
    assert "optimizer marked plan unsafe" in section
    assert section.index("return") < section.index('cause = str(quality_report.get("probable_cause")')
