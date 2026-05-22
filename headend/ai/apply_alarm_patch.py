"""
TimeLapse Pro — Alarm API Endpoints + Integration Patches
===========================================================

TRIN 1: Kopiér alarm_engine.py til headend/ai/alarm_engine.py

TRIN 2: Kør dette script for at patche integration.py og main.py:
  python headend/ai/apply_alarm_patch.py

TRIN 3: Tilføj PostgreSQL tabel (kører automatisk ved headend-restart,
        men kan køres manuelt for at undgå at vente):
  psql timelapse_db -c "
    CREATE TABLE IF NOT EXISTS alarm_events (
        id               SERIAL PRIMARY KEY,
        rule_id          TEXT NOT NULL,
        rule_name        TEXT,
        severity         TEXT NOT NULL,
        capture_id       INTEGER,
        device_id        TEXT,
        description      TEXT,
        matched_on       TEXT,
        confidence       REAL,
        triggered_at     TIMESTAMP NOT NULL DEFAULT NOW(),
        acknowledged_at  TIMESTAMP,
        acknowledged_by  TEXT,
        notes            TEXT
    );"
"""

# ══════════════════════════════════════════════════════════════════════════════
# Alarm API Endpoints — tilføj til setup_ai_router() i integration.py
# ══════════════════════════════════════════════════════════════════════════════

ALARM_ENDPOINTS = '''
    # ── Alarm endpoints ───────────────────────────────────────────────────────

    @ai_router.get("/alarms")
    def list_alarms(
        device_id:    Optional[str] = None,
        severity:     Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit:        int = 50,
        db: Session = Depends(get_db_fn),
    ):
        """
        Hent alarm-events, nyeste først.
        ?severity=critical|warning|maintenance
        ?acknowledged=false → kun ubehandlede
        """
        from sqlalchemy import text as _text
        conditions = ["1=1"]
        params     = {}
        if device_id:
            conditions.append("device_id = :device_id")
            params["device_id"] = device_id
        if severity:
            conditions.append("severity = :severity")
            params["severity"] = severity
        if acknowledged is False:
            conditions.append("acknowledged_at IS NULL")
        elif acknowledged is True:
            conditions.append("acknowledged_at IS NOT NULL")

        where = " AND ".join(conditions)
        rows  = db.execute(_text(f"""
            SELECT id, rule_id, rule_name, severity, capture_id, device_id,
                   description, matched_on, confidence, triggered_at,
                   acknowledged_at, acknowledged_by, notes
            FROM alarm_events
            WHERE {where}
            ORDER BY triggered_at DESC
            LIMIT :limit
        """), {**params, "limit": limit}).fetchall()

        return [
            {
                "id":             r[0],
                "rule_id":        r[1],
                "rule_name":      r[2],
                "severity":       r[3],
                "capture_id":     r[4],
                "device_id":      r[5],
                "description":    r[6],
                "matched_on":     json.loads(r[7]) if r[7] else [],
                "confidence":     r[8],
                "triggered_at":   r[9].isoformat() if r[9] else None,
                "acknowledged_at": r[10].isoformat() if r[10] else None,
                "acknowledged_by": r[11],
                "notes":           r[12],
            }
            for r in rows
        ]

    @ai_router.post("/alarms/{alarm_id}/acknowledge")
    def acknowledge_alarm(
        alarm_id: int,
        payload:  dict = {},
        db: Session = Depends(get_db_fn),
    ):
        """Kvitter en alarm som behandlet."""
        from sqlalchemy import text as _text
        from datetime import datetime, timezone
        db.execute(_text("""
            UPDATE alarm_events
            SET acknowledged_at = :ts, acknowledged_by = :by, notes = :notes
            WHERE id = :id
        """), {
            "id":    alarm_id,
            "ts":    datetime.now(timezone.utc),
            "by":    payload.get("by", "system"),
            "notes": payload.get("notes"),
        })
        db.commit()
        return {"status": "ok", "alarm_id": alarm_id}

    @ai_router.get("/alarms/rules/{device_id}")
    def get_alarm_rules(device_id: str, db: Session = Depends(get_db_fn)):
        """Vis merged alarm-regler for en enhed (til debug og UI)."""
        from ai.alarm_engine import AlarmEngine
        engine = AlarmEngine(db)
        rules  = engine.get_rules_for_device(device_id)
        return {"device_id": device_id, "rules": rules, "total": len(rules)}

    @ai_router.put("/alarms/rules/global")
    def update_global_alarm_rules(payload: dict, db: Session = Depends(get_db_fn)):
        """
        Opdater globale alarm-regler i config_defaults.
        Body: {"rules": [{...}, ...]}
        Regler merges med DEFAULT_ALARM_RULES per ID.
        """
        from database import ConfigDefaults
        from ai.alarm_engine import _merge_rules, DEFAULT_ALARM_RULES
        defaults = db.query(ConfigDefaults).first()
        if not defaults:
            raise HTTPException(status_code=404, detail="config_defaults ikke fundet")

        new_rules    = payload.get("rules", [])
        merged       = _merge_rules(DEFAULT_ALARM_RULES, new_rules)
        defaults.alarm_rules = json.dumps(merged, ensure_ascii=False)
        db.commit()
        return {"status": "ok", "rules_count": len(merged)}

    @ai_router.get("/alarms/summary")
    def alarm_summary(db: Session = Depends(get_db_fn)):
        """Hurtig opsummering til dashboard: antal alarmer per severity."""
        from sqlalchemy import text as _text
        rows = db.execute(_text("""
            SELECT severity, COUNT(*) as total,
                   SUM(CASE WHEN acknowledged_at IS NULL THEN 1 ELSE 0 END) as unacked
            FROM alarm_events
            GROUP BY severity
        """)).fetchall()
        return {
            r[0]: {"total": r[1], "unacknowledged": r[2]}
            for r in rows
        }
'''


