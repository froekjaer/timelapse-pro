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
import shutil
import sys
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


def _detect_runtime() -> dict[str, Any]:
    candidates = {
        "allwinner_viplite": [
            "/usr/lib/libVIPLite.so",
            "/usr/lib/aarch64-linux-gnu/libVIPLite.so",
            "/usr/local/lib/libVIPLite.so",
        ],
        "onnxruntime": ["onnxruntime_test", "python3"],
        "rknn": ["rknn_lite_runtime"],
        "hailo": ["hailortcli"],
    }
    found: dict[str, Any] = {}
    for name, paths in candidates.items():
        hits = []
        for path in paths:
            if "/" in path:
                if Path(path).exists():
                    hits.append(path)
            else:
                resolved = shutil.which(path)
                if resolved:
                    hits.append(resolved)
        found[name] = hits
    return {
        "detected": found,
        "preferred": "allwinner_viplite" if found.get("allwinner_viplite") else None,
        "device_hints": {
            "dev_galcore": Path("/dev/galcore").exists(),
            "dev_vip": any(Path(p).exists() for p in ("/dev/vipcore", "/dev/viplite", "/dev/npu")),
            "proc_device_tree_model": _read_text("/proc/device-tree/model"),
        },
    }


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_bytes().rstrip(b"\x00").decode("utf-8", "ignore")
    except Exception:
        return None


def _cpu_fallback(image: Path, model: Path | None, runtime_info: dict[str, Any]) -> dict[str, Any]:
    _import_edge_modules()
    try:
        from ai.autonomous_optimizer import AutonomousImageOptimizer
    except Exception:
        from edge.ai.autonomous_optimizer import AutonomousImageOptimizer

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
    top = recs[0] if recs else {"action": "ok", "confidence": 0.55}
    return {
        "engine": "edge_npu_contract_cpu_fallback",
        "available": False,
        "runtime": runtime_info,
        "model_path": str(model) if model else None,
        "is_anomaly": bool(recs),
        "label": top.get("action", "ok"),
        "probable_cause": top.get("action", "ok"),
        "confidence": float(top.get("confidence", 0.55)),
        "recommended_action": top.get("reason", "CPU fallback completed; install vendor NPU runtime/model for acceleration."),
        "optimizer": result,
    }


def analyse(image: Path, model: Path | None) -> dict[str, Any]:
    runtime_info = _detect_runtime()
    # The Allwinner A733 NPU integration point belongs here. The surrounding
    # contract is already stable; vendor-specific bindings can replace this
    # fallback without touching QualityChecker or EdgeAgent.
    try:
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
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    image = Path(args.image)
    model = Path(args.model) if args.model else None
    payload = analyse(image, model)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
