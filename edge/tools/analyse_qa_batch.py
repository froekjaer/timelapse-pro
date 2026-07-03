#!/usr/bin/env python3
"""
Analyse a folder of images with the same QA report used by EdgeAgent.

Useful for camera calibration, Orange Pi/NPU smoke tests and comparing
quality.edge_ai.mode behaviour without waiting for scheduled captures.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _import_edge() -> None:
    edge_root = Path(__file__).resolve().parents[1]
    repo_root = edge_root.parent
    for path in (edge_root, repo_root):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _config(mode: str, runner: str, model: str, vendor_binary: str) -> dict:
    return {
        "quality": {
            "check_enabled": True,
            "blur_threshold": 80,
            "dark_threshold": 25,
            "bright_threshold": 230,
            "adaptive_exposure": {
                "enabled": mode not in {"off", "monitor"},
                "target_brightness": 118,
                "brightness_tolerance": 32,
                "step_ev": 0.3,
                "min_ev": -2.0,
                "max_ev": 2.0,
            },
            "edge_ai": {
                "enabled": mode != "off",
                "mode": mode,
                "prefer_npu": mode == "npu_first",
                "runner": runner,
                "model_path": model,
                "vendor_binary": vendor_binary,
            },
        }
    }


def iter_images(root: Path):
    suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    if root.is_file() and root.suffix.lower() in suffixes:
        yield root
        return
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and path.suffix.lower() in suffixes
            and ".thumbs" not in path.parts
            and ".headend-thumbs" not in path.parts
        ):
            yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Image file or directory")
    parser.add_argument("--mode", default="assist", choices=["off", "monitor", "assist", "autonomous", "npu_first", "lab"])
    parser.add_argument("--runner", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--vendor-binary", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    _import_edge()
    try:
        from capture.quality import QualityChecker
    except Exception:
        from edge.capture.quality import QualityChecker

    checker = QualityChecker(_config(args.mode, args.runner, args.model, args.vendor_binary))
    output = Path(args.out) if args.out else None
    fh = output.open("w", encoding="utf-8") if output else sys.stdout
    count = 0
    try:
        for image in iter_images(Path(args.path)):
            report = checker.qa_report(image)
            opt = report.get("autonomous_optimizer") or {}
            row = {
                "image": str(image),
                "flag": report.get("flag"),
                "passed": report.get("passed"),
                "probable_cause": report.get("probable_cause"),
                "confidence": report.get("confidence"),
                "score": opt.get("score"),
                "policy": opt.get("policy"),
                "control_plan": opt.get("control_plan"),
                "recommendations": opt.get("recommendations", []),
                "npu": report.get("npu"),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    finally:
        if output:
            fh.close()
    if output:
        print(json.dumps({"status": "ok", "images": count, "out": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
