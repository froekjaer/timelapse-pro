"""Deterministic supersession rules for stale application updates."""

from typing import Any
from datetime import datetime, timezone


_SUPERSEDED_UPDATE_STATUSES = {"pending", "approved", "blocked"}
_SUPERSEDED_TARGET_STATUSES = {"pending", "queued", "approved", "authorized"}
_ACTIONABLE_TARGET_STATUSES = _SUPERSEDED_TARGET_STATUSES


def device_already_at_update_version(device: Any, update: Any) -> bool:
    installed = str(getattr(device, "app_version", None) or "").strip()
    target = str(getattr(update, "version", None) or "").strip()
    if not installed or not target:
        return False
    return installed == target or (len(installed) >= 12 and target.startswith(installed))


def _append_note(value: str | None, note: str) -> str:
    return f"{value or ''}\n{note}".strip()


def _cascade_target_status(
    db: Any,
    target_model: Any,
    pending_update_ids: list[int],
    note: str,
    *,
    new_status: str,
    device_id: str | None = None,
) -> int:
    """Move UpdateTarget rows for closed/blocked PendingUpdates to a consistent
    terminal status, so the flow-status API/UI never shows a target as still
    queued/approved/authorized while its parent update can no longer progress.
    """
    if not pending_update_ids:
        return 0
    now = datetime.now(timezone.utc)
    query = db.query(target_model).filter(
        target_model.pending_update_id.in_(pending_update_ids),
        target_model.status.in_(sorted(_ACTIONABLE_TARGET_STATUSES)),
    )
    if device_id is not None:
        query = query.filter(target_model.device_id == device_id)
    moved = 0
    for target in query.all():
        if getattr(target, "pending_update_id", None) not in pending_update_ids:
            continue
        if device_id is not None and getattr(target, "device_id", None) != device_id:
            continue
        if getattr(target, "status", None) not in _ACTIONABLE_TARGET_STATUSES:
            continue
        target.status = new_status
        if hasattr(target, "last_error"):
            target.last_error = _append_note(getattr(target, "last_error", None), note)
        if hasattr(target, "completed_at") and getattr(target, "completed_at", None) is None:
            target.completed_at = now
        if hasattr(target, "last_report_at"):
            target.last_report_at = now
        moved += 1
    return moved


def reset_stale_targets_on_block(
    db: Any,
    target_model: Any,
    pending_update_id: int,
    note: str,
) -> int:
    """A PendingUpdate that is (still) 'blocked' can never advance a target sitting
    in queued/approved/authorized — nothing moves those forward while the parent is
    blocked. Mirrors the terminal-failure mapping report_update()/
    mark_headend_update_failed() already use for a blocked parent: target.status
    becomes "failed", with last_error carrying why.
    """
    return _cascade_target_status(db, target_model, [pending_update_id], note, new_status="failed")


def close_targets_for_superseded_updates(
    db: Any,
    target_model: Any,
    pending_update_ids: list[int],
    note: str,
    *,
    device_id: str | None = None,
) -> int:
    """Same cascade supersede_pending_app_updates already does for app_updates,
    generalized for CMDB-driven supersession of OS/platform-app candidates.
    """
    return _cascade_target_status(
        db, target_model, pending_update_ids, note, new_status="superseded", device_id=device_id
    )


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
        if hasattr(candidate, "resolution_reason"):
            candidate.resolution_reason = f"Superseded by signed release {new_version}"
        candidate_id = getattr(candidate, "id", None)
        if candidate_id is not None:
            superseded_ids.append(candidate_id)

    if target_model is not None and superseded_ids:
        _cascade_target_status(db, target_model, superseded_ids, note, new_status="superseded", device_id=device_id)

    return len(superseded_ids) if superseded_ids else sum(
        1 for candidate in candidates if getattr(candidate, "status", None) == "superseded"
    )
