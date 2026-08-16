"""Oldest-first backlog sweep for missing thumbnails and missing AI tags.

Complements two existing mechanisms that both structurally miss imported/
legacy captures:

- `headend/main.py`'s `_thumbnail_auto_loop` only scans the 500 MOST RECENT
  captures (`captured_at DESC`). Imported historical photos keep their
  original EXIF timestamp, so they are permanently pushed out of that
  window by newer regular captures and are never reached.
- `headend/ai/integration.py`'s `recover_pending_captures` only runs ONCE
  per Headend restart (capped at 5000 rows). A stable, long-running
  production Headend restarts rarely, so a large historical backlog can
  take a very long time to drain through that path alone.

This module is deliberately **decision logic only** — no DB session, no
filesystem access, no AI-queue implementation. All I/O is injected as
callables so the caps/skip/backpressure behaviour is testable without a
real database, disk, or AI worker. The caller (headend/main.py) is
responsible for the SQLAlchemy query (oldest-first, bounded scan window)
and for gating the whole sweep behind the `legacy_backlog_sweep_enabled`
setting — disabled by default, since AI tagging can incur real cost
(cloud Gemini) or load (local Ollama) depending on the configured
strategy, and the size of a customer's historical backlog is unknown
ahead of time. See Dokumentation/HANDOVER_LOG.md, 2026-08-16 entry.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_MINUTES = 30.0
DEFAULT_THUMBNAIL_SCAN_LIMIT = 500
DEFAULT_THUMBNAIL_MAX_PER_RUN = 100
DEFAULT_AI_SCAN_LIMIT = 500
DEFAULT_AI_MAX_PER_RUN = 50


def sweep_thumbnails(
    candidates: list,
    *,
    find_image,
    thumbs_dir_for,
    generate_thumbnail,
    is_valid_jpeg,
    find_existing_thumbnail,
    max_per_run: int = DEFAULT_THUMBNAIL_MAX_PER_RUN,
) -> tuple[int, int]:
    """Generate missing thumbnails for an oldest-first candidate list.

    `candidates` are objects with `.device_id`/`.filename` (real Capture
    rows, or lightweight test doubles). Returns (generated, failed). Never
    raises for a single bad candidate — logs and continues, so one
    corrupt/missing file cannot stop the rest of the run.
    """
    generated = failed = 0
    for capture in candidates:
        if generated >= max_per_run:
            break
        try:
            image_path = find_image(capture.device_id, capture.filename)
            if not image_path:
                continue
            if find_existing_thumbnail(image_path):
                continue
            target = thumbs_dir_for(image_path) / image_path.name
            ok, error = generate_thumbnail(image_path, target)
            if ok and is_valid_jpeg(target):
                generated += 1
            else:
                failed += 1
                log.warning("legacy_backlog_sweep: thumbnail fejlede for %s: %s", capture.filename, error)
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the sweep
            failed += 1
            log.warning("legacy_backlog_sweep: uventet fejl ved thumbnail for %s: %s", capture.filename, exc)
    return generated, failed


def run_once(
    db,
    Capture,
    *,
    enabled: bool,
    thumbnail_lock_locked: bool,
    find_image,
    thumbs_dir_for,
    generate_thumbnail,
    is_valid_jpeg,
    find_existing_thumbnail,
    queue_capture_for_analysis,
    thumbnail_scan_limit: int = DEFAULT_THUMBNAIL_SCAN_LIMIT,
    thumbnail_max_per_run: int = DEFAULT_THUMBNAIL_MAX_PER_RUN,
    ai_scan_limit: int = DEFAULT_AI_SCAN_LIMIT,
    ai_max_per_run: int = DEFAULT_AI_MAX_PER_RUN,
) -> dict:
    """One full sweep pass: query oldest-first candidates and process them.
    Owns the SQLAlchemy querying so the caller (headend/main.py's loop) only
    needs to supply a session/model and the same helper functions the
    existing thumbnail/AI machinery already uses. Returns all-zero
    immediately when `enabled` is False — the caller is expected to compute
    that from the `legacy_backlog_sweep_enabled` setting."""
    result = {"thumbnails_generated": 0, "thumbnails_failed": 0, "ai_queued": 0, "ai_queue_full": 0}
    if not enabled:
        return result

    if not thumbnail_lock_locked:
        thumb_candidates = (
            db.query(Capture)
            .filter(Capture.filename.isnot(None))
            .order_by(Capture.captured_at.asc())
            .limit(thumbnail_scan_limit)
            .all()
        )
        result["thumbnails_generated"], result["thumbnails_failed"] = sweep_thumbnails(
            thumb_candidates,
            find_image=find_image,
            thumbs_dir_for=thumbs_dir_for,
            generate_thumbnail=generate_thumbnail,
            is_valid_jpeg=is_valid_jpeg,
            find_existing_thumbnail=find_existing_thumbnail,
            max_per_run=thumbnail_max_per_run,
        )

    ai_candidates = (
        db.query(Capture)
        .filter(Capture.filename.isnot(None), Capture.ai_tags.is_(None), Capture.ai_analyzed_at.is_(None))
        .order_by(Capture.captured_at.asc())
        .limit(ai_scan_limit)
        .all()
    )
    result["ai_queued"], result["ai_queue_full"] = sweep_ai_tags(
        ai_candidates,
        find_image=find_image,
        queue_capture_for_analysis=queue_capture_for_analysis,
        max_per_run=ai_max_per_run,
    )
    return result


# Settings-nøgler — alle læses fra DB hver runde (ikke env vars, ikke faste
# konstanter), så en admin kan ændre dem live fra Systemadministration uden
# en Headend-genstart. Se SystemAdminPage.tsx for UI-felterne.
SETTING_ENABLED = "legacy_backlog_sweep_enabled"
SETTING_INTERVAL_MINUTES = "legacy_backlog_sweep_interval_minutes"
SETTING_THUMBNAIL_SCAN_LIMIT = "legacy_backlog_sweep_thumbnail_scan_limit"
SETTING_THUMBNAIL_MAX_PER_RUN = "legacy_backlog_sweep_thumbnail_max_per_run"
SETTING_AI_SCAN_LIMIT = "legacy_backlog_sweep_ai_scan_limit"
SETTING_AI_MAX_PER_RUN = "legacy_backlog_sweep_ai_max_per_run"


def _read_number(get_setting, db, key: str, default, cast, floor):
    """Tolerant settings-parser: forkert/tomt input falder tilbage til
    default i stedet for at vælte baggrundstråden."""
    try:
        return max(floor, cast(get_setting(db, key, str(default))))
    except (TypeError, ValueError):
        return default


def run_forever(
    *,
    get_setting,
    thumbnail_lock,
    find_image,
    thumbs_dir_for,
    generate_thumbnail,
    is_valid_jpeg,
    find_existing_thumbnail,
    startup_delay_s: float = 240,
) -> None:
    """Background-thread entry point. Owns the session lifecycle and the
    sleep loop so headend/main.py only needs to wire up the handful of
    main.py-local helpers (thumbnail generation, `_get_setting`) that can't
    be imported cleanly from here without a circular dependency. Everything
    importable on its own (SessionLocal, Capture, queue_capture_for_analysis)
    is imported directly by this function instead of being injected. All
    tunables (interval, caps) are re-read from settings every iteration —
    an admin change takes effect on the next cycle, no restart needed."""
    import time as _t
    from database import SessionLocal, Capture
    from ai.integration import queue_capture_for_analysis

    _t.sleep(startup_delay_s)
    while True:
        interval_minutes = DEFAULT_INTERVAL_MINUTES
        try:
            db = SessionLocal()
            try:
                enabled = get_setting(db, SETTING_ENABLED, "false").lower() == "true"
                interval_minutes = _read_number(get_setting, db, SETTING_INTERVAL_MINUTES, DEFAULT_INTERVAL_MINUTES, float, 0.5)
                result = run_once(db, Capture, enabled=enabled, thumbnail_lock_locked=thumbnail_lock.locked(),
                    find_image=find_image, thumbs_dir_for=thumbs_dir_for, generate_thumbnail=generate_thumbnail,
                    is_valid_jpeg=is_valid_jpeg, find_existing_thumbnail=find_existing_thumbnail,
                    queue_capture_for_analysis=queue_capture_for_analysis,
                    thumbnail_scan_limit=_read_number(get_setting, db, SETTING_THUMBNAIL_SCAN_LIMIT, DEFAULT_THUMBNAIL_SCAN_LIMIT, int, 1),
                    thumbnail_max_per_run=_read_number(get_setting, db, SETTING_THUMBNAIL_MAX_PER_RUN, DEFAULT_THUMBNAIL_MAX_PER_RUN, int, 1),
                    ai_scan_limit=_read_number(get_setting, db, SETTING_AI_SCAN_LIMIT, DEFAULT_AI_SCAN_LIMIT, int, 1),
                    ai_max_per_run=_read_number(get_setting, db, SETTING_AI_MAX_PER_RUN, DEFAULT_AI_MAX_PER_RUN, int, 1))
                if any(result.values()):
                    log.info("Legacy backlog sweep: %s", result)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001 - a bad run must not kill the background thread
            log.warning("Legacy backlog sweep fejl: %s", exc)
        _t.sleep(interval_minutes * 60)


def sweep_ai_tags(
    candidates: list,
    *,
    find_image,
    queue_capture_for_analysis,
    max_per_run: int = DEFAULT_AI_MAX_PER_RUN,
) -> tuple[int, int]:
    """Queue oldest-first captures that have never been AI-analysed.

    Returns (queued, queue_full_hits). Stops as soon as the AI queue
    reports itself full once — no point hammering a full queue for the
    rest of this run; the next scheduled run will pick up where this one
    left off, since anything already queued/analysed drops out of the
    candidate list naturally.
    """
    queued = queue_full = 0
    for capture in candidates:
        if queued >= max_per_run:
            break
        try:
            image_path = find_image(capture.device_id, capture.filename)
            if not image_path:
                continue
            if queue_capture_for_analysis(capture.id):
                queued += 1
            else:
                queue_full += 1
                break
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the sweep
            log.warning("legacy_backlog_sweep: uventet fejl ved AI-kø for capture %s: %s", capture.id, exc)
    return queued, queue_full
