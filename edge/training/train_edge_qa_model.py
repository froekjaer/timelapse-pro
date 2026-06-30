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


def read_resized_image(path: str, size: int) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


def image_array_to_tensor(img: np.ndarray, augment: bool, torch):
    if augment:
        img = img.copy()
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


def image_to_tensor(path: str, size: int, augment: bool, torch):
    return image_array_to_tensor(read_resized_image(path, size), augment, torch)


def prepare_rows(
    rows: list[dict[str, Any]],
    *,
    input_size: int,
    preload: bool,
    skip_unreadable: bool,
    skipped_out: Path | None,
) -> list[dict[str, Any]]:
    usable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        try:
            if preload:
                prepared = dict(row)
                prepared["_image_rgb"] = read_resized_image(str(row["image"]), input_size)
                usable.append(prepared)
            else:
                usable.append(row)
        except Exception as exc:
            if not skip_unreadable:
                raise
            skipped.append({"image": row.get("image"), "label": row.get("label"), "error": str(exc)})
    if skipped_out:
        skipped_out.parent.mkdir(parents=True, exist_ok=True)
        with skipped_out.open("w", encoding="utf-8") as fh:
            for row in skipped:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if skip_unreadable and skipped:
        print(json.dumps({"event": "skipped_unreadable", "count": len(skipped), "out": str(skipped_out) if skipped_out else None}, ensure_ascii=False), flush=True)
    return usable


def make_model(nn, num_classes: int, *, arch: str, pretrained: bool, freeze_backbone: bool):
    if arch == "mobilenet_v2":
        try:
            import torch
            import torchvision.models as models
        except Exception as exc:
            raise SystemExit("torchvision is required for --arch mobilenet_v2") from exc

        weights = None
        if pretrained:
            try:
                weights = models.MobileNet_V2_Weights.DEFAULT
            except Exception:
                weights = None
        backbone = models.mobilenet_v2(weights=weights)
        if freeze_backbone:
            for param in backbone.features.parameters():
                param.requires_grad = False
        in_features = backbone.classifier[-1].in_features
        backbone.classifier[-1] = nn.Linear(in_features, num_classes)

        class ImageNetNormalize(nn.Module):
            def __init__(self):
                super().__init__()
                self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
                self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

            def forward(self, x):
                return (x - self.mean) / self.std

        return nn.Sequential(ImageNetNormalize(), backbone)

    def block(inp, out, stride=1):
        return nn.Sequential(
            nn.Conv2d(inp, out, 3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out),
            nn.ReLU(inplace=True),
        )

    def ds_block(inp, out, stride=1):
        return nn.Sequential(
            nn.Conv2d(inp, inp, 3, stride=stride, padding=1, groups=inp, bias=False),
            nn.BatchNorm2d(inp),
            nn.ReLU(inplace=True),
            nn.Conv2d(inp, out, 1, bias=False),
            nn.BatchNorm2d(out),
            nn.ReLU(inplace=True),
        )

    return nn.Sequential(
        block(3, 8, 4),
        ds_block(8, 12, 2),
        ds_block(12, 20, 2),
        ds_block(20, 32, 2),
        nn.AdaptiveAvgPool2d((1, 1)),
        nn.Flatten(),
        nn.Dropout(0.10),
        nn.Linear(32, num_classes),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--arch", choices=["micro", "mobilenet_v2"], default="micro")
    parser.add_argument("--pretrained", action="store_true", help="Use pretrained weights when supported")
    parser.add_argument("--freeze-backbone", action="store_true", help="Freeze feature extractor when supported")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--preload", action="store_true", help="Read and resize images once before training")
    parser.add_argument("--skip-unreadable", action="store_true", help="Skip unreadable images and write skipped-images.jsonl")
    args = parser.parse_args()

    torch, nn, DataLoader, Dataset = require_torch()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    input_size = int(MODEL_INPUT_CONTRACT["width"])
    rows = prepare_rows(
        load_manifest(Path(args.manifest)),
        input_size=input_size,
        preload=args.preload,
        skip_unreadable=args.skip_unreadable,
        skipped_out=Path(args.out_dir) / "skipped-images.jsonl",
    )

    class QaDataset(Dataset):
        def __init__(self, items: list[dict[str, Any]], augment: bool):
            self.items = items
            self.augment = augment

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, idx: int):
            row = self.items[idx]
            if "_image_rgb" in row:
                tensor = image_array_to_tensor(row["_image_rgb"], self.augment, torch)
            else:
                tensor = image_to_tensor(row["image"], input_size, self.augment, torch)
            return tensor, int(row["class_id"])

    train_rows = [r for r in rows if r.get("split") == "train"]
    val_rows = [r for r in rows if r.get("split") == "val"]
    test_rows = [r for r in rows if r.get("split") == "test"]
    if not train_rows or not val_rows:
        raise SystemExit("Manifest must contain train and val rows")

    device = "mps" if args.device == "auto" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    if args.device != "auto":
        device = args.device

    print(json.dumps({"event": "training_start", "device": device, "arch": args.arch, "pretrained": args.pretrained, "freeze_backbone": args.freeze_backbone, "rows": len(rows)}, ensure_ascii=False), flush=True)
    model = make_model(
        nn,
        len(LABEL_TO_SPEC),
        arch=args.arch,
        pretrained=args.pretrained,
        freeze_backbone=args.freeze_backbone,
    ).to(device)
    counts = Counter(int(r["class_id"]) for r in train_rows)
    weights = torch.ones(len(LABEL_TO_SPEC), dtype=torch.float32)
    for class_id in range(len(LABEL_TO_SPEC)):
        weights[class_id] = 1.0 / max(counts.get(class_id, 1), 1)
    weights = (weights / weights.mean()).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    train_loader = DataLoader(QaDataset(train_rows, True), batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(QaDataset(val_rows, False), batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)
    test_loader = DataLoader(QaDataset(test_rows, False), batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers) if test_rows else None

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
        print(json.dumps(metrics, ensure_ascii=False), flush=True)
        if metrics["accuracy"] > best_acc:
            best_acc = metrics["accuracy"]
            torch.save(model.state_dict(), best_path)

    model.load_state_dict(torch.load(best_path, map_location=device))
    model.eval()
    test_metrics = evaluate(test_loader) if test_loader else None
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
        "label_counts": Counter(row["label"] for row in rows),
        "split_counts": Counter(row["split"] for row in rows),
        "arch": args.arch,
        "pretrained": args.pretrained,
        "freeze_backbone": args.freeze_backbone,
        "preload": args.preload,
        "skip_unreadable": args.skip_unreadable,
        "input_normalization": "imagenet_inside_onnx" if args.arch == "mobilenet_v2" else "scale_0_1",
        "history": history,
        "test_metrics": test_metrics,
        "best_val_accuracy": best_acc,
        "onnx": str(onnx_path),
        "pytorch": str(best_path),
    }
    (out_dir / "edge_qa_model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "out_dir": str(out_dir),
        "onnx": str(onnx_path),
        "best_val_accuracy": best_acc,
        "test_accuracy": test_metrics["accuracy"] if test_metrics else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
