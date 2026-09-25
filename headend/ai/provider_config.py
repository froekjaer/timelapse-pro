"""Shared AI provider configuration helpers.

These helpers recover provider configuration from the same Headend authority used
by production code. Credential values stay inside provider constructors and must
never be emitted as status/report metadata.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str
    service_account_path: str
    project_id: str
    location: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key or self.service_account_path)


def read_gemini_config(db) -> GeminiConfig:
    from ai.settings_helper import get_setting

    return GeminiConfig(
        api_key=os.getenv("GEMINI_API_KEY", "") or get_setting(db, "gemini_api_key"),
        service_account_path=(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
            or get_setting(db, "gemini_service_account_path")
        ),
        project_id=(
            os.getenv("GOOGLE_CLOUD_PROJECT", "")
            or get_setting(db, "gemini_project_id")
        ),
        location=(
            os.getenv("GOOGLE_CLOUD_LOCATION", "")
            or get_setting(db, "gemini_location", "europe-west1")
        ),
    )


def build_gemini_vision_service_from_db(db, cloud_model: str):
    """Build GeminiVisionService from one existing Headend DB session."""
    from ai.gemini_service import GeminiVisionService

    config = read_gemini_config(db)
    if not config.configured:
        return None
    return GeminiVisionService(
        service_account_path=config.service_account_path,
        project_id=config.project_id,
        location=config.location,
        api_key=config.api_key,
        model=cloud_model,
    )


def build_gemini_vision_service(get_db_fn, cloud_model: str):
    """Build GeminiVisionService from Headend settings/environment.

    Compatibility helper for existing call sites. Returns None when no Gemini
    credential source is configured.
    """
    db_gen = get_db_fn()
    db = next(db_gen)
    try:
        return build_gemini_vision_service_from_db(db, cloud_model)
    finally:
        db_gen.close()
