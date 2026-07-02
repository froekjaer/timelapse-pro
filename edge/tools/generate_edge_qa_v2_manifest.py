#!/usr/bin/env python3
"""Build a balanced Edge QA manifest with reproducible synthetic lens defects."""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _import_edge_modules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_import_edge_modules()
try:
    from edge.ai.model_contract import LABEL_TO_SPEC, QA_CLASSES, validate_label
except Exception:
    from ai.model_contract import LABEL_TO_SPEC, QA_CLASSES, validate_label


SYNTHETIC_LABELS = {
    "blurry",
    "snow_or_dirt_on_lens",
    "condensation",
    "white_balance_cast",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                if row.get("label") in LABEL_TO_SPEC and Path(str(row.get("image", ""))).exists():
                    rows.append(row)
    return rows


def with_label(row: dict[str, Any], label: str, image: Path, *, source_label: str, transform: str) -> dict[str, Any]:
    spec = validate_label(label)
    out = dict(row)
    out.update({
        "schema": "timelapse.edge_qa.training_curated.v2",
        "image": str(image),
        "label": spec.label,
        "class_id": spec.class_id,
        "probable_cause": spec.probable_cause,
        "quality_dimension": spec.quality_dimension,
        "confidence": 0.82,
        "review_priority": "synthetic_candidate",
        "source": "synthetic_edge_qa_v2",
        "synthetic": {
            "source_image": row.get("image"),
            "source_label": source_label,
            "transform": transform,
        },
        "notes": f"synthetic {label} from {source_label}",
    })
    return out


def split_for_index(idx: int) -> str:
    mod = idx % 10
    if mod == 8:
        return "val"
    if mod == 9:
        return "test"
    return "train"


def read_source(path: str, max_dim: int) -> np.ndarray | None:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = min(1.0, float(max_dim) / float(max(h, w)))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    return img


def synth_blurry(img: np.ndarray, rng: random.Random) -> tuple[np.ndarray, str]:
    k = rng.choice([9, 11, 13, 15, 17])
    if rng.random() < 0.45:
        kernel = np.zeros((k, k), dtype=np.float32)
        if rng.random() < 0.5:
            kernel[k // 2, :] = 1.0
            transform = f"motion_blur_horizontal_{k}"
        else:
            kernel[:, k // 2] = 1.0
            transform = f"motion_blur_vertical_{k}"
        kernel /= kernel.sum()
        return cv2.filter2D(img, -1, kernel), transform
    return cv2.GaussianBlur(img, (k, k), rng.uniform(1.5, 4.0)), f"gaussian_blur_{k}"


def synth_white_balance(img: np.ndarray, rng: random.Random) -> tuple[np.ndarray, str]:
    out = img.astype(np.float32)
    if rng.random() < 0.5:
        gains = np.array([rng.uniform(0.78, 0.92), rng.uniform(0.95, 1.05), rng.uniform(1.18, 1.38)], dtype=np.float32)
        transform = "warm_cast"
    else:
        gains = np.array([rng.uniform(1.18, 1.40), rng.uniform(0.96, 1.06), rng.uniform(0.76, 0.92)], dtype=np.float32)
        transform = "cool_cast"
    out *= gains.reshape(1, 1, 3)
    out = cv2.convertScaleAbs(np.clip(out, 0, 255), alpha=rng.uniform(0.96, 1.05), beta=rng.uniform(-4, 4))
    return out, transform


def synth_snow_or_dirt(img: np.ndarray, rng: random.Random) -> tuple[np.ndarray, str]:
    h, w = img.shape[:2]
    overlay = img.copy().astype(np.float32)
    mask = np.zeros((h, w), dtype=np.float32)
    for _ in range(rng.randint(12, 34)):
        cx = rng.randint(0, w - 1)
        cy = rng.randint(0, h - 1)
        radius = rng.randint(max(4, min(h, w) // 90), max(10, min(h, w) // 22))
        color = rng.uniform(180, 245)
        cv2.circle(mask, (cx, cy), radius, color, -1, lineType=cv2.LINE_AA)
    for _ in range(rng.randint(120, 360)):
        cx = rng.randint(0, w - 1)
        cy = rng.randint(0, h - 1)
        radius = rng.randint(1, max(2, min(h, w) // 220))
        cv2.circle(mask, (cx, cy), radius, rng.uniform(150, 255), -1, lineType=cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (0, 0), rng.uniform(1.2, 4.5))
    alpha = np.clip(mask / 255.0 * rng.uniform(0.35, 0.78), 0, 0.82)
    tint = np.full_like(overlay, rng.uniform(190, 245), dtype=np.float32)
    overlay = overlay * (1.0 - alpha[..., None]) + tint * alpha[..., None]
    return np.clip(overlay, 0, 255).astype(np.uint8), "translucent_snow_dirt_particles"


def synth_condensation(img: np.ndarray, rng: random.Random) -> tuple[np.ndarray, str]:
    h, w = img.shape[:2]
    soft = cv2.GaussianBlur(img, (0, 0), rng.uniform(5.0, 12.0)).astype(np.float32)
    haze = np.full_like(soft, rng.uniform(190, 235), dtype=np.float32)
    y, x = np.ogrid[:h, :w]
    cx = rng.uniform(0.35, 0.65) * w
    cy = rng.uniform(0.35, 0.65) * h
    radius = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    radial = 1.0 - np.clip(radius / (0.75 * max(h, w)), 0, 1)
    alpha = np.clip(radial * rng.uniform(0.20, 0.48) + rng.uniform(0.10, 0.22), 0, 0.62)
    out = soft * (1.0 - alpha[..., None]) + haze * alpha[..., None]
    noise = np.random.default_rng(rng.randint(0, 2**32 - 1)).normal(0, rng.uniform(2.0, 5.0), out.shape)
    return np.clip(out + noise, 0, 255).astype(np.uint8), "soft_haze_condensation"


def synthesize(label: str, img: np.ndarray, rng: random.Random) -> tuple[np.ndarray, str]:
    if label == "blurry":
        return synth_blurry(img, rng)
    if label == "white_balance_cast":
        return synth_white_balance(img, rng)
    if label == "snow_or_dirt_on_lens":
        return synth_snow_or_dirt(img, rng)
    if label == "condensation":
        return synth_condensation(img, rng)
    raise ValueError(f"No synthetic transform for {label}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", nargs="+", required=True, help="Candidate/curated JSONL files")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--synthetic-dir", required=True)
    parser.add_argument("--target-per-label", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-source-dim", type=int, default=1024)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    rows: list[dict[str, Any]] = []
    for path in args.input:
        rows.extend(load_jsonl(Path(path)))

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row["label"])].append(row)

    selected: list[dict[str, Any]] = []
    for spec in QA_CLASSES:
        label_rows = list(buckets.get(spec.label, []))
        rng.shuffle(label_rows)
        label_rows.sort(key=lambda row: (
            str(row.get("review_priority") or "") != "human_approved",
            str(row.get("review_priority") or "") != "auto_candidate",
            row.get("image", ""),
        ))
        selected.extend(label_rows[: args.target_per_label])

    source_pool = [
        row for label in ("ok", "depth_of_field_issue", "direct_sun_reflection", "overexposed", "underexposed")
        for row in buckets.get(label, [])
    ]
    if not source_pool:
        raise SystemExit("No usable source images for synthetic generation")
    rng.shuffle(source_pool)

    synthetic_dir = Path(args.synthetic_dir)
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter(row["label"] for row in selected)
    synth_counts: Counter[str] = Counter()
    source_idx = 0
    for spec in QA_CLASSES:
        label = spec.label
        if label not in SYNTHETIC_LABELS:
            continue
        needed = max(0, args.target_per_label - counts[label])
        label_dir = synthetic_dir / label
        label_dir.mkdir(parents=True, exist_ok=True)
        attempts = 0
        while synth_counts[label] < needed and attempts < needed * 20:
            attempts += 1
            source = source_pool[source_idx % len(source_pool)]
            source_idx += 1
            img = read_source(str(source["image"]), args.max_source_dim)
            if img is None:
                continue
            out_img, transform = synthesize(label, img, rng)
            idx = synth_counts[label]
            dst = label_dir / f"{label}_{idx:05d}_{Path(str(source['image'])).stem}.jpg"
            cv2.imwrite(str(dst), out_img, [int(cv2.IMWRITE_JPEG_QUALITY), 91])
            row = with_label(source, label, dst, source_label=str(source["label"]), transform=transform)
            row["split"] = split_for_index(idx)
            selected.append(row)
            synth_counts[label] += 1

    selected.sort(key=lambda row: (str(row.get("split")), str(row.get("label")), str(row.get("image"))))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "status": "ok",
        "input_rows": len(rows),
        "selected_rows": len(selected),
        "target_per_label": args.target_per_label,
        "labels": Counter(row["label"] for row in selected),
        "splits": Counter(row.get("split") for row in selected),
        "synthetic_labels": synth_counts,
        "out": str(out),
        "synthetic_dir": str(synthetic_dir),
    }
    summary = json.loads(json.dumps(summary, ensure_ascii=False, default=dict))
    if args.summary_out:
        Path(args.summary_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
