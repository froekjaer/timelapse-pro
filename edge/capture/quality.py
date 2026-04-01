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
        quality_cfg = config.get("quality", {})
        self._enabled         = quality_cfg.get("check_enabled", True)
        self._blur_thresh     = float(quality_cfg.get("blur_threshold", 80.0))
        self._dark_thresh     = float(quality_cfg.get("dark_threshold", 25.0))
        self._bright_thresh   = float(quality_cfg.get("bright_threshold", 230.0))
        self._cv2_available   = self._check_opencv()

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

    @staticmethod
    def _compute_sha256(filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
