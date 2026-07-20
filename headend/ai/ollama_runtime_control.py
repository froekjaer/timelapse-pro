"""Auditable, time-limited runtime control for the local Ollama service."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import bindparam, text


log = logging.getLogger(__name__)

LABEL = "homebrew.mxcl.ollama"
MODE_KEY = "ollama_runtime_control_mode"
UNTIL_KEY = "ollama_runtime_control_until"
LOW_MODEL_KEY = "ollama_runtime_low_memory_model"
RESUME_SERVICE_KEY = "ollama_runtime_resume_service"
MODEL_CACHE_KEY = "ollama_installed_models_cache"

VALID_MODES = {"normal", "paused", "low_memory"}
MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 24 * 60
DEFAULT_LOW_MEMORY_MODEL = "llava-phi3:latest"
MAX_LOW_MEMORY_MODEL_BYTES = 4 * 1024 ** 3

_lock = threading.RLock()
_monitor_started = False


class OllamaRuntimePaused(RuntimeError):
    """Raised before a local inference request while Ollama is paused."""


def _get_value(db, key: str, default: str = "") -> str:
    row = db.execute(
        text("SELECT value FROM system_settings WHERE key = :key"),
        {"key": key},
    ).fetchone()
    return str(row[0]) if row and row[0] not in (None, "") else default


def _set_value(db, key: str, value: str, updated_by: str) -> None:
    db.execute(text("""
        INSERT INTO system_settings (key, value, updated_by, updated_at)
        VALUES (:key, :value, :updated_by, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_by = EXCLUDED.updated_by,
            updated_at = NOW()
    """), {"key": key, "value": value, "updated_by": updated_by})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _target() -> str:
    return f"gui/{os.getuid()}/{LABEL}"


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _launchctl(*args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["/bin/launchctl", *args], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"launchctl kunne ikke køres: {exc}") from exc


def _http_json(path: str, *, timeout: float = 3) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:11434{path}", timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def service_status() -> dict:
    try:
        result = _launchctl("print", _target())
        output = f"{result.stdout}\n{result.stderr}"
        loaded = result.returncode == 0
        running = loaded and "state = running" in output
        pid = None
        for line in output.splitlines():
            if line.strip().startswith("pid ="):
                try:
                    pid = int(line.split("=", 1)[1].strip())
                except ValueError:
                    pass
                break
    except RuntimeError:
        loaded, running, pid = False, False, None

    loaded_models: list[dict] = []
    api_healthy = False
    if running:
        try:
            loaded_models = _http_json("/api/ps").get("models", [])
            api_healthy = True
        except Exception:
            pass
    loaded_bytes = sum(int(model.get("size_vram") or model.get("size") or 0) for model in loaded_models)
    return {
        "service_loaded": loaded,
        "service_running": running,
        "api_healthy": api_healthy,
        "pid": pid,
        "loaded_models": [model.get("name") or model.get("model") for model in loaded_models],
        "loaded_memory_gb": round(loaded_bytes / (1024 ** 3), 2),
    }


def list_installed_models(db=None) -> list[dict]:
    try:
        models = _http_json("/api/tags", timeout=5).get("models", [])
        result = [{
            "name": str(model.get("name") or model.get("model") or ""),
            "size": int(model.get("size") or 0),
            "families": list((model.get("details") or {}).get("families") or []),
            "family": str((model.get("details") or {}).get("family") or ""),
        } for model in models if model.get("name") or model.get("model")]
        if db is not None and result:
            serialized = json.dumps(result, separators=(",", ":"), sort_keys=True)
            if _get_value(db, MODEL_CACHE_KEY, "") != serialized:
                _set_value(db, MODEL_CACHE_KEY, serialized, "runtime-control")
                db.commit()
        return result
    except Exception:
        if db is None:
            return []
        try:
            cached = json.loads(_get_value(db, MODEL_CACHE_KEY, "[]"))
            return cached if isinstance(cached, list) else []
        except Exception:
            return []


def _is_vision_model(model: dict) -> bool:
    families = {str(value).lower() for value in model.get("families") or []}
    family = str(model.get("family") or "").lower()
    name = str(model.get("name") or "").lower()
    return bool(
        families.intersection({"clip", "mllama", "qwen25vl", "qwen3vl"})
        or family in {"mllama", "qwen25vl", "qwen3vl"}
        or any(marker in name for marker in ("vision", "llava", "vl:", "minicpm-v"))
    )


def _is_low_memory_model(model: dict) -> bool:
    return _is_vision_model(model) and 0 < int(model.get("size") or 0) <= MAX_LOW_MEMORY_MODEL_BYTES


def unload_models() -> list[str]:
    try:
        from openwebui_runtime import unload_ollama_models
        return unload_ollama_models()
    except Exception as exc:
        log.warning("Ollama modeller kunne ikke frigives: %s", exc)
        return []


def stop_service() -> None:
    unload_models()
    status = service_status()
    if not status["service_loaded"]:
        return
    result = _launchctl("bootout", _target(), timeout=30)
    if result.returncode != 0 and "Could not find service" not in f"{result.stdout}{result.stderr}":
        raise RuntimeError((result.stderr or result.stdout or "Ollama stop fejlede").strip())


def start_service() -> None:
    status = service_status()
    if status["api_healthy"]:
        return
    if not status["service_loaded"]:
        plist = _plist_path()
        if not plist.exists():
            raise RuntimeError(f"Ollama LaunchAgent mangler: {plist}")
        result = _launchctl("bootstrap", f"gui/{os.getuid()}", str(plist), timeout=30)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Ollama bootstrap fejlede").strip())
    result = _launchctl("kickstart", _target(), timeout=30)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Ollama start fejlede").strip())
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if service_status()["api_healthy"]:
            return
        time.sleep(0.25)
    raise RuntimeError("Ollama startede, men API blev ikke klar inden for 12 sekunder")


def _parse_until(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _read_state(db) -> dict:
    keys = (MODE_KEY, UNTIL_KEY, LOW_MODEL_KEY, RESUME_SERVICE_KEY)
    statement = text(
        "SELECT key, value FROM system_settings WHERE key IN :keys"
    ).bindparams(bindparam("keys", expanding=True))
    rows = db.execute(statement, {"keys": keys}).fetchall()
    values = {str(row[0]): str(row[1] or "") for row in rows}
    mode = values.get(MODE_KEY, "normal")
    if mode not in VALID_MODES:
        mode = "normal"
    return {
        "mode": mode,
        "until": _parse_until(values.get(UNTIL_KEY, "")),
        "low_memory_model": values.get(LOW_MODEL_KEY) or DEFAULT_LOW_MEMORY_MODEL,
        "resume_service": values.get(RESUME_SERVICE_KEY, "true").lower() == "true",
    }


def _write_state(db, *, mode: str, until: datetime | None, low_memory_model: str,
                 resume_service: bool, updated_by: str) -> None:
    values = {
        MODE_KEY: mode,
        UNTIL_KEY: until.isoformat() if until else "",
        LOW_MODEL_KEY: low_memory_model,
        RESUME_SERVICE_KEY: "true" if resume_service else "false",
    }
    for key, value in values.items():
        _set_value(db, key, value, updated_by)
    db.commit()


def set_control_mode(db, *, mode: str, duration_minutes: int,
                     low_memory_model: str | None, updated_by: str) -> dict:
    if mode not in VALID_MODES:
        raise ValueError("Ukendt Ollama-driftstilstand")
    if mode != "normal" and not MIN_DURATION_MINUTES <= duration_minutes <= MAX_DURATION_MINUTES:
        raise ValueError(
            f"Varighed skal være mellem {MIN_DURATION_MINUTES} og {MAX_DURATION_MINUTES} minutter"
        )

    with _lock:
        previous = service_status()
        selected_model = (low_memory_model or DEFAULT_LOW_MEMORY_MODEL).strip()
        until = utc_now() + timedelta(minutes=duration_minutes) if mode != "normal" else None

        if mode == "paused":
            stop_service()
            _write_state(
                db, mode=mode, until=until, low_memory_model=selected_model,
                resume_service=previous["service_running"], updated_by=updated_by,
            )
        elif mode == "low_memory":
            start_service()
            installed = list_installed_models(db)
            low_memory_models = [model for model in installed if _is_low_memory_model(model)]
            if selected_model not in {model["name"] for model in low_memory_models}:
                raise ValueError("Den valgte model er ikke en installeret visionmodel under 4 GB")
            unload_models()
            _write_state(
                db, mode=mode, until=until, low_memory_model=selected_model,
                resume_service=True, updated_by=updated_by,
            )
        else:
            start_service()
            unload_models()
            _write_state(
                db, mode="normal", until=None, low_memory_model=selected_model,
                resume_service=True, updated_by=updated_by,
            )
        return get_runtime_status(db, reconcile=False)


def _restore_expired(db, state: dict) -> None:
    if state["mode"] == "paused" and state["resume_service"]:
        start_service()
    if state["mode"] == "low_memory":
        unload_models()
    _write_state(
        db, mode="normal", until=None, low_memory_model=state["low_memory_model"],
        resume_service=state["resume_service"], updated_by="runtime-monitor",
    )
    log.info("Ollama tidsbegrænset driftstilstand udløb; normal drift gendannet")


def _state_has_expired(state: dict, now: datetime | None = None) -> bool:
    if state["mode"] == "normal":
        return False
    return state["until"] is None or state["until"] <= (now or utc_now())


def get_runtime_status(db, *, reconcile: bool = True) -> dict:
    with _lock:
        state = _read_state(db)
        now = utc_now()
        if reconcile and _state_has_expired(state, now):
            _restore_expired(db, state)
            state = _read_state(db)
        installed = list_installed_models(db)
        vision_models = [model for model in installed if _is_vision_model(model)]
        low_memory_models = [model for model in installed if _is_low_memory_model(model)]
        remaining = None
        if state["until"]:
            remaining = max(0, int((state["until"] - now).total_seconds()))
        return {
            "mode": state["mode"],
            "until": state["until"].isoformat() if state["until"] else None,
            "remaining_seconds": remaining,
            "low_memory_model": state["low_memory_model"],
            "recommended_low_memory_model": DEFAULT_LOW_MEMORY_MODEL,
            "installed_models": installed,
            "vision_models": vision_models,
            "low_memory_models": low_memory_models,
            "service": service_status(),
        }


def vision_model_override(configured_model: str) -> tuple[str, bool]:
    """Return effective model and whether the low-memory limits must be used."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        state = _read_state(db)
        if _state_has_expired(state):
            _restore_expired(db, state)
            state = _read_state(db)
        if state["mode"] == "paused":
            raise OllamaRuntimePaused("Ollama er midlertidigt pauset fra AI Styring")
        if state["mode"] == "low_memory":
            return state["low_memory_model"], True
        return configured_model, False
    finally:
        db.close()


def runtime_is_paused(db) -> bool:
    state = _read_state(db)
    if _state_has_expired(state):
        _restore_expired(db, state)
        state = _read_state(db)
    return state["mode"] == "paused"


def _monitor_loop() -> None:
    from database import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                with _lock:
                    state = _read_state(db)
                    if _state_has_expired(state):
                        _restore_expired(db, state)
            finally:
                db.close()
        except Exception as exc:
            log.warning("Ollama runtime-monitor fejlede: %s", exc)
        time.sleep(5)


def start_runtime_monitor() -> None:
    global _monitor_started
    with _lock:
        if _monitor_started:
            return
        threading.Thread(
            target=_monitor_loop, name="ollama-runtime-monitor", daemon=True,
        ).start()
        _monitor_started = True
