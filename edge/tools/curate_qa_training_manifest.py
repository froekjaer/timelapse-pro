#!/usr/bin/env python3
"""
Build a training manifest from mined Edge QA candidates.

The miner intentionally keeps review rows. This tool creates the smaller,
safer manifest used for the first model: approved review labels win, rejected
rows are skipped, and unreviewed rows default to auto/review-recommended only.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _import_edge_modules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_import_edge_modules()
try:
    from edge.ai.model_contract import LABEL_TO_SPEC, validate_label
except Exception:
    from ai.model_contract import LABEL_TO_SPEC, validate_label


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_reviews(paths: list[Path]) -> dict[str, dict[str, str]]:
    reviews: dict[str, dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                image = (row.get("image") or "").strip()
                if image:
                    reviews[image] = row
    return reviews


def row_with_label(row: dict[str, Any], label: str) -> dict[str, Any]:
    spec = validate_label(label)
    out = dict(row)
    out["label"] = spec.label
    out["class_id"] = spec.class_id
    out["probable_cause"] = spec.probable_cause
    out["quality_dimension"] = spec.quality_dimension
    out["schema"] = "timelapse.edge_qa.training_curated.v1"
    return out


def curate(
    rows: list[dict[str, Any]],
    reviews: dict[str, dict[str, str]],
    *,
    include_review_recommended: bool,
    include_needs_review: bool,
) -> tuple[list[dict[str, Any]], Counter]:
    curated: list[dict[str, Any]] = []
    decisions: Counter = Counter()
    for row in rows:
        image = str(row.get("image") or "")
        review = reviews.get(image, {})
        approved = (review.get("approved_label") or "").strip()
        notes = (review.get("notes") or "").strip()
        if approved.lower() in {"reject", "skip", "bad", "delete"}:
            decisions["review_rejected"] += 1
            continue
        if approved:
            try:
                curated_row = row_with_label(row, approved)
            except Exception:
                decisions["review_invalid_label"] += 1
                continue
            curated_row["review_priority"] = "human_approved"
            curated_row["notes"] = notes or curated_row.get("notes", "")
            curated.append(curated_row)
            decisions["human_approved"] += 1
            continue

        priority = str(row.get("review_priority") or "")
        if priority == "auto_candidate":
            curated.append(row)
            decisions["auto_candidate"] += 1
        elif priority == "review_recommended" and include_review_recommended:
            curated.append(row)
            decisions["review_recommended_included"] += 1
        elif priority == "needs_human_review" and include_needs_review:
            curated.append(row)
            decisions["needs_review_included"] += 1
        else:
            decisions[f"{priority or 'unknown'}_skipped"] += 1
    return curated, decisions


def balance(rows: list[dict[str, Any]], per_label: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row["label"])].append(row)
    selected: list[dict[str, Any]] = []
    for label in sorted(LABEL_TO_SPEC):
        label_rows = buckets.get(label, [])
        rng.shuffle(label_rows)
        label_rows.sort(key=lambda row: (
            str(row.get("review_priority") or "") != "human_approved",
            str(row.get("review_priority") or "") != "auto_candidate",
            row.get("image", ""),
        ))
        selected.extend(label_rows[:per_label] if per_label > 0 else label_rows)
    selected.sort(key=lambda row: (row["split"], row["label"], row["image"]))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", nargs="+", required=True, help="Mined candidate JSONL files")
    parser.add_argument("--review-csv", nargs="*", default=[], help="Optional review CSV files")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--per-label", type=int, default=800)
    parser.add_argument("--include-review-recommended", action="store_true")
    parser.add_argument("--include-needs-review", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for path in args.candidates:
        rows.extend(load_jsonl(Path(path)))
    reviews = load_reviews([Path(p) for p in args.review_csv])
    curated, decisions = curate(
        rows,
        reviews,
        include_review_recommended=args.include_review_recommended,
        include_needs_review=args.include_needs_review,
    )
    selected = balance(curated, args.per_label, args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "status": "ok",
        "input_rows": len(rows),
        "review_rows": len(reviews),
        "curated_rows": len(curated),
        "selected": len(selected),
        "labels_selected": Counter(row["label"] for row in selected),
        "splits_selected": Counter(row["split"] for row in selected),
        "decisions": decisions,
        "out": str(out),
    }
    summary = json.loads(json.dumps(summary, ensure_ascii=False, default=dict))
    if args.summary_out:
        Path(args.summary_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
