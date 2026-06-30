#!/usr/bin/env python3
"""
Probe Orange Pi 4 Pro/A733 NPU readiness for TimeLapse Pro edge QA.

This does not run inference. It verifies the manual-described deployment shape:
ai-sdk present, VIPLite/runtime hints visible and an optional .nb model path.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai-sdk-root", default="", help="Optional explicit ai-sdk root")
    parser.add_argument("--model", default="", help="Optional .nb model path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    _import_edge()
    try:
        from ai.npu_runtime import detect_orangepi_npu_runtime
    except Exception:
        from edge.ai.npu_runtime import detect_orangepi_npu_runtime

    payload = detect_orangepi_npu_runtime(
        ai_sdk_root=args.ai_sdk_root or None,
        model_path=args.model or None,
    )
    indent = 2 if args.pretty else None
    print(json.dumps(payload, ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
