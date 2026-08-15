-- TimeLapse Pro - v32 SSH Tunnel UX convergence
-- Adds explicit host-key trust and browser terminal session audit.
-- This migration must not update known_hosts, disable host-key verification,
-- or trust unauthenticated ssh-keyscan output.

CREATE TABLE IF NOT EXISTS ssh_host_key_trust (
    id                 SERIAL PRIMARY KEY,
    device_id          VARCHAR(50) NOT NULL,
    hostname           VARCHAR(255),
    port               INTEGER,
    key_type           VARCHAR(40) NOT NULL,
    fingerprint_sha256 VARCHAR(128) NOT NULL,
    public_key_path    VARCHAR(300),
    trusted_state      VARCHAR(30) NOT NULL DEFAULT 'untrusted_observed',
    evidence_source    VARCHAR(120) NOT NULL,
    observed_at        TIMESTAMPTZ,
    trusted_at         TIMESTAMPTZ,
    trusted_by         VARCHAR(100),
    trust_reason       TEXT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_ssh_host_key_trust_device_key UNIQUE (device_id, key_type, fingerprint_sha256)
);

CREATE INDEX IF NOT EXISTS idx_ssh_host_key_trust_device ON ssh_host_key_trust(device_id);
CREATE INDEX IF NOT EXISTS idx_ssh_host_key_trust_key_type ON ssh_host_key_trust(key_type);
CREATE INDEX IF NOT EXISTS idx_ssh_host_key_trust_fingerprint ON ssh_host_key_trust(fingerprint_sha256);
CREATE INDEX IF NOT EXISTS idx_ssh_host_key_trust_state ON ssh_host_key_trust(trusted_state);

CREATE TABLE IF NOT EXISTS ssh_terminal_session_audit (
    id                 SERIAL PRIMARY KEY,
    session_id         VARCHAR(80) UNIQUE NOT NULL,
    grant_id           VARCHAR(80) NOT NULL,
    device_id          VARCHAR(50) NOT NULL,
    principal          VARCHAR(120) NOT NULL,
    role               VARCHAR(50),
    capability         VARCHAR(120) NOT NULL,
    remote_port        INTEGER,
    identity_key_path  VARCHAR(300),
    host_fingerprint   VARCHAR(128),
    status             VARCHAR(30) NOT NULL DEFAULT 'created',
    reason             TEXT,
    started_at         TIMESTAMPTZ,
    ended_at           TIMESTAMPTZ,
    expires_at         TIMESTAMPTZ NOT NULL,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ssh_terminal_session_device ON ssh_terminal_session_audit(device_id);
CREATE INDEX IF NOT EXISTS idx_ssh_terminal_session_grant ON ssh_terminal_session_audit(grant_id);
CREATE INDEX IF NOT EXISTS idx_ssh_terminal_session_principal ON ssh_terminal_session_audit(principal);
CREATE INDEX IF NOT EXISTS idx_ssh_terminal_session_status ON ssh_terminal_session_audit(status);

GRANT ALL PRIVILEGES ON TABLE ssh_host_key_trust TO timelapse;
GRANT ALL PRIVILEGES ON TABLE ssh_terminal_session_audit TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE ssh_host_key_trust_id_seq TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE ssh_terminal_session_audit_id_seq TO timelapse;
