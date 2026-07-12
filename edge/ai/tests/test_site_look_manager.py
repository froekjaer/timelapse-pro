"""
Unit Tests for Site-Wide Look Matching Manager

Tests cover:
- ColorProfile class and color profile lookup
- Picture Control recommendations
- SiteReferenceFrame creation, serialization, deserialization
- CameraLUT generation and application
- SiteLookManager core functionality
- Feature extraction
- Quality threshold validation
- Error handling and edge cases

Run with: pytest -v edge/ai/tests/test_site_look_manager.py
"""
from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from site_look_manager import (
    ColorProfile,
    NIKON_Z30_PROFILE,
    CANON_EOS_PROFILE,
    CAMERA_COLOR_PROFILES,
    get_color_profile,
    PICTURE_CONTROL_RECOMMENDATIONS,
    get_picture_control_recommendation,
    SiteReferenceFrame,
    CameraLUT,
    SiteLookManager,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for test storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config(temp_storage_dir):
    """Sample configuration for SiteLookManager."""
    return {
        "site_look_storage_path": str(temp_storage_dir),
        "reference_quality_threshold": 75.0,
    }


@pytest.fixture
def sample_reference():
    """Sample SiteReferenceFrame for testing."""
    return SiteReferenceFrame(
        site_id="test-site-1",
        customer_id="test-customer",
        created_at=datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc),
        created_by_camera_id="tlp-001",
        created_by_camera_model="Nikon Z30",
        reference_lab_mean=(120.0, 5.0, -3.0),
        reference_lab_std=(15.0, 8.0, 10.0),
        reference_hsv_stats={
            "hue_mean": 120.0,
            "saturation_mean": 90.0,
            "value_mean": 140.0,
        },
        target_brightness_mean=120.0,
        target_brightness_median=118.0,
        target_contrast_std=45.0,
        target_dynamic_range=200.0,
        reference_white_balance_kelvin=5600,
        reference_white_balance_tint=0.0,
        reference_picture_control="Flat",
        quality_score=92.5,
        blur_score=150.0,
        no_clip=True,
        scene_type="day",
        estimated_kelvin=5600,
    )


@pytest.fixture
def sample_lut():
    """Sample CameraLUT for testing."""
    return CameraLUT(
        camera_id="tlp-002",
        camera_model="Canon EOS 2000D",
        site_id="test-site-1",
        generated_at=datetime(2026, 7, 12, 12, 30, 0, tzinfo=timezone.utc),
        color_matrix=[[0.9, 0.05, 0.05], [0.05, 0.9, 0.05], [0.05, 0.05, 0.9]],
        exposure_offset_ev=-0.15,
        gamma_adjustment=1.0,
        saturation_multiplier=1.08,
        contrast_multiplier=1.0,
        wb_kelvin_hint=5600,
        wb_tint_hint=0.0,
        picture_control_hint="Neutral",
        match_quality_score=0.87,
    )


# ============================================================================
# ColorProfile Tests
# ============================================================================

