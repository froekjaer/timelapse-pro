"""
Model-separated analysis storage for TimeLapse Pro.

This is an additive companion to the legacy captures.ai_result/ai_tags fields.
Each AI/QA engine gets its own row per capture, so Edge QA, Edge NPU,
headend Ollama and Gemini/cloud can be compared and retuned without
overwriting each other's data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text


ENGINE_EDGE_CV = "edge_cv_v1"
ENGINE_EDGE_NPU = "edge_npu"
ENGINE_HEADEND_OLLAMA = "headend_ollama"
ENGINE_GEMINI_CLOUD = "gemini_cloud"


def ensure_capture_model_results_table(db) -> None:
    """Create the additive model-result table if the migration has not run yet."""
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS capture_model_results (
            id              BIGSERIAL PRIMARY KEY,
            capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
            engine          TEXT NOT NULL,
            model           TEXT NOT NULL DEFAULT '',
            model_version   TEXT,
            result_kind     TEXT NOT NULL DEFAULT 'analysis',
            scope           TEXT,
            confidence      REAL,
            result_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
            tags_json       JSONB NOT NULL DEFAULT '[]'::jsonb,
            source          TEXT,
            analysed_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_capture_model_result
                UNIQUE (capture_id, engine, model, result_kind)
        )
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_capture_model_results_capture
            ON capture_model_results(capture_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_capture_model_results_engine
            ON capture_model_results(engine, analysed_at DESC)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_capture_model_results_tags_gin
            ON capture_model_results USING GIN (tags_json)
    """))


def get_capture_model_results(db, capture_id: int) -> list[dict[str, Any]]:
    """Read back every per-engine result row for one capture (til proveniens-UI).

    2026-07-04 (Claude): additiv læse-side til Codex' model-separerede lager
    (se HANDOVER_LOG.md "Codex fortsætter: model-separeret AI/QA-lager").
    Kalder ensure_capture_model_results_table() først, så et helt frisk
    headend-checkout uden migrationen stadig svarer [] i stedet for at fejle.
    """
    ensure_capture_model_results_table(db)
    rows = db.execute(text("""
        SELECT engine, model, model_version, result_kind, scope, confidence,
               result_json, tags_json, source, analysed_at
        FROM capture_model_results
        WHERE capture_id = :capture_id
        ORDER BY analysed_at DESC
    """), {"capture_id": int(capture_id)}).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        result_json = r.result_json if isinstance(r.result_json, dict) else (json.loads(r.result_json) if r.result_json else {})
        tags_json = r.tags_json if isinstance(r.tags_json, list) else (json.loads(r.tags_json) if r.tags_json else [])
        out.append({
            "engine": r.engine,
            "model": r.model,
            "model_version": r.model_version,
            "result_kind": r.result_kind,
            "scope": r.scope,
            "confidence": r.confidence,
            "result": result_json,
            "tags": tags_json,
            "source": r.source,
            "analysed_at": r.analysed_at.isoformat() if r.analysed_at else None,
        })
    return out


def engine_from_legacy_payload(payload: dict[str, Any], fallback_model: str | None = None) -> str:
    engine = str(payload.get("engine") or "").strip().lower()
    model = str(payload.get("model") or fallback_model or "").strip().lower()
    if engine == "cloud" or "gemini" in model:
        return ENGINE_GEMINI_CLOUD
    if engine == "local" or model:
        return ENGINE_HEADEND_OLLAMA
    return "headend_ai"


def upsert_capture_model_result(
    db,
    *,
    capture_id: int,
    engine: str,
    model: str | None = None,
    result_kind: str = "analysis",
    result_json: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    model_version: str | None = None,
    scope: str | None = None,
    confidence: float | None = None,
    source: str | None = None,
    analysed_at: datetime | None = None,
) -> int:
    ensure_capture_model_results_table(db)
    payload = result_json or {}
    tag_list = list(dict.fromkeys(str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()))
    analysed_at = analysed_at or datetime.now(timezone.utc)
    row = db.execute(text("""
        INSERT INTO capture_model_results (
            capture_id, engine, model, model_version, result_kind, scope,
            confidence, result_json, tags_json, source, analysed_at
        ) VALUES (
            :capture_id, :engine, :model, :model_version, :result_kind, :scope,
            :confidence, CAST(:result_json AS jsonb), CAST(:tags_json AS jsonb),
            :source, :analysed_at
        )
        ON CONFLICT (capture_id, engine, model, result_kind)
        DO UPDATE SET
            model_version = EXCLUDED.model_version,
            scope = EXCLUDED.scope,
            confidence = EXCLUDED.confidence,
            result_json = EXCLUDED.result_json,
            tags_json = EXCLUDED.tags_json,
            source = EXCLUDED.source,
            analysed_at = EXCLUDED.analysed_at,
            updated_at = NOW()
        RETURNING id
    """), {
        "capture_id": int(capture_id),
        "engine": str(engine),
        "model": model or "",
        "model_version": model_version,
        "result_kind": result_kind,
        "scope": scope,
        "confidence": confidence,
        "result_json": json.dumps(payload, ensure_ascii=False),
        "tags_json": json.dumps(tag_list, ensure_ascii=False),
        "source": source,
        "analysed_at": analysed_at,
    }).fetchone()
    return int(row[0])
