"""
TimeLapse Pro — Notifications API Endpoints
============================================
Tilføj til headend/main.py.

Endpoints:
  GET  /api/admin/notifications        → hent config (password maskeret)
  PUT  /api/admin/notifications        → gem config
  POST /api/admin/notifications/test   → send test-notifikation
"""

# Indsæt disse endpoints i main.py — f.eks. efter /api/admin/settings endpoints


NOTIFICATIONS_ENDPOINTS = '''
# ── Notifications ─────────────────────────────────────────────────────────────

@app.get("/api/admin/notifications")
def get_notifications(db: Session = Depends(get_db)):
    """Hent notifikations-konfiguration. Password returneres maskeret."""
    try:
        row = db.execute(text("SELECT value FROM settings WHERE key='notifications'")).fetchone()
        if not row:
            return {}
        cfg = json.loads(row[0])
        # Maskér passwords
        if "email" in cfg and "password" in cfg["email"]:
            cfg["email"]["password"] = "••••••••••••••••" if cfg["email"]["password"] else ""
        if "sms" in cfg and "api_token" in cfg["sms"]:
            cfg["sms"]["api_token"] = "••••••••" if cfg["sms"]["api_token"] else ""
        return cfg
    except Exception as e:
        log.error("Notifications get fejl: %s", e)
        return {}


@app.put("/api/admin/notifications")
def update_notifications(payload: dict, db: Session = Depends(get_db)):
    """
    Gem notifikations-konfiguration.
    Maskerede passwords (•) bevares fra eksisterende config.
    """
    try:
        # Hent eksisterende config for at bevare passwords
        row = db.execute(text("SELECT value FROM settings WHERE key='notifications'")).fetchone()
        existing = json.loads(row[0]) if row else {}

        # Bevar passwords der ikke er ændret (indeholder •)
        if "email" in payload and "password" in payload["email"]:
            if "•" in payload["email"]["password"]:
                payload["email"]["password"] = existing.get("email", {}).get("password", "")
        if "sms" in payload and "api_token" in payload["sms"]:
            if "•" in payload["sms"]["api_token"]:
                payload["sms"]["api_token"] = existing.get("sms", {}).get("api_token", "")

        value = json.dumps(payload, ensure_ascii=False, indent=2)
        if row:
            db.execute(text("UPDATE settings SET value=:v WHERE key='notifications'"), {"v": value})
        else:
            db.execute(text("INSERT INTO settings (key, value) VALUES ('notifications', :v)"), {"v": value})
        db.commit()
        log.info("Notifications config opdateret")
        return {"status": "ok"}
    except Exception as e:
        log.error("Notifications update fejl: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/notifications/test")
def test_notification(payload: dict, db: Session = Depends(get_db)):
    """
    Send test-notifikation.
    Body: {"channel": "email"} | {"channel": "sms"} | {"channel": "teams"}
    """
    channel = payload.get("channel", "email")

    row = db.execute(text("SELECT value FROM settings WHERE key='notifications'")).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ingen notifikations-konfiguration fundet")

    config = json.loads(row[0])
    config["min_severity"] = "info"  # Test sendes altid uanset severity

    test_alarm = {
        "rule_name":    "Test notifikation",
        "rule_id":      "test",
        "severity":     "info",
        "device_id":    "TL-TEST",
        "description":  "Dette er en test-notifikation fra TimeLapse Pro. Systemet fungerer korrekt.",
        "matched_on":   ["test:manual"],
        "confidence":   1.0,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "capture_id":   None,
    }

    try:
        from ai.notify import send_email, send_sms, send_teams
        result = False
        if channel == "email":
            result = send_email(test_alarm, config)
        elif channel == "sms":
            result = send_sms(test_alarm, config)
        elif channel == "teams":
            result = send_teams(test_alarm, config)
        else:
            raise HTTPException(status_code=400, detail=f"Ukendt kanal: {channel}")

        return {"status": "ok" if result else "failed", "channel": channel}
    except Exception as e:
        log.error("Test notifikation fejl: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
'''

if __name__ == "__main__":
    import shutil
    from pathlib import Path
    from datetime import datetime

    ROOT    = Path(__file__).parent.parent.parent
    MAIN_PY = ROOT / "headend" / "main.py"

    print("\n── Notifications API Patch ──")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(MAIN_PY, MAIN_PY.with_suffix(f".py.bak_{ts}"))

    content = MAIN_PY.read_text(encoding="utf-8")

    if "/api/admin/notifications" in content:
        print("· Notifications endpoints allerede tilføjet")
    else:
        # Indsæt før SIEM-sektionen eller sidst i admin-endpoints
        target = "\n# ── Alarm endpoints"
        if target not in content:
            target = "\n@app.get(\"/api/ai/status\")"
        if target in content:
            content = content.replace(target, "\n" + NOTIFICATIONS_ENDPOINTS + "\n" + target)
            MAIN_PY.write_text(content, encoding="utf-8")
            print("✓ Notifications endpoints tilføjet i main.py")
        else:
            print("⚠ Indsætningspunkt ikke fundet — tilføj manuelt")
