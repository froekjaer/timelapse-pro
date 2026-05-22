-- =============================================================================
-- TimeLapse Pro — Schema Patch v2.1
-- Escalation workflow + Manuel korrektions-feedback loop
-- =============================================================================
-- Køres oven på schema_v2.sql
-- =============================================================================

-- ── Udvid ai_analyses med eskalerings-felter ──────────────────────────────────

ALTER TABLE ai_analyses
    ADD COLUMN IF NOT EXISTS should_escalate      BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS escalation_score     REAL,          -- 0.0–1.0 usikkerhed
    ADD COLUMN IF NOT EXISTS escalation_reasons   TEXT[],        -- hvilke kriterier der triggede
    ADD COLUMN IF NOT EXISTS escalation_status    TEXT DEFAULT 'none',
    -- none | pending_review | approved | rejected | completed
    ADD COLUMN IF NOT EXISTS escalation_approved_by  TEXT,
    ADD COLUMN IF NOT EXISTS escalation_approved_at  TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS gemini_result        JSONB,
    ADD COLUMN IF NOT EXISTS gemini_model         TEXT,
    ADD COLUMN IF NOT EXISTS gemini_analysed_at   TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS gemini_tags          TEXT[],        -- tags fra Gemini
    ADD COLUMN IF NOT EXISTS gemini_scene_dk      TEXT;

CREATE INDEX IF NOT EXISTS idx_ai_escalate
    ON ai_analyses(should_escalate, escalation_status)
    WHERE should_escalate = TRUE;

CREATE INDEX IF NOT EXISTS idx_ai_escalate_date
    ON ai_analyses(analysed_at, should_escalate);


