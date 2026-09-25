"""Authoritative capability router for TimeLapse AI.

The router owns provider selection and fallback. Product code asks for a
capability/function and remains provider-agnostic. Existing image strategy names
are translated here as a compatibility policy; they are not provider calls.
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable

from ai.provider_contract import (
    AICapability,
    NoEligibleProvider,
    ProviderOutput,
    ProviderUnavailable,
)
from ai.provider_adapters import (
    AppleFoundationProvider,
    GeminiProvider,
    OllamaProvider,
)

log = logging.getLogger(__name__)

KNOWN_PROVIDERS = ("apple", "ollama", "gemini")

DEFAULT_FUNCTION_PROVIDER_ORDER: dict[str, tuple[str, ...]] = {
    # Preserve current production behaviour until an admin explicitly changes it.
    "search": ("ollama",),
    "siem": ("ollama",),
    "aiops": ("ollama",),
    "cmdb": ("ollama",),
    "summarization": ("ollama",),
}

IMAGE_STRATEGY_POLICY: dict[str, tuple[str | None, str | None]] = {
    "technical_only": (None, None),
    "local_only": ("ollama", None),
    "cloud_only": ("gemini", None),
    "apple_only": ("apple", None),
    "local_then_cloud": ("ollama", "gemini"),
}


_OLLAMA_VISION_LOCK = threading.Lock()


@dataclass(frozen=True)
class RoutedImageResult:
    result: Any
    provider: str
    execution: str


@dataclass(frozen=True)
class ImageProviderPlan:
    strategy: str
    primary: str | None
    escalation: str | None

    @property
    def enabled(self) -> bool:
        return bool(self.primary)


def _safe_function_name(function: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", str(function or "").lower()).strip("_")
    return value or "default"


def _parse_provider_order(value: str | None, fallback: Iterable[str]) -> tuple[str, ...]:
    requested = [
        item.strip().lower()
        for item in str(value or "").split(",")
        if item.strip()
    ]
    ordered: list[str] = []
    for name in requested or list(fallback):
        if name in KNOWN_PROVIDERS and name not in ordered:
            ordered.append(name)
    return tuple(ordered)


def generate_structured_data(
    get_db_fn: Callable,
    *,
    function: str,
    prompt: str,
) -> dict[str, Any] | None:
    """Provider-neutral structured generation for product entrypoints.

    Trusted TimeLapse provenance is attached after provider parsing, so model
    output cannot spoof the provider/model/capability identity.
    """
    try:
        output = CapabilityRouter(get_db_fn).generate_structured(
            function=function,
            prompt=prompt,
        )
    except Exception as exc:
        log.warning(
            "AI capability analyse fejlede: function=%s error=%s",
            function,
            type(exc).__name__,
        )
        return None
    if not isinstance(output.data, dict):
        return None
    data = dict(output.data)
    data["_timelapse_provider"] = output.provenance()
    return data


class CapabilityRouter:
    def __init__(self, get_db_fn: Callable | None = None):
        if get_db_fn is None:
            from database import get_db
            get_db_fn = get_db
        self._get_db = get_db_fn

    def image_plan(self, strategy: str) -> ImageProviderPlan:
        primary, escalation = IMAGE_STRATEGY_POLICY.get(
            str(strategy or ""),
            IMAGE_STRATEGY_POLICY["cloud_only"],
        )
        return ImageProviderPlan(
            strategy=str(strategy or "cloud_only"),
            primary=primary,
            escalation=escalation,
        )

    def image_runtime_deferred(self, plan: ImageProviderPlan) -> bool:
        """Return True when the configured primary runtime is intentionally paused.

        This preserves the existing Open WebUI/Ollama resource-control contract
        without exposing Ollama checks to product business logic.
        """
        if plan.primary != "ollama":
            return False
        try:
            from ai.ollama_runtime_control import runtime_is_paused
            db_gen = self._get_db()
            db = next(db_gen)
            try:
                return bool(runtime_is_paused(db))
            finally:
                db_gen.close()
        except Exception:
            return False

    def analyse_image_plan(
        self,
        *,
        plan: ImageProviderPlan,
        phase: str,
        image_path,
        vocabulary_full: dict[str, list[str]],
        vocabulary_local: dict[str, list[str]],
        approved_tag_set: set[str],
        context_block: str = "",
        reference_image_path=None,
        local_model: str | None = None,
        cloud_model: str | None = None,
    ) -> RoutedImageResult:
        if phase not in {"primary", "escalation"}:
            raise ValueError("phase skal være primary eller escalation")
        provider_name = plan.primary if phase == "primary" else plan.escalation
        if not provider_name:
            raise ProviderUnavailable("none", f"ingen {phase} image-provider konfigureret")
        vocabulary = vocabulary_local if provider_name == "ollama" else vocabulary_full
        result = self.analyse_image(
            provider_name=provider_name,
            image_path=image_path,
            vocabulary_by_cat=vocabulary,
            approved_tag_set=approved_tag_set,
            reference_image_path=reference_image_path,
            context_block=context_block,
            local_model=local_model,
            cloud_model=cloud_model,
            function="image",
        )
        execution = "cloud" if provider_name == "gemini" else "local"
        return RoutedImageResult(
            result=result,
            provider=provider_name,
            execution=execution,
        )

    def provider_order(self, function: str) -> tuple[str, ...]:
        from ai.settings_helper import get_setting

        function_name = _safe_function_name(function)
        fallback = DEFAULT_FUNCTION_PROVIDER_ORDER.get(function_name, ("ollama",))
        db_gen = self._get_db()
        db = next(db_gen)
        try:
            configured = get_setting(
                db,
                f"ai_provider_{function_name}_order",
                ",".join(fallback),
            )
        finally:
            db_gen.close()
        return _parse_provider_order(configured, fallback)

    def _provider(
        self,
        name: str,
        *,
        vision_model: str | None = None,
        cloud_model: str | None = None,
    ):
        from ai.provider_config import build_gemini_vision_service_from_db
        from ai.settings_helper import get_setting

        provider_name = str(name or "").lower()
        if provider_name not in KNOWN_PROVIDERS:
            raise ProviderUnavailable(provider_name or "unknown", "ukendt provider")

        db_gen = self._get_db()
        db = next(db_gen)
        try:
            if provider_name == "apple":
                timeout_s = int(get_setting(db, "apple_ai_timeout_s", "120"))
                temperature = float(get_setting(db, "apple_ai_temperature", "0.2"))
                return AppleFoundationProvider(
                    timeout_s=timeout_s,
                    temperature=temperature,
                )

            if provider_name == "ollama":
                return OllamaProvider(
                    base_url=get_setting(db, "ollama_url", "http://127.0.0.1:11434"),
                    vision_model=vision_model or get_setting(
                        db, "ollama_vision_model", "qwen2.5vl:7b"
                    ),
                    text_model=get_setting(db, "ollama_text_model", "llama3.2:latest"),
                    timeout_s=int(get_setting(db, "ollama_text_timeout_s", "90")),
                    num_predict=int(get_setting(db, "ollama_text_num_predict", "1800")),
                    temperature=float(get_setting(db, "ollama_text_temperature", "0.1")),
                    keep_alive_s=int(get_setting(db, "ollama_keep_alive_s", "30")),
                )

            selected_cloud_model = cloud_model or get_setting(
                db, "gemini_text_model", "gemini-3.8-flash"
            )
            service = build_gemini_vision_service_from_db(db, selected_cloud_model)
            if service is None:
                raise ProviderUnavailable("gemini", "credentials ikke konfigureret")
            return GeminiProvider(service)
        finally:
            db_gen.close()

    def provider_availability(
        self,
        provider_name: str,
        capability: AICapability,
        *,
        local_model: str | None = None,
        cloud_model: str | None = None,
    ) -> dict[str, Any]:
        """Probe one selected provider/capability without exposing credentials."""
        try:
            provider = self._provider(
                provider_name,
                vision_model=local_model,
                cloud_model=cloud_model,
            )
            return provider.availability(capability)
        except Exception as exc:
            return {
                "available": False,
                "reason": type(exc).__name__,
                "provider": provider_name,
            }

    def _attempts_error(
        self,
        capability: AICapability,
        attempts: list[dict[str, str]],
    ) -> NoEligibleProvider:
        return NoEligibleProvider(capability, attempts)

    def generate_structured(
        self,
        *,
        function: str,
        prompt: str,
        provider_order: Iterable[str] | None = None,
        model: str | None = None,
    ) -> ProviderOutput:
        order = tuple(provider_order or self.provider_order(function))
        attempts: list[dict[str, str]] = []
        for provider_name in order:
            try:
                provider = self._provider(provider_name, cloud_model=model)
                if not provider.supports(AICapability.STRUCTURED):
                    raise ProviderUnavailable(provider_name, "structured understøttes ikke")
                output = provider.generate_structured(prompt, model=model)
                return replace(
                    output,
                    metadata={
                        **output.metadata,
                        "function": _safe_function_name(function),
                        "provider_order": list(order),
                    },
                )
            except Exception as exc:
                attempts.append({
                    "provider": provider_name,
                    "error_type": type(exc).__name__,
                })
                log.warning(
                    "AI capability fallback: function=%s capability=structured provider=%s error=%s",
                    function,
                    provider_name,
                    type(exc).__name__,
                )
        raise self._attempts_error(AICapability.STRUCTURED, attempts)

    def generate_text(
        self,
        *,
        function: str,
        prompt: str,
        provider_order: Iterable[str] | None = None,
        model: str | None = None,
    ) -> ProviderOutput:
        order = tuple(provider_order or self.provider_order(function))
        attempts: list[dict[str, str]] = []
        for provider_name in order:
            try:
                provider = self._provider(provider_name, cloud_model=model)
                if not provider.supports(AICapability.TEXT):
                    raise ProviderUnavailable(provider_name, "text understøttes ikke")
                output = provider.generate_text(prompt, model=model)
                return replace(
                    output,
                    metadata={
                        **output.metadata,
                        "function": _safe_function_name(function),
                        "provider_order": list(order),
                    },
                )
            except Exception as exc:
                attempts.append({
                    "provider": provider_name,
                    "error_type": type(exc).__name__,
                })
                log.warning(
                    "AI capability fallback: function=%s capability=text provider=%s error=%s",
                    function,
                    provider_name,
                    type(exc).__name__,
                )
        raise self._attempts_error(AICapability.TEXT, attempts)

    def analyse_image(
        self,
        *,
        provider_name: str,
        image_path,
        vocabulary_by_cat: dict[str, list[str]],
        approved_tag_set: set[str],
        reference_image_path=None,
        prompt_examples: list[str] | None = None,
        context_block: str = "",
        local_model: str | None = None,
        cloud_model: str | None = None,
        function: str = "image",
    ):
        provider = self._provider(
            provider_name,
            vision_model=local_model,
            cloud_model=cloud_model,
        )
        if not provider.supports(AICapability.VISION):
            raise ProviderUnavailable(provider_name, "vision understøttes ikke")
        call = lambda: provider.analyse_image(
            image_path=image_path,
            vocabulary_by_cat=vocabulary_by_cat,
            approved_tag_set=approved_tag_set,
            reference_image_path=reference_image_path,
            prompt_examples=prompt_examples,
            context_block=context_block,
            model=local_model if provider_name == "ollama" else cloud_model,
        )
        if provider_name == "ollama":
            with _OLLAMA_VISION_LOCK:
                result = call()
        else:
            result = call()
        raw = getattr(result, "raw_response", None)
        if isinstance(raw, dict):
            raw.setdefault("router", {
                "function": _safe_function_name(function),
                "capability": AICapability.VISION.value,
                "provider": provider_name,
            })
        return result

    def image_batch_info(
        self,
        *,
        provider_name: str,
        cloud_model: str | None = None,
    ) -> dict[str, Any]:
        provider = self._provider(provider_name, cloud_model=cloud_model)
        if not hasattr(provider, "batch_info"):
            raise ProviderUnavailable(provider_name, "batch vision transport understøttes ikke")
        return provider.batch_info()

    def submit_image_batch(
        self,
        *,
        provider_name: str,
        items,
        vocabulary_by_cat: dict[str, list[str]],
        display_name: str,
        gcs_bucket: str = "",
        bucket_region: str = "",
        context_by_key: dict[str, str] | None = None,
        cloud_model: str | None = None,
    ):
        provider = self._provider(provider_name, cloud_model=cloud_model)
        if not hasattr(provider, "submit_image_batch"):
            raise ProviderUnavailable(provider_name, "batch vision transport understøttes ikke")
        return provider.submit_image_batch(
            items=items,
            vocabulary_by_cat=vocabulary_by_cat,
            display_name=display_name,
            gcs_bucket=gcs_bucket,
            bucket_region=bucket_region,
            context_by_key=context_by_key or {},
        )

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        providers: dict[str, Any] = {}
        for name in KNOWN_PROVIDERS:
            try:
                provider = self._provider(name)
                item = {
                    "configured": True,
                    "capabilities": sorted(cap.value for cap in provider.capabilities),
                }
                if probe:
                    probe_cap = (
                        AICapability.VISION
                        if provider.supports(AICapability.VISION)
                        else AICapability.TEXT
                    )
                    item["availability"] = provider.availability(probe_cap)
                providers[name] = item
            except Exception as exc:
                providers[name] = {
                    "configured": False,
                    "capabilities": [],
                    "error_type": type(exc).__name__,
                }

        policies = {
            function: list(self.provider_order(function))
            for function in DEFAULT_FUNCTION_PROVIDER_ORDER
        }
        return {
            "providers": providers,
            "policies": policies,
            "image_strategies": {
                key: {"primary": value[0], "escalation": value[1]}
                for key, value in IMAGE_STRATEGY_POLICY.items()
            },
        }
