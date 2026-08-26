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
    GET  /api/cmdb/{device_id}/break-glass/checkout-history → fuld checkout-historik (audit)
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
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from database import CustomerRiskInput, CustomerRiskProfile, Device, DeviceInventory, BreakGlassAccount, BreakGlassCheckoutAudit, PendingUpdate, get_db, now_utc
from services.fair_risk import estimate_annual_loss

log = logging.getLogger(__name__)

router = APIRouter(tags=["CMDB"])


def migrate_break_glass_applied_at_column(engine) -> None:
    """Additive migration, called once from main.py::startup().

    2026-08-25 incident: the naive try/except-pass idiom used elsewhere in
    this codebase for "column already exists" silently swallowed a
    DIFFERENT failure here (InsufficientPrivilege — break_glass_accounts
    turned out to be owned by a non-application DB role) and the migration
    never actually ran. edge_sync.py then unconditionally queried the
    missing column on every poll, 500ing every device's sync for ~10
    minutes before this was caught. Only swallow the specific
    "already exists" case now; anything else surfaces as a real error so
    it can never again fail this quietly.
    """
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE break_glass_accounts ADD COLUMN applied_at TIMESTAMP"))
                conn.commit()
                log.info("DB migration break-glass: break_glass_accounts.applied_at tilføjet")
            except Exception as exc:
                if "already exists" in str(exc).lower() or "duplicate column" in str(exc).lower():
                    pass
                else:
                    log.error(
                        "DB migration break-glass: ALTER TABLE fejlede af en IKKE-forventet "
                        "årsag (ikke 'already exists') — applied_at findes muligvis IKKE i DB "
                        "endnu, hvilket vil crashe edge_sync for alle devices: %s", exc,
                    )
    except Exception as exc:
        log.error("DB migration break-glass fejl: %s", exc)

# ── Break-glass checkout-hærdning (opt-in, default slået FRA) ─────────────────
# Lukker en del af det dokumenterede SABSA-/compliance-hul i checkout_break_glass.
# MFA er stadig en opfølgning (kræver auth-integration), men rate-limit + valgfri
# IP-allowlist kan slås til uden at ændre det normale flow:
#   TIMELAPSE_BREAKGLASS_CHECKOUT_MAX_PER_HOUR=3   (0 = ingen grænse, default)
#   TIMELAPSE_BREAKGLASS_IP_ALLOWLIST=10.0.0.0/8,192.168.1.5  (tom = ingen filtrering)
import threading as _bg_threading
from collections import deque as _bg_deque
import ipaddress as _bg_ipaddress
_bg_checkout_log: dict[tuple, _bg_deque] = {}
_bg_checkout_lock = _bg_threading.Lock()


def _enforce_break_glass_policy(request: "Request | None", device_id: str, admin_username: str) -> None:
    # IP-allowlist (valgfri)
    allow_raw = os.getenv("TIMELAPSE_BREAKGLASS_IP_ALLOWLIST", "").strip()
    if allow_raw and request is not None:
        client_ip = getattr(getattr(request, "client", None), "host", None)
        nets = []
        for item in allow_raw.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                nets.append(_bg_ipaddress.ip_network(item, strict=False))
            except ValueError:
                continue
        ok = False
        if client_ip:
            try:
                ip = _bg_ipaddress.ip_address(client_ip)
                ok = any(ip in n for n in nets)
            except ValueError:
                ok = False
        if not ok:
            raise HTTPException(status_code=403, detail="Break-glass checkout ikke tilladt fra denne IP")
    # Rate-limit (valgfri)
    try:
        max_per_hour = int(os.getenv("TIMELAPSE_BREAKGLASS_CHECKOUT_MAX_PER_HOUR", "0"))
    except ValueError:
        max_per_hour = 0
    if max_per_hour > 0:
        import time as _t
        key = (device_id, admin_username)
        now = _t.monotonic()
        with _bg_checkout_lock:
            bucket = _bg_checkout_log.setdefault(key, _bg_deque())
            while bucket and now - bucket[0] > 3600:
                bucket.popleft()
            if len(bucket) >= max_per_hour:
                raise HTTPException(status_code=429, detail="Break-glass checkout rate-limit overskredet (prøv senere)")
            bucket.append(now)


