-- =============================================================================
-- TimeLapse Pro — v9 capture_model_results
-- Separate analysis/tag storage per AI/QA engine and model.
--
-- Purpose:
--   Keep Edge CV/NPU, headend Ollama and Gemini/cloud results side by side.
--   Existing captures.ai_result / captures.ai_tags remain as compatibility fields.
-- =============================================================================

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
);

CREATE INDEX IF NOT EXISTS idx_capture_model_results_capture
    ON capture_model_results(capture_id);

CREATE INDEX IF NOT EXISTS idx_capture_model_results_engine
    ON capture_model_results(engine, analysed_at DESC);

CREATE INDEX IF NOT EXISTS idx_capture_model_results_tags_gin
    ON capture_model_results USING GIN (tags_json);

COMMENT ON TABLE capture_model_results IS
    'Per-capture results split by engine/model. Keeps edge QA, Ollama and Gemini isolated.';

COMMENT ON COLUMN capture_model_results.engine IS
    'Examples: edge_cv_v1, edge_npu, headend_ollama, gemini_cloud.';

COMMENT ON COLUMN capture_model_results.result_kind IS
    'analysis, qa, tags, optics, or future model-specific result classes.';
