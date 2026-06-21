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
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ── Konfiguration ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = "http://localhost:11434"
VISION_MODEL      = os.getenv("TIMELAPSE_VISION_MODEL", "qwen2.5vl:7b")
FALLBACK_MODELS   = [
    m.strip()
    for m in os.getenv("TIMELAPSE_VISION_FALLBACK_MODELS", "llava-phi3:latest").split(",")
    if m.strip()
]
TEXT_MODEL        = "llama3.2:latest"
TIMEOUT_VISION    = int(os.getenv("TIMELAPSE_VISION_TIMEOUT", "120"))
TIMEOUT_TEXT      = 60
MAX_IMAGE_BYTES   = int(os.getenv("TIMELAPSE_VISION_MAX_IMAGE_BYTES", str(900_000)))
MAX_IMAGE_EDGE    = int(os.getenv("TIMELAPSE_VISION_MAX_IMAGE_EDGE", "768"))
MAX_PROMPT_TAGS   = int(os.getenv("TIMELAPSE_VISION_MAX_PROMPT_TAGS", "45"))
MAX_PROMPT_TAGS_PER_CATEGORY = int(os.getenv("TIMELAPSE_VISION_MAX_PROMPT_TAGS_PER_CATEGORY", "6"))
VISION_NUM_CTX     = int(os.getenv("TIMELAPSE_VISION_NUM_CTX", "4096"))
VISION_NUM_PREDICT = int(os.getenv("TIMELAPSE_VISION_NUM_PREDICT", "320"))

CONSTRUCTION_WORK_TAGS = {
    "byggefremskridt", "tom_grund", "udgravning", "jordarbejde", "pilotering",
    "fundamentstøbning", "kælder_støbt", "betondæk_støbt", "råhus_opførelse",
    "råhus_færdigt", "murerarbejde", "tagkonstruktion", "tagdækning", "tagpap",
    "facade_beklædning", "puds", "isolering_ydervæg", "vinduesmontage",
    "dørmontage", "indvendig_aptering", "el_installation", "vvs_installation",
    "gulvlægning", "maling_indvendig", "maling_udvendig", "flisearbejde",
    "badeværelse_montage", "køkken_montage", "færdigbygget", "renovering",
    "nedrivning", "tilbygning", "ombygning", "stillads", "arbejdslift",
    "tårnkran", "mobilkran", "gravemaskine", "betonbil", "betonpumpe",
    "construction_progress", "excavation", "earthworks", "pile_driving",
    "foundation_pouring", "concrete_deck_cast", "structural_work",
    "masonry_work", "roof_structure", "roofing", "facade_cladding",
    "external_wall_insulation", "window_installation", "door_installation",
    "interior_fit_out", "electrical_installation", "plumbing_installation",
    "flooring", "interior_painting", "exterior_painting", "tiling",
    "bathroom_installation", "kitchen_installation", "demolition", "renovation",
    "tower_crane", "mobile_crane", "excavator", "concrete_truck", "concrete_pump",
}

NEUTRAL_FALLBACK_TAGS = {
    "overskyet", "grå_himmel", "regn", "let_regn", "kraftig_regn", "skydække",
    "dagslys", "mørk_dag", "diffust_lys", "træ", "træer", "busk", "hæk",
    "natur", "skov", "vej", "tag", "skråt_tag", "nabobygning",
    "klart_billede", "undereksponeret", "korrekt_eksponering",
    "solskin", "delvis_skyet", "blå_himmel", "hvide_skyer", "klar_himmel",
    "lavt_skydække", "høj_sol", "lav_sol", "solrig_dag", "klart_sollys",
    "modlys", "direkte_sollys", "skygge", "lang_skygge", "kort_skygge",
    "gyldent_lys", "sol_i_linsen", "genskin", "linse_refleks",
    "irriterende_genskin", "god_timelapse_belysning", "overeksponeret",
    "udbrændte_højlys", "flare", "lav_kontrast",
    "overcast", "grey_sky", "rain", "light_rain", "heavy_rain", "cloud_cover",
    "daylight", "dark_day", "diffuse_light", "tree", "trees", "bush", "hedge",
    "nature", "forest", "road", "roof", "sloped_roof", "neighboring_building",
    "clear_image", "underexposed", "correct_exposure", "sunshine", "partly_cloudy",
    "blue_sky", "white_clouds", "clear_sky", "low_cloud_cover", "high_sun",
    "low_sun", "sunny_day", "clear_sunlight", "backlight", "direct_sunlight",
    "shadow", "long_shadow", "short_shadow", "golden_light", "sun_in_lens",
    "glare", "lens_reflection", "annoying_glare", "good_timelapse_lighting",
    "overexposed", "blown_highlights", "lens_flare", "low_contrast", "city_view",
    "buildings",
}

