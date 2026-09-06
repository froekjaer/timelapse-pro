"""WebAuthn origin and RP ID selection helpers."""

from __future__ import annotations

import os
from typing import Callable
from urllib.parse import urlparse


def _csv_settings(value: str | None) -> list[str]:
    return [item.strip().rstrip("/") for item in (value or "").split(",") if item.strip()]


def _request_origin(request) -> str:
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if origin:
        return origin
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").strip()
    host = (request.headers.get("host") or request.url.netloc).strip()
    if not urlparse(f"{proto}://{host}").hostname:
        raise ValueError("Ugyldig WebAuthn origin")
    return f"{proto}://{host}".rstrip("/")


def _default_rp_id_for_origin(origin: str) -> str:
    host = urlparse(origin).hostname or "localhost"
    if host == "timelapse-pro.dk" or host.endswith(".timelapse-pro.dk"):
        return "timelapse-pro.dk"
    return host


def resolve_webauthn_settings(db, request, get_setting: Callable, env=os.environ) -> tuple[str, str, str]:
    base_url = get_setting(db, "base_url", env.get("BASE_URL", "http://127.0.0.1:8000")).strip().rstrip("/")
    allowed = _csv_settings(get_setting(db, "webauthn_allowed_origins", env.get("WEBAUTHN_ALLOWED_ORIGINS", "")))
    rp_name = get_setting(db, "webauthn_rp_name", env.get("WEBAUTHN_RP_NAME", "TimeLapse Pro")).strip() or "TimeLapse Pro"
    if request is not None and allowed:
        origin = _request_origin(request)
        if origin not in allowed:
            raise ValueError("WebAuthn origin er ikke tilladt")
        return _default_rp_id_for_origin(origin), rp_name, origin
    origin = get_setting(db, "webauthn_origin", env.get("WEBAUTHN_ORIGIN", base_url)).strip().rstrip("/")
    host = urlparse(origin).hostname or "localhost"
    rp_id = get_setting(db, "webauthn_rp_id", env.get("WEBAUTHN_RP_ID", host)).strip() or host
    return rp_id, rp_name, origin


def replace_setting_value(db, settings_model, key: str, value: str) -> None:
    row = db.query(settings_model).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.add(settings_model(key=key, value=value))
