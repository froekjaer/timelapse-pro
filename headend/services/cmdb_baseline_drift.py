"""CMDB baseline-drift reconciliation.

Closes FIND-CMDB-MISSING-PACKAGE-DETECTION and FIND-CMDB-UNTRACKED-DOCKER-CE-CHANNEL
(2026-08-16): CMDB update-tracking previously only compared *installed* package
versions against the catalog, so a package the hardware target expects but that
was never installed (e.g. gpsd on TL-043EB9E72EFD) was never flagged. Per Peter's
direction the same day, this is widened beyond packages to cover services and
local accounts, and to detect BOTH directions: things that should exist but
don't, and things that exist but shouldn't.

Per-package apt origin (which repo a given installed package came from) is
still not collected — that would need per-package `apt-cache policy` lookups
and would false-positive on the entire base OS image. What IS built
(2026-08-19, ACT-CMDB-APT-SOURCE-TRACKING): the general form of the
docker-ce finding, which was really "an apt CHANNEL isn't in CMDB's
baseline" — compute_apt_source_drift() compares the device's configured apt
repo URIs (edge/utils/inventory.py::_apt_sources()) against a hardware
target's expected_apt_sources, both directions, the same shape as
services/accounts below.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

_HARDWARE_ROOT = Path(__file__).resolve().parents[1] / "tools" / "hardware"


@dataclass(frozen=True)
class DriftResult:
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.missing or self.unexpected)


def compute_package_drift(expected_packages: list[str], installed_packages: dict[str, str]) -> DriftResult:
    """Packages the hardware target expects that aren't installed.

    One-directional by design — see module docstring for why "unexpected
    package" detection isn't built here.
    """
    installed = set(installed_packages or {})
    missing = sorted(set(expected_packages or []) - installed)
    return DriftResult(missing=missing, unexpected=[])


def compute_service_drift(expected_services: list[str], enabled_services: list[str]) -> DriftResult:
    """Services that should be enabled but aren't, and services that are
    enabled but aren't part of the expected baseline for this hardware target.
    """
    expected = set(expected_services or [])
    enabled = set(enabled_services or [])
    missing = sorted(expected - enabled)
    unexpected = sorted(enabled - expected)
    return DriftResult(missing=missing, unexpected=unexpected)


def compute_account_drift(expected_users: list[str], local_users: list[dict]) -> DriftResult:
    """Local (UID>=1000) accounts that should exist but don't, and accounts
    that exist but aren't part of the expected baseline for this hardware
    target. `local_users` is the list-of-dicts shape edge/utils/inventory.py
    reports (each with a "username" key).
    """
    expected = set(expected_users or [])
    present = {str(u.get("username") or "") for u in (local_users or []) if u.get("username")}
    missing = sorted(expected - present)
    unexpected = sorted(present - expected)
    return DriftResult(missing=missing, unexpected=unexpected)


def compute_apt_source_drift(expected_sources: list[str], configured_sources: list[str]) -> DriftResult:
    """Apt repo URIs the hardware target expects that aren't configured, and
    repos that are configured but aren't part of the expected baseline —
    the general form of FIND-CMDB-UNTRACKED-DOCKER-CE-CHANNEL. `configured_sources`
    is the list edge/utils/inventory.py::_apt_sources() reports.
    """
    expected = set(expected_sources or [])
    configured = set(configured_sources or [])
    missing = sorted(expected - configured)
    unexpected = sorted(configured - expected)
    return DriftResult(missing=missing, unexpected=unexpected)


def compute_baseline_drift(target: dict, inventory: dict) -> dict[str, DriftResult]:
    """Full four-category comparison for one device against its hardware target.

    `target` is a parsed target.yaml (must have extra_packages,
    expected_enabled_services, expected_local_users, expected_apt_sources).
    `inventory` is a device_inventory-shaped dict (os_packages,
    software_inventory with _enabled_services / _local_users / _apt_sources
    keys, as persisted by headend/cmdb.py).
    """
    software = inventory.get("software_inventory") or {}
    return {
        "packages": compute_package_drift(
            target.get("extra_packages") or [],
            inventory.get("os_packages") or {},
        ),
        "services": compute_service_drift(
            target.get("expected_enabled_services") or [],
            software.get("_enabled_services") or [],
        ),
        "accounts": compute_account_drift(
            target.get("expected_local_users") or [],
            software.get("_local_users") or [],
        ),
        "apt_sources": compute_apt_source_drift(
            target.get("expected_apt_sources") or [],
            software.get("_apt_sources") or [],
        ),
    }


_CATEGORY_LABELS = {
    "packages": "pakke(r)",
    "apt_sources": "apt-kilde(r)",
    "services": "service(s)",
    "accounts": "lokal(e) konto/konti",
}


def drift_to_grc_finding_rows(device_id: str, drift: dict[str, DriftResult]) -> list[dict]:
    """Flatten a compute_baseline_drift() result into grc_items-shaped rows.

    One row per (category, direction) that actually has drift — callers are
    expected to upsert these against the existing grc_items table using the
    same external_id/created_by conventions as the rest of the GRC register.
    """
    rows: list[dict] = []
    for category, result in drift.items():
        label = _CATEGORY_LABELS.get(category, category)
        if result.missing:
            rows.append({
                "item_type": "finding",
                "external_id": f"FIND-CMDB-DRIFT-{device_id}-{category.upper()}-MISSING",
                "title": f"{device_id}: mangler {len(result.missing)} forventet {label} jf. hardware-target",
                "description": f"Forventet men ikke fundet: {', '.join(result.missing)}",
                "severity_hint": "medium",
                "kind": "missing",
                "category": category,
                "items": result.missing,
            })
        if result.unexpected:
            rows.append({
                "item_type": "finding",
                "external_id": f"FIND-CMDB-DRIFT-{device_id}-{category.upper()}-UNEXPECTED",
                "title": f"{device_id}: {len(result.unexpected)} uventet(e) {label} ud over hardware-target-baseline",
                "description": f"Til stede men ikke i baseline: {', '.join(result.unexpected)}",
                "severity_hint": "medium",
                "kind": "unexpected",
                "category": category,
                "items": result.unexpected,
            })
    return rows


# ── Hardware-target resolution ──────────────────────────────────────────────

def available_target_ids() -> list[str]:
    if not _HARDWARE_ROOT.is_dir():
        return []
    return sorted(p.name for p in _HARDWARE_ROOT.iterdir() if (p / "target.yaml").is_file())


def load_target_yaml(target_id: str) -> dict:
    path = _HARDWARE_ROOT / target_id / "target.yaml"
    return yaml.safe_load(path.read_text()) or {}


def resolve_target_id(
    hardware_model: str | None,
    soc_model: str | None,
    target_ids: list[str],
    load_target: Callable[[str], dict],
) -> str | None:
    """Best-effort match of a reported hardware_model/soc_model against each
    target.yaml's device_tree_model_patterns. Substring match on the combined,
    lowercased haystack — mirrors how these patterns are already used at
    image-build time (see inject_edge_image.py).
    """
    haystack = f"{hardware_model or ''} {soc_model or ''}".lower()
    for target_id in target_ids:
        patterns = load_target(target_id).get("device_tree_model_patterns") or []
        if any(str(pattern).lower() in haystack for pattern in patterns):
            return target_id
    return None


# ── Orchestration: compute drift for one device, upsert GRC findings ────────

def reconcile_device_baseline(db, device_id: str, actor: str) -> dict:
    """Compute baseline drift for one device and upsert grc_items findings.

    Findings that no longer apply (drift resolved since the last run) are
    auto-closed. Returns a summary dict suitable for an admin API response.
    """
    from database import DeviceInventory, GrcItem

    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        return {"ok": False, "error": "no_inventory", "device_id": device_id}

    target_id = resolve_target_id(inv.hardware_model, inv.soc_model, available_target_ids(), load_target_yaml)
    if not target_id:
        return {"ok": False, "error": "no_matching_hardware_target", "device_id": device_id}

    target = load_target_yaml(target_id)
    inventory_dict = {
        "os_packages": json.loads(inv.os_packages or "{}"),
        "software_inventory": json.loads(inv.software_inventory or "{}"),
    }
    drift = compute_baseline_drift(target, inventory_dict)
    rows = drift_to_grc_finding_rows(device_id, drift)

    now = datetime.now(timezone.utc)
    seen_external_ids = {row["external_id"] for row in rows}
    for row in rows:
        existing = db.query(GrcItem).filter_by(item_type="finding", external_id=row["external_id"]).first()
        if existing:
            existing.title = row["title"]
            existing.description = row["description"]
            existing.status = "open"
            existing.updated_by = actor
            existing.updated_at = now
        else:
            db.add(GrcItem(
                item_type="finding",
                external_id=row["external_id"],
                title=row["title"],
                description=row["description"],
                status="open",
                priority=row["severity_hint"],
                owner="Claude",
                source=f"cmdb_baseline_drift {now.date().isoformat()}",
                created_by=actor,
                updated_by=actor,
            ))

    prefix = f"FIND-CMDB-DRIFT-{device_id}-"
    stale = [
        item for item in db.query(GrcItem).filter_by(item_type="finding", status="open").all()
        if item.external_id.startswith(prefix) and item.external_id not in seen_external_ids
    ]
    for item in stale:
        item.status = "closed"
        item.updated_by = actor
        item.updated_at = now

    db.commit()
    return {
        "ok": True,
        "device_id": device_id,
        "target_id": target_id,
        "findings_open": len(rows),
        "findings_auto_closed": len(stale),
        "drift": {k: {"missing": v.missing, "unexpected": v.unexpected} for k, v in drift.items()},
    }
