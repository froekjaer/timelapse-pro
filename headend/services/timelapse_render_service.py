"""Validated render options and deterministic FFmpeg filter construction."""

from __future__ import annotations

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException


ALLOWED_RESOLUTIONS = {"1080p", "4k", "original"}
ALLOWED_CODECS = {"h264", "h265"}
ALLOWED_CROPS = {"16:9", "4:3", "1:1", "original"}
ALLOWED_KEN_BURNS = {"none", "zoom_in", "zoom_out"}
ALLOWED_TIMESTAMP_POSITIONS = {"tl", "tr", "bl", "br"}
ALLOWED_TIMESTAMP_FORMATS = {"pts", "datetime"}
ALLOWED_STABILIZATION = {"none", "light", "strong"}
ALLOWED_DENOISE = {"none", "light", "strong"}
ALLOWED_SHARPEN = {"none", "light", "strong"}


def safe_title(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "timelapse"))
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    result = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_title).strip("_")[:80]
    return result or "timelapse"


def _choice(payload: dict, key: str, default: str, allowed: set[str]) -> str:
    value = str(payload.get(key, default))
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f"Ugyldig {key}: {value}")
    return value


@dataclass(frozen=True)
class RenderOptions:
    fps: int
    resolution: str
    codec: str
    deflicker: bool
    # Temporal exposure/white-balance smoothing (headend/services/exposure_ramping.py).
    # Independent of `deflicker` above (that's an ffmpeg pixel-domain filter on the
    # rendered frames; this is a pre-render pass over the source images using measured
    # brightness/color per frame). Default False — zero effect on existing renders.
    exposure_ramping: bool
    fade_frames: int
    timestamp_overlay: bool
    timestamp_position: str
    timestamp_format: str
    ken_burns: str
    crop_ratio: str
    stabilization: str
    denoise: str
    sharpen: str
    title: str

    @classmethod
    def from_payload(cls, payload: dict) -> "RenderOptions":
        try:
            fps = int(payload.get("fps", 25))
            fade_frames = int(payload.get("fade_frames", 0))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="fps og fade_frames skal være heltal") from exc
        if not 1 <= fps <= 60:
            raise HTTPException(status_code=422, detail="fps skal være mellem 1 og 60")
        if not 0 <= fade_frames <= 600:
            raise HTTPException(status_code=422, detail="fade_frames skal være mellem 0 og 600")
        return cls(
            fps=fps,
            resolution=_choice(payload, "resolution", "1080p", ALLOWED_RESOLUTIONS),
            codec=_choice(payload, "codec", "h264", ALLOWED_CODECS),
            deflicker=bool(payload.get("deflicker", False)),
            exposure_ramping=bool(payload.get("exposure_ramping", False)),
            fade_frames=fade_frames,
            timestamp_overlay=bool(payload.get("timestamp_overlay", False)),
            timestamp_position=_choice(payload, "timestamp_position", "br", ALLOWED_TIMESTAMP_POSITIONS),
            timestamp_format=_choice(payload, "timestamp_format", "pts", ALLOWED_TIMESTAMP_FORMATS),
            ken_burns=_choice(payload, "ken_burns", "none", ALLOWED_KEN_BURNS),
            crop_ratio=_choice(payload, "crop_ratio", "16:9", ALLOWED_CROPS),
            stabilization=_choice(payload, "stabilization", "none", ALLOWED_STABILIZATION),
            denoise=_choice(payload, "denoise", "none", ALLOWED_DENOISE),
            sharpen=_choice(payload, "sharpen", "none", ALLOWED_SHARPEN),
            title=safe_title(payload.get("title")),
        )


