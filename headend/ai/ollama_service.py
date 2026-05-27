"""
TimeLapse Pro — Ollama Vision Service
=======================================
Håndterer al kommunikation med den lokale Ollama vision-model.

Funktioner:
  - Dansk billed-analyse med selvudvidende tags (~300 startpunkter)
  - Change detection via to-billeders sammenligning
  - GDPR-safe detektion (ansigt/nummerplade → flag, ikke identifikation)
  - Kamera-kvalitetsvurdering
  - Robust JSON-parsing med fallback

Modellen modtager ALDRIG instrukser om at identificere personer.
Den returnerer kun: antal, tilstedeværelse, bounding box.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ── Konfiguration ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = "http://localhost:11434"
VISION_MODEL      = "qwen2.5vl:7b"
TEXT_MODEL        = "llama3.2:latest"
TIMEOUT_VISION    = 600   # sekunder — vision er tung
TIMEOUT_TEXT      = 60
MAX_IMAGE_BYTES   = 5 * 1024 * 1024   # 5 MB — resize hvis større


# =============================================================================
# DATAKLASSER — intern repræsentation af analyse-resultat
# =============================================================================

@dataclass
class GDPRFlag:
    detection_type: str                     # face / license_plate / person_counted / vehicle_detail
    detail:         dict                    # {"plate_visible": True, "readable": False} osv.
    bounding_box:   Optional[dict] = None   # {x, y, w, h} normaliseret 0–1


@dataclass
class ImageAnalysisResult:
    # Scene
    scene_dk:        str
    # Tags
    approved_tags:   list[str]              # kendte, godkendte tags fra vokabular
    new_tags:        list[str]              # model-opfundne, til review
    # Change detection
    change_detected: bool
    change_summary:  Optional[str]
    change_tags:     list[str]
    # Kvalitet
    quality_flag:    str
    quality_ok:      bool
    # GDPR
    has_gdpr_data:   bool
    gdpr_detections: list[GDPRFlag]
    # Meta
    model:           str
    duration_ms:     int
    raw_response:    dict


# =============================================================================
# PROMPTS
# =============================================================================

def _build_vision_prompt(vocabulary_by_category: dict[str, list[str]]) -> str:
    """Byg enkelt-billed prompt med hele vokabularet."""

    # Formater vokabular som kompakt kategoriseret liste
    vocab_lines = []
    for cat, tags in vocabulary_by_category.items():
        vocab_lines.append(f"  [{cat}]: {', '.join(tags)}")
    vocab_text = "\n".join(vocab_lines)

    return f"""Du er et præcist AI-system til dokumentation af byggepladser.
Analyser dette billede og returner KUN et JSON-objekt — ingen forklaring, ingen kommentarer.

## EKSISTERENDE TAG-VOKABULAR (brug disse præfereret)
{vocab_text}

## REGLER FOR TAGS
- Brug eksisterende tags fra listen når de passer
- Tilføj NYE tags i "new_tags" hvis du ser noget der ikke er dækket
- Alle tags: dansk, lowercase, underscore (ikke mellemrum)
- Vær generøs — 15 til 35 tags pr. billede
- Tag kun det du faktisk kan se

## GDPR-REGLER (VIGTIGT)
- Identificer ALDRIG navne, ansigtstræk eller nummerplader som tekst
- Rapportér KUN: er der et ansigt (ja/nej), er der en nummerplade (ja/nej)
- For køretøjer: mærke/model KUN hvis tydeligt synligt som model-type, IKKE som identifikation

## RETURNER PRÆCIS DETTE JSON-FORMAT:
{{
  "scene": "Kort dansk beskrivelse af hvad der foregår på billedet (1-2 sætninger)",
  "tags": ["tag1", "tag2", "..."],
  "new_tags": ["evt_nyt_tag"],
  "quality": {{
    "flag": "klart_billede",
    "ok": true
  }},
  "gdpr": {{
    "has_data": false,
    "detections": []
  }}
}}

