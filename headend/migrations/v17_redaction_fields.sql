-- Migration v17: Redaction fields for GDPR compliance (UI-010)
-- Dato: 2026-07-07
-- Beskrivelse: Tilføjer felter til sporing af GDPR data og redaction status

-- Redaction status enumeration
CREATE TYPE redaction_status_enum AS ENUM (
    'pending',      -- Afventer GDPR analyse
    'analyzed',     -- Analyseret, ingen GDPR fundet
    'detected',     -- GDPR data fundet (ansigter/nummerplader)
    'redacted',     -- Sløret/redigeret
    'exempt',       -- Fritaget (fx lukket byggeplads)
    'skipped'       -- Sprunget over (ingen AI tilgængelig)
);

-- Tilføj redaction felter til captures
ALTER TABLE captures
    ADD COLUMN redaction_status redaction_status_enum DEFAULT 'pending',
    ADD COLUMN has_gdpr_data BOOLEAN DEFAULT NULL,
    ADD COLUMN redaction_method VARCHAR(50),  -- 'opencv_blur', 'manual', 'none'
    ADD COLUMN gdpr_detections JSONB,        -- {faces: [{bbox, confidence}], plates: [{bbox, confidence}]}
    ADD COLUMN redacted_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN redacted_by VARCHAR(100);      -- 'auto' eller brugernavn

-- Index for queries på redaction status
CREATE INDEX idx_captures_redaction_status ON captures(redaction_status) WHERE redaction_status IS NOT NULL;
CREATE INDEX idx_captures_has_gdpr_data ON captures(has_gdpr_data) WHERE has_gdpr_data IS NOT NULL;

-- Kommentar
COMMENT ON COLUMN captures.redaction_status IS 'Redaction workflow status: pending/analyzed/detected/redacted/exempt/skipped';
COMMENT ON COLUMN captures.has_gdpr_data IS 'TRUE hvis GDPR-data (ansigter/nummerplader) er detekteret';
COMMENT ON COLUMN captures.redaction_method IS 'Metode brugt til redaction: opencv_blur/manual/none';
COMMENT ON COLUMN captures.gdpr_detections IS 'JSONB med detaljeret detection data: {faces: [], plates: []}';
COMMENT ON COLUMN captures.redacted_at IS 'Tidspunkt for redaction';
COMMENT ON COLUMN captures.redacted_by IS 'Hvem udførte redaction (auto eller brugernavn)';
