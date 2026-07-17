-- Append-only GRC discussion history. Comments are evidence-bearing audit records.
CREATE TABLE IF NOT EXISTS grc_comments (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL REFERENCES grc_items(id),
    body TEXT NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_grc_comments_item ON grc_comments(item_id);
CREATE INDEX IF NOT EXISTS ix_grc_comments_created_by ON grc_comments(created_by);
