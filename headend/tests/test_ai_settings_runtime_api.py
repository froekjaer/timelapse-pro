from ai import settings_api
from ai.ollama_service import OllamaVisionService


def test_ai_runtime_returns_all_declared_fields(monkeypatch):
    monkeypatch.setattr(
        settings_api,
        "get_setting",
        lambda _db, _key, default: default,
    )
    monkeypatch.setattr(OllamaVisionService, "list_models", lambda _self: ["qwen3-vl:8b"])

    result = settings_api.get_ai_runtime(_user=object(), db=object())

    assert {field["key"] for field in result["fields"]} == set(settings_api.AI_RUNTIME_FIELDS)
    keep_alive = next(field for field in result["fields"] if field["key"] == "ollama_keep_alive_s")
    assert keep_alive["default"] == "30"
    assert keep_alive["min"] == 0
    assert result["installed_models"] == ["qwen3-vl:8b"]