def ffmpeg_filter_capabilities(ffmpeg_path: str = "ffmpeg") -> set[str]:
    """Return filters provided by the deployed binary, not assumed build features."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {
        match.group(1)
        for line in result.stdout.splitlines()
        if (match := re.match(r"^\s*[.TSC]{2,4}\s+([A-Za-z0-9_]+)\s", line))
    }


def required_filters(options: RenderOptions) -> set[str]:
    required: set[str] = set()
    if options.deflicker:
        required.add("deflicker")
    if options.stabilization != "none":
        required.add("deshake")
    if options.denoise != "none":
        required.add("nlmeans")
    if options.sharpen != "none":
        required.add("unsharp")
    if options.timestamp_overlay:
        # "pts" is drawn via ffmpeg's built-in %{pts} expression (drawtext).
        # "datetime" needs each frame's REAL, possibly-irregularly-spaced
        # capture time, which drawtext has no concept of — that's rendered as
        # a generated per-frame subtitle track burned in via the libass-based
        # `subtitles` filter instead (see build_datetime_subtitle_file below).
        if options.timestamp_format == "datetime":
            required.add("subtitles")
        else:
            required.add("drawtext")
    return required


def validate_filter_capabilities(options: RenderOptions, available: set[str]) -> None:
    missing = sorted(required_filters(options) - available)
    if missing:
        raise HTTPException(
            status_code=422,
            detail="FFmpeg-installationen mangler valgte filtre: " + ", ".join(missing),
        )


def enhancement_filters(options: RenderOptions) -> list[str]:
    """Build conservative filters in an order suitable for photographic masters."""
    filters: list[str] = []
    if options.stabilization == "light":
        filters.append("deshake=rx=16:ry=16:edge=mirror")
    elif options.stabilization == "strong":
        filters.append("deshake=rx=32:ry=32:edge=mirror")
    if options.deflicker:
        filters.append("deflicker=size=10:mode=pm")
    if options.denoise == "light":
        filters.append("nlmeans=s=1.0:p=7:r=9")
    elif options.denoise == "strong":
        filters.append("nlmeans=s=2.0:p=7:r=15")
    if options.sharpen == "light":
        filters.append("unsharp=5:5:0.35:5:5:0")
    elif options.sharpen == "strong":
        filters.append("unsharp=5:5:0.65:5:5:0")
    return filters


# ── Real-datetime timestamp overlay (subtitle-based) ─────────────────────────
#
# ffmpeg's drawtext has a built-in %{pts} expression for elapsed PLAYBACK time,
# but no concept of a frame's real, independently-varying capture time — a
# timelapse's source photos are rarely evenly spaced (the camera can go
# offline, skip intervals, etc.), so there's no formula that turns "frame
# index" into "correct real date". Instead we generate an ASS subtitle file
# with one cue per rendered frame, each showing that frame's actual
# `captured_at`, and burn it in via ffmpeg's libass-based `subtitles` filter.

_ASS_ALIGNMENT = {"tl": 7, "tr": 9, "bl": 1, "br": 3}  # numpad-style layout


def _ass_timecode(seconds: float) -> str:
    """Format seconds as ASS H:MM:SS.CS (centiseconds)."""
    centis_total = max(0, round(seconds * 100))
    hours, rem = divmod(centis_total, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _ass_escape_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def _ass_frame_text(captured_at: datetime | None, zone: ZoneInfo) -> str:
    if captured_at is None:
        return "?"
    aware = captured_at if captured_at.tzinfo else captured_at.replace(tzinfo=timezone.utc)
    return aware.astimezone(zone).strftime("%Y-%m-%d %H:%M")


def build_datetime_subtitle_file(
    frame_timestamps: list[datetime | None],
    fps: int,
    position: str,
    play_res: tuple[int, int],
    output_path: Path,
    tz_name: str = "Europe/Copenhagen",
) -> None:
    """Write an .ass subtitle file with one cue per rendered frame, timed to
    match the render's fixed per-frame duration (1/fps each, same as the
    FFmpeg concat demuxer's `duration` directive) and showing that frame's
    real capture timestamp converted to `tz_name`.
    """
    zone = ZoneInfo(tz_name)
    align = _ASS_ALIGNMENT.get(position, 3)
    width, height = play_res
    fontsize = max(18, round(height / 30))
    frame_duration = 1.0 / fps

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        # White text, opaque-ish black box background (BorderStyle=3), matching the
        # look of the pts drawtext overlay (fontcolor=white:box=1:boxcolor=black@0.4).
        f"Style: Default,Arial,{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,"
        f"0,0,0,0,100,100,0,0,3,2,0,{align},20,20,20,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for index, captured_at in enumerate(frame_timestamps):
        start = _ass_timecode(index * frame_duration)
        end = _ass_timecode((index + 1) * frame_duration)
        text = _ass_escape_text(_ass_frame_text(captured_at, zone))
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ffmpeg_filter_path_escape(path: str) -> str:
    """Escape a filesystem path for use as an ffmpeg filter argument value
    (e.g. subtitles=<path>). ffmpeg filter syntax treats ':' as the option
    separator and needs '\\' and undecorated ':' escaped."""
    return path.replace("\\", "\\\\").replace(":", "\\:")