class TestColorProfile:
    """Test ColorProfile dataclass and related functions."""

    def test_nikon_z30_profile_attributes(self):
        """Test Nikon Z30 profile has expected attributes."""
        assert NIKON_Z30_PROFILE.name == "Nikon Z30"
        assert NIKON_Z30_PROFILE.manufacturer == "nikon"
        assert NIKON_Z30_PROFILE.base_gamma == 2.2
        assert len(NIKON_Z30_PROFILE.color_matrix_3x3) == 3
        assert len(NIKON_Z30_PROFILE.supported_picture_controls) == 7
        assert "Flat" in NIKON_Z30_PROFILE.supported_picture_controls
        assert NIKON_Z30_PROFILE.typical_kelvin_range == (2700, 7200)

    def test_canon_eos_profile_attributes(self):
        """Test Canon EOS profile has expected attributes."""
        assert CANON_EOS_PROFILE.name == "Canon EOS 1300D/2000D"
        assert CANON_EOS_PROFILE.manufacturer == "canon"
        assert CANON_EOS_PROFILE.base_gamma == 2.2
        assert len(CANON_EOS_PROFILE.supported_picture_controls) == 7
        assert "Neutral" in CANON_EOS_PROFILE.supported_picture_controls
        assert CANON_EOS_PROFILE.typical_kelvin_range == (2700, 7000)

    def test_get_color_profile_nikon(self):
        """Test getting Nikon color profile."""
        profile = get_color_profile("Nikon Z30")
        assert profile.manufacturer == "nikon"
        assert "Flat" in profile.supported_picture_controls

    def test_get_color_profile_canon(self):
        """Test getting Canon color profile."""
        profile = get_color_profile("Canon EOS 2000D")
        assert profile.manufacturer == "canon"
        assert "Neutral" in profile.supported_picture_controls

    def test_get_color_profile_canon_generic(self):
        """Test getting Canon generic profile."""
        profile = get_color_profile("Canon EOS")
        assert profile.manufacturer == "canon"

    def test_get_color_profile_fallback(self):
        """Test fallback to generic profile for unknown camera."""
        profile = get_color_profile("Unknown Camera Model")
        assert profile.manufacturer == "generic"
        assert profile.name == "Generic sRGB"
        assert len(profile.supported_picture_controls) == 1
        assert "Standard" in profile.supported_picture_controls

    def test_get_color_profile_case_insensitive(self):
        """Test profile lookup is case-insensitive."""
        profile1 = get_color_profile("nikon z30")
        profile2 = get_color_profile("NIKON Z30")
        profile3 = get_color_profile("Nikon Z30")
        assert profile1.name == profile2.name == profile3.name

    def test_color_matrix_format(self):
        """Test color matrix is 3x3."""
        for profile in CAMERA_COLOR_PROFILES.values():
            assert len(profile.color_matrix_3x3) == 3
            for row in profile.color_matrix_3x3:
                assert len(row) == 3
                # Check values are reasonable (0-1 range typically)
                for val in row:
                    assert isinstance(val, (int, float))


# ============================================================================
# Picture Control Tests
# ============================================================================

class TestPictureControlRecommendations:
    """Test Picture Control/Style recommendations."""

    def test_nikon_default_timelapse(self):
        """Test Nikon default recommendation for timelapse."""
        rec = get_picture_control_recommendation("Nikon Z30", "default_for_timelapse")
        assert rec["picture_control"] == "Flat"
        assert "parameters" in rec
        assert rec["parameters"].get("sharpening") == 3

    def test_canon_default_timelapse(self):
        """Test Canon default recommendation for timelapse."""
        rec = get_picture_control_recommendation("Canon EOS 2000D", "default_for_timelapse")
        assert rec["picture_control"] == "Neutral"
        assert "parameters" in rec

    def test_nikon_vivid_colors(self):
        """Test Nikon vivid colors recommendation."""
        rec = get_picture_control_recommendation("Nikon Z30", "vivid_colors")
        assert rec["picture_control"] == "Vivid"

    def test_canon_landscape(self):
        """Test Canon landscape recommendation."""
        rec = get_picture_control_recommendation("Canon EOS", "vivid_colors")
        assert rec["picture_control"] == "Landscape"

    def test_fallback_to_default(self):
        """Test fallback for unknown camera."""
        rec = get_picture_control_recommendation("Unknown Camera")
        assert rec["picture_control"] == "Standard"
        assert rec["parameters"] == {}

    def test_fallback_to_default_scenario(self):
        """Test fallback for unknown scenario."""
        rec = get_picture_control_recommendation("Nikon Z30", "unknown_scenario")
        assert rec["picture_control"] == "Flat"  # Falls back to default_for_timelapse


# ============================================================================
# SiteReferenceFrame Tests
# ============================================================================

