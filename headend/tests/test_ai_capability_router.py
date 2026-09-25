from __future__ import annotations

from pathlib import Path

import pytest

from ai.capability_router import (
    CapabilityRouter,
    DEFAULT_FUNCTION_PROVIDER_ORDER,
)
from ai.provider_adapters import GeminiProvider
from ai.provider_config import resolve_gemini_location
from ai.provider_contract import (
    AICapability,
    NoEligibleProvider,
    ProviderOutput,
    ProviderUnavailable,
)


HEADEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = HEADEND_DIR.parent


class _FakeStructuredProvider:
    capabilities = frozenset({AICapability.STRUCTURED})

    def __init__(self, name: str, *, fail: bool = False):
        self.name = name
        self.fail = fail

    def supports(self, capability: AICapability) -> bool:
        return capability in self.capabilities

    def generate_structured(self, prompt: str, **_kwargs) -> ProviderOutput:
        if self.fail:
            raise ProviderUnavailable(self.name, "test-unavailable")
        return ProviderOutput(
            provider=self.name,
            model=f"{self.name}-model",
            capability=AICapability.STRUCTURED,
            duration_ms=7,
            content='{"ok": true}',
            data={"ok": True},
            raw_response='{"ok": true}',
            metadata={"execution": "test"},
        )


def test_legacy_image_strategies_translate_only_in_router():
    router = CapabilityRouter(lambda: iter(()))

    assert router.image_plan("technical_only").primary is None
    assert router.image_plan("local_only").primary == "ollama"
    assert router.image_plan("cloud_only").primary == "gemini"
    assert router.image_plan("apple_only").primary == "apple"

    local_cloud = router.image_plan("local_then_cloud")
    assert local_cloud.primary == "ollama"
    assert local_cloud.escalation == "gemini"


def test_function_defaults_preserve_existing_ollama_behaviour():
    assert DEFAULT_FUNCTION_PROVIDER_ORDER == {
        "search": ("ollama",),
        "siem": ("ollama",),
        "aiops": ("ollama",),
        "cmdb": ("ollama",),
        "summarization": ("ollama",),
    }


def test_structured_capability_falls_back_in_declared_order(monkeypatch):
    router = CapabilityRouter(lambda: iter(()))
    providers = {
        "apple": _FakeStructuredProvider("apple", fail=True),
        "ollama": _FakeStructuredProvider("ollama"),
    }
    monkeypatch.setattr(
        router,
        "_provider",
        lambda name, **_kwargs: providers[name],
    )

    output = router.generate_structured(
        function="search",
        prompt="test",
        provider_order=("apple", "ollama"),
    )

    assert output.provider == "ollama"
    assert output.data == {"ok": True}
    assert output.metadata["function"] == "search"
    assert output.metadata["provider_order"] == ["apple", "ollama"]


def test_structured_capability_fails_closed_when_no_provider_succeeds(monkeypatch):
    router = CapabilityRouter(lambda: iter(()))
    monkeypatch.setattr(
        router,
        "_provider",
        lambda name, **_kwargs: _FakeStructuredProvider(name, fail=True),
    )

    with pytest.raises(NoEligibleProvider) as exc:
        router.generate_structured(
            function="siem",
            prompt="test",
            provider_order=("apple", "ollama"),
        )

    assert exc.value.capability == AICapability.STRUCTURED
    assert [item["provider"] for item in exc.value.attempts] == ["apple", "ollama"]


def test_product_entrypoints_use_capability_router_not_vendor_clients():
    main = (HEADEND_DIR / "main.py").read_text(encoding="utf-8")
    integration = (HEADEND_DIR / "ai" / "integration.py").read_text(encoding="utf-8")
    text_services = (HEADEND_DIR / "ai" / "text_services.py").read_text(encoding="utf-8")
    review_api = (HEADEND_DIR / "ai" / "review_api.py").read_text(encoding="utf-8")

    assert "from ai.capability_router import generate_structured_data" in main
    assert "_call_ollama_text" not in main
    assert "def _capture_spec_from_ai(" in main
    assert "_capture_spec_from_ollama" not in main

    worker = integration[
        integration.index("def _worker("):
        integration.index("def queue_capture_for_analysis")
    ]
    assert "CapabilityRouter" in worker
    assert "AppleFoundationVisionService(" not in worker
    assert "GeminiVisionService(" not in worker
    assert "OllamaVisionService(" not in worker

    manual = integration[
        integration.index('@ai_router.post("/analyze/{capture_id}")'):
        integration.index('@ai_router.get("/result/{capture_id}")')
    ]
    assert "CapabilityRouter" in manual
    assert "OllamaVisionService(" not in manual
    assert "GeminiVisionService(" not in manual
    assert "AppleFoundationVisionService(" not in manual

    assert "CapabilityRouter" in text_services
    assert "/api/generate" not in text_services
    assert "GeminiVisionService(" not in review_api


