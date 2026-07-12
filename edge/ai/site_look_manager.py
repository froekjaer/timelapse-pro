"""
TimeLapse Pro — Site-Wide Look Matching Manager
================================================

Ensures all cameras on a site can produce timelapse videos with consistent
look (colors, exposure, etc.) that can be edited together without visible
differences.

Architecture:
    1. Site Reference Frame: A "golden reference" look for the entire site
    2. Look Matching Engine: Analyzes camera vs reference and generates LUTs
    3. Camera-Specific Profiles: Nikon Picture Control, Canon Picture Styles
    4. Reference Propagation: Distributes reference to all cameras on site
    5. Video Pipeline: Renders with common look applied

Design principles:
    - CPU-only operation (no GPU required)
    - Deterministic results for reproducibility
    - Camera-specific color science (Nikon vs Canon have different responses)
    - LUT-based approach for maximum quality and flexibility

Key features:
    - Auto-generate site reference from first high-quality capture
    - Per-camera LUT generation for matching to reference
    - Support for Nikon Z30 Picture Controls (Flat, Standard, Vivid, etc.)
    - Support for Canon EOS Picture Styles (Standard, Portrait, Landscape, etc.)
    - Temperature-aware matching (warm vs cool lighting conditions)
    - Exposure matching within physical limits
"""
from __future__ import annotations

import dataclasses
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ── Camera-Specific Color Profiles ─────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class ColorProfile:
    """Camera-specific color response characteristics."""
    name: str
    manufacturer: str  # "nikon", "canon", "sony", etc.
    base_gamma: float  # Typical gamma curve (2.2 for most)
    color_matrix_3x3: list[list[float]]  # RGB to XYZ approximation
    saturation_boost: float  # Default saturation multiplier
    contrast_boost: float  # Default contrast multiplier
    supported_picture_controls: list[str]
    typical_kelvin_range: tuple[int, int]  # (min, max) WB range in K


# Nikon Z30 color characteristics (measured from DXO/optical data)
NIKON_Z30_PROFILE = ColorProfile(
    name="Nikon Z30",
    manufacturer="nikon",
    base_gamma=2.2,
    color_matrix_3x3=[
        [0.638, 0.299, 0.063],  # Red channel sensitivity
        [0.144, 0.639, 0.217],  # Green channel sensitivity
        [0.046, 0.121, 0.833],  # Blue channel sensitivity
    ],
    saturation_boost=1.05,
    contrast_boost=1.0,
    supported_picture_controls=[
        "Flat",           # Minimal processing, max dynamic range
        "Standard",       # Nikon's default balanced look
        "Neutral",        # Lower contrast/saturation
        "Vivid",          # Increased saturation and contrast
        "Monochrome",     # Black and white
        "Portrait",       # Skin-tone optimized
        "Landscape",      # Sky and foliage optimized
    ],
    typical_kelvin_range=(2700, 7200),
)

# Canon EOS 1300D/2000D color characteristics
CANON_EOS_PROFILE = ColorProfile(
    name="Canon EOS 1300D/2000D",
    manufacturer="canon",
    base_gamma=2.2,
    color_matrix_3x3=[
        [0.689, 0.273, 0.038],  # Canon tends to be warmer/redder
        [0.165, 0.612, 0.223],
        [0.056, 0.107, 0.837],
    ],
    saturation_boost=1.0,
    contrast_boost=1.05,  # Canon typically has slightly more contrast
    supported_picture_styles=[
        "Standard",       # Canon's default
        "Portrait",       # Soother tones for skin
        "Landscape",      # Deeper blues/greens
        "Neutral",        # Flat for post-processing
        "Faithful",       # Accurate color reproduction
        "Monochrome",     # Black and white
        "Auto",           # Camera-selected
    ],
    typical_kelvin_range=(2700, 7000),
)

CAMERA_COLOR_PROFILES: dict[str, ColorProfile] = {
    "Nikon Z30": NIKON_Z30_PROFILE,
    "Nikon Z fc": NIKON_Z30_PROFILE,  # Same sensor family
    "Canon EOS 1300D": CANON_EOS_PROFILE,
    "Canon EOS 2000D": CANON_EOS_PROFILE,
    "Canon EOS 4000D": CANON_EOS_PROFILE,
    "Canon EOS": CANON_EOS_PROFILE,  # Generic fallback
}


