"""
TimeLapse Pro - autonomous edge image optimizer.

This module turns cheap local image measurements into practical control advice:
exposure compensation, white balance hints, focus actions, aperture/depth-of-field
signals and schedule avoid-window suggestions. It is deliberately deterministic
so it can run on every edge node while a future NPU model acts as an accelerator
or confidence booster, not as a hard dependency.
"""
from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Any

try:
    from ai.modes import edge_ai_policy
except Exception:  # pragma: no cover - used when imported as edge.ai.*
    from edge.ai.modes import edge_ai_policy


@dataclasses.dataclass(frozen=True)
class OptimizerRecommendation:
    kind: str
    action: str
    confidence: float
    reason: str
    params: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "action": self.action,
            "confidence": round(float(self.confidence), 2),
            "reason": self.reason,
            "params": self.params,
        }


class AutonomousImageOptimizer:
    """Analyse one captured image and propose next-capture improvements."""

    def __init__(self, config: dict):
        self._config = config
        self._policy = edge_ai_policy(config)
        quality = config.get("quality", {}) or {}
        adaptive = quality.get("adaptive_exposure", {}) or {}
        self._target_brightness = float(adaptive.get("target_brightness", 118.0))
        self._brightness_tolerance = float(adaptive.get("brightness_tolerance", 32.0))
        self._step_ev = float(adaptive.get("step_ev", 0.3))
        self._min_ev = float(adaptive.get("min_ev", -2.0))
        self._max_ev = float(adaptive.get("max_ev", 2.0))
        self._blur_threshold = float(quality.get("blur_threshold", 80.0))
        self._dark_threshold = float(quality.get("dark_threshold", 25.0))
        self._bright_threshold = float(quality.get("bright_threshold", 230.0))

    def analyse(self, image_path: Path, quality_report: dict | None = None) -> dict[str, Any]:
        if not self._policy.run_optimizer:
            return {
                "engine": "edge_autonomous_optimizer_v1",
                "policy": self._policy.as_dict(),
                "enabled": False,
                "score": None,
                "features": {},
                "recommendations": [],
                "control_plan": {
                    "next_capture_ev_delta": 0.0,
                    "commands": [],
                    "avoid_window_suggestion": None,
                    "autonomous_safe_to_apply": False,
                },
            }
        features = self._extract_features(image_path)
        quality_report = quality_report or {}
        recommendations = self._recommend(features, quality_report)
        control = self._control_plan(features, quality_report, recommendations)
        score = self._score(features, quality_report)
        return {
            "engine": "edge_autonomous_optimizer_v1",
            "policy": self._policy.as_dict(),
            "score": score,
            "features": features,
            "recommendations": [r.as_dict() for r in recommendations],
            "control_plan": control,
        }

    def _extract_features(self, image_path: Path) -> dict[str, Any]:
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"cv2.imread returned None for {image_path}")

        h, w = img.shape[:2]
        max_dim = 1280
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        h, w = gray.shape[:2]
        center = gray[h // 4:h * 3 // 4, w // 4:w * 3 // 4]
        edge_mask = np.ones(gray.shape, dtype=bool)
        edge_mask[h // 4:h * 3 // 4, w // 4:w * 3 // 4] = False
        edges = gray[edge_mask]

        thirds = []
        for y0, y1 in ((0, h // 3), (h // 3, h * 2 // 3), (h * 2 // 3, h)):
            for x0, x1 in ((0, w // 3), (w // 3, w * 2 // 3), (w * 2 // 3, w)):
                crop = gray[y0:y1, x0:x1]
                thirds.append(float(cv2.Laplacian(crop, cv2.CV_64F).var()) if crop.size else 0.0)

        channels = img.reshape(-1, 3).astype("float32")
        b_mean, g_mean, r_mean = [float(x) for x in channels.mean(axis=0)]
        rg = r_mean / max(g_mean, 1.0)
        bg = b_mean / max(g_mean, 1.0)
        color_cast_strength = max(abs(rg - 1.0), abs(bg - 1.0))
        if color_cast_strength < 0.10:
            color_cast = "neutral"
        elif rg > bg and rg > 1.10:
            color_cast = "warm/red"
        elif bg > rg and bg > 1.10:
            color_cast = "cool/blue"
        elif rg < 0.90 and bg < 0.90:
            color_cast = "green"
        else:
            color_cast = "mixed"

        p01, p05, p50, p95, p99 = [float(x) for x in np.percentile(gray, [1, 5, 50, 95, 99])]
        dynamic_range = p95 - p05
        clipped_shadows = float(np.mean(gray <= 3))
        clipped_highlights = float(np.mean(gray >= 252))
        highlight_ratio = float(np.mean(gray > 245))
        dark_ratio = float(np.mean(gray < self._dark_threshold))
        bright_ratio = float(np.mean(gray > self._bright_threshold))
        contrast_std = float(np.std(gray))
        saturation_mean = float(np.mean(hsv[:, :, 1]))
        saturation_std = float(np.std(hsv[:, :, 1]))
        lab_a = float(np.mean(lab[:, :, 1]) - 128.0)
        lab_b = float(np.mean(lab[:, :, 2]) - 128.0)

        center_blur = float(cv2.Laplacian(center, cv2.CV_64F).var()) if center.size else 0.0
        edge_blur = float(cv2.Laplacian(edges, cv2.CV_64F).var()) if edges.size else 0.0
        global_blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        focus_uniformity = min(thirds) / max(max(thirds), 1.0) if thirds else 0.0

        return {
            "width": int(w),
            "height": int(h),
            "brightness_mean": round(float(np.mean(gray)), 2),
            "brightness_median": round(p50, 2),
            "center_brightness": round(float(np.mean(center)) if center.size else p50, 2),
            "dynamic_range_p05_p95": round(dynamic_range, 2),
            "contrast_std": round(contrast_std, 2),
            "dark_ratio": round(dark_ratio, 4),
            "bright_ratio": round(bright_ratio, 4),
            "highlight_ratio": round(highlight_ratio, 4),
            "clipped_shadows": round(clipped_shadows, 4),
            "clipped_highlights": round(clipped_highlights, 4),
            "saturation_mean": round(saturation_mean, 2),
            "saturation_std": round(saturation_std, 2),
            "white_balance": {
                "red_green_ratio": round(rg, 3),
                "blue_green_ratio": round(bg, 3),
                "lab_a_offset": round(lab_a, 2),
                "lab_b_offset": round(lab_b, 2),
                "cast": color_cast,
                "cast_strength": round(color_cast_strength, 3),
            },
            "focus": {
                "global_blur": round(global_blur, 2),
                "center_blur": round(center_blur, 2),
                "edge_blur": round(edge_blur, 2),
                "uniformity": round(focus_uniformity, 3),
                "thirds_blur": [round(v, 2) for v in thirds],
            },
        }

    def _recommend(
        self,
        features: dict[str, Any],
        quality_report: dict,
    ) -> list[OptimizerRecommendation]:
        recs: list[OptimizerRecommendation] = []
        brightness = float(features.get("brightness_mean", quality_report.get("brightness_mean") or 128.0))
        center = float(features.get("center_brightness", brightness))
        highlight_ratio = float(features.get("highlight_ratio", 0.0))
        clipped_highlights = float(features.get("clipped_highlights", 0.0))
        clipped_shadows = float(features.get("clipped_shadows", 0.0))
        contrast = float(features.get("contrast_std", 0.0))
        saturation = float(features.get("saturation_mean", 0.0))
        focus = features.get("focus", {}) or {}
        global_blur = float(focus.get("global_blur", quality_report.get("blur_score") or 0.0))
        center_blur = float(focus.get("center_blur", global_blur))
        edge_blur = float(focus.get("edge_blur", global_blur))
        uniformity = float(focus.get("uniformity", 1.0))
        wb = features.get("white_balance", {}) or {}
        cast_strength = float(wb.get("cast_strength", 0.0))
        cause = str(quality_report.get("probable_cause") or quality_report.get("flag") or "")

        if brightness > self._target_brightness + self._brightness_tolerance:
            recs.append(OptimizerRecommendation(
                "exposure",
                "decrease_ev",
                min(0.95, 0.55 + (brightness - self._target_brightness) / 180.0),
                "Image is brighter than the configured target.",
                {"ev_delta": -self._step_ev},
            ))
        elif brightness < self._target_brightness - self._brightness_tolerance:
            recs.append(OptimizerRecommendation(
                "exposure",
                "increase_ev",
                min(0.95, 0.55 + (self._target_brightness - brightness) / 180.0),
                "Image is dark with clipped shadows.",
                {"ev_delta": self._step_ev},
            ))

        direct_sun_signal = (
            highlight_ratio > 0.05
            and (
                center > self._bright_threshold
                or cause == "direct_sun_reflection"
                or clipped_highlights > 0.01
                or bright_ratio > 0.10
            )
        )
        if direct_sun_signal:
            recs.append(OptimizerRecommendation(
                "schedule",
                "avoid_direct_sun_window",
                min(0.96, 0.75 + highlight_ratio),
                "Strong central highlights indicate direct sun/reflection.",
                {"suggested_window_minutes": 20, "ev_delta": -self._step_ev},
            ))
        elif clipped_highlights > 0.02:
            recs.append(OptimizerRecommendation(
                "exposure",
                "protect_highlights",
                min(0.92, 0.68 + clipped_highlights * 3.0),
                "Highlight clipping detected.",
                {"ev_delta": -self._step_ev, "meteringmode": "Evaluative"},
            ))

        if global_blur < self._blur_threshold:
            recs.append(OptimizerRecommendation(
                "focus",
                "run_autofocus_or_focus_slice",
                min(0.95, 0.70 + (self._blur_threshold - global_blur) / max(self._blur_threshold, 1.0) * 0.20),
                "Global sharpness is below threshold.",
                {"lab_command": "focus_slice", "prefer_preview_validation": True},
            ))

        if center_blur > self._blur_threshold * 1.5 and edge_blur < center_blur * 0.35:
            recs.append(OptimizerRecommendation(
                "depth_of_field",
                "increase_depth_of_field",
                0.76,
                "Center is sharp but edges are much softer; depth of field may be too shallow.",
                {"aperture_hint": "stop_down_one_step", "iso_guard": "avoid_high_iso_if_possible"},
            ))
        elif uniformity < 0.22 and global_blur >= self._blur_threshold:
            recs.append(OptimizerRecommendation(
                "framing_or_focus",
                "validate_focus_plane",
                0.70,
                "Sharpness is uneven across the frame.",
                {"lab_command": "preview_grid_focus_check"},
            ))

        if cast_strength > 0.18:
            action = "set_whitebalance_daylight" if wb.get("cast") == "cool/blue" else "set_whitebalance_auto_or_cloudy"
            recs.append(OptimizerRecommendation(
                "white_balance",
                action,
                min(0.90, 0.62 + cast_strength),
                f"White balance color cast detected: {wb.get('cast')}.",
                {"cast": wb.get("cast"), "red_green_ratio": wb.get("red_green_ratio"), "blue_green_ratio": wb.get("blue_green_ratio")},
            ))

        if cause in {"snow_or_dirt_on_lens", "condensation_or_soft_lens_obstruction"}:
            recs.append(OptimizerRecommendation(
                "maintenance",
                "inspect_lens_front_glass",
                0.88,
                "Existing QA classified likely lens/front-glass obstruction.",
                {"dispatch": "clean_lens_or_check_heater"},
            ))
        elif global_blur < self._blur_threshold and contrast < 22 and brightness > 160 and saturation < 45:
            recs.append(OptimizerRecommendation(
                "maintenance",
                "inspect_for_snow_dirt_or_condensation",
                0.82,
                "Low contrast, low saturation and soft detail suggest obstruction.",
                {"dispatch": "clean_lens_or_check_heater"},
            ))

        return self._dedupe(recs)

    def _control_plan(
        self,
        features: dict[str, Any],
        quality_report: dict,
        recommendations: list[OptimizerRecommendation],
    ) -> dict[str, Any]:
        ev_delta = 0.0
        commands: list[dict[str, Any]] = []
        avoid_window = None
        for rec in recommendations:
            if rec.kind in {"exposure", "schedule"}:
                ev_delta += float(rec.params.get("ev_delta", 0.0) or 0.0)
            if rec.kind == "focus" and self._policy.allow_camera_commands and rec.confidence >= self._policy.confidence_floor:
                commands.append({"type": "lab", "command": rec.params.get("lab_command", "focus_slice")})
            if rec.kind == "white_balance" and self._policy.allow_camera_commands and rec.confidence >= self._policy.confidence_floor:
                commands.append({"type": "camera_config", "key": "whitebalance", "action": rec.action})
            if rec.action == "avoid_direct_sun_window" and self._policy.allow_schedule_suggestions:
                avoid_window = {
                    "action": "avoid",
                    "reason": "edge_detected_direct_sun_reflection",
                    "duration_minutes": int(rec.params.get("suggested_window_minutes", 20)),
                }

        ev_delta = max(-self._step_ev * 2, min(self._step_ev * 2, ev_delta))
        if abs(ev_delta) < 0.01:
            ev_delta = 0.0
        return {
            "next_capture_ev_delta": round(ev_delta if self._policy.allow_ev_autopilot else 0.0, 2),
            "commands": commands,
            "avoid_window_suggestion": avoid_window,
            "autonomous_safe_to_apply": self._safe_to_apply(recommendations, quality_report),
        }

    def _safe_to_apply(self, recommendations: list[OptimizerRecommendation], quality_report: dict) -> bool:
        if not recommendations:
            return False
        if not self._policy.allow_ev_autopilot:
            return False
        if quality_report.get("flag") == "hash_mismatch":
            return False
        risky = {"maintenance", "depth_of_field"}
        return all(r.kind not in risky for r in recommendations) and any(
            r.confidence >= self._policy.confidence_floor for r in recommendations
        )

    def _score(self, features: dict[str, Any], quality_report: dict) -> dict[str, Any]:
        brightness = float(features.get("brightness_mean", quality_report.get("brightness_mean") or self._target_brightness))
        focus = features.get("focus", {}) or {}
        blur = float(focus.get("global_blur", quality_report.get("blur_score") or self._blur_threshold))
        wb = features.get("white_balance", {}) or {}
        cast_strength = float(wb.get("cast_strength", 0.0))
        highlight_penalty = min(35.0, float(features.get("highlight_ratio", 0.0)) * 180.0)
        exposure_penalty = min(35.0, abs(brightness - self._target_brightness) / max(self._target_brightness, 1.0) * 45.0)
        focus_penalty = 0.0 if blur >= self._blur_threshold else min(35.0, (self._blur_threshold - blur) / max(self._blur_threshold, 1.0) * 35.0)
        wb_penalty = min(18.0, cast_strength * 40.0)
        score = max(0.0, 100.0 - exposure_penalty - focus_penalty - wb_penalty - highlight_penalty)
        grade = "excellent" if score >= 88 else "good" if score >= 72 else "usable" if score >= 55 else "needs_attention"
        return {
            "overall": round(score, 1),
            "grade": grade,
            "exposure_penalty": round(exposure_penalty, 1),
            "focus_penalty": round(focus_penalty, 1),
            "white_balance_penalty": round(wb_penalty, 1),
            "highlight_penalty": round(highlight_penalty, 1),
        }

    @staticmethod
    def _dedupe(recommendations: list[OptimizerRecommendation]) -> list[OptimizerRecommendation]:
        best: dict[tuple[str, str], OptimizerRecommendation] = {}
        for rec in recommendations:
            key = (rec.kind, rec.action)
            if key not in best or rec.confidence > best[key].confidence:
                best[key] = rec
        return sorted(best.values(), key=lambda r: r.confidence, reverse=True)
