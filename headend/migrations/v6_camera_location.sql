-- ═══════════════════════════════════════════════════════════════════════
-- Migration v6: Kamera lokation
-- Tilføjer camera_id til bootstrap_tokens så enrollment kan auto-oprette
-- DeviceAssignment og binde device til den rigtige kamera-lokation.
-- ═══════════════════════════════════════════════════════════════════════

-- bootstrap_tokens: knyt til logisk kamera/lokation ved provisionering
ALTER TABLE bootstrap_tokens
    ADD COLUMN IF NOT EXISTS camera_id VARCHAR(36) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_bootstrap_tokens_camera_id
    ON bootstrap_tokens(camera_id);

-- cameras: sørg for customer_name cached-kolonne (view-friendly)
-- (cameras har allerede site_id og customer_id — dette er blot en reminder)

-- device_assignments: tilføj note_type til skelne "auto" vs "manual"
ALTER TABLE device_assignments
    ADD COLUMN IF NOT EXISTS assignment_type VARCHAR(20) DEFAULT 'manual';
-- 'auto' = oprettet automatisk ved enrollment
-- 'manual' = oprettet manuelt via UI
