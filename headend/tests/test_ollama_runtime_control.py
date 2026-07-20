from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai import ollama_runtime_control as control
from ai import ollama_service
from ai import settings_api


def test_pause_stops_service_and_persists_expiry(monkeypatch):
    stopped = []
    written = []
    monkeypatch.setattr(control, "service_status", lambda: {
        "service_running": True, "service_loaded": True,
    })
    monkeypatch.setattr(control, "stop_service", lambda: stopped.append(True))
    monkeypatch.setattr(control, "_write_state", lambda _db, **values: written.append(values))
    monkeypatch.setattr(control, "get_runtime_status", lambda _db, reconcile=False: {"mode": "paused"})

    result = control.set_control_mode(
        object(), mode="paused", duration_minutes=90,
        low_memory_model="llava-phi3:latest", updated_by="codex",
    )

    assert result == {"mode": "paused"}
    assert stopped == [True]
    assert written[0]["resume_service"] is True
    assert written[0]["mode"] == "paused"
    assert 89 * 60 <= (written[0]["until"] - control.utc_now()).total_seconds() <= 90 * 60


def test_low_memory_mode_accepts_only_installed_vision_model(monkeypatch):
    actions = []
    monkeypatch.setattr(control, "service_status", lambda: {"service_running": True})
    monkeypatch.setattr(control, "start_service", lambda: actions.append("start"))
    monkeypatch.setattr(control, "unload_models", lambda: actions.append("unload") or [])
    monkeypatch.setattr(control, "list_installed_models", lambda _db: [
        {"name": "llava-phi3:latest", "size": 3_000_000_000, "family": "llama", "families": ["llama", "clip"]},
        {"name": "llama3.2:latest", "size": 2_000_000_000, "family": "llama", "families": ["llama"]},
        {"name": "qwen3-vl:8b", "size": 6_000_000_000, "family": "qwen3vl", "families": ["qwen3vl"]},
    ])
    monkeypatch.setattr(control, "_write_state", lambda _db, **values: actions.append(values["mode"]))
    monkeypatch.setattr(control, "get_runtime_status", lambda _db, reconcile=False: {"mode": "low_memory"})

    assert control.set_control_mode(
        object(), mode="low_memory", duration_minutes=60,
        low_memory_model="llava-phi3:latest", updated_by="codex",
    )["mode"] == "low_memory"
    assert actions == ["start", "unload", "low_memory"]

    with pytest.raises(ValueError, match="visionmodel"):
        control.set_control_mode(
            object(), mode="low_memory", duration_minutes=60,
            low_memory_model="llama3.2:latest", updated_by="codex",
        )

    with pytest.raises(ValueError, match="under 4 GB"):
        control.set_control_mode(
            object(), mode="low_memory", duration_minutes=60,
            low_memory_model="qwen3-vl:8b", updated_by="codex",
        )


def test_runtime_model_override_is_temporary_and_fail_closed(monkeypatch):
    fake_db = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr("database.SessionLocal", lambda: fake_db)
    monkeypatch.setattr(control, "_read_state", lambda _db: {
        "mode": "low_memory",
        "until": control.utc_now() + timedelta(minutes=30),
        "low_memory_model": "llava-phi3:latest",
        "resume_service": True,
    })

    assert control.vision_model_override("qwen2.5vl:7b") == ("llava-phi3:latest", True)

    monkeypatch.setattr(control, "_read_state", lambda _db: {
        "mode": "paused",
        "until": control.utc_now() + timedelta(minutes=30),
        "low_memory_model": "llava-phi3:latest",
        "resume_service": True,
    })
    with pytest.raises(control.OllamaRuntimePaused):
        control.vision_model_override("qwen2.5vl:7b")


def test_low_memory_profile_cannot_fallback_to_large_model(monkeypatch):
    monkeypatch.setattr(
        control,
        "vision_model_override",
        lambda _configured: ("llava-phi3:latest", True),
    )
    monkeypatch.setattr(ollama_service, "_db_setting", lambda _key, default: default)
    monkeypatch.setattr(ollama_service, "_db_int", lambda _key, default: default)
    monkeypatch.setattr(ollama_service, "_db_float", lambda _key, default: default)

    service = ollama_service.OllamaVisionService(
        vision_model="qwen2.5vl:7b",
        fallback_models=["qwen3-vl:8b"],
    )
    try:
        assert service.vision_model == "llava-phi3:latest"
        assert service.runtime_low_memory is True
        assert service.fallback_models == []
        assert service.max_image_edge <= 768
        assert service.max_image_bytes <= 900_000
        assert service.vision_num_ctx <= 4096
        assert service.vision_num_predict <= 512
    finally:
        service._client.close()


def test_expired_pause_restarts_previous_service(monkeypatch):
    actions = []
    state = {
        "mode": "paused",
        "until": control.utc_now() - timedelta(seconds=1),
        "low_memory_model": "llava-phi3:latest",
        "resume_service": True,
    }
    monkeypatch.setattr(control, "_read_state", lambda _db: state)
    monkeypatch.setattr(control, "start_service", lambda: actions.append("start"))
    monkeypatch.setattr(control, "_write_state", lambda _db, **values: actions.append(values["mode"]))

    control._restore_expired(object(), state)

    assert actions == ["start", "normal"]


def test_settings_api_exposes_audited_runtime_control(monkeypatch):
    expected = {"mode": "paused", "until": "2026-07-21T01:00:00+00:00"}
    monkeypatch.setattr(control, "set_control_mode", lambda *_args, **_kwargs: dict(expected))
    monkeypatch.setattr(settings_api, "_audit_ollama_control", lambda *_args: None)
    monkeypatch.setattr(settings_api, "get_setting", lambda _db, key, default: {
        "ollama_vision_model": "qwen2.5vl:7b",
        "ollama_text_model": "llama3.2:latest",
    }.get(key, default))

    result = settings_api.update_ollama_runtime_control(
        settings_api.OllamaRuntimeControlUpdate(
            mode="paused", duration_minutes=60, low_memory_model="llava-phi3:latest",
        ),
        user=SimpleNamespace(username="codex"), db=object(),
    )

    assert result["mode"] == "paused"
    assert result["configured_vision_model"] == "qwen2.5vl:7b"


def test_ai_ui_contains_pause_low_memory_and_resume_controls():
    source = (Path(__file__).parents[2] / "timelapse-ui/src/pages/AIPage.tsx").read_text()
    assert "/api/settings/ollama-runtime-control" in source
    assert "Ollama memory-styring" in source
    assert "Brug lav-memory" in source
    assert "Normal drift" in source
    assert "Varighed i minutter" in source
