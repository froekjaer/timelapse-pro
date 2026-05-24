-- =============================================================================
-- TimeLapse Pro - v3.1 update governance
-- Signed change tickets, artifacts and per-target deployment state.
-- =============================================================================

ALTER TABLE devices ADD COLUMN IF NOT EXISTS customer_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS idx_devices_customer_id ON devices(customer_id);

CREATE TABLE IF NOT EXISTS change_tickets (
    id                  SERIAL PRIMARY KEY,
    ticket_id           VARCHAR(80) UNIQUE NOT NULL,
    title               VARCHAR(200) NOT NULL,
    summary             TEXT,
    pending_update_id   INTEGER,
    update_type         VARCHAR(50),
    severity            VARCHAR(20),
    environment         VARCHAR(20) DEFAULT 'production',
    scope               VARCHAR(20),
    scope_id            VARCHAR(36),
    status              VARCHAR(30) DEFAULT 'draft',
    source_commit       VARCHAR(64),
    source_ref          VARCHAR(200),
    artifact_id         VARCHAR(80),
    sbom_ref            VARCHAR(500),
    test_evidence_ref   VARCHAR(500),
    rollback_plan       TEXT,
    reboot_required     BOOLEAN DEFAULT FALSE,
    maintenance_window  VARCHAR(50),
    human_readable_md   TEXT,
    machine_json        TEXT,
    content_sha256      VARCHAR(64),
    signature           TEXT,
    signed_by           VARCHAR(200),
    signed_at           TIMESTAMP WITH TIME ZONE,
    created_by          VARCHAR(100),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_change_tickets_ticket_id ON change_tickets(ticket_id);
CREATE INDEX IF NOT EXISTS idx_change_tickets_pending_update_id ON change_tickets(pending_update_id);
CREATE INDEX IF NOT EXISTS idx_change_tickets_status ON change_tickets(status);
CREATE INDEX IF NOT EXISTS idx_change_tickets_content_sha256 ON change_tickets(content_sha256);
CREATE INDEX IF NOT EXISTS idx_change_tickets_created_at ON change_tickets(created_at);

CREATE TABLE IF NOT EXISTS change_approvals (
    id                    SERIAL PRIMARY KEY,
    ticket_id             VARCHAR(80) NOT NULL,
    decision              VARCHAR(30) NOT NULL,
    decided_by            VARCHAR(100) NOT NULL,
    decided_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approval_context      TEXT,
    signature             TEXT,
    signed_payload_sha256 VARCHAR(64),
    notes                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_change_approvals_ticket_id ON change_approvals(ticket_id);
CREATE INDEX IF NOT EXISTS idx_change_approvals_decided_at ON change_approvals(decided_at);

CREATE TABLE IF NOT EXISTS update_artifacts (
    id              SERIAL PRIMARY KEY,
    artifact_id     VARCHAR(80) UNIQUE NOT NULL,
    artifact_type   VARCHAR(50) NOT NULL,
    version         VARCHAR(100),
    source_commit   VARCHAR(64),
    source_ref      VARCHAR(200),
    filename        VARCHAR(500),
    storage_path    VARCHAR(1000),
    size_bytes      INTEGER,
    sha256          VARCHAR(64) NOT NULL,
    manifest_json   TEXT,
    sbom_ref        VARCHAR(500),
    signature       TEXT,
    signed_by       VARCHAR(200),
    signed_at       TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_update_artifacts_artifact_id ON update_artifacts(artifact_id);
CREATE INDEX IF NOT EXISTS idx_update_artifacts_sha256 ON update_artifacts(sha256);
CREATE INDEX IF NOT EXISTS idx_update_artifacts_created_at ON update_artifacts(created_at);

CREATE TABLE IF NOT EXISTS update_targets (
    id                SERIAL PRIMARY KEY,
    pending_update_id INTEGER,
    ticket_id         VARCHAR(80),
    artifact_id       VARCHAR(80),
    device_id         VARCHAR(50) NOT NULL,
    camera_id         VARCHAR(36),
    customer_id       VARCHAR(36),
    site_id           VARCHAR(36),
    status            VARCHAR(30) DEFAULT 'pending',
    attempt_count     INTEGER DEFAULT 0,
    last_error        TEXT,
    current_version   VARCHAR(100),
    target_version    VARCHAR(100),
    rollback_version  VARCHAR(100),
    started_at        TIMESTAMP WITH TIME ZONE,
    completed_at      TIMESTAMP WITH TIME ZONE,
    rollback_at       TIMESTAMP WITH TIME ZONE,
    last_report_at    TIMESTAMP WITH TIME ZONE,
    report_json       TEXT
);

CREATE INDEX IF NOT EXISTS idx_update_targets_pending_update_id ON update_targets(pending_update_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_ticket_id ON update_targets(ticket_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_artifact_id ON update_targets(artifact_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_device_id ON update_targets(device_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_camera_id ON update_targets(camera_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_customer_id ON update_targets(customer_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_site_id ON update_targets(site_id);
CREATE INDEX IF NOT EXISTS idx_update_targets_status ON update_targets(status);
