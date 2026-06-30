from pathlib import Path
import json
import subprocess
import sys

import cv2
import numpy as np

from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
from edge.ai.model_contract import (
    classification_to_contract,
    contract_metadata,
    label_from_filename,
    scores_to_contract,
)
from edge.ai.npu_quality import NpuQualityAdapter
from edge.ai.npu_runtime import detect_orangepi_npu_runtime
from edge.capture.quality import QualityChecker, QualityFlag, QualityResult
from edge.tools.generate_qa_test_images import generate
from edge.tools.mine_qa_training_candidates import label_from_report


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


def test_npu_merge_ignores_rejected_low_confidence_result():
    checker = make_checker()
    report = {
        "is_anomaly": False,
        "probable_cause": "ok",
        "confidence": 0.55,
        "recommended_action": "Ingen handling",
    }
    merged = checker._merge_npu_result(report.copy(), {
        "accepted": False,
        "probable_cause": "focus_or_lens_issue",
        "confidence": 0.99,
        "recommended_action": "Kør LAB focus slice",
    })

    assert merged["probable_cause"] == "ok"
    assert merged["confidence"] == 0.55


def test_npu_merge_accepts_high_confidence_result():
    checker = make_checker()
    report = {
        "is_anomaly": False,
        "probable_cause": "ok",
        "confidence": 0.55,
        "recommended_action": "Ingen handling",
    }
    merged = checker._merge_npu_result(report.copy(), {
        "accepted": True,
        "is_anomaly": True,
        "probable_cause": "focus_or_lens_issue",
        "confidence": 0.82,
        "recommended_action": "Kør LAB focus slice",
    })

    assert merged["is_anomaly"] is True
    assert merged["probable_cause"] == "focus_or_lens_issue"
    assert merged["confidence"] == 0.82


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


def test_autonomous_optimizer_uses_bright_ratio_without_name_error(tmp_path):
    img = np.full((360, 640, 3), 120, dtype=np.uint8)
    img[:, :180] = 255
    path = _write_jpeg(tmp_path / "off_center_reflection.jpg", img)

    result = AutonomousImageOptimizer({
        "quality": {
            "bright_threshold": 230,
            "adaptive_exposure": {"target_brightness": 118, "step_ev": 0.3},
        }
    }).analyse(path, {"flag": "ok"})

    assert result["features"]["bright_ratio"] > 0.10
    assert any(r["action"] == "avoid_direct_sun_window" for r in result["recommendations"])


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
    assert payload["schema"] == "timelapse.edge_qa.v1"


def test_edge_qa_contract_maps_known_labels():
    payload = classification_to_contract("depth_of_field_issue", 0.87, engine="test")

    assert payload["schema"] == "timelapse.edge_qa.v1"
    assert payload["class_id"] == 2
    assert payload["probable_cause"] == "depth_of_field_issue"
    assert payload["quality_dimension"] == "depth_of_field"
    assert payload["is_anomaly"] is True


def test_training_miner_prefers_primary_quality_flag_over_optimizer():
    report = {
        "flag": "underexposed",
        "probable_cause": "underexposure_or_camera_blocked",
        "autonomous_optimizer": {
            "recommendations": [
                {"kind": "depth_of_field", "action": "increase_depth_of_field", "confidence": 0.82}
            ]
        },
    }

    assert label_from_report(report) == "underexposed"


def test_training_miner_prefers_exposure_recommendation_over_depth_of_field():
    report = {
        "flag": "ok",
        "probable_cause": "ok",
        "autonomous_optimizer": {
            "recommendations": [
                {"kind": "depth_of_field", "action": "increase_depth_of_field", "confidence": 0.76},
                {"kind": "exposure", "action": "increase_ev", "confidence": 0.81},
            ]
        },
    }

    assert label_from_report(report) == "underexposed"


def test_training_miner_keeps_high_quality_scene_as_ok():
    report = {
        "flag": "ok",
        "passed": True,
        "is_anomaly": False,
        "blur_score": 220.0,
        "brightness_mean": 125.0,
        "cv_features": {
            "dark_ratio": 0.04,
            "bright_ratio": 0.01,
            "highlight_ratio": 0.002,
            "contrast_std": 48.0,
            "saturation_mean": 62.0,
        },
        "autonomous_optimizer": {
            "score": {"overall": 86.0, "grade": "good"},
            "recommendations": [
                {"kind": "exposure", "action": "increase_ev", "confidence": 0.64}
            ],
        },
    }

    assert label_from_report(report) == "ok"