class TestSiteReferenceFrame:
    """Test SiteReferenceFrame class."""

    def test_creation(self, sample_reference):
        """Test SiteReferenceFrame creation."""
        assert sample_reference.site_id == "test-site-1"
        assert sample_reference.quality_score == 92.5
        assert sample_reference.no_clip is True
        assert sample_reference.scene_type == "day"

    def test_to_dict(self, sample_reference):
        """Test serialization to dictionary."""
        data = sample_reference.to_dict()
        assert data["site_id"] == "test-site-1"
        assert data["quality_score"] == 92.5
        assert "created_at" in data
        assert isinstance(data["created_at"], str)

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "site_id": "test-site-1",
            "customer_id": "test-customer",
            "created_at": "2026-07-12T12:00:00+00:00",
            "created_by_camera_id": "tlp-001",
            "created_by_camera_model": "Nikon Z30",
            "reference_lab_mean": [120.0, 5.0, -3.0],
            "reference_lab_std": [15.0, 8.0, 10.0],
            "reference_hsv_stats": {"hue_mean": 120.0, "saturation_mean": 90.0, "value_mean": 140.0},
            "target_brightness_mean": 120.0,
            "target_brightness_median": 118.0,
            "target_contrast_std": 45.0,
            "target_dynamic_range": 200.0,
            "reference_white_balance_kelvin": 5600,
            "reference_white_balance_tint": 0.0,
            "reference_picture_control": "Flat",
            "quality_score": 92.5,
            "blur_score": 150.0,
            "no_clip": True,
            "scene_type": "day",
            "estimated_kelvin": 5600,
        }
        ref = SiteReferenceFrame.from_dict(data)
        assert ref.site_id == "test-site-1"
        assert ref.quality_score == 92.5
        assert ref.reference_lab_mean == (120.0, 5.0, -3.0)

    def test_serialization_roundtrip(self, sample_reference):
        """Test serialization and deserialization roundtrip."""
        data = sample_reference.to_dict()
        restored = SiteReferenceFrame.from_dict(data)
        assert restored.site_id == sample_reference.site_id
        assert restored.quality_score == sample_reference.quality_score
        assert restored.reference_lab_mean == sample_reference.reference_lab_mean

    def test_save_and_load(self, sample_reference, temp_storage_dir):
        """Test saving and loading from file."""
        ref_path = temp_storage_dir / "test_reference.json"
        sample_reference.save(ref_path)
        assert ref_path.exists()

        loaded = SiteReferenceFrame.load(ref_path)
        assert loaded is not None
        assert loaded.site_id == sample_reference.site_id
        assert loaded.quality_score == sample_reference.quality_score

    def test_load_missing_file(self, temp_storage_dir):
        """Test loading non-existent file returns None."""
        result = SiteReferenceFrame.load(temp_storage_dir / "nonexistent.json")
        assert result is None

    def test_load_corrupt_file(self, temp_storage_dir):
        """Test loading corrupt file returns None."""
        corrupt_path = temp_storage_dir / "corrupt.json"
        corrupt_path.write_text("not valid json {")
        result = SiteReferenceFrame.load(corrupt_path)
        assert result is None

    def test_quality_threshold_check(self):
        """Test quality score is within valid range."""
        ref = SiteReferenceFrame(
            site_id="test",
            customer_id="test",
            created_at=datetime.now(timezone.utc),
            created_by_camera_id="test",
            created_by_camera_model="test",
            reference_lab_mean=(100, 0, 0),
            reference_lab_std=(10, 10, 10),
            reference_hsv_stats={},
            target_brightness_mean=100,
            target_brightness_median=100,
            target_contrast_std=30,
            target_dynamic_range=150,
            reference_white_balance_kelvin=5500,
            reference_white_balance_tint=0,
            reference_picture_control="Flat",
            quality_score=85.0,  # Should be >= 75
            blur_score=100,
            no_clip=True,
            scene_type="day",
            estimated_kelvin=5500,
        )
        assert ref.quality_score >= 75.0


# ============================================================================
# CameraLUT Tests
# ============================================================================

