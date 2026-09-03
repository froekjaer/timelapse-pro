"""Promotion metadata for update queue rows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable


_PROMOTION_RE = re.compile(r"^\[Promoveret fra ([^\]]+) til ([^\]]+)\]")
_APP_UPDATE_TYPES = {
    "app_updates",
    "app_security",
    "timelapse_update",
    "timelapse_updates",
    "timelapse_security",
}


def promotion_source(update: Any) -> str | None:
    match = _PROMOTION_RE.match(getattr(update, "description", None) or "")
    return match.group(1) if match else None


@dataclass
class PromotionStatus:
    production_update: Any | None
    eligible: bool
    blocked_reason: str | None


class PromotionContext:
    def __init__(
        self,
        *,
        production_matches: dict[tuple[str, str, str, str | None], Any],
        latest_deployed_nonprod: dict[tuple[str, str, str | None], Any],
        resolve_update_targets: Callable[[Any], list[Any]],
        find_artifact_for_update: Callable[[Any], Any | None],
        is_deployable_artifact: Callable[[Any | None], bool],
    ) -> None:
        self.production_matches = production_matches
        self.latest_deployed_nonprod = latest_deployed_nonprod
        self.resolve_update_targets = resolve_update_targets
        self.find_artifact_for_update = find_artifact_for_update
        self.is_deployable_artifact = is_deployable_artifact

    def status(self, update: Any) -> PromotionStatus:
        production_update = self.production_matches.get(_production_key(update))
        if getattr(update, "status", None) != "deployed":
            return PromotionStatus(production_update, False, None)
        if getattr(update, "environment", None) not in {"test", "staging"}:
            return PromotionStatus(production_update, False, "Kun deployed test/staging-kandidater kan promoveres direkte.")
        if production_update:
            return PromotionStatus(production_update, False, "Allerede promoveret til production.")
        latest = self.latest_deployed_nonprod.get(_nonprod_key(update))
        if not latest or getattr(latest, "id", None) != getattr(update, "id", None):
            return PromotionStatus(production_update, False, "Historisk deployment erstattet af en nyere non-prod deployment.")
        artifact = self.find_artifact_for_update(update)
        if not self.is_deployable_artifact(artifact):
            return PromotionStatus(production_update, False, "Mangler deploybart signeret artifact.")
        if not self._app_candidate_still_installed(update):
            return PromotionStatus(production_update, False, "Target-enhed rapporterer ikke længere denne app-version.")
        return PromotionStatus(production_update, True, None)

    def _app_candidate_still_installed(self, update: Any) -> bool:
        if getattr(update, "update_type", None) not in _APP_UPDATE_TYPES:
            return True
        targets = self.resolve_update_targets(update)
        if not targets:
            return False
        version = str(getattr(update, "version", None) or "").strip()
        for device in targets:
            installed = str(getattr(device, "app_version", None) or "").strip()
            if not installed or not version:
                return False
            if installed != version and not version.startswith(installed):
                return False
        return True


def build_update_promotion_context(
    db: Any,
    update_model: Any,
    *,
    resolve_update_targets: Callable[[Any], list[Any]],
    find_artifact_for_update: Callable[[Any], Any | None],
    is_deployable_artifact: Callable[[Any | None], bool],
) -> PromotionContext:
    production_matches = {
        _production_key(update): update
        for update in db.query(update_model).filter(update_model.environment == "production").all()
    }
    latest_deployed_nonprod: dict[tuple[str, str, str | None], Any] = {}
    deployed_rows = db.query(update_model).filter(
        update_model.status == "deployed",
        update_model.environment.in_(["lab", "test", "staging"]),
    ).order_by(
        update_model.deployed_at.desc().nullslast(),
        update_model.created_at.desc(),
        update_model.id.desc(),
    ).all()
    for update in deployed_rows:
        latest_deployed_nonprod.setdefault(_nonprod_key(update), update)

    return PromotionContext(
        production_matches=production_matches,
        latest_deployed_nonprod=latest_deployed_nonprod,
        resolve_update_targets=resolve_update_targets,
        find_artifact_for_update=find_artifact_for_update,
        is_deployable_artifact=is_deployable_artifact,
    )


def serialize_pending_update(update: Any, promotion_context: PromotionContext) -> dict[str, Any]:
    promotion = promotion_context.status(update)
    source = promotion_source(update)
    production = promotion.production_update
    return {
        "id": getattr(update, "id", None),
        "update_type": update.update_type,
        "version": update.version,
        "description": update.description,
        "severity": update.severity,
        "scope": update.scope,
        "scope_id": update.scope_id,
        "status": update.status,
        "resolution_reason": getattr(update, "resolution_reason", None),
        "environment": update.environment,
        "target_device_ids": json.loads(update.target_device_ids) if update.target_device_ids else None,
        "deployed_count": update.deployed_count or 0,
        "failed_count": update.failed_count or 0,
        "created_at": update.created_at.isoformat() if update.created_at else None,
        "approved_at": update.approved_at.isoformat() if update.approved_at else None,
        "approved_by": update.approved_by,
        "deployed_at": update.deployed_at.isoformat() if update.deployed_at else None,
        "rollback_at": update.rollback_at.isoformat() if update.rollback_at else None,
        "production_promotion_id": production.id if production else None,
        "production_promotion_status": production.status if production else None,
        "promotion_source_environment": source,
        "promotion_eligible": promotion.eligible,
        "promotion_blocked_reason": promotion.blocked_reason,
        "prod_ready": update.environment == "production" and update.status == "pending" and source in {"lab", "test", "staging"},
    }


def _production_key(update: Any) -> tuple[str, str, str, str | None]:
    return (update.update_type, update.version, update.scope, update.scope_id)


def _nonprod_key(update: Any) -> tuple[str, str, str | None]:
    return (update.update_type, update.scope, update.scope_id)
