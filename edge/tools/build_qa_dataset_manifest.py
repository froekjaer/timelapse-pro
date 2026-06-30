#!/usr/bin/env python3
"""
Build a JSONL manifest for TimeLapse Edge QA training/evaluation images.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
    from ai.model_contract import LABEL_TO_SPEC, label_from_filename, label_from_probable_cause, validate_label
except Exception:
    from edge.ai.model_contract import LABEL_TO_SPEC, label_from_filename, label_from_probable_cause, validate_label


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


def image_size(path: Path) -> tuple[int | None, int | None]:
    img = cv2.imread(str(path))
    if img is None:
        return None, None
    height, width = img.shape[:2]
    return int(width), int(height)


def load_batch_labels(path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not path:
        return labels
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            image = str(row.get("image") or "")
            if not image:
                continue
            cause = row.get("probable_cause")
            label = label_from_probable_cause(str(cause), default="")
            if label:
                labels[image] = label
                labels[Path(image).name] = label
    return labels


def split_for_index(index: int, train_ratio: float, val_ratio: float) -> str:
    bucket = index % 100
    train_cut = int(train_ratio * 100)
    val_cut = train_cut + int(val_ratio * 100)
    if bucket < train_cut:
        return "train"
    if bucket < val_cut:
        return "val"
    return "test"


def build_row(
    image: Path,
    *,
    index: int,
    source: str,
    default_label: str,
    batch_labels: dict[str, str],
    train_ratio: float,
    val_ratio: float,
    created_at: str,
) -> dict[str, Any]:
    label = (
        batch_labels.get(str(image))
        or batch_labels.get(image.name)
        or label_from_filename(image.name, default=default_label)
    )
    spec = validate_label(label)
    width, height = image_size(image)
    return {
        "schema": "timelapse.edge_qa.dataset_manifest.v1",
        "image": str(image.resolve()),
        "label": spec.label,
        "class_id": spec.class_id,
        "probable_cause": spec.probable_cause,
        "quality_dimension": spec.quality_dimension,
        "split": split_for_index(index, train_ratio, val_ratio),
        "source": source,
        "sha256": sha256_file(image),
        "width": width,
        "height": height,
        "created_at": created_at,
        "notes": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="Image files or folders")
    parser.add_argument("--out", required=True, help="JSONL output path")
    parser.add_argument("--source", default="edge_qa_manifest")
    parser.add_argument("--default-label", default="ok", choices=sorted(LABEL_TO_SPEC))
    parser.add_argument("--from-batch-jsonl", default="", help="Optional analyse_qa_batch.py JSONL output")
    parser.add_argument("--train-ratio", type=float, default=0.80)
    parser.add_argument("--val-ratio", type=float, default=0.10)
    args = parser.parse_args()

    if args.train_ratio < 0 or args.val_ratio < 0 or args.train_ratio + args.val_ratio >= 1:
        raise SystemExit("--train-ratio + --val-ratio must be between 0 and 1")

    images = list(iter_images(Path(p) for p in args.paths))
    batch_labels = load_batch_labels(Path(args.from_batch_jsonl)) if args.from_batch_jsonl else {}
    created_at = datetime.now(timezone.utc).isoformat()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for index, image in enumerate(images):
            row = build_row(
                image,
                index=index,
                source=args.source,
                default_label=args.default_label,
                batch_labels=batch_labels,
                train_ratio=args.train_ratio,
                val_ratio=args.val_ratio,
                created_at=created_at,
            )
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "ok", "images": len(images), "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
