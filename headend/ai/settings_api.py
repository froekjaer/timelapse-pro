"""
TimeLapse Pro — Settings API endpoints
Tilføj til main.py: from ai.settings_api import settings_router; app.include_router(settings_router)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from ai.settings_helper import get_all_settings, set_setting

settings_router = APIRouter(prefix="/api/settings", tags=["settings"])


def _require_platform_admin(request: Request, db: Session = Depends(get_db)):
    from main import get_current_user, _is_platform_admin, _mfa_required_for_user, _session_is_mfa_verified, _session_payload
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if not _is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Kræver platformadministrator")
    if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
        raise HTTPException(status_code=403, detail="MFA kræves")
    return user

class SettingUpdate(BaseModel):
    value: str
    updated_by: str = "admin"


AI_RUNTIME_FIELDS = {
    "ollama_url": {"label": "Ollama URL", "type": "text", "default": "http://127.0.0.1:11434"},
    "ollama_vision_model": {"label": "Teknisk fallback vision-model", "type": "model", "default": "qwen3-vl:8b"},
    "ollama_text_model": {"label": "Tekst/AI Ops-model", "type": "model", "default": "llama3.2:latest"},
    "ollama_fallback_models": {"label": "Vision fallback-modeller", "type": "text", "default": "qwen2.5vl:7b"},
    "ollama_vision_timeout_s": {"label": "Vision timeout (sek.)", "type": "int", "default": "120", "min": 10, "max": 900},
    "ollama_max_image_bytes": {"label": "Maks. billedstørrelse (bytes)", "type": "int", "default": "1500000", "min": 100000, "max": 20000000},
    "ollama_max_image_edge": {"label": "Maks. billedkant (px)", "type": "int", "default": "1024", "min": 256, "max": 4096},
    "ollama_vision_num_ctx": {"label": "Vision context tokens", "type": "int", "default": "8192", "min": 1024, "max": 131072},
    "ollama_vision_num_predict": {"label": "Vision output tokens", "type": "int", "default": "768", "min": 128, "max": 8192},
    "ollama_vision_temperature": {"label": "Vision temperature", "type": "float", "default": "0.1", "min": 0, "max": 2},
    "ollama_vision_top_p": {"label": "Vision top-p", "type": "float", "default": "0.8", "min": 0, "max": 1},
    "ollama_vision_repeat_penalty": {"label": "Vision repeat penalty", "type": "float", "default": "1.18", "min": 0.5, "max": 2},
    "ollama_max_prompt_tags": {"label": "Maks. tags i prompt", "type": "int", "default": "100", "min": 10, "max": 1000},
    "ollama_max_prompt_tags_per_category": {"label": "Maks. tags pr. kategori", "type": "int", "default": "10", "min": 1, "max": 100},
    "ollama_text_timeout_s": {"label": "Tekst timeout (sek.)", "type": "int", "default": "90", "min": 10, "max": 900},
    "ollama_text_num_predict": {"label": "Tekst output tokens", "type": "int", "default": "1800", "min": 128, "max": 16384},
    "ollama_text_temperature": {"label": "Tekst temperature", "type": "float", "default": "0.1", "min": 0, "max": 2},
}


class RuntimeUpdate(BaseModel):
    values: dict[str, str]


class PromptDraft(BaseModel):
    template: str
    notes: str | None = None


def _validate_runtime_value(key: str, value: str) -> str:
    spec = AI_RUNTIME_FIELDS.get(key)
    if not spec:
        raise HTTPException(status_code=400, detail=f"Ukendt AI-indstilling: {key}")
    value = str(value).strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{spec['label']} må ikke være tom")
    if spec["type"] in {"int", "float"}:
        try:
            number = int(value) if spec["type"] == "int" else float(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{spec['label']} har ugyldig værdi")
        if number < spec["min"] or number > spec["max"]:
            raise HTTPException(status_code=400, detail=f"{spec['label']} skal være mellem {spec['min']} og {spec['max']}")
    return value

@settings_router.get("")
def list_settings(_user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    return get_all_settings(db)

def update_setting(key: str, payload: SettingUpdate, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    set_setting(db, key, payload.value, user.username)
    return {"ok": True, "key": key}


@settings_router.get("/ai-runtime")
def get_ai_runtime(_user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    fields = []
    for key, spec in AI_RUNTIME_FIELDS.items():
        value = get_setting(db, key, spec["default"])
        fields.append({"key": key, **spec, "value": value,
                       "source": "database" if value != spec["default"] else "database_or_default"})
    models = []
    try:
        from ai.ollama_service import OllamaVisionService
        models = OllamaVisionService().list_models()
    except Exception:
        pass
    return {"fields": fields, "installed_models": models}


@settings_router.put("/ai-runtime")
def update_ai_runtime(payload: RuntimeUpdate, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    validated = {key: _validate_runtime_value(key, value) for key, value in payload.values.items()}
    for key, value in validated.items():
        set_setting(db, key, value, user.username)
    return {"ok": True, "updated": sorted(validated)}


@settings_router.get("/ai-prompts")
def get_ai_prompts(_user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    from ai.prompt_registry import list_prompts
    return list_prompts(db)


@settings_router.post("/ai-prompts/{purpose}/draft")
def save_ai_prompt_draft(purpose: str, payload: PromptDraft, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    from ai.prompt_registry import create_draft
    try:
        return create_draft(db, purpose, payload.template, payload.notes, user.username)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ukendt promptformål")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@settings_router.post("/ai-prompts/{prompt_id}/activate")
def activate_ai_prompt(prompt_id: int, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    from ai.prompt_registry import activate_prompt
    try:
        return activate_prompt(db, prompt_id, user.username)
    except KeyError:
        raise HTTPException(status_code=404, detail="Promptversion findes ikke")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Keep the legacy generic route last so it cannot shadow /ai-runtime.
settings_router.put("/{key}")(update_setting)

from ai.ai_strategy import AIConfigManager

@settings_router.get("/config")
def list_ai_configs(_user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    try:
        return AIConfigManager(db).list_all()
    except Exception:
        return []

@settings_router.post("/config")
def save_ai_config(payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    from ai.ai_strategy import AIConfigManager
    mgr = AIConfigManager(db)
    mgr.set_config(
        strategy             = payload.get("strategy", "cloud_only"),
        customer_id          = payload.get("customer_id"),
        site_id              = payload.get("site_id"),
        customer_name        = payload.get("customer_name"),
        site_name            = payload.get("site_name"),
        local_model          = payload.get("local_model", "qwen3-vl:8b"),
        cloud_model          = payload.get("cloud_model", "gemini-2.5-flash"),
        escalation_threshold = payload.get("escalation_threshold", 0.70),
        escalation_new_tags  = payload.get("escalation_new_tags", 4),
        always_escalate_tags = payload.get("always_escalate_tags"),
        always_cloud_tags    = payload.get("always_cloud_tags"),
        tag_vocabulary_limit = payload.get("tag_vocabulary_limit", 80),
        enabled              = payload.get("enabled", True),
        notes                = payload.get("notes"),
        updated_by           = user.username,
    )
    return {"ok": True}
