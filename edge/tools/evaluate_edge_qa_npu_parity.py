#!/usr/bin/env python3
"""Compare Edge QA ONNX CPU output with Orange Pi VIPLite/NPU output."""

from __future__ import annotations

import argparse
import json
import math
import random
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort


LABELS = [
    "ok",
    "blurry",
    "depth_of_field_issue",
    "snow_or_dirt_on_lens",
    "condensation",
    "direct_sun_reflection",
    "underexposed",
    "overexposed",
    "white_balance_cast",
]


def _iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.jpg")
        if path.is_file() and ".thumbs" not in path.parts
    )


def _pick_images(root: Path, limit: int, seed: int) -> list[Path]:
    images = _iter_images(root)
    rng = random.Random(seed)
    if limit and len(images) > limit:
        return sorted(rng.sample(images, limit))
    return images


def _softmax(logits: np.ndarray) -> np.ndarray:
    logits = logits.astype(np.float32)
    logits = logits - float(np.max(logits))
    exp = np.exp(logits)
    return exp / max(float(np.sum(exp)), 1e-9)


def _onnx_scores(session: ort.InferenceSession, image: Path) -> dict[str, float]:
    img = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image: {image}")
    img = cv2.cvtColor(cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    arr = img.astype("float32") / 255.0
    nchw = np.transpose(arr, (2, 0, 1))[None, ...]
    logits = session.run(None, {session.get_inputs()[0].name: nchw})[0][0]
    probs = _softmax(np.asarray(logits, dtype=np.float32))
    return {label: float(probs[idx]) for idx, label in enumerate(LABELS)}


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)


def _remote_npu_scores(
    image: Path,
    *,
    remote: str,
    remote_model: str,
    vendor_binary: str,
    input_layout: str,
    input_dtype: str | None,
    input_scale: str | None,
) -> dict[str, Any]:
    remote_image = f"/tmp/timelapse-edge-qa-parity-{image.name}"
    scp = _run(["scp", "-q", str(image), f"{remote}:{remote_image}"], timeout=60)
    if scp.returncode != 0:
        raise RuntimeError((scp.stderr or scp.stdout).strip())

    remote_cmd = [
        *shlex.split(vendor_binary),
        "--model",
        remote_model,
        "--image",
        remote_image,
        "--json",
        "--input-layout",
        input_layout,
        "--classes",
        str(len(LABELS)),
    ]
    if input_dtype:
        remote_cmd.extend(["--input-dtype", input_dtype])
    command = " ".join(shlex.quote(part) for part in remote_cmd)
    if input_scale is not None:
        command = f"TIMELAPSE_EDGE_QA_INPUT_SCALE={shlex.quote(input_scale)} {command}"
    proc = _run(["ssh", remote, command], timeout=30)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise RuntimeError((stderr or stdout)[-1000:])
    json_line = next((line for line in reversed(stdout.splitlines()) if line.strip().startswith("{")), stdout)
    payload = json.loads(json_line)
    if not payload.get("available", True):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def _top(scores: dict[str, float]) -> tuple[str, float]:
    label = max(scores, key=lambda key: scores[key])
    return label, float(scores[label])


