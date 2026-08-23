"""Deterministic supersession rules for stale application updates."""

from typing import Any
from datetime import datetime, timezone


_SUPERSEDED_UPDATE_STATUSES = {"pending", "approved"}
_SUPERSEDED_TARGET_STATUSES = {"pending", "queued", "approved", "authorized"}


def device_already_at_update_version(device: Any, update: Any) -> bool:
    installed = str(getattr(device, "app_version", None) or "").strip()
    target = str(getattr(update, "version", None) or "").strip()
    if not installed or not target:
        return False
    return installed == target or (len(installed) >= 12 and target.startswith(installed))


def _append_note(value: str | None, note: str) -> str:
    return f"{value or ''}\n{note}".strip()


def supersede_pending_app_updates(
    db: Any,
    model: Any,
    device_id: str,
    new_version: str,
    *,
    target_model: Any | None = None,
) -> int:
    """Close older app update candidates for a device when a new signed release exists."""
    candidates = db.query(model).filter(
        model.update_type == "app_updates",
        model.scope == "device",
        model.scope_id == device_id,
        model.status.in_(sorted(_SUPERSEDED_UPDATE_STATUSES)),
        model.version != new_version,
    ).all()
    note = f"Superseded by signed release {new_version}."
    superseded_ids: list[int] = []
    for candidate in candidates:
        if getattr(candidate, "status", None) not in _SUPERSEDED_UPDATE_STATUSES:
            continue
        if getattr(candidate, "version", None) == new_version:
            continue
        candidate.status = "superseded"
        candidate.description = _append_note(getattr(candidate, "description", None), note)
        candidate_id = getattr(candidate, "id", None)
        if candidate_id is not None:
            superseded_ids.append(candidate_id)

    if target_model is not None and superseded_ids:
        now = datetime.now(timezone.utc)
        targets = db.query(target_model).filter(
            target_model.pending_update_id.in_(superseded_ids),
            target_model.device_id == device_id,
            target_model.status.in_(sorted(_SUPERSEDED_TARGET_STATUSES)),
        ).all()
        for target in targets:
            if getattr(target, "pending_update_id", None) not in superseded_ids:
                continue
            if getattr(target, "device_id", None) != device_id:
                continue
            if getattr(target, "status", None) not in _SUPERSEDED_TARGET_STATUSES:
                continue
            target.status = "superseded"
            if hasattr(target, "last_error"):
                target.last_error = _append_note(getattr(target, "last_error", None), note)
            if hasattr(target, "completed_at") and getattr(target, "completed_at", None) is None:
                target.completed_at = now
            if hasattr(target, "last_report_at"):
                target.last_report_at = now

    return len(superseded_ids) if superseded_ids else sum(
        1 for candidate in candidates if getattr(candidate, "status", None) == "superseded"
    )
