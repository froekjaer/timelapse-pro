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
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

HEADEND_DIR = Path(__file__).resolve().parents[1]
if str(HEADEND_DIR) not in sys.path:
    sys.path.insert(0, str(HEADEND_DIR))

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# Reviewed human annotations for benchmark cases. These are deliberately
# separate from provider output: a model never writes its own ground truth.
GROUND_TRUTH_VERSION = 1


def _service(name: str, model: str | None, get_db_fn):
    if name == "apple":
        from ai.apple_foundation_service import AppleFoundationVisionService
        return AppleFoundationVisionService()
    if name == "ollama":
        from ai.ollama_service import OllamaVisionService
        return OllamaVisionService(vision_model=model)
    if name == "gemini":
        from ai.provider_config import build_gemini_vision_service

        service = build_gemini_vision_service(
            get_db_fn,
            model or "gemini-3.8-flash",
        )
        if service is None:
            raise RuntimeError(
                "Gemini er ikke konfigureret via autoritativ Headend settings/environment"
            )
        return service
    raise ValueError(f"Ukendt provider: {name}")


def _predefined_vocabulary() -> tuple[dict[str, list[str]], set[str]]:
    from ai.tag_vocabulary import PREDEFINED_TAGS, get_all_predefined

    return (
        {category: list(tags) for category, tags in PREDEFINED_TAGS.items()},
        set(get_all_predefined()),
    )


def _load_vocabulary_context(source: str, get_db_fn):
    """Load benchmark vocabulary without mutating authoritative state.

    auto: read approved DB vocabulary; fall back to static predefined vocabulary.
    database: require approved DB vocabulary and fail closed if unavailable.
    predefined: use the repository's curated PREDEFINED_TAGS only.
    empty: legacy baseline with no controlled vocabulary.
    """
    if source == "empty":
        by_category: dict[str, list[str]] = {}
        approved: set[str] = set()
        return by_category, approved, {
            "requested_source": source,
            "effective_source": "empty",
            "category_count": 0,
            "tag_count": 0,
            "fallback_reason": None,
        }

    if source == "predefined":
        by_category, approved = _predefined_vocabulary()
        return by_category, approved, {
            "requested_source": source,
            "effective_source": "predefined",
            "category_count": len(by_category),
            "tag_count": len(approved),
            "fallback_reason": None,
        }

    if source not in {"auto", "database"}:
        raise ValueError(f"Ukendt vocabulary source: {source}")

    try:
        from ai.tag_vocabulary import load_approved_vocabulary_readonly

        by_category, approved = load_approved_vocabulary_readonly(get_db_fn)
        if not approved:
            raise RuntimeError("approved_vocabulary_empty")
        return by_category, approved, {
            "requested_source": source,
            "effective_source": "database",
            "category_count": len(by_category),
            "tag_count": len(approved),
            "fallback_reason": None,
        }
    except Exception as exc:
        if source == "database":
            raise RuntimeError(
                f"Autoritativ vocabulary kunne ikke læses ({type(exc).__name__})"
            ) from exc

        by_category, approved = _predefined_vocabulary()
        return by_category, approved, {
            "requested_source": source,
            "effective_source": "predefined",
            "category_count": len(by_category),
            "tag_count": len(approved),
            "fallback_reason": type(exc).__name__,
        }


