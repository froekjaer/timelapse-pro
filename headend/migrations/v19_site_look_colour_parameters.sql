-- Migration: persist advanced Site Look colour-temperature parameters
-- Version: 19
-- Date: 2026-07-15

ALTER TABLE site_look_config
    ADD COLUMN IF NOT EXISTS neutral_kelvin INT DEFAULT 6500,
    ADD COLUMN IF NOT EXISTS warm_lab_threshold DECIMAL(7,2) DEFAULT 20,
    ADD COLUMN IF NOT EXISTS cool_lab_threshold DECIMAL(7,2) DEFAULT -10,
    ADD COLUMN IF NOT EXISTS warm_kelvin_multiplier DECIMAL(8,2) DEFAULT 50,
    ADD COLUMN IF NOT EXISTS cool_kelvin_multiplier DECIMAL(8,2) DEFAULT 80,
    ADD COLUMN IF NOT EXISTS kelvin_min INT DEFAULT 2700,
    ADD COLUMN IF NOT EXISTS kelvin_max INT DEFAULT 10000;

ALTER TABLE site_look_config
    DROP CONSTRAINT IF EXISTS site_look_kelvin_range_valid;

ALTER TABLE site_look_config
    ADD CONSTRAINT site_look_kelvin_range_valid
    CHECK (kelvin_min <= neutral_kelvin AND neutral_kelvin <= kelvin_max);
