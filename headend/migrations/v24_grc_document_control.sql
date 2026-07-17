CREATE TABLE IF NOT EXISTS grc_documents (
    id BIGSERIAL PRIMARY KEY, document_id VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(300) NOT NULL, document_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft', owner VARCHAR(100) NOT NULL,
    approver_role VARCHAR(50) NOT NULL DEFAULT 'super_admin',
    classification VARCHAR(30) NOT NULL DEFAULT 'internal',
    retention_class VARCHAR(50) NOT NULL DEFAULT 'grc_controlled',
    created_by VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_grc_documents_type ON grc_documents(document_type);
CREATE INDEX IF NOT EXISTS ix_grc_documents_status ON grc_documents(status);

CREATE TABLE IF NOT EXISTS grc_document_revisions (
    id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL REFERENCES grc_documents(id),
    revision INTEGER NOT NULL, lifecycle_status VARCHAR(30) NOT NULL DEFAULT 'draft',
    content_sha256 VARCHAR(64) NOT NULL, content TEXT NOT NULL, source_uri VARCHAR(1000),
    generator VARCHAR(100) NOT NULL, grc_snapshot_sha256 VARCHAR(64) NOT NULL,
    change_summary TEXT, created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), approved_by VARCHAR(100), approved_at TIMESTAMPTZ,
    CONSTRAINT uq_grc_document_revision UNIQUE(document_id, revision)
);
CREATE INDEX IF NOT EXISTS ix_grc_document_revisions_document ON grc_document_revisions(document_id);
CREATE INDEX IF NOT EXISTS ix_grc_document_revisions_hash ON grc_document_revisions(content_sha256);

CREATE TABLE IF NOT EXISTS grc_document_item_links (
    id BIGSERIAL PRIMARY KEY,
    revision_id BIGINT NOT NULL REFERENCES grc_document_revisions(id),
    item_id BIGINT NOT NULL REFERENCES grc_items(id),
    relationship VARCHAR(40) NOT NULL DEFAULT 'included',
    CONSTRAINT uq_grc_document_item_link UNIQUE(revision_id, item_id)
);
