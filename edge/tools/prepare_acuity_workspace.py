#!/usr/bin/env python3
"""Prepare an Allwinner ACUITY workspace for the Edge QA ONNX model."""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def select_rows(rows: list[dict[str, Any]], per_label: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        image = Path(str(row.get("image") or ""))
        if image.exists():
            buckets[str(row.get("label") or "unknown")].append(row)
    selected: list[dict[str, Any]] = []
    for label in sorted(buckets):
        label_rows = sorted(
            buckets[label],
            key=lambda row: (
                str(row.get("split") or "") != "train",
                str(row.get("review_priority") or "") != "auto_candidate",
                row.get("image", ""),
            ),
        )
        selected.extend(label_rows[:per_label])
    return selected


def copy_calibration_images(rows: list[dict[str, Any]], out_dir: Path) -> list[str]:
    calibration_dir = out_dir / "calibration"
    calibration_dir.mkdir(parents=True, exist_ok=True)
    dataset: list[str] = []
    label_counts: Counter[str] = Counter()
    for row in rows:
        src = Path(str(row["image"]))
        label = str(row.get("label") or "unknown")
        idx = label_counts[label]
        label_counts[label] += 1
        safe_label = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in label)
        dst = calibration_dir / f"{safe_label}_{idx:03d}_{src.name}"
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            continue
        img = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(dst), img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        dataset.append(str(dst.relative_to(out_dir)))
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to edge_qa_model.onnx")
    parser.add_argument("--manifest", required=True, help="Curated training manifest")
    parser.add_argument("--metadata", default="", help="Optional model metadata JSON")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--name", default="edge_qa_model")
    parser.add_argument("--per-label", type=int, default=24)
    args = parser.parse_args()

    model = Path(args.model)
    out_dir = Path(args.out_dir)
    model_dir = out_dir / args.name
    if model_dir.exists():
        shutil.rmtree(model_dir)
    model_dir.mkdir(parents=True)

    target_model = model_dir / f"{args.name}.onnx"
    shutil.copy2(model, target_model)
    external_data = model.with_name(model.name + ".data")
    if external_data.exists():
        shutil.copy2(external_data, model_dir / external_data.name)
    if args.metadata:
        metadata = Path(args.metadata)
        if metadata.exists():
            shutil.copy2(metadata, model_dir / metadata.name)

    rows = select_rows(load_rows(Path(args.manifest)), args.per_label)
    dataset = copy_calibration_images(rows, model_dir)
    (model_dir / "dataset.txt").write_text("\n".join(dataset) + ("\n" if dataset else ""), encoding="utf-8")
    (model_dir / "inputs_outputs.txt").write_text(
        "--inputs image --input-size-list '3,224,224' --outputs logits\n",
        encoding="utf-8",
    )
    # The MobileNet smoke ONNX graph contains ImageNet normalization internally.
    # ACUITY should therefore only scale raw 8-bit RGB pixels to 0..1.
    (model_dir / "channel_mean_value.txt").write_text("0 0 0 0.00392157\n", encoding="utf-8")
    (model_dir / "README_TIMELAPSE.md").write_text(
        "\n".join([
            "# TimeLapse Edge QA ACUITY workspace",
            "",
            "Target: Orange Pi 4 Pro A733 / NPU v3 / VIPLite v2.0",
            "Input: NCHW RGB, 3x224x224, scale 1/255.",
            "Output: `logits` with 9 classes from `edge.ai.model_contract`.",
            "",
            "Run from the ACUITY models directory:",
            "",
            "```bash",
            "export ACUITY_PATH=/path/to/acuity-toolkit",
            "export VIV_SDK=/opt/timelapse/ai-sdk/unified-tina",
            "source ../scripts/pegasus_setup.sh v3",
            "../scripts/pegasus_import.sh edge_qa_model",
            "../scripts/pegasus_quantize.sh edge_qa_model uint8",
            "../scripts/pegasus_inference.sh edge_qa_model uint8",
            "../scripts/pegasus_export_ovx_nbg.sh edge_qa_model uint8 $VSIMULATOR_CONFIG $VIV_SDK",
            "```",
        ]) + "\n",
        encoding="utf-8",
    )

    summary = {
        "status": "ok",
        "workspace": str(model_dir),
        "model": str(target_model),
        "external_data": str(model_dir / external_data.name) if external_data.exists() else None,
        "dataset_rows": len(dataset),
        "labels": Counter(row.get("label") for row in rows),
    }
    print(json.dumps(summary, ensure_ascii=False, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
