-- 2026-08-08 (Claude, Peter): config-inheritance for manual on-camera
-- changes. `cameras.config` is the DESIRED state (pushed down to Edge via
-- the hierarchical config resolver). This is the OBSERVED state — what a
-- technician's camera-session (edge/camera/technician_session.py) actually
-- read off the camera's dials/menu when the session ended, which may have
-- drifted from `config` if they preferred adjusting the camera by hand.
-- Deliberately NOT auto-applied to `config` — see
-- headend/api/camera_hardware_api.py for the read/compare endpoint; a human
-- decides whether to accept the drift as the new desired state.
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS observed_settings TEXT;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS observed_settings_at TIMESTAMPTZ;
