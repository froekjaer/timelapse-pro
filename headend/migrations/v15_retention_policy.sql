-- Migration v15: Retention policy (GDPR G-02)
-- Dato: 2026-07-06
-- Formål: Implementer retention policy pr. kamera for GDPR-compliance
--
-- Se DPIA_SKABELON_OG_RETENTION_POLICY_v1.md §3 for design
--
-- 1. Tilføj retention_days til cameras-tabellen
-- 2. Opret deletion_log til revisionsspor af slettede captures
-- 3. Indeks for performance

-- 1. Retention days pr. kamera (default 365 dage, konfigurerbart pr. kunde/site/kamera)
ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS retention_days INTEGER DEFAULT 365;

-- 2. Deletion log — revisionsspor for slettede captures (uafhængig af billedet)
CREATE TABLE IF NOT EXISTS capture_deletion_log (
    id SERIAL PRIMARY KEY,
    capture_id INTEGER NOT NULL,
    camera_id VARCHAR(36) NOT NULL,
    customer_id VARCHAR(36),
    site_id VARCHAR(36),
    filename VARCHAR(255) NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deletion_reason VARCHAR(100),
    retention_days INTEGER,
    performed_by VARCHAR(100),
    file_size BIGINT,
    CONSTRAINT fk_deletion_capture FOREIGN KEY (capture_id) REFERENCES captures(id) ON DELETE CASCADE
);

-- 3. Indeks for performance
CREATE INDEX IF NOT EXISTS idx_deletion_log_camera ON capture_deletion_log(camera_id);
CREATE INDEX IF NOT EXISTS idx_deletion_log_customer ON capture_deletion_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_deletion_log_site ON capture_deletion_log(site_id);
CREATE INDEX IF NOT EXISTS idx_deletion_log_deleted_at ON capture_deletion_log(deleted_at);

-- 4. Trigger til automatisk logging (OPTIONAL - kan implementeres senere)
-- Dette ville automatisk logge sletninger, men kræver at captures-tabellen
-- har en deleted_at kolonne. For nu logges sletninger fra application-laget.
