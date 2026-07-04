"""
TimeLapse Pro — AI & GDPR Database Models
==========================================
SQLAlchemy ORM-modeller til ai_analyses, capture_tags,
ai_tag_vocabulary og gdpr_detections.

ALDRIG importer gdpr-modeller i normale endpoints —
brug kun GDPRManager via ai_router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

# Genbruger Base fra headend/database.py
from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# TAG VOKABULAR
# =============================================================================

class AITagVocabulary(Base):
    __tablename__ = "ai_tag_vocabulary"

    id          = Column(Integer, primary_key=True)
    tag         = Column(String(100), unique=True, nullable=False, index=True)
    category    = Column(String(80), nullable=False, default="øvrige")
    count       = Column(Integer, default=0)
    first_seen  = Column(DateTime(timezone=True), default=_now)
    last_seen   = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    predefined  = Column(Boolean, default=False)
    approved    = Column(Boolean, default=True)
    rejected    = Column(Boolean, default=False)
    notes       = Column(Text)

    # Relations
    capture_links = relationship("CaptureTag", back_populates="tag_vocab", lazy="dynamic")

    def __repr__(self):
        status = "✓" if self.approved else ("✗" if self.rejected else "?")
        return f"<Tag {status} '{self.tag}' [{self.category}] ×{self.count}>"


# =============================================================================
# AI ANALYSE — én pr. capture
# =============================================================================

class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        UniqueConstraint("capture_id", name="uq_ai_analyses_capture"),
    )

    id                   = Column(Integer, primary_key=True)
    capture_id           = Column(Integer, ForeignKey("captures.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id          = Column(String(100), index=True)
    analysed_at          = Column(DateTime(timezone=True), default=_now, index=True)
    model_vision         = Column(String(100), nullable=False)
    model_version        = Column(String(50))
    duration_ms          = Column(Integer)

    # Billed-beskrivelse
    scene_dk             = Column(Text)
    change_detected      = Column(Boolean, default=False)
    change_summary       = Column(Text)

    # Kvalitet
    ai_quality_flag      = Column(String(50))
    ai_quality_ok        = Column(Boolean, default=True)

    # Reference til forrige billede (change detection)
    reference_capture_id = Column(Integer, ForeignKey("captures.id", ondelete="SET NULL"), nullable=True)

    # Rå model-output (debugging/reanalyse)
    raw_response         = Column(JSONB)

    # GDPR-flag (boolean — selve dataen er i gdpr_detections)
    has_gdpr_data        = Column(Boolean, default=False)

    # Relations
    capture              = relationship("Capture", foreign_keys=[capture_id], backref="ai_analysis")
    reference_capture    = relationship("Capture", foreign_keys=[reference_capture_id])
    capture_tags         = relationship("CaptureTag", back_populates="analysis", cascade="all, delete-orphan")

    @property
    def tags(self) -> list[str]:
        return [ct.tag_vocab.tag for ct in self.capture_tags if ct.tag_vocab and ct.tag_vocab.approved]

    def __repr__(self):
        chg = " [CHANGE]" if self.change_detected else ""
        gdpr = " [GDPR]" if self.has_gdpr_data else ""
        return f"<AIAnalysis capture={self.capture_id}{chg}{gdpr}>"


# =============================================================================
# KRYDSREFERENCE — Capture ↔ Tag (M:M)
# =============================================================================

class CaptureTag(Base):
    __tablename__ = "capture_tags"
    __table_args__ = (
        UniqueConstraint("capture_id", "tag_id", name="uq_capture_tag"),
        Index("idx_capture_tags_capture", "capture_id"),
        Index("idx_capture_tags_tag", "tag_id"),
    )

    id          = Column(Integer, primary_key=True)
    capture_id  = Column(Integer, ForeignKey("captures.id", ondelete="CASCADE"), nullable=False)
    tag_id      = Column(Integer, ForeignKey("ai_tag_vocabulary.id", ondelete="CASCADE"), nullable=False)
    analysis_id = Column(Integer, ForeignKey("ai_analyses.id", ondelete="SET NULL"), nullable=True)
    confidence  = Column(Float, default=1.0)
    is_new_tag  = Column(Boolean, default=False)
    tagged_at   = Column(DateTime(timezone=True), default=_now)

    # Relations
    tag_vocab   = relationship("AITagVocabulary", back_populates="capture_links")
    analysis    = relationship("AIAnalysis", back_populates="capture_tags")


# =============================================================================
# MODEL-SEPAREREDE RESULTATER — Edge/Ollama/Gemini side om side
# =============================================================================

class CaptureModelResult(Base):
    __tablename__ = "capture_model_results"
    __table_args__ = (
        UniqueConstraint("capture_id", "engine", "model", "result_kind", name="uq_capture_model_result"),
        Index("idx_capture_model_results_capture", "capture_id"),
        Index("idx_capture_model_results_engine", "engine", "analysed_at"),
    )

    id            = Column(Integer, primary_key=True)
    capture_id    = Column(Integer, ForeignKey("captures.id", ondelete="CASCADE"), nullable=False)
    engine        = Column(String(80), nullable=False)
    model         = Column(String(160), nullable=False, default="")
    model_version = Column(String(80))
    result_kind   = Column(String(50), nullable=False, default="analysis")
    scope         = Column(String(120))
    confidence    = Column(Float)
    result_json   = Column(JSONB, nullable=False, default=dict)
    tags_json     = Column(JSONB, nullable=False, default=list)
    source        = Column(String(80))
    analysed_at   = Column(DateTime(timezone=True), default=_now, nullable=False)
    created_at    = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at    = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# =============================================================================
# GDPR DETEKTIONER (RESTRICTED)
# Importeres KUN i gdpr_manager.py — aldrig i normale endpoints
# =============================================================================

class GDPRDetection(Base):
    __tablename__ = "gdpr_detections"

    id              = Column(Integer, primary_key=True)
    capture_id      = Column(Integer, ForeignKey("captures.id", ondelete="RESTRICT"), nullable=False, index=True)
    analysis_id     = Column(Integer, ForeignKey("ai_analyses.id", ondelete="SET NULL"), nullable=True)
    detected_at     = Column(DateTime(timezone=True), default=_now, index=True)
    location_id     = Column(String(100))

    detection_type  = Column(String(50), nullable=False, index=True)
    # Mulige værdier:
    #   'face'             — ansigt detekteret
    #   'license_plate'    — nummerplade detekteret (ikke nødvendigvis aflæst)
    #   'person_counted'   — antal personer (ingen identifikation)
    #   'vehicle_detail'   — specifik køretøjsinfo

    detail_json     = Column(JSONB)      # aldrig eksponeret i normale views
    bounding_box    = Column(JSONB)      # {x, y, w, h} normaliseret 0–1

    # Retention
    retain_until    = Column(DateTime(timezone=True))
    deletion_reason = Column(Text)
    deleted_at      = Column(DateTime(timezone=True))

    # Lovgrundlag
    legal_basis     = Column(String(100), default="legitimate_interest")
    consent_ref     = Column(String(200))

    def is_expired(self) -> bool:
        if self.retain_until is None:
            return False
        return datetime.now(timezone.utc) > self.retain_until

    def soft_delete(self, reason: str):
        self.deleted_at = _now()
        self.deletion_reason = reason
        self.detail_json = None      # slet selve dataen
        self.bounding_box = None


class GDPRAccessLog(Base):
    """Uforanderlig audit-log. Ingen UPDATE/DELETE via applikationslaget."""
    __tablename__ = "gdpr_access_log"

    id              = Column(Integer, primary_key=True)
    accessed_at     = Column(DateTime(timezone=True), default=_now, index=True)
    user_id         = Column(String(100), nullable=False)
    user_email      = Column(String(200))
    action          = Column(String(50), nullable=False)
    # SELECT / EXPORT / DELETE / APPROVE / VIEW_DETAIL
    detection_ids   = Column(ARRAY(Integer))
    capture_ids     = Column(ARRAY(Integer))
    reason          = Column(Text)
    ip_address      = Column(String(50))
    session_id      = Column(String(200))
    result          = Column(String(20), default="ok")


class GDPRDeletionQueue(Base):
    __tablename__ = "gdpr_deletion_queue"

    id              = Column(Integer, primary_key=True)
    detection_id    = Column(Integer, ForeignKey("gdpr_detections.id"), nullable=True)
    capture_id      = Column(Integer, ForeignKey("captures.id"), nullable=True)
    queued_at       = Column(DateTime(timezone=True), default=_now)
    scheduled_for   = Column(DateTime(timezone=True), nullable=False, index=True)
    reason          = Column(String(100), nullable=False)
    requested_by    = Column(String(100))
    completed_at    = Column(DateTime(timezone=True))
    status          = Column(String(20), default="pending")   # pending / completed / failed
