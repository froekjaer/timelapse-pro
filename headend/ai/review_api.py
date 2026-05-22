"""
TimeLapse Pro — Review & Feedback API Endpoints
================================================
Endpoints til admin-gennemgang af eskalerede billeder
og manuel korrektions-workflow.

Monteres i main.py:
    from ai.review_api import review_router
    app.include_router(review_router)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from ai.feedback_manager import (
    EscalationManager, CorrectionsManager, PromptOptimizer, ESCALATION_RULES
)
# get_ai_router importeres lazy i _run_gemini_for_approved

review_router = APIRouter(prefix="/api/review", tags=["review"])


# =============================================================================
# ESKALERINGS-ENDPOINTS
# =============================================================================

@review_router.get("/escalation/pending")
def get_escalation_queue(
    location_id: Optional[str] = None,
    date_filter: Optional[date] = None,
    limit:       int = 100,
    db: Session  = Depends(get_db),
):
    """
    Hent billeder der afventer admin-godkendelse til Gemini-eskalering.
    Sorteret efter usikkerhedsscore (højest først).
    """
    items = EscalationManager(db).get_pending(
        location_id=location_id,
        date_filter=date_filter,
        limit=limit,
    )
    return {
        "count": len(items),
        "items": [
            {
                "analysis_id":       i.analysis_id,
                "capture_id":        i.capture_id,
                "filename":          i.filename,
                "captured_at":       i.captured_at.isoformat(),
                "location_id":       i.location_id,
                "scene_dk":          i.scene_dk,
                "escalation_score":  round(i.escalation_score, 3),
                "escalation_reasons": i.escalation_reasons,
                "current_tags":      i.current_tags,
                "quality_flag":      i.quality_flag,
                "change_detected":   i.change_detected,
            }
            for i in items
        ],
    }


class EscalationAction(BaseModel):
    analysis_ids: list[int]
    admin_id:     str = "admin"


@review_router.post("/escalation/approve")
def approve_escalations(
    payload: EscalationAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Godkend udvalgte billeder til Gemini-analyse.
    Analysen køres i baggrunden.
    """
    EscalationManager(db).approve_batch(payload.analysis_ids, payload.admin_id)

    # Kør Gemini-analyse i baggrunden
    background_tasks.add_task(
        _run_gemini_for_approved,
        analysis_ids=payload.analysis_ids,
    )

    return {
        "approved": len(payload.analysis_ids),
        "message":  f"Gemini analyserer {len(payload.analysis_ids)} billeder i baggrunden",
    }


@review_router.post("/escalation/reject")
def reject_escalations(payload: EscalationAction, db: Session = Depends(get_db)):
    """Afvis eskalering — billederne behøver ikke Gemini."""
    EscalationManager(db).reject_batch(payload.analysis_ids, payload.admin_id)
    return {"rejected": len(payload.analysis_ids)}


@review_router.get("/escalation/stats")
def escalation_stats(days: int = 7, db: Session = Depends(get_db)):
    """Eskalerings-statistik til dashboard."""
    stats = EscalationManager(db).get_stats(days=days)
    return {
        **stats,
        "rules": ESCALATION_RULES,
    }


async def _run_gemini_for_approved(analysis_ids: list[int]):
    """Baggrundsjob: kald Gemini for godkendte analyser."""
    from database import SessionLocal
    from ai.gemini_service import GeminiVisionService
    from ai.repositories import TagRepository
    from pathlib import Path
    import os

    db = SessionLocal()
    try:
        gemini = GeminiVisionService()
        esc_manager = EscalationManager(db)
        tag_repo    = TagRepository(db)
        from ai.ai_router import get_ai_router; router = get_ai_router()

        approved = esc_manager.get_approved_for_gemini(limit=len(analysis_ids) + 10)

        vocab_by_cat  = tag_repo.get_approved_by_category()
        approved_set  = set(tag_repo.get_approved_tags())

        for item in approved:
            try:
                image_path = router._resolve_image_path(item["filename"])
                if not image_path:
                    continue

                result = gemini.analyse(
                    image_path        = image_path,
                    vocabulary_by_cat = vocab_by_cat,
                    approved_tag_set  = approved_set,
                )

                esc_manager.save_gemini_result(
                    analysis_id  = item["analysis_id"],
                    gemini_model = result.model,
                    tags         = result.approved_tags,
                    scene_dk     = result.scene_dk,
                    raw_result   = result.raw_response,
                )

                # Merge Gemini-tags ind i capture_tags
                tag_repo.upsert_capture_tags(
                    capture_id    = item["capture_id"],
                    analysis_id   = item["analysis_id"],
                    approved_tags = result.approved_tags,
                    new_tags      = result.new_tags,
                )

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    "Gemini fejl for analyse %d: %s", item["analysis_id"], e
                )
    finally:
        db.close()


# =============================================================================
# KORREKTIONS-ENDPOINTS
# =============================================================================

