"""Provider adapters for the TimeLapse AI capability layer."""
from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from ai.provider_contract import (
    AICapability,
    ProviderOutput,
    ProviderUnavailable,
)


def _safe_provider_failure(exc: Exception) -> str:
    """Classify provider failures without emitting secrets or raw request payloads."""
    message = str(exc or "").lower()
    if any(token in message for token in ("401", "unauthenticated", "invalid api key", "authentication")):
        return "authentication_failed"
    if any(token in message for token in ("403", "permission denied", "permission_denied", "forbidden")):
        return "permission_denied"
    if any(token in message for token in ("404", "not found", "model not found")):
        return "model_or_endpoint_not_found"
    if any(token in message for token in ("429", "resource_exhausted", "rate limit", "quota")):
        return "quota_or_rate_limit"
    if any(token in message for token in ("region", "location")):
        return "region_or_location_error"
    if any(token in message for token in ("timeout", "timed out")):
        return "timeout"
    return type(exc).__name__


def _json_payload(text: str) -> dict[str, Any] | list[Any]:
    candidate = str(text or "").strip()
    if not candidate:
        raise ValueError("tomt structured response")
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\[{].*[\]}])\s*```", candidate, re.DOTALL)
        if not match:
            match = re.search(r"([\[{].*[\]}])", candidate, re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(1))
    if not isinstance(value, (dict, list)):
        raise ValueError("structured response skal være JSON object eller array")
    return value


class _BaseProvider:
    name = "unknown"
    capabilities: frozenset[AICapability] = frozenset()

    def supports(self, capability: AICapability) -> bool:
        return capability in self.capabilities

    def _require(self, capability: AICapability) -> None:
        if not self.supports(capability):
            raise ProviderUnavailable(self.name, f"capability {capability.value} understøttes ikke")


class OllamaProvider(_BaseProvider):
    name = "ollama"
    capabilities = frozenset({
        AICapability.VISION,
        AICapability.TEXT,
        AICapability.STRUCTURED,
        AICapability.LOCAL_EXECUTION,
    })

    def __init__(
        self,
        *,
        base_url: str,
        vision_model: str,
        text_model: str,
        timeout_s: int = 90,
        num_predict: int = 1800,
        temperature: float = 0.1,
        keep_alive_s: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.vision_model = vision_model
        self.text_model = text_model
        self.timeout_s = timeout_s
        self.num_predict = num_predict
        self.temperature = temperature
        self.keep_alive_s = keep_alive_s
        self._client = httpx.Client(timeout=timeout_s)

    def availability(self, capability: AICapability) -> dict[str, Any]:
        self._require(capability)
        try:
            response = self._client.get(f"{self.base_url}/api/tags", timeout=min(self.timeout_s, 5))
            response.raise_for_status()
            models = [
                str(item.get("name") or item.get("model") or "")
                for item in (response.json().get("models") or [])
            ]
            return {
                "available": True,
                "reason": None,
                "provider": self.name,
                "models": [model for model in models if model],
            }
        except Exception as exc:
            return {
                "available": False,
                "reason": type(exc).__name__,
                "provider": self.name,
            }

    def analyse_image(self, **kwargs):
        self._require(AICapability.VISION)
        from ai.ollama_service import OllamaVisionService

        service = OllamaVisionService(
            base_url=self.base_url,
            vision_model=kwargs.pop("model", None) or self.vision_model,
        )
        if not service.health_check():
            raise ProviderUnavailable(self.name, "Ollama vision runtime svarer ikke")
        return service.analyse(**kwargs)

    def _generate(self, prompt: str, *, structured: bool, model: str | None = None) -> ProviderOutput:
        capability = AICapability.STRUCTURED if structured else AICapability.TEXT
        self._require(capability)
        selected_model = model or self.text_model
        payload: dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive_s,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        if structured:
            payload["format"] = "json"

        started = time.monotonic()
        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            raw = response.json()
        except Exception as exc:
            raise ProviderUnavailable(self.name, type(exc).__name__) from exc

        content = str(raw.get("response") or "")
        data = _json_payload(content) if structured else None
        return ProviderOutput(
            provider=self.name,
            model=str(raw.get("model") or selected_model),
            capability=capability,
            duration_ms=int((time.monotonic() - started) * 1000),
            content=content,
            data=data,
            raw_response={
                key: raw.get(key)
                for key in (
                    "model", "created_at", "response", "done", "done_reason",
                    "total_duration", "load_duration", "prompt_eval_count",
                    "prompt_eval_duration", "eval_count", "eval_duration",
                )
                if key in raw
            },
            metadata={"execution": "local"},
        )

    def generate_text(self, prompt: str, **kwargs) -> ProviderOutput:
        return self._generate(prompt, structured=False, model=kwargs.get("model"))

    def generate_structured(self, prompt: str, **kwargs) -> ProviderOutput:
        return self._generate(prompt, structured=True, model=kwargs.get("model"))


class AppleFoundationProvider(_BaseProvider):
    name = "apple"
    capabilities = frozenset({
        AICapability.VISION,
        AICapability.TEXT,
        AICapability.STRUCTURED,
        AICapability.LOCAL_EXECUTION,
    })

    def __init__(self, *, timeout_s: int = 120, temperature: float = 0.2):
        self.timeout_s = timeout_s
        self.temperature = temperature

    @property
    def model(self) -> str:
        from ai.apple_foundation_service import APPLE_MODEL_NAME
        return APPLE_MODEL_NAME

    def availability(self, capability: AICapability) -> dict[str, Any]:
        self._require(capability)
        from ai.apple_foundation_service import AppleFoundationVisionService
        status = AppleFoundationVisionService(
            timeout_s=self.timeout_s,
            temperature=self.temperature,
        ).availability()
        return {
            **status,
            "provider": self.name,
            "model": self.model,
        }

    def analyse_image(self, **kwargs):
        self._require(AICapability.VISION)
        from ai.apple_foundation_service import AppleFoundationVisionService

        service = AppleFoundationVisionService(
            timeout_s=self.timeout_s,
            temperature=self.temperature,
        )
        status = service.availability()
        if not status.get("available"):
            raise ProviderUnavailable(self.name, str(status.get("reason") or "ikke tilgængelig"))
        kwargs.pop("model", None)
        return service.analyse(**kwargs)

    def _respond(self, prompt: str, *, structured: bool) -> ProviderOutput:
        capability = AICapability.STRUCTURED if structured else AICapability.TEXT
        self._require(capability)
        from ai.apple_foundation_service import _run, _sdk

        fm = _sdk()
        session = fm.LanguageModelSession()
        options = fm.GenerationOptions(temperature=self.temperature)
        request = prompt
        if structured:
            request += (
                "\n\nReturner KUN gyldig JSON uden markdown eller forklarende tekst. "
                "JSON-strukturen i opgaven skal følges."
            )

        started = time.monotonic()
        try:
            response = _run(
                __import__("asyncio").wait_for(
                    session.respond(request, options=options),
                    timeout=self.timeout_s,
                )
            )
        except Exception as exc:
            raise ProviderUnavailable(self.name, type(exc).__name__) from exc

        content = str(getattr(response, "content", response)).strip()
        data = _json_payload(content) if structured else None
        return ProviderOutput(
            provider=self.name,
            model=self.model,
            capability=capability,
            duration_ms=int((time.monotonic() - started) * 1000),
            content=content,
            data=data,
            raw_response=content,
            metadata={
                "execution": "local",
                "runtime": "apple_fm_sdk",
                "structured_mode": "json_parse" if structured else None,
            },
        )

    def generate_text(self, prompt: str, **kwargs) -> ProviderOutput:
        return self._respond(prompt, structured=False)

    def generate_structured(self, prompt: str, **kwargs) -> ProviderOutput:
        return self._respond(prompt, structured=True)


class GeminiProvider(_BaseProvider):
    name = "gemini"
    capabilities = frozenset({
        AICapability.VISION,
        AICapability.TEXT,
        AICapability.STRUCTURED,
        AICapability.CLOUD_EXECUTION,
    })

    def __init__(self, service):
        self.service = service

    @property
    def model(self) -> str:
        return str(self.service.model)

    def availability(self, capability: AICapability) -> dict[str, Any]:
        self._require(capability)
        try:
            from google.genai import types

            response = self.service._generate_content_with_retry(
                contents=["Reply exactly: TIMELAPSE_OK"],
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=16,
                ),
            )
            available = bool(str(getattr(response, "text", "") or "").strip())
        except Exception as exc:
            return {
                "available": False,
                "reason": _safe_provider_failure(exc),
                "provider": self.name,
                "model": self.model,
                "execution": "cloud",
            }
        return {
            "available": available,
            "reason": None if available else "empty_response",
            "provider": self.name,
            "model": self.model,
            "execution": "cloud",
        }

    def analyse_image(self, **kwargs):
        self._require(AICapability.VISION)
        kwargs.pop("model", None)
        return self.service.analyse(**kwargs)

    def batch_info(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "is_vertex": bool(getattr(self.service, "is_vertex", False)),
            "location": getattr(self.service, "location", None),
        }

    def submit_image_batch(
        self,
        *,
        items,
        vocabulary_by_cat,
        display_name: str,
        gcs_bucket: str,
        bucket_region: str = "",
        context_by_key=None,
    ):
        self._require(AICapability.VISION)
        if getattr(self.service, "is_vertex", False):
            from ai.gemini_service import validate_batch_bucket_region
            validate_batch_bucket_region(
                str(getattr(self.service, "location", "") or ""),
                str(bucket_region or ""),
            )
        return self.service.submit_batch_job(
            items=items,
            vocabulary_by_cat=vocabulary_by_cat,
            display_name=display_name,
            gcs_bucket=gcs_bucket,
            context_by_key=context_by_key or {},
        )

    def _generate(self, prompt: str, *, structured: bool) -> ProviderOutput:
        capability = AICapability.STRUCTURED if structured else AICapability.TEXT
        self._require(capability)
        try:
            from google.genai import types
        except ImportError as exc:
            raise ProviderUnavailable(self.name, "google-genai er ikke installeret") from exc

        config_kwargs: dict[str, Any] = {
            "temperature": 0.1,
            "max_output_tokens": 4096,
        }
        if structured:
            config_kwargs["response_mime_type"] = "application/json"

        started = time.monotonic()
        try:
            response = self.service._generate_content_with_retry(
                contents=[prompt],
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            raise ProviderUnavailable(self.name, _safe_provider_failure(exc)) from exc

        content = str(response.text or "")
        data = _json_payload(content) if structured else None
        return ProviderOutput(
            provider=self.name,
            model=self.model,
            capability=capability,
            duration_ms=int((time.monotonic() - started) * 1000),
            content=content,
            data=data,
            raw_response=content,
            metadata={
                "execution": "cloud",
                "vertex": bool(getattr(self.service, "is_vertex", False)),
                "location": getattr(self.service, "location", None),
            },
        )

    def generate_text(self, prompt: str, **kwargs) -> ProviderOutput:
        return self._generate(prompt, structured=False)

    def generate_structured(self, prompt: str, **kwargs) -> ProviderOutput:
        return self._generate(prompt, structured=True)