def _load_annotations(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else payload
    out = {}
    for case in cases:
        sha = str(case.get("sha256", "")).strip().lower()
        if sha:
            out[sha] = case
    return out


def _privacy_score(result: dict, annotation: dict | None) -> dict | None:
    if not annotation:
        return None
    privacy = annotation.get("privacy") or {}
    expected_person = privacy.get("person_present")
    if expected_person is None:
        return None
    detections = result.get("gdpr_detections") or []
    types = {str(d.get("detection_type", "")) for d in detections}
    predicted_person = "person_counted" in types
    expected_face = privacy.get("recognizable_face")
    predicted_face = "face" in types
    score = {
        "person_present_expected": bool(expected_person),
        "person_present_predicted": predicted_person,
        "person_detection_correct": predicted_person == bool(expected_person),
        "recognizable_face_expected": expected_face,
        "face_predicted": predicted_face,
    }
    if expected_face is not None:
        score["face_detection_correct"] = predicted_face == bool(expected_face)
    return score


def _run(
    name: str,
    image: Path,
    model: str | None,
    get_db_fn,
    vocabulary_by_cat: dict[str, list[str]],
    approved_tag_set: set[str],
) -> dict:
    started = time.monotonic()
    try:
        result = _service(name, model, get_db_fn).analyse(
            image_path=image,
            vocabulary_by_cat=vocabulary_by_cat,
            approved_tag_set=approved_tag_set,
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
        reviewed = [r["reviewed_score"] for r in ok if r.get("reviewed_score")]
        person_scored = [s for s in reviewed if s.get("person_detection_correct") is not None]
        face_scored = [s for s in reviewed if s.get("face_detection_correct") is not None]
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
            "reviewed_privacy": {
                "person_cases_scored": len(person_scored),
                "person_correct": sum(bool(s["person_detection_correct"]) for s in person_scored),
                "recognizable_face_cases_scored": len(face_scored),
                "recognizable_face_correct": sum(bool(s["face_detection_correct"]) for s in face_scored),
            } if reviewed else None,
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
    p.add_argument("--vocabulary-source",
                   choices=("auto", "database", "predefined", "empty"),
                   default="auto",
                   help=(
                       "Prompt vocabulary: auto=read-only DB with predefined fallback; "
                       "database=strict DB; predefined=repo baseline; empty=legacy baseline"
                   ))
    p.add_argument("--annotations", type=Path, default=None,
                   help="Reviewed JSON ground truth; matched by image SHA-256")
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()

    images = _images(args.target, args.limit)
    if not images:
        p.error("Ingen billeder fundet")

    from database import get_db

    try:
        vocabulary_by_cat, approved_tag_set, vocabulary_meta = _load_vocabulary_context(
            args.vocabulary_source,
            get_db,
        )
    except Exception as exc:
        p.error(str(exc))

    models = {"apple": None, "ollama": args.ollama_model, "gemini": args.gemini_model}
    annotations = _load_annotations(args.annotations)
    runs = []

    jobs = [(image, provider, n + 1)
            for image in images for n in range(args.repeat)
            for provider in args.providers]

    def execute(job):
        image, provider, iteration = job
        row = _run(
            provider,
            image,
            models[provider],
            get_db,
            vocabulary_by_cat,
            approved_tag_set,
        )
        sha256 = hashlib.sha256(image.read_bytes()).hexdigest()
        row.update({
            "image": str(image),
            "sha256": sha256,
            "iteration": iteration,
        })
        annotation = annotations.get(sha256)
        if annotation:
            row["annotation_case_id"] = annotation.get("case_id")
            if row["ok"]:
                row["reviewed_score"] = _privacy_score(row["result"], annotation)
        return row

    if args.mode == "parallel":
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.providers)) as pool:
            for row in pool.map(execute, jobs):
                runs.append(row)
    else:
        for job in jobs:
            runs.append(execute(job))

    report = {
        "benchmark_version": 3,
        "target": str(args.target),
        "image_count": len(images),
        "repeat": args.repeat,
        "mode": args.mode,
        "providers": args.providers,
        "vocabulary": vocabulary_meta,
        "annotations": str(args.annotations) if args.annotations else None,
        "ground_truth_version": GROUND_TRUTH_VERSION if args.annotations else None,
        "summary": _summary(runs, args.providers),
        "runs": runs,
        "note": (
            "LAB evidence only. Provider output/confidence is not ground truth. "
            "Vocabulary loading is read-only; benchmark must not mutate production state. "
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
