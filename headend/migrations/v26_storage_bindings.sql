-- Logical storage registry. Physical disks and NAS mounts can be replaced
-- without changing application code or image records.
CREATE TABLE IF NOT EXISTS storage_bindings (
    id BIGSERIAL PRIMARY KEY,
    logical_name VARCHAR(80) NOT NULL,
    backend_type VARCHAR(20) NOT NULL DEFAULT 'local',
    path VARCHAR(1000) NOT NULL,
    access_mode VARCHAR(20) NOT NULL DEFAULT 'read_write',
    priority INTEGER NOT NULL DEFAULT 100 CHECK (priority >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    expected_volume_uuid VARCHAR(80),
    description VARCHAR(300),
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_storage_binding_role_path UNIQUE (logical_name, path)
);
CREATE INDEX IF NOT EXISTS ix_storage_bindings_logical_name ON storage_bindings(logical_name);

