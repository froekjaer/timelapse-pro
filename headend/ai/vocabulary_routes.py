"""AI Vocabulary + Review routes — Sprint D"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from ai.repositories import TagRepository, AnalysisRepository

vocab_router = APIRouter(prefix="/api/ai/vocabulary", tags=["ai-vocabulary"])
vocab_read_router = APIRouter(prefix="/api/ai/vocabulary", tags=["ai-vocabulary"])


class MergeTagsPayload(BaseModel):
    source_tag_ids: list[int]
    canonical_tag: str
    category: str | None = None

class UpdateTranslationPayload(BaseModel):
    display_name_da: str | None = None
    display_name_en: str | None = None

@vocab_router.get("/pending")
def pending(db: Session = Depends(get_db)):
    return TagRepository(db).get_pending_review()

@vocab_read_router.get("/translations")
def translations(db: Session = Depends(get_db)):
    """Tag → dansk visningsnavn — bruges af kundevendt UI til at vise danske
    tag-labels i stedet for de rå engelske kanoniske nøgler. Cachevenlig — ændrer
    sig kun når et tag godkendes/rettes, ikke ved hver billedanalyse.
    """
    return TagRepository(db).get_tag_translations()

@vocab_router.put("/{tag_id}/translation")
def update_translation(tag_id: int, payload: UpdateTranslationPayload, db: Session = Depends(get_db)):
    """Admin retter AI's danske/engelske oversættelsesforslag for et tag."""
    TagRepository(db).update_translation(tag_id, payload.display_name_da, payload.display_name_en)
    return {"ok": True}

@vocab_router.post("/{tag_id}/approve")
def approve(tag_id: int, category: str = None, db: Session = Depends(get_db)):
    TagRepository(db).approve_tag(tag_id, category)
    return {"ok": True}

@vocab_router.post("/{tag_id}/reject")
def reject(tag_id: int, db: Session = Depends(get_db)):
    TagRepository(db).reject_tag(tag_id)
    return {"ok": True}

@vocab_router.get("/statistics")
def statistics(db: Session = Depends(get_db)):
    return TagRepository(db).get_statistics()

@vocab_router.get("/similar")
def similar(limit: int = 50, threshold: float = 0.72, db: Session = Depends(get_db)):
    return TagRepository(db).get_similar_tag_suggestions(limit=limit, threshold=threshold)

@vocab_router.post("/merge")
def merge(payload: MergeTagsPayload, db: Session = Depends(get_db)):
    return TagRepository(db).merge_tags(
        source_tag_ids=payload.source_tag_ids,
        canonical_tag=payload.canonical_tag,
        category=payload.category,
    )

@vocab_router.get("/co-occurring/{tag}")
def co_occurring(tag: str, db: Session = Depends(get_db)):
    return TagRepository(db).co_occurring_tags(tag)

@vocab_router.get("/ai-similar")
def ai_similar(limit: int = 30, db: Session = Depends(get_db)):
    """Find semantisk lignende tags via lokal AI (llama3.2:latest)."""
    from ai.tag_similarity_ai import get_ai_similar_tags
    return get_ai_similar_tags(db, limit=limit)
