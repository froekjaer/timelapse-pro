"""
TimeLapse Pro — HAL: Raspberry Pi-adapter
==========================================
Dækker RPi 4 (BCM2711, arm64) og RPi 5 (BCM2712, arm64).
"""

from __future__ import annotations

from .base import HardwareAdapter


class RaspberryPiAdapter(HardwareAdapter):
    def __init__(self, generation: int = 4) -> None:
        self._gen = generation

    def model_name(self) -> str:
        return f"Raspberry Pi {self._gen} Model B (BCM{'2712' if self._gen == 5 else '2711'}, arm64)"

    def hal_id(self) -> str:
        return f"rpi{self._gen}"

    def has_csi(self) -> bool:
        # Begge RPi 4 og 5 har CSI-stik (MIPI)
        return True

    def gpu_backend(self) -> str | None:
        # RPi 5 har VideoCore VII; RPi 4 har VideoCore VI
        # Ingen CUDA, men OpenCL via VC4CL er muligt
        return "opencl" if self._gen >= 5 else None

    def capabilities(self) -> dict:
        caps = super().capabilities()
        caps["arch"] = "arm64"
        caps["soc"] = "BCM2712" if self._gen == 5 else "BCM2711"
        caps["generation"] = self._gen
        # RPi 5 har Hailo AI HAT mulighed
        caps["hailo_hat_possible"] = self._gen >= 5
        return caps
