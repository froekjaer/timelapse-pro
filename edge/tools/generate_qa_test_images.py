#!/usr/bin/env python3
"""
Generate synthetic QA test images for TimeLapse Pro edge analysis.

The images are intentionally simple and deterministic. They are useful for
manual UI checks, regression tests and edge runtime smoke tests when no camera
is attached.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def _grid(width: int = 1280, height: int = 720, value: int = 128) -> np.ndarray:
    img = np.full((height, width, 3), value, dtype=np.uint8)
    for y in range(0, height, 24):
        cv2.line(img, (0, y), (width - 1, y), (230, 230, 230), 1)
    for x in range(0, width, 24):
        cv2.line(img, (x, 0), (x, height - 1), (230, 230, 230), 1)
    cv2.putText(img, "TimeLapse Pro QA", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (20, 20, 20), 3)
    return img


def _write(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), img):
        raise RuntimeError(f"Could not write {path}")


def generate(out_dir: Path) -> list[Path]:
    outputs: list[Path] = []

    normal = _grid(value=135)
    outputs.append(out_dir / "qa_01_normal_balanced.jpg")
    _write(outputs[-1], normal)

    under = _grid(value=35)
    outputs.append(out_dir / "qa_02_underexposed.jpg")
    _write(outputs[-1], under)

    over = _grid(value=218)
    cv2.circle(over, (640, 360), 150, (255, 255, 255), -1)
    outputs.append(out_dir / "qa_03_direct_sun_reflection.jpg")
    _write(outputs[-1], over)

    blurry = cv2.GaussianBlur(_grid(value=145), (41, 41), 0)
    outputs.append(out_dir / "qa_04_blurry_focus.jpg")
    _write(outputs[-1], blurry)

    cool = _grid(value=125)
    cool[:, :, 0] = np.clip(cool[:, :, 0] + 85, 0, 255)
    cool[:, :, 2] = np.clip(cool[:, :, 2] - 35, 0, 255)
    outputs.append(out_dir / "qa_05_cool_white_balance.jpg")
    _write(outputs[-1], cool)

    dof_base = _grid(value=140)
    dof = cv2.GaussianBlur(dof_base, (39, 39), 0)
    h, w = dof.shape[:2]
    dof[h // 4:h * 3 // 4, w // 4:w * 3 // 4] = dof_base[h // 4:h * 3 // 4, w // 4:w * 3 // 4]
    outputs.append(out_dir / "qa_06_shallow_depth_of_field.jpg")
    _write(outputs[-1], dof)

    dirty = cv2.GaussianBlur(_grid(value=190), (51, 51), 0)
    dirty = cv2.addWeighted(dirty, 0.65, np.full_like(dirty, 245), 0.35, 0)
    outputs.append(out_dir / "qa_07_snow_or_dirty_lens.jpg")
    _write(outputs[-1], dirty)

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/timelapse-qa-test-images")
    args = parser.parse_args()
    outputs = generate(Path(args.out))
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
