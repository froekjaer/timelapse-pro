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
                rows.append(json.loads(line))
    return rows


def write_suite(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            out = dict(row)
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

    travbyen_path = args.out_dir / args.travbyen_name
    night_path = args.out_dir / args.night_name
    write_suite(travbyen, travbyen_path)
    write_suite(night, night_path)

    summary = {
        "source_manifest": str(args.manifest),
        "suites": {
            "travbyen_daylight_realworld": {"path": str(travbyen_path), **summarize(travbyen)},
            "froekjaer_night_0100_0559": {"path": str(night_path), **summarize(night)},
        },
    }
    summary_path = args.out_dir / "edge-qa-v2-eval-suites-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