def test_training_miner_allows_noisy_depth_hint_on_good_scene_as_ok():
    report = {
        "flag": "ok",
        "passed": True,
        "is_anomaly": False,
        "blur_score": 155.0,
        "brightness_mean": 142.0,
        "cv_features": {
            "dark_ratio": 0.02,
            "bright_ratio": 0.0,
            "highlight_ratio": 0.0,
            "contrast_std": 18.5,
            "saturation_mean": 34.0,
        },
        "autonomous_optimizer": {
            "score": {"overall": 86.9, "grade": "good"},
            "recommendations": [
                {"kind": "depth_of_field", "action": "increase_depth_of_field", "confidence": 0.76}
            ],
        },
    }

    assert label_from_report(report) == "ok"


def test_training_miner_rejects_dirty_or_dark_scene_as_ok():
    report = {
        "flag": "ok",
        "passed": True,
        "is_anomaly": False,
        "blur_score": 210.0,
        "brightness_mean": 70.0,
        "cv_features": {
            "dark_ratio": 0.31,
            "bright_ratio": 0.001,
            "highlight_ratio": 0.001,
            "contrast_std": 54.0,
            "saturation_mean": 72.0,
        },
        "autonomous_optimizer": {
            "score": {"overall": 79.0, "grade": "good"},
            "recommendations": [
                {"kind": "exposure", "action": "increase_ev", "confidence": 0.81},
                {"kind": "depth_of_field", "action": "increase_depth_of_field", "confidence": 0.76},
            ],
        },
    }

    assert label_from_report(report) == "underexposed"


def test_edge_qa_contract_scores_accept_dict_and_list():
    by_name = scores_to_contract({"ok": 0.1, "direct_sun_reflection": 0.91})
    by_index = scores_to_contract([0.1, 0.2, 0.3, 0.4, 0.5, 0.95])

    assert by_name["label"] == "direct_sun_reflection"
    assert by_index["label"] == "direct_sun_reflection"
    assert any(c["label"] == "white_balance_cast" for c in contract_metadata()["classes"])


def test_edge_qa_contract_rejects_unknown_label():
    try:
        classification_to_contract("mystery", 0.5)
    except ValueError as exc:
        assert "Unknown edge QA label" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_label_from_filename_covers_synthetic_images():
    assert label_from_filename("qa_06_shallow_depth_of_field.jpg") == "depth_of_field_issue"
    assert label_from_filename("qa_07_snow_or_dirty_lens.jpg") == "snow_or_dirt_on_lens"


def test_npu_adapter_accepts_runner_command_with_arguments(tmp_path):
    img = np.full((120, 180, 3), 220, dtype=np.uint8)
    path = _write_jpeg(tmp_path / "adapter.jpg", img)
    runner = f"{sys.executable} edge/tools/edge_qa_npu_runner.py"

    adapter = NpuQualityAdapter({
        "quality": {
            "edge_ai": {
                "enabled": True,
                "mode": "npu_first",
                "prefer_npu": True,
                "runner": runner,
                "model_path": "",
            }
        }
    })

    assert adapter.available() is True
    result = adapter.analyse(path)
    assert result is not None
    assert result["engine"] == "edge_npu_contract_cpu_fallback"


