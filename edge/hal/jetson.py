"""
TimeLapse Pro — HAL: NVIDIA Jetson-adapter
===========================================
Dækker Jetson Orin Nano (og andre Jetson-varianter via best-effort).
Jetson kører L4T (Linux for Tegra) / JetPack — IKKE et injiceret rootfs-image.
Installation sker via install_timelapse_edge.sh oven på eksisterende JetPack.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import HardwareAdapter


def _read_jetson_release() -> dict[str, str]:
    """Læs /etc/nv_tegra_release eller /etc/nv_jetson_release."""
    for path in ("/etc/nv_tegra_release", "/etc/nv_jetson_release"):
        try:
            text = Path(path).read_text()
            data: dict[str, str] = {}
            for line in text.splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    data[k.strip().lower()] = v.strip().strip('"')
            return data
        except OSError:
            continue
    return {}


class JetsonAdapter(HardwareAdapter):
    def __init__(self) -> None:
        self._release = _read_jetson_release()

    def model_name(self) -> str:
        # Prøv at læse model fra device-tree
        try:
            raw = Path("/proc/device-tree/model").read_bytes().rstrip(b"\x00").decode()
            if raw:
                return raw
        except OSError:
            pass
        return "NVIDIA Jetson Orin Nano"

    def hal_id(self) -> str:
        return "jetson-orin-nano"

    def has_npu(self) -> bool:
        # Alle Jetson-varianter har DLA (Deep Learning Accelerator) + GPU
        return True

    def has_csi(self) -> bool:
        return True  # Jetson Orin Nano har 2x 4-lane MIPI CSI

    def gpu_backend(self) -> str | None:
        return "cuda"

    def jetpack_version(self) -> str | None:
        return self._release.get("r_version") or self._release.get("# r")

    def cuda_version(self) -> str | None:
        try:
            out = subprocess.check_output(
                ["nvcc", "--version"], text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if "release" in line.lower():
                    import re
                    m = re.search(r"release\s+([\d.]+)", line)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return None

    def capabilities(self) -> dict:
        caps = super().capabilities()
        caps["arch"] = "arm64"
        caps["soc"] = "NVIDIA Orin"
        caps["jetpack_version"] = self.jetpack_version()
        caps["cuda_version"] = self.cuda_version()
        caps["dla_cores"] = 2   # Orin Nano har 2 DLA cores
        caps["gpu_cores"] = 1024  # Orin Nano Super: 1024 CUDA cores
        return caps
