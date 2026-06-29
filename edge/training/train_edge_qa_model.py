#!/usr/bin/env python3
"""
Train a compact Edge QA classifier and export ONNX for ACUITY conversion.

Run this in a separate training venv, not the production headend/edge venv.
The production runtime only needs the exported .nb and the VIPLite wrapper.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
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
    from edge.ai.model_contract import LABEL_TO_SPEC, MODEL_INPUT_CONTRACT, contract_metadata
except Exception:
    from ai.model_contract import LABEL_TO_SPEC, MODEL_INPUT_CONTRACT, contract_metadata


def require_torch():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset
    except Exception as exc:
        raise SystemExit(
            "PyTorch is not installed. Create an isolated training venv and run: "
            "pip install -r edge/training/requirements-edge-qa.txt"
        ) from exc
    return torch, nn, DataLoader, Dataset


def load_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                if row.get("label") in LABEL_TO_SPEC and Path(row["image"]).exists():
                    rows.append(row)
    if not rows:
        raise SystemExit(f"No usable rows in {path}")
    return rows


def image_to_tensor(path: str, size: int, augment: bool, torch):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    if augment:
        if random.random() < 0.5:
            img = cv2.flip(img, 1)
        if random.random() < 0.35:
            alpha = random.uniform(0.82, 1.18)
            beta = random.uniform(-18, 18)
            img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
        if random.random() < 0.20:
            k = random.choice([3, 5])
            img = cv2.GaussianBlur(img, (k, k), 0)
    arr = img.astype("float32") / 255.0
    arr = np.transpose(arr, (2, 0, 1))
    return torch.from_numpy(arr)


def make_model(nn, num_classes: int):
    def block(inp, out, stride=1):
        return nn.Sequential(
            nn.Conv2d(inp, out, 3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out),
            nn.ReLU(inplace=True),
            nn.Conv2d(out, out, 3, padding=1, bias=False),
            nn.BatchNorm2d(out),
            nn.ReLU(inplace=True),
        )

    return nn.Sequential(
        block(3, 24, 2),
        block(24, 48, 2),
        block(48, 96, 2),
        block(96, 160, 2),
        nn.AdaptiveAvgPool2d((1, 1)),
        nn.Flatten(),
        nn.Dropout(0.15),
        nn.Linear(160, num_classes),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    torch, nn, DataLoader, Dataset = require_torch()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    rows = load_manifest(Path(args.manifest))
    input_size = int(MODEL_INPUT_CONTRACT["width"])

    class QaDataset(Dataset):
        def __init__(self, items: list[dict[str, Any]], augment: bool):
            self.items = items
            self.augment = augment

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, idx: int):
            row = self.items[idx]
            return image_to_tensor(row["image"], input_size, self.augment, torch), int(row["class_id"])

    train_rows = [r for r in rows if r.get("split") == "train"]
    val_rows = [r for r in rows if r.get("split") == "val"]
    test_rows = [r for r in rows if r.get("split") == "test"]
    if not train_rows or not val_rows:
        raise SystemExit("Manifest must contain train and val rows")

    device = "mps" if args.device == "auto" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    if args.device != "auto":
        device = args.device

    model = make_model(nn, len(LABEL_TO_SPEC)).to(device)
    counts = Counter(int(r["class_id"]) for r in train_rows)
    weights = torch.ones(len(LABEL_TO_SPEC), dtype=torch.float32)
    for class_id in range(len(LABEL_TO_SPEC)):
        weights[class_id] = 1.0 / max(counts.get(class_id, 1), 1)
    weights = (weights / weights.mean()).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    train_loader = DataLoader(QaDataset(train_rows, True), batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(QaDataset(val_rows, False), batch_size=args.batch_size, shuffle=False, num_workers=0)

    def evaluate(loader):
        model.eval()
        total = correct = 0
        loss_sum = 0.0
        per_class: dict[int, list[int]] = {}
        with torch.no_grad():
            for x, y in loader:
                x = x.to(device)
                y = y.to(device)
                logits = model(x)
                loss = loss_fn(logits, y)
                pred = logits.argmax(dim=1)
                total += int(y.numel())
                correct += int((pred == y).sum().item())
                loss_sum += float(loss.item()) * int(y.numel())
                for cls, ok in zip(y.cpu().tolist(), (pred == y).cpu().tolist()):
                    per_class.setdefault(int(cls), [0, 0])
                    per_class[int(cls)][0] += int(bool(ok))
                    per_class[int(cls)][1] += 1
        return {
            "loss": loss_sum / max(total, 1),
            "accuracy": correct / max(total, 1),
            "per_class_accuracy": {str(k): v[0] / max(v[1], 1) for k, v in sorted(per_class.items())},
        }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_acc = -1.0
    history = []
    best_path = out_dir / "edge_qa_model.pt"
    for epoch in range(1, args.epochs + 1):
        model.train()
        for x, y in train_loader:
            x = x.to(device)
            y = y.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
        metrics = evaluate(val_loader)
        metrics["epoch"] = epoch
        history.append(metrics)
        print(json.dumps(metrics, ensure_ascii=False))
        if metrics["accuracy"] > best_acc:
            best_acc = metrics["accuracy"]
            torch.save(model.state_dict(), best_path)

    model.load_state_dict(torch.load(best_path, map_location=device))
    model.eval()
    dummy = torch.zeros(1, 3, input_size, input_size, device=device)
    onnx_path = out_dir / "edge_qa_model.onnx"
    torch.onnx.export(
        model,
        dummy,
        onnx_path,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=13,
    )

    metadata = {
        "contract": contract_metadata(),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "test_rows": len(test_rows),
        "history": history,
        "best_val_accuracy": best_acc,
        "onnx": str(onnx_path),
        "pytorch": str(best_path),
    }
    (out_dir / "edge_qa_model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "out_dir": str(out_dir), "onnx": str(onnx_path), "best_val_accuracy": best_acc}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
