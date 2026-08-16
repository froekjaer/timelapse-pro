"""Temporal exposure/white-balance smoothing for timelapse renders.

Opt-in, additive pre-render pass. Never mutates original capture files —
always reads the source image and, on success, writes a corrected copy to a
job-scoped temp directory. Any failure (unreadable frame, PIL error, disk
error) for an individual frame falls back to using that frame's ORIGINAL
path unmodified; a failure anywhere in this module must never abort or
change the outcome of a render that did not request this option.

Deliberately independent from edge/ai/site_look_manager.py's per-camera LUT
matching — that system corrects *between cameras* against a fixed site
reference; this one corrects *within one camera's sequence over time*
against a local, centered rolling baseline, which is the actual "deflicker /
holy-grail ramping" problem (see Dokumentation/HANDOVER_LOG.md, 2026-08-16
entry). No cross-import between edge/ and headend/ — they run in separate
environments with separate dependency sets.

Pipeline:
1. Extract cheap per-frame features (luma + R/G/B means) from a small
   thumbnail of each frame.
2. Build a centered rolling-median baseline per channel — robust to
   single-frame outliers. Because the window tracks genuine gradual trends
   (clouds, day->night), a real lighting change is not fought: only the
   short-term jitter around the local trend gets flattened.
3. Derive a bounded exposure (luma) gain and a separately, more tightly
   bounded, green-anchored white-balance gain per frame.
4. Apply the gains to a full-resolution copy of the frame and write it to a
   temp directory; the caller points ffmpeg at the corrected copies instead
   of the originals for this render job only.
"""
from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageStat

log = logging.getLogger(__name__)

# Conservative defaults: enough to remove flicker/jitter, not enough to
# visibly fight an intentional exposure change (e.g. a technician re-aiming
# the camera, or a genuine dusk/dawn transition spread across many frames).
DEFAULT_WINDOW = 15
DEFAULT_MAX_EV = 0.5
DEFAULT_MAX_WB_RATIO = 0.12
THUMB_SIZE = 96
JPEG_QUALITY = 95


@dataclass(frozen=True)
class FrameFeatures:
    brightness: float  # 0-255 luma mean
    r: float
    g: float
    b: float


@dataclass(frozen=True)
class FrameCorrection:
    gain_r: float
    gain_g: float
    gain_b: float

    @property
    def is_identity(self) -> bool:
        return self.gain_r == self.gain_g == self.gain_b == 1.0


IDENTITY = FrameCorrection(1.0, 1.0, 1.0)


def extract_frame_features(path: str, thumb_size: int = THUMB_SIZE) -> Optional[FrameFeatures]:
    """Best-effort feature extraction. Returns None on any failure — caller
    must treat that frame as pass-through, never as a reason to abort."""
    try:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            rgb.thumbnail((thumb_size, thumb_size))
            r, g, b = ImageStat.Stat(rgb).mean
            luma = ImageStat.Stat(rgb.convert("L")).mean[0]
            return FrameFeatures(brightness=luma, r=r, g=g, b=b)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see module docstring
        log.warning("exposure_ramping: kunne ikke analysere %s: %s", path, exc)
        return None


def _windowed_median(values: list[Optional[float]], index: int, half_window: int) -> Optional[float]:
    window = [v for v in values[max(0, index - half_window): index + half_window + 1] if v is not None]
    if not window:
        return None
    return statistics.median(window)


def _clamp(ratio: float, max_ratio: float) -> float:
    return max(1.0 - max_ratio, min(1.0 + max_ratio, ratio))


def compute_corrections(
    features: list[Optional[FrameFeatures]],
    window: int = DEFAULT_WINDOW,
    max_ev: float = DEFAULT_MAX_EV,
    max_wb_ratio: float = DEFAULT_MAX_WB_RATIO,
) -> list[FrameCorrection]:
    """One correction per input frame, same order/length. Frames with no
    features (extraction failed) or no usable local baseline get the
    identity correction — left exactly as-is."""
    half = max(1, window // 2)
    brightness = [f.brightness if f else None for f in features]
    reds = [f.r if f else None for f in features]
    greens = [f.g if f else None for f in features]
    blues = [f.b if f else None for f in features]

    corrections: list[FrameCorrection] = []
    for i, f in enumerate(features):
        if f is None or f.brightness <= 0 or f.g <= 0:
            corrections.append(IDENTITY)
            continue

        base_brightness = _windowed_median(brightness, i, half)
        base_r = _windowed_median(reds, i, half)
        base_g = _windowed_median(greens, i, half)
        base_b = _windowed_median(blues, i, half)
        if not base_brightness or not base_g or base_r is None or base_b is None:
            corrections.append(IDENTITY)
            continue

        ev = math.log2((base_brightness + 1.0) / (f.brightness + 1.0))
        ev = max(-max_ev, min(max_ev, ev))
        luma_gain = 2.0 ** ev

        # Green-anchored white balance: how far off this frame's R/G and B/G
        # ratio are from the local window's own R/G and B/G ratio.
        frame_rg = f.r / f.g
        frame_bg = f.b / f.g
        base_rg = base_r / base_g
        base_bg = base_b / base_g
        wb_gain_r = _clamp(base_rg / frame_rg, max_wb_ratio) if frame_rg > 0 else 1.0
        wb_gain_b = _clamp(base_bg / frame_bg, max_wb_ratio) if frame_bg > 0 else 1.0

        corrections.append(FrameCorrection(
            gain_r=luma_gain * wb_gain_r,
            gain_g=luma_gain,
            gain_b=luma_gain * wb_gain_b,
        ))
    return corrections


def _gain_lut(gain: float) -> list[int]:
    return [max(0, min(255, round(i * gain))) for i in range(256)]


def apply_correction(src_path: str, dst_path: Path, correction: FrameCorrection) -> bool:
    """Write a corrected copy of src_path to dst_path. Returns False (and
    leaves dst_path untouched) on any failure, or when the correction is a
    no-op — caller must fall back to src_path itself. Never modifies
    src_path."""
    if correction.is_identity:
        return False
    try:
        with Image.open(src_path) as img:
            rgb = img.convert("RGB")
            bands = rgb.split()
            luts = (_gain_lut(correction.gain_r), _gain_lut(correction.gain_g), _gain_lut(correction.gain_b))
            corrected = Image.merge("RGB", [band.point(lut) for band, lut in zip(bands, luts)])
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            corrected.save(dst_path, format="JPEG", quality=JPEG_QUALITY)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("exposure_ramping: kunne ikke skrive korrigeret kopi af %s: %s", src_path, exc)
        return False


def build_ramped_frame_sequence(
    image_paths: list[tuple[str, datetime]],
    output_dir: Path,
    **params,
) -> list[tuple[str, datetime]]:
    """Return a same-length, same-order list of (path, captured_at) tuples
    where each path is either a temporally-smoothed copy (written under
    output_dir) or the ORIGINAL path when smoothing that specific frame
    failed or wasn't needed. Per-frame failures never raise; only a truly
    unexpected error (e.g. output_dir's filesystem is unwritable) can
    propagate, so the caller's own try/except can fall back to the
    completely original sequence."""
    features = [extract_frame_features(path) for path, _ in image_paths]
    corrections = compute_corrections(features, **params)

    result: list[tuple[str, datetime]] = []
    for index, ((src_path, captured_at), correction) in enumerate(zip(image_paths, corrections)):
        dst_path = output_dir / f"{index:06d}.jpg"
        if apply_correction(src_path, dst_path, correction):
            result.append((str(dst_path), captured_at))
        else:
            result.append((src_path, captured_at))
    return result
