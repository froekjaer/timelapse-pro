"""
TimeLapse Pro — HAL: OrangePi-adapter
======================================
Dækker alle OrangePi-varianter. Skelner mellem:
  • OrangePi 4 Pro  (Rockchip RK3399, arm64)
  • OrangePi PC Plus (Allwinner H3, armhf / 32-bit)
  • Andre OrangePi (best-effort via model-string)
"""

from __future__ import annotations

from .base import HardwareAdapter


class OrangePiAdapter(HardwareAdapter):
    def __init__(self, model_string: str = "") -> None:
        self._raw = model_string.lower()

    def model_name(self) -> str:
        if "4 pro" in self._raw or "rk3399" in self._raw:
            return "OrangePi 4 Pro (RK3399, arm64)"
        if "a733" in self._raw or "sun60iw2" in self._raw:
            return "OrangePi 4 Pro (Allwinner A733, arm64)"
        if "pc plus" in self._raw or "pcplus" in self._raw:
            return "OrangePi PC Plus (H3, armhf)"
        if "zero3" in self._raw:
            return "OrangePi Zero3 (H618, arm64)"
        if "zero2" in self._raw:
            return "OrangePi Zero2 (H616, arm64)"
        if "allwinner" in self._raw or "sun8i" in self._raw or "h3" in self._raw:
            return "OrangePi (Allwinner H3, armhf)"
        return f"OrangePi ({self._raw[:40]})"

    def hal_id(self) -> str:
        if "4 pro" in self._raw or "rk3399" in self._raw:
            return "orangepi4pro"
        if "pc plus" in self._raw or "pcplus" in self._raw or "allwinner" in self._raw or "sun8i" in self._raw:
            return "orangepi-pc-plus"
        if "zero3" in self._raw:
            return "orangepi-zero3"
        return "orangepi4pro"  # safe fallback for ukendte arm64 OrangePi

    def has_csi(self) -> bool:
        # OrangePi 4 Pro har 2x CSI; PC Plus ingen
        return "rk3399" in self._raw or "4 pro" in self._raw

    def capabilities(self) -> dict:
        caps = super().capabilities()
        if "rk3399" in self._raw or "4 pro" in self._raw:
            caps["arch"] = "arm64"
            caps["soc"] = "RK3399"
        elif "allwinner" in self._raw or "sun8i" in self._raw or "h3" in self._raw or "pc plus" in self._raw:
            caps["arch"] = "armhf"
            caps["soc"] = "Allwinner H3"
        else:
            caps["arch"] = "arm64"
        return caps
