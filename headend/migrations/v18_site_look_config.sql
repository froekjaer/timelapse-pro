-- Migration: Site-Wide Look Matching Configuration
-- Version: 18
-- Date: 2026-07-12
-- Description: Hierarchical configuration system (global > customer > site > camera)
--              with edge caching support

-- ============================================================================
-- Site Look Configuration Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS site_look_config (
    id SERIAL PRIMARY KEY,

    -- Hierarchy level (which level this config applies to)
    level VARCHAR(20) NOT NULL CHECK (level IN ('global', 'customer', 'site', 'camera')),

    -- Level identifiers (only one should be set per row based on level)
    customer_id VARCHAR(255),
    site_id VARCHAR(255),
    camera_id VARCHAR(255),

    -- Feature toggle
    enabled BOOLEAN DEFAULT true,

    -- Storage configuration
    storage_path VARCHAR(500) DEFAULT '/var/lib/timelapse/site_looks',

    -- Reference settings
    reference_quality_threshold DECIMAL(5,2) DEFAULT 75.0,  -- 0-100
    auto_create_reference BOOLEAN DEFAULT true,
    auto_update_reference BOOLEAN DEFAULT false,

    -- LUT generation settings
    lut_auto_generate BOOLEAN DEFAULT true,
    lut_regeneration_interval_hours INT DEFAULT 168,  -- 7 days

    -- Polling configuration (for edge nodes)
    config_poll_interval_seconds INT DEFAULT 300,  -- 5 minutes
    config_cache_ttl_seconds INT DEFAULT 86400,  -- 24 hours (max cache if DB unreachable)

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255),

    -- Constraints
    UNIQUE (level, customer_id, site_id, camera_id),
    CHECK (
        (level = 'global' AND customer_id IS NULL AND site_id IS NULL AND camera_id IS NULL) OR
        (level = 'customer' AND customer_id IS NOT NULL AND site_id IS NULL AND camera_id IS NULL) OR
        (level = 'site' AND customer_id IS NOT NULL AND site_id IS NOT NULL AND camera_id IS NULL) OR
        (level = 'camera' AND customer_id IS NOT NULL AND site_id IS NOT NULL AND camera_id IS NOT NULL)
    )
);

-- Indexes for efficient lookups
CREATE INDEX idx_site_look_config_hierarchy ON site_look_config (level, customer_id, site_id, camera_id);
CREATE INDEX idx_site_look_config_customer ON site_look_config (customer_id) WHERE customer_id IS NOT NULL;
CREATE INDEX idx_site_look_config_site ON site_look_config (site_id) WHERE site_id IS NOT NULL;
CREATE INDEX idx_site_look_config_camera ON site_look_config (camera_id) WHERE camera_id IS NOT NULL;

-- ============================================================================
-- Global Defaults (inserted once)
-- ============================================================================

INSERT INTO site_look_config (
    level, enabled, storage_path, reference_quality_threshold,
    auto_create_reference, auto_update_reference,
    lut_auto_generate, lut_regeneration_interval_hours,
    config_poll_interval_seconds, config_cache_ttl_seconds,
    created_by
) VALUES (
    'global', true, '/var/lib/timelapse/site_looks', 75.0,
    true, false,
    true, 168,
    300, 86400,
    'system'
) ON CONFLICT (level, customer_id, site_id, camera_id) DO NOTHING;

-- ============================================================================
-- Edge Config Cache Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS edge_config_cache (
    edge_node_id VARCHAR(255) PRIMARY KEY,
    config_json JSONB NOT NULL,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    version BIGINT DEFAULT 1
);

CREATE INDEX idx_edge_config_cache_expires ON edge_config_cache (expires_at);

-- ============================================================================
-- Config Change Log (audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS site_look_config_log (
    id SERIAL PRIMARY KEY,
    edge_node_id VARCHAR(255),
    config_level VARCHAR(20),
    customer_id VARCHAR(255),
    site_id VARCHAR(255),
    camera_id VARCHAR(255),
    action VARCHAR(20),  -- 'created', 'updated', 'deleted', 'cached'
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_site_look_config_log_time ON site_look_config_log (changed_at DESC);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE site_look_config IS 'Hierarchical configuration for Site-Wide Look Matching (global > customer > site > camera)';
COMMENT ON TABLE edge_config_cache IS 'Cached configuration for edge nodes to enable offline operation';
COMMENT ON TABLE site_look_config_log IS 'Audit trail for configuration changes';

COMMENT ON COLUMN site_look_config.level IS 'Configuration level: global=system-wide, customer=per-customer, site=per-site, camera=per-camera';
COMMENT ON COLUMN site_look_config.config_poll_interval_seconds IS 'How often edge nodes should poll for config changes';
COMMENT ON COLUMN site_look_config.config_cache_ttl_seconds IS 'Maximum time edge can use cached config if DB is unreachable';
