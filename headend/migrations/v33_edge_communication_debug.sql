-- TimeLapse Pro - v33 Edge/Headend communication debug observations
-- Stores sanitized Edge-facing API request metadata for admin diagnostics.
-- Private keys, tokens, passwords and authorization material must not be stored here.

CREATE TABLE IF NOT EXISTS edge_api_communication_logs (
    id                     SERIAL PRIMARY KEY,
    device_id              VARCHAR(50),
    direction              VARCHAR(20) DEFAULT 'edge_to_headend',
    method                 VARCHAR(12) NOT NULL,
    path                   VARCHAR(500) NOT NULL,
    query_string           TEXT,
    status_code            INTEGER,
    transport_scheme       VARCHAR(20),
    transport_security     VARCHAR(30),
    client_host            VARCHAR(100),
    user_agent             VARCHAR(300),
    request_content_type   VARCHAR(120),
    request_bytes          INTEGER,
    request_body_json      TEXT,
    request_body_truncated BOOLEAN DEFAULT FALSE,
    interpretation         TEXT,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edge_api_comm_device ON edge_api_communication_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_api_comm_path ON edge_api_communication_logs(path);
CREATE INDEX IF NOT EXISTS idx_edge_api_comm_status ON edge_api_communication_logs(status_code);
CREATE INDEX IF NOT EXISTS idx_edge_api_comm_transport ON edge_api_communication_logs(transport_security);
CREATE INDEX IF NOT EXISTS idx_edge_api_comm_created_at ON edge_api_communication_logs(created_at);

GRANT ALL PRIVILEGES ON TABLE edge_api_communication_logs TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE edge_api_communication_logs_id_seq TO timelapse;
