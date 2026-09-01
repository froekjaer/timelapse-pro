-- TimeLapse Pro - v35 Live-reported camera hardware/firmware
-- Peter (2026-09-01): get the physical camera's own hardware/firmware data
-- (not just admin-entered model/serial_number, which are separate free-text
-- fields and often left blank) into CMDB. Populated by Edge via gphoto2
-- (edge/diagnostics/camera_diagnostics.py) every sync cycle.
--
-- Remote firmware PUSH is not possible via gphoto2/PTP for any camera in the
-- current fleet (Nikon and Canon both require SD-card + on-camera menu) — see
-- HANDOVER_LOG 2026-09-01. latest_known_firmware_version is a best-effort
-- value scraped periodically from the manufacturer's own firmware page (no
-- vendor API exists), not an authoritative source.

ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reported_model VARCHAR(100);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reported_manufacturer VARCHAR(100);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reported_serial_number VARCHAR(100);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reported_firmware_version VARCHAR(50);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reported_at TIMESTAMP;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS latest_known_firmware_version VARCHAR(50);
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS latest_firmware_checked_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_cameras_reported_serial ON cameras(reported_serial_number);
