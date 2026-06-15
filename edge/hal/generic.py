"""
TimeLapse Pro — HAL: Generic fallback-adapter
=============================================
Bruges på hardware der ikke matches af de specifikke adaptere.
Giver safe defaults og prøver at læse info fra /proc.
"""

from __future__ import annotations

import platform
from pathlib import Path

from .base import HardwareAdapter


class GenericAdapter(HardwareAdapter):
    def __init__(self, model_string: str = "") -> None:
        self._raw = model_string

    def model_name(self) -> str:
        if self._raw:
            return self._raw[:80]
        return platform.machine() or "Unknown"

    def hal_id(self) -> str:
        return "generic"

    def capabilities(self) -> dict:
        caps = super().capabilities()
        caps["arch"] = platform.machine()
        caps["platform"] = platform.platform()
        return caps
