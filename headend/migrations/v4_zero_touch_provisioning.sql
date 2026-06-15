-- TimeLapse Pro — Migration v4: Zero-touch provisioning
-- Tilføjer hardware_model, enrollment_state og ssh_pubkey til devices-tabellen.
-- Safe: bruger "IF NOT EXISTS" / "IF column does not exist" pattern.
-- Kør med: sqlite3 timelapse_headend.db < migrations/v4_zero_touch_provisioning.sql

-- SQLite understøtter ikke "ADD COLUMN IF NOT EXISTS" direkte,
-- men PRAGMA table_info kan bruges. Kør scriptet idempotent via Python:
--   python headend/tools/run_migration.py v4_zero_touch_provisioning.sql

-- hardware_model: kort id for boardet, fx "rpi4", "orangepi4pro"
ALTER TABLE devices ADD COLUMN hardware_model TEXT;

-- enrollment_state: "unassigned" (ingen site endnu) eller "active"
-- Default "active" for eksisterende enheder (bagud-kompatibelt)
ALTER TABLE devices ADD COLUMN enrollment_state TEXT DEFAULT 'active';

-- ssh_pubkey: ed25519 public key genereret af bootstrap_agent.py ved first-boot
ALTER TABLE devices ADD COLUMN ssh_pubkey TEXT;

-- Index for hurtig lookup af uassignerede enheder
CREATE INDEX IF NOT EXISTS idx_devices_enrollment_state
    ON devices (enrollment_state)
    WHERE enrollment_state = 'unassigned';
