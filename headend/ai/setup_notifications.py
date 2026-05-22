#!/usr/bin/env python3
"""
TimeLapse Pro — Notifikations-opsætning
========================================
Konfigurerer Gmail (og valgfrit SMS/Teams) i headend-databasen,
og patcher alarm_engine.py til at sende notifikationer.

Kør fra timelapse-pro roden:
  python3 headend/ai/setup_notifications.py

Du bliver bedt om Gmail App Password under opsætningen.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "headend"))

import os
os.chdir(ROOT / "headend")

GREEN  = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"
CYAN   = "\033[96m"; BOLD   = "\033[1m";  RESET = "\033[0m"


def setup_config() -> dict:
    print(f"\n{BOLD}── Gmail konfiguration ──{RESET}")
    print("Du skal bruge dit Gmail App Password (16 tegn).")
    print("Hent det på: myaccount.google.com → Sikkerhed → App-adgangskoder\n")

    email  = input("Din Gmail-adresse:     ").strip()
    pwd    = input("Gmail App Password:    ").strip().replace(" ", "")
    to_raw = input("Send alarmer til (email, kommasepareret): ").strip()
    to     = [e.strip() for e in to_raw.split(",") if e.strip()]

    config = {
        "email": {
            "enabled":   True,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username":  email,
            "password":  pwd,
            "from":      f"TimeLapse Pro <{email}>",
            "to":        to,
        },
        "sms": {
            "enabled":   False,
            "provider":  "gatewayapi",
            "api_token": "",
            "sender":    "TimeLapse",
            "to":        [],
        },
        "teams": {
            "enabled":     False,
            "webhook_url": "",
        },
        "min_severity": "warning",
    }

    # Valgfri SMS
    print(f"\n{BOLD}── SMS via GatewayAPI (valgfrit) ──{RESET}")
    do_sms = input("Aktivér SMS? (j/N): ").strip().lower()
    if do_sms == "j":
        token  = input("GatewayAPI API token: ").strip()
        phones = input("Telefonnumre (+4512345678, kommasepareret): ").strip()
        config["sms"]["enabled"]   = True
        config["sms"]["api_token"] = token
        config["sms"]["to"]        = [p.strip() for p in phones.split(",") if p.strip()]

    # Valgfri Teams
    print(f"\n{BOLD}── Microsoft Teams (valgfrit) ──{RESET}")
    do_teams = input("Aktivér Teams webhook? (j/N): ").strip().lower()
    if do_teams == "j":
        webhook = input("Teams webhook URL: ").strip()
        config["teams"]["enabled"]     = True
        config["teams"]["webhook_url"] = webhook

    return config


def save_to_db(config: dict) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL", "postgresql://timelapse@localhost/timelapse_db")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    value = json.dumps(config, ensure_ascii=False, indent=2)
    existing = db.execute(text("SELECT id FROM settings WHERE key='notifications'")).fetchone()
    if existing:
        db.execute(text("UPDATE settings SET value=:v WHERE key='notifications'"), {"v": value})
    else:
        db.execute(text("INSERT INTO settings (key, value) VALUES ('notifications', :v)"), {"v": value})
    db.commit()
    print(f"  {GREEN}✓ Konfiguration gemt i database{RESET}")


def send_test_email(config: dict) -> None:
    """Send en test-email for at verificere opsætningen."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from notify import send_email

    test_alarm = {
        "rule_name":   "Test alarm",
        "rule_id":     "test",
        "severity":    "info",
        "device_id":   "TL-TEST",
        "description": "Dette er en test-alarm fra TimeLapse Pro. Hvis du modtager denne mail virker notifikations-systemet korrekt.",
        "matched_on":  ["test"],
        "confidence":  1.0,
        "triggered_at": "2026-05-14T12:00:00+00:00",
        "capture_id":  0,
    }
    config_with_info = dict(config)
    config_with_info["min_severity"] = "info"

    print(f"\n  Sender test-email til {config['email']['to']}...")
    ok = send_email(test_alarm, config_with_info)
    if ok:
        print(f"  {GREEN}✓ Test-email sendt — tjek din indbakke{RESET}")
    else:
        print(f"  {RED}✗ Test-email fejlede — tjek SMTP-indstillinger{RESET}")


def patch_alarm_engine() -> None:
    """Tilføj notify()-kald i alarm_engine._save_alarm_event()."""
    engine_path = ROOT / "headend" / "ai" / "alarm_engine.py"
    content     = engine_path.read_text(encoding="utf-8")

    if "from ai.notify import notify" in content:
        print(f"  · notify() allerede integreret i alarm_engine.py")
        return

    old = '        except Exception as e:\n            log.error("Kunne ikke gemme alarm: %s", e)'
    new = '''        except Exception as e:
            log.error("Kunne ikke gemme alarm: %s", e)
            return

        # Send notifikationer
        try:
            from ai.notify import notify
            notify(alarm, self._db)
        except Exception as ne:
            log.debug("Notifikations-fejl (ikke kritisk): %s", ne)'''

    if old in content:
        content = content.replace(old, new)
        engine_path.write_text(content, encoding="utf-8")
        print(f"  {GREEN}✓ notify() integreret i alarm_engine.py{RESET}")
    else:
        print(f"  {YELLOW}⚠ Indsætningspunkt ikke fundet — tilføj notify()-kald manuelt{RESET}")


def main():
    print(f"\n{BOLD}╔══════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║  TimeLapse Pro — Notifikations-opsætning    ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════╝{RESET}")

    config = setup_config()

    print(f"\n{BOLD}── Gemmer konfiguration ──{RESET}")
    try:
        save_to_db(config)
    except Exception as e:
        print(f"  {RED}✗ DB-fejl: {e}{RESET}")
        print(f"  Konfiguration (gem manuelt):")
        print(json.dumps(config, indent=2, ensure_ascii=False))
        sys.exit(1)

    print(f"\n{BOLD}── Patcher alarm_engine.py ──{RESET}")
    patch_alarm_engine()

    print(f"\n{BOLD}── Test ──{RESET}")
    do_test = input("Send test-email nu? (J/n): ").strip().lower()
    if do_test != "n":
        send_test_email(config)

    print(f"\n{GREEN}{BOLD}✓ Opsætning færdig{RESET}")
    print(f"\nNæste skridt:")
    print(f"  Genstart headend så nye indstillinger træder i kraft:")
    print(f"  sudo launchctl unload && load /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist")
    print()


if __name__ == "__main__":
    main()
