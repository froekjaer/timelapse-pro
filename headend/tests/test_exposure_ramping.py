"""Tests for headend/services/exposure_ramping.py.

Focus: (1) the correction math is bounded and behaves as designed (no-op on
stable sequences, flattens single-frame outliers, does not fight a genuine
gradual trend), and (2) the module degrades safely per-frame — a corrupt or
missing frame must never abort the whole sequence or raise past the public
entry point.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))
from services import exposure_ramping as ramp  # noqa: E402
from services.timelapse_render_service import RenderOptions  # noqa: E402


def _make_jpeg(path: Path, rgb: tuple[int, int, int], size: int = 32) -> None:
    Image.new("RGB", (size, size), rgb).save(path, format="JPEG", quality=95)


def _ts(i: int) -> datetime:
    return datetime(2026, 8, 16, 12, 0, i, tzinfo=timezone.utc)


# ── RenderOptions wiring ─────────────────────────────────────────────────────

def test_exposure_ramping_defaults_false_and_does_not_affect_other_fields() -> None:
    options = RenderOptions.from_payload({})
    assert options.exposure_ramping is False
    options_on = RenderOptions.from_payload({"exposure_ramping": True, "deflicker": True})
    assert options_on.exposure_ramping is True
    assert options_on.deflicker is True  # independent flags, no cross-interference


# ── Feature extraction ───────────────────────────────────────────────────────

def test_extract_frame_features_reads_solid_color_image(tmp_path: Path) -> None:
    path = tmp_path / "grey.jpg"
    _make_jpeg(path, (128, 128, 128))
    features = ramp.extract_frame_features(str(path))
    assert features is not None
    assert 120 <= features.brightness <= 136
    assert abs(features.r - features.g) < 5
    assert abs(features.g - features.b) < 5


def test_extract_frame_features_returns_none_for_missing_file() -> None:
    assert ramp.extract_frame_features("/nonexistent/path/does-not-exist.jpg") is None


def test_extract_frame_features_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.jpg"
    path.write_bytes(b"this is not a jpeg")
    assert ramp.extract_frame_features(str(path)) is None


# ── Correction math ──────────────────────────────────────────────────────────

def test_compute_corrections_is_identity_for_a_stable_sequence() -> None:
    features = [ramp.FrameFeatures(brightness=120, r=120, g=120, b=120) for _ in range(10)]
    corrections = ramp.compute_corrections(features)
    assert all(c.is_identity for c in corrections)


def test_compute_corrections_flattens_a_single_frame_outlier() -> None:
    features = [ramp.FrameFeatures(brightness=120, r=120, g=120, b=120) for _ in range(15)]
    features[7] = ramp.FrameFeatures(brightness=60, r=60, g=60, b=60)  # sudden dark frame
    corrections = ramp.compute_corrections(features)
    assert corrections[7].gain_g > 1.0  # brightened back toward the local baseline
    assert all(c.is_identity for i, c in enumerate(corrections) if i != 7)


def test_compute_corrections_clamps_extreme_outliers() -> None:
    features = [ramp.FrameFeatures(brightness=120, r=120, g=120, b=120) for _ in range(15)]
    features[7] = ramp.FrameFeatures(brightness=5, r=5, g=5, b=5)  # near-black frame
    corrections = ramp.compute_corrections(features, max_ev=0.5)
    # 2**0.5 ~= 1.414 is the ceiling for a pure exposure (luma) gain
    assert corrections[7].gain_g <= 2.0 ** 0.5 + 1e-6


def test_compute_corrections_does_not_fight_a_gradual_trend_in_the_interior() -> None:
    # A steady day->night ramp: for any frame with a FULL, symmetric window
    # available (i.e. not near the start/end of the batch), the windowed
    # median of a linear trend equals the frame's own value exactly — so the
    # correction is a true no-op. Only the edge frames (truncated, one-sided
    # window) see any correction at all, and that's covered separately below.
    features = [
        ramp.FrameFeatures(brightness=200 - 5 * i, r=200 - 5 * i, g=200 - 5 * i, b=200 - 5 * i)
        for i in range(15)
    ]
    corrections = ramp.compute_corrections(features, window=15)
    half = 15 // 2
    interior = corrections[half: len(corrections) - half]
    for c in interior:
        assert c.is_identity


def test_compute_corrections_bounds_edge_of_sequence_trend_correction() -> None:
    # The first/last frames of a batch only have a one-sided window, so a
    # genuine gradual trend does produce a small correction there — but it
    # must stay well inside the configured clamp, never treated as a hard
    # flicker outlier.
    features = [
        ramp.FrameFeatures(brightness=200 - 5 * i, r=200 - 5 * i, g=200 - 5 * i, b=200 - 5 * i)
        for i in range(15)
    ]
    corrections = ramp.compute_corrections(features, window=15, max_ev=0.5)
    assert corrections[0].gain_g <= 2.0 ** 0.5 + 1e-6
    assert corrections[-1].gain_g <= 2.0 ** 0.5 + 1e-6


def test_compute_corrections_treats_missing_features_as_identity() -> None:
    features = [None, None, ramp.FrameFeatures(brightness=120, r=120, g=120, b=120), None]
    corrections = ramp.compute_corrections(features)
    assert all(c.is_identity for c in corrections)


# ── Correction application ───────────────────────────────────────────────────

def test_apply_correction_is_a_noop_for_identity(tmp_path: Path) -> None:
    src = tmp_path / "src.jpg"
    _make_jpeg(src, (100, 100, 100))
    dst = tmp_path / "dst.jpg"
    assert ramp.apply_correction(str(src), dst, ramp.IDENTITY) is False
    assert not dst.exists()


def test_apply_correction_brightens_image_and_leaves_source_untouched(tmp_path: Path) -> None:
    src = tmp_path / "src.jpg"
    _make_jpeg(src, (100, 100, 100))
    src_bytes_before = src.read_bytes()
    dst = tmp_path / "dst.jpg"
    correction = ramp.FrameCorrection(gain_r=1.2, gain_g=1.2, gain_b=1.2)
    assert ramp.apply_correction(str(src), dst, correction) is True
    assert dst.exists()
    with Image.open(dst) as out:
        assert out.getpixel((0, 0))[0] > 100
    assert src.read_bytes() == src_bytes_before  # original never modified


def test_apply_correction_fails_closed_for_missing_source(tmp_path: Path) -> None:
    dst = tmp_path / "dst.jpg"
    correction = ramp.FrameCorrection(gain_r=1.2, gain_g=1.2, gain_b=1.2)
    assert ramp.apply_correction("/nonexistent/frame.jpg", dst, correction) is False
    assert not dst.exists()


# ── End-to-end sequence building: the safety-critical fallback behaviour ───

def test_build_ramped_frame_sequence_preserves_order_and_length(tmp_path: Path) -> None:
    src_dir = tmp_path / "captures"
    src_dir.mkdir()
    image_paths = []
    for i in range(12):
        path = src_dir / f"{i:03d}.jpg"
        _make_jpeg(path, (110 + i, 110 + i, 110 + i))
        image_paths.append((str(path), _ts(i)))

    output = ramp.build_ramped_frame_sequence(image_paths, tmp_path / "ramped")
    assert len(output) == len(image_paths)
    assert [ts for _, ts in output] == [ts for _, ts in image_paths]
    for path, _ in output:
        assert Path(path).exists()


def test_build_ramped_frame_sequence_falls_back_to_original_for_a_corrupt_frame(tmp_path: Path) -> None:
    src_dir = tmp_path / "captures"
    src_dir.mkdir()
    image_paths = []
    for i in range(6):
        path = src_dir / f"{i:03d}.jpg"
        if i == 3:
            path.write_bytes(b"not a real jpeg")
        else:
            _make_jpeg(path, (120, 120, 120))
        image_paths.append((str(path), _ts(i)))

    output = ramp.build_ramped_frame_sequence(image_paths, tmp_path / "ramped")
    assert len(output) == 6
    # The corrupt frame's own path must be passed through unchanged, not dropped.
    assert output[3][0] == image_paths[3][0]


def test_build_ramped_frame_sequence_never_raises_for_an_entirely_unreadable_batch(tmp_path: Path) -> None:
    image_paths = [(f"/nonexistent/{i}.jpg", _ts(i)) for i in range(5)]
    output = ramp.build_ramped_frame_sequence(image_paths, tmp_path / "ramped")
    assert output == image_paths  # everything falls back to the originals, no crash


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
