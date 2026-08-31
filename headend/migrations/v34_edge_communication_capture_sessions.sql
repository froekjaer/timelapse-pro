-- TimeLapse Pro - v34 Edge communication debug: bounded capture sessions
-- Replaces the always-on edge_api_communication_logs writer with an
-- explicit, time- and/or count-bounded capture window. No row is written
-- to edge_api_communication_logs unless an active session (matching the
-- request's device_id, or device_id IS NULL for "all devices") covers it.

CREATE TABLE IF NOT EXISTS edge_communication_capture_sessions (
    id                SERIAL PRIMARY KEY,
    device_id         VARCHAR(50),
    started_at        TIMESTAMPTZ DEFAULT NOW(),
    started_by        VARCHAR(100) NOT NULL,
    duration_minutes  INTEGER,
    max_packets       INTEGER,
    packet_count      INTEGER NOT NULL DEFAULT 0,
    stopped_at        TIMESTAMPTZ,
    stop_reason       VARCHAR(30)
);

CREATE INDEX IF NOT EXISTS idx_edge_capture_session_device ON edge_communication_capture_sessions(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_capture_session_started_at ON edge_communication_capture_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_edge_capture_session_stopped_at ON edge_communication_capture_sessions(stopped_at);

GRANT ALL PRIVILEGES ON TABLE edge_communication_capture_sessions TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE edge_communication_capture_sessions_id_seq TO timelapse;
