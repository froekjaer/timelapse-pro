#!/usr/bin/env python3
"""
cleanup_stale_credentials.py — Identify and cleanup stale credentials in TimeLapse Pro

Formål:
1. Identificer stale credentials (gammel HMAC, inactive devices, expired tokens)
2. Vis rapport over hvad der bør revokeres/migreres
3. (Valgfri) Udfør faktisk cleanup med confirmation

Se GO_LIVE_CHECKLIST_v10.md P0-07 og RISK_ASSESSMENT_v10.md for kontekst.

Brug:
    python3 cleanup_stale_credentials.py [--dry-run] [--older-than DAYS] [--execute]

Environment:
    Kræver DATABASE_URL eller at der køres mod aktiv headend database.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from argparse import ArgumentParser
from typing import List, Dict, Any

# Tilføj headend til path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker, Session
    from database import KeyCredential, Device, User, CapturedToken
except ImportError as e:
    print(f"ERROR: Kunne ikke importere database moduler: {e}")
    print("Sørg for at scriptet køres fra timelapse-pro root med venv aktiveret")
    sys.exit(1)


# ── Konfiguration ────────────────────────────────────────────────────────────────

DEFAULT_STALE_DAYS = 30  # Credentials inactive i 30+ dage er stale


# ── Farver til terminal ───────────────────────────────────────────────────────────
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log_info(msg: str):
    print(f"{Colors.GREEN}[INFO]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")


def log_section(msg: str):
    print(f"\n{Colors.BOLD}=== {msg} ==={Colors.RESET}")


def log_subsection(msg: str):
    print(f"\n{Colors.BLUE}--- {msg} ---{Colors.RESET}")


# ── Credential analyse ─────────────────────────────────────────────────────────────

def get_database_url() -> str:
    """Hent DATABASE_URL fra miljø eller .env fil."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Prøv at læse fra .env fil
        env_file = "/opt/timelapse/headend/.env"
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        db_url = line.strip().split("=", 1)[1]
                        break
    if not db_url:
        raise RuntimeError("DATABASE_URL ikke fundet — sæt environment variabel eller kør fra headend server")
    return db_url


def analyze_stale_credentials(db: Session, older_than_days: int) -> Dict[str, Any]:
    """Analyser database for stale credentials."""

    stale_candidates = []
    stale_devices = []
    auto_revoke_candidates = []

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    # 1. Stale API/SSH credentials (KeyCredential)
    log_subsection("KeyCredential analysis")
    creds = db.query(KeyCredential).filter(
        KeyCredential.status == "active",
        KeyCredential.last_used_at < cutoff
    ).all()

    for cred in creds:
        candidate = {
            "type": "KeyCredential",
            "credential_id": cred.credential_id,
            "entity_type": cred.entity_type,
            "entity_id": cred.entity_id,
            "key_type": cred.key_type,
            "last_used": cred.last_used_at,
            "last_used_days_ago": (datetime.now(timezone.utc) - cred.last_used_at).days if cred.last_used_at else None,
            "created": cred.created_at,
            "auto_revoke": False,  # Default, opdateres nedenfor
            "reason": ""
        }

        # Marker for auto-revoke hvis secondary/backup credential
        if cred.key_type in ["ssh", "api"] and cred.label and "secondary" in cred.label.lower():
            candidate["auto_revoke"] = True
            candidate["reason"] = "Secondary credential (kan auto-revokeres)"
            auto_revoke_candidates.append(candidate)
        else:
            candidate["reason"] = f"Inaktiv i {candidate['last_used_days_ago']} dage"
            stale_candidates.append(candidate)

        log_info(f"  {cred.key_type}/{cred.entity_type}/{cred.entity_id}: last_used {cred.last_used_at}")

    # 2. Stale/inactive devices
    log_subsection("Device analysis")
    devices = db.query(Device).filter(
        Device.last_heartbeat < cutoff
    ).all()

    for device in devices:
        stale_device = {
            "device_id": device.device_id,
            "name": device.label or device.device_id,
            "last_heartbeat": device.last_heartbeat,
            "last_heartbeat_days_ago": (datetime.now(timezone.utc) - device.last_heartbeat).days if device.last_heartbeat else None,
            "auth_token": device.auth_token,
            "auth_token_secret": device.auth_token_secret,
        }
        stale_devices.append(stale_device)
        log_info(f"  {device.device_id}: last_heartbeat {device.last_heartbeat}")

    # 3. Stale captured tokens (hvis tabellen eksisterer)
    try:
        log_subsection("CapturedToken analysis")
        tokens = db.query(CapturedToken).filter(
            CapturedToken.expires_at < datetime.now(timezone.utc)
        ).all()

        for token in tokens:
            log_info(f"  Udløbet token for device {token.device_id}: expires {token.expires_at}")
    except Exception:
        log_warn("CapturedToken analyse sprunget over (tabel eksisterer måske ikke)")

    return {
        "stale_credentials": stale_candidates,
        "stale_devices": stale_devices,
        "auto_revoke_candidates": auto_revoke_candidates,
        "cutoff_date": cutoff,
        "older_than_days": older_than_days
    }