class TestCameraLUT:
    """Test CameraLUT class."""

    def test_creation(self, sample_lut):
        """Test CameraLUT creation."""
        assert sample_lut.camera_id == "tlp-002"
        assert sample_lut.match_quality_score == 0.87
        assert sample_lut.exposure_offset_ev == -0.15

    def test_to_dict(self, sample_lut):
        """Test serialization to dictionary."""
        data = sample_lut.to_dict()
        assert data["camera_id"] == "tlp-002"
        assert data["match_quality_score"] == 0.87
        assert data["exposure_offset_ev"] == -0.15

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "camera_id": "tlp-002",
            "camera_model": "Canon EOS 2000D",
            "site_id": "test-site-1",
            "generated_at": "2026-07-12T12:30:00+00:00",
            "color_matrix": [[0.9, 0.05, 0.05], [0.05, 0.9, 0.05], [0.05, 0.05, 0.9]],
            "exposure_offset_ev": -0.15,
            "gamma_adjustment": 1.0,
            "saturation_multiplier": 1.08,
            "contrast_multiplier": 1.0,
            "wb_kelvin_hint": 5600,
            "wb_tint_hint": 0.0,
            "picture_control_hint": "Neutral",
            "match_quality_score": 0.87,
        }
        lut = CameraLUT.from_dict(data)
        assert lut.camera_id == "tlp-002"
        assert lut.match_quality_score == 0.87

    def test_serialization_roundtrip(self, sample_lut):
        """Test serialization and deserialization roundtrip."""
        data = sample_lut.to_dict()
        restored = CameraLUT.from_dict(data)
        assert restored.camera_id == sample_lut.camera_id
        assert restored.match_quality_score == sample_lut.match_quality_score

    def test_save_and_load(self, sample_lut, temp_storage_dir):
        """Test saving and loading from file."""
        lut_path = temp_storage_dir / "test_lut.json"
        sample_lut.save(lut_path)
        assert lut_path.exists()

        loaded = CameraLUT.load(lut_path)
        assert loaded is not None
        assert loaded.camera_id == sample_lut.camera_id

    def test_load_missing_file(self, temp_storage_dir):
        """Test loading non-existent file returns None."""
        result = CameraLUT.load(temp_storage_dir / "nonexistent.json")
        assert result is None

    def test_color_matrix_format(self, sample_lut):
        """Test color matrix is 3x3."""
        assert len(sample_lut.color_matrix) == 3
        for row in sample_lut.color_matrix:
            assert len(row) == 3

    def test_exposure_clamping(self):
        """Test exposure values are clamped to reasonable range."""
        lut = CameraLUT(
            camera_id="test",
            camera_model="test",
            site_id="test",
            generated_at=datetime.now(timezone.utc),
            color_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            exposure_offset_ev=-1.5,  # Within range
            gamma_adjustment=1.0,
            saturation_multiplier=1.0,
            contrast_multiplier=1.0,
            wb_kelvin_hint=None,
            wb_tint_hint=0.0,
            picture_control_hint="Standard",
            match_quality_score=0.8,
        )
        assert -2.0 <= lut.exposure_offset_ev <= 2.0


# ============================================================================
# SiteLookManager Tests
# ============================================================================

class TestSiteLookManager:
    """Test SiteLookManager class."""

    def test_initialization(self, sample_config):
        """Test manager initialization."""
        manager = SiteLookManager(sample_config)
        assert manager._storage_base == Path(sample_config["site_look_storage_path"])
        assert manager._storage_base.exists()

    def test_storage_path_creation(self, temp_storage_dir):
        """Test storage directory is created."""
        storage_path = temp_storage_dir / "new_storage"
        config = {"site_look_storage_path": str(storage_path)}
        manager = SiteLookManager(config)
        assert storage_path.exists()

    def test_has_reference_no_reference(self, sample_config):
        """Test has_reference when no reference exists."""
        manager = SiteLookManager(sample_config)
        assert manager.has_reference("test-site") is False

    def test_save_and_get_reference(self, sample_config, sample_reference):
        """Test saving and retrieving reference."""
        manager = SiteLookManager(sample_config)
        manager.save_reference(sample_reference)
        assert manager.has_reference("test-site-1") is True

        retrieved = manager.get_reference("test-site-1")
        assert retrieved is not None
        assert retrieved.site_id == sample_reference.site_id
        assert retrieved.quality_score == sample_reference.quality_score

    def test_save_and_get_camera_lut(self, sample_config, sample_lut):
        """Test saving and retrieving camera LUT."""
        manager = SiteLookManager(sample_config)
        manager.save_camera_lut(sample_lut)

        retrieved = manager.get_camera_lut("test-site-1", "tlp-002")
        assert retrieved is not None
        assert retrieved.camera_id == sample_lut.camera_id
        assert retrieved.match_quality_score == sample_lut.match_quality_score

    def test_get_reference_path(self, sample_config):
        """Test reference path generation."""
        manager = SiteLookManager(sample_config)
        path = manager._get_reference_path("test-site")
        assert "test-site" in str(path)
        assert path.suffix == ".json"

    def test_get_lut_path(self, sample_config):
        """Test LUT path generation."""
        manager = SiteLookManager(sample_config)
        path = manager._get_lut_path("test-site", "camera-1")
        assert "test-site" in str(path)
        assert "camera-1" in str(path)
        assert path.suffix == ".json"


