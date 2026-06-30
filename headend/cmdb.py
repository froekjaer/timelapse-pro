# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — cmdb.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.0.0
# Dato     : 2026-05-11
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   1.0.0  11-maj-2026  Initial CMDB + break-glass implementation
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — CMDB API
=========================
Monteres på FastAPI-appen i main.py:

    from cmdb import router as cmdb_router
    app.include_router(cmdb_router, prefix="/api/cmdb")

Endpoints:
    GET  /api/cmdb/                         → liste alle enheder (inventory summary)
    GET  /api/cmdb/{device_id}              → fuld CMDB-post for enhed
    PUT  /api/cmdb/{device_id}              → admin opdaterer felt (environment, notes, location_id)
    POST /api/inventory/{device_id}         → edge rapporterer inventar ved startup
    POST /api/cmdb/{device_id}/break-glass  → admin opretter break-glass konto
    GET  /api/cmdb/{device_id}/break-glass  → list break-glass konti (ingen passwords)
    POST /api/cmdb/{device_id}/break-glass/checkout → checkout: vis password + roter
    DELETE /api/cmdb/{device_id}/break-glass/{account_id} → slet konto
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import Device, DeviceInventory, BreakGlassAccount, PendingUpdate, get_db, now_utc

log = logging.getLogger(__name__)

router = APIRouter(tags=["CMDB"])


def _require_cmdb_role(*roles: str):
    """Local RBAC bridge for this router without making cmdb.py import main.py at module load."""
    def _check(request: Request, db: Session = Depends(get_db)):
        from main import _ROLE_HIERARCHY, get_current_user

        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        return user

    return _check


HEADEND_MANAGED_HOMEBREW_FORMULAE = {
    "certbot": "TimeLapse TLS/certificate platformkomponent",
    "ffmpeg": "TimeLapse video/rendering platformkomponent",
    "nginx": "TimeLapse reverse proxy platformkomponent",
    "node": "TimeLapse UI build/runtime platformkomponent",
    "ollama": "TimeLapse AI analyse platformkomponent",
    "postgresql@17": "TimeLapse database platformkomponent",
    "python@3.13": "TimeLapse Headend Python runtime",
}


def _parse_version_gap(version: str | None) -> dict:
    text = (version or "").strip()
    import re
    match = re.match(r"(.+?)\s+(.+?)\s*->\s*(.+)$", text)
    if match:
        component, current, latest = [part.strip() for part in match.groups()]
        return {
            "component": component,
            "current_version": current,
            "latest_available_version": latest,
            "version_gap_label": f"{current} -> {latest}",
            "package_count": None,
        }
    count_match = re.match(r"(\d+)\s+pakker", text)
    if count_match:
        count = int(count_match.group(1))
        return {
            "component": None,
            "current_version": None,
            "latest_available_version": f"{count} pakker klar",
            "version_gap_label": f"{count} pakker klar",
            "package_count": count,
        }
    return {
        "component": None,
        "current_version": None,
        "latest_available_version": text or None,
        "version_gap_label": text or None,
        "package_count": None,
    }


def _update_summary_for_device(db: Session, device_id: str) -> dict:
    updates = (
        db.query(PendingUpdate)
        .filter(PendingUpdate.scope == "device", PendingUpdate.scope_id == device_id)
        .order_by(PendingUpdate.created_at.desc())
        .all()
    )
    active = [u for u in updates if u.status in {"pending", "approved", "blocked", "rollback_requested"}]
    latest = []
    for update in active[:6]:
        gap = _parse_version_gap(update.version)
        latest.append({
            "id": update.id,
            "update_type": update.update_type,
            "status": update.status,
            "severity": update.severity,
            "environment": update.environment,
            **gap,
        })
    return {
        "active_count": len(active),
        "security_count": sum(1 for u in active if "security" in (u.update_type or "")),
        "blocked_count": sum(1 for u in active if u.status == "blocked"),
        "approved_count": sum(1 for u in active if u.status == "approved"),
        "latest": latest,
    }


