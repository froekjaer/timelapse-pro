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
    from .ollama_service import GDPRFlag, MAX_IMAGE_BYTES, ImageAnalysisResult
except ImportError:
    if __package__:
        raise
    from ollama_service import GDPRFlag, MAX_IMAGE_BYTES, ImageAnalysisResult

log = logging.getLogger(__name__)

RETRYABLE_ERROR_MARKERS = (
    "503",
    "UNAVAILABLE",
    "RESOURCE_EXHAUSTED",
    "RATE_LIMIT",
    "temporarily",
    "high demand",
)
GEMINI_MAX_IMAGE_EDGE = 1920

# Rå JSON-schema (dict) — bruges til Batch API (JSONL skal være json.dumps'bar,
# kan ikke indeholde types.Schema-objekter). Skal afspejle samme struktur som
# de typed Schema-objekter bygget i analyse() — hold dem i sync ved ændringer.
RESPONSE_SCHEMA_DICT = {
    "type": "OBJECT",
    "properties": {
        "scene":      {"type": "STRING"},
        "tags":       {"type": "ARRAY", "items": {"type": "STRING"}},
        "new_tags":   {"type": "ARRAY", "items": {"type": "STRING"}},
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
    "required": ["scene", "tags", "new_tags", "confidence", "change", "quality", "gdpr"],
}


def build_prompt_text(
    vocabulary_by_cat: dict[str, list[str]],
    has_reference: bool = False,
    prompt_examples: Optional[list[str]] = None,
) -> str:
    """Byg analyse-prompten — delt mellem synkron analyse() og batch-requests."""
    vocab_lines = [f"  [{cat}]: {', '.join(tags)}" for cat, tags in vocabulary_by_cat.items()]
    examples_txt = ""
    if prompt_examples:
        examples_txt = "\n## LAERTE EKSEMPLER\n" + "\n".join(
            f"  - {example}" for example in prompt_examples[:10]
        )
    change_txt = ""
    if has_reference:
        change_txt = (
            "\nDu modtager TO billeder: BILLEDE 1 = reference, "
            "BILLEDE 2 = aktuelt.\n"
        )
    return f"""Du er et praecist dansk AI-system til byggepladser.
## TAG-VOKABULAR
{chr(10).join(vocab_lines)}
{examples_txt}
## REGLER
- Match ord fra listen NOEJAGTIGT og laeg dem i "tags".
- Nye ord laegges i "new_tags". Find mellem 15 og 35 tags i alt.
{change_txt}
## RETURNER KUN JSON
{{
  "scene": "Beskrivelse",
  "tags": ["tag1"],
  "new_tags": [],
  "confidence": 0.90,
  "change": {{"detected": false, "summary": null, "new_items": [], "removed_items": []}},
  "quality": {{"flag": "klart_billede", "ok": true}},
  "gdpr": {{"has_data": false, "detections": []}}
}}"""


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
    ) -> ImageAnalysisResult:
        from google.genai import types

        start = time.monotonic()

        prompt = build_prompt_text(
            vocabulary_by_cat,
            has_reference=bool(reference_image_path),
            prompt_examples=prompt_examples,
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
                "confidence": types.Schema(type=types.Type.NUMBER),
                "change": change_schema,
                "quality": quality_schema,
                "gdpr": gdpr_schema,
            },
            required=["scene", "tags", "new_tags", "confidence", "change", "quality", "gdpr"],
        )

        response = self._generate_content_with_retry(
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
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
        if len(data) > MAX_IMAGE_BYTES or self._should_resize_by_dimensions(data):
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
            byte_scale = min(1.0, (MAX_IMAGE_BYTES / len(data)) ** 0.5 * 0.9)
            scale = min(dimension_scale, byte_scale)
            if scale >= 1.0:
                return data
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return buf.tobytes()
        except Exception:
            return data[:MAX_IMAGE_BYTES]

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
        all_tags = [str(tag).lower().strip() for tag in parsed.get("tags", [])]
        raw_new = [str(tag).lower().strip() for tag in parsed.get("new_tags", [])]
        approved = [tag for tag in all_tags if tag in approved_tag_set]
        new = list(dict.fromkeys([tag for tag in all_tags if tag not in approved_tag_set] + raw_new))

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
        )

    # ── Batch API — bulk genanalyse til ~50% af normal pris ────────────────
    # Asynkront: submit job → poll status → download resultater når succeeded.
    # SLO 24 timer, ofte hurtigere. Bruges KUN af post-processing bulk-jobs,
    # ikke af den løbende live capture-pipeline (se ai/integration.py).

    def _encode_image_b64(self, path: Path | str) -> str:
        """Samme resize-logik som _load_part, men returnerer base64 til JSONL."""
        data = Path(path).read_bytes()
        if len(data) > MAX_IMAGE_BYTES or self._should_resize_by_dimensions(data):
            data = self._resize(data)
        return base64.b64encode(data).decode("ascii")

    def build_batch_request_line(
        self,
        key: str,
        image_path: Path | str,
        vocabulary_by_cat: dict[str, list[str]],
    ) -> dict:
        """Byg én JSONL-linje (dict) til Batch API — samme prompt/schema som analyse()."""
        prompt = build_prompt_text(vocabulary_by_cat, has_reference=False)
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
                    "temperature": 0.1,
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
    ) -> str:
        """Byg JSONL-fil af items=[(key, image_path), ...], upload og opret batch-job.
        Returnerer Google's job-navn (fx 'batches/123456') til polling/resultater.

        BEMÆRK: Kun testet/understøttet med AI Studio (api_key). Vertex AI
        (service account) bruger typisk Cloud Storage til batch input/output
        i stedet for Files API — denne metode er IKKE verificeret til Vertex.
        """
        if self.is_vertex:
            raise NotImplementedError(
                "Batch-mode er kun implementeret til Gemini AI Studio (API-nøgle). "
                "Vertex AI (service account) kræver Cloud Storage-baseret batch input — "
                "ikke understøttet endnu. Brug en AI Studio API-nøgle for batch-jobs."
            )
        import tempfile

        display_name = display_name or f"timelapse-batch-{_uuid.uuid4().hex[:8]}"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            tmp_path = f.name
            for key, image_path in items:
                line = self.build_batch_request_line(key, image_path, vocabulary_by_cat)
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
            log.info("Gemini batch job oprettet: %s (%d billeder)", job.name, len(items))
            return job.name
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def get_batch_status(self, job_name: str) -> dict:
        """Hent status for et batch-job. State: PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED|EXPIRED."""
        job = self._client.batches.get(name=job_name)
        state = job.state.name if hasattr(job.state, "name") else str(job.state)
        return {"state": state, "job": job}

    def download_batch_results(self, job) -> list[dict]:
        """Download og parse resultater fra et succeeded batch-job.
        Returnerer liste af {"key": str, "text": str|None, "error": str|None}.
        """
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

    def parse_batch_result_text(self, text: str, approved_tag_set: set[str]) -> ImageAnalysisResult:
        """Parse ét batch-resultats JSON-svar til samme ImageAnalysisResult som analyse()."""
        parsed = self._parse(text)
        return self._build(parsed, approved_tag_set, has_ref=False, duration_ms=0, raw_text=text)
