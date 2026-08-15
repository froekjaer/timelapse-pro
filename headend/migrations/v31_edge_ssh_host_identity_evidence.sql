-- TimeLapse Pro - v31 Edge SSH host identity evidence
-- Read-only authenticated Edge reports about SSH server host public keys.
-- These rows are evidence only; they must not update known_hosts or mark
-- fingerprints trusted automatically.

BEGIN;

CREATE TABLE IF NOT EXISTS edge_ssh_host_identity_evidence (
    id                  SERIAL PRIMARY KEY,
    device_id           VARCHAR(50) NOT NULL,
    key_type            VARCHAR(30) NOT NULL,
    fingerprint         VARCHAR(128) NOT NULL,
    public_key_path     VARCHAR(300) NOT NULL,
    hostname            VARCHAR(120),
    observed_at         TIMESTAMPTZ NOT NULL,
    reported_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence_source     VARCHAR(80) NOT NULL DEFAULT 'authenticated_edge_report',
    software_version    VARCHAR(100),
    source_commit       VARCHAR(64),
    release_artifact_id VARCHAR(80),
    status              VARCHAR(30) NOT NULL DEFAULT 'observed',
    trusted_state       VARCHAR(30) NOT NULL DEFAULT 'untrusted_observed',
    raw_evidence_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_edge_ssh_host_identity_device ON edge_ssh_host_identity_evidence(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_ssh_host_identity_fingerprint ON edge_ssh_host_identity_evidence(fingerprint);
CREATE INDEX IF NOT EXISTS idx_edge_ssh_host_identity_key_type ON edge_ssh_host_identity_evidence(key_type);
CREATE INDEX IF NOT EXISTS idx_edge_ssh_host_identity_observed ON edge_ssh_host_identity_evidence(observed_at);
CREATE INDEX IF NOT EXISTS idx_edge_ssh_host_identity_source ON edge_ssh_host_identity_evidence(evidence_source);
CREATE INDEX IF NOT EXISTS idx_edge_ssh_host_identity_trusted_state ON edge_ssh_host_identity_evidence(trusted_state);

GRANT ALL PRIVILEGES ON TABLE edge_ssh_host_identity_evidence TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE edge_ssh_host_identity_evidence_id_seq TO timelapse;

COMMIT;