def _components_from_mapping(mapping: dict, component_type: str, scope: str) -> list[dict]:
    components = []
    for name, version in sorted((mapping or {}).items()):
        if str(name).startswith("_"):
            continue
        components.append({
            "type": component_type,
            "name": str(name),
            "version": str(version),
            "scope": scope,
        })
    return components


def _sbom_for_inventory(inv: DeviceInventory) -> dict:
    os_packages = {}
    venv_packages = {}
    software_inventory = {}
    for attr, target in (
        ("os_packages", os_packages),
        ("venv_packages", venv_packages),
        ("software_inventory", software_inventory),
    ):
        raw = getattr(inv, attr, None)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                target.update(parsed)
        except Exception:
            pass
    components = []
    components.extend(_components_from_mapping(os_packages, "library", "os"))
    components.extend(_components_from_mapping(venv_packages, "library", "python"))
    components.extend(_components_from_mapping(software_inventory, "application", "managed-software"))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:timelapse-sbom-{inv.device_id}",
        "version": 1,
        "metadata": {
            "timestamp": now_utc().isoformat(),
            "component": {
                "type": "device",
                "name": inv.device_id,
                "version": inv.app_version,
            },
            "properties": [
                {"name": "timelapse:device_id", "value": inv.device_id},
                {"name": "timelapse:environment", "value": inv.environment or ""},
                {"name": "timelapse:os_name", "value": inv.os_name or ""},
                {"name": "timelapse:kernel_version", "value": inv.kernel_version or ""},
                {"name": "timelapse:package_manager", "value": getattr(inv, "package_manager", None) or ""},
                {"name": "timelapse:inventory_reported_at", "value": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else ""},
            ],
        },
        "components": components,
    }


def _managed_update_severity(name: str) -> str:
    if name in {"nginx", "postgresql@17", "certbot"}:
        return "high"
    if name in {"ollama", "python@3.13", "node"}:
        return "medium"
    return "low"


def _pending_environment(inv: DeviceInventory) -> str:
    return "production" if (inv.environment or "").lower() == "production" else "test"


def _display_device_status(device: Device | None) -> str:
    if not device:
        return "unknown"
    raw_status = device.status or "unknown"
    if raw_status in {"provisioning", "import", "unknown"}:
        return raw_status
    if not device.last_seen:
        return "offline"
    last_seen = device.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_s = (now_utc() - last_seen).total_seconds()
    if age_s < 15 * 60:
        return "online"
    if age_s < 24 * 3600:
        return "stale"
    return "offline"


def _sync_managed_application_updates(db: Session, device_id: str, inv: DeviceInventory, payload: dict) -> None:
    software = payload.get("software_inventory") or {}
    updates = software.get("available_software_updates") or payload.get("available_software_updates") or []
    if not isinstance(updates, list):
        return

    for item in updates:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name not in HEADEND_MANAGED_HOMEBREW_FORMULAE:
            continue
        installed = str(item.get("installed_version") or "ukendt")
        available = str(item.get("available_version") or "ukendt")
        version = f"{name} {installed} -> {available}"
        exists = db.query(PendingUpdate).filter(
            PendingUpdate.update_type == "application_updates",
            PendingUpdate.scope == "device",
            PendingUpdate.scope_id == device_id,
            PendingUpdate.status.in_(["pending", "approved"]),
            or_(
                PendingUpdate.version == version,
                PendingUpdate.description.ilike(f"%{name}%"),
            ),
        ).first()
        if exists:
            exists.version = version
            exists.description = (
                f"{name} kan opdateres via Headend-kontrolleret Homebrew-artifact/lab-flow "
                f"({installed} -> {available}). {HEADEND_MANAGED_HOMEBREW_FORMULAE[name]}."
            )
            exists.severity = _managed_update_severity(name)
            exists.environment = _pending_environment(inv)
            continue

        db.add(PendingUpdate(
            update_type="application_updates",
            version=version,
            description=(
                f"{name} kan opdateres via Headend-kontrolleret Homebrew-artifact/lab-flow "
                f"({installed} -> {available}). {HEADEND_MANAGED_HOMEBREW_FORMULAE[name]}."
            ),
            severity=_managed_update_severity(name),
            scope="device",
            scope_id=device_id,
            status="pending",
            environment=_pending_environment(inv),
            target_device_ids=json.dumps([device_id]),
        ))


