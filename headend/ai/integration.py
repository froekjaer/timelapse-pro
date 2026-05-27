"""
TimeLapse Pro — AI Integration til headend
==========================================
Indeholder:
  - DB-migration (ai_result, ai_analyzed_at kolonner)
  - Sidecar JSON opdatering med AI-resultat
  - Async baggrundskø til analyse af nye captures
  - FastAPI endpoints

Brug i main.py:
  from ai.integration import setup_ai, ai_router, run_ai_migration

  # I startup():
  run_ai_migration(engine)

  # Efter app er defineret:
  setup_ai(app)
  app.include_router(ai_router)
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

log = logging.getLogger("headend.ai")

# ── DB Migration ──────────────────────────────────────────────────────────────

def run_ai_migration(engine) -> None:
    """
    Tilføj ai_result og ai_analyzed_at kolonner til captures-tabellen.
    Kør ved startup — idempotent, fejler ikke hvis kolonner allerede findes.
    """
    from sqlalchemy import text
    new_cols = [
        ("ai_result",      "TEXT"),       # JSON fra OllamaService.as_dict()
        ("ai_analyzed_at", "DATETIME"),   # Tidsstempel for analyse
    ]
    with engine.connect() as conn:
        for col, typ in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE captures ADD COLUMN {col} {typ}"))
                conn.commit()
                log.info("DB migration: captures.%s tilføjet", col)
            except Exception:
                pass  # Kolonnen findes allerede


# ── Sidecar opdatering ────────────────────────────────────────────────────────

def update_sidecar_with_ai(image_path: Path, ai_result: dict) -> bool:
    """
    Tilføj ai_analysis-sektion til eksisterende sidecar JSON.

    Sidecar ligger ved siden af billedet: {filnavn}.json
    Opretter sidecar med kun AI-data hvis den ikke eksisterer endnu.

    Returns True ved succes.
    """
    sidecar_path = image_path.with_suffix(".json")

    # Indlæs eksisterende sidecar eller start med tom dict
    existing = {}
    if sidecar_path.exists():
        try:
            existing = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Kunne ikke parse sidecar %s: %s", sidecar_path.name, e)

    # Tilføj AI-sektion
    existing["ai_analysis"] = {
        "analyzed_at":   datetime.now(timezone.utc).isoformat(),
        "model":         ai_result.get("model"),
        "scene_dk":      ai_result.get("scene_dk"),
        "tags":          ai_result.get("tags", []),
        "new_tags":      ai_result.get("new_tags", []),
        "quality_flag":  ai_result.get("quality_flag"),
        "change_detected": ai_result.get("change_detected", False),
        "probable_cause": ai_result.get("probable_cause"),
        "confidence":    ai_result.get("confidence"),
        "description":   ai_result.get("description"),
        "is_anomaly":    ai_result.get("is_anomaly"),
        "alarm":         ai_result.get("alarm"),
        "action":        ai_result.get("action"),
        "used_thumbnail": ai_result.get("used_thumbnail", False),
        "latency_ms":    ai_result.get("latency_ms"),
    }

    try:
        sidecar_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.debug("Sidecar opdateret med AI: %s", sidecar_path.name)
        return True
    except Exception as e:
        log.warning("Kunne ikke skrive sidecar %s: %s", sidecar_path.name, e)
        return False


# ── Async analyse-kø ──────────────────────────────────────────────────────────

_analysis_queue: queue.Queue = queue.Queue(maxsize=500)
_worker_thread:  Optional[threading.Thread] = None
OLLAMA_PLAY_MODE_KEY = "peter-vil-gerne-lege-med-ollama"
_last_play_mode_log = 0.0
_ollama_analysis_lock = threading.Lock()


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "ja"}


def _open_webui_priority_enabled(get_db_fn) -> bool:
    try:
        from ai.settings_helper import get_setting

        db_gen = get_db_fn()
        db = next(db_gen)
        try:
            return _is_truthy(get_setting(db, OLLAMA_PLAY_MODE_KEY, "false"))
        finally:
            db_gen.close()
    except Exception as exc:
        log.debug("AI: kunne ikke læse Ollama-prioritet: %s", exc)
        return False


def _load_vocabulary(get_db_fn):
    from ai.tag_vocabulary import TagVocabulary
    vocab = TagVocabulary(get_db_fn)
    return vocab, vocab.get_approved_by_category(), set(vocab.get_approved_tags())


def _analysis_payload(result) -> dict:
    return {
        "scene_dk": result.scene_dk,
        "tags": result.approved_tags,
        "new_tags": result.new_tags,
        "change_detected": result.change_detected,
        "change_summary": result.change_summary,
        "change_tags": result.change_tags,
        "quality_flag": result.quality_flag,
        "quality_ok": result.quality_ok,
        "has_gdpr_data": result.has_gdpr_data,
        "gdpr_detections": [
            {
                "type": item.detection_type,
                "detail": item.detail,
                "bbox": item.bounding_box,
            }
            for item in result.gdpr_detections
        ],
        "model": result.model,
        "duration_ms": result.duration_ms,
        "raw_response": result.raw_response,
    }


def _worker(get_db_fn, find_image_fn):
    """
    Baggrundstråd der analyserer captures fra køen.
    Kører som daemon — stopper automatisk ved shutdown.
    """
    from ai.ollama_service import OllamaVisionService; get_ollama_service = lambda *a, **kw: OllamaVisionService(*a, **kw)
    from ai.alarm_engine import AlarmEngine, run_alarm_migration

    log.info("AI analyse-worker startet")
    while True:
        if _open_webui_priority_enabled(get_db_fn):
            global _last_play_mode_log
            now = time.monotonic()
            if now - _last_play_mode_log > 60:
                log.info("AI: Timelapse-analyse pauset; Open WebUI har Ollama-prioritet")
                _last_play_mode_log = now
            time.sleep(10)
            continue

        try:
            capture_id = _analysis_queue.get(timeout=5)
        except queue.Empty:
            continue

        try:
            from database import Capture

            db_gen = get_db_fn()
            db = next(db_gen)
            try:
                capture = db.query(Capture).filter_by(id=capture_id).first()
                if not capture:
                    continue
                if capture.ai_result:
                    continue  # Allerede analyseret
                device_id = capture.device_id
                filename = capture.filename
                captured_at = capture.captured_at
            finally:
                db_gen.close()

            image_path = find_image_fn(device_id, filename)
            if not image_path:
                log.debug("AI: billede ikke fundet for capture %d", capture_id)
                continue

            svc = get_ollama_service()
            if not svc.health_check():
                log.debug("AI: Ollama ikke tilgængelig — springer over capture %d", capture_id)
                continue

            vocab, vocabulary_by_cat, approved_tag_set = _load_vocabulary(get_db_fn)
            with _ollama_analysis_lock:
                result = svc.analyse(
                    image_path=image_path,
                    vocabulary_by_cat=vocabulary_by_cat,
                    approved_tag_set=approved_tag_set,
                )
            payload = _analysis_payload(result)
            tags = result.approved_tags + result.new_tags

            db_gen = get_db_fn()
            db = next(db_gen)
            try:
                capture = db.query(Capture).filter_by(id=capture_id).first()
                if capture:
                    capture.ai_result      = json.dumps(payload, ensure_ascii=False)
                    capture.ai_tags        = json.dumps(tags, ensure_ascii=False)
                    capture.ai_analyzed_at = datetime.now(timezone.utc)
                    db.commit()

                    try:
                        alarm_engine = AlarmEngine(db)
                        alarm_engine.evaluate(
                            capture_id  = capture_id,
                            device_id   = device_id,
                            ai_result   = payload,
                            tags        = tags,
                            captured_at = captured_at,
                        )
                    except Exception as _ae:
                        log.debug("Alarm engine fejl: %s", _ae)
            except Exception:
                db.rollback()
                raise
            finally:
                db_gen.close()

            vocab.record_usage(result.approved_tags, result.new_tags)
            update_sidecar_with_ai(image_path, payload)

            log.info(
                "AI: capture=%d %s → %d tags, quality=%s, change=%s, %dms",
                capture_id, filename, len(tags), result.quality_flag,
                result.change_detected, result.duration_ms,
            )

        except Exception as e:
            log.exception("AI worker fejl for capture %d: %s", capture_id, e)
        finally:
            _analysis_queue.task_done()


def queue_capture_for_analysis(capture_id: int) -> None:
    """Læg et capture i AI-analysekøen. Non-blocking."""
    try:
        _analysis_queue.put_nowait(capture_id)
    except queue.Full:
        log.warning("AI kø fuld — springer over capture %d", capture_id)


def setup_ai(get_db_fn, find_image_fn) -> None:
    """
    Start AI baggrundstråd.
    Kald fra main.py startup efter DB er klar.

    Args:
        get_db_fn:     get_db generator fra main.py
        find_image_fn: _find_image funktion fra main.py
    """
    global _worker_thread
    _worker_thread = threading.Thread(
        target=_worker,
        args=(get_db_fn, find_image_fn),
        daemon=True,
        name="ai-worker",
    )
    _worker_thread.start()
    log.info("AI analyse-worker klar")


# ── FastAPI endpoints ─────────────────────────────────────────────────────────

ai_router = APIRouter(prefix="/api/ai", tags=["AI"])


def _get_db_dep():
    """Placeholder — overskrives i setup_ai_router()."""
    raise NotImplementedError


def setup_ai_router(get_db_fn, find_image_fn):
    """
    Konfigurér AI-router med de rigtige afhængigheder fra main.py.
    Kald én gang ved startup.
    """
    from ai.ollama_service import OllamaVisionService; get_ollama_service = lambda *a, **kw: OllamaVisionService(*a, **kw)
    from ai.alarm_engine import AlarmEngine, run_alarm_migration

    @ai_router.get("/status")
    def ai_status():
        """Ollama status og tilgængelige modeller."""
        svc = get_ollama_service()
        return {
            "ollama_running": len(svc.list_models()) > 0,
            "vision_ready":   svc.health_check(),
            "models":         svc.list_models(),
            "queue_size":     _analysis_queue.qsize(),
            "open_webui_priority": _open_webui_priority_enabled(get_db_fn),
        }

    @ai_router.get("/ollama-priority")
    def get_ollama_priority(db: Session = Depends(get_db_fn)):
        """Hent driftsprioritet for lokal Ollama."""
        from ai.settings_helper import get_setting

        enabled = _is_truthy(get_setting(db, OLLAMA_PLAY_MODE_KEY, "false"))
        return {
            "key": OLLAMA_PLAY_MODE_KEY,
            "open_webui_priority": enabled,
            "timelapse_ai_paused": enabled,
            "mode": "open_webui" if enabled else "timelapse",
            "queue_size": _analysis_queue.qsize(),
        }

    @ai_router.put("/ollama-priority")
    def set_ollama_priority(payload: dict, db: Session = Depends(get_db_fn)):
        """Sæt om Open WebUI midlertidigt må prioriteres over Timelapse AI."""
        from ai.settings_helper import set_setting

        enabled = bool(payload.get("open_webui_priority", False))
        set_setting(db, OLLAMA_PLAY_MODE_KEY, "true" if enabled else "false", "ui")
        return {
            "key": OLLAMA_PLAY_MODE_KEY,
            "open_webui_priority": enabled,
            "timelapse_ai_paused": enabled,
            "mode": "open_webui" if enabled else "timelapse",
            "queue_size": _analysis_queue.qsize(),
        }

    @ai_router.post("/analyze/{capture_id}")
    def analyze_capture(capture_id: int, db: Session = Depends(get_db_fn)):
        """Tving AI-analyse af et specifikt capture (synkront)."""
        from database import Capture
        capture = db.query(Capture).filter_by(id=capture_id).first()
        if not capture:
            raise HTTPException(status_code=404, detail="Capture ikke fundet")
        device_id = capture.device_id
        filename = capture.filename
        blur_score = capture.blur_score
        quality_flag = capture.quality_flag
        quality_passed = capture.quality_passed
        db.rollback()

        image_path = find_image_fn(device_id, filename)
        if not image_path:
            raise HTTPException(status_code=404, detail="Billedfil ikke fundet på disk")

        svc = get_ollama_service()
        if not svc.health_check():
            raise HTTPException(status_code=503, detail="Ollama ikke tilgængelig")

        vocab, vocabulary_by_cat, approved_tag_set = _load_vocabulary(get_db_fn)
        with _ollama_analysis_lock:
            result = svc.analyse(
                image_path=image_path,
                vocabulary_by_cat=vocabulary_by_cat,
                approved_tag_set=approved_tag_set,
            )
        payload = _analysis_payload(result)
        tags = result.approved_tags + result.new_tags

        capture = db.query(Capture).filter_by(id=capture_id).first()
        if capture:
            capture.ai_result      = json.dumps(payload, ensure_ascii=False)
            capture.ai_tags        = json.dumps(tags, ensure_ascii=False)
            capture.ai_analyzed_at = datetime.now(timezone.utc)
            db.commit()
        vocab.record_usage(result.approved_tags, result.new_tags)

        update_sidecar_with_ai(image_path, payload)

        return {
            "capture_id": capture_id,
            "filename":   filename,
            "opencv": {
                "blur_score":    blur_score,
                "quality_flag":  quality_flag,
                "quality_passed": quality_passed,
            },
            "ai": payload,
        }

    @ai_router.get("/result/{capture_id}")
    def get_ai_result(capture_id: int, db: Session = Depends(get_db_fn)):
        """Hent gemt AI-resultat for et capture."""
        from database import Capture
        capture = db.query(Capture).filter_by(id=capture_id).first()
        if not capture:
            raise HTTPException(status_code=404, detail="Capture ikke fundet")
        if not capture.ai_result:
            raise HTTPException(status_code=404, detail="Ingen AI-analyse endnu")
        return {
            "capture_id":    capture_id,
            "ai_analyzed_at": capture.ai_analyzed_at.isoformat() if capture.ai_analyzed_at else None,
            "ai":            json.loads(capture.ai_result),
        }

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

    @ai_router.get("/tags/search")
    def search_by_tags(
        tags:         str,
        device_id:    Optional[str] = None,
        device_ids:   Optional[str] = None,
        date_from:    Optional[str] = None,
        date_to:      Optional[str] = None,
        limit:        int = 500,
        db: Session = Depends(get_db_fn),
    ):
        """Søg billeder efter AI-tags. ?tags=crane,car"""
        from database import Capture
        import json as _json

        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if not tag_list:
            raise HTTPException(status_code=400, detail="Angiv mindst ét tag")

        from datetime import datetime as _dt, timedelta as _td
        q = db.query(Capture).filter(Capture.ai_tags.isnot(None))

        # Multi-device filter
        all_devs = []
        if device_ids:
            all_devs = [d.strip() for d in device_ids.split(",") if d.strip()]
        elif device_id:
            all_devs = [device_id]
        if all_devs:
            q = q.filter(Capture.device_id.in_(all_devs))

        # Dato filter i SQL
        if date_from:
            try: q = q.filter(Capture.captured_at >= _dt.fromisoformat(date_from))
            except Exception: pass
        if date_to:
            try: q = q.filter(Capture.captured_at < _dt.fromisoformat(date_to) + _td(days=1))
            except Exception: pass

        captures = q.order_by(Capture.captured_at.desc()).limit(limit * 3).all()

        results = []
        for c in captures:
            try:
                c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
                if any(t in c_tags for t in tag_list):
                    results.append({
                        "id":             c.id,
                        "device_id":      c.device_id,
                        "filename":       c.filename,
                        "captured_at":    c.captured_at.isoformat() if c.captured_at else None,
                        "tags":           c_tags,
                        "blur_score":     c.blur_score,
                        "quality_passed": c.quality_passed,
                        "ai_result":      c.ai_result,
                        "filesize_mb":    round(c.filesize / 1e6, 1) if c.filesize else None,
                    })
            except Exception:
                pass
            if len(results) >= limit:
                break

        return {"query": tag_list, "total": len(results), "results": results}

    @ai_router.get("/tags/all")
    def all_tags(device_id: Optional[str] = None, db: Session = Depends(get_db_fn)):
        """Returner alle kendte tags med antal — merger gammel ai_tags + ny vocabulary."""
        from database import Capture
        from sqlalchemy import text
        import json as _json
        from collections import Counter

        tag_counter: Counter = Counter()

        # 1. Gammel ai_tags kolonne
        q = db.query(Capture.ai_tags).filter(Capture.ai_tags.isnot(None))
        if device_id:
            q = q.filter(Capture.device_id == device_id)
        for (tags_json,) in q.all():
            try:
                for t in _json.loads(tags_json):
                    tag_counter[t] += 1
            except Exception:
                pass

        # 2. Ny capture_tags tabel (Sprint D)
        try:
            vocab_q = """
                SELECT tv.tag, tv.count
                FROM ai_tag_vocabulary tv
                WHERE tv.approved = TRUE AND tv.rejected = FALSE AND tv.count > 0
                ORDER BY tv.count DESC
                LIMIT 200
            """
            rows = db.execute(text(vocab_q)).fetchall()
            for tag, count in rows:
                tag_counter[tag] = max(tag_counter.get(tag, 0), count)
        except Exception:
            pass

        total = sum(1 for _ in db.query(Capture.id).filter(Capture.ai_tags.isnot(None)).all())
        return {
            "total_tagged": total,
            "tags": [{"tag": t, "count": c} for t, c in tag_counter.most_common(200)],
        }

    @ai_router.get("/flagged")
    def ai_flagged(
        limit: int = 20,
        device_id: Optional[str] = None,
        db: Session = Depends(get_db_fn),
    ):
        """Captures med AI-anomalier eller alarmer."""
        from database import Capture
        q = db.query(Capture).filter(Capture.ai_result.isnot(None))
        if device_id:
            q = q.filter_by(device_id=device_id)
        captures = q.order_by(Capture.id.desc()).limit(limit * 5).all()

        results = []
        for c in captures:
            try:
                ai = json.loads(c.ai_result)
                if ai.get("is_anomaly") or ai.get("alarm"):
                    results.append({
                        "capture_id":  c.id,
                        "device_id":   c.device_id,
                        "filename":    c.filename,
                        "captured_at": c.captured_at.isoformat() if c.captured_at else None,
                        "ai":          ai,
                    })
            except Exception:
                pass
            if len(results) >= limit:
                break

        return {"total": len(results), "results": results}
