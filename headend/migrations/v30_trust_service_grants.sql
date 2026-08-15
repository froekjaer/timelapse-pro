-- TimeLapse Pro - v30 Trust Service, PDP audit and EdgeServiceGrant foundation

BEGIN;

CREATE TABLE IF NOT EXISTS edge_service_grants (
    id                SERIAL PRIMARY KEY,
    grant_id          VARCHAR(80) UNIQUE NOT NULL,
    jti               VARCHAR(80) UNIQUE NOT NULL,
    edge_id           VARCHAR(50) NOT NULL,
    user_id           INTEGER,
    username          VARCHAR(100) NOT NULL,
    role              VARCHAR(50) NOT NULL,
    tenant_id         VARCHAR(36),
    resource          VARCHAR(200) NOT NULL,
    purpose           VARCHAR(120) NOT NULL,
    capabilities_json TEXT NOT NULL,
    context_json      TEXT,
    mfa_required      BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_verified      BOOLEAN NOT NULL DEFAULT FALSE,
    status            VARCHAR(20) NOT NULL DEFAULT 'active',
    issued_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ NOT NULL,
    revoked_at        TIMESTAMPTZ,
    revoked_by        VARCHAR(100),
    revoke_reason     TEXT,
    signature         TEXT NOT NULL,
    last_challenge_id VARCHAR(120),
    use_count         INTEGER NOT NULL DEFAULT 0,
    last_used_at      TIMESTAMPTZ,
    metadata_json     TEXT
);

CREATE INDEX IF NOT EXISTS idx_edge_service_grants_edge ON edge_service_grants(edge_id);
CREATE INDEX IF NOT EXISTS idx_edge_service_grants_user ON edge_service_grants(username);
CREATE INDEX IF NOT EXISTS idx_edge_service_grants_tenant ON edge_service_grants(tenant_id);
CREATE INDEX IF NOT EXISTS idx_edge_service_grants_status ON edge_service_grants(status);
CREATE INDEX IF NOT EXISTS idx_edge_service_grants_expires ON edge_service_grants(expires_at);

CREATE TABLE IF NOT EXISTS trust_policy_decision_audit (
    id           SERIAL PRIMARY KEY,
    decision_id  VARCHAR(80) UNIQUE NOT NULL,
    principal    VARCHAR(120) NOT NULL,
    role         VARCHAR(50),
    tenant_id    VARCHAR(36),
    resource     VARCHAR(200) NOT NULL,
    action       VARCHAR(120) NOT NULL,
    capability   VARCHAR(120),
    allowed      BOOLEAN NOT NULL,
    reason       TEXT NOT NULL,
    context_json TEXT,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trust_policy_decision_principal ON trust_policy_decision_audit(principal);
CREATE INDEX IF NOT EXISTS idx_trust_policy_decision_tenant ON trust_policy_decision_audit(tenant_id);
CREATE INDEX IF NOT EXISTS idx_trust_policy_decision_allowed ON trust_policy_decision_audit(allowed);
CREATE INDEX IF NOT EXISTS idx_trust_policy_decision_at ON trust_policy_decision_audit(decided_at);

GRANT ALL PRIVILEGES ON TABLE edge_service_grants TO timelapse;
GRANT ALL PRIVILEGES ON TABLE trust_policy_decision_audit TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE edge_service_grants_id_seq TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE trust_policy_decision_audit_id_seq TO timelapse;

COMMIT;
