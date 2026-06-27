from pathlib import Path
import json
import subprocess
import sys

import cv2
import numpy as np

from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
from edge.capture.quality import QualityChecker, QualityFlag, QualityResult


def make_checker() -> QualityChecker:
    return QualityChecker({
        "quality": {
            "check_enabled": True,
            "blur_threshold": 80,
            "dark_threshold": 25,
            "bright_threshold": 230,
        }
    })


def test_qa_report_maps_blurry_to_focus_issue(monkeypatch):
    checker = make_checker()

    def fake_check(_path, _expected_sha256=None):
        return QualityResult(
            flag=QualityFlag.BLURRY,
            passed=False,
            blur_score=20.0,
            brightness_mean=100.0,
            blur_threshold=80.0,
            dark_threshold=25.0,
            bright_threshold=230.0,
            sha256_verified=True,
            message="fake blurry",
        )

    monkeypatch.setattr(checker, "check", fake_check)
    report = checker.qa_report(Path("sample.jpg"))

    assert report["engine"] == "edge_cv_v1"
    assert report["is_anomaly"] is True
    assert report["probable_cause"] == "focus_or_lens_issue"
    assert "LAB focus slice" in report["recommended_action"]


def test_qa_report_keeps_ok_images_non_anomalous(monkeypatch):
    checker = make_checker()

    def fake_check(_path, _expected_sha256=None):
        return QualityResult(
            flag=QualityFlag.OK,
            passed=True,
            blur_score=120.0,
            brightness_mean=110.0,
            blur_threshold=80.0,
            dark_threshold=25.0,
            bright_threshold=230.0,
            sha256_verified=True,
            message="ok",
        )

    monkeypatch.setattr(checker, "check", fake_check)
    report = checker.qa_report(Path("sample.jpg"))

    assert report["is_anomaly"] is False
    assert report["probable_cause"] == "ok"
    assert report["confidence"] == 0.55


def test_qa_report_detects_direct_sun_reflection(monkeypatch):
    checker = make_checker()

    def fake_check(_path, _expected_sha256=None):
        return QualityResult(
            flag=QualityFlag.OVEREXPOSED,
            passed=False,
            blur_score=160.0,
            brightness_mean=242.0,
            blur_threshold=80.0,
            dark_threshold=25.0,
            bright_threshold=230.0,
            sha256_verified=True,
            message="too bright",
        )

    monkeypatch.setattr(checker, "check", fake_check)
    monkeypatch.setattr(checker, "_cv_features", lambda _path: {
        "highlight_ratio": 0.12,
        "center_brightness": 246.0,
        "contrast_std": 48.0,
        "bright_ratio": 0.20,
        "saturation_mean": 60.0,
    })

    report = checker.qa_report(Path("sample.jpg"))

    assert report["probable_cause"] == "direct_sun_reflection"
    assert "avoid-window" in report["recommended_action"]


def test_qa_report_detects_snow_or_dirt(monkeypatch):
    checker = make_checker()

    def fake_check(_path, _expected_sha256=None):
        return QualityResult(
            flag=QualityFlag.BLURRY,
            passed=False,
            blur_score=18.0,
            brightness_mean=190.0,
            blur_threshold=80.0,
            dark_threshold=25.0,
            bright_threshold=230.0,
            sha256_verified=True,
            message="soft bright image",
        )

    monkeypatch.setattr(checker, "check", fake_check)
    monkeypatch.setattr(checker, "_cv_features", lambda _path: {
        "highlight_ratio": 0.01,
        "center_brightness": 190.0,
        "contrast_std": 12.0,
        "bright_ratio": 0.01,
        "saturation_mean": 20.0,
    })

    report = checker.qa_report(Path("sample.jpg"))

    assert report["probable_cause"] == "snow_or_dirt_on_lens"
    assert report["is_anomaly"] is True


def _write_jpeg(path: Path, image: np.ndarray) -> Path:
    ok = cv2.imwrite(str(path), image)
    assert ok
    return path


