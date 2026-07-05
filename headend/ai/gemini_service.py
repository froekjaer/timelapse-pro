from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
import uuid as _uuid
from pathlib import Path
from typing import Optional

try:
    from .ollama_service import GDPRFlag, MAX_IMAGE_BYTES, ImageAnalysisResult, _resize_with_pil
    from .tag_vocabulary import normalize_tag
except ImportError:
    if __package__:
        raise
    from ollama_service import GDPRFlag, MAX_IMAGE_BYTES, ImageAnalysisResult, _resize_with_pil
    from tag_vocabulary import normalize_tag

log = logging.getLogger(__name__)

RETRYABLE_ERROR_MARKERS = (
    "503",
    "UNAVAILABLE",
    "RESOURCE_EXHAUSTED",
    "RATE_LIMIT",
    "temporarily",
    "high demand",
)
# Billedbudget til Gemini (cloud). Det DELTE MAX_IMAGE_BYTES=900KB var tænkt til
# den lille lokale Ollama — for Gemini krympede det 6-7 MB fotos til ~890 px, så
# fjerne detaljer (tegltage, kirketårn, arbejdere) forsvandt. Gemini 2.5 håndterer
# store billeder fint, så vi giver den et meget større budget → langt rigere tags.
GEMINI_MAX_IMAGE_EDGE  = int(os.getenv("TIMELAPSE_GEMINI_MAX_IMAGE_EDGE", "3072"))
GEMINI_MAX_IMAGE_BYTES = int(os.getenv("TIMELAPSE_GEMINI_MAX_IMAGE_BYTES", str(4_000_000)))

# Rå JSON-schema (dict) — bruges til Batch API (JSONL skal være json.dumps'bar,
# kan ikke indeholde types.Schema-objekter). Skal afspejle samme struktur som
# de typed Schema-objekter bygget i analyse() — hold dem i sync ved ændringer.
RESPONSE_SCHEMA_DICT = {
    "type": "OBJECT",
    "properties": {
        "scene":      {"type": "STRING"},
        "tags":       {"type": "ARRAY", "items": {"type": "STRING"}},
        "new_tags":   {"type": "ARRAY", "items": {"type": "STRING"}},
        "new_tags_da": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": {"type": "NUMBER"},
        "change": {
            "type": "OBJECT",
            "properties": {
                "detected":     {"type": "BOOLEAN"},
                "summary":      {"type": "STRING"},
                "new_items":    {"type": "ARRAY", "items": {"type": "STRING"}},
                "removed_items": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["detected", "summary", "new_items", "removed_items"],
        },
        "quality": {
            "type": "OBJECT",
            "properties": {
                "flag": {"type": "STRING"},
                "ok":   {"type": "BOOLEAN"},
            },
            "required": ["flag", "ok"],
        },
        "gdpr": {
            "type": "OBJECT",
            "properties": {
                "has_data": {"type": "BOOLEAN"},
                "detections": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type":   {"type": "STRING"},
                            "detail": {"type": "OBJECT"},
                            "bbox":   {"type": "ARRAY", "items": {"type": "NUMBER"}},
                        },
                        "required": ["type"],
                    },
                },
            },
            "required": ["has_data", "detections"],
        },
    },
    "required": ["scene", "tags", "new_tags", "new_tags_da", "confidence", "change", "quality", "gdpr"],
}


