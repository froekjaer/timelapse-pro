"""
TimeLapse Pro — Hardware Abstraction Layer (HAL)
================================================
Giver et ensartet interface til hardware-specifikke funktioner,
uanset om agenten kører på OrangePi, Raspberry Pi, Jetson eller andet.

Brug:
    from hal import get_adapter, HardwareAdapter
    hw = get_adapter()
    print(hw.model_name())
    print(hw.camera_devices())
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import HardwareAdapter

log = logging.getLogger("hal")

# ── Detektér hardware-model via device-tree ───────────────────────────────────

_DT_MODEL_PATHS = [
    "/proc/device-tree/model",
    "/sys/firmware/devicetree/base/model",
]


def detect_hardware_string() -> str:
    """Læs hardware-model-streng fra device-tree (ARM/AARCH64 standard).
    Returnerer tom streng hvis ikke tilgængeligt (x86/Mac/container)."""
    for path in _DT_MODEL_PATHS:
        try:
            raw = Path(path).read_bytes().rstrip(b"\x00").decode(errors="replace").strip()
            if raw:
                return raw
        except OSError:
            continue

    # Jetson: tjek /proc/device-tree/compatible
    try:
        compat = Path("/proc/device-tree/compatible").read_bytes()
        decoded = compat.rstrip(b"\x00").decode(errors="replace")
        if "nvidia" in decoded.lower() or "tegra" in decoded.lower():
            return "NVIDIA Jetson (compatible)"
    except OSError:
        pass

    return ""


def get_adapter() -> HardwareAdapter:
    """Returner den bedste HardwareAdapter for den kørende hardware."""
    from .orangepi import OrangePiAdapter
    from .rpi import RaspberryPiAdapter
    from .jetson import JetsonAdapter
    from .generic import GenericAdapter

    hw_str = detect_hardware_string().lower()
    log.debug("HAL: device-tree model = %r", hw_str)

    if "raspberry pi 5" in hw_str:
        log.info("HAL: Raspberry Pi 5 detekteret")
        return RaspberryPiAdapter(generation=5)

    if "raspberry pi 4" in hw_str or "raspberry pi" in hw_str:
        log.info("HAL: Raspberry Pi 4 detekteret")
        return RaspberryPiAdapter(generation=4)

    if "nvidia" in hw_str or "jetson" in hw_str or "tegra" in hw_str:
        log.info("HAL: NVIDIA Jetson detekteret")
        return JetsonAdapter()

    if any(kw in hw_str for kw in ("orangepi", "orange pi", "rk3399",
                                    "allwinner", "sun8i", "h3", "h5", "h6",
                                    "rockchip")):
        log.info("HAL: OrangePi detekteret — model=%r", hw_str)
        return OrangePiAdapter(model_string=hw_str)

    log.info("HAL: Ukendt hardware (%r) — bruger GenericAdapter", hw_str)
    return GenericAdapter(model_string=hw_str)


def hal_model_id(hw_str: str | None = None) -> str:
    """Returner en kort model-id streng egnet til target.yaml / UI."""
    if hw_str is None:
        hw_str = detect_hardware_string().lower()
    else:
        hw_str = hw_str.lower()

    if "raspberry pi 5" in hw_str:
        return "rpi5"
    if "raspberry pi 4" in hw_str or "raspberry pi" in hw_str:
        return "rpi4"
    if "nvidia" in hw_str or "jetson" in hw_str or "tegra" in hw_str:
        return "jetson-orin-nano"
    if "rk3399" in hw_str or "orangepi 4" in hw_str or "orange pi 4" in hw_str:
        return "orangepi4pro"
    if "allwinner" in hw_str or "sun8i" in hw_str or "h3" in hw_str or "orangepi pc" in hw_str:
        return "orangepi-pc-plus"
    if "rockchip" in hw_str or "orangepi" in hw_str or "orange pi" in hw_str:
        return "orangepi4pro"
    return "generic"