def _sync_edge_os_updates(db: Session, device_id: str, inv: DeviceInventory, payload: dict) -> None:
    """
    Opret/opdater PendingUpdate-rækker for edge OS-opdateringer rapporteret via inventory.
    Opretter én os_security og/eller én os_updates PendingUpdate pr. device.
    """
    apt = payload.get("os_updates_available")
    if not isinstance(apt, dict):
        return
    total    = int(apt.get("total", 0))
    security = int(apt.get("security", 0))
    packages = apt.get("packages", [])
    if total == 0:
        return

    env = _pending_environment(inv)

    def _upsert_os_update(update_type: str, count: int, pkg_list: list) -> None:
        version = f"{count} pakker"
        names = ", ".join(p["name"] for p in pkg_list[:10])
        desc  = (
            f"Edge {device_id}: {count} {'sikkerhedsopdaterin' if 'security' in update_type else 'OS-opdaterin'}"
            f"g{'er' if count != 1 else ''} tilgænge{'lig' if count == 1 else 'lig'}e via apt. "
            f"Første pakker: {names}{'…' if len(pkg_list) > 10 else ''}. "
            f"Installér via Headend-signeret offline OS bundle."
        )
        existing = db.query(PendingUpdate).filter(
            PendingUpdate.update_type == update_type,
            PendingUpdate.scope == "device",
            PendingUpdate.scope_id == device_id,
            PendingUpdate.status.in_(["pending", "approved"]),
        ).first()
        if existing:
            existing.version = version
            existing.description = desc
            existing.severity = "high" if "security" in update_type else "medium"
            existing.environment = env
        else:
            db.add(PendingUpdate(
                update_type=update_type,
                version=version,
                description=desc,
                severity="high" if "security" in update_type else "medium",
                scope="device",
                scope_id=device_id,
                status="pending",
                environment=env,
                target_device_ids=json.dumps([device_id]),
            ))
            log.info("CMDB: PendingUpdate oprettet: %s for %s (%d pakker)", update_type, device_id, count)

    if security > 0:
        sec_pkgs = [p for p in packages if p.get("security")]
        _upsert_os_update("os_security", security, sec_pkgs)

    non_sec = total - security
    if non_sec > 0:
        other_pkgs = [p for p in packages if not p.get("security")]
        _upsert_os_update("os_updates", non_sec, other_pkgs)


# ── Kryptering ────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    """
    Henter Fernet-instansen fra env-variablen BREAK_GLASS_ENC_KEY.

    Generér nøgle (én gang, gem i launchd plist / .env):
        python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = os.environ.get("BREAK_GLASS_ENC_KEY")
    if not key:
        raise RuntimeError(
            "BREAK_GLASS_ENC_KEY ikke sat — kan ikke håndtere break-glass konti. "
            "Generér med: python3 -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def _encrypt(plaintext: str) -> str:
    """Kryptér streng → base64url ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    """Dekryptér ciphertext → plaintext. Kaster HTTPException ved fejl."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Break-glass dekryptering fejlede — forkert nøgle?")


def _generate_password(length: int = 24) -> str:
    """Generér kryptografisk stærkt password (alphanumerisk, ingen tvetydige tegn)."""
    alphabet = string.ascii_letters + string.digits
    # Fjern tvetydige: O, 0, l, 1, I
    alphabet = alphabet.translate(str.maketrans("", "", "O0lI1"))
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── Inventar-handler (kaldt af main.py efter device-auth) ─────────────────────