def test_bulk_analysis_paths_use_capability_router():
    backfill = (HEADEND_DIR / "ai" / "backfill.py").read_text(encoding="utf-8")
    batch = (HEADEND_DIR / "ai" / "ai_batch_submit.py").read_text(encoding="utf-8")

    for source in (backfill, batch):
        assert "CapabilityRouter" in source
        assert "GeminiVisionService(" not in source
        assert "OllamaVisionService(" not in source
        assert "AppleFoundationVisionService(" not in source

    assert "submit_image_batch(" in batch
    assert "analyse_image_plan(" in backfill


def test_deterministic_siem_stays_independent_of_model_router():
    deterministic_siem = (HEADEND_DIR / "siem.py").read_text(encoding="utf-8")
    ai_text = (HEADEND_DIR / "ai" / "text_services.py").read_text(encoding="utf-8")

    assert "ai.capability_router" not in deterministic_siem
    assert "CapabilityRouter" in ai_text


def test_natural_search_keeps_tenant_filter_outside_model():
    main = (HEADEND_DIR / "main.py").read_text(encoding="utf-8")
    endpoint = main[
        main.index('@app.post("/api/ai/captures/natural-search")'):
        main.index("@app.", main.index('@app.post("/api/ai/captures/natural-search")') + 10)
    ]

    assert "_capture_spec_from_ai" in endpoint
    assert "_capture_is_allowed" in endpoint
    assert "CapabilityRouter" not in endpoint
    # Provider receives a prompt and returns a safe filter spec; DB access remains
    # in TimeLapse product code after authentication/tenant scoping.
    assert "_query_capture_candidates" in endpoint


def test_provider_policy_is_admin_managed_and_allowlisted():
    settings = (HEADEND_DIR / "ai" / "settings_api.py").read_text(encoding="utf-8")

    assert "ai_provider_search_order" in settings
    assert "ai_provider_siem_order" in settings
    assert "ai_provider_aiops_order" in settings
    assert "ai_provider_cmdb_order" in settings
    assert "KNOWN_PROVIDERS" in settings
    assert '@settings_router.get("/ai-providers")' in settings


def test_capability_smoke_tool_uses_authoritative_router():
    smoke = (HEADEND_DIR / "tools" / "smoke_ai_capabilities.py").read_text(encoding="utf-8")

    assert "CapabilityRouter(get_db)" in smoke
    assert "generate_text(" in smoke
    assert "generate_structured(" in smoke
    assert "GeminiVisionService(" not in smoke
    assert "OllamaVisionService(" not in smoke
    assert "AppleFoundationVisionService(" not in smoke


def test_gemini_availability_probe_performs_remote_generation():
    class Response:
        text = "TIMELAPSE_OK"

    class HealthyService:
        model = "gemini-test"

        def __init__(self):
            self.called = False

        def _generate_content_with_retry(self, contents, config):
            self.called = True
            assert contents == ["Reply exactly: TIMELAPSE_OK"]
            return Response()

    service = HealthyService()
    status = GeminiProvider(service).availability(AICapability.STRUCTURED)

    assert service.called is True
    assert status["available"] is True
    assert status["reason"] is None


def test_gemini_availability_probe_fails_closed_with_safe_reason():
    class BrokenService:
        model = "gemini-test"

        def _generate_content_with_retry(self, contents, config):
            raise RuntimeError("404 publisher model not found in location europe-west1")

    status = GeminiProvider(BrokenService()).availability(AICapability.TEXT)

    assert status["available"] is False
    assert status["reason"] == "model_or_endpoint_not_found"


def test_gemini_38_region_resolution_preserves_residency_family():
    assert resolve_gemini_location("gemini-3.8-flash", "europe-west1") == "eu"
    assert resolve_gemini_location("gemini-3.8-flash", "europe-north1") == "eu"
    assert resolve_gemini_location("gemini-3.8-flash", "us-central1") == "us"
    assert resolve_gemini_location("gemini-3.8-flash", "eu") == "eu"


def test_gemini_region_resolution_does_not_rewrite_legacy_or_unknown_regions():
    assert resolve_gemini_location("gemini-2.5-flash", "europe-west1") == "europe-west1"
    assert resolve_gemini_location("gemini-3.8-flash", "asia-northeast1") == "asia-northeast1"


def test_gemini_runtime_settings_separate_text_region_from_vision_region():
    settings = (HEADEND_DIR / "ai" / "settings_api.py").read_text(encoding="utf-8")

    assert '"gemini_location"' in settings
    assert '"gemini_text_location"' in settings
    assert '"default": "eu"' in settings
    assert 'payload.get("cloud_model", "gemini-3.8-flash")' in settings


def test_capability_smoke_reports_safe_provider_attempts():
    smoke = (HEADEND_DIR / "tools" / "smoke_ai_capabilities.py").read_text(encoding="utf-8")
    router = (HEADEND_DIR / "ai" / "capability_router.py").read_text(encoding="utf-8")

    assert 'row["attempts"] = exc.attempts' in smoke
    assert 'attempt["reason"] = exc.reason' in router
