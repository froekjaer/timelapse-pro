"""
TimeLapse Pro — Settings API endpoints
Tilføj til main.py: from ai.settings_api import settings_router; app.include_router(settings_router)
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from ai.settings_helper import get_all_settings, set_setting

settings_router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingUpdate(BaseModel):
    value: str
    updated_by: str = "admin"

@settings_router.get("")
def list_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)

@settings_router.put("/{key}")
def update_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db)):
    set_setting(db, key, payload.value, payload.updated_by)
    return {"ok": True, "key": key}

from ai.ai_strategy import AIConfigManager

@settings_router.get("/config")
def list_ai_configs(db: Session = Depends(get_db)):
    try:
        return AIConfigManager(db).list_all()
    except Exception:
        return []

@settings_router.post("/config")
def save_ai_config(payload: dict, db: Session = Depends(get_db)):
    from ai.ai_strategy import AIConfigManager
    mgr = AIConfigManager(db)
    mgr.set_config(
        strategy             = payload.get("strategy", "cloud_only"),
        customer_id          = payload.get("customer_id"),
        site_id              = payload.get("site_id"),
        customer_name        = payload.get("customer_name"),
        site_name            = payload.get("site_name"),
        local_model          = payload.get("local_model", "llava-phi3:latest"),
        cloud_model          = payload.get("cloud_model", "gemini-2.5-flash"),
        escalation_threshold = payload.get("escalation_threshold", 0.70),
        escalation_new_tags  = payload.get("escalation_new_tags", 4),
        always_escalate_tags = payload.get("always_escalate_tags"),
        always_cloud_tags    = payload.get("always_cloud_tags"),
        tag_vocabulary_limit = payload.get("tag_vocabulary_limit", 80),
        enabled              = payload.get("enabled", True),
        notes                = payload.get("notes"),
        updated_by           = payload.get("updated_by", "admin"),
    )
    return {"ok": True}