# ══════════════════════════════════════════════════════════════════════════════
# Patch-script — kør direkte
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import shutil
    from pathlib import Path
    from datetime import datetime

    ROOT        = Path(__file__).parent.parent.parent
    INTEGRATION = ROOT / "headend" / "ai" / "integration.py"
    MAIN_PY     = ROOT / "headend" / "main.py"

    print("\n╔══════════════════════════════════════════════╗")
    print("║  TimeLapse Pro — Alarm System Patch         ║")
    print("╚══════════════════════════════════════════════╝\n")

    # ── Patch integration.py ──────────────────────────────────────────────────
    print("── headend/ai/integration.py ──")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(INTEGRATION, INTEGRATION.with_suffix(f".py.bak_{ts}"))
    print(f"  ✓ Backup: integration.py.bak_{ts}")

    content = INTEGRATION.read_text(encoding="utf-8")

    # Import alarm_engine
    if "alarm_engine" not in content:
        old = "from ai.ollama_service import get_ollama_service"
        new = "from ai.ollama_service import get_ollama_service\nfrom ai.alarm_engine import AlarmEngine, run_alarm_migration"
        if old in content:
            content = content.replace(old, new)
            print("  ✓ alarm_engine import tilføjet")
        else:
            print("  ⚠ Import-linje ikke fundet")

    # run_alarm_migration i run_ai_migration
    if "run_alarm_migration" not in content:
        old = 'log.info("DB migration: captures.%s tilføjet", col)'
        new = 'log.info("DB migration: captures.%s tilføjet", col)\n    run_alarm_migration(engine)'
        if old in content:
            content = content.replace(old, new, 1)
            print("  ✓ run_alarm_migration tilføjet")
        else:
            print("  ⚠ Migration-kald ikke fundet — tilføj run_alarm_migration(engine) manuelt i run_ai_migration()")

    # Tilføj alarm endpoints i setup_ai_router
    if "/alarms" not in content:
        # Find slutningen af setup_ai_router og indsæt endpoints
        old = "\n    @ai_router.get(\"/tags/search\")"
        new = ALARM_ENDPOINTS + "\n    @ai_router.get(\"/tags/search\")"
        if old in content:
            content = content.replace(old, new)
            print("  ✓ Alarm endpoints tilføjet")
        else:
            print("  ⚠ Indsætningspunkt for alarm endpoints ikke fundet")
    else:
        print("  · Alarm endpoints allerede tilføjet")

    INTEGRATION.write_text(content, encoding="utf-8")
    print("  ✓ integration.py gemt\n")

    # ── Patch AI worker i integration.py ──────────────────────────────────────
    print("── AI worker alarm-integration ──")
    content = INTEGRATION.read_text(encoding="utf-8")

    if "AlarmEngine" not in content or "evaluate" not in content:
        # Tilføj alarm-evaluering i _worker() efter sidecar-opdatering
        old = '            update_sidecar_with_ai(image_path, result.as_dict())\n\n            if result.alarm:'
        new = '''            update_sidecar_with_ai(image_path, result.as_dict())

            # Evaluér alarm-regler
            try:
                alarm_engine = AlarmEngine(db)
                tags_json = capture.ai_tags
                tags = json.loads(tags_json) if tags_json else []
                alarm_engine.evaluate(
                    capture_id  = capture_id,
                    device_id   = capture.device_id,
                    ai_result   = result.as_dict(),
                    tags        = tags,
                    captured_at = capture.captured_at,
                )
            except Exception as _ae:
                log.debug("Alarm engine fejl: %s", _ae)

            if result.alarm:'''
        if old in content:
            content = content.replace(old, new)
            INTEGRATION.write_text(content, encoding="utf-8")
            print("  ✓ Alarm-evaluering tilføjet i AI worker")
        else:
            print("  ⚠ AI worker alarm-integration ikke fundet — tilføj manuelt")
    else:
        print("  · Alarm-evaluering allerede i worker")

    # ── PostgreSQL tabel ──────────────────────────────────────────────────────
    print("\n── PostgreSQL ──")
    import subprocess
    result = subprocess.run([
        "/opt/homebrew/bin/psql", "timelapse_db", "-c", """
        CREATE TABLE IF NOT EXISTS alarm_events (
            id               SERIAL PRIMARY KEY,
            rule_id          TEXT NOT NULL,
            rule_name        TEXT,
            severity         TEXT NOT NULL,
            capture_id       INTEGER,
            device_id        TEXT,
            description      TEXT,
            matched_on       TEXT,
            confidence       REAL,
            triggered_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            acknowledged_at  TIMESTAMP,
            acknowledged_by  TEXT,
            notes            TEXT
        );
        ALTER TABLE config_defaults ADD COLUMN IF NOT EXISTS alarm_rules TEXT;
        """
    ], capture_output=True, text=True)
    if result.returncode == 0:
        print("  ✓ alarm_events tabel og alarm_rules kolonne klar")
    else:
        print(f"  ⚠ psql fejl: {result.stderr.strip()}")
        print("  Kør manuelt:")
        print("  /opt/homebrew/bin/psql timelapse_db -c \"CREATE TABLE IF NOT EXISTS alarm_events (id SERIAL PRIMARY KEY, rule_id TEXT NOT NULL, rule_name TEXT, severity TEXT NOT NULL, capture_id INTEGER, device_id TEXT, description TEXT, matched_on TEXT, confidence REAL, triggered_at TIMESTAMP NOT NULL DEFAULT NOW(), acknowledged_at TIMESTAMP, acknowledged_by TEXT, notes TEXT);\"")

    print("\n═" * 48)
    print("✓ Alarm system patch færdig\n")
    print("Næste skridt:")
    print("  1. Genstart headend")
    print("  2. Test: curl http://localhost:8000/api/ai/alarms/summary")
    print("  3. Se regler: curl 'http://localhost:8000/api/ai/alarms/rules/TL-C87FF9587CA0'")
