"""Shared AI provider configuration helpers.

These helpers recover provider configuration from the same Headend authority used
by production code. They must not log or return credential values.
"""
from __future__ import annotations

import os


def build_gemini_vision_service(get_db_fn, cloud_model: str):
    """Build GeminiVisionService from Headend settings/environment.

    Returns None when no Gemini credential source is configured. Credential
    values stay inside the provider constructor and are never returned as
    benchmark/report metadata.
    """
    from ai.gemini_service import GeminiVisionService
    from ai.settings_helper import get_setting

    db_gen = get_db_fn()
    db = next(db_gen)
    try:
        gemini_key = os.getenv("GEMINI_API_KEY", "") or get_setting(db, "gemini_api_key")
        gemini_sa_path = (
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
            or get_setting(db, "gemini_service_account_path")
        )
        gemini_project_id = (
            os.getenv("GOOGLE_CLOUD_PROJECT", "")
            or get_setting(db, "gemini_project_id")
        )
        gemini_location = (
            os.getenv("GOOGLE_CLOUD_LOCATION", "")
            or get_setting(db, "gemini_location", "europe-west1")
        )
    finally:
        db_gen.close()

    if not gemini_key and not gemini_sa_path:
        return None

    return GeminiVisionService(
        service_account_path=gemini_sa_path,
        project_id=gemini_project_id,
        location=gemini_location,
        api_key=gemini_key,
        model=cloud_model,
    )