Eksempel på gdpr.detections hvis relevant:
  {{"type": "face", "detail": {{"count": 2, "wearing_helmet": true}}, "bbox": {{"x": 0.3, "y": 0.1, "w": 0.1, "h": 0.15}}}}
  {{"type": "license_plate", "detail": {{"visible": true, "readable": false}}, "bbox": {{"x": 0.6, "y": 0.7, "w": 0.12, "h": 0.04}}}}
  {{"type": "person_counted", "detail": {{"count": 5}}, "bbox": null}}

Returner KUN JSON. Ingen tekst før eller efter."""


def _build_change_prompt(vocabulary_by_category: dict[str, list[str]]) -> str:
    """Byg to-billeders change detection prompt."""

    vocab_lines = []
    for cat, tags in vocabulary_by_category.items():
        vocab_lines.append(f"  [{cat}]: {', '.join(tags)}")
    vocab_text = "\n".join(vocab_lines)

    return f"""Du er et AI-system til byggeplads-dokumentation.
Du modtager TO billeder: BILLEDE 1 = referencebillede (forrige dag), BILLEDE 2 = aktuelt billede.
Sammenlign dem og returner KUN JSON.

## TAG-VOKABULAR
{vocab_text}

## GDPR-REGLER
- Identificer ALDRIG navne eller nummerplader som tekst
- Rapportér KUN tilstedeværelse (ja/nej) og antal

## RETURNER PRÆCIS DETTE JSON-FORMAT:
{{
  "scene": "Dansk beskrivelse af det aktuelle billede (1-2 sætninger)",
  "tags": ["tag1", "tag2"],
  "new_tags": [],
  "change": {{
    "detected": true,
    "summary": "Dansk beskrivelse af hvad der er nyt siden referencebilledet",
    "magnitude": "ingen / lille / moderat / stor",
    "new_items": ["ny_container", "ny_lastbil"],
    "removed_items": ["stillads_fjernet"]
  }},
  "quality": {{
    "flag": "klart_billede",
    "ok": true
  }},
  "gdpr": {{
    "has_data": false,
    "detections": []
  }}
}}

