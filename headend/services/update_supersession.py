"""Deterministic supersession rules for pending application updates."""

from typing import Any


def supersede_pending_app_updates(db: Any, model: Any, device_id: str, new_version: str) -> int:
    candidates = db.query(model).filter(
        model.update_type == "app_updates",
        model.scope == "device",
        model.scope_id == device_id,
        model.environment == "test",
        model.status == "pending",
        model.version != new_version,
    ).all()
    for candidate in candidates:
        candidate.status = "superseded"
        note = f"Superseded by signed release {new_version}."
        candidate.description = f"{candidate.description or ''}\n{note}".strip()
    return len(candidates)