@review_router.get("/day/{review_date}")
def get_day_for_review(
    review_date:    date,
    location_id:    Optional[str] = None,
    only_escalated: bool = False,
    limit:          int = 200,
    db: Session     = Depends(get_db),
):
    """
    Hent alle analyserede captures for en dag — klar til gennemgang.
    Inkluderer nuværende tags, analyse-resultat og eventuelle korrektioner.
    """
    captures = CorrectionsManager(db).get_day_captures(
        review_date    = review_date,
        location_id    = location_id,
        only_escalated = only_escalated,
        limit          = limit,
    )
    return {
        "date":     str(review_date),
        "count":    len(captures),
        "captures": [
            {
                "capture_id":      c.capture_id,
                "filename":        c.filename,
                "captured_at":     c.captured_at.isoformat(),
                "location_id":     c.location_id,
                "scene_dk":        c.scene_dk,
                "current_tags":    c.current_tags,
                "quality_flag":    c.quality_flag,
                "quality_ok":      c.quality_ok,
                "change_detected": c.change_detected,
                "should_escalate": c.should_escalate,
                "gemini_tags":     c.gemini_tags,
                "corrected_tags":  c.corrected_tags,
                "correction_id":   c.correction_id,
                "is_corrected":    c.correction_id is not None,
            }
            for c in captures
        ],
    }


class SessionCreate(BaseModel):
    session_date: date
    admin_id:     str = "admin"
    location_id:  Optional[str] = None
    notes:        Optional[str] = None


@review_router.post("/session/start")
def start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """Opret en ny korrektions-session."""
    session_id = CorrectionsManager(db).start_session(
        session_date = payload.session_date,
        admin_id     = payload.admin_id,
        location_id  = payload.location_id,
        notes        = payload.notes,
    )
    return {"session_id": session_id}


class CorrectionPayload(BaseModel):
    capture_id:             int
    session_id:             int
    admin_id:               str = "admin"
    corrected_tags:         list[str]
    corrected_quality_flag: str
    corrected_quality_ok:   bool
    corrected_scene:        Optional[str] = None
    corrected_change:       Optional[bool] = None
    notes:                  Optional[str] = None


@review_router.post("/correction")
def save_correction(payload: CorrectionPayload, db: Session = Depends(get_db)):
    """Gem manuel korrektion for ét capture."""
    correction_id = CorrectionsManager(db).save_correction(
        capture_id            = payload.capture_id,
        session_id            = payload.session_id,
        admin_id              = payload.admin_id,
        corrected_tags        = payload.corrected_tags,
        corrected_quality_flag= payload.corrected_quality_flag,
        corrected_quality_ok  = payload.corrected_quality_ok,
        corrected_scene       = payload.corrected_scene,
        corrected_change      = payload.corrected_change,
        notes                 = payload.notes,
    )
    return {"correction_id": correction_id}


@review_router.post("/session/{session_id}/complete")
def complete_session(
    session_id:      int,
    generate_examples: bool = True,
    db: Session      = Depends(get_db),
):
    """
    Afslut korrektions-session.
    Genererer automatisk few-shot eksempler til prompt-optimering.
    """
    stats = CorrectionsManager(db).complete_session(session_id)

    examples_created = 0
    if generate_examples:
        examples_created = PromptOptimizer(db).generate_examples(min_occurrences=2)

    return {
        **stats,
        "examples_generated": examples_created,
        "message": (
            f"Session afsluttet. "
            f"{examples_created} nye prompt-eksempler genereret."
            if examples_created else
            "Session afsluttet. Ikke nok korrektioner til nye eksempler endnu."
        ),
    }


# =============================================================================
# STATISTIK OG FREMGANG
# =============================================================================

@review_router.get("/stats/accuracy")
def accuracy_trend(days: int = 30, db: Session = Depends(get_db)):
    """
    Model-nøjagtighed over tid baseret på korrektioner.
    Viser om modellen forbedres efter prompt-opdateringer.
    """
    return PromptOptimizer(db).get_accuracy_trend(days=days)


@review_router.get("/stats/corrections")
def correction_stats(days: int = 30, db: Session = Depends(get_db)):
    """Tag-korrektions-statistik — hvilke tags glemmes/fejltagges oftest."""
    return CorrectionsManager(db).get_correction_stats(days=days)


@review_router.get("/prompt-examples")
def get_prompt_examples(location_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Vis aktive few-shot eksempler der bruges i prompts."""
    examples = PromptOptimizer(db).get_active_examples(location_id=location_id, limit=50)
    return {"count": len(examples), "examples": examples}


@review_router.post("/prompt-examples/generate")
def generate_examples(
    min_occurrences: int = 3,
    location_id:     Optional[str] = None,
    db: Session      = Depends(get_db),
):
    """Manuel trigger af prompt-optimering."""
    count = PromptOptimizer(db).generate_examples(
        min_occurrences=min_occurrences,
        location_id=location_id,
    )
    return {"examples_generated": count}
