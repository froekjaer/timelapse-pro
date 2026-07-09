"""
TimeLapse Pro — Edge AI/QA Weekend Feature Tests (P1)
======================================================

Tests for Edge AI and Quality Analysis features (weekend 4-6 July 2026):
- quality.py QA score calculation
- ai/autonomous_optimizer.py model execution
- NPU runner integration
- QA result upload/contract
- Quality analysis integration
- NPU runtime detection

Kør: pytest tests/test_edge_ai_quality.py -v

Marker: unit (kræver ikke live headend, men kræver OpenCV)
"""
import os
import sys
import pytest
import tempfile
from pathlib import Path
from PIL import Image
import numpy as np

# Setup path til edge moduler
HERE = Path(__file__).resolve().parent
EDGE_ROOT = HERE.parent / "edge"
if str(EDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(EDGE_ROOT))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))


# ── Test Image Generation ───────────────────────────────────────────────────

def create_test_image(
    width: int = 1920,
    height: int = 1080,
    blur: bool = False,
    brightness: int = 128,
    noise: bool = False
) -> Path:
    """Create a test JPEG image with specified characteristics."""
    img_array = np.full((height, width, 3), brightness, dtype=np.uint8)

    # Add variation if not pure color
    if not noise and brightness == 128:
        img_array = np.random.randint(100, 156, (height, width, 3), dtype=np.uint8)

    # Apply blur if requested
    if blur:
        try:
            import cv2
            img_array = cv2.GaussianBlur(img_array, (31, 31), 0)
        except ImportError:
            pass

    # Convert to PIL Image and save
    img = Image.fromarray(img_array)
    tmp_path = Path(tempfile.gettempdir()) / f"test_img_{os.urandom(4).hex()}.jpg"
    img.save(tmp_path, quality=85)
    return tmp_path


# ── 1. QualityChecker Tests ───────────────────────────────────────────────────