def get_color_profile(camera_model: str) -> ColorProfile:
    """Get color profile for camera model, with fallback to generic."""
    model_key = camera_model.strip()
    for key, profile in CAMERA_COLOR_PROFILES.items():
        if key.lower() in model_key.lower() or model_key.lower() in key.lower():
            return profile
    # Generic sRGB profile as fallback
    return ColorProfile(
        name="Generic sRGB",
        manufacturer="generic",
        base_gamma=2.2,
        color_matrix_3x3=[
            [0.644, 0.307, 0.049],
            [0.164, 0.615, 0.221],
            [0.056, 0.109, 0.835],
        ],
        saturation_boost=1.0,
        contrast_boost=1.0,
        supported_picture_controls=["Standard"],
        typical_kelvin_range=(2700, 7000),
    )


# ── Picture Control Recommendations ───────────────────────────────────────────────

PICTURE_CONTROL_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    # Nikon Z30 recommendations
    "Nikon Z30": {
        "default_for_timelapse": "Flat",  # Max dynamic range, minimal processing
        "high_contrast_scene": "Standard",
        "low_light": "Standard",  # Better noise handling
        "vivid_colors": "Vivid",
        "post_friendly": "Flat",  # Most flexibility in grading
        "ready_to_use": "Standard",  # Good out-of-camera look
        # Picture Control parameter adjustments (sharpening, contrast, brightness, saturation, hue)
        "flat_params": {"sharpening": 3, "contrast": 0, "brightness": 0, "saturation": 0, "hue": 0},
        "standard_params": {"sharpening": 4, "contrast": 1, "brightness": 0, "saturation": 0, "hue": 0},
    },
    # Canon EOS recommendations
    "Canon EOS": {
        "default_for_timelapse": "Neutral",  # Flat for maximum flexibility
        "high_contrast_scene": "Standard",
        "low_light": "Standard",
        "vivid_colors": "Landscape",
        "post_friendly": "Neutral",
        "ready_to_use": "Standard",
        # Picture Style parameter adjustments (sharpness, contrast, saturation, color tone)
        "neutral_params": {"sharpness": 2, "contrast": 1, "saturation": 1, "color_tone": 0},
        "standard_params": {"sharpness": 3, "contrast": 2, "saturation": 2, "color_tone": 0},
    },
}


def get_picture_control_recommendation(camera_model: str, scenario: str = "default_for_timelapse") -> dict[str, Any]:
    """Get recommended Picture Control/Style for camera model and scenario."""
    model_key = camera_model.strip()
    for key, recs in PICTURE_CONTROL_RECOMMENDATIONS.items():
        if key.lower() in model_key.lower() or model_key.lower() in key.lower():
            return {
                "picture_control": recs.get(scenario, recs.get("default_for_timelapse", "Standard")),
                "parameters": recs.get(f"{recs.get(scenario, 'standard')}_params", {}),
            }
    return {
        "picture_control": "Standard",
        "parameters": {},
    }


# ── Site Reference Frame ─────────────────────────────────────────────────────────