INTERIOR_WORK_TAGS = {
    "badeværelse_montage", "køkken_montage", "gulvlægning", "maling_indvendig",
    "flisearbejde", "indvendig_aptering", "el_installation", "vvs_installation",
    "bathroom_installation", "kitchen_installation", "flooring", "interior_painting",
    "tiling", "interior_fit_out", "electrical_installation", "plumbing_installation",
}

VOCABULARY_CATEGORY_NAMES = {
    "strukturer", "bygningstyper", "byggefremskridt", "tunge_maskiner",
    "udstyr_og_redskaber", "køretøjer", "materialer_på_plads",
    "arbejdere_og_aktivitet", "vejr", "lys_og_tid", "sikkerhed_og_afspærring",
    "pladstilstand", "omgivelser", "gdpr_safe", "anomalier_og_hændelser",
    "dyr", "kamera_kvalitet", "change_detection", "vejr/omgivelser",
    "weather", "light_and_time", "camera_quality",
}

OUTDOOR_SCENE_WORDS = {
    "landskab", "byudsigt", "træ", "træer", "himmel", "skyet", "skyer",
    "tage", "tag", "udendørs", "natur", "horisont",
}

TAG_SYNONYMS = {
    "tag": "roof",
    "tage": "roof",
    "skråt_tag": "sloped_roof",
    "skyet": "overcast",
    "overskyet": "overcast",
    "by": "city_view",
    "byudsigt": "city_view",
    "bygninger": "buildings",
    "træ": "tree",
    "træer": "trees",
    "klart_billede": "clear_image",
    "dagslys": "daylight",
    "solskin": "sunshine",
    "solrig_dag": "sunny_day",
    "klart_sollys": "clear_sunlight",
    "direkte_sollys": "direct_sunlight",
    "sol_i_linsen": "sun_in_lens",
    "modlys": "backlight",
    "genskin": "glare",
    "irriterende_genskin": "annoying_glare",
    "linse_refleks": "lens_reflection",
    "overeksponeret": "overexposed",
    "udbrændte_højlys": "blown_highlights",
    "lav_kontrast": "low_contrast",
    "vejr_omgivelser": "",
    "klart_solskin": "clear_sunlight",
    "klar_sol": "clear_sunlight",
    "direkte_sol": "direct_sunlight",
    "sol_refleks": "lens_reflection",
    "sun_flare": "lens_flare",
    "direct_sun": "direct_sunlight",
}


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
    new_tags:        list[str]              # model-opfundne, til review (ENGELSK)
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
    # AI-foreslået dansk oversættelse pr. new_tag — {"loading_ramp": "lastrampe"}
    # (default — sidst i listen så den ikke kræver positional opdatering alle steder)
    new_tags_da:     dict[str, str] = field(default_factory=dict)


# =============================================================================
# PROMPTS
# =============================================================================

def _build_vision_prompt(vocabulary_by_category: dict[str, list[str]]) -> str:
    """Byg kompakt enkelt-billed prompt med begrænset vokabular."""

    vocab_lines = []
    used = 0
    for cat, tags in vocabulary_by_category.items():
        if used >= MAX_PROMPT_TAGS:
            break
        remaining = max(0, MAX_PROMPT_TAGS - used)
        selected = tags[:min(MAX_PROMPT_TAGS_PER_CATEGORY, remaining)]
        if selected:
            vocab_lines.append(f"{cat}: {', '.join(selected)}")
            used += len(selected)
    vocab_text = "\n".join(vocab_lines)

    return f"""Analyze this timelapse image. Respond only with valid JSON. No markdown, no explanation.

IMPORTANT:
- Do NOT assume the image shows a construction site.
- Only use construction tags if construction activity, materials, machines, scaffolding or new construction is clearly visible.
- If the image mainly shows landscape, weather, trees, roofs or a city view, use only neutral tags like weather/surroundings/light/camera_quality.
- Describe weather and lighting when visible: daylight, sunshine, overcast, blue_sky, diffuse_light, clear_sunlight, backlight, direct_sunlight, sun_in_lens, glare, lens_flare, overexposed.
- Use good_timelapse_lighting when the image has usable daylight without clear backlight, sun_in_lens, distracting_glare or overexposure.
- Prefer fewer correct tags over more incorrect tags.
- Return 0-8 tags. Never a long list.
- Indoor tags like bathroom_installation, kitchen_installation, flooring and interior_painting may only be used if indoor work is actually visible.

Prefer these ENGLISH tags, but only when they visually fit:
{vocab_text}

Rules:
- Tags MUST be English, lowercase, underscore-separated.
- New words you invent also go in "new_tags" (ENGLISH). For each one, suggest a short
  natural DANISH translation at the SAME position in "new_tags_da" (parallel array,
  same length/order as "new_tags"). Example:
  "new_tags": ["loading_ramp"], "new_tags_da": ["lastrampe"]
- "scene" stays in Danish — it is free text shown to Danish users, not a tag.
- Describe only what can be seen.
- Never identify people or license plates.

JSON format:
{{
  "scene": "Billedet viser ...",
  "tags": ["tag1", "tag2"],
  "new_tags": [],
  "new_tags_da": [],
  "quality": {{"flag": "clear_image", "ok": true}},
  "gdpr": {{"has_data": false, "detections": []}}
}}
Return only the JSON object."""