def test_edge_qa_npu_runner_normalises_vendor_binary(tmp_path):
    img = np.full((120, 180, 3), 220, dtype=np.uint8)
    image = _write_jpeg(tmp_path / "adapter.jpg", img)
    model = tmp_path / "edge_qa.nb"
    model.write_bytes(b"demo")
    vendor = tmp_path / "vendor.py"
    vendor.write_text(
        "import json\n"
        "print(json.dumps({'scores': {'ok': 0.1, 'direct_sun_reflection': 0.92}}))\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "edge/tools/edge_qa_npu_runner.py",
            "--model",
            str(model),
            "--image",
            str(image),
            "--vendor-binary",
            f"{sys.executable} {vendor}",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["label"] in {"direct_sun_reflection", "ok"}
    if payload["engine"] != "edge_npu_contract_pending_vendor_binding":
        assert payload["probable_cause"] == "direct_sun_reflection"


def test_orangepi_npu_probe_reports_missing_model(tmp_path):
    payload = detect_orangepi_npu_runtime(
        ai_sdk_root=str(tmp_path / "missing-ai-sdk"),
        model_path=str(tmp_path / "missing.nb"),
    )

    assert payload["engine"] == "orangepi_npu_probe_v1"
    assert payload["npu_ready"] is False
    assert "ai_sdk" in payload["missing"]
    assert "model_path" in payload["missing"]
    assert payload["manual_contract"]["model_format"] == ".nb"


def test_probe_orangepi_npu_cli_emits_json(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            "edge/tools/probe_orangepi_npu.py",
            "--ai-sdk-root",
            str(tmp_path / "missing-ai-sdk"),
            "--model",
            str(tmp_path / "missing.nb"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["engine"] == "orangepi_npu_probe_v1"
    assert payload["npu_ready"] is False


def test_build_qa_dataset_manifest_from_generated_images(tmp_path):
    image_dir = tmp_path / "images"
    generate(image_dir)
    out = tmp_path / "manifest.jsonl"

    proc = subprocess.run(
        [
            sys.executable,
            "edge/tools/build_qa_dataset_manifest.py",
            str(image_dir),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(proc.stdout)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    assert summary["images"] == 7
    assert len(rows) == 7
    labels = {row["label"] for row in rows}
    assert "direct_sun_reflection" in labels
    assert "depth_of_field_issue" in labels
    assert all(row["sha256"] for row in rows)


def test_mine_qa_training_candidates_and_render_review_sheet(tmp_path):
    image_dir = tmp_path / "images"
    generate(image_dir)
    manifest = tmp_path / "candidates.jsonl"
    summary = tmp_path / "summary.json"
    review_dir = tmp_path / "review"

    mine = subprocess.run(
        [
            sys.executable,
            "edge/tools/mine_qa_training_candidates.py",
            str(image_dir),
            "--out",
            str(manifest),
            "--summary-out",
            str(summary),
            "--per-label",
            "20",
            "--include-review",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    mine_summary = json.loads(mine.stdout)
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    labels = {row["label"] for row in rows}

    assert mine_summary["selected"] == len(rows)
    assert "ok" in labels
    assert "depth_of_field_issue" in labels
    assert "white_balance_cast" in labels

    render = subprocess.run(
        [
            sys.executable,
            "edge/tools/render_qa_review_sheet.py",
            "--manifest",
            str(manifest),
            "--out-dir",
            str(review_dir),
            "--max-per-label",
            "5",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    render_summary = json.loads(render.stdout)
    assert Path(render_summary["review_csv"]).exists()
    assert (review_dir / "ok.jpg").exists()


def test_curate_qa_training_manifest_uses_approved_labels(tmp_path):
    image_dir = tmp_path / "images"
    generate(image_dir)
    mined = tmp_path / "candidates.jsonl"
    curated = tmp_path / "curated.jsonl"
    review = tmp_path / "review.csv"
    summary = tmp_path / "summary.json"

    subprocess.run(
        [
            sys.executable,
            "edge/tools/mine_qa_training_candidates.py",
            str(image_dir),
            "--out",
            str(mined),
            "--per-label",
            "20",
            "--include-review",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    first_row = json.loads(mined.read_text(encoding="utf-8").splitlines()[0])
    review.write_text(
        "image,label,confidence,review_priority,approved_label,notes\n"
        f"{first_row['image']},{first_row['label']},{first_row.get('confidence')},"
        f"{first_row.get('review_priority')},ok,review override\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "edge/tools/curate_qa_training_manifest.py",
            "--candidates",
            str(mined),
            "--review-csv",
            str(review),
            "--out",
            str(curated),
            "--summary-out",
            str(summary),
            "--per-label",
            "20",
            "--include-review-recommended",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    rows = [json.loads(line) for line in curated.read_text(encoding="utf-8").splitlines()]

    assert payload["selected"] == len(rows)
    assert any(row["image"] == first_row["image"] and row["label"] == "ok" for row in rows)
    assert payload["decisions"]["human_approved"] == 1