# ============================================================================
# Feature Extraction Tests
# ============================================================================

class TestFeatureExtraction:
    """Test feature extraction from images."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    @pytest.fixture
    def sample_image(self, temp_storage_dir):
        """Create a sample test image."""
        # Create a simple test image (gradient)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(640):
            img[:, i] = [i * 255 // 640, 128, 128 - i * 128 // 640]

        image_path = temp_storage_dir / "test_image.jpg"
        import cv2
        cv2.imwrite(str(image_path), img)
        return image_path

    def test_extract_features_valid_image(self, manager, sample_image):
        """Test feature extraction from valid image."""
        features = manager._extract_reference_features(sample_image)
        assert features is not None
        assert "brightness_mean" in features
        assert "lab_mean" in features
        assert "hsv_stats" in features
        assert "contrast_std" in features
        assert "clipped_shadows" in features
        assert "clipped_highlights" in features
        assert "blur_score" in features

    def test_extract_features_missing_file(self, manager):
        """Test feature extraction from missing file."""
        result = manager._extract_reference_features(Path("/nonexistent/image.jpg"))
        assert result is None

    def test_feature_values_valid_range(self, manager, sample_image):
        """Test extracted features are in valid ranges."""
        features = manager._extract_reference_features(sample_image)
        assert 0 <= features["brightness_mean"] <= 255
        assert 0 <= features["contrast_std"] <= 128
        assert 0.0 <= features["clipped_shadows"] <= 1.0
        assert 0.0 <= features["clipped_highlights"] <= 1.0
        assert features["blur_score"] >= 0

    def test_lab_values_format(self, manager, sample_image):
        """Test LAB values are properly formatted."""
        features = manager._extract_reference_features(sample_image)
        lab_mean = features["lab_mean"]
        assert len(lab_mean) == 3
        assert all(isinstance(v, (int, float)) for v in lab_mean)

        lab_std = features["lab_std"]
        assert len(lab_std) == 3
        assert all(isinstance(v, (int, float)) for v in lab_std)

    def test_dynamic_range_calculation(self, manager, sample_image):
        """Test dynamic range is calculated correctly."""
        features = manager._extract_reference_features(sample_image)
        assert features["dynamic_range"] > 0
        assert features["dynamic_range"] <= 255


# ============================================================================
# Scene Classification Tests
# ============================================================================

class TestSceneClassification:
    """Test scene type classification."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    def test_classify_night_scene(self, manager):
        """Test night scene classification."""
        features = {"brightness_mean": 20, "lab_mean": (80, 0, 0)}
        scene = manager._classify_scene(features)
        assert scene == "night"

    def test_classify_golden_hour(self, manager):
        """Test golden hour classification."""
        features = {"brightness_mean": 210, "lab_mean": (120, 5, 25)}
        scene = manager._classify_scene(features)
        assert scene == "golden_hour"

    def test_classify_overcast(self, manager):
        """Test overcast scene classification."""
        features = {"brightness_mean": 150, "lab_mean": (130, -20, 0)}
        scene = manager._classify_scene(features)
        assert scene == "overcast"

    def test_classify_day(self, manager):
        """Test normal day classification."""
        features = {"brightness_mean": 120, "lab_mean": (120, 0, 0)}
        scene = manager._classify_scene(features)
        assert scene == "day"

    def test_classify_unknown(self, manager):
        """Test unknown scene classification."""
        features = {"brightness_mean": 50, "lab_mean": (100, 0, 0)}
        scene = manager._classify_scene(features)
        assert scene == "unknown"