def _require_cmdb_role(*roles: str):
    """Local RBAC bridge for this router without making cmdb.py import main.py at module load.

    2026-07-03: tilføjet MFA-håndhævelse. Denne bro tjekkede tidligere KUN rolle —
    den kaldte aldrig main._mfa_required_for_user()/_session_is_mfa_verified(), så
    hele CMDB-routeren (inkl. break-glass password-checkout) reelt omgik MFA-
    politikken, selvom RISK_ASSESSMENT_v10.md/GO_LIVE_CHECKLIST_v10.md markerer
    MFA som "løst" for admin/super_admin. Se
    Claude_Kritisk_Statusgennemgang_2026-07-03.md §2.2/§2.3.
    """
    def _check(request: Request, db: Session = Depends(get_db)):
        from main import (
            _ROLE_HIERARCHY,
            _mfa_required_for_user,
            _session_is_mfa_verified,
            _session_payload,
            get_current_user,
        )

        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
        return user

    return _check


def _visible_device_ids(db: Session, user) -> set[str] | None:
    """Return None for platform scope, otherwise the tenant's explicit device set."""
    from main import _is_platform_admin, _visible_device_query

    if _is_platform_admin(user):
        return None
    return {row[0] for row in _visible_device_query(db, user).with_entities(Device.device_id).all()}


