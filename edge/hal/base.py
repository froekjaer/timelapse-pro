"""
TimeLapse Pro — HAL base class
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class HardwareAdapter(ABC):
    """
    Abstrakt base-klasse for hardware-adaptere.

    Hver metode returnerer sikre defaults hvis hardware-specifik info
    ikke er tilgængelig, så agenten altid kan starte.
    """

    @abstractmethod
    def model_name(self) -> str:
        """Menneskevenligt hardware-navn, fx 'Raspberry Pi 4 Model B'."""

    @abstractmethod
    def hal_id(self) -> str:
        """Kort ID egnet til target.yaml, fx 'rpi4', 'orangepi4pro'."""

    def camera_devices(self) -> list[str]:
        """
        Liste af kamera-device-paths tilgængelige via gphoto2.
        Typisk USB: ['usb:'], CSI: ['/dev/video0'] etc.
        Default: tom liste (agenten bruger auto-discover).
        """
        return []

    def has_npu(self) -> bool:
        """Har boardet en dedikeret NPU/GPU til inference?"""
        return False

    def has_csi(self) -> bool:
        """Understøtter boardet CSI-kamera (udover USB)?"""
        return False

    def gpu_backend(self) -> str | None:
        """GPU/inference-backend, fx 'cuda', 'opencl', None."""
        return None

    def capabilities(self) -> dict:
        """
        Returner dict med hardware-capabilities til inventory-rapportering.
        Alle felter er valgfrie; manglende felter tolkes som False/None.
        """
        return {
            "hal_id":       self.hal_id(),
            "model_name":   self.model_name(),
            "has_npu":      self.has_npu(),
            "has_csi":      self.has_csi(),
            "gpu_backend":  self.gpu_backend(),
            "camera_devices": self.camera_devices(),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(hal_id={self.hal_id()!r})"
