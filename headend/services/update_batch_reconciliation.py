"""Batch-update identity, artifact binding, and catalog-session helpers.

Kept outside the Headend API module so trust-boundary logic can be tested and
reused without growing the already ratcheted main.py monolith.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


def normalized_package_targets(value: Any) -> list[dict[str, str]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    if not isinstance(value, list):
        return []
    targets: dict[tuple[str, str], dict[str, str]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower().replace("_", "-")
        target = str(item.get("available_version") or item.get("new_ver") or item.get("version") or "").strip()
        if name and target:
            targets[(name, target)] = {"name": name, "available_version": target}
    return [targets[key] for key in sorted(targets)]


def package_targets_fingerprint(value: Any) -> str | None:
    targets = normalized_package_targets(value)
    if not targets:
        return None
    payload = json.dumps(targets, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def artifact_package_targets(artifact: Any | None) -> list[dict[str, str]]:
    if not artifact or not artifact.manifest_json:
        return []
    try:
        manifest = json.loads(artifact.manifest_json)
    except Exception:
        return []
    direct = normalized_package_targets(((manifest.get("created") or {}).get("lab_evidence") or {}).get("packages_requested"))
    if direct:
        return direct
    output = next((item for item in (manifest.get("outputs") or []) if isinstance(item, dict) and item.get("path") == "package-manifest.json"), None)
    if not output or not artifact.storage_path:
        return []
    try:
        root = Path(artifact.storage_path).expanduser().resolve()
        package_manifest = (root / "package-manifest.json").resolve()
        if root not in package_manifest.parents or not package_manifest.is_file():
            return []
        actual_hash = hashlib.sha256(package_manifest.read_bytes()).hexdigest()
        if not hmac.compare_digest(str(output.get("sha256") or "").lower(), actual_hash.lower()):
            return []
        return normalized_package_targets(json.loads(package_manifest.read_text()).get("packages_requested"))
    except Exception:
        return []


def artifact_matches_update_packages(artifact: Any | None, package_details: Any) -> bool:
    expected = package_targets_fingerprint(package_details)
    actual = package_targets_fingerprint(artifact_package_targets(artifact))
    return bool(expected and actual and hmac.compare_digest(expected, actual))


def supersede_changed_batch_candidate(db: Any, update: Any, reason: str, *, target_model: Any, ticket_model: Any, close_targets: Callable, now_utc: Callable) -> None:
    update.status = "superseded"
    update.resolution_reason = reason
    update.description = f"{(update.description or '').rstrip()}\n\n{reason}".strip()
    if update.id is None:
        return
    close_targets(db, target_model, [update.id], reason, device_id=update.scope_id)
    for ticket in db.query(ticket_model).filter_by(pending_update_id=update.id).all():
        if ticket.status not in {"deployed", "rolled_back", "rejected", "cancelled"}:
            ticket.status = "cancelled"
            ticket.updated_at = now_utc()


def update_policy_ticket_error(db: Any, update: Any, artifact: Any | None, *, ticket_model: Any) -> str | None:
    """Fail closed unless the newest change ticket authorizes this artifact."""
    ticket = db.query(ticket_model).filter_by(pending_update_id=update.id).order_by(ticket_model.created_at.desc()).first()
    if not ticket or ticket.status != "approved":
        return "change ticket is not approved"
    if artifact and ticket.artifact_id != artifact.artifact_id:
        return "approved change ticket is not bound to the selected artifact"
    return None


def ignored_terminal_update_report(update: Any, device_id: str, status: str, *, logger: Any) -> dict[str, Any] | None:
    """Keep stale Edge reports from reopening administratively terminal work."""
    if update.status not in {"superseded", "rejected"}:
        return None
    logger.warning("Ignoring late Edge report for terminal update %s (%s): device=%s status=%s", update.id, update.status, device_id, status)
    return {"ok": True, "ignored": True, "reason": f"update_{update.status}"}


def inventory_snapshots(session_factory: Callable, inventory_model: Any, *, field: str, apt_only: bool = False) -> list[dict[str, Any]]:
    db = session_factory()
    try:
        query = db.query(inventory_model)
        query = query.filter(inventory_model.package_manager.ilike("%apt%")) if apt_only else query.filter(getattr(inventory_model, field).isnot(None))
        rows = query.order_by(inventory_model.device_id).all()
        fields = ["device_id", field, "environment"] + (["os_name"] if apt_only else [])
        return [{name: getattr(row, name) for name in fields} for row in rows]
    finally:
        db.close()


def refresh_os_catalog_devices(*, session_factory: Callable, inventory_model: Any, user_model: Any, generate: Callable, default_image: Callable, import_catalog: Callable, payload_model: Any, now_utc: Callable, logger: Any) -> None:
    devices = inventory_snapshots(session_factory, inventory_model, field="os_packages", apt_only=True)
    system_user = user_model(username="system:os-catalog-refresh", role="system", password_hash="")
    for snapshot in devices:
        device_id = str(snapshot.get("device_id") or "").strip()
        try:
            installed = json.loads(snapshot.get("os_packages") or "{}")
        except Exception:
            installed = {}
        if not device_id or not isinstance(installed, dict) or not installed:
            continue
        try:
            generated = generate(installed=installed, device_id=device_id, architecture="arm64", image=default_image(SimpleNamespace(**snapshot)))
            db = session_factory()
            try:
                import_catalog(payload_model(device_id=device_id, apt_list_text=generated["apt_list_text"], source=f"headend-scheduled-cmdb-refresh:{now_utc():%Y-%m-%d}", environment=snapshot.get("environment") or "lab", create_updates=True), system_user, db)
                db.commit()
                logger.info("OS-katalogopdagelse: opdateret for %s", device_id)
            except Exception as exc:
                db.rollback(); logger.warning("OS-katalogopdagelse: fejl for %s: %s", device_id, exc)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("OS-katalogopdagelse: katalog-build fejlede for %s: %s", device_id, exc)


def refresh_python_catalog_devices(*, session_factory: Callable, inventory_model: Any, user_model: Any, reconcile: Callable, requirements_text: Callable, write_json: Callable, upsert: Callable, now_utc: Callable, logger: Any) -> None:
    devices = inventory_snapshots(session_factory, inventory_model, field="venv_packages")
    user_model(username="system:python-catalog-refresh", role="system", password_hash="")
    for snapshot in devices:
        device_id = str(snapshot.get("device_id") or "").strip()
        try:
            installed = json.loads(snapshot.get("venv_packages") or "{}")
        except Exception:
            installed = {}
        if not device_id or not isinstance(installed, dict) or not installed:
            continue
        try:
            decisions = reconcile(installed, requirements_text())
            if not decisions:
                continue
            created_at = now_utc(); environment = snapshot.get("environment") or "lab"
            plan = {"schema": "dk.froekjaer.timelapse.python_update_plan.v1", "source": "headend-cmdb-pypi-reconcile", "generated_at": created_at.isoformat(), "device_id": device_id, "environment": environment, "decisions": decisions}
            plan_path = write_json("python-update-plans", f"{device_id}-{created_at:%Y%m%d-%H%M%S}.json", plan)
            db = session_factory()
            try:
                upsert(db, device_id, environment, decisions, f"headend-scheduled-pypi-refresh:{created_at:%Y-%m-%d}", plan_path)
                db.commit(); logger.info("Python-katalogopdagelse: opdateret for %s", device_id)
            except Exception as exc:
                db.rollback(); logger.warning("Python-katalogopdagelse: fejl for %s: %s", device_id, exc)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Python-katalogopdagelse: katalog-build fejlede for %s: %s", device_id, exc)
