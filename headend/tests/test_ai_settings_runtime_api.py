from ai import ollama_service, settings_api
from ai.ollama_service import OllamaVisionService


def test_ai_runtime_returns_all_declared_fields(monkeypatch):
    monkeypatch.setattr(
        settings_api,
        "get_setting",
        lambda _db, _key, default: default,
    )
    class _Db:
        def execute(self, _statement, _params):
            class _Result:
                @staticmethod
                def fetchone():
                    return None

            return _Result()

        def rollback(self):
            pass

    monkeypatch.setattr(OllamaVisionService, "list_models", lambda _self: ["qwen3-vl:8b"])

    result = settings_api.get_ai_runtime(_user=object(), db=_Db())

    assert {field["key"] for field in result["fields"]} == set(settings_api.AI_RUNTIME_FIELDS)
    keep_alive = next(field for field in result["fields"] if field["key"] == "ollama_keep_alive_s")
    assert keep_alive["default"] == "30"
    assert keep_alive["min"] == 0
    assert result["installed_models"] == ["qwen3-vl:8b"]


def test_ai_runtime_exposes_legacy_value_until_saved_canonically(monkeypatch):
    monkeypatch.setattr(settings_api, "get_setting", lambda _db, _key, _default: "")

    class _Db:
        def execute(self, _statement, params):
            value = "1536" if params["key"] == "ollama_max_image_edge" else None

            class _Result:
                @staticmethod
                def fetchone():
                    return (value,) if value else None

            return _Result()

        def rollback(self):
            pass

    value, source = settings_api._get_runtime_value(
        _Db(), "ollama_max_image_edge", settings_api.AI_RUNTIME_FIELDS["ollama_max_image_edge"]
    )

    assert value == "1536"
    assert source == "legacy_database"


def test_runtime_setting_prefers_canonical_system_settings(monkeypatch):
    class _Result:
        def __init__(self, value):
            self._value = value

        def fetchone(self):
            return (self._value,) if self._value is not None else None

    class _Db:
        def execute(self, statement, _params):
            table = str(statement).split("FROM ", 1)[1].split(" ", 1)[0]
            return _Result({
                "system_settings": "qwen2.5vl:7b",
                "settings": "qwen3-vl:8b",
            }[table])

        def close(self):
            pass

    monkeypatch.setattr("database.SessionLocal", lambda: _Db())

    assert ollama_service._db_setting("ollama_vision_model", "fallback") == "qwen2.5vl:7b"
