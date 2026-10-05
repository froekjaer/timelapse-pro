"""
TimeLapse Pro - optional Edge NPU quality adapter.

Orange Pi 4 Pro variants expose a 3 TOPS NPU through vendor SDK tooling. This
adapter intentionally keeps the contract tiny: if a local runner and model are
configured, it executes them and merges their JSON output into the deterministic
OpenCV QA report. If not, callers simply keep using CPU QA.
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    from ai.modes import edge_ai_policy
    from ai.model_contract import SCHEMA_VERSION, validate_label
except Exception:  # pragma: no cover - used when imported as edge.ai.*
    from edge.ai.modes import edge_ai_policy
    from edge.ai.model_contract import SCHEMA_VERSION, validate_label

log = logging.getLogger(__name__)

# Shipped in every app release and image (2026-10-05), so the NPU runs on
# every Edge without per-device setup. Config (quality.edge_ai.model_path /
# vendor_binary) still overrides. The model is a candidate, not an accepted
# QA model — see npu_influence below.
_EDGE_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_MODEL = _EDGE_ROOT / "ai" / "models" / "edge_qa_edge_cnn_mini.nb"
BUNDLED_VENDOR_BINARY = _EDGE_ROOT / "npu_viplite" / "bin" / "edge_qa_viplite"
BUNDLED_VENDOR_ARGS = "--input-layout nchw_rgb --input-dtype uint8"


class NpuQualityAdapter:
    """Best-effort wrapper around a local vendor NPU quality runner."""

    def __init__(self, config: dict):
        self._policy = edge_ai_policy(config)
        edge_ai = (config.get("quality", {}) or {}).get("edge_ai", {}) or {}
        self._enabled = bool(edge_ai.get("enabled", False))
        self._prefer_npu = bool(edge_ai.get("prefer_npu", True)) or self._policy.prefer_npu
        self._runner = str(
            edge_ai.get("runner")
            or os.getenv("TIMELAPSE_EDGE_AI_RUNNER", "")
        ).strip()
        self._model = str(
            edge_ai.get("model_path")
            or os.getenv("TIMELAPSE_EDGE_AI_MODEL", "")
            or (BUNDLED_MODEL if BUNDLED_MODEL.is_file() else "")
        ).strip()
        self._vendor_binary = str(
            edge_ai.get("vendor_binary")
            or os.getenv("TIMELAPSE_EDGE_AI_VENDOR_BINARY", "")
            or (f"{BUNDLED_VENDOR_BINARY} {BUNDLED_VENDOR_ARGS}" if BUNDLED_VENDOR_BINARY.is_file() else "")
        ).strip()
        # "shadow" (default): run on the NPU and record the result with every
        # capture, but the CPU QA verdict stands. "merge": a confident NPU
        # result may set anomaly/cause. Only switch to merge once a model has
        # passed real-world acceptance (Travbyen suite) — 2026-10-05.
        influence = str(edge_ai.get("npu_influence") or "shadow").strip().lower()
        self.influence = influence if influence in {"shadow", "merge"} else "shadow"
        self._timeout_s = int(edge_ai.get("timeout_s", 8))
        self._min_confidence = float(edge_ai.get("min_confidence", self._policy.confidence_floor))

    def available(self) -> bool:
        if not self._enabled or not self._policy.run_npu or not self._prefer_npu:
            return False
        if not self._runner:
            return False
        runner_cmd = shlex.split(self._runner)
        if not runner_cmd:
            return False
        runner_path = shutil.which(runner_cmd[0]) if "/" not in runner_cmd[0] else runner_cmd[0]
        return bool(runner_path and Path(runner_path).exists())

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "policy": self._policy.as_dict(),
            "prefer_npu": self._prefer_npu,
            "available": self.available(),
            "runner": self._runner or None,
            "model_path": self._model or None,
            "model_present": bool(self._model and Path(self._model).exists()),
            "vendor_binary": self._vendor_binary or None,
            "min_confidence": self._min_confidence,
            "influence": self.influence,
            "runtime": "vendor_npu_json_runner",
        }

    def analyse(self, image_path: Path) -> dict[str, Any] | None:
        """Run configured NPU model. Runner must print one JSON object to stdout."""
        if not self.available():
            return None
        cmd = shlex.split(self._runner) + ["--model", self._model, "--image", str(image_path), "--json"]
        if self._vendor_binary:
            cmd.extend(["--vendor-binary", self._vendor_binary])
        try:
            env = os.environ.copy()
            env["TIMELAPSE_EDGE_AI_MODE"] = self._policy.mode
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout_s, env=env)
        except Exception as exc:
            log.warning("Edge NPU QA runner failed: %s", exc)
            return {"engine": "edge_npu", "available": False, "error": str(exc)}
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-500:]
            log.warning("Edge NPU QA runner rc=%s: %s", result.returncode, detail)
            return {"engine": "edge_npu", "available": False, "error": detail}
        try:
            data = json.loads(result.stdout)
        except Exception as exc:
            log.warning("Edge NPU QA runner returned invalid JSON: %s", exc)
            return {"engine": "edge_npu", "available": False, "error": "invalid_json"}
        if not isinstance(data, dict):
            return {"engine": "edge_npu", "available": False, "error": "json_not_object"}
        if data.get("schema") != SCHEMA_VERSION:
            log.warning("Edge NPU QA runner returned unsupported schema: %r", data.get("schema"))
            return {
                "engine": "edge_npu",
                "available": False,
                "accepted": False,
                "error": "unsupported_schema",
                "expected_schema": SCHEMA_VERSION,
            }
        try:
            validate_label(str(data.get("label") or ""))
        except ValueError:
            log.warning("Edge NPU QA runner returned unknown label: %r", data.get("label"))
            return {
                "engine": "edge_npu",
                "available": False,
                "accepted": False,
                "error": "unknown_label",
                "schema": SCHEMA_VERSION,
            }
        data.setdefault("engine", "edge_npu")
        data.setdefault("available", True)
        data.setdefault("policy", self._policy.as_dict())
        try:
            confidence = float(data.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        data["accepted"] = confidence >= self._min_confidence
        if not data["accepted"]:
            data["ignored_reason"] = "below_min_confidence"
            data["min_confidence"] = self._min_confidence
        return data
