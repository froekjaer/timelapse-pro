from ai.ai_strategy import AIConfig, VALID_STRATEGIES
from ai.apple_foundation_service import AppleFoundationVisionService
from ai.model_results import ENGINE_APPLE_FOUNDATION, engine_from_legacy_payload


def test_apple_strategy_is_declared():
    assert "apple_only" in VALID_STRATEGIES


def test_apple_strategy_does_not_claim_gemini_or_ollama():
    config = AIConfig(
        strategy="apple_only",
        local_model="qwen2.5vl:7b",
        cloud_model="gemini-2.5-flash",
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


def test_apple_response_parser_accepts_plain_json():
    parsed = AppleFoundationVisionService._parse_json(
        '{"scene":"test","tags":["road"],"new_tags":[]}'
    )
    assert parsed["scene"] == "test"
    assert parsed["tags"] == ["road"]


def test_apple_response_parser_accepts_fenced_json():
    parsed = AppleFoundationVisionService._parse_json(
        'prefix\n' + chr(96) * 3 + 'json\n{"scene":"test","tags":[]}\n' + chr(96) * 3
    )
    assert parsed["scene"] == "test"


def test_apple_engine_provenance_is_separate_from_ollama():
    assert engine_from_legacy_payload(
        {"engine": "apple", "model": "apple-foundation-model-on-device"}
    ) == ENGINE_APPLE_FOUNDATION
