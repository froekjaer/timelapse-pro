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
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Device, DeviceInventory, BreakGlassAccount, get_db, now_utc

log = logging.getLogger(__name__)

router = APIRouter(tags=["CMDB"])


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


# ── Inventar-endpoint (kaldt af edge ved startup) ─────────────────────────────

@router.post("/../../inventory/{device_id}", include_in_schema=True)
def report_inventory(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """
    Edge rapporterer hardwareinventar ved startup.
    Opretter DeviceInventory-post hvis den ikke eksisterer.
    Opdaterer hardware-/software-felter og inventory_reported_at.

    Kræver ikke auth-token i denne version (edge rapporterer under bootstrap).
    TODO: Kræv edge JWT-token i næste sprint.
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
    inv.python_version          = payload.get("python_version")
    inv.app_version             = payload.get("app_version")
    if "venv_packages" in payload:
        inv.venv_packages       = json.dumps(payload["venv_packages"])

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

    # Sæt app_version på Device-record også
    device = db.query(Device).filter_by(device_id=device_id).first()
    if device and payload.get("app_version"):
        device.app_version = payload["app_version"]

    db.commit()
    return {"status": "ok", "device_id": device_id}


# ── CMDB list / detail ────────────────────────────────────────────────────────

@router.get("/")
def list_cmdb(db: Session = Depends(get_db)):
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
            "hostname":             inv.hostname,
            "location_id":          inv.location_id,
            "inventory_reported_at": inv.inventory_reported_at.isoformat() if inv.inventory_reported_at else None,
            "provisioned_at":       inv.provisioned_at.isoformat() if inv.provisioned_at else None,
            "provisioned_by":       inv.provisioned_by,
            "gpg_fingerprint":      inv.gpg_fingerprint,
            "notes":                inv.notes,
            # Fra Device-tabellen
            "status":               device.status if device else "unknown",
            "customer_name":        device.customer_name if device else None,
            "site_name":            device.site_name if device else None,
            "ip_address":           device.ip_address if device else None,
            "last_seen":            device.last_seen.isoformat() if device and device.last_seen else None,
            "break_glass_count":    bg_count,
        })
    return result


@router.get("/{device_id}")
def get_cmdb(device_id: str, db: Session = Depends(get_db)):
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

    return {
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
        "python_version":           inv.python_version,
        "app_version":              inv.app_version,
        "venv_packages":            packages,
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
        "status":                   device.status if device else "unknown",
        "customer_name":            device.customer_name if device else None,
        "site_name":                device.site_name if device else None,
        "ip_address":               device.ip_address if device else None,
        "last_seen":                device.last_seen.isoformat() if device and device.last_seen else None,
    }


@router.put("/{device_id}")
def update_cmdb(device_id: str, payload: dict, db: Session = Depends(get_db)):
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
def create_break_glass(device_id: str, payload: dict, db: Session = Depends(get_db)):
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
def list_break_glass(device_id: str, db: Session = Depends(get_db)):
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
def checkout_break_glass(device_id: str, payload: dict, db: Session = Depends(get_db)):
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
def delete_break_glass(device_id: str, account_id: int, db: Session = Depends(get_db)):
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
