-- TimeLapse Pro GRC register v1. PostgreSQL is the authoritative store.
CREATE TABLE IF NOT EXISTS grc_items (
    id BIGSERIAL PRIMARY KEY,
    item_type VARCHAR(20) NOT NULL CHECK (item_type IN ('requirement','control','risk','test','finding','action')),
    external_id VARCHAR(100) NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    priority VARCHAR(10), owner VARCHAR(100), due_at TIMESTAMPTZ,
    source VARCHAR(300), scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb, version INTEGER NOT NULL DEFAULT 1,
    created_by VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by VARCHAR(100) NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_grc_items_type_external_id UNIQUE (item_type, external_id)
);
CREATE INDEX IF NOT EXISTS ix_grc_items_item_type ON grc_items(item_type);
CREATE INDEX IF NOT EXISTS ix_grc_items_status ON grc_items(status);

CREATE TABLE IF NOT EXISTS grc_links (
    id BIGSERIAL PRIMARY KEY, source_item_id BIGINT NOT NULL REFERENCES grc_items(id),
    target_item_id BIGINT NOT NULL REFERENCES grc_items(id), relationship VARCHAR(40) NOT NULL,
    rationale TEXT, created_by VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_grc_links_edge UNIQUE (source_item_id, target_item_id, relationship)
);
CREATE INDEX IF NOT EXISTS ix_grc_links_source ON grc_links(source_item_id);
CREATE INDEX IF NOT EXISTS ix_grc_links_target ON grc_links(target_item_id);

CREATE TABLE IF NOT EXISTS grc_test_runs (
    id BIGSERIAL PRIMARY KEY, test_item_id BIGINT NOT NULL REFERENCES grc_items(id),
    environment VARCHAR(30) NOT NULL, result VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ,
    executed_by VARCHAR(100) NOT NULL, release_ref VARCHAR(150), notes TEXT,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_grc_test_runs_test ON grc_test_runs(test_item_id);

CREATE TABLE IF NOT EXISTS grc_evidence (
    id BIGSERIAL PRIMARY KEY, item_id BIGINT REFERENCES grc_items(id),
    test_run_id BIGINT REFERENCES grc_test_runs(id), evidence_type VARCHAR(40) NOT NULL,
    title VARCHAR(300) NOT NULL, uri VARCHAR(1000), sha256 VARCHAR(64), content JSONB,
    collected_by VARCHAR(100) NOT NULL, collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_class VARCHAR(50) NOT NULL DEFAULT 'grc_standard',
    CHECK (item_id IS NOT NULL OR test_run_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_grc_evidence_item ON grc_evidence(item_id);
CREATE INDEX IF NOT EXISTS ix_grc_evidence_run ON grc_evidence(test_run_id);
