-- TimeLapse Pro - v3.3 key management
-- Credential lifecycle registry for Headend, Edge, SSH, API and signing keys.
--
-- Compliance intent:
--   SABSA: identity, trust boundary and business ownership traceability.
--   IEC 62443: authenticated communication, secure remote access and revocation.
--   ISO 27000: access control, cryptographic key management and audit evidence.
--   NIS2: operational resilience, incident response and supplier/customer accountability.
--   CRA: secure-by-design device identity, update/signing trust and vulnerability response.

BEGIN;

CREATE TABLE IF NOT EXISTS key_credentials (
    id                 SERIAL PRIMARY KEY,
    credential_id      VARCHAR(80) UNIQUE NOT NULL,
    entity_type        VARCHAR(30) NOT NULL,
    entity_id          VARCHAR(100) NOT NULL,
    key_type           VARCHAR(30) NOT NULL,
    label              VARCHAR(200),
    status             VARCHAR(30) NOT NULL DEFAULT 'active',
    scopes_json        TEXT,
    public_key         TEXT,
    fingerprint        VARCHAR(128),
    secret_hash        VARCHAR(128),
    algorithm          VARCHAR(50),
    compliance_domains VARCHAR(200) DEFAULT 'SABSA,IEC62443,ISO27000,NIS2,CRA',
    created_by         VARCHAR(100),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at         TIMESTAMPTZ,
    last_used_at       TIMESTAMPTZ,
    last_used_from     VARCHAR(100),
    use_count          INTEGER NOT NULL DEFAULT 0,
    revoked_at         TIMESTAMPTZ,
    revoked_by         VARCHAR(100),
    revoke_reason      TEXT,
    rotated_from_id    VARCHAR(80),
    metadata_json      TEXT
);

CREATE INDEX IF NOT EXISTS idx_key_credentials_entity ON key_credentials(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_key_credentials_key_type ON key_credentials(key_type);
CREATE INDEX IF NOT EXISTS idx_key_credentials_status ON key_credentials(status);
CREATE INDEX IF NOT EXISTS idx_key_credentials_fingerprint ON key_credentials(fingerprint);
CREATE INDEX IF NOT EXISTS idx_key_credentials_secret_hash ON key_credentials(secret_hash);
CREATE INDEX IF NOT EXISTS idx_key_credentials_expires_at ON key_credentials(expires_at);

CREATE TABLE IF NOT EXISTS key_audit_events (
    id            SERIAL PRIMARY KEY,
    credential_id VARCHAR(80),
    event_type    VARCHAR(50) NOT NULL,
    actor         VARCHAR(100),
    entity_type   VARCHAR(30),
    entity_id     VARCHAR(100),
    details_json  TEXT,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_key_audit_credential ON key_audit_events(credential_id);
CREATE INDEX IF NOT EXISTS idx_key_audit_event_type ON key_audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_key_audit_entity ON key_audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_key_audit_occurred_at ON key_audit_events(occurred_at DESC);

GRANT ALL PRIVILEGES ON TABLE key_credentials TO timelapse;
GRANT ALL PRIVILEGES ON TABLE key_audit_events TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE key_credentials_id_seq TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE key_audit_events_id_seq TO timelapse;

COMMIT;
