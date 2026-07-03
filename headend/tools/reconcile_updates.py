#!/usr/bin/env python3
"""
TimeLapse Pro - Headend update reconciliation.

Creates PendingUpdate records from CMDB installed-state and a Headend-owned
update catalog. Edge reports what is installed; Headend decides what is missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import DeviceInventory, PendingUpdate, SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile CMDB installed-state with update catalog")
    parser.add_argument("--device-id", required=True)
    parser.add_argument(
        "--catalog",
        required=True,
        help="Headend-owned JSON update catalog from the lab/mirror pipeline",
    )
    parser.add_argument(
        "--plan-output",
        help="Write a Headend-generated OS update plan/bundle request JSON",
    )
    parser.add_argument("--environment", default="production", choices=["lab", "staging", "production"])
    parser.add_argument("--dry-run", action="store_true", help="Show decisions without DB writes")
    parser.add_argument("--create", action="store_true", help="Create pending update records")
    args = parser.parse_args()

    if args.dry_run and args.create:
        parser.error("--dry-run and --create are mutually exclusive")
    if not args.dry_run and not args.create:
        parser.error("choose --dry-run or --create")

    catalog = read_catalog(Path(args.catalog))

    db = SessionLocal()
    try:
        inv = db.query(DeviceInventory).filter_by(device_id=args.device_id).first()
        if not inv:
            raise SystemExit(f"CMDB inventory not found for {args.device_id}")
        installed = json.loads(inv.os_packages or "{}")
        decisions = reconcile(installed, catalog)

        plan = {
            "schema": "dk.froekjaer.timelapse.os_update_plan.v1",
            "source": "headend-cmdb-reconcile",
            "device_id": args.device_id,
            "environment": args.environment,
            "catalog_source": catalog.get("source"),
            "inventory_reported_at": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
            "decisions": decisions,
            "bundle_requests": bundle_requests(args.device_id, args.environment, decisions, catalog),
        }

        print(json.dumps(plan, indent=2, ensure_ascii=False))
        if args.plan_output:
            plan_path = Path(args.plan_output).expanduser().resolve()
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")

        if args.create:
            created = create_pending_updates(db, args.device_id, args.environment, decisions, catalog)
            db.commit()
            print(json.dumps({"created": created}, indent=2, ensure_ascii=False))
    finally:
        db.close()
    return 0


def read_catalog(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data.get("packages"), list):
        raise SystemExit("catalog must contain packages[]")
    return data


def reconcile(installed: dict[str, str], catalog: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for package in catalog.get("packages", []):
        name = package.get("name")
        available = package.get("available_version")
        category = package.get("category") or "os_updates"
        if category not in {"os_security", "os_updates"}:
            continue
        installed_version = installed.get(name)
        if not name or not available or not installed_version:
            continue
        if installed_version == available:
            continue
        grouped[category].append({
            "name": name,
            "installed_version": installed_version,
            "available_version": available,
            "severity": package.get("severity") or ("high" if category == "os_security" else "low"),
            "source_repo": package.get("source_repo"),
        })

    decisions = {}
    for category, packages in grouped.items():
        severities = {p["severity"] for p in packages}
        severity = "high" if "high" in severities else "medium" if "medium" in severities else "low"
        decisions[category] = {
            "package_count": len(packages),
            "severity": severity,
            "packages": packages,
            "package_preview": packages[:50],
            "truncated": max(0, len(packages) - 50),
        }
    return decisions


def bundle_requests(
    device_id: str,
    environment: str,
    decisions: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    requests = []
    generated_at = datetime.now(timezone.utc).isoformat()
    for category, decision in decisions.items():
        packages = decision.get("packages") or []
        if not packages:
            continue
        requests.append({
            "schema": "dk.froekjaer.timelapse.os_bundle_request.v1",
            "source": "headend-cmdb-reconcile",
            "generated_at": generated_at,
            "device_id": device_id,
            "environment": environment,
            "category": category,
            "catalog_source": catalog.get("source"),
            "package_count": decision.get("package_count"),
            "severity": decision.get("severity"),
            "packages": packages,
            "truncated": decision.get("truncated", 0),
            "edge_requires_direct_internet": False,
            "edge_may_run_apt_get_upgrade": False,
        })
    return requests


def create_pending_updates(
    db,
    device_id: str,
    environment: str,
    decisions: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    created = []
    for update_type, decision in decisions.items():
        existing = (
            db.query(PendingUpdate)
            .filter(
                PendingUpdate.update_type == update_type,
                PendingUpdate.scope == "device",
                PendingUpdate.scope_id == device_id,
                PendingUpdate.status.in_(["pending", "approved"]),
            )
            .first()
        )
        if existing:
            created.append({"update_type": update_type, "status": "exists", "id": existing.id})
            continue

        count = int(decision["package_count"])
        label = "sikkerhedsopdatering(er)" if update_type == "os_security" else "funktionelle OS-opdatering(er)"
        update = PendingUpdate(
            update_type=update_type,
            version=f"{count} pakker",
            description=(
                f"{count} {label} klar via Headend update catalog "
                f"({catalog.get('source', 'unknown source')})"
            ),
            severity=decision["severity"],
            scope="device",
            scope_id=device_id,
            status="pending",
            environment=environment,
        )
        db.add(update)
        db.flush()
        created.append({"update_type": update_type, "status": "created", "id": update.id})
    return created


if __name__ == "__main__":
    raise SystemExit(main())
