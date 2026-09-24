"""Apple Foundation Models vision provider for macOS 27.

Uses Apple's preinstalled fm CLI instead of introducing a second Python
runtime dependency. The CLI is part of macOS 27 and talks to the on-device
SystemLanguageModel by default. No API key or cloud credential is required.

This adapter implements the same analyse contract as the existing
Ollama/Gemini providers so queue, persistence, vocabulary and alarm paths
remain authoritative and shared.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .gemini_service import build_prompt_text
from .ollama_service import ImageAnalysisResult, OllamaVisionService

log = logging.getLogger(__name__)

APPLE_MODEL_NAME = "apple-foundation-model-on-device"


class AppleFoundationVisionService:
    def __init__(self, fm_binary: str = "fm", timeout_s: int = 120):
        self.fm_binary = fm_binary
        self.timeout_s = timeout_s

    def availability(self) -> dict:
        path = shutil.which(self.fm_binary)
        if not path:
            return {
                "available": False,
                "reason": "fm CLI ikke fundet; Apple Foundation Models kræver macOS 27",
                "binary": None,
            }
        try:
            proc = subprocess.run(
                [path, "respond", "Reply with exactly: OK"],
                capture_output=True,
                text=True,
                timeout=min(self.timeout_s, 30),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"available": False, "reason": str(exc), "binary": path}
        if proc.returncode != 0:
            reason = (proc.stderr or proc.stdout or "fm respond fejlede").strip()
            return {"available": False, "reason": reason[:500], "binary": path}
        return {"available": True, "reason": None, "binary": path}

    def health_check(self) -> bool:
        return bool(self.availability()["available"])

    def analyse(
        self,
        image_path: Path | str,
        vocabulary_by_cat: dict[str, list[str]],
        approved_tag_set: set[str],
        reference_image_path: Optional[Path | str] = None,
        prompt_examples: Optional[list[str]] = None,
        context_block: str = "",
    ) -> ImageAnalysisResult:
        fm_path = shutil.which(self.fm_binary)
        if not fm_path:
            raise RuntimeError("Apple Foundation Models 'fm' CLI blev ikke fundet")

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        prompt = build_prompt_text(
            vocabulary_by_cat,
            has_reference=bool(reference_image_path),
            prompt_examples=prompt_examples,
            context_block=context_block,
        )
        cmd = [fm_path, "respond", prompt]
        if reference_image_path:
            ref = Path(reference_image_path)
            if ref.exists():
                cmd += ["--image", str(ref)]
        cmd += ["--image", str(image_path)]

        started = time.monotonic()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout_s,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc.returncode != 0:
            error = (proc.stderr or proc.stdout or "ukendt fm-fejl").strip()
            raise RuntimeError(f"Apple Foundation Models fejlede: {error[:1000]}")

        parsed = self._parse_json(proc.stdout)
        if not parsed:
            raise ValueError("Apple Foundation Models returnerede ikke gyldig JSON")

        normalizer = object.__new__(OllamaVisionService)
        return normalizer._build_result(
            parsed=parsed,
            approved_tag_set=approved_tag_set,
            has_reference=bool(reference_image_path),
            model=APPLE_MODEL_NAME,
            duration_ms=duration_ms,
            raw_response={"provider": "apple_foundation_models", "response": parsed},
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = (raw or "").strip()
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            pass
        match = re.search(r"\x60\x60\x60(?:json)?\\s*(\\{.*?\\})\\s*\x60\x60\x60", raw, re.DOTALL)
        if not match:
            match = re.search(r"(\\{.*\\})", raw, re.DOTALL)
        if not match:
            return {}
        candidate = re.sub(r",\\s*([}\\]])", r"\\1", match.group(1))
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
