"""AI Vocabulary + Review routes — Sprint D"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from ai.repositories import TagRepository, AnalysisRepository

vocab_router = APIRouter(prefix="/api/ai/vocabulary", tags=["ai-vocabulary"])


class MergeTagsPayload(BaseModel):
    source_tag_ids: list[int]
    canonical_tag: str
    category: str | None = None

@vocab_router.get("/pending")
def pending(db: Session = Depends(get_db)):
    return TagRepository(db).get_pending_review()

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
