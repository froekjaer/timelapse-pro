CREATE TABLE IF NOT EXISTS ai_prompt_templates (
    id BIGSERIAL PRIMARY KEY,
    purpose VARCHAR(60) NOT NULL,
    version INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'retired')),
    template TEXT NOT NULL,
    allowed_variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_by VARCHAR(100),
    activated_at TIMESTAMPTZ,
    UNIQUE (purpose, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_prompt_templates_active_purpose
    ON ai_prompt_templates (purpose)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS ix_ai_prompt_templates_purpose_version
    ON ai_prompt_templates (purpose, version DESC);
