#!/usr/bin/env python3
"""
Mine balanced Edge QA training candidates from historical captures.

This is not a replacement for human review. It creates a high-signal JSONL
manifest with deterministic CPU QA labels, confidence, features and review
priority so the first NPU model can be trained from curated real images.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2


def _import_edge_modules() -> None:
    edge_root = Path(__file__).resolve().parents[1]
    repo_root = edge_root.parent
    for path in (edge_root, repo_root):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


_import_edge_modules()
try:
    from ai.model_contract import LABEL_TO_SPEC, label_from_probable_cause, validate_label
    from capture.quality import QualityChecker
except Exception:
    from edge.ai.model_contract import LABEL_TO_SPEC, label_from_probable_cause, validate_label
    from edge.capture.quality import QualityChecker


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES and ".thumbs" not in child.parts:
                    yield child


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def split_for_key(key: str, train_ratio: float, val_ratio: float) -> str:
    bucket = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16) % 10000 / 10000.0
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + val_ratio:
        return "val"
    return "test"


def qa_config() -> dict[str, Any]:
    return {
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
                "mode": "assist",
                "prefer_npu": False,
                "runner": "",
                "model_path": "",
                "lens_obstruction_enabled": True,
                "direct_sun_detection_enabled": True,
            },
        }
    }


def image_size(path: Path) -> tuple[int | None, int | None]:
    img = cv2.imread(str(path))
    if img is None:
        return None, None
    height, width = img.shape[:2]
    return int(width), int(height)


def label_from_report(report: dict[str, Any]) -> str:
    optimizer = report.get("autonomous_optimizer") or {}
    recs = optimizer.get("recommendations") or []
    if recs:
        top = select_recommendation(recs)
        mapped = label_from_action(str(top.get("action") or ""))
        if mapped:
            return mapped
    cause = str(report.get("probable_cause") or "")
    label = label_from_probable_cause(cause, default="")
    if label:
        return label
    flag = str(report.get("flag") or "")
    return {
        "ok": "ok",
        "blurry": "blurry",
        "underexposed": "underexposed",
        "overexposed": "overexposed",
    }.get(flag, "ok")


def select_recommendation(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
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


def label_from_action(action: str) -> str:
    return {
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
    }.get(action, "")


def review_priority(report: dict[str, Any], label: str, min_confidence: float) -> str:
    try:
        confidence = float(report.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0
    optimizer = report.get("autonomous_optimizer") or {}
    score = optimizer.get("score") or {}
    grade = str(score.get("grade") or "")
    if label == "ok" and report.get("passed") and not report.get("is_anomaly"):
        return "auto_candidate" if grade in {"excellent", "good", "usable"} else "review_recommended"
    if confidence < min_confidence:
        return "needs_human_review"
    if label == "ok" and report.get("is_anomaly"):
        return "needs_human_review"
    if label != "ok" and not report.get("is_anomaly"):
        return "needs_human_review"
    if label in {"condensation", "depth_of_field_issue"}:
        return "review_recommended"
    return "auto_candidate"


def row_for_image(
    image: Path,
    checker: QualityChecker,
    *,
    source: str,
    train_ratio: float,
    val_ratio: float,
    min_confidence: float,
    created_at: str,
) -> dict[str, Any]:
    report = checker.qa_report(image)
    label = label_from_report(report)
    spec = validate_label(label)
    width, height = image_size(image)
    optimizer = report.get("autonomous_optimizer") or {}
    return {
        "schema": "timelapse.edge_qa.training_candidate.v1",
        "image": str(image.resolve()),
        "label": spec.label,
        "class_id": spec.class_id,
        "probable_cause": spec.probable_cause,
        "quality_dimension": spec.quality_dimension,
        "confidence": report.get("confidence"),
        "review_priority": review_priority(report, spec.label, min_confidence),
        "split": split_for_key(str(image.resolve()), train_ratio, val_ratio),
        "source": source,
        "sha256": sha256_file(image),
        "width": width,
        "height": height,
        "created_at": created_at,
        "quality_report": {
            "flag": report.get("flag"),
            "passed": report.get("passed"),
            "blur_score": report.get("blur_score"),
            "brightness_mean": report.get("brightness_mean"),
            "cv_features": report.get("cv_features", {}),
            "score": optimizer.get("score"),
            "recommendations": optimizer.get("recommendations", []),
        },
        "notes": "",
    }


def select_balanced(rows: list[dict[str, Any]], per_label: int, include_review: bool) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not include_review and row.get("review_priority") == "needs_human_review":
            continue
        buckets[str(row["label"])].append(row)
    selected: list[dict[str, Any]] = []
    for label in sorted(LABEL_TO_SPEC):
        label_rows = buckets.get(label, [])
        label_rows.sort(key=lambda row: (row.get("review_priority") != "auto_candidate", -float(row.get("confidence") or 0.0)))
        selected.extend(label_rows[:per_label])
    selected.sort(key=lambda row: (row["label"], row["image"]))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="Image files or folders")
    parser.add_argument("--out", required=True, help="JSONL output path")
    parser.add_argument("--summary-out", default="", help="Optional summary JSON path")
    parser.add_argument("--source", default="historical_cpu_qa")
    parser.add_argument("--limit", type=int, default=0, help="Max images to inspect before balancing")
    parser.add_argument("--per-label", type=int, default=500, help="Max selected rows per label")
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--include-review", action="store_true", help="Include low-confidence review rows")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.80)
    parser.add_argument("--val-ratio", type=float, default=0.10)
    args = parser.parse_args()

    images = list(iter_images(Path(p) for p in args.paths))
    rng = random.Random(args.seed)
    if args.limit and len(images) > args.limit:
        images = rng.sample(images, args.limit)
        images.sort()

    checker = QualityChecker(qa_config())
    created_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for image in images:
        try:
            rows.append(row_for_image(
                image,
                checker,
                source=args.source,
                train_ratio=args.train_ratio,
                val_ratio=args.val_ratio,
                min_confidence=args.min_confidence,
                created_at=created_at,
            ))
        except Exception as exc:
            errors.append({"image": str(image), "error": str(exc)})

    selected = select_balanced(rows, args.per_label, args.include_review)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "status": "ok",
        "inspected": len(images),
        "selected": len(selected),
        "errors": len(errors),
        "out": str(out),
        "labels_inspected": Counter(row["label"] for row in rows),
        "labels_selected": Counter(row["label"] for row in selected),
        "review_priority_selected": Counter(row["review_priority"] for row in selected),
        "error_samples": errors[:20],
    }
    summary = json.loads(json.dumps(summary, ensure_ascii=False, default=dict))
    if args.summary_out:
        Path(args.summary_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
