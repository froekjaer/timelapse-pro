-- =============================================================================
-- TimeLapse Pro — Database Schema v2
-- AI Tags, Cross-Reference, Abstraction Layer, GDPR
-- =============================================================================
-- Køres som migration oven på eksisterende schema.
-- Bruger PostgreSQL RLS til GDPR-isolation.
-- =============================================================================

-- ── Roller ────────────────────────────────────────────────────────────────────
-- Oprettes én gang. Bruges af RLS policies.

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'timelapse_app') THEN
        CREATE ROLE timelapse_app NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'timelapse_gdpr_admin') THEN
        CREATE ROLE timelapse_gdpr_admin NOLOGIN;
    END IF;
END $$;


-- =============================================================================
-- LAG 1: AI ANALYSE
-- Én række pr. capture — fuld AI-output
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_analyses (
    id              SERIAL PRIMARY KEY,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    location_id     TEXT,                        -- kopi af location på analyse-tidspunkt
    analysed_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_vision    TEXT NOT NULL,               -- fx 'llama3.2-vision:11b'
    model_version   TEXT,
    duration_ms     INTEGER,                     -- analyse-tid

    -- Billed-beskrivelse
    scene_dk        TEXT,                        -- dansk ét-sætnings beskrivelse
    change_detected BOOLEAN DEFAULT FALSE,       -- noget nyt ift. reference?
    change_summary  TEXT,                        -- hvad er nyt?

    -- Kvalitets-override fra AI (supplerer OpenCV)
    ai_quality_flag TEXT,                        -- ok / beskidt_linse / tåget / osv.
    ai_quality_ok   BOOLEAN DEFAULT TRUE,

    -- Reference-billede brugt til change detection
    reference_capture_id INTEGER REFERENCES captures(id) ON DELETE SET NULL,

    -- Rå JSON-output fra modellen (til debugging/reanalyse)
    raw_response    JSONB,

    -- GDPR-flag: indeholder analysen persondata?
    has_gdpr_data   BOOLEAN DEFAULT FALSE,

    CONSTRAINT uq_ai_analyses_capture UNIQUE (capture_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_analyses_capture   ON ai_analyses(capture_id);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_location  ON ai_analyses(location_id);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_analysed  ON ai_analyses(analysed_at);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_change    ON ai_analyses(change_detected) WHERE change_detected = TRUE;


-- =============================================================================
-- LAG 1: TAG VOKABULAR
-- Selvudvidende — foruddefinerede + model-opfundne
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_tag_vocabulary (
    id          SERIAL PRIMARY KEY,
    tag         TEXT UNIQUE NOT NULL,
    category    TEXT NOT NULL DEFAULT 'øvrige',
    count       INTEGER DEFAULT 0,               -- antal gange set
    first_seen  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    predefined  BOOLEAN DEFAULT FALSE,
    approved    BOOLEAN DEFAULT TRUE,            -- false = afventer review
    rejected    BOOLEAN DEFAULT FALSE,
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_vocab_tag      ON ai_tag_vocabulary(tag);
CREATE INDEX IF NOT EXISTS idx_vocab_approved ON ai_tag_vocabulary(approved, rejected);
CREATE INDEX IF NOT EXISTS idx_vocab_category ON ai_tag_vocabulary(category);


-- =============================================================================
-- LAG 2: KRYDSREFERENCE — Capture ↔ Tags (M:M)
-- =============================================================================

CREATE TABLE IF NOT EXISTS capture_tags (
    id              SERIAL PRIMARY KEY,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    tag_id          INTEGER NOT NULL REFERENCES ai_tag_vocabulary(id) ON DELETE CASCADE,
    analysis_id     INTEGER REFERENCES ai_analyses(id) ON DELETE SET NULL,
    confidence      REAL DEFAULT 1.0,            -- 0.0–1.0, fra modellen hvis muligt
    is_new_tag      BOOLEAN DEFAULT FALSE,        -- flagget som nyt af modellen
    tagged_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_capture_tag UNIQUE (capture_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_capture_tags_capture  ON capture_tags(capture_id);
CREATE INDEX IF NOT EXISTS idx_capture_tags_tag      ON capture_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_capture_tags_new      ON capture_tags(is_new_tag) WHERE is_new_tag = TRUE;

-- Hjælpefunktion: tæl tag-brug op i vokabular
CREATE OR REPLACE FUNCTION update_tag_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE ai_tag_vocabulary
    SET count    = count + 1,
        last_seen = NOW()
    WHERE id = NEW.tag_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_tag_count ON capture_tags;
CREATE TRIGGER trg_update_tag_count
    AFTER INSERT ON capture_tags
    FOR EACH ROW EXECUTE FUNCTION update_tag_count();


-- =============================================================================
-- LAG 3: ABSTRAKTIONSLAG — Views
-- Disse views eksponerer ALDRIG GDPR-data.
-- Al kode der ikke er GDPR-admin bruger disse views.
-- =============================================================================

-- Capture-oversigt uden GDPR-felter
CREATE OR REPLACE VIEW v_capture_public AS
SELECT
    c.id,
    c.device_id,
    c.filename,
    c.captured_at,
    c.filesize,
    c.camera_model,
    c.quality_flag,
    c.quality_passed,
    c.blur_score,
    c.brightness_mean,
    c.exposure_time,
    c.aperture,
    c.iso,
    c.uploaded,
    -- AI-data (ikke GDPR)
    a.scene_dk,
    a.change_detected,
    a.change_summary,
    a.ai_quality_flag,
    a.ai_quality_ok,
    a.model_vision,
    a.analysed_at,
    -- GDPR-flag (boolean kun — ikke selve dataen)
    COALESCE(a.has_gdpr_data, FALSE) AS has_gdpr_data
FROM captures c
LEFT JOIN ai_analyses a ON a.capture_id = c.id;

-- Tag-statistik pr. lokation og dato
CREATE OR REPLACE VIEW v_tag_statistics AS
SELECT
    tv.tag,
    tv.category,
    tv.count          AS total_count,
    tv.approved,
    tv.predefined,
    tv.first_seen,
    tv.last_seen,
    -- Antal unikke lokationer tagget er set på
    COUNT(DISTINCT a.location_id) AS location_count,
    -- Seneste dato tagget blev set
    MAX(ct.tagged_at) AS latest_occurrence
FROM ai_tag_vocabulary tv
LEFT JOIN capture_tags ct  ON ct.tag_id = tv.id
LEFT JOIN ai_analyses  a   ON a.id = ct.analysis_id
WHERE tv.approved = TRUE AND tv.rejected = FALSE
GROUP BY tv.id, tv.tag, tv.category, tv.count, tv.approved, tv.predefined, tv.first_seen, tv.last_seen;

-- Tags pr. capture (flad liste til API)
CREATE OR REPLACE VIEW v_capture_tags_flat AS
SELECT
    ct.capture_id,
    c.filename,
    c.captured_at,
    c.device_id,
    a.location_id,
    array_agg(tv.tag ORDER BY ct.confidence DESC) FILTER (WHERE tv.approved = TRUE) AS tags,
    array_agg(tv.tag ORDER BY ct.confidence DESC) FILTER (WHERE ct.is_new_tag = TRUE AND tv.approved = FALSE) AS pending_tags,
    COUNT(tv.id) FILTER (WHERE tv.approved = TRUE) AS tag_count
FROM capture_tags ct
JOIN captures           c   ON c.id = ct.capture_id
JOIN ai_tag_vocabulary  tv  ON tv.id = ct.tag_id
LEFT JOIN ai_analyses   a   ON a.id = ct.analysis_id
GROUP BY ct.capture_id, c.filename, c.captured_at, c.device_id, a.location_id;

-- Tags over tid pr. lokation (til dashboard-grafer)
CREATE OR REPLACE VIEW v_location_tag_timeline AS
SELECT
    a.location_id,
    tv.tag,
    tv.category,
    DATE(c.captured_at) AS capture_date,
    COUNT(*)            AS occurrences
FROM capture_tags ct
JOIN captures          c   ON c.id  = ct.capture_id
JOIN ai_analyses       a   ON a.id  = ct.analysis_id
JOIN ai_tag_vocabulary tv  ON tv.id = ct.tag_id
WHERE tv.approved = TRUE AND tv.rejected = FALSE
GROUP BY a.location_id, tv.tag, tv.category, DATE(c.captured_at);

-- Change detection oversigt
CREATE OR REPLACE VIEW v_change_events AS
SELECT
    a.id              AS analysis_id,
    c.id              AS capture_id,
    c.filename,
    c.captured_at,
    c.device_id,
    a.location_id,
    a.change_summary,
    a.model_vision,
    a.analysed_at,
    -- Tags der indikerer ændring
    array_agg(tv.tag) FILTER (WHERE tv.category = 'change_detection' AND tv.approved = TRUE) AS change_tags
FROM ai_analyses a
JOIN captures          c   ON c.id = a.capture_id
LEFT JOIN capture_tags ct  ON ct.capture_id = c.id
LEFT JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id
WHERE a.change_detected = TRUE
GROUP BY a.id, c.id, c.filename, c.captured_at, c.device_id, a.location_id, a.change_summary, a.model_vision, a.analysed_at;


-- =============================================================================
-- LAG 1: GDPR-DATA (isoleret tabel)
-- Indeholder: ansigter, nummerplader, persondata
-- RLS sikrer at KUN timelapse_gdpr_admin kan læse
-- =============================================================================

CREATE TABLE IF NOT EXISTS gdpr_detections (
    id              SERIAL PRIMARY KEY,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE RESTRICT,
    analysis_id     INTEGER REFERENCES ai_analyses(id) ON DELETE SET NULL,
    detected_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    location_id     TEXT,

    -- Type: face / license_plate / person_identified / other
    detection_type  TEXT NOT NULL,

    -- Hvad der blev set (ALDRIG eksponeret via normale views)
    detail_json     JSONB,           -- fx {"plate": "AB12345", "confidence": 0.92}
    bounding_box    JSONB,           -- {x, y, w, h} i billedet

    -- Retention
    retain_until    TIMESTAMP WITH TIME ZONE,   -- NULL = manuelt
    deletion_reason TEXT,
    deleted_at      TIMESTAMP WITH TIME ZONE,   -- soft delete

    -- Lovgrundlag (GDPR Art. 6)
    legal_basis     TEXT DEFAULT 'legitimate_interest',
    consent_ref     TEXT            -- reference til consent_log hvis relevant
);

CREATE INDEX IF NOT EXISTS idx_gdpr_capture  ON gdpr_detections(capture_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_type     ON gdpr_detections(detection_type);
CREATE INDEX IF NOT EXISTS idx_gdpr_retain   ON gdpr_detections(retain_until) WHERE deleted_at IS NULL;

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE gdpr_detections ENABLE ROW LEVEL SECURITY;

-- Ingen adgang for normale brugere
CREATE POLICY gdpr_deny_default ON gdpr_detections
    FOR ALL TO timelapse_app
    USING (FALSE);

-- Kun gdpr_admin-rollen kan se ikke-slettede rækker
CREATE POLICY gdpr_admin_select ON gdpr_detections
    FOR SELECT TO timelapse_gdpr_admin
    USING (deleted_at IS NULL);

CREATE POLICY gdpr_admin_insert ON gdpr_detections
    FOR INSERT TO timelapse_gdpr_admin
    WITH CHECK (TRUE);

CREATE POLICY gdpr_admin_update ON gdpr_detections
    FOR UPDATE TO timelapse_gdpr_admin
    USING (deleted_at IS NULL);


-- =============================================================================
-- GDPR AUDIT LOG
-- Uforanderlig log over enhver adgang til GDPR-data
-- INSERT only — aldrig UPDATE/DELETE
-- =============================================================================

CREATE TABLE IF NOT EXISTS gdpr_access_log (
    id              BIGSERIAL PRIMARY KEY,
    accessed_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_id         TEXT NOT NULL,           -- auth-brugerens ID
    user_email      TEXT,
    action          TEXT NOT NULL,           -- SELECT / EXPORT / DELETE / APPROVE
    detection_ids   INTEGER[],               -- hvilke rækker
    capture_ids     INTEGER[],
    reason          TEXT,                    -- hvorfor (påkrævet ved eksport)
    ip_address      TEXT,
    session_id      TEXT,
    result          TEXT DEFAULT 'ok'        -- ok / denied / error
);

-- Ingen UPDATE/DELETE på audit log — insert only via trigger
ALTER TABLE gdpr_access_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_insert_only ON gdpr_access_log
    FOR INSERT TO timelapse_gdpr_admin WITH CHECK (TRUE);

CREATE POLICY audit_select ON gdpr_access_log
    FOR SELECT TO timelapse_gdpr_admin USING (TRUE);

-- Ingen DELETE overhovedet (heller ikke admin) — beskyttet via REVOKE
REVOKE DELETE ON gdpr_access_log FROM timelapse_gdpr_admin;
REVOKE UPDATE ON gdpr_access_log FROM timelapse_gdpr_admin;


-- =============================================================================
-- GDPR SLETNINGSKØ
-- Planlagte sletninger (retention policy + sletteanmodninger)
-- =============================================================================

CREATE TABLE IF NOT EXISTS gdpr_deletion_queue (
    id              SERIAL PRIMARY KEY,
    detection_id    INTEGER REFERENCES gdpr_detections(id),
    capture_id      INTEGER REFERENCES captures(id),
    queued_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scheduled_for   TIMESTAMP WITH TIME ZONE NOT NULL,
    reason          TEXT NOT NULL,           -- retention_expired / user_request / manual
    requested_by    TEXT,                    -- user_id hvis anmodning
    completed_at    TIMESTAMP WITH TIME ZONE,
    status          TEXT DEFAULT 'pending'   -- pending / completed / failed
);

CREATE INDEX IF NOT EXISTS idx_gdpr_queue_pending ON gdpr_deletion_queue(scheduled_for)
    WHERE status = 'pending';


-- =============================================================================
-- GDPR ADMIN VIEW (kun for gdpr_admin-rollen)
-- =============================================================================

CREATE OR REPLACE VIEW v_gdpr_admin AS
SELECT
    gd.id,
    gd.capture_id,
    c.filename,
    c.captured_at,
    gd.location_id,
    gd.detection_type,
    gd.detail_json,
    gd.detected_at,
    gd.retain_until,
    gd.legal_basis,
    gd.deleted_at,
    -- Antal gange denne detection er tilgået
    (SELECT COUNT(*) FROM gdpr_access_log al
     WHERE gd.id = ANY(al.detection_ids)) AS access_count,
    -- Er der en planlagt sletning?
    (SELECT scheduled_for FROM gdpr_deletion_queue dq
     WHERE dq.detection_id = gd.id AND dq.status = 'pending'
     ORDER BY scheduled_for LIMIT 1) AS scheduled_deletion
FROM gdpr_detections gd
JOIN captures c ON c.id = gd.capture_id
WHERE gd.deleted_at IS NULL;

-- Kun gdpr_admin kan se dette view
REVOKE ALL ON v_gdpr_admin FROM PUBLIC;
GRANT SELECT ON v_gdpr_admin TO timelapse_gdpr_admin;


-- =============================================================================
-- RETTIGHEDER
-- =============================================================================

-- Normale app-rettigheder (ingen GDPR)
GRANT SELECT ON v_capture_public         TO timelapse_app;
GRANT SELECT ON v_tag_statistics         TO timelapse_app;
GRANT SELECT ON v_capture_tags_flat      TO timelapse_app;
GRANT SELECT ON v_location_tag_timeline  TO timelapse_app;
GRANT SELECT ON v_change_events          TO timelapse_app;
GRANT SELECT, INSERT, UPDATE ON ai_analyses        TO timelapse_app;
GRANT SELECT, INSERT, UPDATE ON ai_tag_vocabulary  TO timelapse_app;
GRANT SELECT, INSERT         ON capture_tags       TO timelapse_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public      TO timelapse_app;

-- GDPR admin (inkluderer alt app har, plus GDPR-tabeller)
GRANT timelapse_app TO timelapse_gdpr_admin;
GRANT SELECT, INSERT, UPDATE ON gdpr_detections    TO timelapse_gdpr_admin;
GRANT SELECT, INSERT         ON gdpr_access_log    TO timelapse_gdpr_admin;
GRANT SELECT, INSERT, UPDATE ON gdpr_deletion_queue TO timelapse_gdpr_admin;
GRANT SELECT ON v_gdpr_admin                       TO timelapse_gdpr_admin;
