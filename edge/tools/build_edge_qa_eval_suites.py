#!/usr/bin/env python3
"""Build reproducible Edge QA evaluation suites from a training manifest."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


TIMESTAMP_RE = re.compile(r"_(\d{8})_(\d{6})(?:_|\.|$)")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                image = Path(str(row.get("image", "")))
                if not any("thumb" in part.lower() for part in image.parts):
                    rows.append(row)
    return rows


def write_suite(rows: list[dict[str, Any]], path: Path, *, force_test_split: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            out = dict(row)
            if force_test_split:
                out["split"] = "test"
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")


def image_hour(image: str) -> int | None:
    match = TIMESTAMP_RE.search(Path(image).name)
    if not match:
        return None
    return int(match.group(2)[:2])


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "labels": dict(Counter(row.get("label") for row in rows)),
        "sources": dict(Counter(row.get("source") for row in rows)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--travbyen-name", default="edge-qa-v2-travbyen-daylight-realworld-manifest.jsonl")
    parser.add_argument("--night-name", default="edge-qa-v2-froekjaer-night-0100-0559-manifest.jsonl")
    parser.add_argument("--holdout-train-name", default="edge-qa-v2-balanced-train-with-realworld-holdout-manifest.jsonl")
    parser.add_argument("--realworld-name", default="edge-qa-v2-realworld-only-manifest.jsonl")
    args = parser.parse_args()

    rows = load_jsonl(args.manifest)

    travbyen = [
        row for row in rows
        if "/Kirkbi_A_S/Travbyen/" in str(row.get("image", ""))
        and row.get("source") == "historical_cpu_qa"
    ]
    night = []
    for row in rows:
        image = str(row.get("image", ""))
        hour = image_hour(image)
        if (
            "/Frøkjær/Nordre_Villavej_17c/" in image
            and row.get("source") == "historical_cpu_qa"
            and hour is not None
            and 1 <= hour <= 5
        ):
            night.append(row)
    realworld = [
        row for row in rows
        if row.get("source") == "historical_cpu_qa"
    ]

    travbyen_path = args.out_dir / args.travbyen_name
    night_path = args.out_dir / args.night_name
    realworld_path = args.out_dir / args.realworld_name
    holdout_images = {str(row.get("image")) for row in travbyen}
    holdout_images.update(str(row.get("image")) for row in night)
    holdout_train = [row for row in rows if str(row.get("image")) not in holdout_images]
    holdout_train_path = args.out_dir / args.holdout_train_name
    write_suite(travbyen, travbyen_path, force_test_split=True)
    write_suite(night, night_path, force_test_split=True)
    write_suite(realworld, realworld_path, force_test_split=False)
    write_suite(holdout_train, holdout_train_path, force_test_split=False)

    summary = {
        "source_manifest": str(args.manifest),
        "suites": {
            "travbyen_daylight_realworld": {"path": str(travbyen_path), **summarize(travbyen)},
            "froekjaer_night_0100_0559": {"path": str(night_path), **summarize(night)},
            "balanced_train_with_realworld_holdout": {
                "path": str(holdout_train_path),
                "held_out_images": len(holdout_images),
                **summarize(holdout_train),
            },
            "realworld_only": {"path": str(realworld_path), **summarize(realworld)},
        },
    }
    summary_path = args.out_dir / "edge-qa-v2-eval-suites-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
