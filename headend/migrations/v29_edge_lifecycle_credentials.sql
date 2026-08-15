-- TimeLapse Pro - v29 Edge lifecycle and credential inventory
-- WP-1 convergence baseline: canonical provisioning state machine and
-- normalized inventory for API, SSH/tunnel, local service, bootstrap,
-- local TLS and release/update trust paths.

BEGIN;

CREATE TABLE IF NOT EXISTS edge_lifecycle_records (
    id                     SERIAL PRIMARY KEY,
    device_id              VARCHAR(50) UNIQUE NOT NULL,
    state                  VARCHAR(40) NOT NULL DEFAULT 'manufactured',
    hardware_fingerprint   VARCHAR(128),
    hardware_evidence_json TEXT,
    prepared_at            TIMESTAMPTZ,
    bootstrapped_at        TIMESTAMPTZ,
    hardware_verified_at   TIMESTAMPTZ,
    enrolled_at            TIMESTAMPTZ,
    credentialed_at        TIMESTAMPTZ,
    assigned_at            TIMESTAMPTZ,
    commissioned_at        TIMESTAMPTZ,
    revoked_at             TIMESTAMPTZ,
    retired_at             TIMESTAMPTZ,
    transition_reason      TEXT,
    metadata_json          TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_edge_lifecycle_device_id ON edge_lifecycle_records(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_lifecycle_state ON edge_lifecycle_records(state);
CREATE INDEX IF NOT EXISTS idx_edge_lifecycle_hardware_fingerprint ON edge_lifecycle_records(hardware_fingerprint);

CREATE TABLE IF NOT EXISTS edge_credential_inventory (
    id                       SERIAL PRIMARY KEY,
    device_id                VARCHAR(50) NOT NULL,
    trust_path               VARCHAR(50) NOT NULL,
    credential_id            VARCHAR(80),
    key_type                 VARCHAR(30),
    subject                  VARCHAR(120),
    issuer                   VARCHAR(120),
    owner                    VARCHAR(120),
    private_key_location     VARCHAR(300),
    public_key_location      VARCHAR(300),
    storage                  VARCHAR(200),
    secret_hash              VARCHAR(128),
    fingerprint              VARCHAR(128),
    source_table             VARCHAR(80),
    source_id                VARCHAR(120),
    lifetime                 VARCHAR(120),
    scope                    TEXT,
    audience                 VARCHAR(200),
    rotation                 VARCHAR(200),
    revocation               VARCHAR(200),
    status                   VARCHAR(30) NOT NULL DEFAULT 'active',
    legacy_path              BOOLEAN NOT NULL DEFAULT FALSE,
    compromise_procedure     TEXT,
    lifecycle_state_created  VARCHAR(40),
    metadata_json            TEXT,
    issued_at                TIMESTAMPTZ,
    activated_at             TIMESTAMPTZ,
    rotated_at               TIMESTAMPTZ,
    revoked_at               TIMESTAMPTZ,
    retired_at               TIMESTAMPTZ,
    expires_at               TIMESTAMPTZ,
    consumed_at              TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_edge_credential_inventory_path UNIQUE (device_id, trust_path, credential_id)
);

ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS secret_hash VARCHAR(128);
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(128);
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS source_table VARCHAR(80);
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS source_id VARCHAR(120);
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS issued_at TIMESTAMPTZ;
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS rotated_at TIMESTAMPTZ;
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS retired_at TIMESTAMPTZ;
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE edge_credential_inventory ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_device ON edge_credential_inventory(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_trust_path ON edge_credential_inventory(trust_path);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_key_type ON edge_credential_inventory(key_type);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_status ON edge_credential_inventory(status);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_legacy ON edge_credential_inventory(legacy_path);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_secret_hash ON edge_credential_inventory(secret_hash);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_fingerprint ON edge_credential_inventory(fingerprint);
CREATE INDEX IF NOT EXISTS idx_edge_credential_inventory_expires ON edge_credential_inventory(expires_at);

GRANT ALL PRIVILEGES ON TABLE edge_lifecycle_records TO timelapse;
GRANT ALL PRIVILEGES ON TABLE edge_credential_inventory TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE edge_lifecycle_records_id_seq TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE edge_credential_inventory_id_seq TO timelapse;

COMMIT;
