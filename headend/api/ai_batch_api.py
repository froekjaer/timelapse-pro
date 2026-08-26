# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — ai_batch_api.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Gemini Batch API — bulk AI re-analysis at ~50% of normal price.

Montér i main.py:
    from api.ai_batch_api import router as ai_batch_router, start_ai_batch_background_loop
    app.include_router(ai_batch_router)
    # in startup(), replacing the old inline threading.Thread(...) call:
    start_ai_batch_background_loop(interval_minutes)

Endpoints:
    POST /api/admin/ai-batch/start
    GET  /api/admin/ai-batch/jobs

Extracted from main.py (2026-08-26, Phase 1 of the main.py modularization
plan — see /Users/peter/.claude/plans/twinkling-toasting-treehouse.md).
Self-contained domain: an async spin-off of the synchronous post-processing
queue, used only on explicit admin request, backed by the AiBatchJob DB
table (not a module-level lock/dict like some of the other Phase 3
candidates) plus a background poller thread that checks Google for job
completion every few minutes.

require_role comes from auth.py at module scope (Phase 0). A few genuinely
main.py-wide utilities this domain still needs (_ensure_capture_device_access,
_get_setting, _allowed_capture_device_ids, _find_image — each used broadly
across main.py, not specific to this domain) are lazy-imported per function,
matching the same idiom already used elsewhere for non-auth main.py
dependencies.
"""
from __future__ import annotations

import json
import json as _json
import logging
import threading as _threading
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import AiBatchJob, Capture, SessionLocal, get_db, now_utc
from auth import require_role

log = logging.getLogger("headend")

router = APIRouter(tags=["AI Batch"])


# ── Gemini Batch API — bulk AI-genanalyse til ~50% af normal pris ────────────
# Asynkront spor, separat fra den synkrone post-processing-kø ovenfor.
# Bruges KUN ved eksplicit anmodning — aldrig automatisk, og påvirker ikke
# den løbende live capture-pipeline.

@router.post("/api/admin/ai-batch/start")
def start_ai_batch_job(
    payload: dict,
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """Start et Gemini Batch-job — vælger captures efter samme kriterier som
    post-processing (device_id, limit, force_ai), men sender dem som ÉT
    asynkront batch-job til Google i stedet for den synkrone live-kø.
    """
    from main import _ensure_capture_device_access, _get_setting, _allowed_capture_device_ids
    force_ai = bool(payload.get("force_ai", False))
    limit_raw = payload.get("limit")
    limit = max(1, int(limit_raw)) if limit_raw not in (None, "", 0, "0") else None
    device_id = str(payload.get("device_id") or "").strip() or None
    notify_on_complete = bool(payload.get("notify_on_complete", True))

    if device_id:
        _ensure_capture_device_access(db, current_user, device_id)

    from ai.ai_strategy import AIConfigManager
    cfg = AIConfigManager(db).get_config(customer_id=None, site_id=None)
    if not cfg.use_cloud:
        raise HTTPException(
            status_code=400,
            detail="Batch-mode kræver cloud_only eller local_then_cloud strategi (Gemini) — nuværende strategi bruger ikke cloud"
        )

    from ai.integration import _build_gemini_service
    svc = _build_gemini_service(get_db, cfg.cloud_model)
    if not svc:
        raise HTTPException(status_code=400, detail="Ingen Gemini API-nøgle konfigureret (Indstillinger → AI)")

    gcs_bucket = ""
    if getattr(svc, "is_vertex", False):
        gcs_bucket = _get_setting(db, "gemini_gcs_bucket", "").strip()
        if not gcs_bucket:
            raise HTTPException(
                status_code=400,
                detail="Vertex AI batch kræver et GCS-bucket — sæt 'gemini_gcs_bucket' i Indstillinger → AI"
            )
        # GDPR: bucket SKAL ligge i samme EU-region som Vertex-endpointet, ellers
        # brydes databehandlings-garantien på data-at-rest under batch-kørslen.
        # Delt guard (også brugt af ai_batch_submit.py CLI) — se
        # ai/gemini_service.validate_batch_bucket_region() for begrundelse/historik.
        from ai.gemini_service import validate_batch_bucket_region
        bucket_region = _get_setting(db, "gemini_gcs_bucket_region", "").strip()
        try:
            validate_batch_bucket_region(svc.location, bucket_region)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # NB (Fase 3, 2026-07-03): samme scope-afgrænsning som post-processing-jobbet
    # ovenfor — se den note for begrundelse.
    allowed_device_ids = _allowed_capture_device_ids(db, current_user)
    if allowed_device_ids is not None and not allowed_device_ids:
        raise HTTPException(status_code=400, detail="Ingen synlige enheder")
    allowed_list = list(allowed_device_ids) if allowed_device_ids is not None else None

    # Opret job-rækken med det samme (status=submitting) og returnér STRAKS.
    # Det tunge arbejde — find filer, byg kontekst pr. billede, base64-encode og
    # upload hele JSONL'en til Google — kan tage minutter for 26.000 billeder og
    # ville ellers ramme nginx' 60s timeout (504). Det kører nu i en baggrundstråd,
    # og UI'et følger status via /api/admin/ai-batch/jobs.
    job_id = str(_uuid.uuid4())
    db.add(AiBatchJob(
        id=job_id, gemini_job_name=None, status="submitting",
        capture_ids="[]", cloud_model=cfg.cloud_model, total_count=0,
        requested_by=current_user.username, notify_on_complete=notify_on_complete,
        submitted_at=now_utc(),
    ))
    db.commit()

    _cloud_model = cfg.cloud_model
    _username = current_user.username

    def _submit_ai_batch_bg():
        from database import Capture as _Cap, Device as _Dev
        from ai.capture_context import build_capture_context, format_context_block
        from ai.tag_vocabulary import TagVocabulary
        bg_gen = get_db(); bg = next(bg_gen)
        try:
            svc2 = _build_gemini_service(get_db, _cloud_model)
            if not svc2:
                raise RuntimeError("Ingen Gemini-credentials")
            q = bg.query(_Cap).filter(_Cap.filename.isnot(None))
            if allowed_list is not None:
                q = q.filter(_Cap.device_id.in_(allowed_list))
            if device_id:
                q = q.filter(_Cap.device_id == device_id)
            if not force_ai:
                q = q.filter(or_(_Cap.ai_result.is_(None), _Cap.ai_tags.is_(None)))
            q = q.order_by(_Cap.captured_at.desc(), _Cap.id.desc())
            if limit:
                q = q.limit(limit)
            caps = q.all()

            from main import _find_image
            items = []; missing = 0; ctx_by_key = {}; dev_cache = {}
            for cap in caps:
                path = _find_image(cap.device_id, cap.filename)
                if not path:
                    missing += 1; continue
                key = f"cap-{cap.id}"
                items.append((key, path, cap.id))
                try:
                    dev = dev_cache.get(cap.device_id)
                    if dev is None:
                        dev = bg.query(_Dev).filter_by(device_id=cap.device_id).first()
                        dev_cache[cap.device_id] = dev
                    ctx_by_key[key] = format_context_block(build_capture_context(bg, cap, dev))
                except Exception:
                    ctx_by_key[key] = ""

            if not items:
                bg.query(AiBatchJob).filter_by(id=job_id).update(
                    {"status": "failed", "error_message": "Ingen af billederne findes på disk"})
                bg.commit(); return

            vocab_by_cat = TagVocabulary(get_db).get_approved_by_category()
            job_name = svc2.submit_batch_job(
                items=[(k, p) for k, p, _c in items],
                vocabulary_by_cat=vocab_by_cat,
                display_name=f"timelapse-batch-{job_id[:8]}",
                gcs_bucket=gcs_bucket,
                context_by_key=ctx_by_key,
            )
            bg.query(AiBatchJob).filter_by(id=job_id).update({
                "gemini_job_name": job_name, "status": "submitted",
                "capture_ids": _json.dumps([c for _k, _p, c in items]),
                "total_count": len(items),
            })
            bg.commit()
            log.info("AI batch-job startet (baggrund): %s (%d billeder, %d manglede) af %s",
                     job_name, len(items), missing, _username)
        except Exception as exc:
            log.exception("AI batch-job (baggrund) fejlede")
            try:
                bg.query(AiBatchJob).filter_by(id=job_id).update(
                    {"status": "failed", "error_message": str(exc)[:500]})
                bg.commit()
            except Exception:
                pass
        finally:
            bg_gen.close()

    _threading.Thread(target=_submit_ai_batch_bg, daemon=True,
                      name=f"ai-batch-submit-{job_id[:8]}").start()
    return {
        "id": job_id, "status": "submitting",
        "message": "Batch-job oprettes i baggrunden — følg status under AI-batch jobs.",
    }


@router.get("/api/admin/ai-batch/jobs")
def list_ai_batch_jobs(
    _user=require_role("super_admin", "admin", "operator"),
    db: Session = Depends(get_db),
):
    """List de seneste 50 batch-jobs — til UI-oversigt."""
    jobs = db.query(AiBatchJob).order_by(AiBatchJob.created_at.desc()).limit(50).all()
    return [{
        "id": j.id,
        "gemini_job_name": j.gemini_job_name,
        "status": j.status,
        "total_count": j.total_count,
        "success_count": j.success_count,
        "error_count": j.error_count,
        "requested_by": j.requested_by,
        "cloud_model": j.cloud_model,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "submitted_at": j.submitted_at.isoformat() if j.submitted_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "error_message": j.error_message,
    } for j in jobs]


_BATCH_RUNNING_STATES = {"PENDING", "RUNNING", "JOB_STATE_PENDING", "JOB_STATE_RUNNING"}
_BATCH_SUCCESS_STATES = {"SUCCEEDED", "JOB_STATE_SUCCEEDED"}
_BATCH_FAILED_STATES  = {"FAILED", "JOB_STATE_FAILED"}
_BATCH_CANCELLED_STATES = {"CANCELLED", "JOB_STATE_CANCELLED"}
_BATCH_EXPIRED_STATES = {"EXPIRED", "JOB_STATE_EXPIRED"}


def _notify_batch_job(db, job: "AiBatchJob", status: str) -> None:
    if not job.notify_on_complete:
        return
    try:
        from ai.notify import notify_batch_complete
        duration_min = 0.0
        if job.submitted_at and job.completed_at:
            duration_min = (job.completed_at - job.submitted_at).total_seconds() / 60
        notify_batch_complete(db, {
            "status": status,
            "total": job.total_count,
            "success": job.success_count,
            "errors": job.error_count,
            "model": job.cloud_model,
            "requested_by": job.requested_by,
            "duration_min": duration_min,
        })
    except Exception as exc:
        log.debug("Batch notifikation fejl (ikke kritisk): %s", exc)


def _finalize_ai_batch_job(db, job: "AiBatchJob", svc, gemini_job) -> None:
    """Download og skriv resultater fra et succeeded batch-job tilbage til captures."""
    from ai.tag_vocabulary import TagVocabulary
    vocab = TagVocabulary(get_db)
    approved_set = set(vocab.get_approved_tags())

    try:
        results = svc.download_batch_results(gemini_job)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Resultat-download fejlede: {exc}"
        job.completed_at = now_utc()
        db.commit()
        _notify_batch_job(db, job, "failed")
        log.warning("Batch-job %s: download fejlede: %s", job.gemini_job_name, exc)
        return

    # AI Studio-jobs har "key" (fx "cap-123") i hvert resultat — match direkte.
    # Vertex-jobs har INGEN key (Vertex-konventionen er anderledes) — match i
    # stedet POSITIONELT mod capture_ids i den rækkefølge de blev submittet i,
    # da Vertex AI batch garanteret bevarer input-rækkefølgen i output.
    job_capture_ids = json.loads(job.capture_ids or "[]")
    uses_positional_matching = bool(results) and all(r.get("key") is None for r in results)
    if uses_positional_matching and len(results) != len(job_capture_ids):
        log.warning(
            "Batch-job %s: antal resultater (%d) matcher ikke antal submittede billeder (%d) — "
            "positionel matching kan være forskudt. Springer over for at undgå fejlmatch.",
            job.gemini_job_name, len(results), len(job_capture_ids),
        )

    success_count = 0
    error_count = 0
    for index, r in enumerate(results):
        if uses_positional_matching:
            if len(results) != len(job_capture_ids) or index >= len(job_capture_ids):
                error_count += 1
                continue
            capture_id = job_capture_ids[index]
        else:
            key = r.get("key") or ""
            if not key.startswith("cap-"):
                continue
            try:
                capture_id = int(key[len("cap-"):])
            except ValueError:
                continue
        capture = db.query(Capture).filter_by(id=capture_id).first()
        if not capture:
            continue
        if r.get("error") or not r.get("text"):
            error_count += 1
            continue
        try:
            result = svc.parse_batch_result_text(r["text"], approved_set)
            ai_payload = {
                "scene_dk": result.scene_dk,
                "tags": result.approved_tags,
                "new_tags": result.new_tags,
                "new_tags_da": getattr(result, "new_tags_da", {}),
                "change_detected": result.change_detected,
                "change_summary": result.change_summary,
                "change_tags": result.change_tags,
                "quality_flag": result.quality_flag,
                "quality_ok": result.quality_ok,
                "has_gdpr_data": result.has_gdpr_data,
                "gdpr_detections": [
                    {"type": g.detection_type, "detail": g.detail, "bbox": g.bounding_box}
                    for g in result.gdpr_detections
                ],
                "model": job.cloud_model,
                # 2026-07-04 (Claude, proveniens-UI task #28): batch-jobs kører altid
                # via Gemini/Vertex AI Batch API — aldrig lokal Ollama.
                "engine": "cloud",
                "duration_ms": result.duration_ms,
                "raw_response": result.raw_response,
            }
            # Bevar evt. eksisterende edge-QA under 'edge_ai', så batch-Gemini ikke
            # sletter den (samme som live-workeren gør).
            if capture.ai_result and "edge_ai" not in ai_payload:
                try:
                    _prev = _json.loads(capture.ai_result)
                    _edge_prev = _prev.get("edge_ai") if isinstance(_prev.get("edge_ai"), dict) else None
                    if _edge_prev:
                        ai_payload["edge_ai"] = _edge_prev
                    elif _prev.get("source") == "edge":
                        ai_payload["edge_ai"] = _prev
                except Exception:
                    pass
            tags = result.approved_tags + result.new_tags
            capture.ai_result = _json.dumps(ai_payload, ensure_ascii=False)
            capture.ai_tags = _json.dumps(tags, ensure_ascii=False)
            try:
                from ai.model_results import ENGINE_GEMINI_CLOUD, upsert_capture_model_result
                upsert_capture_model_result(
                    db,
                    capture_id=capture.id,
                    engine=ENGINE_GEMINI_CLOUD,
                    model=str(job.cloud_model or ai_payload.get("model") or ""),
                    result_kind="analysis",
                    result_json=ai_payload,
                    tags=tags,
                    confidence=float(ai_payload["confidence"]) if ai_payload.get("confidence") is not None else None,
                    source="gemini_batch",
                )
            except Exception as exc:
                log.debug("Kunne ikke gemme Gemini batch i capture_model_results for capture %d: %s", capture.id, exc)
            capture.ai_analyzed_at = now_utc()
            # Registrér brug + nye tags til godkendelse — manglede helt før denne fix,
            # så batch-opdagede tags forsvandt i stedet for at lande i Tag Review.
            vocab.record_usage(result.approved_tags, result.new_tags, getattr(result, "new_tags_da", None))
            success_count += 1
        except Exception as exc:
            log.warning("Batch resultat-parse fejl for capture %d: %s", capture_id, exc)
            error_count += 1

    db.commit()
    job.status = "succeeded"
    job.success_count = success_count
    job.error_count = error_count
    job.completed_at = now_utc()
    db.commit()
    log.info("AI batch-job %s færdig: %d ok, %d fejl", job.gemini_job_name, success_count, error_count)
    _notify_batch_job(db, job, "succeeded")


def _poll_one_ai_batch_job(db, job: "AiBatchJob") -> None:
    from ai.integration import _build_gemini_service
    svc = _build_gemini_service(get_db, job.cloud_model or "gemini-2.5-flash")
    if not svc:
        return
    try:
        status = svc.get_batch_status(job.gemini_job_name)
    except Exception as exc:
        log.warning("Kunne ikke hente batch-status %s: %s", job.gemini_job_name, exc)
        return

    state = status["state"]
    if state in _BATCH_RUNNING_STATES:
        changed = False
        if job.status != "running":
            job.status = "running"
            changed = True
        # Skriv løbende fremdrift hjem (Vertex completion_stats) → UI viser X/total %.
        prog = status.get("progress") or {}
        if prog:
            s = int(prog.get("success") or 0)
            e = int(prog.get("error") or 0)
            if job.success_count != s:
                job.success_count = s; changed = True
            if job.error_count != e:
                job.error_count = e; changed = True
        if changed:
            db.commit()
        return
    if state in _BATCH_SUCCESS_STATES:
        _finalize_ai_batch_job(db, job, svc, status["job"])
    elif state in _BATCH_FAILED_STATES:
        job.status = "failed"
        job.error_message = str(getattr(status["job"], "error", "ukendt fejl"))
        job.completed_at = now_utc()
        db.commit()
        _notify_batch_job(db, job, "failed")
    elif state in _BATCH_CANCELLED_STATES:
        job.status = "cancelled"
        job.completed_at = now_utc()
        db.commit()
    elif state in _BATCH_EXPIRED_STATES:
        job.status = "expired"
        job.error_message = "Job udløb efter 48 timer hos Google"
        job.completed_at = now_utc()
        db.commit()
        _notify_batch_job(db, job, "failed")


def _ai_batch_poller_loop(interval_minutes: float = 5.0) -> None:
    """Baggrundstråd — poller alle igangværende batch-jobs periodisk.
    Et job kan tage op til 24 timer hos Google, så hyppig polling er ufarlig
    (billig API-kald) men sjælden nok til ikke at spamme.
    """
    import time as _time_mod
    log.info("AI batch-job poller startet (interval=%.0fm)", interval_minutes)
    while True:
        try:
            db = SessionLocal()
            try:
                pending = db.query(AiBatchJob).filter(
                    AiBatchJob.status.in_(["submitted", "running"])
                ).all()
                for job in pending:
                    try:
                        _poll_one_ai_batch_job(db, job)
                    except Exception as exc:
                        log.warning("Fejl ved polling af batch-job %s: %s", job.gemini_job_name, exc)
            finally:
                db.close()
        except Exception as exc:
            log.warning("AI batch poller-loop fejl: %s", exc)
        _time_mod.sleep(interval_minutes * 60)



def start_ai_batch_background_loop(interval_minutes: float = 5.0) -> None:
    """Starts the AI batch-job poller thread. Same shape as itim.py's
    start_itim_collector() — the thread-start itself lives here, called once
    from main.py's startup(), inside the same try/except block that used to
    wrap the inline threading.Thread(...) call directly."""
    t = _threading.Thread(
        target=_ai_batch_poller_loop,
        args=(interval_minutes,),
        name="ai-batch-poller",
        daemon=True,
    )
    t.start()
