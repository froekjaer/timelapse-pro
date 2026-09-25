"""Apple Foundation Models provider for macOS 27.

Production path uses Apple's Python Foundation Models SDK (apple_fm_sdk).
The /usr/bin/fm CLI is deliberately not used by the Headend worker; it remains
useful only for manual LAB diagnostics.

The provider returns the existing TimeLapse ImageAnalysisResult contract so
queue, persistence, vocabulary, alarm and sidecar paths stay authoritative.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .gemini_service import build_prompt_text
from .ollama_service import ImageAnalysisResult, OllamaVisionService

log = logging.getLogger(__name__)

APPLE_MODEL_NAME = "apple-foundation-model-on-device"
QUALITY_FLAGS = [
    "clear_image", "overexposed", "underexposed", "blown_highlights", "glare",
    "sun_in_lens", "lens_flare", "low_contrast", "dirty_lens",
    "condensation_on_lens", "foggy_image", "motion_blur", "incorrect_focus",
    "obstruction_in_front_of_camera", "night_image_ok", "night_image_too_dark",
    "camera_moved", "unusable_image",
]


def _sdk():
    try:
        import apple_fm_sdk as fm
    except ImportError as exc:
        raise RuntimeError(
            "apple_fm_sdk er ikke installeret. Installer Headend requirements på macOS 27."
        ) from exc
    return fm


def _schema_types(fm):
    """Create SDK Generable types lazily so non-macOS imports remain safe."""

    @fm.generable
    class Change:
        detected: bool = fm.guide("Om en reel ændring er observeret")
        summary: str = fm.guide("Kort dansk ændringsbeskrivelse; tom streng hvis ingen")
        new_items: list[str] = fm.guide("Nye synlige elementer", max_items=20)
        removed_items: list[str] = fm.guide("Elementer der ikke længere ses", max_items=20)

    @fm.generable
    class Quality:
        flag: str = fm.guide("Primær billedkvalitet", anyOf=QUALITY_FLAGS)
        ok: bool = fm.guide("Om billedet er anvendeligt til dokumentation")

    @fm.generable
    class GDPRDetection:
        type: str = fm.guide(
            "Kun type af persondata; transskriber aldrig identitet eller nummerplade",
            anyOf=["person_counted", "face", "license_plate"],
        )

    @fm.generable
    class GDPR:
        has_data: bool = fm.guide("Om person, ansigt eller nummerplade er synlig")
        detections: list[GDPRDetection] = fm.guide(
            "Observerede persondata-typer uden identitet", max_items=50
        )

    @fm.generable
    class TimeLapseAnalysis:
        scene: str = fm.guide("Kort dansk beskrivelse af det faktisk synlige")
        tags: list[str] = fm.guide(
            "Synlige kendte tags, lowercase underscore_separated", max_items=40
        )
        new_tags: list[str] = fm.guide(
            "Nye synlige engelske tags, lowercase underscore_separated", max_items=25
        )
        new_tags_da: list[str] = fm.guide(
            "Danske oversættelser parallelt med new_tags", max_items=25
        )
        confidence: float = fm.guide(
            "Samlet model-confidence; ikke verificeret sandhed", range=(0.0, 1.0)
        )
        change: Change
        quality: Quality
        gdpr: GDPR

    return TimeLapseAnalysis


def _run(coro):
    """Run SDK coroutine from the synchronous AI worker.

    The current Headend AI queue is synchronous/threaded. If this provider is
    later called from an active asyncio loop, run the coroutine in a helper
    thread instead of nesting asyncio.run().
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


class AppleFoundationVisionService:
    def __init__(self, timeout_s: int = 120, temperature: float = 0.2):
        self.timeout_s = timeout_s
        self.temperature = temperature

    def availability(self) -> dict:
        try:
            fm = _sdk()
            session = fm.LanguageModelSession()
            response = _run(asyncio.wait_for(
                session.respond("Reply with exactly: OK"),
                timeout=min(self.timeout_s, 30),
            ))
            text = str(getattr(response, "content", response)).strip()
            return {
                "available": bool(text),
                "reason": None if text else "Apple Foundation Model gav tomt svar",
                "runtime": "apple_fm_sdk",
            }
        except Exception as exc:
            return {"available": False, "reason": str(exc)[:500], "runtime": "apple_fm_sdk"}

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
        fm = _sdk()
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        prompt = build_prompt_text(
            vocabulary_by_cat,
            has_reference=bool(reference_image_path),
            prompt_examples=prompt_examples,
            context_block=context_block,
        )
        prompt += (
            "\n\nAPPLE GUIDED OUTPUT: Beskriv kun det, der faktisk kan observeres. "
            "Provider-confidence er kun modellens egen usikkerhed og er ikke ground truth. "
            "Gæt ikke på identitet eller andre personoplysninger."
        )

        attachments = [prompt]
        if reference_image_path:
            ref = Path(reference_image_path)
            if ref.exists():
                attachments.append(fm.ImageAttachment(ref))
        attachments.append(fm.ImageAttachment(image_path))

        result_type = _schema_types(fm)
        session = fm.LanguageModelSession()
        options = fm.GenerationOptions(temperature=self.temperature)

        started = time.monotonic()
        typed = _run(asyncio.wait_for(
            session.respond(attachments, generating=result_type, options=options),
            timeout=self.timeout_s,
        ))
        duration_ms = int((time.monotonic() - started) * 1000)

        # SDK 0.2.1 returns the generated dataclass directly in the physical
        # Headend POC. Keep a content fallback for SDK compatibility.
        generated = getattr(typed, "content", typed)
        parsed = asdict(generated)

        # Adapt the typed observation to the existing canonical result builder.
        # Canonical vocabulary/alarm semantics remain TimeLapse-owned.
        parsed["change"]["summary"] = parsed["change"].get("summary") or None
        parsed["gdpr"]["detections"] = [
            {"type": item.get("type"), "detail": {}, "bbox": []}
            for item in parsed["gdpr"].get("detections", [])
        ]

        normalizer = object.__new__(OllamaVisionService)
        result = normalizer._build_result(
            parsed=parsed,
            approved_tag_set=approved_tag_set,
            has_reference=bool(reference_image_path),
            model=APPLE_MODEL_NAME,
            duration_ms=duration_ms,
            raw_response={
                "provider": "apple_foundation_models",
                "runtime": "apple_fm_sdk",
                "response": parsed,
            },
        )
        return result