Returner KUN JSON."""


# =============================================================================
# OLLAMA VISION SERVICE
# =============================================================================

class OllamaVisionService:

    def __init__(
        self,
        base_url:     str = OLLAMA_BASE_URL,
        vision_model: str = VISION_MODEL,
    ):
        self.base_url     = base_url.rstrip("/")
        self.vision_model = vision_model
        self._client      = httpx.Client(timeout=TIMEOUT_VISION)

    # ── Offentlig API ─────────────────────────────────────────────────────────

    def analyse(
        self,
        image_path:          Path | str,
        vocabulary_by_cat:   dict[str, list[str]],
        approved_tag_set:    set[str],
        reference_image_path: Optional[Path | str] = None,
    ) -> ImageAnalysisResult:
        """
        Analysér et billede (med optional reference til change detection).

        vocabulary_by_cat:  {kategori: [tags]} — fra TagVocabulary.get_approved_by_category()
        approved_tag_set:   set af godkendte tags — til opdeling approved/new
        reference_image_path: referencebillede fra ~24 timer før
        """
        start = time.monotonic()

        # Kodning
        images = [self._encode_image(image_path)]
        if reference_image_path:
            # Reference sendes FØRST (Billede 1), aktuelt senest (Billede 2)
            images = [self._encode_image(reference_image_path), images[0]]
            prompt = _build_change_prompt(vocabulary_by_cat)
        else:
            prompt = _build_vision_prompt(vocabulary_by_cat)

        # Kald model
        raw = self._call_ollama(
            model=self.vision_model,
            prompt=prompt,
            images=images,
        )

        duration_ms = int((time.monotonic() - start) * 1000)

        # Parse
        parsed = self._parse_response(raw)
        return self._build_result(
            parsed=parsed,
            approved_tag_set=approved_tag_set,
            has_reference=reference_image_path is not None,
            model=self.vision_model,
            duration_ms=duration_ms,
            raw_response=raw,
        )

    def health_check(self) -> bool:
        """Tjek om Ollama kører og modellen er tilgængelig."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m["name"] for m in resp.json().get("models", [])]
            model_family = self.vision_model.split(":")[0]
            available = any(m == self.vision_model or m.split(":")[0] == model_family for m in models)
            if not available:
                log.warning("Vision model %s ikke fundet. Tilgængelige: %s",
                            self.vision_model, models)
            return available
        except Exception as e:
            log.error("Ollama health check fejlede: %s", e)
            return False

    def list_models(self) -> list[str]:
        """Returnér tilgængelige Ollama-modelnavne."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            log.error("Ollama model-liste fejlede: %s", e)
            return []

    # ── Intern: HTTP ──────────────────────────────────────────────────────────

    def _call_ollama(self, model: str, prompt: str, images: list[str]) -> dict:
        """Kald Ollama API og returnér parsed JSON fra model-svaret."""
        payload = {
            "model":  model,
            "prompt": prompt,
            "images": images,
            "stream": False,
            "options": {
                "temperature": 0.1,      # lav temperatur → konsistente JSON-svar
                "num_predict": 1500,
            },
        }
        try:
            resp = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=TIMEOUT_VISION,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            log.error("Ollama timeout efter %ds for model %s", TIMEOUT_VISION, model)
            raise
        except httpx.HTTPStatusError as e:
            log.error("Ollama HTTP-fejl %d: %s", e.response.status_code, e.response.text[:200])
            raise

    # ── Intern: Billede-kodning ───────────────────────────────────────────────

    def _encode_image(self, path: Path | str) -> str:
        """Læs billede, resize hvis nødvendigt, returnér base64."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Billede ikke fundet: {p}")

        data = p.read_bytes()

        # Resize hvis over grænse
        if len(data) > MAX_IMAGE_BYTES:
            data = self._resize_image(data)

        return base64.b64encode(data).decode("utf-8")

    def _resize_image(self, data: bytes) -> bytes:
        """Reducer billedstørrelse til under MAX_IMAGE_BYTES."""
        try:
            import cv2
            import numpy as np
            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            scale = (MAX_IMAGE_BYTES / len(data)) ** 0.5 * 0.9
            h, w = img.shape[:2]
            img_small = cv2.resize(img, (int(w * scale), int(h * scale)))
            _, buf = cv2.imencode(".jpg", img_small, [cv2.IMWRITE_JPEG_QUALITY, 85])
            log.debug("Billede resized: %d KB → %d KB",
                      len(data) // 1024, len(buf) // 1024)
            return buf.tobytes()
        except Exception as e:
            log.warning("Resize fejlede, bruger original: %s", e)
            return data

    # ── Intern: JSON-parsing ──────────────────────────────────────────────────

    def _parse_response(self, raw: dict) -> dict:
        """
        Udtræk og parse JSON fra model-svar.
        Robusthed: håndterer markdown-fences, trailing commas, partial output.
        """
        text = raw.get("response", "")

        # Forsøg 1: direkte JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Forsøg 1b: modellen returnerede JSON-indhold uden ydre klammer.
        candidate = "{" + text.strip().strip(",") + "}"
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Forsøg 2: udtræk JSON-blok fra markdown
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Forsøg 3: find første { ... } blok
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            candidate = match.group(1)
            # Fjern trailing commas (common model-fejl)
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        salvaged = self._salvage_response(text)
        if salvaged:
            return salvaged

        log.warning("Kunne ikke parse model-svar som JSON. Rå svar: %s", text[:300])
        return {}

    def _salvage_response(self, text: str) -> dict:
        """Best-effort parsing når modellen returnerer næsten-JSON."""
        result: dict = {}

        scene = re.search(r'"scene"\s*:\s*"([^"]*)"', text, re.DOTALL)
        if scene:
            result["scene"] = scene.group(1).strip()

        for key in ("tags", "new_tags"):
            match = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            if not match:
                match = re.search(rf'"{key}"\s*:\s*\[(.*?)(?:"(?:new_tags|quality|gdpr)"\s*:|$)', text, re.DOTALL)
            if match:
                result[key] = re.findall(r'"([^"]+)"', match.group(1))

        quality_flag = re.search(r'"flag"\s*:\s*"([^"]*)"', text, re.DOTALL)
        quality_ok = re.search(r'"ok"\s*:\s*(true|false)', text, re.IGNORECASE)
        if quality_flag or quality_ok:
            result["quality"] = {
                "flag": quality_flag.group(1).strip() if quality_flag else "ukendt",
                "ok": quality_ok.group(1).lower() == "true" if quality_ok else True,
            }

        has_gdpr = re.search(r'"has_data"\s*:\s*(true|false)', text, re.IGNORECASE)
        if has_gdpr:
            result["gdpr"] = {
                "has_data": has_gdpr.group(1).lower() == "true",
                "detections": [],
            }

        return result

    # ── Intern: Byg resultat ──────────────────────────────────────────────────

    def _build_result(
        self,
        parsed:          dict,
        approved_tag_set: set[str],
        has_reference:   bool,
        model:           str,
        duration_ms:     int,
        raw_response:    dict,
    ) -> ImageAnalysisResult:

        # Tags — opdel i kendte (approved) og nye
        all_tags  = [str(t).lower().strip().replace(" ", "_").replace("-", "_") for t in parsed.get("tags", [])]
        raw_new   = [str(t).lower().strip().replace(" ", "_").replace("-", "_") for t in parsed.get("new_tags", [])]
        all_tags  = list(dict.fromkeys(t for t in all_tags if t))[:60]
        raw_new   = list(dict.fromkeys(t for t in raw_new if t))[:60]

        approved_tags = [t for t in all_tags if t in approved_tag_set]
        new_tags      = [t for t in all_tags if t not in approved_tag_set] + raw_new
        new_tags      = list(dict.fromkeys(new_tags))   # deduplicate

        # Change detection
        change_block   = parsed.get("change", {}) if has_reference else {}
        change_detected = bool(change_block.get("detected", False))
        change_summary  = change_block.get("summary") if change_detected else None
        change_tags     = (
            change_block.get("new_items", []) +
            ["fjernet_" + t for t in change_block.get("removed_items", [])]
        ) if change_detected else []

        # Kvalitet
        quality_block = parsed.get("quality", {})
        quality_flag  = str(quality_block.get("flag", "ukendt"))
        quality_ok    = bool(quality_block.get("ok", True))

        # GDPR
        gdpr_block  = parsed.get("gdpr", {})
        has_gdpr    = bool(gdpr_block.get("has_data", False))
        gdpr_flags  = []
        for det in gdpr_block.get("detections", []):
            dtype = str(det.get("type", ""))
            if dtype in ("face", "license_plate", "person_counted", "vehicle_detail"):
                gdpr_flags.append(GDPRFlag(
                    detection_type=dtype,
                    detail=det.get("detail", {}),
                    bounding_box=det.get("bbox"),
                ))
                has_gdpr = True

        return ImageAnalysisResult(
            scene_dk        = str(parsed.get("scene", "Ingen beskrivelse")),
            approved_tags   = approved_tags,
            new_tags        = new_tags,
            change_detected = change_detected,
            change_summary  = change_summary,
            change_tags     = change_tags,
            quality_flag    = quality_flag,
            quality_ok      = quality_ok,
            has_gdpr_data   = has_gdpr,
            gdpr_detections = gdpr_flags,
            model           = model,
            duration_ms     = duration_ms,
            raw_response    = raw_response,
        )