-- =============================================================================
-- FEEDBACK SESSIONS
-- Én session pr. admin-gennemgang af en dags billeder
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_feedback_sessions (
    id                  SERIAL PRIMARY KEY,
    session_date        DATE NOT NULL,
    location_id         TEXT,
    admin_id            TEXT NOT NULL,
    started_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at        TIMESTAMP WITH TIME ZONE,
    captures_reviewed   INTEGER DEFAULT 0,
    corrections_made    INTEGER DEFAULT 0,
    escalations_reviewed INTEGER DEFAULT 0,
    notes               TEXT,
    -- Automatisk prompt-forbedring baseret på session
    prompt_update_generated BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_feedback_date
    ON ai_feedback_sessions(session_date DESC);


-- =============================================================================
-- MANUELLE KORREKTIONER
-- Ground truth — bruges til prompt-optimering
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_corrections (
    id                  SERIAL PRIMARY KEY,
    capture_id          INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    analysis_id         INTEGER REFERENCES ai_analyses(id) ON DELETE SET NULL,
    session_id          INTEGER REFERENCES ai_feedback_sessions(id) ON DELETE SET NULL,

    -- Hvad modellen sagde (snapshot)
    original_tags       TEXT[],
    original_scene      TEXT,
    original_quality_flag TEXT,
    original_quality_ok BOOLEAN,
    original_change_detected BOOLEAN,

    -- Hvad admin rettede til
    corrected_tags      TEXT[],
    corrected_scene     TEXT,
    corrected_quality_flag TEXT,
    corrected_quality_ok BOOLEAN,
    corrected_change_detected BOOLEAN,

    -- Diff (beregnet automatisk)
    tags_added          TEXT[],   -- tags admin tilføjede
    tags_removed        TEXT[],   -- tags admin fjernede
    quality_changed     BOOLEAN DEFAULT FALSE,
    scene_changed       BOOLEAN DEFAULT FALSE,

    -- Meta
    notes               TEXT,     -- admin-kommentar
    corrected_by        TEXT NOT NULL,
    corrected_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    correction_type     TEXT DEFAULT 'manual',
    -- manual | escalation_merge | auto_backfill

    -- Er denne korrektion brugt til prompt-optimering?
    used_in_prompt      BOOLEAN DEFAULT FALSE,
    used_in_prompt_at   TIMESTAMP WITH TIME ZONE,

    CONSTRAINT uq_correction_capture UNIQUE (capture_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_corrections_capture  ON ai_corrections(capture_id);
CREATE INDEX IF NOT EXISTS idx_corrections_session  ON ai_corrections(session_id);
CREATE INDEX IF NOT EXISTS idx_corrections_date     ON ai_corrections(corrected_at);
CREATE INDEX IF NOT EXISTS idx_corrections_unused   ON ai_corrections(used_in_prompt)
    WHERE used_in_prompt = FALSE;


-- =============================================================================
-- FEW-SHOT EKSEMPLER
-- Genereres fra korrektioner — bruges i næste prompt
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_prompt_examples (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    based_on_corrections INTEGER[],   -- correction IDs der genererede dette
    example_type    TEXT NOT NULL,    -- tags / quality / change / scene
    -- Eksempel-tekst der indsættes i prompten
    example_text    TEXT NOT NULL,    -- "Når du ser X, er korrekte tags: Y"
    priority        INTEGER DEFAULT 5, -- 1=høj, 10=lav
    active          BOOLEAN DEFAULT TRUE,
    times_used      INTEGER DEFAULT 0,
    location_id     TEXT,             -- NULL = generisk, ellers lokation-specifik
    -- Metrik: hjalp eksemplet?
    accuracy_before REAL,
    accuracy_after  REAL
);

CREATE INDEX IF NOT EXISTS idx_examples_active ON ai_prompt_examples(active, priority)
    WHERE active = TRUE;


-- =============================================================================
-- VIEWS TIL REVIEW UI
-- =============================================================================

-- Dagens billeder til gennemgang
CREATE OR REPLACE VIEW v_daily_review AS
SELECT
    c.id                AS capture_id,
    c.filename,
    c.captured_at,
    c.device_id,
    a.location_id,
    a.scene_dk,
    a.ai_quality_flag,
    a.ai_quality_ok,
    a.change_detected,
    a.should_escalate,
    a.escalation_score,
    a.escalation_reasons,
    a.escalation_status,
    a.gemini_tags,
    a.gemini_scene_dk,

    -- Tags fra lokal model
    (SELECT array_agg(tv.tag ORDER BY ct.confidence DESC)
     FROM capture_tags ct
     JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id
     WHERE ct.capture_id = c.id AND tv.approved = TRUE
    ) AS current_tags,

    -- Er der allerede lavet korrektion?
    (SELECT corr.id FROM ai_corrections corr WHERE corr.capture_id = c.id LIMIT 1)
        AS correction_id,
    (SELECT corr.corrected_tags FROM ai_corrections corr WHERE corr.capture_id = c.id LIMIT 1)
        AS corrected_tags

FROM captures c
JOIN ai_analyses a ON a.capture_id = c.id
ORDER BY c.captured_at DESC;


-- Eskalerings-kø (afventer admin-godkendelse)
CREATE OR REPLACE VIEW v_escalation_queue AS
SELECT
    a.id            AS analysis_id,
    c.id            AS capture_id,
    c.filename,
    c.captured_at,
    c.device_id,
    a.location_id,
    a.scene_dk,
    a.escalation_score,
    a.escalation_reasons,
    a.escalation_status,
    a.ai_quality_flag,
    a.change_detected,
    (SELECT array_agg(tv.tag ORDER BY ct.confidence DESC)
     FROM capture_tags ct
     JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id
     WHERE ct.capture_id = c.id AND tv.approved = TRUE
    ) AS current_tags
FROM ai_analyses a
JOIN captures c ON c.id = a.capture_id
WHERE a.should_escalate = TRUE
  AND a.escalation_status = 'pending_review'
ORDER BY a.escalation_score DESC, c.captured_at DESC;


-- Korrektions-statistik (til at vurdere model-fremgang)
CREATE OR REPLACE VIEW v_correction_stats AS
SELECT
    DATE(corr.corrected_at)     AS correction_date,
    COUNT(*)                    AS total_corrections,
    COUNT(*) FILTER (WHERE corr.quality_changed)  AS quality_corrections,
    COUNT(*) FILTER (WHERE corr.scene_changed)    AS scene_corrections,
    AVG(array_length(corr.tags_added, 1))::REAL   AS avg_tags_added,
    AVG(array_length(corr.tags_removed, 1))::REAL AS avg_tags_removed,
    -- Tags der oftest tilføjes (model glemmer dem)
    (SELECT unnest(tags_added) FROM ai_corrections
     WHERE DATE(corrected_at) = DATE(corr.corrected_at)
     GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1) AS most_added_tag,
    -- Tags der oftest fjernes (model fejltagger)
    (SELECT unnest(tags_removed) FROM ai_corrections
     WHERE DATE(corrected_at) = DATE(corr.corrected_at)
     GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1) AS most_removed_tag
FROM ai_corrections corr
GROUP BY DATE(corr.corrected_at)
ORDER BY correction_date DESC;