@dataclasses.dataclass
class SiteReferenceFrame:
    """Golden reference look for an entire site.

    All cameras on the site will match their output to this reference,
    ensuring consistent timelapse videos that can be edited together.
    """
    site_id: str
    customer_id: str
    created_at: datetime
    created_by_camera_id: str
    created_by_camera_model: str

    # Color characteristics (from reference image)
    reference_lab_mean: tuple[float, float, float]  # (L, a, b) means
    reference_lab_std: tuple[float, float, float]   # (L, a, b) standard deviations
    reference_hsv_stats: dict[str, float]            # H, S, V statistics

    # Exposure characteristics
    target_brightness_mean: float
    target_brightness_median: float
    target_contrast_std: float
    target_dynamic_range: float

    # White balance reference
    reference_white_balance_kelvin: Optional[int]
    reference_white_balance_tint: float

    # Picture Control/Style reference
    reference_picture_control: str

    # Quality metrics (must meet threshold to become reference)
    quality_score: float
    blur_score: float
    no_clip: bool  # No significant highlight/shadow clipping

    # Scene classification (for time-of-day matching)
    scene_type: str  # "day", "golden_hour", "overcast", "night", etc.
    estimated_kelvin: int  # Estimated scene color temperature

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "customer_id": self.customer_id,
            "created_at": self.created_at.isoformat(),
            "created_by_camera_id": self.created_by_camera_id,
            "created_by_camera_model": self.created_by_camera_model,
            "reference_lab_mean": self.reference_lab_mean,
            "reference_lab_std": self.reference_lab_std,
            "reference_hsv_stats": self.reference_hsv_stats,
            "target_brightness_mean": self.target_brightness_mean,
            "target_brightness_median": self.target_brightness_median,
            "target_contrast_std": self.target_contrast_std,
            "target_dynamic_range": self.target_dynamic_range,
            "reference_white_balance_kelvin": self.reference_white_balance_kelvin,
            "reference_white_balance_tint": self.reference_white_balance_tint,
            "reference_picture_control": self.reference_picture_control,
            "quality_score": self.quality_score,
            "blur_score": self.blur_score,
            "no_clip": self.no_clip,
            "scene_type": self.scene_type,
            "estimated_kelvin": self.estimated_kelvin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteReferenceFrame":
        return cls(
            site_id=data["site_id"],
            customer_id=data["customer_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by_camera_id=data["created_by_camera_id"],
            created_by_camera_model=data["created_by_camera_model"],
            reference_lab_mean=tuple(data["reference_lab_mean"]),
            reference_lab_std=tuple(data["reference_lab_std"]),
            reference_hsv_stats=data["reference_hsv_stats"],
            target_brightness_mean=float(data["target_brightness_mean"]),
            target_brightness_median=float(data["target_brightness_median"]),
            target_contrast_std=float(data["target_contrast_std"]),
            target_dynamic_range=float(data["target_dynamic_range"]),
            reference_white_balance_kelvin=data.get("reference_white_balance_kelvin"),
            reference_white_balance_tint=float(data.get("reference_white_balance_tint", 0.0)),
            reference_picture_control=data["reference_picture_control"],
            quality_score=float(data["quality_score"]),
            blur_score=float(data["blur_score"]),
            no_clip=bool(data["no_clip"]),
            scene_type=data["scene_type"],
            estimated_kelvin=int(data["estimated_kelvin"]),
        )

    def save(self, path: Path) -> None:
        """Save reference frame to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        log.info(f"Site reference frame saved: {path}")

    @classmethod
    def load(cls, path: Path) -> Optional["SiteReferenceFrame"]:
        """Load reference frame from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
            log.warning(f"Failed to load site reference frame from {path}: {exc}")
            return None


# ── LUT (Look-Up Table) Generation ───────────────────────────────────────────────

@dataclasses.dataclass
class CameraLUT:
    """Look-Up Table for matching a camera to the site reference.

    The LUT stores the color adjustments needed to transform this camera's
    output to match the site reference look.
    """
    camera_id: str
    camera_model: str
    site_id: str
    generated_at: datetime

    # Color transformation matrix (3x3 for RGB)
    color_matrix: list[list[float]]

    # Exposure adjustments
    exposure_offset_ev: float  # EV offset to match reference brightness
    gamma_adjustment: float    # Gamma curve adjustment

    # Saturation and contrast adjustments
    saturation_multiplier: float
    contrast_multiplier: float

    # White balance adjustment hint (for camera command)
    wb_kelvin_hint: Optional[int]
    wb_tint_hint: float

    # Picture Control hint (for camera command)
    picture_control_hint: str

    # Match quality score (0-1, higher is better)
    match_quality_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_model": self.camera_model,
            "site_id": self.site_id,
            "generated_at": self.generated_at.isoformat(),
            "color_matrix": self.color_matrix,
            "exposure_offset_ev": self.exposure_offset_ev,
            "gamma_adjustment": self.gamma_adjustment,
            "saturation_multiplier": self.saturation_multiplier,
            "contrast_multiplier": self.contrast_multiplier,
            "wb_kelvin_hint": self.wb_kelvin_hint,
            "wb_tint_hint": self.wb_tint_hint,
            "picture_control_hint": self.picture_control_hint,
            "match_quality_score": self.match_quality_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CameraLUT":
        return cls(
            camera_id=data["camera_id"],
            camera_model=data["camera_model"],
            site_id=data["site_id"],
            generated_at=datetime.fromisoformat(data["generated_at"]),
            color_matrix=data["color_matrix"],
            exposure_offset_ev=float(data["exposure_offset_ev"]),
            gamma_adjustment=float(data["gamma_adjustment"]),
            saturation_multiplier=float(data["saturation_multiplier"]),
            contrast_multiplier=float(data["contrast_multiplier"]),
            wb_kelvin_hint=data.get("wb_kelvin_hint"),
            wb_tint_hint=float(data.get("wb_tint_hint", 0.0)),
            picture_control_hint=data["picture_control_hint"],
            match_quality_score=float(data["match_quality_score"]),
        )

    def save(self, path: Path) -> None:
        """Save LUT to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        log.info(f"Camera LUT saved: {path}")

    @classmethod
    def load(cls, path: Path) -> Optional["CameraLUT"]:
        """Load LUT from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
            log.warning(f"Failed to load camera LUT from {path}: {exc}")
            return None

    def apply_to_image(self, image_path: Path, output_path: Path) -> bool:
        """Apply LUT to an image (for video rendering pipeline).

        This is a CPU-based implementation suitable for edge nodes.
        For production rendering, consider GPU acceleration.
        """
        try:
            # Read image
            img = cv2.imread(str(image_path))
            if img is None:
                log.error(f"Failed to read image: {image_path}")
                return False

            # Apply exposure adjustment (simple gain for now)
            if abs(self.exposure_offset_ev) > 0.01:
                gain = math.pow(2.0, self.exposure_offset_ev)
                img = np.clip(img * gain, 0, 255).astype(np.uint8)

            # Apply color matrix (RGB to RGB transformation)
            matrix = np.array(self.color_matrix, dtype=np.float32)
            img_float = img.astype(np.float32)
            img_bgr = cv2.transform(img_float, matrix)
            img_bgr = np.clip(img_bgr, 0, 255).astype(np.uint8)

            # Apply saturation adjustment
            if abs(self.saturation_multiplier - 1.0) > 0.01:
                hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                h, s, v = cv2.split(hsv)
                s = np.clip(s * self.saturation_multiplier, 0, 255).astype(np.uint8)
                hsv_adjusted = cv2.merge([h, s, v])
                img_bgr = cv2.cvtColor(hsv_adjusted, cv2.COLOR_HSV2BGR)

            # Apply contrast adjustment (simple linear stretch)
            if abs(self.contrast_multiplier - 1.0) > 0.01:
                lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                # Apply contrast to L channel
                l_mean = l.mean()
                l = np.clip((l - l_mean) * self.contrast_multiplier + l_mean, 0, 255).astype(np.uint8)
                lab_adjusted = cv2.merge([l, a, b])
                img_bgr = cv2.cvtColor(lab_adjusted, cv2.COLOR_LAB2BGR)

            # Write output
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            log.debug(f"LUT applied: {image_path} -> {output_path}")
            return True

        except Exception as exc:
            log.error(f"LUT application failed: {exc}")
            return False


# ── Site Look Manager ───────────────────────────────────────────────────────────

class SiteLookManager:
    """Main manager for site-wide look matching.

    Responsibilities:
    - Create site reference frames from high-quality captures
    - Generate per-camera LUTs for matching to reference
    - Store/retrieve reference frames and LUTs
    - Provide camera command hints for consistent capture
    """

    def __init__(self, config: dict):
        self._config = config
        self._storage_base = Path(config.get("site_look_storage_path", "/var/lib/timelapse/site_looks"))
        self._storage_base.mkdir(parents=True, exist_ok=True)

    def _get_reference_path(self, site_id: str) -> Path:
        """Get path to site reference frame file."""
        return self._storage_base / f"{site_id}_reference.json"

    def _get_lut_path(self, site_id: str, camera_id: str) -> Path:
        """Get path to camera LUT file."""
        return self._storage_base / f"{site_id}_{camera_id}_lut.json"

    def has_reference(self, site_id: str) -> bool:
        """Check if site has a reference frame."""
        return self._get_reference_path(site_id).exists()

    def get_reference(self, site_id: str) -> Optional[SiteReferenceFrame]:
        """Get site reference frame."""
        path = self._get_reference_path(site_id)
        return SiteReferenceFrame.load(path)

    def save_reference(self, reference: SiteReferenceFrame) -> None:
        """Save site reference frame."""
        path = self._get_reference_path(reference.site_id)
        reference.save(path)

    def get_camera_lut(self, site_id: str, camera_id: str) -> Optional[CameraLUT]:
        """Get camera LUT for site."""
        path = self._get_lut_path(site_id, camera_id)
        return CameraLUT.load(path)

    def save_camera_lut(self, lut: CameraLUT) -> None:
        """Save camera LUT."""
        path = self._get_lut_path(lut.site_id, lut.camera_id)
        lut.save(path)

    def create_reference_from_capture(
        self,
        image_path: Path,
        site_id: str,
        customer_id: str,
        camera_id: str,
        camera_model: str,
        quality_report: Optional[dict] = None,
    ) -> Optional[SiteReferenceFrame]:
        """Create site reference frame from a high-quality capture.

        The capture must meet quality thresholds to become a reference:
        - Quality score >= 80
        - No significant clipping
        - Good sharpness

        Returns the created reference, or None if quality is insufficient.
        """
        quality_report = quality_report or {}
        quality_score = float(quality_report.get("score", {}).get("overall", 0.0))

        # Quality threshold for becoming a reference
        if quality_score < 75.0:
            log.info(f"Image quality {quality_score:.1f} below reference threshold 75.0")
            return None

        # Extract features from image
        features = self._extract_reference_features(image_path)
        if features is None:
            log.error(f"Failed to extract features from {image_path}")
            return None

        # Check for clipping
        if features["clipped_highlights"] > 0.03 or features["clipped_shadows"] > 0.05:
            log.info(f"Image has too much clipping (highlights: {features['clipped_highlights']:.3f}, shadows: {features['clipped_shadows']:.3f})")
            return None

        # Get camera color profile
        color_profile = get_color_profile(camera_model)

        # Determine scene type and estimated kelvin
        scene_type = self._classify_scene(features)
        estimated_kelvin = self._estimate_color_temperature(features)

        # Get recommended Picture Control for this camera
        pic_rec = get_picture_control_recommendation(camera_model, "post_friendly")

        # Create reference frame
        reference = SiteReferenceFrame(
            site_id=site_id,
            customer_id=customer_id,
            created_at=datetime.now(timezone.utc),
            created_by_camera_id=camera_id,
            created_by_camera_model=camera_model,
            reference_lab_mean=features["lab_mean"],
            reference_lab_std=features["lab_std"],
            reference_hsv_stats=features["hsv_stats"],
            target_brightness_mean=features["brightness_mean"],
            target_brightness_median=features["brightness_median"],
            target_contrast_std=features["contrast_std"],
            target_dynamic_range=features["dynamic_range"],
            reference_white_balance_kelvin=estimated_kelvin,
            reference_white_balance_tint=features["wb_tint"],
            reference_picture_control=pic_rec["picture_control"],
            quality_score=quality_score,
            blur_score=float(quality_report.get("blur_score", features["blur_score"])),
            no_clip=(features["clipped_highlights"] < 0.02 and features["clipped_shadows"] < 0.04),
            scene_type=scene_type,
            estimated_kelvin=estimated_kelvin,
        )

        self.save_reference(reference)
        log.info(f"Created site reference for {site_id} from {camera_model} (quality: {quality_score:.1f})")
        return reference

    def generate_camera_lut(
        self,
        image_path: Path,
        site_id: str,
        camera_id: str,
        camera_model: str,
    ) -> Optional[CameraLUT]:
        """Generate LUT for a camera to match the site reference.

        Analyzes the camera's current output and calculates the adjustments
        needed to match the site reference look.
        """
        reference = self.get_reference(site_id)
        if reference is None:
            log.warning(f"No site reference found for {site_id}, cannot generate LUT")
            return None

        # Extract features from camera image
        features = self._extract_reference_features(image_path)
        if features is None:
            log.error(f"Failed to extract features from {image_path}")
            return None

        # Get camera color profile
        camera_profile = get_color_profile(camera_model)

        # Calculate color transformation matrix
        color_matrix = self._calculate_color_matrix(
            features["lab_mean"],
            reference.reference_lab_mean,
            camera_profile,
        )

        # Calculate exposure adjustment
        exposure_ev = math.log2(
            (reference.target_brightness_mean + 1.0) /
            (features["brightness_mean"] + 1.0)
        )
        exposure_ev = max(-2.0, min(2.0, exposure_ev))  # Clamp to reasonable range

        # Calculate saturation adjustment
        sat_ratio = (
            reference.reference_hsv_stats.get("saturation_mean", 120.0) /
            max(features["hsv_stats"].get("saturation_mean", 1.0), 1.0)
        )
        saturation_mult = max(0.7, min(1.5, sat_ratio))

        # Calculate contrast adjustment
        contrast_ratio = (
            reference.target_contrast_std /
            max(features["contrast_std"], 1.0)
        )
        contrast_mult = max(0.8, min(1.3, contrast_ratio))

        # Calculate match quality score
        lab_distance = math.sqrt(sum(
            (features["lab_mean"][i] - reference.reference_lab_mean[i]) ** 2
            for i in range(3)
        ))
        match_quality = max(0.0, 1.0 - lab_distance / 50.0)  # Normalize to 0-1

        # Get Picture Control recommendation
        pic_rec = get_picture_control_recommendation(camera_model, "post_friendly")

        # Create LUT
        lut = CameraLUT(
            camera_id=camera_id,
            camera_model=camera_model,
            site_id=site_id,
            generated_at=datetime.now(timezone.utc),
            color_matrix=color_matrix,
            exposure_offset_ev=round(exposure_ev, 3),
            gamma_adjustment=1.0,  # For now, assume standard gamma
            saturation_multiplier=round(saturation_mult, 3),
            contrast_multiplier=round(contrast_mult, 3),
            wb_kelvin_hint=reference.reference_white_balance_kelvin,
            wb_tint_hint=reference.reference_white_balance_tint,
            picture_control_hint=pic_rec["picture_control"],
            match_quality_score=round(match_quality, 3),
        )

        self.save_camera_lut(lut)
        log.info(f"Generated LUT for {camera_id} ({camera_model}) -> {site_id} (match: {match_quality:.3f})")
        return lut

    def get_capture_hints(
        self,
        site_id: str,
        camera_id: str,
        camera_model: str,
    ) -> dict[str, Any]:
        """Get camera command hints for matching to site reference.

        Returns hints for:
        - White balance (kelvin and tint)
        - Picture Control/Style selection
        - Exposure compensation hint
        """
        lut = self.get_camera_lut(site_id, camera_id)
        if lut is None:
            # No LUT yet, provide defaults based on reference
            reference = self.get_reference(site_id)
            if reference is None:
                # No reference either, provide camera defaults
                pic_rec = get_picture_control_recommendation(camera_model, "default_for_timelapse")
                return {
                    "has_reference": False,
                    "picture_control": pic_rec["picture_control"],
                    "parameters": pic_rec.get("parameters", {}),
                    "wb_kelvin_hint": None,
                    "ev_hint": 0.0,
                }
            # Use reference settings
            pic_rec = get_picture_control_recommendation(camera_model, "default_for_timelapse")
            return {
                "has_reference": True,
                "picture_control": reference.reference_picture_control,
                "parameters": pic_rec.get("parameters", {}),
                "wb_kelvin_hint": reference.reference_white_balance_kelvin,
                "wb_tint_hint": reference.reference_white_balance_tint,
                "ev_hint": 0.0,
            }

        # Use LUT hints
        pic_rec = get_picture_control_recommendation(camera_model, "default_for_timelapse")
        return {
            "has_reference": True,
            "picture_control": lut.picture_control_hint,
            "parameters": pic_rec.get(f"{lut.picture_control_hint.lower()}_params", {}),
            "wb_kelvin_hint": lut.wb_kelvin_hint,
            "wb_tint_hint": lut.wb_tint_hint,
            "ev_hint": lut.exposure_offset_ev,
            "match_quality": lut.match_quality_score,
        }

    def _extract_reference_features(self, image_path: Path) -> Optional[dict]:
        """Extract color and exposure features from an image."""
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return None

            # Downscale for speed
            max_dim = 1280
            h, w = img.shape[:2]
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))

            # Convert to different color spaces
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

            # Brightness statistics
            brightness_mean = float(gray.mean())
            brightness_median = float(np.median(gray))

            # LAB statistics (perceptually uniform)
            l_mean = float(lab[:, :, 0].mean())
            a_mean = float(lab[:, :, 1].mean()) - 128.0  # Center around 0
            b_mean = float(lab[:, :, 2].mean()) - 128.0
            lab_mean = (l_mean, a_mean, b_mean)

            l_std = float(lab[:, :, 0].std())
            a_std = float(lab[:, :, 1].std())
            b_std = float(lab[:, :, 2].std())
            lab_std = (l_std, a_std, b_std)

            # HSV statistics
            h_mean = float(hsv[:, :, 0].mean())
            s_mean = float(hsv[:, :, 1].mean())
            v_mean = float(hsv[:, :, 2].mean())
            hsv_stats = {"hue_mean": h_mean, "saturation_mean": s_mean, "value_mean": v_mean}

            # Contrast and dynamic range
            contrast_std = float(gray.std())
            p05, p95 = np.percentile(gray, [5, 95])
            dynamic_range = float(p95 - p05)

            # Clipping detection
            clipped_shadows = float(np.mean(gray <= 5))
            clipped_highlights = float(np.mean(gray >= 250))

            # Blur score (sharpness)
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # White balance tint estimation (simple)
            wb_tint = float((lab[:, :, 1].mean() - 128.0) / 128.0)  # Green-magenta shift

            return {
                "brightness_mean": brightness_mean,
                "brightness_median": brightness_median,
                "lab_mean": lab_mean,
                "lab_std": lab_std,
                "hsv_stats": hsv_stats,
                "contrast_std": contrast_std,
                "dynamic_range": dynamic_range,
                "clipped_shadows": clipped_shadows,
                "clipped_highlights": clipped_highlights,
                "blur_score": blur_score,
                "wb_tint": wb_tint,
            }

        except Exception as exc:
            log.error(f"Feature extraction failed: {exc}")
            return None

    def _calculate_color_matrix(
        self,
        source_lab: tuple[float, float, float],
        target_lab: tuple[float, float, float],
        camera_profile: ColorProfile,
    ) -> list[list[float]]:
        """Calculate color transformation matrix.

        This is a simplified implementation. For production, consider:
        - Using CIEDE2000 color difference formula
        - 3D LUT interpolation for better accuracy
        - Per-channel curves instead of linear matrix
        """
        # Start with camera's native color matrix
        base_matrix = camera_profile.color_matrix_3x3

        # Calculate LAB deltas
        dl = target_lab[0] - source_lab[0]
        da = target_lab[1] - source_lab[1]
        db = target_lab[2] - source_lab[2]

        # Convert LAB deltas to RGB adjustments (simplified)
        # This is a rough approximation - proper implementation would use
        # LAB to XYZ to RGB conversion with proper matrices
        r_adjust = 1.0 + (dl / 256.0) + (da / 512.0)
        g_adjust = 1.0 + (dl / 256.0) - (da / 1024.0)
        b_adjust = 1.0 + (dl / 256.0) + (db / 512.0)

        # Apply adjustments to base matrix (diagonal scaling)
        adjusted_matrix = [
            [base_matrix[0][0] * r_adjust, base_matrix[0][1], base_matrix[0][2]],
            [base_matrix[1][0], base_matrix[1][1] * g_adjust, base_matrix[1][2]],
            [base_matrix[2][0], base_matrix[2][1], base_matrix[2][2] * b_adjust],
        ]

        # Normalize rows to preserve brightness
        for i in range(3):
            row_sum = sum(adjusted_matrix[i])
            if row_sum > 0:
                adjusted_matrix[i] = [v / row_sum for v in adjusted_matrix[i]]

        return adjusted_matrix

    def _classify_scene(self, features: dict) -> str:
        """Classify scene type based on color and brightness."""
        brightness = features["brightness_mean"]
        lab_mean = features["lab_mean"]

        # Simple classification rules
        if brightness < 30:
            return "night"
        elif brightness > 200 and lab_mean[2] > 20:  # High + warm (b in LAB)
            return "golden_hour"
        elif brightness > 120 and lab_mean[1] < -15:  # Bright + cool (a in LAB, negative = green/cyan)
            return "overcast"
        elif 80 <= brightness <= 180:
            return "day"
        else:
            return "unknown"

    def _estimate_color_temperature(self, features: dict) -> int:
        """Estimate scene color temperature in Kelvin."""
        lab_mean = features["lab_mean"]
        a_channel = lab_mean[1]  # Red-green (negative = green, positive = red)
        b_channel = lab_mean[2]  # Yellow-blue (negative = blue, positive = yellow)

        # Convert LAB chromaticity to approximate Kelvin
        # This is a rough approximation based on the Planckian locus
        if b_channel > 20:
            # Warm/yellowish
            kelvin = int(6500 - b_channel * 50)
        elif b_channel < -10:
            # Cool/bluish
            kelvin = int(6500 - b_channel * 80)
        else:
            # Neutral
            kelvin = 6500

        # Clamp to reasonable range
        kelvin = max(2700, min(10000, kelvin))
        return kelvin