def build_prompt_text(
    vocabulary_by_cat: dict[str, list[str]],
    has_reference: bool = False,
    prompt_examples: Optional[list[str]] = None,
    context_block: str = "",
) -> str:
    """Byg analyse-prompten — delt mellem synkron analyse() og batch-requests.

    HYBRID, ÅBENT vokabular (v4): modellen tagger FRIT hvad den faktisk ser.
    Listen herunder er INSPIRATION og hjælp til ensartede ord — IKKE en
    afkrydsningsliste. Tidligere blev hele vokabularet rakt frem med "match
    EXACTLY", hvilket fik modellen til at rapportere fravær (no_crane,
    no_worker). Den adfærd er nu eksplicit forbudt.

    context_block: valgfri kontekstblok (kunde/site/kamera/tid/baseline) fra
                   capture_context.format_context_block().
    """
    # Vokabularet vises kompakt som inspiration. Vi viser kategori + ord, men
    # rammer det som "almindelige ord", ikke som en lukket liste.
    vocab_lines = [f"  [{cat}]: {', '.join(tags)}" for cat, tags in vocabulary_by_cat.items()]
    examples_txt = ""
    if prompt_examples:
        examples_txt = "\n## LÆRTE EKSEMPLER (tidligere godkendte tags — til inspiration)\n" + "\n".join(
            f"  - {example}" for example in prompt_examples[:10]
        )
    change_txt = ""
    if has_reference:
        change_txt = (
            "\n## ÆNDRING SIDEN SIDST\n"
            "Du modtager TO billeder: BILLEDE 1 = referencebillede (tidligere), "
            "BILLEDE 2 = det aktuelle billede du skal analysere. Beskriv i "
            '"change" hvad der konkret er nyt, fjernet eller flyttet. Ignorer '
            "rene lys-/vejrforskelle som 'ændring'.\n"
        )
    context_txt = f"\n{context_block}\n" if context_block else ""

    return f"""You are an expert AI observer for outdoor time-lapse cameras (typically Danish construction sites, but NOT always — it may be landscape, a street, a yard or a roof).

Your job is to look at the image like an attentive human guard would and describe what is ACTUALLY there — freely and in your own words — with special attention to anything unusual, new or worth a second look.
{context_txt}
## HOW TO TAG (open vocabulary)
- Describe the WHOLE scene, not just the weather. Name the actual content: structures (roofs, roof type, facades, gables, chimneys, windows), building types (house, apartment block, etc.), vegetation (trees, forest, hedge, grass, garden), vehicles, terrain and surroundings (road, city view, hills, water) — and on a building site also the machinery, materials and construction stage. THEN add light/weather and finally image quality.
- There is NO rigid quota, but a content-rich image deserves a THOROUGH set — typically 12–25 tags. Only return few tags when the image is genuinely simple (e.g. nothing but sky). Never pad with things that aren't there.
- Tags MUST be English, lowercase, underscore_separated (e.g. "tower_crane", "roof_tiles", "car_in_driveway").
- Tag ONLY what is genuinely visible. NEVER tag the ABSENCE of something. Do not output tags like "no_crane", "no_worker", "no_activity", "nothing_unusual" — if it isn't there, simply don't mention it.
- The vocabulary below is INSPIRATION and helps keep wording consistent — it is NOT a checklist. If a word fits exactly, reuse it (put it in "tags"). If you need a word that isn't listed, invent it and put it in "new_tags".
- CONSISTENCY: if a listed word already covers the concept, REUSE it instead of inventing a near-synonym — use "city_view" (not "view_over_town"/"landscape_view"), "residential_area" (not "residential_housing"). One concept = one tag.
- Tags MUST be English even for Danish-specific things: "danish_flag" (not "dannebrog"), "construction_site" (not "byggeplads").
- Do not assume construction. If the scene is mainly landscape, rooftops, a street or a yard, tag THAT richly (roofs, trees, buildings, city view, vehicles …).

## TAG VOCABULARY (inspiration — reuse when it fits)
{chr(10).join(vocab_lines)}
{examples_txt}
## EVENTS & ANOMALIES (look actively for these — tag them when present)
- Safety/emergency: fire, smoke, flames, flooding, water_damage, structural_damage, crack, collapse_risk, accident.
- Emergency vehicles: ambulance, fire_truck, police_car.
- Security/novelty: unauthorized_person, unknown_vehicle, person_at_night, vehicle_at_night, people_in_normally_empty_area, abandoned_equipment, vandalism, theft_risk, animal_on_site.
- Use the KONTEXT above to judge what is UNUSUAL for THIS camera (e.g. a vehicle in a driveway that the baseline doesn't describe, or people present at night).
- When you tag something from this group, mention it briefly in "scene" so a human knows why.

## IMAGE QUALITY (judge independently of the scene)
- Set "quality.flag" to the single most relevant of: clear_image, overexposed, underexposed, blown_highlights, glare, sun_in_lens, lens_flare, low_contrast, dirty_lens, condensation_on_lens, foggy_image, motion_blur, incorrect_focus, obstruction_in_front_of_camera, night_image_ok, night_image_too_dark, camera_moved.
- "quality.ok" = false if the image is hard to use for documentation (heavy glare/overexposure, blur, dirty lens, too dark, obstruction). Otherwise true.
- You may ALSO add relevant quality words to "tags" (e.g. "glare", "overexposed", "dirty_lens") so they are searchable.
- DEAD FRAMES — use VERY sparingly: tag "unusable_image" (quality.ok=false) ONLY when the frame has NO discernible content at all — a uniform blank/black/gray sensor error, a total whiteout, or the lens fully blocked. If you can make out ANY real content — ground, a wall, a roof, structures, vegetation, sky, vehicles — even in dull, flat, overcast or low-contrast light, or even if a large part of the frame is a single gray surface, it is NOT unusable: describe what you see normally. An overcast or gray scene is a REAL scene, not a dead frame. When you do use "unusable_image", use that ONE tag only — never invent synonyms (gray_image, blank_image, image_error …) and add no scene/weather tags.

## DANISH TRANSLATIONS FOR NEW TAGS
- "new_tags_da" MUST be a PARALLEL ARRAY to "new_tags" — same length, same order. For each new tag, give a short natural Danish translation (e.g. "new_tags": ["loading_ramp"], "new_tags_da": ["lastrampe"]). It's a suggestion a human reviews later. If "new_tags" is empty, "new_tags_da" is also empty.

## GDPR
- Report ONLY presence/count of persons, faces and license plates in "gdpr". NEVER read or transcribe names or plate text.
{change_txt}
## RETURN ONLY JSON
{{
  "scene": "Kort dansk beskrivelse af hvad billedet viser — nævn særligt det usædvanlige (fri tekst, ikke et tag)",
  "tags": ["tag1", "tag2"],
  "new_tags": [],
  "new_tags_da": [],
  "confidence": 0.90,
  "change": {{"detected": false, "summary": null, "new_items": [], "removed_items": []}},
  "quality": {{"flag": "clear_image", "ok": true}},
  "gdpr": {{"has_data": false, "detections": []}}
}}"""


