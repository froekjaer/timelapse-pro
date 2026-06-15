-- ============================================================================
-- TimeLapse Pro — Migration v5: Batch bootstrap tokens
-- ============================================================================
-- Tilføjer multi-use support til bootstrap_tokens tabellen.
-- Batch-tokens bages ind i disk-images og kan bruges af op til max_uses enheder.
--
-- Kør som: psql postgresql://timelapse@localhost/timelapse_db -f v5_batch_bootstrap_tokens.sql
-- ============================================================================

-- max_uses: 1 = single-use (default, eksisterende tokens), N = batch
ALTER TABLE bootstrap_tokens
    ADD COLUMN IF NOT EXISTS max_uses   INTEGER NOT NULL DEFAULT 1;

-- use_count: antal gange token er brugt (atomisk increment ved enrollment)
ALTER TABLE bootstrap_tokens
    ADD COLUMN IF NOT EXISTS use_count  INTEGER NOT NULL DEFAULT 0;

-- token_type: "single" | "batch" — hurtig filtrering i admin UI
ALTER TABLE bootstrap_tokens
    ADD COLUMN IF NOT EXISTS token_type VARCHAR(20) NOT NULL DEFAULT 'single';

-- Sæt eksisterende brugte tokens korrekt
-- (used_at sat → token er brugt → use_count=1)
UPDATE bootstrap_tokens
SET use_count = 1
WHERE used_at IS NOT NULL AND use_count = 0;

-- Index på token_type for admin-listing
CREATE INDEX IF NOT EXISTS idx_bootstrap_tokens_token_type
    ON bootstrap_tokens(token_type);

-- Eksempel på oprettelse af batch-token (kør i psql):
-- INSERT INTO bootstrap_tokens
--   (token, device_label, max_uses, token_type, expires_at, created_by)
-- VALUES
--   ('btk-batch-XXXXX', 'Batch token — rpi4 image 2026-06', 500, 'batch',
--    NOW() + INTERVAL '365 days', 'admin');