# ============================================================================
# Color Temperature Estimation Tests
# ============================================================================

class TestColorTemperatureEstimation:
    """Test color temperature estimation in Kelvin."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    def test_warm_scene_high_kelvin(self, manager):
        """Test warm scene results in lower Kelvin."""
        features = {"lab_mean": (120, 0, 30)}
        kelvin = manager._estimate_color_temperature(features)
        assert kelvin < 6000
        assert kelvin >= 2700

    def test_cool_scene_low_kelvin(self, manager):
        """Test cool scene results in higher Kelvin."""
        features = {"lab_mean": (120, 0, -15)}
        kelvin = manager._estimate_color_temperature(features)
        assert kelvin > 6500
        assert kelvin <= 10000

    def test_neutral_scene_mid_kelvin(self, manager):
        """Test neutral scene results in mid-range Kelvin."""
        features = {"lab_mean": (120, 0, 0)}
        kelvin = manager._estimate_color_temperature(features)
        assert kelvin == 6500

    def test_kelvin_clamping(self, manager):
        """Test Kelvin is clamped to valid range."""
        features = {"lab_mean": (120, 0, 100)}  # Very warm
        kelvin = manager._estimate_color_temperature(features)
        assert kelvin >= 2700
        assert kelvin <= 10000


# ============================================================================
# Quality Threshold Tests
# ============================================================================

class TestQualityThresholds:
    """Test quality threshold validation."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    @pytest.fixture
    def high_quality_image(self, temp_storage_dir):
        """Create a high-quality test image."""
        img = np.random.randint(100, 180, (480, 640, 3), dtype=np.uint8)
        path = temp_storage_dir / "high_quality.jpg"
        import cv2
        cv2.imwrite(str(path), img)
        return path

    def test_create_reference_high_quality(self, manager, high_quality_image):
        """Test reference creation from high-quality image."""
        quality_report = {"score": {"overall": 85.0}}
        ref = manager.create_reference_from_capture(
            image_path=high_quality_image,
            site_id="test-site",
            customer_id="test-customer",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
            quality_report=quality_report,
        )
        assert ref is not None
        assert ref.site_id == "test-site"
        assert ref.quality_score >= 75.0

    def test_create_reference_low_quality_rejected(self, manager, temp_storage_dir):
        """Test low-quality image is rejected for reference."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        path = temp_storage_dir / "low_quality.jpg"
        import cv2
        cv2.imwrite(str(path), img)

        quality_report = {"score": {"overall": 60.0}}
        ref = manager.create_reference_from_capture(
            image_path=path,
            site_id="test-site",
            customer_id="test-customer",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
            quality_report=quality_report,
        )
        assert ref is None

    def test_create_reference_below_threshold(self, manager, high_quality_image):
        """Test reference creation fails below 75.0 threshold."""
        quality_report = {"score": {"overall": 74.9}}
        ref = manager.create_reference_from_capture(
            image_path=high_quality_image,
            site_id="test-site",
            customer_id="test-customer",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
            quality_report=quality_report,
        )
        assert ref is None

    def test_create_reference_exactly_threshold(self, manager, high_quality_image):
        """Test reference creation succeeds at exactly 75.0 threshold."""
        quality_report = {"score": {"overall": 75.0}}
        ref = manager.create_reference_from_capture(
            image_path=high_quality_image,
            site_id="test-site",
            customer_id="test-customer",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
            quality_report=quality_report,
        )
        assert ref is not None


# ============================================================================
# Capture Hints Tests
# ============================================================================

class TestCaptureHints:
    """Test capture hints generation."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    def test_hints_no_reference_no_lut(self, manager):
        """Test hints when no reference exists."""
        hints = manager.get_capture_hints(
            site_id="test-site",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
        )
        assert hints["has_reference"] is False
        assert "picture_control" in hints
        assert hints["picture_control"] == "Flat"  # Nikon default for timelapse
        assert hints["wb_kelvin_hint"] is None

    def test_hints_with_reference(self, manager, sample_reference):
        """Test hints when reference exists but no LUT."""
        manager.save_reference(sample_reference)
        hints = manager.get_capture_hints(
            site_id="test-site-1",
            camera_id="tlp-002",
            camera_model="Canon EOS 2000D",
        )
        assert hints["has_reference"] is True
        assert hints["wb_kelvin_hint"] == 5600
        assert "parameters" in hints

    def test_hints_with_lut(self, manager, sample_reference, sample_lut):
        """Test hints when LUT exists."""
        manager.save_reference(sample_reference)
        manager.save_camera_lut(sample_lut)
        hints = manager.get_capture_hints(
            site_id="test-site-1",
            camera_id="tlp-002",
            camera_model="Canon EOS 2000D",
        )
        assert hints["has_reference"] is True
        assert hints["wb_kelvin_hint"] == 5600
        assert hints["ev_hint"] == -0.15
        assert "match_quality" in hints
        assert hints["match_quality"] == 0.87


