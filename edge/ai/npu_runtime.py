"""
Orange Pi / vendor NPU runtime detection for edge QA.

The Orange Pi 4 Pro A733 manual describes an Allwinner ACUITY -> VIPLite flow
where deployable models are exported as .nb files and executed through the
board-side ai-sdk examples/runtime. This module only probes; it never requires
the SDK to be installed for normal edge operation.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


AI_SDK_ROOT_CANDIDATES = (
    "/opt/timelapse/ai-sdk",
    "/opt/ai-sdk",
    "~/ai-sdk",
)

VIPLITE_LIBRARY_CANDIDATES = (
    "/usr/lib/libVIPLite.so",
    "/usr/lib/aarch64-linux-gnu/libVIPLite.so",
    "/usr/local/lib/libVIPLite.so",
    "/opt/timelapse/ai-sdk/viplite-tina",
    "/opt/ai-sdk/viplite-tina",
    "~/ai-sdk/viplite-tina",
)

NPU_DEVICE_CANDIDATES = (
    "/dev/galcore",
    "/dev/vipcore",
    "/dev/viplite",
    "/dev/npu",
)

AI_SDK_EXAMPLES = (
    "yolov5",
    "resnet50",
    "struct2depth",
    "transformer_cls",
    "yolact",
    "deepspeech2",
    "chineseocr",
)


def _expand(path: str) -> Path:
    return Path(path).expanduser()


def read_text(path: str) -> str | None:
    try:
        return Path(path).read_bytes().rstrip(b"\x00").decode("utf-8", "ignore")
    except Exception:
        return None


def _command_version(command: list[str], timeout_s: float = 2.0) -> str | None:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
    except Exception:
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    return text.splitlines()[0][:180] if text else None


def ai_sdk_root_candidates(extra: str | None = None) -> list[Path]:
    roots: list[Path] = []
    for value in (extra, os.getenv("TIMELAPSE_AI_SDK_ROOT")):
        if value:
            roots.append(_expand(value))
    roots.extend(_expand(path) for path in AI_SDK_ROOT_CANDIDATES)
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            deduped.append(root)
            seen.add(key)
    return deduped


def detect_orangepi_npu_runtime(
    *,
    ai_sdk_root: str | None = None,
    model_path: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-serialisable report about local NPU readiness."""
    roots = ai_sdk_root_candidates(ai_sdk_root)
    existing_roots = [root for root in roots if root.exists()]

    examples: dict[str, list[str]] = {}
    example_models: dict[str, list[str]] = {}
    for root in existing_roots:
        for name in AI_SDK_EXAMPLES:
            binary_hits = sorted((root / "examples" / name).glob(f"**/{name}"))
            if binary_hits:
                examples.setdefault(name, []).extend(str(path) for path in binary_hits)
            model_hits = sorted((root / "examples" / name / "model").glob("**/*.nb"))
            model_hits.extend(sorted((root / "models").glob(f"**/{name}*.nb")))
            if model_hits:
                example_models.setdefault(name, []).extend(str(path) for path in model_hits)

    viplite_hits = [
        str(path)
        for path in (_expand(candidate) for candidate in VIPLITE_LIBRARY_CANDIDATES)
        if path.exists()
    ]
    command_hits = {
        "onnxruntime_test": shutil.which("onnxruntime_test"),
        "rknn_lite_runtime": shutil.which("rknn_lite_runtime"),
        "hailortcli": shutil.which("hailortcli"),
        "python3": shutil.which("python3"),
        "cmake": shutil.which("cmake"),
        "make": shutil.which("make"),
    }
    command_hits = {key: value for key, value in command_hits.items() if value}

    devices = {path: Path(path).exists() for path in NPU_DEVICE_CANDIDATES}
    model = Path(model_path).expanduser() if model_path else None
    model_present = bool(model and model.exists())
    has_ai_sdk = bool(existing_roots)
    has_viplite = bool(viplite_hits)
    has_device = any(devices.values())
    npu_ready = bool(model_present and has_ai_sdk and (has_viplite or has_device))

    missing = []
    if not has_ai_sdk:
        missing.append("ai_sdk")
    if not (has_viplite or has_device):
        missing.append("viplite_runtime_or_device")
    if model_path and not model_present:
        missing.append("model_path")
    elif not model_path:
        missing.append("model_path_config")

    return {
        "engine": "orangepi_npu_probe_v1",
        "npu_ready": npu_ready,
        "preferred": "allwinner_viplite" if (has_ai_sdk or has_viplite or has_device) else None,
        "missing": missing,
        "manual_contract": {
            "npu": "3 TOPS",
            "model_format": ".nb",
            "pc_conversion": "Allwinner ACUITY Docker + ai-sdk pegasus_* scripts",
            "board_runtime": "ai-sdk viplite-tina / VIPLite",
        },
        "model": {
            "path": str(model) if model else None,
            "present": model_present,
            "suffix": model.suffix if model else None,
        },
        "ai_sdk": {
            "candidates": [str(path) for path in roots],
            "roots": [str(path) for path in existing_roots],
            "examples": examples,
            "example_models": example_models,
        },
        "runtime": {
            "viplite": viplite_hits,
            "commands": command_hits,
            "vip_version_hint": _command_version(["strings", viplite_hits[0]]) if viplite_hits and shutil.which("strings") else None,
        },
        "device_hints": {
            "devices": devices,
            "proc_device_tree_model": read_text("/proc/device-tree/model"),
            "cpuinfo_hardware": _cpuinfo_hardware(),
            "machine": platform.machine(),
            "system": platform.system(),
        },
    }


def _cpuinfo_hardware() -> str | None:
    text = read_text("/proc/cpuinfo")
    if not text:
        return None
    for line in text.splitlines():
        if line.lower().startswith(("hardware", "model name")):
            return line.split(":", 1)[-1].strip()
    return None
