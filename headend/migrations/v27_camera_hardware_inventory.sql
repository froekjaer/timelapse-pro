-- Physical camera hardware CMDB (2026-08-08, Claude/Peter). The `cameras`
-- table already had `model`/`serial_number` columns but nothing ever
-- populated them — this migration adds the fields to actually collect from
-- the camera itself over PTP/gphoto2, plus a small editable reference table
-- so "is this camera's firmware current?" doesn't require redeploying code.
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS firmware_version VARCHAR(50);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS battery_level_pct INTEGER;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS storage_free_mb INTEGER;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS storage_free_images_est INTEGER;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS shutter_count INTEGER;
-- shutter_count_source: 'canon_ptp_shuttercounter' | 'nikon_exif_mechanical'
-- | 'nikon_exif_total' | NULL (unknown/unsupported for this model).
-- Distinct sources are not directly comparable — see admin-guide note.
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS shutter_count_source VARCHAR(40);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS hardware_inventory_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS camera_firmware_reference (
    id BIGSERIAL PRIMARY KEY,
    manufacturer VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    latest_version VARCHAR(50) NOT NULL,
    rated_shutter_actuations INTEGER,
    notes TEXT,
    source_url VARCHAR(500),
    updated_by VARCHAR(100) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_camera_firmware_reference_model UNIQUE (manufacturer, model)
);

-- Seeded 2026-08-08 from manufacturer support pages (see source_url). This
-- table is meant to be kept current by hand as new firmware ships — it is
-- deliberately NOT auto-fetched from the internet (no reliable, stable API
-- for either vendor), so treat it as a living reference, not a live feed.
INSERT INTO camera_firmware_reference (manufacturer, model, latest_version, rated_shutter_actuations, notes, source_url, updated_by)
VALUES
    ('Canon', 'Canon EOS 1300D', '1.2.0', 100000,
     'v1.2.0 retter en PTP-kommunikations-sårbarhed (efter v1.1.1). Relevant for os, da kameraet netop styres via PTP.',
     'https://sg.canon/en/support/0400612202', 'claude'),
    ('Canon', 'Canon EOS 2000D', '1.2.1', 100000,
     'Også solgt som EOS Rebel T7 / EOS 1500D — identisk firmware. v1.0.1 rettede en PTP-sårbarhed; v1.2.1 er en stabilitetsopdatering.',
     'https://www.usa.canon.com/support/canon-product-advisories/Firmware-Notice-EOS-Rebel-T7-Firmware-Version-1-2-1', 'claude'),
    ('Nikon', 'NIKON Z30', 'C1.20', 100000,
     'C1.10 tilføjede "Save zoom position (PZ lenses)" — bør være aktiveret for vores power zoom-kits. Skudtæller er upålidelig for denne model ved videobrug (elektronisk lukker tælles ikke mekanisk), men stillbilleder (vores brug) rammer mekanisk lukker.',
     'https://downloadcenter.nikonimglib.com/en/download/fw/556.html', 'claude')
ON CONFLICT (manufacturer, model) DO NOTHING;