def report_inventory(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """
    Edge rapporterer hardwareinventar ved startup.
    Opretter DeviceInventory-post hvis den ikke eksisterer.
    Opdaterer hardware-/software-felter og inventory_reported_at.
    """
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        inv = DeviceInventory(device_id=device_id)
        db.add(inv)
        log.info("CMDB: Ny inventar-post oprettet for %s", device_id)
    else:
        log.info("CMDB: Inventar opdateret for %s", device_id)

    # Hardware
    inv.hardware_model          = payload.get("hardware_model")
    inv.soc_model               = payload.get("soc_model")
    inv.cpu_cores               = payload.get("cpu_cores")
    inv.ram_mb                  = payload.get("ram_mb")
    inv.mac_address             = payload.get("mac_address")
    inv.serial_number           = payload.get("serial_number")
    inv.hostname                = payload.get("hostname")

    # OS / Software
    inv.os_name                 = payload.get("os_name")
    inv.kernel_version          = payload.get("kernel_version")
    if hasattr(inv, "firmware_version"):
        inv.firmware_version    = payload.get("firmware_version")
    inv.python_version          = payload.get("python_version")
    inv.app_version             = payload.get("app_version")
    if hasattr(inv, "package_manager"):
        inv.package_manager     = payload.get("package_manager")
    if hasattr(inv, "os_packages") and "os_packages" in payload:
        inv.os_packages         = json.dumps(payload["os_packages"])
    if "venv_packages" in payload:
        inv.venv_packages       = json.dumps(payload["venv_packages"])
    if hasattr(inv, "software_inventory") and "software_inventory" in payload:
        software_inventory = payload["software_inventory"]
        if not isinstance(software_inventory, dict):
            software_inventory = {}
        software_inventory = dict(software_inventory)
        # Embed extra fields for SBOM / CMDB dashboard
        if payload.get("ip_addresses"):
            software_inventory["_network"] = {"ip_addresses": payload.get("ip_addresses")}
        if "os_updates_available" in payload:
            software_inventory["_os_updates_available"] = payload["os_updates_available"]
        if "services" in payload:
            software_inventory["_services"] = payload["services"]
        if "local_users" in payload:
            software_inventory["_local_users"] = payload["local_users"]
        if "sudo_users" in payload:
            software_inventory["_sudo_users"] = payload["sudo_users"]
        if payload.get("git_commit"):
            software_inventory["_git_commit"] = payload["git_commit"]
        if payload.get("git_tag"):
            software_inventory["_git_tag"] = payload["git_tag"]
        inv.software_inventory  = json.dumps(software_inventory)

    # Storage
    inv.boot_storage_type       = payload.get("boot_storage_type")
    inv.boot_storage_total_gb   = payload.get("boot_storage_total_gb")
    inv.boot_storage_used_pct   = payload.get("boot_storage_used_pct")
    inv.data_partition_path     = payload.get("data_partition_path")
    inv.data_partition_total_gb = payload.get("data_partition_total_gb")
    inv.data_partition_used_pct = payload.get("data_partition_used_pct")

    # Netværk
    inv.primary_interface       = payload.get("primary_interface")
    inv.wifi_capable            = payload.get("wifi_capable", False)
    inv.wifi_ssid               = payload.get("wifi_ssid")

    # Signering
    inv.gpg_fingerprint         = payload.get("gpg_fingerprint")

    # Tracking
    inv.inventory_reported_at   = now_utc()

    # Sæt app_version/IP på Device-record også. Headend/node-agent kan være
    # inventory-only, så opret en let Device-række når den mangler.
    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device:
        device = Device(
            device_id=device_id,
            location_name=payload.get("hostname") or device_id,
            first_seen=now_utc(),
            last_seen=now_utc(),
            app_version=payload.get("app_version"),
            status="online",
        )
        db.add(device)
        log.info("CMDB: Device-række oprettet fra inventory for %s", device_id)
    else:
        device.last_seen = now_utc()
        device.status = "online"
    if payload.get("app_version"):
        device.app_version = payload["app_version"]
    if payload.get("ip_address"):
        device.ip_address = payload["ip_address"]

    _sync_managed_application_updates(db, device_id, inv, payload)
    _sync_edge_os_updates(db, device_id, inv, payload)

    db.commit()
    return {
        "status": "ok",
        "device_id": device_id,
        "os_updates_pending": int((payload.get("os_updates_available") or {}).get("total", 0)),
        "os_security_pending": int((payload.get("os_updates_available") or {}).get("security", 0)),
    }


# ── CMDB list / detail ────────────────────────────────────────────────────────

@router.get("/")
def list_cmdb(_user=Depends(_require_cmdb_role("viewer")), db: Session = Depends(get_db)):
    """Oversigt over alle CMDB-poster — til CMDB-siden i UI."""
    rows = db.query(DeviceInventory).order_by(DeviceInventory.device_id).all()
    result = []
    for inv in rows:
        device = db.query(Device).filter_by(device_id=inv.device_id).first()
        bg_count = db.query(BreakGlassAccount).filter_by(
            device_id=inv.device_id, is_active=True
        ).count()
        result.append({
            "device_id":            inv.device_id,
            "environment":          inv.environment,
            "hardware_model":       inv.hardware_model,
            "soc_model":            inv.soc_model,
            "os_name":              inv.os_name,
            "app_version":          inv.app_version,
            "firmware_version":     getattr(inv, "firmware_version", None),
            "package_manager":      getattr(inv, "package_manager", None),
            "hostname":             inv.hostname,
            "location_id":          inv.location_id,
            "inventory_reported_at": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
            "provisioned_at":       inv.provisioned_at.isoformat() if inv.provisioned_at else None,
            "provisioned_by":       inv.provisioned_by,
            "gpg_fingerprint":      inv.gpg_fingerprint,
            "notes":                inv.notes,
            # Fra Device-tabellen
            "status":               _display_device_status(device),
            "customer_name":        device.customer_name if device else None,
            "site_name":            device.site_name if device else None,
            "ip_address":           device.ip_address if device else None,
            "last_seen":            device.last_seen.isoformat() if device and device.last_seen else None,
            "break_glass_count":    bg_count,
            "update_summary":       _update_summary_for_device(db, inv.device_id),
        })
    return result


@router.get("/sbom/all")
def get_all_sboms(_user=Depends(_require_cmdb_role("viewer")), db: Session = Depends(get_db)):
    """Generér SBOM pr. kendt CMDB-enhed."""
    inventories = db.query(DeviceInventory).order_by(DeviceInventory.device_id).all()
    return {
        "generated_at": now_utc().isoformat(),
        "count": len(inventories),
        "sboms": [_sbom_for_inventory(inv) for inv in inventories],
    }


@router.get("/{device_id}")
def get_cmdb(device_id: str, _user=Depends(_require_cmdb_role("viewer")), db: Session = Depends(get_db)):
    """Fuld CMDB-post for én enhed."""
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Ingen CMDB-post for denne enhed")
    device = db.query(Device).filter_by(device_id=device_id).first()

    packages = {}
    if inv.venv_packages:
        try:
            packages = json.loads(inv.venv_packages)
        except Exception:
            pass
    os_packages = {}
    if getattr(inv, "os_packages", None):
        try:
            os_packages = json.loads(inv.os_packages)
        except Exception:
            pass
    software_inventory = {}
    if getattr(inv, "software_inventory", None):
        try:
            software_inventory = json.loads(inv.software_inventory)
        except Exception:
            pass

    result = {
        "device_id":                inv.device_id,
        "environment":              inv.environment,
        # Hardware
        "hardware_model":           inv.hardware_model,
        "soc_model":                inv.soc_model,
        "cpu_cores":                inv.cpu_cores,
        "ram_mb":                   inv.ram_mb,
        "mac_address":              inv.mac_address,
        "serial_number":            inv.serial_number,
        "hostname":                 inv.hostname,
        # OS/Software
        "os_name":                  inv.os_name,
        "kernel_version":           inv.kernel_version,
        "firmware_version":         getattr(inv, "firmware_version", None),
        "python_version":           inv.python_version,
        "app_version":              inv.app_version,
        "package_manager":          getattr(inv, "package_manager", None),
        "os_packages":              os_packages,
        "venv_packages":            packages,
        "software_inventory":       software_inventory,
        # Storage
        "boot_storage_type":        inv.boot_storage_type,
        "boot_storage_total_gb":    inv.boot_storage_total_gb,
        "boot_storage_used_pct":    inv.boot_storage_used_pct,
        "data_partition_path":      inv.data_partition_path,
        "data_partition_total_gb":  inv.data_partition_total_gb,
        "data_partition_used_pct":  inv.data_partition_used_pct,
        # Netværk
        "primary_interface":        inv.primary_interface,
        "wifi_capable":             inv.wifi_capable,
        "wifi_ssid":                inv.wifi_ssid,
        # Signering + lokation
        "gpg_fingerprint":          inv.gpg_fingerprint,
        "location_id":              inv.location_id,
        # Provisioning + tracking
        "provisioned_at":           inv.provisioned_at.isoformat() if inv.provisioned_at else None,
        "provisioned_by":           inv.provisioned_by,
        "inventory_reported_at":    inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
        "notes":                    inv.notes,
        "created_at":               inv.created_at.isoformat() if inv.created_at else None,
        "updated_at":               inv.updated_at.isoformat() if inv.updated_at else None,
        # Fra Device
        "status":                   _display_device_status(device),
        "customer_name":            device.customer_name if device else None,
        "site_name":                device.site_name if device else None,
        "ip_address":               device.ip_address if device else None,
        "last_seen":                device.last_seen.isoformat() if device and device.last_seen else None,
    }
    result["update_summary"] = _update_summary_for_device(db, device_id)
    return result


@router.get("/{device_id}/sbom")
def get_device_sbom(device_id: str, _user=Depends(_require_cmdb_role("viewer")), db: Session = Depends(get_db)):
    """Generér SBOM fra seneste CMDB inventory for en device/headend node."""
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Ingen CMDB-post for denne enhed")
    return _sbom_for_inventory(inv)


@router.put("/{device_id}")
def update_cmdb(device_id: str, payload: dict, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """
    Admin opdaterer editerbare CMDB-felter.
    Hardware-felter opdateres kun af edge — ikke her.
    """
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Ingen CMDB-post for denne enhed")

    editable = ["environment", "notes", "location_id", "provisioned_by",
                "provisioned_at", "gpg_fingerprint"]
    for field in editable:
        if field in payload:
            setattr(inv, field, payload[field])

    db.commit()
    log.info("CMDB opdateret for %s: %s", device_id, list(payload.keys()))
    return {"status": "ok"}


# ── Break-the-glass ───────────────────────────────────────────────────────────

@router.post("/{device_id}/break-glass")
def create_break_glass(device_id: str, payload: dict, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """
    Admin opretter en break-glass konto for en enhed.

    Body:
        admin_username  (str)  Hvilken admin-konto der ejer denne adgang
        ssh_username    (str, optional) Standard: "emergency"
        public_key      (str, optional) SSH public key til authorized_keys
        expires_days    (int, optional) Antal dage til udløb (0 = udløber ikke)

    Password genereres automatisk og krypteres. Admin ser det IKKE ved oprettelse
    — brug /checkout for at hente det.
    """
    admin_username = payload.get("admin_username")
    if not admin_username:
        raise HTTPException(status_code=400, detail="admin_username påkrævet")

    # Tjek om der allerede eksisterer en aktiv konto
    existing = db.query(BreakGlassAccount).filter_by(
        device_id=device_id, admin_username=admin_username, is_active=True
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Aktiv break-glass konto eksisterer allerede for {admin_username} på {device_id}. "
                   "Brug /checkout for at hente password eller slet den eksisterende først."
        )

    password = _generate_password()
    encrypted = _encrypt(password)

    expires_days = payload.get("expires_days", 0)
    expires_at = (now_utc() + timedelta(days=expires_days)) if expires_days else None

    account = BreakGlassAccount(
        device_id       = device_id,
        admin_username  = admin_username,
        ssh_username    = payload.get("ssh_username", "emergency"),
        password_enc    = encrypted,
        public_key      = payload.get("public_key"),
        expires_at      = expires_at,
        rotation_reason = "initial",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    log.info("Break-glass oprettet: device=%s admin=%s id=%d", device_id, admin_username, account.id)

    # Vi returnerer IKKE passwordet her — admin skal bruge /checkout
    return {
        "status":   "ok",
        "id":       account.id,
        "device_id": device_id,
        "admin_username": admin_username,
        "ssh_username":   account.ssh_username,
        "expires_at":     account.expires_at.isoformat() if account.expires_at else None,
        "message":  "Konto oprettet. Brug /checkout for at hente password.",
    }


@router.get("/{device_id}/break-glass")
def list_break_glass(device_id: str, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """List alle break-glass konti for en enhed — UDEN passwords."""
    accounts = db.query(BreakGlassAccount).filter_by(
        device_id=device_id, is_active=True
    ).all()
    return [
        {
            "id":               a.id,
            "admin_username":   a.admin_username,
            "ssh_username":     a.ssh_username,
            "has_public_key":   bool(a.public_key),
            "checkout_count":   a.checkout_count,
            "last_used_at":     a.last_used_at.isoformat() if a.last_used_at else None,
            "last_used_by":     a.last_used_by,
            "rotated_at":       a.rotated_at.isoformat() if a.rotated_at else None,
            "expires_at":       a.expires_at.isoformat() if a.expires_at else None,
            "created_at":       a.created_at.isoformat() if a.created_at else None,
        }
        for a in accounts
    ]


@router.post("/{device_id}/break-glass/checkout")
def checkout_break_glass(device_id: str, payload: dict, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """
    Checkout break-glass password.

    - Dekrypterer og returnerer det aktuelle password
    - Genererer straks et NYT password og krypterer det (rotation)
    - Logger tidspunkt og bruger
    - TODO Sprint CMDB-2: push nyt password til edge via SSH

    Body:
        admin_username  (str)  Hvilken admin der checker ud
        reason          (str)  Årsag til adgang (til audit log)

    SIKKERHED: Denne endpoint skal i produktion kræve:
        1. Stærk MFA (ikke bare session-cookie)
        2. IP-whitelisting
        3. Rate limiting (maks 3 checkouts pr. time)
    """
    admin_username = payload.get("admin_username")
    reason = payload.get("reason", "Ikke angivet")

    if not admin_username:
        raise HTTPException(status_code=400, detail="admin_username påkrævet")

    account = db.query(BreakGlassAccount).filter_by(
        device_id=device_id, admin_username=admin_username, is_active=True
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Ingen aktiv break-glass konto fundet")

    # Tjek udløb
    if account.expires_at and account.expires_at < now_utc():
        raise HTTPException(status_code=403, detail="Break-glass konto er udløbet")

    # Dekryptér det aktuelle password (til returnering)
    current_password = _decrypt(account.password_enc)

    # Generer og kryptér nyt password (rotation)
    new_password = _generate_password()
    account.password_enc    = _encrypt(new_password)
    account.rotated_at      = now_utc()
    account.rotation_reason = f"checkout af {admin_username}: {reason}"
    account.last_used_at    = now_utc()
    account.last_used_by    = admin_username
    account.checkout_count  = (account.checkout_count or 0) + 1

    db.commit()

    log.warning(
        "BREAK-GLASS CHECKOUT: device=%s admin=%s reason='%s' checkout_count=%d",
        device_id, admin_username, reason, account.checkout_count
    )

    # TODO Sprint CMDB-2: push nyt password til edge
    # Dette kræver SSH-forbindelse til edge (break-glass giver jo netop adgang
    # til enheder der måske ikke er tilgængelige via normal kanal — så det er
    # komplekst. For nu: admin er ansvarlig for at rotere manuelt efter brug.)

    return {
        "device_id":        device_id,
        "ssh_username":     account.ssh_username,
        "password":         current_password,
        # ⚠️ Dette er det AKTUELLE password (inden rotation).
        # Det nye password er allerede gemt i DB.
        # Gem dette password sikkert — det vises kun denne ene gang.
        "rotated":          True,
        "checkout_count":   account.checkout_count,
        "warning":          "Password vises kun denne ene gang. Gem det nu. Rotation er sket.",
    }


@router.delete("/{device_id}/break-glass/{account_id}")
def delete_break_glass(device_id: str, account_id: int, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """Deaktiver (soft delete) en break-glass konto."""
    account = db.query(BreakGlassAccount).filter_by(
        id=account_id, device_id=device_id
    ).first()
    if not account:
        raise HTTPException(status_code=404)
    account.is_active = False
    account.rotation_reason = "slettet af admin"
    db.commit()
    log.info("Break-glass deaktiveret: id=%d device=%s", account_id, device_id)
    return {"status": "ok"}