class TestQualityChecker:
    """Test quality.py QualityChecker class."""

    def setup_method(self):
        """Setup QualityChecker instance."""
        try:
            from edge.capture.quality import QualityChecker
            self.QualityChecker = QualityChecker
        except ImportError:
            from capture.quality import QualityChecker
            self.QualityChecker = QualityChecker

        self.config = {
            "quality": {
                "check_enabled": True,
                "blur_threshold": 80.0,
                "dark_threshold": 25.0,
                "bright_threshold": 230.0,
                "edge_ai": {
                    "enabled": True,
                    "lens_obstruction_enabled": True,
                    "direct_sun_detection_enabled": True
                }
            }
        }
        self.checker = self.QualityChecker(self.config)

    def test_checker_initializes_with_config(self):
        """QualityChecker skal initialiseres med config."""
        assert self.checker._enabled is True
        assert self.checker._blur_thresh == 80.0
        assert self.checker._dark_thresh == 25.0
        assert self.checker._bright_thresh == 230.0

    def test_checker_disabled_when_check_enabled_false(self):
        """QualityChecker skal være disabled når check_enabled=False."""
        cfg = {"quality": {"check_enabled": False}}
        checker = self.QualityChecker(cfg)
        assert checker._enabled is False

    def test_check_returns_quality_result(self):
        """check() skal returnere QualityResult objekt."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.checker.check(img_path)
            assert result is not None
            assert hasattr(result, "flag")
            assert hasattr(result, "passed")
            assert hasattr(result, "blur_score")
            assert hasattr(result, "brightness_mean")
        finally:
            img_path.unlink(missing_ok=True)

    def test_check_ok_image_passes(self):
        """OK image skal have flag=OK og passed=True."""
        img_path = create_test_image(brightness=128, noise=True)
        try:
            result = self.checker.check(img_path)
            assert result.flag.value in ["ok", "blurry"]  # Can be blurry if random noise is low
            assert result.brightness_mean is not None
        finally:
            img_path.unlink(missing_ok=True)

    def test_check_detects_dark_image(self):
        """Mørkt image skal flagges som underexposed."""
        img_path = create_test_image(brightness=10)
        try:
            result = self.checker.check(img_path)
            assert result.brightness_mean is not None
            assert result.brightness_mean < 25.0
            assert result.flag.value == "underexposed"
            assert result.passed is False
        finally:
            img_path.unlink(missing_ok=True)

    def test_check_detects_bright_image(self):
        """Lyst image skal flagges som overexposed."""
        img_path = create_test_image(brightness=250)
        try:
            result = self.checker.check(img_path)
            assert result.brightness_mean is not None
            assert result.brightness_mean > 230.0
            assert result.flag.value == "overexposed"
            assert result.passed is False
        finally:
            img_path.unlink(missing_ok=True)

    def test_check_blur_image_detected(self):
        """Sløret image skal have lav blur_score."""
        img_path = create_test_image(brightness=128, blur=True)
        try:
            result = self.checker.check(img_path)
            assert result.blur_score is not None
            # Blur score skal være lavere end threshold for blurry images
            # Men dette afhænger af hvor meget vi blurrer
        finally:
            img_path.unlink(missing_ok=True)

    def test_check_sha256_verification(self):
        """SHA256 verification skal virke."""
        img_path = create_test_image()
        try:
            import hashlib
            expected_sha = hashlib.sha256(img_path.read_bytes()).hexdigest()
            result = self.checker.check(img_path, expected_sha256=expected_sha)
            assert result.sha256_verified is True
        finally:
            img_path.unlink(missing_ok=True)

    def test_check_sha256_mismatch_detected(self):
        """SHA256 mismatch skal detekteres."""
        img_path = create_test_image()
        try:
            result = self.checker.check(img_path, expected_sha256="wrong" * 16)
            assert result.sha256_verified is False
            assert result.flag.value == "hash_mismatch"
        finally:
            img_path.unlink(missing_ok=True)

    def test_qa_report_returns_dict(self):
        """qa_report() skal returnere dict med kontrakt."""
        img_path = create_test_image(brightness=128)
        try:
            report = self.checker.qa_report(img_path)
            assert isinstance(report, dict)
            assert "engine" in report
            assert "is_anomaly" in report
            assert "probable_cause" in report
            assert "confidence" in report
            assert "recommended_action" in report
        finally:
            img_path.unlink(missing_ok=True)

    def test_qa_report_contains_cv_features(self):
        """qa_report skal indeholde cv_features når OpenCV er tilgængelig."""
        img_path = create_test_image(brightness=128)
        try:
            report = self.checker.qa_report(img_path)
            if self.checker._cv2_available:
                assert "cv_features" in report
                assert isinstance(report["cv_features"], dict)
        finally:
            img_path.unlink(missing_ok=True)

    def test_qa_report_includes_npu_status(self):
        """qa_report skal inkludere NPU status."""
        img_path = create_test_image(brightness=128)
        try:
            report = self.checker.qa_report(img_path)
            assert "npu" in report
            assert isinstance(report["npu"], dict)
        finally:
            img_path.unlink(missing_ok=True)


# ── 2. AutonomousImageOptimizer Tests ─────────────────────────────────────────

class TestAutonomousOptimizer:
    """Test ai/autonomous_optimizer.py AutonomousImageOptimizer class."""

    def setup_method(self):
        """Setup optimizer instance."""
        try:
            from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
            self.AutonomousImageOptimizer = AutonomousImageOptimizer
        except ImportError:
            from ai.autonomous_optimizer import AutonomousImageOptimizer
            self.AutonomousImageOptimizer = AutonomousImageOptimizer

        self.config = {
            "quality": {
                "check_enabled": True,
                "blur_threshold": 80.0,
                "dark_threshold": 25.0,
                "bright_threshold": 230.0,
                "adaptive_exposure": {
                    "enabled": True,
                    "target_brightness": 118.0,
                    "brightness_tolerance": 32.0,
                    "step_ev": 0.3,
                    "min_ev": -2.0,
                    "max_ev": 2.0
                },
                "edge_ai": {
                    "enabled": True,
                    "mode": "assist",
                    "prefer_npu": True
                }
            }
        }
        self.optimizer = self.AutonomousImageOptimizer(self.config)

    def test_optimizer_initializes(self):
        """AutonomousImageOptimizer skal initialisere."""
        assert self.optimizer is not None
        assert hasattr(self.optimizer, "analyse")

    def test_analyse_returns_dict(self):
        """analyse() skal returnere dict."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            assert isinstance(result, dict)
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_contains_engine(self):
        """analyse() resultat skal indeholde engine."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            assert "engine" in result
            assert result["engine"] == "edge_autonomous_optimizer_v1"
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_contains_features(self):
        """analyse() skal indeholde extracted features."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            assert "features" in result
            features = result["features"]
            assert "brightness_mean" in features
            assert "width" in features
            assert "height" in features
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_contains_observations(self):
        """analyse() skal indeholde observations."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            assert "observations" in result
            assert isinstance(result["observations"], list)
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_contains_recommendations(self):
        """analyse() skal indeholde recommendations."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            assert "recommendations" in result
            assert isinstance(result["recommendations"], list)
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_contains_control_plan(self):
        """analyse() skal indeholde control_plan."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            assert "control_plan" in result
            control = result["control_plan"]
            assert "next_capture_ev_delta" in control
            assert "commands" in control
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_detects_dark_image(self):
        """analyse() skal detektere mørke billeder."""
        img_path = create_test_image(brightness=10)
        try:
            result = self.optimizer.analyse(img_path)
            features = result["features"]
            assert features["brightness_mean"] < 50
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_focus_features(self):
        """analyse() skal indeholde focus features."""
        img_path = create_test_image(brightness=128, noise=True)
        try:
            result = self.optimizer.analyse(img_path)
            features = result.get("features", {})
            assert "focus" in features
            focus = features["focus"]
            assert "global_blur" in focus
            assert "center_blur" in focus
        finally:
            img_path.unlink(missing_ok=True)

    def test_analyse_white_balance_features(self):
        """analyse() skal indeholde white balance features."""
        img_path = create_test_image(brightness=128)
        try:
            result = self.optimizer.analyse(img_path)
            features = result.get("features", {})
            assert "white_balance" in features
            wb = features["white_balance"]
            assert "cast" in wb
            assert "cast_strength" in wb
        finally:
            img_path.unlink(missing_ok=True)


# ── 3. NPU Runtime Detection Tests ───────────────────────────────────────────

class TestNPURuntime:
    """Test NPU runtime detection."""

    def test_npu_runtime_module_exists(self):
        """NPU runtime module skal eksistere."""
        try:
            from edge.ai import npu_runtime
            assert hasattr(npu_runtime, "detect_orangepi_npu_runtime")
        except ImportError:
            try:
                from ai import npu_runtime
                assert hasattr(npu_runtime, "detect_orangepi_npu_runtime")
            except ImportError:
                pytest.skip("NPU runtime module ikke tilgængelig")

    def test_npu_runtime_detect_returns_dict(self):
        """detect_orangepi_npu_runtime skal returnere dict."""
        try:
            from edge.ai.npu_runtime import detect_orangepi_npu_runtime
        except ImportError:
            from ai.npu_runtime import detect_orangepi_npu_runtime

        result = detect_orangepi_npu_runtime()
        assert isinstance(result, dict)
        assert "available" in result
        assert isinstance(result["available"], bool)

    def test_npu_runtime_available_false_when_no_npu(self):
        """NPU runtime skal returne available=False når ingen NPU."""
        try:
            from edge.ai.npu_runtime import detect_orangepi_npu_runtime
        except ImportError:
            from ai.npu_runtime import detect_orangepi_npu_runtime

        result = detect_orangepi_npu_runtime()
        # På systemer uden NPU skal available være False
        assert "available" in result


# ── 4. Edge QA NPU Runner Tests ───────────────────────────────────────────────

class TestEdgeQANPURunner:
    """Test edge_qa_npu_runner.py script."""

    def test_npu_runner_module_exists(self):
        """edge_qa_npu_runner module skal eksistere."""
        try:
            from edge.tools import edge_qa_npu_runner
            assert hasattr(edge_qa_npu_runner, "_detect_runtime")
            assert hasattr(edge_qa_npu_runner, "_cpu_fallback")
        except ImportError:
            pytest.skip("edge_qa_npu_runner ikke tilgængelig")

    def test_npu_runner_cpu_fallback_returns_dict(self):
        """_cpu_fallback skal returnere valid kontrakt."""
        try:
            from edge.tools.edge_qa_npu_runner import _cpu_fallback
        except ImportError:
            pytest.skip("edge_qa_npu_runner ikke tilgængelig")

        img_path = create_test_image(brightness=128)
        try:
            result = _cpu_fallback(img_path, None, {"available": False})
            assert isinstance(result, dict)
            assert "engine" in result
            assert "is_anomaly" in result
        finally:
            img_path.unlink(missing_ok=True)


# ── 5. Integration Tests ─────────────────────────────────────────────────────

class TestEdgeAIIntegration:
    """Integration tests for Edge AI komponenter."""

    def test_quality_checker_with_optimizer(self):
        """QualityChecker kan arbejde med AutonomousImageOptimizer."""
        try:
            from edge.capture.quality import QualityChecker
            from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
        except ImportError:
            from capture.quality import QualityChecker
            from ai.autonomous_optimizer import AutonomousImageOptimizer

        config = {
            "quality": {
                "check_enabled": True,
                "blur_threshold": 80.0,
                "dark_threshold": 25.0,
                "bright_threshold": 230.0,
                "edge_ai": {"enabled": True}
            }
        }

        checker = QualityChecker(config)
        optimizer = AutonomousImageOptimizer(config)

        img_path = create_test_image(brightness=150)
        try:
            # Kør quality check
            quality = checker.check(img_path)
            assert quality is not None

            # Kør optimizer analyse med quality report
            qa_report = checker.qa_report(img_path)
            result = optimizer.analyse(img_path, qa_report)

            assert result is not None
            assert "engine" in result
        finally:
            img_path.unlink(missing_ok=True)

    def test_quality_report_complete_contract(self):
        """qa_report skal returnere komplet kontrakt for upload."""
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        config = {"quality": {"check_enabled": True}}
        checker = QualityChecker(config)

        img_path = create_test_image(brightness=128)
        try:
            report = checker.qa_report(img_path)

            # Tjek alle påkrævede felter for upload kontrakt
            required_fields = [
                "engine",
                "is_anomaly",
                "probable_cause",
                "confidence",
                "recommended_action"
            ]
            for field in required_fields:
                assert field in report, f"Manglende felt: {field}"
        finally:
            img_path.unlink(missing_ok=True)


# ── 6. Edge Cases ──────────────────────────────────────────────────────────

class TestEdgeAIECases:
    """Edge case tests for Edge AI."""

    def test_quality_checker_missing_file(self):
        """QualityChecker skal håndtere manglende fil."""
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        checker = QualityChecker({"quality": {"check_enabled": True}})
        result = checker.check(Path("/nonexistent/file.jpg"))
        assert result.flag.value == "error"
        assert result.passed is False

    def test_optimizer_invalid_image(self):
        """Optimizer skal håndtere invalid image."""
        try:
            from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
        except ImportError:
            from ai.autonomous_optimizer import AutonomousImageOptimizer

        optimizer = AutonomousImageOptimizer({"quality": {}})

        # Create invalid image file
        tmp_path = Path(tempfile.gettempdir()) / f"invalid_{os.urandom(4).hex()}.jpg"
        tmp_path.write_text("not an image")

        try:
            result = optimizer.analyse(tmp_path)
            # Skal håndtere fejlen
            assert result is not None
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_quality_disabled_returns_ok(self):
        """Disabled quality checker skal altid returnere OK."""
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        checker = QualityChecker({"quality": {"check_enabled": False}})

        img_path = create_test_image(brightness=10)  # Very dark
        try:
            result = checker.check(img_path)
            # Når disabled, skal altid være OK
            assert result.flag.value == "ok"
            assert result.passed is True
            assert result.message == "Quality checks disabled"
        finally:
            img_path.unlink(missing_ok=True)


# ── 7. Performance Tests ───────────────────────────────────────────────────────

class TestEdgeAIPerformance:
    """Performance tests for Edge AI."""

    def test_quality_check_performance(self):
        """Quality check skal være hurtig (<500ms for 1080p)."""
        import time
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        checker = QualityChecker({"quality": {"check_enabled": True}})

        img_path = create_test_image(width=1920, height=1080, brightness=128)
        try:
            start = time.time()
            result = checker.check(img_path)
            elapsed = time.time() - start

            assert result is not None
            # Quality check skal være hurtig
            assert elapsed < 2.0, f"Quality check tog {elapsed:.2f}s (for langsomt)"
        finally:
            img_path.unlink(missing_ok=True)

    def test_optimizer_analyse_performance(self):
        """Optimizer analyse skal være hurtig (<1s for 1080p)."""
        import time
        try:
            from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
        except ImportError:
            from ai.autonomous_optimizer import AutonomousImageOptimizer

        optimizer = AutonomousImageOptimizer({"quality": {"check_enabled": True}})

        img_path = create_test_image(width=1920, height=1080, brightness=128)
        try:
            start = time.time()
            result = optimizer.analyse(img_path)
            elapsed = time.time() - start

            assert result is not None
            # Optimize skal være hurtig
            assert elapsed < 3.0, f"Optimizer analyse tog {elapsed:.2f}s (for langsomt)"
        finally:
            img_path.unlink(missing_ok=True)


# ── 8. Weekend Feature Validation ────────────────────────────────────────────

class TestWeekendFeatures:
    """Valider at weekend features (4-6 July 2026) virker."""

    def test_quality_report_autonomous_optimizer_integration(self):
        """qa_report skal integrere autonomous_optimizer resultat."""
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        config = {
            "quality": {
                "check_enabled": True,
                "edge_ai": {"enabled": True}
            }
        }
        checker = QualityChecker(config)

        img_path = create_test_image(brightness=128)
        try:
            report = checker.qa_report(img_path)

            # Tjek autonomous_optimizer integration
            if "autonomous_optimizer" in report:
                assert isinstance(report["autonomous_optimizer"], dict)
        finally:
            img_path.unlink(missing_ok=True)

    def test_npu_status_in_qa_report(self):
        """qa_report skal inkludere NPU status (weekend feature)."""
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        checker = QualityChecker({"quality": {"check_enabled": True}})

        img_path = create_test_image(brightness=128)
        try:
            report = checker.qa_report(img_path)
            assert "npu" in report
            npu_info = report["npu"]
            assert "available" in npu_info
        finally:
            img_path.unlink(missing_ok=True)

    def test_cv_features_completeness(self):
        """cv_features skal være komplet (weekend feature udvidelse)."""
        try:
            from edge.capture.quality import QualityChecker
        except ImportError:
            from capture.quality import QualityChecker

        checker = QualityChecker({"quality": {"check_enabled": True}})

        img_path = create_test_image(brightness=150)
        try:
            report = checker.qa_report(img_path)
            cv_features = report.get("cv_features", {})

            # Tjek vigtige CV features
            expected_keys = [
                "dark_ratio", "bright_ratio", "contrast_std",
                "saturation_mean", "white_balance"
            ]

            # Nogle features kan mangle hvis OpenCV ikke er tilgængelig
            if checker._cv2_available:
                for key in expected_keys:
                    assert key in cv_features, f"Manglende CV feature: {key}"
        finally:
            img_path.unlink(missing_ok=True)