def _build_change_prompt(vocabulary_by_category: dict[str, list[str]]) -> str:
    """Byg to-billeders change detection prompt."""

    vocab_lines = []
    for cat, tags in vocabulary_by_category.items():
        vocab_lines.append(f"  [{cat}]: {', '.join(tags)}")
    vocab_text = "\n".join(vocab_lines)

    return f"""You are an AI system for construction site documentation.
You receive TWO images: IMAGE 1 = reference image (previous day), IMAGE 2 = current image.
Compare them and return ONLY JSON.

## TAG VOCABULARY (canonical — ENGLISH)
{vocab_text}

## GDPR RULES
- NEVER identify names or license plates as text
- Report ONLY presence (yes/no) and count

## RULES
- Tags MUST be English. "new_tags" (also English) for words you invent — and for
  EACH one, suggest a short natural DANISH translation at the same position in
  "new_tags_da" (parallel array, same length/order as "new_tags").
- "scene" and "change.summary" stay in Danish — free text for Danish users, not tags.

## RETURN EXACTLY THIS JSON FORMAT:
{{
  "scene": "Dansk beskrivelse af det aktuelle billede (1-2 sætninger)",
  "tags": ["tag1", "tag2"],
  "new_tags": [],
  "new_tags_da": [],
  "change": {{
    "detected": true,
    "summary": "Dansk beskrivelse af hvad der er nyt siden referencebilledet",
    "magnitude": "ingen / lille / moderat / stor",
    "new_items": ["new_container", "new_truck"],
    "removed_items": ["scaffolding_removed"]
  }},
  "quality": {{
    "flag": "clear_image",
    "ok": true
  }},
  "gdpr": {{
    "has_data": false,
    "detections": []
  }}
}}

Return ONLY JSON."""


# =============================================================================
# OLLAMA VISION SERVICE
# =============================================================================