def test_autonomous_optimizer_detects_direct_sun_and_ev_action(tmp_path):
    img = np.full((360, 640, 3), 150, dtype=np.uint8)
    cv2.circle(img, (320, 180), 90, (255, 255, 255), -1)
    path = _write_jpeg(tmp_path / "direct_sun.jpg", img)

    result = AutonomousImageOptimizer({
        "quality": {
            "bright_threshold": 230,
            "adaptive_exposure": {"target_brightness": 118, "step_ev": 0.3},
        }
    }).analyse(path, {"flag": "overexposed", "probable_cause": "direct_sun_reflection"})

    actions = {r["action"] for r in result["recommendations"]}
    assert "avoid_direct_sun_window" in actions
    assert result["control_plan"]["next_capture_ev_delta"] < 0
    assert result["control_plan"]["avoid_window_suggestion"]["action"] == "avoid"


def test_autonomous_optimizer_detects_white_balance_cast(tmp_path):
    img = np.zeros((240, 360, 3), dtype=np.uint8)
    img[:, :] = (210, 125, 90)  # BGR: blue-heavy cool cast
    path = _write_jpeg(tmp_path / "cool_cast.jpg", img)

    result = AutonomousImageOptimizer({"quality": {}}).analyse(path, {"flag": "ok"})

    wb = result["features"]["white_balance"]
    actions = {r["action"] for r in result["recommendations"]}
    assert wb["cast"] == "cool/blue"
    assert "set_whitebalance_daylight" in actions


def test_autonomous_optimizer_detects_depth_of_field_issue(tmp_path):
    sharp = np.zeros((360, 640, 3), dtype=np.uint8)
    for y in range(0, 360, 12):
        cv2.line(sharp, (0, y), (639, y), (255, 255, 255), 1)
    for x in range(0, 640, 12):
        cv2.line(sharp, (x, 0), (x, 359), (255, 255, 255), 1)
    blurred = cv2.GaussianBlur(sharp, (31, 31), 0)
    img = blurred.copy()
    img[90:270, 160:480] = sharp[90:270, 160:480]
    path = _write_jpeg(tmp_path / "shallow_dof.jpg", img)

    result = AutonomousImageOptimizer({
        "quality": {"blur_threshold": 80}
    }).analyse(path, {"flag": "ok", "blur_score": 120})

    actions = {r["action"] for r in result["recommendations"]}
    assert "increase_depth_of_field" in actions
    assert result["control_plan"]["autonomous_safe_to_apply"] is False


def test_autonomous_optimizer_monitor_mode_never_applies_ev(tmp_path):
    img = np.full((240, 360, 3), 230, dtype=np.uint8)
    path = _write_jpeg(tmp_path / "bright_monitor.jpg", img)

    result = AutonomousImageOptimizer({
        "quality": {
            "adaptive_exposure": {"target_brightness": 118, "step_ev": 0.3},
            "edge_ai": {"enabled": True, "mode": "monitor"},
        }
    }).analyse(path, {"flag": "ok"})

    assert result["policy"]["mode"] == "monitor"
    assert any(r["action"] == "decrease_ev" for r in result["recommendations"])
    assert result["control_plan"]["next_capture_ev_delta"] == 0.0
    assert result["control_plan"]["autonomous_safe_to_apply"] is False


def test_autonomous_optimizer_off_mode_returns_disabled(tmp_path):
    img = np.full((120, 180, 3), 128, dtype=np.uint8)
    path = _write_jpeg(tmp_path / "off.jpg", img)

    result = AutonomousImageOptimizer({
        "quality": {"edge_ai": {"enabled": True, "mode": "off"}}
    }).analyse(path, {})

    assert result["enabled"] is False
    assert result["recommendations"] == []
    assert result["control_plan"]["autonomous_safe_to_apply"] is False


def test_edge_qa_npu_runner_emits_json_contract(tmp_path):
    img = np.full((120, 180, 3), 220, dtype=np.uint8)
    path = _write_jpeg(tmp_path / "runner.jpg", img)

    proc = subprocess.run(
        [
            sys.executable,
            "edge/tools/edge_qa_npu_runner.py",
            "--model",
            str(tmp_path / "missing.nb"),
            "--image",
            str(path),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["engine"] == "edge_npu_contract_cpu_fallback"
    assert payload["available"] is False
    assert "runtime" in payload
    assert "optimizer" in payload