def validate_batch_bucket_region(vertex_region: str, bucket_region: str) -> None:
    """GDPR-guard (R12/DPIA, se Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md §4):
    et GCS-bucket brugt til Vertex AI batch-jobs SKAL ligge i samme region-familie som
    selve Vertex-endpointet, ellers brydes databehandlings-garantien på data-at-rest
    under batch-kørslen (data kunne ende uden for EU selvom Vertex-kaldet selv går til
    en EU-region).

    Delt mellem to kaldesteder der ELLERS nemt kunne drifte fra hinanden:
    `headend/main.py` (API-endepunktet bag "Kør AI-batch nu" i UI'et) og
    `headend/ai/ai_batch_submit.py` (CLI-scriptet til manuel bulk re-tag). Før dette
    blev delt ud (2026-07-05, Claude periodisk tjek) havde kun API-stien tjekket dette
    — CLI-scriptet kunne sende et helt bulk-batch-job til et forkert-region bucket uden
    nogen advarsel.

    Bevidst IKKE fail-closed hvis `bucket_region` er tom (ikke konfigureret) — se
    RISK_ASSESSMENT_v10.md R12: dette er et no-op i det tilfælde, ikke en fejl, for at
    undgå at et hidtil fungerende, korrekt opsat batch-job pludselig stopper, fordi
    nogen aldrig har udfyldt det valgfrie 'gemini_gcs_bucket_region'-felt. Tjekker kun
    at de to regioner er i samme "familie" (fx begge 'europe-*'), IKKE at de faktisk er
    i EU — det er stadig operatørens ansvar at selve Vertex-regionen (`GOOGLE_CLOUD_LOCATION`
    / 'gemini_location') er sat til en EU-region i første omgang.

    Rejser ValueError (med samme, danske fejltekst begge steder) hvis begge er sat og
    ikke matcher. Ellers intet (ingen returværdi).
    """
    vertex_region = (vertex_region or "").strip().lower()
    bucket_region = (bucket_region or "").strip().lower()
    if bucket_region and vertex_region and not bucket_region.startswith(vertex_region.split("-")[0]):
        raise ValueError(
            f"GCS-bucket region ({bucket_region}) matcher ikke Vertex AI region ({vertex_region}) — "
            "stoppet for at undgå databehandling uden for EU. Bekræft 'gemini_gcs_bucket_region' i Indstillinger → AI."
        )


