-- TimeLapse Pro v3.5 — SIEM enrichment columns
-- Run as database owner/admin. The application role should not need ALTER TABLE.

ALTER TABLE security_events ADD COLUMN IF NOT EXISTS source VARCHAR(50);
ALTER TABLE security_events ADD COLUMN IF NOT EXISTS category VARCHAR(80);
ALTER TABLE security_events ADD COLUMN IF NOT EXISTS logger VARCHAR(160);
ALTER TABLE security_events ADD COLUMN IF NOT EXISTS process VARCHAR(160);
ALTER TABLE security_events ADD COLUMN IF NOT EXISTS normalized TEXT;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE security_events TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE security_events_id_seq TO timelapse;