def print_report(analysis: Dict[str, Any]):
    """Print en pæn rapport af analysen."""

    log_section("Stale Credential Report")

    stale_creds = analysis["stale_credentials"]
    stale_devices = analysis["stale_devices"]
    auto_revoke = analysis["auto_revoke_candidates"]

    print(f"\nCutoff date: {analysis['cutoff_date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Older than: {analysis['older_than_days']} days")

    # Stale credentials
    log_subsection(f"Stale Credentials ({len(stale_creds)})")
    if not stale_creds:
        log_info("Ingen stale credentials fundet")
    else:
        for cred in stale_creds:
            print(f"\n  Credential ID: {cred['credential_id']}")
            print(f"  Type: {cred['key_type']}")
            print(f"  Entity: {cred['entity_type']}/{cred['entity_id']}")
            print(f"  Last used: {cred['last_used']} ({cred['last_used_days_ago']} days ago)")
            print(f"  Reason: {cred['reason']}")

    # Stale devices
    log_subsection(f"Stale Devices ({len(stale_devices)})")
    if not stale_devices:
        log_info("Ingen stale devices fundet")
    else:
        for device in stale_devices:
            print(f"\n  Device ID: {device['device_id']}")
            print(f"  Name: {device['name']}")
            print(f"  Last heartbeat: {device['last_heartbeat']} ({device['last_heartbeat_days_ago']} days ago)")
            print(f"  Has auth_token: {'Yes' if device['auth_token'] else 'No'}")
            print(f"  Has HMAC secret: {'Yes' if device['auth_token_secret'] else 'No'}")

    # Auto-revoke candidates
    log_subsection(f"Auto-Revoke Candidates ({len(auto_revoke)})")
    if not auto_revoke:
        log_info("Ingen auto-revoke candidates (sekundære credentials)")
    else:
        for cred in auto_revoke:
            print(f"\n  Credential ID: {cred['credential_id']}")
            print(f"  Type: {cred['key_type']}")
            print(f"  Entity: {cred['entity_type']}/{cred['entity_id']}")
            print(f"  Last used: {cred['last_used']}")
            print(f"  Reason: {cred['reason']}")

    # Samlet konklusion
    log_section("Summary")
    total_issues = len(stale_creds) + len(stale_devices) + len(auto_revoke)
    if total_issues == 0:
        log_info(f"✅ INGEN STALE CREDENTIALS FUNDET (>{analysis['older_than_days']} dage)")
    else:
        log_warn(f"⚠️  FANDT {total_issues} potentielle problemer:")
        log_warn(f"   - {len(stale_creds)} stale credentials")
        log_warn(f"   - {len(stale_devices)} stale devices")
        log_warn(f"   - {len(auto_revoke)} auto-revoke candidates")


def execute_cleanup(db: Session, analysis: Dict[str, Any], dry_run: bool = True):
    """Udfør cleanup — revoke credentials og tokens."""

    if dry_run:
        log_section("[DRY-RUN] Cleanup Execution")
        log_info("Ingen ændringer vil blive udført (brug --execute for faktisk cleanup)")
        return

    log_section("Cleanup Execution")
    log_warn("Dette vil REVOKE credentials og kan påvirke systemet!")
    response = input("Er du sikker på du vil fortsætte? (yes/no): ")
    if response.lower() != "yes":
        log_info("Cleanup afbrudt")
        return

    # Revoke auto-revoke candidates
    for cred_dict in analysis["auto_revoke_candidates"]:
        cred = db.query(KeyCredential).filter_by(credential_id= cred_dict["credential_id"]).first()
        if cred:
            cred.status = "revoked"
            cred.revoked_at = datetime.now(timezone.utc)
            cred.revoked_by = "cleanup_stale_credentials.py"
            cred.revoke_reason = cred_dict["reason"]
            log_info(f"Revokerede credential {cred.credential_id}")

    db.commit()
    log_info(f"✅ Cleanup færdig: {len(analysis['auto_revoke_candidates'])} credentials revokeret")


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    parser = ArgumentParser(
        description="Identificer og cleanup stale credentials i TimeLapse Pro"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Vis hvad der ville blive gjort uden at udføre det (default)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Udfør faktisk cleanup (kræver explicit confirmation)"
    )
    parser.add_argument(
        "--older-than",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"Credientials inaktive i mere end N dage (default: {DEFAULT_STALE_DAYS})"
    )

    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    log_section("TimeLapse Pro Stale Credential Cleanup")

    try:
        # Opret database forbindelse
        db_url = get_database_url()
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        # Kør analyse
        analysis = analyze_stale_credentials(db, args.older_than)

        # Print rapport
        print_report(analysis)

        # Udfør cleanup (hvis ikke dry-run)
        execute_cleanup(db, analysis, args.dry_run)

        db.close()

    except Exception as e:
        log_error(f"Fejl under cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