class GeminiVisionService:
    def __init__(
        self,
        service_account_path: str = "",
        project_id: str = "",
        location: str = "",
        model: str = "gemini-2.5-flash-lite-preview-06-17",
        api_key: str = "",
    ):
        service_account_path = service_account_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
        api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        self.model = model
        self.project = project_id
        self.location = location
        self.is_vertex = bool(service_account_path and Path(service_account_path).exists())
        self._client = self._build_client(service_account_path, project_id, location, api_key)

    def _build_client(self, sa_path: str, project: str, location: str, api_key: str):
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError("Koer: pip install google-genai") from exc

        if sa_path and Path(sa_path).exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
            client = genai.Client(vertexai=True, project=project, location=location)
            log.info("Gemini klient: Vertex AI (%s)", location)
        elif api_key:
            client = genai.Client(api_key=api_key)
            log.warning("Gemini klient: AI Studio")
        else:
            raise ValueError("Ingen service account eller API-noegle")

        return client

    def analyse(
        self,
        image_path: Path | str,
        vocabulary_by_cat: dict[str, list[str]],
        approved_tag_set: set[str],
        reference_image_path: Optional[Path | str] = None,
        prompt_examples: Optional[list[str]] = None,
        context_block: str = "",
    ) -> ImageAnalysisResult:
        from google.genai import types

        start = time.monotonic()

        prompt = build_prompt_text(
            vocabulary_by_cat,
            has_reference=bool(reference_image_path),
            prompt_examples=prompt_examples,
            context_block=context_block,
        )

        contents = [prompt]
        if reference_image_path:
            contents.append(self._load_part(reference_image_path))
        contents.append(self._load_part(image_path))

        change_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "detected": types.Schema(type=types.Type.BOOLEAN),
                "summary": types.Schema(type=types.Type.STRING),
                "new_items": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "removed_items": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
            },
            required=["detected", "summary", "new_items", "removed_items"],
        )

        quality_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "flag": types.Schema(type=types.Type.STRING),
                "ok": types.Schema(type=types.Type.BOOLEAN),
            },
            required=["flag", "ok"],
        )

        gdpr_det = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "type": types.Schema(type=types.Type.STRING),
                "detail": types.Schema(type=types.Type.OBJECT),
                "bbox": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.NUMBER),
                ),
            },
            required=["type"],
        )

        gdpr_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "has_data": types.Schema(type=types.Type.BOOLEAN),
                "detections": types.Schema(type=types.Type.ARRAY, items=gdpr_det),
            },
            required=["has_data", "detections"],
        )

        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "scene": types.Schema(type=types.Type.STRING),
                "tags": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "new_tags": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "new_tags_da": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "confidence": types.Schema(type=types.Type.NUMBER),
                "change": change_schema,
                "quality": quality_schema,
                "gdpr": gdpr_schema,
            },
            required=["scene", "tags", "new_tags", "new_tags_da", "confidence", "change", "quality", "gdpr"],
        )

        response = self._generate_content_with_retry(
            contents=contents,
            config=types.GenerateContentConfig(
                # Hævet fra 0.1: åbent vokabular kræver lidt mere frihed til at
                # finde dækkende, naturlige ord — stadig lavt nok til konsistens.
                temperature=0.35,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

        raw_text = response.text or ""
        duration_ms = int((time.monotonic() - start) * 1000)
        parsed = self._parse(raw_text)

        return self._build(parsed, approved_tag_set, reference_image_path is not None, duration_ms, raw_text)

    def _generate_content_with_retry(self, contents: list, config):
        delays = (2, 5, 10)
        last_error = None

        for attempt in range(len(delays) + 1):
            try:
                return self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                last_error = exc
                if not self._is_retryable_error(exc) or attempt == len(delays):
                    raise

                delay = delays[attempt]
                log.warning(
                    "Gemini transient fejl (%s). Proever igen om %s sekunder (%s/%s)",
                    exc,
                    delay,
                    attempt + 1,
                    len(delays),
                )
                time.sleep(delay)

        raise last_error

    def health_check(self) -> bool:
        try:
            from google import genai  # noqa: F401

            return True
        except Exception:
            return False

    def _load_part(self, path: Path | str):
        from google.genai import types

        data = Path(path).read_bytes()
        if len(data) > GEMINI_MAX_IMAGE_BYTES or self._should_resize_by_dimensions(data):
            data = self._resize(data)
        return types.Part.from_bytes(data=data, mime_type="image/jpeg")

    def _should_resize_by_dimensions(self, data: bytes) -> bool:
        try:
            import cv2
            import numpy as np

            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return False
            h, w = img.shape[:2]
            return max(w, h) > GEMINI_MAX_IMAGE_EDGE
        except Exception:
            return False

    def _resize(self, data: bytes) -> bytes:
        try:
            import cv2
            import numpy as np

            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return data[:MAX_IMAGE_BYTES]
            h, w = img.shape[:2]
            dimension_scale = min(1.0, GEMINI_MAX_IMAGE_EDGE / max(w, h))
            byte_scale = min(1.0, (GEMINI_MAX_IMAGE_BYTES / len(data)) ** 0.5 * 0.9)
            scale = min(dimension_scale, byte_scale)
            if scale >= 1.0:
                return data
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return buf.tobytes()
        except Exception:
            # cv2 mangler/fejler (fx venv på flaky volumen) — prøv PIL, så vi stadig
            # nedskalerer. ALDRIG trunker bytes (det giver et korrupt JPEG til Gemini).
            return _resize_with_pil(data, GEMINI_MAX_IMAGE_EDGE, GEMINI_MAX_IMAGE_BYTES)

    def _is_retryable_error(self, exc: Exception) -> bool:
        text = str(exc)
        upper_text = text.upper()
        return any(marker in text or marker in upper_text for marker in RETRYABLE_ERROR_MARKERS)

    def _parse(self, text: str) -> dict:
        clean = re.sub(r"```(?:json)?\s*", "", text).strip()
        clean = re.sub(r"```\s*$", "", clean).strip()
        clean = re.sub(r",\s*([}\]])", r"\1", clean)

        try:
            return json.loads(clean)
        except json.JSONDecodeError as exc:
            first_error = exc

        match = re.search(r"({.*})", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                first_error = exc

        tail = clean[-160:].replace("\n", "\\n")
        raise ValueError(
            f"Gemini returnerede ugyldig eller afkortet JSON "
            f"(laengde={len(clean)}, fejl={first_error}, tail={tail!r})"
        )

    def _build(
        self,
        parsed: dict,
        approved_tag_set: set[str],
        has_ref: bool,
        duration_ms: int,
        raw_text: str,
    ) -> ImageAnalysisResult:
        # normalize_tag bringer tags på kanonisk form og kollapser synonymer/danske
        # leaks, så søgning bliver ensartet (city_view i stedet for 10 varianter).
        # dedup (dict.fromkeys bevarer rækkefølge) — undgår dubletter som "trees","trees"
        all_tags = list(dict.fromkeys(t for t in (normalize_tag(tag) for tag in parsed.get("tags", [])) if t))
        raw_new = list(dict.fromkeys(t for t in (normalize_tag(tag) for tag in parsed.get("new_tags", [])) if t))
        raw_new_da = [str(t).strip() for t in parsed.get("new_tags_da", [])]
        # Gemini SKAL levere new_tags_da som parallelt array (samme længde/orden som
        # new_tags) — zip sammen til en dict. Hvis modellen afviger i længde,
        # zip() bare matcher det den kan og dropper resten (ingen krash).
        new_tags_da_map = dict(zip(raw_new, raw_new_da))
        approved = [tag for tag in all_tags if tag in approved_tag_set]
        # new: deduppet OG disjunkt fra approved (et ord modellen lagde i både
        # tags og new_tags må ikke ende begge steder → ellers kryds-dublet i ai_tags)
        new = [t for t in dict.fromkeys([tag for tag in all_tags if tag not in approved_tag_set] + raw_new)
               if t not in approved_tag_set]

        change = parsed.get("change", {}) if has_ref else {}
        change_detected = bool(change.get("detected", False))
        change_tags = []
        if change_detected:
            change_tags = list(change.get("new_items", [])) + [
                f"fjernet_{item}" for item in change.get("removed_items", [])
            ]

        quality = parsed.get("quality", {})
        gdpr = parsed.get("gdpr", {})
        gdpr_flags = []
        has_gdpr = bool(gdpr.get("has_data", False))

        for detection in gdpr.get("detections", []):
            detection_type = str(detection.get("type", ""))
            if detection_type in ("face", "license_plate", "person_counted", "vehicle_detail"):
                gdpr_flags.append(
                    GDPRFlag(
                        detection_type=detection_type,
                        detail=detection.get("detail", {}),
                        bounding_box=detection.get("bbox"),
                    )
                )
                has_gdpr = True

        return ImageAnalysisResult(
            scene_dk=str(parsed.get("scene", "")),
            approved_tags=approved,
            new_tags=new,
            change_detected=change_detected,
            change_summary=change.get("summary") if change_detected else None,
            change_tags=change_tags,
            quality_flag=str(quality.get("flag", "ukendt")),
            quality_ok=bool(quality.get("ok", True)),
            has_gdpr_data=has_gdpr,
            gdpr_detections=gdpr_flags,
            model=self.model,
            duration_ms=duration_ms,
            raw_response={"response": raw_text},
            new_tags_da=new_tags_da_map,
        )

    # ── Batch API — bulk genanalyse til ~50% af normal pris ────────────────
    # Asynkront: submit job → poll status → download resultater når succeeded.
    # SLO 24 timer, ofte hurtigere. Bruges KUN af post-processing bulk-jobs,
    # ikke af den løbende live capture-pipeline (se ai/integration.py).

    def _encode_image_b64(self, path: Path | str) -> str:
        """Samme resize-logik som _load_part, men returnerer base64 til JSONL."""
        data = Path(path).read_bytes()
        if len(data) > GEMINI_MAX_IMAGE_BYTES or self._should_resize_by_dimensions(data):
            data = self._resize(data)
        return base64.b64encode(data).decode("ascii")

    def build_batch_request_line(
        self,
        key: str,
        image_path: Path | str,
        vocabulary_by_cat: dict[str, list[str]],
        context_block: str = "",
    ) -> dict:
        """Byg én JSONL-linje (dict) til Batch API — samme prompt/schema som analyse()."""
        prompt = build_prompt_text(vocabulary_by_cat, has_reference=False, context_block=context_block)
        b64 = self._encode_image_b64(image_path)
        return {
            "key": key,
            "request": {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                    ],
                }],
                "generation_config": {
                    "temperature": 0.35,
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json",
                    "response_schema": RESPONSE_SCHEMA_DICT,
                },
            },
        }

    def submit_batch_job(
        self,
        items: list[tuple[str, Path | str]],
        vocabulary_by_cat: dict[str, list[str]],
        display_name: str = "",
        gcs_bucket: str = "",
        context_by_key: Optional[dict[str, str]] = None,
    ) -> str:
        """Byg batch-anmodninger af items=[(key, image_path), ...] og opret batch-job.
        Returnerer Google's job-navn til polling/resultater.

        Router automatisk efter auth-metode:
          - AI Studio (api_key): Files API — upload JSONL direkte til Google.
          - Vertex AI (service account): kræver gcs_bucket — uploader JSONL til
            Cloud Storage og peger jobbet derhen (Vertex har ikke Files API
            til batch). VIGTIGT for GDPR: bucket'en SKAL ligge i samme EU-region
            som self.location for at databehandlings-garantien holder hele vejen.
        """
        context_by_key = context_by_key or {}
        if self.is_vertex:
            if not gcs_bucket:
                raise ValueError("Vertex AI batch kræver et GCS-bucket (gcs_bucket) — ingen er konfigureret")
            return self._submit_batch_job_vertex_gcs(items, vocabulary_by_cat, gcs_bucket, display_name, context_by_key)
        return self._submit_batch_job_ai_studio(items, vocabulary_by_cat, display_name, context_by_key)

    def _submit_batch_job_ai_studio(
        self,
        items: list[tuple[str, Path | str]],
        vocabulary_by_cat: dict[str, list[str]],
        display_name: str = "",
        context_by_key: Optional[dict[str, str]] = None,
    ) -> str:
        """AI Studio (api_key) batch — Files API. Se submit_batch_job() for routing."""
        import tempfile

        context_by_key = context_by_key or {}
        display_name = display_name or f"timelapse-batch-{_uuid.uuid4().hex[:8]}"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            tmp_path = f.name
            for key, image_path in items:
                line = self.build_batch_request_line(key, image_path, vocabulary_by_cat, context_by_key.get(key, ""))
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

        try:
            from google.genai import types
            uploaded = self._client.files.upload(
                file=tmp_path,
                config=types.UploadFileConfig(display_name=display_name, mime_type="jsonl"),
            )
            job = self._client.batches.create(
                model=self.model,
                src=uploaded.name,
                config={"display_name": display_name},
            )
            log.info("Gemini batch job (AI Studio) oprettet: %s (%d billeder)", job.name, len(items))
            return job.name
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _submit_batch_job_vertex_gcs(
        self,
        items: list[tuple[str, Path | str]],
        vocabulary_by_cat: dict[str, list[str]],
        gcs_bucket: str,
        display_name: str = "",
        context_by_key: Optional[dict[str, str]] = None,
    ) -> str:
        """Vertex AI batch — uploader JSONL til Cloud Storage (Vertex har ikke
        Files API til batch). JSONL-linjer er BARE request-objekter uden
        "key"-felt (Vertex-konventionen er anderledes end AI Studio) — derfor
        matches resultater POSITIONELT (samme rækkefølge ind som ud) i stedet
        for via key. Se _finalize_ai_batch_job i main.py.
        """
        try:
            from google.cloud import storage as _gcs
        except ImportError as exc:
            raise ImportError(
                "Vertex AI batch kræver google-cloud-storage: pip install google-cloud-storage"
            ) from exc

        display_name = display_name or f"timelapse-batch-{_uuid.uuid4().hex[:8]}"
        bucket_name = gcs_bucket.replace("gs://", "").split("/")[0]
        job_prefix = f"ai-batch/{display_name}"

        # Vertex kræver at hver linje har en "request"-property — fjernede den
        # fejlagtigt i en tidligere version (testet og bekræftet ved fejl:
        # "lines ... must contain the 'request' property"). "key" bevares også
        # — ufarligt ekstra felt, og giver mulighed for key-baseret matching af
        # resultater hvis Vertex echoer den tilbage (se _download_batch_results_vertex_gcs).
        # Stream JSONL'en til en TEMP-FIL på disken (én base64-billede ad gangen) i
        # stedet for at bygge hele strengen i hukommelsen — ellers sprænger store
        # batches (tusinder af billeder = titals GB) RAM'en på Mac'en. Upload
        # derefter filen til GCS.
        import tempfile, os as _os_local
        context_by_key = context_by_key or {}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as _jf:
            tmp_path = _jf.name
            for key, image_path in items:
                line = self.build_batch_request_line(key, image_path, vocabulary_by_cat, context_by_key.get(key, ""))
                _jf.write(json.dumps(line, ensure_ascii=False) + "\n")

        try:
            storage_client = _gcs.Client(project=self.project) if self.project else _gcs.Client()
            bucket = storage_client.bucket(bucket_name)
            input_blob = bucket.blob(f"{job_prefix}/input.jsonl")
            input_blob.upload_from_filename(tmp_path, content_type="application/jsonl")
        finally:
            try:
                _os_local.unlink(tmp_path)
            except OSError:
                pass

        input_uri = f"gs://{bucket_name}/{job_prefix}/input.jsonl"
        output_uri = f"gs://{bucket_name}/{job_prefix}/output"

        from google.genai.types import CreateBatchJobConfig
        job = self._client.batches.create(
            model=self.model,
            src=input_uri,
            config=CreateBatchJobConfig(dest=output_uri, display_name=display_name),
        )
        log.info("Gemini batch job (Vertex/GCS) oprettet: %s (%d billeder) → %s",
                  job.name, len(items), output_uri)
        return job.name

    def get_batch_status(self, job_name: str) -> dict:
        """Hent status for et batch-job.
        AI Studio state: PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED|EXPIRED.
        Vertex state:    PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED|PAUSED.
        """
        job = self._client.batches.get(name=job_name)
        state = job.state.name if hasattr(job.state, "name") else str(job.state)
        # Løbende fremdrift (successful/failed/incomplete) til UI'en. google.genai's
        # BatchJob (Vertex-backend) kan eksponere det under forskellige feltnavne
        # afhængigt af SDK-version — prøv defensivt; None hvis intet findes (så
        # falder UI'en tilbage til kun total_count, ingen regression).
        progress = None
        for _attr in ("completion_stats", "completionStats"):
            cs = getattr(job, _attr, None)
            if not cs:
                continue
            def _stat(*names):
                for n in names:
                    v = getattr(cs, n, None)
                    if v is None and isinstance(cs, dict):
                        v = cs.get(n)
                    if v is not None:
                        try:
                            return int(v)
                        except (TypeError, ValueError):
                            return None
                return None
            succ = _stat("successful_count", "successfulCount")
            fail = _stat("failed_count", "failedCount")
            inc  = _stat("incomplete_count", "incompleteCount")
            if succ is not None or fail is not None:
                progress = {"success": succ or 0, "error": fail or 0, "incomplete": inc}
                break
        return {"state": state, "job": job, "progress": progress}

    def download_batch_results(self, job) -> list[dict]:
        """Download og parse resultater fra et succeeded batch-job.
        Returnerer liste af {"key": str|None, "text": str|None, "error": str|None}.
        "key" er None for Vertex-jobs — match da POSITIONELT (samme rækkefølge).
        """
        if self.is_vertex:
            return self._download_batch_results_vertex_gcs(job)
        return self._download_batch_results_ai_studio(job)

    def _download_batch_results_ai_studio(self, job) -> list[dict]:
        results: list[dict] = []

        if getattr(job, "dest", None) and getattr(job.dest, "file_name", None):
            raw = self._client.files.download(file=job.dest.file_name)
            content = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            for line in content.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                key = row.get("key")
                if row.get("response"):
                    try:
                        parts = row["response"]["candidates"][0]["content"]["parts"]
                        text = "".join(p.get("text", "") for p in parts)
                        results.append({"key": key, "text": text, "error": None})
                    except Exception as exc:
                        results.append({"key": key, "text": None, "error": str(exc)})
                else:
                    results.append({"key": key, "text": None, "error": str(row.get("status") or row.get("error") or "ukendt fejl")})

        elif getattr(job, "dest", None) and getattr(job.dest, "inlined_responses", None):
            for resp in job.dest.inlined_responses:
                key = getattr(resp, "key", None)
                if getattr(resp, "response", None):
                    try:
                        results.append({"key": key, "text": resp.response.text, "error": None})
                    except Exception as exc:
                        results.append({"key": key, "text": None, "error": str(exc)})
                else:
                    results.append({"key": key, "text": None, "error": str(getattr(resp, "error", "ukendt fejl"))})

        return results

    def _download_batch_results_vertex_gcs(self, job) -> list[dict]:
        """Læs predictions.jsonl (evt. sharded) fra GCS output-prefix.
        Vertex AI batch-output følger konventionen {"status":, "request":, "response":}
        per linje — ÆLDRE Vertex batch-jobs kan i sjældne tilfælde afvige i feltnavne;
        hvis parsing fejler for alle linjer logges en tydelig fejl med rå-eksempel
        i stedet for at gætte og risikere forkert matchede resultater.
        """
        try:
            from google.cloud import storage as _gcs
        except ImportError as exc:
            raise ImportError(
                "Vertex AI batch kræver google-cloud-storage: pip install google-cloud-storage"
            ) from exc

        dest = getattr(job, "dest", None)
        gcs_uri = getattr(dest, "gcs_uri", None) if dest else None
        if not gcs_uri:
            raise ValueError("Batch-job har intet GCS output-prefix (job.dest.gcs_uri mangler)")

        bucket_name, _, prefix = gcs_uri.replace("gs://", "").partition("/")
        storage_client = _gcs.Client(project=self.project) if self.project else _gcs.Client()
        bucket = storage_client.bucket(bucket_name)
        blobs = [b for b in bucket.list_blobs(prefix=prefix) if b.name.endswith(".jsonl")]
        if not blobs:
            raise ValueError(f"Ingen .jsonl-resultatfiler fundet under {gcs_uri}")

        results: list[dict] = []
        for blob in blobs:
            content = blob.download_as_text()
            for line in content.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                # Vertex echoer evt. "key" tilbage hvis det var i input-linjen —
                # brug det hvis muligt (mere robust end positionel matching).
                # Ellers None, og _finalize_ai_batch_job falder tilbage til
                # positionel matching ud fra rækkefølgen.
                key = row.get("key") or (row.get("request") or {}).get("key")
                response = row.get("response")
                if response:
                    try:
                        parts = response["candidates"][0]["content"]["parts"]
                        text = "".join(p.get("text", "") for p in parts)
                        results.append({"key": key, "text": text, "error": None})
                    except Exception as exc:
                        results.append({"key": key, "text": None, "error": f"parse-fejl: {exc} (rå: {str(row)[:200]})"})
                else:
                    results.append({"key": key, "text": None, "error": str(row.get("status") or row.get("error") or f"ukendt struktur: {str(row)[:200]}")})

        return results

    def parse_batch_result_text(self, text: str, approved_tag_set: set[str]) -> ImageAnalysisResult:
        """Parse ét batch-resultats JSON-svar til samme ImageAnalysisResult som analyse()."""
        parsed = self._parse(text)
        return self._build(parsed, approved_tag_set, has_ref=False, duration_ms=0, raw_text=text)