# ============================================================================
# Color Matrix Calculation Tests
# ============================================================================

class TestColorMatrixCalculation:
    """Test color transformation matrix calculation."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    def test_color_matrix_dimensions(self, manager):
        """Test color matrix is 3x3."""
        source_lab = (120.0, 0.0, 0.0)
        target_lab = (125.0, 2.0, -1.0)
        profile = get_color_profile("Nikon Z30")
        matrix = manager._calculate_color_matrix(source_lab, target_lab, profile)
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)

    def test_color_matrix_normalization(self, manager):
        """Test color matrix rows are normalized."""
        source_lab = (120.0, 5.0, -3.0)
        target_lab = (125.0, 7.0, -2.0)
        profile = get_color_profile("Canon EOS 2000D")
        matrix = manager._calculate_color_matrix(source_lab, target_lab, profile)
        for row in matrix:
            row_sum = sum(row)
            # Each row should sum to approximately 1 after normalization
            if row_sum > 0:
                assert abs(row_sum - 1.0) < 0.01


# ============================================================================
# LUT Generation Tests
# ============================================================================

class TestLUTGeneration:
    """Test LUT generation functionality."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    @pytest.fixture
    def sample_image(self, temp_storage_dir):
        """Create a sample test image."""
        img = np.random.randint(80, 180, (480, 640, 3), dtype=np.uint8)
        path = temp_storage_dir / "test_capture.jpg"
        import cv2
        cv2.imwrite(str(path), img)
        return path

    def test_generate_lut_no_reference(self, manager, sample_image):
        """Test LUT generation fails when no reference exists."""
        lut = manager.generate_camera_lut(
            image_path=sample_image,
            site_id="test-site",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
        )
        assert lut is None

    def test_generate_lut_with_reference(self, manager, sample_image, sample_reference):
        """Test LUT generation with reference."""
        manager.save_reference(sample_reference)
        lut = manager.generate_camera_lut(
            image_path=sample_image,
            site_id="test-site-1",
            camera_id="tlp-002",
            camera_model="Canon EOS 2000D",
        )
        assert lut is not None
        assert lut.camera_id == "tlp-002"
        assert lut.site_id == "test-site-1"
        assert 0.0 <= lut.match_quality_score <= 1.0

    def test_lut_values_valid_ranges(self, manager, sample_image, sample_reference):
        """Test LUT values are in valid ranges."""
        manager.save_reference(sample_reference)
        lut = manager.generate_camera_lut(
            image_path=sample_image,
            site_id="test-site-1",
            camera_id="tlp-002",
            camera_model="Canon EOS 2000D",
        )
        assert -2.0 <= lut.exposure_offset_ev <= 2.0
        assert 0.5 <= lut.saturation_multiplier <= 1.5
        assert 0.5 <= lut.contrast_multiplier <= 1.5
        assert 0.0 <= lut.match_quality_score <= 1.0


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def manager(self, sample_config):
        return SiteLookManager(sample_config)

    def test_create_reference_invalid_path(self, manager):
        """Test reference creation with invalid image path."""
        ref = manager.create_reference_from_capture(
            image_path=Path("/nonexistent/image.jpg"),
            site_id="test-site",
            customer_id="test-customer",
            camera_id="tlp-001",
            camera_model="Nikon Z30",
            quality_report={"score": {"overall": 90.0}},
        )
        assert ref is None

    def test_generate_lut_invalid_path(self, manager, sample_reference):
        """Test LUT generation with invalid image path."""
        manager.save_reference(sample_reference)
        lut = manager.generate_camera_lut(
            image_path=Path("/nonexistent/image.jpg"),
            site_id="test-site-1",
            camera_id="tlp-002",
            camera_model="Canon EOS 2000D",
        )
        assert lut is None

    def test_get_reference_from_corrupt_file(self, temp_storage_dir):
        """Test loading reference from corrupt file."""
        corrupt_path = temp_storage_dir / "test-site-1_reference.json"
        corrupt_path.write_text("corrupt data {")
        manager = SiteLookManager({"site_look_storage_path": str(temp_storage_dir)})
        ref = manager.get_reference("test-site-1")
        assert ref is None