def _ensure_device_access(db: Session, user, device_id: str) -> Device | None:
    device = db.query(Device).filter_by(device_id=device_id).first()
    visible = _visible_device_ids(db, user)
    if visible is not None and device_id not in visible:
        # Do not reveal whether another tenant owns the identifier.
        raise HTTPException(status_code=404, detail="Ingen CMDB-post for denne enhed")
    return device


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
        description = (
            f"{name} kan opdateres via Headend-kontrolleret Homebrew-artifact/lab-flow "
            f"({installed} -> {available}). {HEADEND_MANAGED_HOMEBREW_FORMULAE[name]}."
            "\n\nBlocked: kræver signeret dependency-artifact og rollback-plan før godkendelse."
        )
        exists = db.query(PendingUpdate).filter(
            PendingUpdate.update_type == "application_updates",
            PendingUpdate.scope == "device",
            PendingUpdate.scope_id == device_id,
            PendingUpdate.status.in_(["pending", "approved", "blocked"]),
            or_(
                PendingUpdate.version == version,
                PendingUpdate.description.ilike(f"%{name}%"),
            ),
        ).first()
        if exists:
            exists.version = version
            exists.description = description
            exists.severity = _managed_update_severity(name)
            exists.environment = _pending_environment(inv)
            if exists.status in {"pending", "approved"}:
                exists.status = "blocked"
            continue

        db.add(PendingUpdate(
            update_type="application_updates",
            version=version,
            description=description,
            severity=_managed_update_severity(name),
            scope="device",
            scope_id=device_id,
            status="blocked",
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
            f"CMDB observation — ikke deployable. Opret/verificér lab-katalog og build-plan før Headend-signeret offline OS bundle."
        )
        existing = db.query(PendingUpdate).filter(
            PendingUpdate.update_type == update_type,
            PendingUpdate.scope == "device",
            PendingUpdate.scope_id == device_id,
            PendingUpdate.status.in_(["blocked", "pending", "approved"]),
        ).first()
        if existing:
            existing.version = version
            existing.description = desc
            existing.severity = "high" if "security" in update_type else "medium"
            existing.environment = env
            existing.status = "blocked"
        else:
            db.add(PendingUpdate(
                update_type=update_type,
                version=version,
                description=desc,
                severity="high" if "security" in update_type else "medium",
                scope="device",
                scope_id=device_id,
                status="blocked",
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
        if "enabled_services" in payload:
            software_inventory["_enabled_services"] = payload["enabled_services"]
        if "apt_sources" in payload:
            software_inventory["_apt_sources"] = payload["apt_sources"]
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
    q = db.query(DeviceInventory)
    visible = _visible_device_ids(db, _user)
    if visible is not None:
        q = q.filter(DeviceInventory.device_id.in_(visible)) if visible else q.filter(False)
    rows = q.order_by(DeviceInventory.device_id).all()
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
    q = db.query(DeviceInventory)
    visible = _visible_device_ids(db, _user)
    if visible is not None:
        q = q.filter(DeviceInventory.device_id.in_(visible)) if visible else q.filter(False)
    inventories = q.order_by(DeviceInventory.device_id).all()
    return {
        "generated_at": now_utc().isoformat(),
        "count": len(inventories),
        "sboms": [_sbom_for_inventory(inv) for inv in inventories],
    }


@router.get("/operational-context/{device_id}")
def get_operational_context(
    device_id: str,
    hours: int = 24,
    _user=Depends(_require_cmdb_role("viewer")),
    db: Session = Depends(get_db),
):
    """Correlate CMDB, ITIM and SIEM without replacing their source records."""
    if hours < 1 or hours > 8760:
        raise HTTPException(status_code=422, detail="hours skal være mellem 1 og 8760")
    device = _ensure_device_access(db, _user, device_id)
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Ingen CMDB-post for denne enhed")

    from itim import ItimAlertEvent, ItimHealthStatus, ItimTarget
    from siem import SecurityEvent

    since = now_utc() - timedelta(hours=hours)
    targets = db.query(ItimTarget).filter(ItimTarget.device_id == device_id).all()
    target_ids = [target.id for target in targets]
    health_rows = ({row.target_id: row for row in db.query(ItimHealthStatus)
                    .filter(ItimHealthStatus.target_id.in_(target_ids)).all()}
                   if target_ids else {})
    firing = (db.query(ItimAlertEvent).filter(
        ItimAlertEvent.target_id.in_(target_ids),
        ItimAlertEvent.state == "firing",
    ).order_by(ItimAlertEvent.started_at.desc()).all() if target_ids else [])

    event_query = db.query(SecurityEvent).filter(
        SecurityEvent.device_id == device_id,
        SecurityEvent.occurred_at >= since,
    )
    events = event_query.order_by(SecurityEvent.occurred_at.desc()).limit(10).all()
    severity_counts = {
        str(severity or "info").lower(): int(count)
        for severity, count in event_query.with_entities(
            SecurityEvent.severity, func.count(SecurityEvent.id)
        ).group_by(SecurityEvent.severity).all()
    }

    updates = _update_summary_for_device(db, device_id)
    factors: list[dict] = []
    score = 0

    def add_factor(code: str, points: int, label: str) -> None:
        nonlocal score
        if points > 0:
            score += points
            factors.append({"code": code, "points": points, "label": label})

    states = [health_rows[t.id].state for t in targets if t.id in health_rows]
    add_factor("itim_critical", 35 if "critical" in states else 0, "Kritisk driftsstatus")
    add_factor("itim_warning", 15 if "critical" not in states and "warning" in states else 0,
               "Driftsstatus med advarsel")
    add_factor("siem_critical", 30 if severity_counts.get("critical", 0) else 0,
               "Kritisk SIEM-hændelse i perioden")
    add_factor("siem_error", 15 if severity_counts.get("error", 0) else 0,
               "SIEM-fejl i perioden")
    add_factor("siem_warning", min(10, severity_counts.get("warning", 0) * 2),
               "SIEM-advarsler i perioden")
    add_factor("security_updates", 20 if updates.get("security_count", 0) else 0,
               "Afventende sikkerhedsopdateringer")
    add_factor("blocked_updates", 10 if updates.get("blocked_count", 0) else 0,
               "Blokerede opdateringer")
    add_factor("offline", 20 if not device or str(device.status).lower() != "online" else 0,
               "Enheden er ikke online")
    score = min(100, score)
    risk_level = "critical" if score >= 70 else "high" if score >= 45 else "medium" if score >= 20 else "low"
    commercial_input = None
    business_profile = None
    if device and device.customer_id:
        today = now_utc().date()
        commercial_input = (db.query(CustomerRiskInput).filter(
            CustomerRiskInput.customer_id == device.customer_id,
            CustomerRiskInput.effective_from <= today,
            or_(CustomerRiskInput.effective_to.is_(None), CustomerRiskInput.effective_to >= today),
        ).order_by(CustomerRiskInput.effective_from.desc()).first())
        business_profile = (db.query(CustomerRiskProfile).filter_by(
            customer_id=device.customer_id, status="validated"
        ).order_by(CustomerRiskProfile.version.desc()).first())
    fair = estimate_annual_loss(None, device_id)
    fair["monthly_service_price_available"] = bool(commercial_input)
    fair["customer_risk_profile_available"] = bool(business_profile)
    if business_profile:
        fair["customer_risk_profile_version"] = business_profile.version
        fair["impact_factors"] = {
            "business_dependency": business_profile.business_dependency,
            "availability": business_profile.availability_impact,
            "integrity": business_profile.integrity_impact,
            "confidentiality": business_profile.confidentiality_impact,
            "personal_data_level": business_profile.personal_data_level,
        }
    from main import _is_platform_admin
    if commercial_input and _is_platform_admin(_user):
        fair["monthly_service_price"] = float(commercial_input.monthly_service_price)
        fair["monthly_service_price_currency"] = commercial_input.currency
        fair["monthly_service_price_effective_from"] = commercial_input.effective_from.isoformat()

    return {
        "device": {
            "device_id": device_id,
            "customer_id": device.customer_id if device else None,
            "customer_name": device.customer_name if device else None,
            "site_name": device.site_name if device else None,
            "environment": inv.environment,
            "status": _display_device_status(device),
            "last_seen": device.last_seen.isoformat() if device and device.last_seen else None,
        },
        "priority": {"score": score, "level": risk_level, "factors": factors,
                     "method": "deterministic-operational-priority-v1", "period_hours": hours},
        "fair": fair,
        "updates": updates,
        "itim": {
            "targets": [{
                "target_key": target.target_key,
                "kind": target.kind,
                "state": health_rows[target.id].state if target.id in health_rows else "unknown",
                "summary": health_rows[target.id].summary if target.id in health_rows else None,
            } for target in targets],
            "firing_alerts": len(firing),
        },
        "siem": {
            "counts_by_severity": severity_counts,
            "recent": [{
                "id": event.id, "event_type": event.event_type, "severity": event.severity,
                "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            } for event in events[:10]],
        },
    }


@router.get("/{device_id}")
def get_cmdb(device_id: str, _user=Depends(_require_cmdb_role("viewer")), db: Session = Depends(get_db)):
    """Fuld CMDB-post for én enhed."""
    inv = db.query(DeviceInventory).filter_by(device_id=device_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Ingen CMDB-post for denne enhed")
    device = _ensure_device_access(db, _user, device_id)

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
    _ensure_device_access(db, _user, device_id)
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
    _ensure_device_access(db, _user, device_id)
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
    Admin opretter sin egen break-glass konto for en enhed.

    Ejerskab (admin_username) bindes til den autentificerede sessions brugernavn,
    ikke til request-body — en admin kan ikke oprette eller overtage en konto i en
    anden admins navn (C-06: audit-actor skal være den autentificerede principal).

    Body:
        ssh_username    (str, optional) Standard: "emergency"
        public_key      (str, optional) SSH public key til authorized_keys
        expires_days    (int, optional) Antal dage til udløb (0 = udløber ikke)

    Password genereres automatisk og krypteres. Admin ser det IKKE ved oprettelse
    — brug /checkout for at hente det.
    """
    _ensure_device_access(db, _user, device_id)
    admin_username = _user.username

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
    _ensure_device_access(db, _user, device_id)
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
            "applied":          a.applied_at is not None,
            "applied_at":       a.applied_at.isoformat() if a.applied_at else None,
        }
        for a in accounts
    ]


@router.post("/{device_id}/break-glass/checkout")
def checkout_break_glass(device_id: str, payload: dict, request: Request = None, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """
    Checkout break-glass password for den autentificerede admins egen konto.

    - Dekrypterer og returnerer det AKTUELLE password_enc (det der enten
      allerede er anvendt på enheden, eller vil blive det ved dens næste
      sync — se edge_sync.py/edge/agent.py::_apply_break_glass_password)
    - Roterer KUN til et nyt password hvis `payload.rotate` er sat
      eksplicit (se nedenfor) — IKKE ved hver almindelig checkout
    - Logger tidspunkt og bruger

    2026-08-25 (rettet endnu en rækkefølge-fejl, samme aften, live fanget af
    Peters eget login-forsøg): denne endpoint roterede TIDLIGERE automatisk
    til et nyt password ved HVER checkout — "klargjort til næste checkout".
    Men edge_sync.py/agent.py's leveringsmekanisme skelner ikke mellem "et
    password der lige er vist til en admin og skal være det aktive" og "et
    password der blot er forudgenereret til en fremtidig checkout" — ALT med
    applied_at=None bliver pushet og anvendt ved enhedens NÆSTE sync,
    typisk under et minut senere. Resultatet: det password checkout lige
    havde vist blev rutinemæssigt ugyldigt inden admin nåede at bruge det —
    Peter ramte "Permission denied" gentagne gange fordi hans faktisk
    viste password blev overskrevet på enheden, mens han stadig var ved at
    skrive det ind. Nu er checkout idempotent som standard: samme password
    vises igen og igen, indtil det EKSPLICIT roteres (payload.rotate=true).
    Leverings-cirkularitet (password kan ikke pushes til en enhed der er
    utilgængelig via normal kanal) er stadig accepteret bevidst, jf. Peters
    valg 2026-08-25: leveres ved enhedens næste succesfulde sync, ikke et
    øjeblikkeligt SSH-push — men nu uden at det checkede-ud password
    invaliderer sig selv i baggrunden.

    admin_username bindes til den autentificerede sessions brugernavn, ikke til
    request-body (C-06: audit-actor skal være den autentificerede principal — en
    admin kan ellers checke ud og lade audit-loggen pege på en anden admin). Det
    betyder en admin kun kan checke sin EGEN konto ud.

    Nødhjælp til kollega uden central-adgang: hvis en kollega står på en site og
    ikke selv kan nå det centrale system, ringer/kontakter de en admin der KAN
    — den admin checker sin EGEN konto ud som normalt og udfylder on_behalf_of
    med hvem de hjælper. Det er en dokumentations-markør til audit-historikken
    (se GET .../checkout-history), IKKE en autentificerings-mekanisme — den
    ændrer intet ved hvilken konto der slås op eller hvem den autentificerede
    aktør er.

    Body:
        reason        (str)  Årsag til adgang (til audit log)
        on_behalf_of  (str, optional)  Navn/brugernavn på kollega der hjælpes,
                      hvis checkout sker fordi kollegaen ikke selv kan nå det
                      centrale system
        rotate        (bool, optional, default False)  Generér eksplicit et
                      NYT password i stedet for at vise det nuværende. Brug
                      kun hvis det aktuelle password skal invalideres (f.eks.
                      mistanke om kompromittering) — almindelig checkout skal
                      IKKE rotere, da det ville gøre det viste password
                      forældet igen inden for et sync-interval (se historik
                      2026-08-25 ovenfor).

    SIKKERHED: Denne endpoint skal i produktion kræve:
        1. Stærk MFA (ikke bare session-cookie)
        2. IP-whitelisting
        3. Rate limiting (maks 3 checkouts pr. time)
    """
    _ensure_device_access(db, _user, device_id)
    admin_username = _user.username
    reason = payload.get("reason", "Ikke angivet")
    on_behalf_of = (payload.get("on_behalf_of") or "").strip()[:200] or None
    rotate = bool(payload.get("rotate", False))

    # Opt-in hærdning (rate-limit + IP-allowlist); no-op når env ikke er sat.
    _enforce_break_glass_policy(request, device_id, admin_username)

    account = db.query(BreakGlassAccount).filter_by(
        device_id=device_id, admin_username=admin_username, is_active=True
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Ingen aktiv break-glass konto fundet")

    # Tjek udløb
    if account.expires_at and account.expires_at < now_utc():
        raise HTTPException(status_code=403, detail="Break-glass konto er udløbet")

    was_already_applied = account.applied_at is not None

    if rotate:
        # Eksplicit ønsket rotation — generér og gem et NYT password, som
        # leveres ved enhedens næste sync (samme leverings-cirkularitet som
        # altid). Dette password bliver til gengæld det STABILE svar på
        # alle fremtidige checkouts, indtil nogen roterer eksplicit igen.
        new_password = _generate_password()
        account.password_enc    = _encrypt(new_password)
        account.applied_at      = None
        account.rotated_at      = now_utc()
        account.rotation_reason = f"checkout af {admin_username}: {reason}"
        current_password = new_password
        was_already_applied = False
    else:
        # Almindelig checkout: dekryptér og returnér det AKTUELLE password
        # uændret — det der enten allerede er anvendt på enheden, eller
        # stadig afventer enhedens næste sync. INGEN rotation her; det er
        # netop det der tidligere gjorde det viste password forældet igen
        # inden for et sync-interval.
        current_password = _decrypt(account.password_enc)

    account.last_used_at    = now_utc()
    account.last_used_by    = admin_username
    account.checkout_count  = (account.checkout_count or 0) + 1

    client_ip = getattr(getattr(request, "client", None), "host", None)
    db.add(BreakGlassCheckoutAudit(
        account_id=account.id,
        device_id=device_id,
        checked_out_by=admin_username,
        on_behalf_of=on_behalf_of,
        reason=reason,
        client_ip=client_ip,
    ))

    db.commit()

    log.warning(
        "BREAK-GLASS CHECKOUT: device=%s admin=%s on_behalf_of=%s reason='%s' checkout_count=%d applied=%s rotated=%s",
        device_id, admin_username, on_behalf_of, reason, account.checkout_count, was_already_applied, rotate
    )

    if rotate:
        warning = (
            "Nyt password genereret og gemt. Det virker først når enheden har "
            "synkroniseret med Headend (typisk under et minut) — hvis enheden er "
            "offline, virker det ikke før den er tilbage online."
        )
    elif not was_already_applied:
        warning = (
            "ADVARSEL: dette password er IKKE bekræftet anvendt på enheden endnu "
            "(ingen sync-bekræftelse modtaget siden det blev sat). Det virker først "
            "når enheden har synkroniseret med Headend — hvis enheden er offline, "
            "virker det ikke."
        )
    else:
        warning = "Dette password er aktivt på enheden og forbliver det, indtil det roteres eksplicit."

    return {
        "device_id":        device_id,
        "ssh_username":     account.ssh_username,
        "password":         current_password,
        "applied":          was_already_applied,
        "rotated":          rotate,
        "checkout_count":   account.checkout_count,
        "warning":          warning,
    }


@router.get("/{device_id}/break-glass/checkout-history")
def list_break_glass_checkout_history(device_id: str, limit: int = 50, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """
    Fuld checkout-historik for en enheds break-glass konti — i modsætning til
    GET .../break-glass (som kun viser SENESTE checkout pr. konto), viser dette
    ALLE historiske checkouts, inkl. eventuel on_behalf_of-markering fra
    "hjælp en kollega uden central-adgang"-proceduren. Aldrig passwords.
    """
    _ensure_device_access(db, _user, device_id)
    limit = max(1, min(limit, 500))
    entries = (
        db.query(BreakGlassCheckoutAudit)
        .filter_by(device_id=device_id)
        .order_by(BreakGlassCheckoutAudit.checked_out_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":              e.id,
            "account_id":      e.account_id,
            "checked_out_by":  e.checked_out_by,
            "on_behalf_of":    e.on_behalf_of,
            "reason":          e.reason,
            "client_ip":       e.client_ip,
            "checked_out_at":  e.checked_out_at.isoformat() if e.checked_out_at else None,
        }
        for e in entries
    ]


@router.delete("/{device_id}/break-glass/{account_id}")
def delete_break_glass(device_id: str, account_id: int, _user=Depends(_require_cmdb_role("admin")), db: Session = Depends(get_db)):
    """Deaktiver (soft delete) en break-glass konto."""
    _ensure_device_access(db, _user, device_id)
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
