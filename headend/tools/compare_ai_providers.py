#!/usr/bin/env python3
"""Benchmark TimeLapse AI providers across one image or a capture directory.

LAB only: no writes to captures, vocabulary, alarms or production state.
Provider output is observation evidence, not ground truth.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

HEADEND_DIR = Path(__file__).resolve().parents[1]
if str(HEADEND_DIR) not in sys.path:
    sys.path.insert(0, str(HEADEND_DIR))

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _service(name: str, model: str | None):
    if name == "apple":
        from ai.apple_foundation_service import AppleFoundationVisionService
        return AppleFoundationVisionService()
    if name == "ollama":
        from ai.ollama_service import OllamaVisionService
        return OllamaVisionService(vision_model=model)
    if name == "gemini":
        from ai.gemini_service import GeminiVisionService
        return GeminiVisionService(
            model=model or os.getenv("TIMELAPSE_GEMINI_MODEL", "gemini-3.8-flash"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "eu"),
        )
    raise ValueError(f"Ukendt provider: {name}")


def _run(name: str, image: Path, model: str | None) -> dict:
    started = time.monotonic()
    try:
        result = _service(name, model).analyse(
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


def _images(target: Path, limit: int) -> list[Path]:
    if target.is_file():
        return [target]
    if not target.is_dir():
        raise ValueError(f"Findes ikke: {target}")
    rows = sorted(
        p for p in target.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    return rows[:limit] if limit else rows


def _summary(runs: list[dict], providers: list[str]) -> dict:
    out = {}
    for provider in providers:
        rows = [r for r in runs if r["provider"] == provider]
        ok = [r for r in rows if r["ok"]]
        lat = [r["wall_ms"] for r in ok]
        out[provider] = {
            "runs": len(rows),
            "ok": len(ok),
            "errors": len(rows) - len(ok),
            "success_rate": round(len(ok) / len(rows), 3) if rows else 0,
            "wall_ms": {
                "min": min(lat) if lat else None,
                "median": int(statistics.median(lat)) if lat else None,
                "max": max(lat) if lat else None,
                "mean": int(statistics.mean(lat)) if lat else None,
            },
        }
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("target", type=Path, help="Image or directory of captures")
    p.add_argument("--providers", nargs="+", choices=("apple", "ollama", "gemini"),
                   default=["apple", "ollama", "gemini"])
    p.add_argument("--ollama-model", default=None)
    p.add_argument("--gemini-model", default=None)
    p.add_argument("--limit", type=int, default=20,
                   help="Max images when target is a directory; 0 means all")
    p.add_argument("--repeat", type=int, default=1,
                   help="Runs per provider/image; use >1 for warm-run evidence")
    p.add_argument("--mode", choices=("parallel", "sequential"), default="sequential",
                   help="Sequential gives cleaner latency; parallel tests contention")
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()

    images = _images(args.target, args.limit)
    if not images:
        p.error("Ingen billeder fundet")
    models = {"apple": None, "ollama": args.ollama_model, "gemini": args.gemini_model}
    runs = []

    jobs = [(image, provider, n + 1)
            for image in images for n in range(args.repeat)
            for provider in args.providers]

    def execute(job):
        image, provider, iteration = job
        row = _run(provider, image, models[provider])
        row.update({
            "image": str(image),
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "iteration": iteration,
        })
        return row

    if args.mode == "parallel":
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.providers)) as pool:
            for row in pool.map(execute, jobs):
                runs.append(row)
    else:
        for job in jobs:
            runs.append(execute(job))

    report = {
        "benchmark_version": 2,
        "target": str(args.target),
        "image_count": len(images),
        "repeat": args.repeat,
        "mode": args.mode,
        "providers": args.providers,
        "summary": _summary(runs, args.providers),
        "runs": runs,
        "note": (
            "LAB evidence only. Provider output/confidence is not ground truth. "
            "Use reviewed annotations to score factual accuracy, hallucinations and privacy."
        ),
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(encoded)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if all(r["ok"] for r in runs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
