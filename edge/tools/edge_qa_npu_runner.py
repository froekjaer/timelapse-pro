#!/usr/bin/env python3
"""
TimeLapse Pro edge QA runner with NPU-ready JSON contract.

The runner is intentionally conservative:
- If a vendor NPU runtime is present, this is the stable integration point.
- If no supported runtime/model is present, it returns a CPU/OpenCV result with
  available=false, so the edge agent keeps working and records why NPU was not
  used.

Expected stdout is one JSON object. It is consumed by edge.ai.npu_quality.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import subprocess
from pathlib import Path
from typing import Any


def _repo_edge_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _import_edge_modules() -> None:
    edge_root = _repo_edge_root()
    if str(edge_root) not in sys.path:
        sys.path.insert(0, str(edge_root))
    repo_root = edge_root.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _detect_runtime(model: Path | None = None) -> dict[str, Any]:
    _import_edge_modules()
    try:
        from ai.npu_runtime import detect_orangepi_npu_runtime
    except Exception:
        from edge.ai.npu_runtime import detect_orangepi_npu_runtime
    return detect_orangepi_npu_runtime(model_path=str(model) if model else None)


def _cpu_fallback(image: Path, model: Path | None, runtime_info: dict[str, Any]) -> dict[str, Any]:
    _import_edge_modules()
    try:
        from ai.autonomous_optimizer import AutonomousImageOptimizer
        from ai.model_contract import classification_to_contract, label_from_probable_cause
    except Exception:
        from edge.ai.autonomous_optimizer import AutonomousImageOptimizer
        from edge.ai.model_contract import classification_to_contract, label_from_probable_cause

    cfg = {
        "quality": {
            "check_enabled": True,
            "blur_threshold": 80,
            "dark_threshold": 25,
            "bright_threshold": 230,
            "adaptive_exposure": {
                "enabled": True,
                "target_brightness": 118,
                "brightness_tolerance": 32,
                "step_ev": 0.3,
            },
            "edge_ai": {
                "enabled": True,
                "mode": os.getenv("TIMELAPSE_EDGE_AI_MODE", "assist"),
                "prefer_npu": True,
            },
        }
    }
    result = AutonomousImageOptimizer(cfg).analyse(image, {})
    recs = result.get("recommendations", [])
    top = _select_contract_recommendation(recs)
    label = label_from_probable_cause(top.get("action"), default="ok")
    if label == "ok":
        label = _label_from_optimizer_action(str(top.get("action", "ok")))
    contract = classification_to_contract(
        label,
        float(top.get("confidence", 0.55)),
        engine="edge_npu_contract_cpu_fallback",
        available=False,
        source="autonomous_optimizer",
        extra={
            "runtime": runtime_info,
            "model_path": str(model) if model else None,
            "optimizer": result,
        },
    )
    contract["is_anomaly"] = bool(recs)
    if recs and top.get("reason"):
        contract["recommended_action"] = top.get("reason")
    return contract


def _select_contract_recommendation(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    if not recommendations:
        return {"action": "ok", "confidence": 0.55}
    priority = {
        "maintenance": 100,
        "schedule": 90,
        "depth_of_field": 80,
        "focus": 70,
        "white_balance": 60,
        "framing_or_focus": 50,
        "exposure": 40,
    }

    def score(rec: dict[str, Any]) -> tuple[int, float]:
        return (
            priority.get(str(rec.get("kind") or ""), 0),
            float(rec.get("confidence", 0.0) or 0.0),
        )

    return max(recommendations, key=score)


def _label_from_optimizer_action(action: str) -> str:
    mapping = {
        "ok": "ok",
        "run_autofocus_or_focus_slice": "blurry",
        "validate_focus_plane": "depth_of_field_issue",
        "increase_depth_of_field": "depth_of_field_issue",
        "inspect_lens_front_glass": "snow_or_dirt_on_lens",
        "inspect_for_snow_dirt_or_condensation": "snow_or_dirt_on_lens",
        "avoid_direct_sun_window": "direct_sun_reflection",
        "increase_ev": "underexposed",
        "decrease_ev": "overexposed",
        "protect_highlights": "overexposed",
        "set_whitebalance_daylight": "white_balance_cast",
        "set_whitebalance_auto_or_cloudy": "white_balance_cast",
    }
    return mapping.get(action, "ok")


def _normalise_vendor_payload(payload: dict[str, Any], model: Path | None, runtime_info: dict[str, Any]) -> dict[str, Any]:
    try:
        from ai.model_contract import classification_to_contract, scores_to_contract
    except Exception:
        from edge.ai.model_contract import classification_to_contract, scores_to_contract

    if isinstance(payload.get("scores"), (dict, list)):
        contract = scores_to_contract(
            payload["scores"],
            engine=str(payload.get("engine") or "edge_npu_viplite"),
            available=bool(payload.get("available", True)),
            source="vendor_binary",
        )
    else:
        label = payload.get("label")
        if label is None and payload.get("class_id") is not None:
            try:
                from ai.model_contract import label_from_class_id
            except Exception:
                from edge.ai.model_contract import label_from_class_id

            label = label_from_class_id(int(payload["class_id"]))
        contract = classification_to_contract(
            str(label or "ok"),
            float(payload.get("confidence", 0.0)),
            engine=str(payload.get("engine") or "edge_npu_viplite"),
            available=bool(payload.get("available", True)),
            source="vendor_binary",
        )
    contract.update({
        "runtime": runtime_info,
        "model_path": str(model) if model else None,
        "vendor_raw": payload,
    })
    if payload.get("recommended_action"):
        contract["recommended_action"] = str(payload["recommended_action"])
    if payload.get("probable_cause"):
        contract["probable_cause"] = str(payload["probable_cause"])
    return contract


def _vendor_binary_result(
    vendor_binary: str,
    image: Path,
    model: Path | None,
    runtime_info: dict[str, Any],
) -> dict[str, Any] | None:
    command = shlex.split(vendor_binary)
    if not command:
        return None
    cmd = command + ["--model", str(model or ""), "--image", str(image), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return {
            **_cpu_fallback(image, model, runtime_info),
            "engine": "edge_npu_vendor_binary_error",
            "available": False,
            "error": (proc.stderr or proc.stdout or "").strip()[-500:],
        }
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise ValueError("vendor binary did not emit a JSON object")
    return _normalise_vendor_payload(payload, model, runtime_info)


def analyse(image: Path, model: Path | None, vendor_binary: str = "") -> dict[str, Any]:
    runtime_info = _detect_runtime(model)
    # The Allwinner A733 NPU integration point belongs here. The surrounding
    # contract is already stable; vendor-specific bindings can replace this
    # fallback without touching QualityChecker or EdgeAgent.
    try:
        vendor_binary = vendor_binary or os.getenv("TIMELAPSE_EDGE_AI_VENDOR_BINARY", "")
        if model and model.exists() and vendor_binary:
            return _vendor_binary_result(vendor_binary, image, model, runtime_info) or _cpu_fallback(image, model, runtime_info)
        if model and model.exists() and runtime_info.get("preferred"):
            return {
                **_cpu_fallback(image, model, runtime_info),
                "engine": "edge_npu_contract_pending_vendor_binding",
                "available": False,
                "error": "vendor_runtime_binding_not_installed",
            }
        return _cpu_fallback(image, model, runtime_info)
    except Exception as exc:
        return {
            "engine": "edge_npu_contract_error",
            "available": False,
            "runtime": runtime_info,
            "model_path": str(model) if model else None,
            "is_anomaly": True,
            "label": "runner_error",
            "probable_cause": "edge_npu_runner_error",
            "confidence": 0.80,
            "recommended_action": "Kontroller edge Python venv, OpenCV og NPU runtime installation.",
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="")
    parser.add_argument("--image", required=True)
    parser.add_argument("--vendor-binary", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    image = Path(args.image)
    model = Path(args.model) if args.model else None
    payload = analyse(image, model, args.vendor_binary)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
