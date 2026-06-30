#!/usr/bin/env python3
"""
Render contact sheets from an Edge QA candidate manifest for human review.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def fit_thumb(image_path: Path, width: int, height: int) -> np.ndarray:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        img = np.full((height, width, 3), 230, dtype=np.uint8)
        cv2.putText(img, "unreadable", (10, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 180), 2)
        return img
    h, w = img.shape[:2]
    scale = min(width / max(w, 1), height / max(h, 1))
    resized = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    canvas = np.full((height, width, 3), 245, dtype=np.uint8)
    y = (height - resized.shape[0]) // 2
    x = (width - resized.shape[1]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


def draw_card(row: dict[str, Any], thumb_w: int, thumb_h: int) -> np.ndarray:
    label_h = 56
    card = np.full((thumb_h + label_h, thumb_w, 3), 255, dtype=np.uint8)
    thumb = fit_thumb(Path(row["image"]), thumb_w, thumb_h)
    card[:thumb_h, :] = thumb
    label = str(row.get("label", "?"))
    confidence = row.get("confidence")
    priority = str(row.get("review_priority", ""))
    text1 = f"{label}  conf={confidence}"
    text2 = f"{priority}  {Path(row['image']).name[:34]}"
    cv2.rectangle(card, (0, thumb_h), (thumb_w - 1, thumb_h + label_h - 1), (250, 250, 250), -1)
    cv2.putText(card, text1, (8, thumb_h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(card, text2, (8, thumb_h + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (80, 80, 80), 1, cv2.LINE_AA)
    return card


def render_sheet(rows: list[dict[str, Any]], out_path: Path, cols: int, thumb_w: int, thumb_h: int) -> None:
    if not rows:
        return
    cards = [draw_card(row, thumb_w, thumb_h) for row in rows]
    card_h, card_w = cards[0].shape[:2]
    rows_count = int(np.ceil(len(cards) / cols))
    sheet = np.full((rows_count * card_h, cols * card_w, 3), 245, dtype=np.uint8)
    for idx, card in enumerate(cards):
        y = (idx // cols) * card_h
        x = (idx % cols) * card_w
        sheet[y:y + card_h, x:x + card_w] = card
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out_path), sheet):
        raise RuntimeError(f"Could not write {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-per-label", type=int, default=80)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=360)
    parser.add_argument("--thumb-height", type=int, default=220)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    rows = load_rows(Path(args.manifest))
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_label[str(row.get("label", "unknown"))].append(row)

    review_csv = out_dir / "review.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    with review_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["image", "label", "confidence", "review_priority", "approved_label", "notes"])
        writer.writeheader()
        for label, label_rows in sorted(by_label.items()):
            label_rows.sort(key=lambda row: (-float(row.get("confidence") or 0.0), row["image"]))
            selected = label_rows[:args.max_per_label]
            render_sheet(selected, out_dir / f"{label}.jpg", args.cols, args.thumb_width, args.thumb_height)
            for row in selected:
                writer.writerow({
                    "image": row["image"],
                    "label": row.get("label"),
                    "confidence": row.get("confidence"),
                    "review_priority": row.get("review_priority"),
                    "approved_label": "",
                    "notes": "",
                })
    print(json.dumps({"status": "ok", "labels": sorted(by_label), "out_dir": str(out_dir), "review_csv": str(review_csv)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
