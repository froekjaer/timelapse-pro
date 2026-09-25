from ai.ai_strategy import AIConfig, GLOBAL_DEFAULTS, VALID_STRATEGIES
from ai.apple_foundation_service import APPLE_MODEL_NAME, AppleFoundationVisionService
from ai.model_results import ENGINE_APPLE_FOUNDATION, engine_from_legacy_payload


def test_apple_strategy_is_declared():
    assert "apple_only" in VALID_STRATEGIES


def test_apple_strategy_does_not_claim_gemini_or_ollama():
    config = AIConfig(
        strategy="apple_only",
        local_model="qwen2.5vl:7b",
        cloud_model="gemini-3.8-flash",
        escalation_threshold=0.7,
        escalation_new_tags=4,
        always_escalate_tags=[],
        always_cloud_tags=[],
        tag_vocabulary_limit=80,
        enabled=True,
    )
    assert config.use_local is False
    assert config.use_cloud is False
    assert config.local_first is False


def test_gemini_default_has_moved_off_2_5():
    assert GLOBAL_DEFAULTS["cloud_model"] == "gemini-3.8-flash"


def test_apple_engine_provenance_is_separate_from_ollama():
    assert engine_from_legacy_payload(
        {"engine": "apple", "model": APPLE_MODEL_NAME}
    ) == ENGINE_APPLE_FOUNDATION


def test_apple_provider_is_constructible_without_importing_sdk():
    # Non-macOS CI must be able to import/configure Headend even though the
    # Apple SDK dependency is Darwin-only. Runtime availability is lazy.
    provider = AppleFoundationVisionService()
    assert provider.timeout_s > 0