class OllamaVisionService:

    def __init__(
        self,
        base_url:     str = OLLAMA_BASE_URL,
        vision_model: str = VISION_MODEL,
        fallback_models: Optional[list[str]] = None,
    ):
        self.base_url        = base_url.rstrip("/")
        self.vision_model    = vision_model
        self.fallback_models = fallback_models if fallback_models is not None else FALLBACK_MODELS
        self._client         = httpx.Client(timeout=TIMEOUT_VISION)

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

        raw, model_used = self._call_ollama_with_fallback(prompt=prompt, images=images)

        duration_ms = int((time.monotonic() - start) * 1000)

        # Parse
        parsed = self._parse_response(raw)
        return self._build_result(
            parsed=parsed,
            approved_tag_set=approved_tag_set,
            has_reference=reference_image_path is not None,
            model=model_used,
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
                "top_p": 0.8,
                "repeat_penalty": 1.18,
                "num_ctx": VISION_NUM_CTX,
                "num_predict": VISION_NUM_PREDICT,
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

    def _call_ollama_with_fallback(self, prompt: str, images: list[str]) -> tuple[dict, str]:
        """Prøv primær model og derefter fallback-modeller ved runtime-fejl."""
        candidates = [self.vision_model]
        candidates.extend(m for m in self.fallback_models if m and m not in candidates)

        last_error: Exception | None = None
        for idx, model in enumerate(candidates):
            try:
                if idx:
                    log.warning("Ollama: prøver fallback vision-model %s efter fejl i %s", model, candidates[idx - 1])
                raw = self._sanitize_raw_response(self._call_ollama(model=model, prompt=prompt, images=images))
                if not str(raw.get("response", "")).strip():
                    raise ValueError(f"Ollama model {model} returnerede tomt response-felt")
                return raw, model
            except (ValueError, httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if idx == len(candidates) - 1:
                    break
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Ingen Ollama vision-modeller konfigureret")

    def _sanitize_raw_response(self, raw: dict) -> dict:
        """Behold driftsrelevant Ollama-meta uden store token-context felter."""
        keep = {
            "model",
            "created_at",
            "response",
            "done",
            "done_reason",
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        }
        cleaned = {k: v for k, v in raw.items() if k in keep}
        if "thinking" in raw:
            cleaned["thinking_preview"] = str(raw.get("thinking", ""))[:500]
        return cleaned

    # ── Intern: Billede-kodning ───────────────────────────────────────────────

    def _encode_image(self, path: Path | str) -> str:
        """Læs billede, resize hvis nødvendigt, returnér base64."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Billede ikke fundet: {p}")

        data = p.read_bytes()

        data = self._resize_image(data)

        return base64.b64encode(data).decode("utf-8")

    def _normalize_tag(self, value: object) -> str:
        tag = str(value).lower().strip().replace(" ", "_").replace("-", "_").replace("/", "_")
        tag = re.sub(r"[^a-z0-9_æøå]", "", tag)
        tag = TAG_SYNONYMS.get(tag, tag)
        return tag if tag and tag not in VOCABULARY_CATEGORY_NAMES else ""

    def _normalize_scene_text(self, value: object) -> str:
        text = str(value or "Ingen beskrivelse").strip()
        text = re.sub(r"\bskyet vær\b", "skyet vejr", text, flags=re.IGNORECASE)
        return text or "Ingen beskrivelse"

    def _resize_image(self, data: bytes) -> bytes:
        """Reducer billedstørrelse og pixel-dimensioner til vision-modeller."""
        try:
            import cv2
            import numpy as np
            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return data
            h, w = img.shape[:2]
            scale = min(1.0, MAX_IMAGE_EDGE / max(h, w))
            if len(data) > MAX_IMAGE_BYTES:
                scale = min(scale, (MAX_IMAGE_BYTES / len(data)) ** 0.5 * 0.9)
            if scale < 1.0:
                img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))
            quality = 82
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
            while ok and len(buf) > MAX_IMAGE_BYTES and quality > 55:
                quality -= 7
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                return data
            log.debug("Billede klargjort til AI: %d KB/%dx%d -> %d KB/%dx%d",
                      len(data) // 1024, w, h, len(buf) // 1024, img.shape[1], img.shape[0])
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

        for key in ("tags", "new_tags", "new_tags_da"):
            match = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            if not match:
                match = re.search(rf'"{key}"\s*:\s*\[(.*?)(?:"(?:new_tags|new_tags_da|quality|gdpr)"\s*:|$)', text, re.DOTALL)
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
        all_tags  = [self._normalize_tag(t) for t in parsed.get("tags", [])]
        raw_new_unfiltered = [self._normalize_tag(t) for t in parsed.get("new_tags", [])]
        raw_new_da_unfiltered = [str(t).strip() for t in parsed.get("new_tags_da", [])]
        # Byg da-map FØR dedup/filtrering nedenfor, da zip() kræver justeret indeks —
        # dict-opslag på tag-navn er robust selvom new_tags filtreres senere.
        new_tags_da_map = dict(zip(raw_new_unfiltered, raw_new_da_unfiltered))
        all_tags  = list(dict.fromkeys(t for t in all_tags if t))[:60]
        raw_new   = list(dict.fromkeys(t for t in raw_new_unfiltered if t))[:20]

        moderation_notes: list[str] = []
        scene_text = str(parsed.get("scene", "")).lower()
        outdoor_scene = any(word in scene_text for word in OUTDOOR_SCENE_WORDS)
        if outdoor_scene:
            before = len(all_tags)
            all_tags = [t for t in all_tags if t not in INTERIOR_WORK_TAGS]
            removed = before - len(all_tags)
            if removed:
                moderation_notes.append(f"interior_tags_removed_for_outdoor_scene: removed={removed}")

        work_tags = [t for t in all_tags if t in CONSTRUCTION_WORK_TAGS]
        if len(all_tags) > 12 or len(work_tags) >= 8:
            neutral = [t for t in all_tags if t in NEUTRAL_FALLBACK_TAGS]
            moderation_notes.append(
                f"tag_spam_rejected: total={len(all_tags)} construction_work={len(work_tags)}"
            )
            all_tags = neutral[:8]
            raw_new = []

        approved_tags = [t for t in all_tags if t in approved_tag_set]
        new_tags      = [t for t in all_tags if t not in approved_tag_set and t in NEUTRAL_FALLBACK_TAGS] + raw_new
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

        raw_meta = dict(raw_response or {})
        if moderation_notes:
            raw_meta["postprocess_warnings"] = moderation_notes

        return ImageAnalysisResult(
            scene_dk        = self._normalize_scene_text(parsed.get("scene")),
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
            raw_response    = raw_meta,
            new_tags_da     = new_tags_da_map,
        )
