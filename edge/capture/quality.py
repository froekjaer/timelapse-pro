"""
TimeLapse Pro — Image Quality Checker
=======================================
OpenCV-based quality assessment for captured images.
Runs on CPU — no GPU/NPU dependency.

Checks performed:
  1. Blur (Laplacian variance)  — detects focus drift, dirt, condensation
  2. Under-exposure             — detects night captures, lens cap, relay failure
  3. Over-exposure              — detects direct sun, wrong exposure settings
  4. File integrity             — verifies SHA-256 matches what was recorded at download

SABSA: Integrity — every image is assessed and flagged, but still stored
       and transmitted. Operators review flagged images via web UI.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import math
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class QualityFlag(Enum):
    OK            = "ok"
    BLURRY        = "blurry"           # Laplacian variance below threshold
    UNDEREXPOSED  = "underexposed"     # mean brightness too low
    OVEREXPOSED   = "overexposed"      # mean brightness too high
    HASH_MISMATCH = "hash_mismatch"    # file corrupted after download
    ERROR         = "error"            # assessment itself failed


@dataclasses.dataclass
class QualityResult:
    flag:            QualityFlag
    passed:          bool             # True only if flag == OK
    blur_score:      Optional[float]  # Laplacian variance (higher = sharper)
    brightness_mean: Optional[float]  # 0–255
    blur_threshold:  float
    dark_threshold:  float
    bright_threshold:float
    sha256_verified: bool
    message:         str              # human-readable summary

    def as_dict(self) -> dict:
        return {
            "flag":             self.flag.value,
            "passed":           self.passed,
            "blur_score":       self.blur_score,
            "brightness_mean":  self.brightness_mean,
            "blur_threshold":   self.blur_threshold,
            "dark_threshold":   self.dark_threshold,
            "bright_threshold": self.bright_threshold,
            "sha256_verified":  self.sha256_verified,
            "message":          self.message,
        }


class QualityChecker:
    """
    Assess image quality using OpenCV (CPU-only).

    Config keys (from config.yaml quality section):
        check_enabled:     bool  (default true)
        blur_threshold:    float Laplacian variance; below = blurry (default 80)
        dark_threshold:    float mean brightness; below = underexposed (default 25)
        bright_threshold:  float mean brightness; above = overexposed (default 230)
    """

    def __init__(self, config: dict):
        self._config = config
        quality_cfg = config.get("quality", {})
        self._enabled         = quality_cfg.get("check_enabled", True)
        self._blur_thresh     = float(quality_cfg.get("blur_threshold", 80.0))
        self._dark_thresh     = float(quality_cfg.get("dark_threshold", 25.0))
        self._bright_thresh   = float(quality_cfg.get("bright_threshold", 230.0))
        self._cv2_available   = self._check_opencv()
        edge_ai_cfg = quality_cfg.get("edge_ai", {}) or {}
        self._lens_obstruction_enabled = bool(edge_ai_cfg.get("lens_obstruction_enabled", True))
        self._direct_sun_enabled = bool(edge_ai_cfg.get("direct_sun_detection_enabled", True))
        self._npu = self._load_npu_adapter(config)

    def _check_opencv(self) -> bool:
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            log.warning(
                "opencv-python not installed — quality checks disabled. "
                "Install with: pip install opencv-python-headless"
            )
            return False

    def check(self, filepath: Path, expected_sha256: Optional[str] = None) -> QualityResult:
        """
        Assess image quality.

        Args:
            filepath:        path to the JPEG/RAW image
            expected_sha256: if provided, verify file hash

        Returns:
            QualityResult — always returns, never raises.
            Flag is ERROR if assessment itself fails.
        """
        if not self._enabled:
            return QualityResult(
                flag=QualityFlag.OK, passed=True,
                blur_score=None, brightness_mean=None,
                blur_threshold=self._blur_thresh,
                dark_threshold=self._dark_thresh,
                bright_threshold=self._bright_thresh,
                sha256_verified=False,
                message="Quality checks disabled",
            )

        # ── Hash verification ──────────────────────────────────────────────
        sha256_ok = True
        if expected_sha256:
            actual = self._compute_sha256(filepath)
            sha256_ok = (actual == expected_sha256)
            if not sha256_ok:
                log.error(
                    "SHA-256 mismatch for %s: expected %s got %s",
                    filepath.name, expected_sha256[:12], actual[:12]
                )
                return QualityResult(
                    flag=QualityFlag.HASH_MISMATCH, passed=False,
                    blur_score=None, brightness_mean=None,
                    blur_threshold=self._blur_thresh,
                    dark_threshold=self._dark_thresh,
                    bright_threshold=self._bright_thresh,
                    sha256_verified=False,
                    message=f"File corruption detected: SHA-256 mismatch",
                )

        # ── OpenCV analysis ────────────────────────────────────────────────
        if not self._cv2_available:
            return QualityResult(
                flag=QualityFlag.OK, passed=True,
                blur_score=None, brightness_mean=None,
                blur_threshold=self._blur_thresh,
                dark_threshold=self._dark_thresh,
                bright_threshold=self._bright_thresh,
                sha256_verified=sha256_ok,
                message="OpenCV not available — checks skipped",
            )

        try:
            blur_score, brightness = self._analyse(filepath)
        except Exception as exc:
            log.exception("Quality analysis failed for %s", filepath.name)
            return QualityResult(
                flag=QualityFlag.ERROR, passed=False,
                blur_score=None, brightness_mean=None,
                blur_threshold=self._blur_thresh,
                dark_threshold=self._dark_thresh,
                bright_threshold=self._bright_thresh,
                sha256_verified=sha256_ok,
                message=f"Analysis error: {exc}",
            )

        # ── Apply thresholds ───────────────────────────────────────────────
        if blur_score < self._blur_thresh:
            flag = QualityFlag.BLURRY
            msg  = (f"Blur score {blur_score:.1f} below threshold {self._blur_thresh} "
                    f"— possible focus drift, dirt or condensation on glass")
        elif brightness < self._dark_thresh:
            flag = QualityFlag.UNDEREXPOSED
            msg  = (f"Mean brightness {brightness:.1f} below {self._dark_thresh} "
                    f"— image too dark (night? lens cap? relay failure?)")
        elif brightness > self._bright_thresh:
            flag = QualityFlag.OVEREXPOSED
            msg  = (f"Mean brightness {brightness:.1f} above {self._bright_thresh} "
                    f"— image too bright (sun in lens? wrong exposure?)")
        else:
            flag = QualityFlag.OK
            msg  = (f"OK — blur={blur_score:.1f} brightness={brightness:.1f}")

        passed = (flag == QualityFlag.OK)
        if not passed:
            log.warning("Quality check FAILED for %s: %s", filepath.name, msg)
        else:
            log.info("Quality check PASSED for %s: %s", filepath.name, msg)

        return QualityResult(
            flag=flag, passed=passed,
            blur_score=blur_score,
            brightness_mean=brightness,
            blur_threshold=self._blur_thresh,
            dark_threshold=self._dark_thresh,
            bright_threshold=self._bright_thresh,
            sha256_verified=sha256_ok,
            message=msg,
        )

    def qa_report(self, filepath: Path, expected_sha256: Optional[str] = None) -> dict:
        """
        Return a deterministic Edge QA report for AI/LAB flows.

        This deliberately stays model-free so it can run on small Edge boards and
        remain stable while Headend AI evolves independently.
        """
        quality = self.check(filepath, expected_sha256)
        report = quality.as_dict()
        cv_features = self._cv_features(filepath) if self._cv2_available else {}
        report.update({
            "engine": "edge_cv_v1",
            "is_anomaly": not quality.passed,
            "probable_cause": "ok",
            "confidence": 0.55 if quality.passed else 0.70,
            "recommended_action": "Ingen handling",
            "cv_features": cv_features,
            "npu": self._npu.status() if self._npu else {"enabled": False, "available": False},
        })

        if quality.flag == QualityFlag.HASH_MISMATCH:
            report.update({
                "probable_cause": "file_integrity_error",
                "confidence": 0.98,
                "recommended_action": "Stop automatiseret brug af billedet og gentag upload fra Edge-buffer.",
            })
        elif quality.flag == QualityFlag.BLURRY:
            report.update({
                "probable_cause": "focus_or_lens_issue",
                "confidence": self._blur_confidence(quality.blur_score),
                "recommended_action": "Kør LAB focus slice og kontroller dug, snavs eller fokusdrift.",
            })
        elif quality.flag == QualityFlag.UNDEREXPOSED:
            report.update({
                "probable_cause": "underexposure_or_camera_blocked",
                "confidence": self._brightness_confidence(quality.brightness_mean, low=True),
                "recommended_action": "Kontroller lysforhold, objektivdæksel og relay/kamera-wakeup.",
            })
        elif quality.flag == QualityFlag.OVEREXPOSED:
            report.update({
                "probable_cause": "overexposure_or_direct_sun",
                "confidence": self._brightness_confidence(quality.brightness_mean, low=False),
                "recommended_action": "Kontroller solretning, eksponering og montagevinkel.",
            })
        elif quality.flag == QualityFlag.ERROR:
            report.update({
                "probable_cause": "qa_analysis_error",
                "confidence": 0.80,
                "recommended_action": "Kontroller billedfil og OpenCV-runtime på Edge.",
            })

        heuristic = self._classify_scene_issue(quality, cv_features)
        if heuristic:
            report.update(heuristic)

        npu_result = self._npu.analyse(filepath) if self._npu else None
        if npu_result:
            report["npu"] = {**report.get("npu", {}), **npu_result}
            report = self._merge_npu_result(report, npu_result)

        optimizer_result = self._autonomous_optimizer_report(filepath, report)
        if optimizer_result:
            report["autonomous_optimizer"] = optimizer_result

        report["confidence"] = round(float(report["confidence"]), 2)
        return report

    def _analyse(self, filepath: Path) -> tuple[float, float]:
        """
        Load image, compute Laplacian variance (blur) and mean brightness.
        Returns (blur_score, brightness_mean).
        """
        import cv2
        import numpy as np

        img = cv2.imread(str(filepath))
        if img is None:
            raise ValueError(f"cv2.imread returned None for {filepath}")

        # Resize to max 1024px on longest side for speed (quality unaffected)
        h, w = img.shape[:2]
        max_dim = 1024
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Blur detection: Laplacian variance
        # High variance = sharp image, low variance = blurry
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Brightness: mean pixel value of greyscale image
        brightness = float(np.mean(gray))

        return blur_score, brightness

    def _cv_features(self, filepath: Path) -> dict:
        """Extract cheap CPU features for lens/reflection heuristics."""
        try:
            import cv2
            import numpy as np

            img = cv2.imread(str(filepath))
            if img is None:
                return {}
            h, w = img.shape[:2]
            max_dim = 1024
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            dark_ratio = float(np.mean(gray < self._dark_thresh))
            bright_ratio = float(np.mean(gray > self._bright_thresh))
            highlight_ratio = float(np.mean(gray > 245))
            contrast_std = float(np.std(gray))
            saturation_mean = float(np.mean(hsv[:, :, 1]))
            saturation_std = float(np.std(hsv[:, :, 1]))
            center = gray[gray.shape[0] // 4: gray.shape[0] * 3 // 4, gray.shape[1] // 4: gray.shape[1] * 3 // 4]
            center_brightness = float(np.mean(center)) if center.size else float(np.mean(gray))
            return {
                "dark_ratio": round(dark_ratio, 4),
                "bright_ratio": round(bright_ratio, 4),
                "highlight_ratio": round(highlight_ratio, 4),
                "contrast_std": round(contrast_std, 2),
                "saturation_mean": round(saturation_mean, 2),
                "saturation_std": round(saturation_std, 2),
                "center_brightness": round(center_brightness, 2),
            }
        except Exception as exc:
            log.debug("CV feature extraction failed for %s: %s", filepath.name, exc)
            return {}

    def _classify_scene_issue(self, quality: QualityResult, features: dict) -> dict | None:
        if not features:
            return None
        blur = quality.blur_score if quality.blur_score is not None else math.inf
        brightness = quality.brightness_mean if quality.brightness_mean is not None else 128.0
        contrast = float(features.get("contrast_std", 0))
        highlight_ratio = float(features.get("highlight_ratio", 0))
        bright_ratio = float(features.get("bright_ratio", 0))
        saturation = float(features.get("saturation_mean", 0))
        center = float(features.get("center_brightness", brightness))

        if self._direct_sun_enabled and highlight_ratio > 0.05 and (center > self._bright_thresh - 10 or bright_ratio > 0.10):
            return {
                "is_anomaly": True,
                "probable_cause": "direct_sun_reflection",
                "confidence": min(0.94, 0.70 + highlight_ratio),
                "recommended_action": "Flyt capturetidspunkt via headend avoid-window eller sænk eksponeringskompensation.",
            }
        if self._lens_obstruction_enabled and blur < self._blur_thresh and contrast < 22 and brightness > 170 and saturation < 45:
            return {
                "is_anomaly": True,
                "probable_cause": "snow_or_dirt_on_lens",
                "confidence": 0.82,
                "recommended_action": "Kontroller frontglas/linse for sne, skidt eller saltfilm.",
            }
        if self._lens_obstruction_enabled and blur < self._blur_thresh and contrast < 18 and bright_ratio < 0.02:
            return {
                "is_anomaly": True,
                "probable_cause": "condensation_or_soft_lens_obstruction",
                "confidence": 0.78,
                "recommended_action": "Kontroller dug, kondens og fokus; kør LAB focus slice.",
            }
        return None

    def _merge_npu_result(self, report: dict, npu_result: dict) -> dict:
        """Let NPU raise confidence/cause, while CPU remains authoritative fallback."""
        cause = npu_result.get("probable_cause") or npu_result.get("label")
        confidence = npu_result.get("confidence")
        try:
            npu_conf = float(confidence)
        except Exception:
            npu_conf = 0.0
        if cause and npu_conf >= max(0.60, float(report.get("confidence", 0)) - 0.05):
            report["is_anomaly"] = bool(npu_result.get("is_anomaly", report.get("is_anomaly", True)))
            report["probable_cause"] = str(cause)
            report["confidence"] = max(float(report.get("confidence", 0)), npu_conf)
            if npu_result.get("recommended_action"):
                report["recommended_action"] = str(npu_result["recommended_action"])
        return report

    def _autonomous_optimizer_report(self, filepath: Path, report: dict) -> dict | None:
        try:
            try:
                from ai.autonomous_optimizer import AutonomousImageOptimizer
            except Exception:
                from edge.ai.autonomous_optimizer import AutonomousImageOptimizer

            return AutonomousImageOptimizer(self._config).analyse(filepath, report)
        except Exception as exc:
            log.debug("Autonomous optimizer unavailable for %s: %s", filepath.name, exc)
            return None

    @staticmethod
    def _load_npu_adapter(config: dict):
        try:
            from ai.npu_quality import NpuQualityAdapter

            return NpuQualityAdapter(config)
        except Exception as exc:
            log.debug("NPU adapter unavailable: %s", exc)
            return None

    def _blur_confidence(self, blur_score: Optional[float]) -> float:
        if blur_score is None:
            return 0.70
        gap = max(0.0, self._blur_thresh - blur_score)
        return min(0.95, 0.62 + (gap / max(self._blur_thresh, 1.0)) * 0.30)

    def _brightness_confidence(self, brightness: Optional[float], low: bool) -> float:
        if brightness is None:
            return 0.70
        if low:
            gap = max(0.0, self._dark_thresh - brightness)
            denom = max(self._dark_thresh, 1.0)
        else:
            gap = max(0.0, brightness - self._bright_thresh)
            denom = max(255.0 - self._bright_thresh, 1.0)
        return min(0.95, 0.62 + (gap / denom) * 0.30)

    @staticmethod
    def _compute_sha256(filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
