#!/usr/bin/env python3
"""Run the same TimeLapse image through Apple, Ollama and Gemini in parallel.

LAB/benchmark tool only. It does not write captures, vocabulary or alarms.
Results are observations, not ground truth.

Example:
  cd headend
  python tools/compare_ai_providers.py /path/to/image.jpg --providers apple ollama gemini
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Direct script execution adds headend/tools, not headend, to sys.path.
# Make the sibling ai package resolvable without requiring PYTHONPATH.
HEADEND_DIR = Path(__file__).resolve().parents[1]
if str(HEADEND_DIR) not in sys.path:
    sys.path.insert(0, str(HEADEND_DIR))


def _run(name: str, image: Path, model: str | None) -> dict:
    started = time.monotonic()
    try:
        if name == "apple":
            from ai.apple_foundation_service import AppleFoundationVisionService
            service = AppleFoundationVisionService()
        elif name == "ollama":
            from ai.ollama_service import OllamaVisionService
            service = OllamaVisionService(vision_model=model)
        elif name == "gemini":
            from ai.gemini_service import GeminiVisionService
            service = GeminiVisionService(
                model=model or os.getenv("TIMELAPSE_GEMINI_MODEL", "gemini-3.8-flash"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "eu"),
            )
        else:
            raise ValueError(f"Ukendt provider: {name}")

        result = service.analyse(
            image_path=image,
            vocabulary_by_cat={},
            approved_tag_set=set(),
        )
        payload = asdict(result)
        return {
            "provider": name,
            "ok": True,
            "wall_ms": int((time.monotonic() - started) * 1000),
            "result": payload,
        }
    except Exception as exc:
        return {
            "provider": name,
            "ok": False,
            "wall_ms": int((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--providers", nargs="+", choices=("apple", "ollama", "gemini"),
        default=["apple", "ollama", "gemini"],
    )
    parser.add_argument("--apple-model", default=None)
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--gemini-model", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Billedet findes ikke: {args.image}")

    models = {
        "apple": args.apple_model,
        "ollama": args.ollama_model,
        "gemini": args.gemini_model,
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.providers)) as pool:
        futures = {
            pool.submit(_run, provider, args.image, models[provider]): provider
            for provider in args.providers
        }
        rows = [future.result() for future in concurrent.futures.as_completed(futures)]

    order = {name: idx for idx, name in enumerate(args.providers)}
    rows.sort(key=lambda row: order[row["provider"]])
    report = {
        "image": str(args.image),
        "providers": rows,
        "note": "Provider output is observation evidence, not ground truth.",
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(encoded)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if all(row["ok"] for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