def _metrics(cpu_scores: dict[str, float], npu_scores: dict[str, float]) -> dict[str, float]:
    cpu = np.asarray([cpu_scores[label] for label in LABELS], dtype=np.float64)
    npu = np.asarray([npu_scores[label] for label in LABELS], dtype=np.float64)
    eps = 1e-9
    return {
        "mae": float(np.mean(np.abs(cpu - npu))),
        "max_abs": float(np.max(np.abs(cpu - npu))),
        "cosine": float(np.dot(cpu, npu) / max(np.linalg.norm(cpu) * np.linalg.norm(npu), eps)),
        "kl_cpu_to_npu": float(np.sum(cpu * np.log((cpu + eps) / (npu + eps)))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--onnx-model", type=Path, required=True)
    parser.add_argument("--remote", default="orangepi@192.168.86.134")
    parser.add_argument("--remote-model", default="/opt/timelapse/models/edge_qa.nb")
    parser.add_argument("--vendor-binary", default="/opt/timelapse/bin/edge_qa_viplite")
    parser.add_argument("--input-layout", default="nchw_rgb")
    parser.add_argument("--input-dtype", default=None)
    parser.add_argument("--input-scale", default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260702)
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/edge-qa-npu-parity"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    jsonl_path = args.out_dir / f"edge_qa_npu_parity_{run_id}.jsonl"
    summary_path = args.out_dir / f"edge_qa_npu_parity_{run_id}_summary.json"

    images = _pick_images(args.image_root, args.limit, args.seed)
    session = ort.InferenceSession(str(args.onnx_model), providers=["CPUExecutionProvider"])

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for index, image in enumerate(images, 1):
            try:
                cpu_scores = _onnx_scores(session, image)
                npu_payload = _remote_npu_scores(
                    image,
                    remote=args.remote,
                    remote_model=args.remote_model,
                    vendor_binary=args.vendor_binary,
                    input_layout=args.input_layout,
                    input_dtype=args.input_dtype,
                    input_scale=args.input_scale,
                )
                npu_scores = {label: float(npu_payload["scores"][label]) for label in LABELS}
                cpu_top, cpu_conf = _top(cpu_scores)
                npu_top, npu_conf = _top(npu_scores)
                row = {
                    "image": str(image),
                    "cpu_top": cpu_top,
                    "cpu_confidence": cpu_conf,
                    "npu_top": npu_top,
                    "npu_confidence": npu_conf,
                    "top1_match": cpu_top == npu_top,
                    "metrics": _metrics(cpu_scores, npu_scores),
                    "cpu_scores": cpu_scores,
                    "npu_scores": npu_scores,
                }
                rows.append(row)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"[{index}/{len(images)}] {image.name}: cpu={cpu_top} npu={npu_top} match={row['top1_match']}")
            except Exception as exc:
                failure = {"image": str(image), "error": str(exc)}
                failures.append(failure)
                fh.write(json.dumps({"failure": failure}, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"[{index}/{len(images)}] {image.name}: ERROR {exc}")

    if rows:
        top1_matches = sum(1 for row in rows if row["top1_match"])
        metric_names = ["mae", "max_abs", "cosine", "kl_cpu_to_npu"]
        aggregates = {
            name: {
                "mean": float(np.mean([row["metrics"][name] for row in rows])),
                "median": float(np.median([row["metrics"][name] for row in rows])),
                "max": float(np.max([row["metrics"][name] for row in rows])),
            }
            for name in metric_names
        }
        confusion: dict[str, dict[str, int]] = {}
        for row in rows:
            confusion.setdefault(row["cpu_top"], {}).setdefault(row["npu_top"], 0)
            confusion[row["cpu_top"]][row["npu_top"]] += 1
        worst = sorted(rows, key=lambda row: row["metrics"]["mae"], reverse=True)[:20]
    else:
        top1_matches = 0
        aggregates = {}
        confusion = {}
        worst = []

    summary = {
        "run_id": run_id,
        "image_root": str(args.image_root),
        "onnx_model": str(args.onnx_model),
        "remote": args.remote,
        "remote_model": args.remote_model,
        "vendor_binary": args.vendor_binary,
        "input_layout": args.input_layout,
        "input_dtype": args.input_dtype or "vendor_default",
        "input_scale": args.input_scale or "default",
        "sampled": len(images),
        "completed": len(rows),
        "failed": len(failures),
        "top1_match_rate": float(top1_matches / len(rows)) if rows else 0.0,
        "aggregates": aggregates,
        "confusion_cpu_to_npu": confusion,
        "worst_by_mae": [
            {
                "image": row["image"],
                "cpu_top": row["cpu_top"],
                "npu_top": row["npu_top"],
                "mae": row["metrics"]["mae"],
                "max_abs": row["metrics"]["max_abs"],
                "cpu_confidence": row["cpu_confidence"],
                "npu_confidence": row["npu_confidence"],
            }
            for row in worst
        ],
        "failures": failures[:50],
        "jsonl": str(jsonl_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