# ============================================================================
# Camera-Specific Features Tests
# ============================================================================

class TestCameraSpecificFeatures:
    """Test camera-specific functionality."""

    def test_nikon_flat_timelapse_recommendation(self):
        """Test Nikon Z30 Flat recommendation for timelapse."""
        rec = get_picture_control_recommendation("Nikon Z30", "default_for_timelapse")
        assert rec["picture_control"] == "Flat"
        assert rec["parameters"]["sharpening"] == 3
        assert rec["parameters"]["contrast"] == 0
        assert rec["parameters"]["saturation"] == 0

    def test_canon_neutral_timelapse_recommendation(self):
        """Test Canon Neutral recommendation for timelapse."""
        rec = get_picture_control_recommendation("Canon EOS 2000D", "default_for_timelapse")
        assert rec["picture_control"] == "Neutral"
        assert rec["parameters"]["sharpness"] == 2
        assert rec["parameters"]["contrast"] == 1
        assert rec["parameters"]["saturation"] == 1

    def test_nikon_supported_picture_controls(self):
        """Test Nikon Z30 supports expected Picture Controls."""
        profile = get_color_profile("Nikon Z30")
        assert "Flat" in profile.supported_picture_controls
        assert "Standard" in profile.supported_picture_controls
        assert "Vivid" in profile.supported_picture_controls
        assert "Portrait" in profile.supported_picture_controls
        assert "Landscape" in profile.supported_picture_controls

    def test_canon_supported_picture_styles(self):
        """Test Canon EOS supports expected Picture Styles."""
        profile = get_color_profile("Canon EOS 2000D")
        assert "Neutral" in profile.supported_picture_controls
        assert "Standard" in profile.supported_picture_controls
        assert "Portrait" in profile.supported_picture_controls
        assert "Landscape" in profile.supported_picture_controls
        assert "Faithful" in profile.supported_picture_controls


# ============================================================================
# Integration with autonomous_optimizer Tests
# ============================================================================

class TestAutonomousOptimizerIntegration:
    """Test integration with autonomous_optimizer module."""

    def test_module_imports(self):
        """Test module can be imported by autonomous_optimizer."""
        import sys
        from edge.ai import site_look_manager
        assert hasattr(site_look_manager, 'SiteLookManager')
        assert hasattr(site_look_manager, 'SiteReferenceFrame')
        assert hasattr(site_look_manager, 'CameraLUT')

    def test_exported_functions(self):
        """Test key functions are exported."""
        from site_look_manager import (
            get_color_profile,
            get_picture_control_recommendation,
            SiteLookManager,
        )
        assert callable(get_color_profile)
        assert callable(get_picture_control_recommendation)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
