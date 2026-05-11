-- ═══════════════════════════════════════════════════════════════════════════
-- TimeLapse Pro — Migration v2.8.0: CMDB
-- ───────────────────────────────────────────────────────────────────────────
-- Database : timelapse_db (PostgreSQL)
-- Dato     : 2026-05-11
-- Køres    : psql -U postgres -d timelapse_db -f v2_8_cmdb.sql
-- Idempotent: ja (IF NOT EXISTS / DO NOTHING)
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── device_inventory ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS device_inventory (
    id                      SERIAL PRIMARY KEY,
    device_id               VARCHAR(50)  NOT NULL UNIQUE,

    -- Miljø
    environment             VARCHAR(20)  NOT NULL DEFAULT 'production',
    -- CHECK (environment IN ('lab', 'staging', 'production'))
    -- (CHECK constraint tilføjes separat for at undgå fejl ved genafvikling)

    -- Hardware
    hardware_model          VARCHAR(100),
    soc_model               VARCHAR(50),
    cpu_cores               INTEGER,
    ram_mb                  INTEGER,
    mac_address             VARCHAR(20),
    serial_number           VARCHAR(100),
    hostname                VARCHAR(100),

    -- OS / Software
    os_name                 VARCHAR(100),
    kernel_version          VARCHAR(100),
    python_version          VARCHAR(20),
    app_version             VARCHAR(50),
    venv_packages           TEXT,           -- JSON

    -- Storage (boot)
    boot_storage_type       VARCHAR(20),    -- emmc | sd | nvme
    boot_storage_total_gb   FLOAT,
    boot_storage_used_pct   FLOAT,

    -- Storage (data-partition)
    data_partition_path     VARCHAR(100),
    data_partition_total_gb FLOAT,
    data_partition_used_pct FLOAT,

    -- Netværk
    primary_interface       VARCHAR(20),
    wifi_capable            BOOLEAN         DEFAULT FALSE,
    wifi_ssid               VARCHAR(100),

    -- Signering
    gpg_fingerprint         VARCHAR(64),

    -- Lokation (pre-Location Model)
    location_id             VARCHAR(36),

    -- Provisioning
    provisioned_at          TIMESTAMPTZ,
    provisioned_by          VARCHAR(100),

    -- Tracking
    inventory_reported_at   TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_device_inventory_device_id
    ON device_inventory (device_id);

-- Tilføj CHECK constraint kun hvis den ikke allerede eksisterer
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_device_inventory_environment'
    ) THEN
        ALTER TABLE device_inventory
            ADD CONSTRAINT ck_device_inventory_environment
            CHECK (environment IN ('lab', 'staging', 'production'));
    END IF;
END $$;


-- ── break_glass_accounts ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS break_glass_accounts (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(50)  NOT NULL,
    admin_username  VARCHAR(100) NOT NULL,

    -- SSH-konto på edge
    ssh_username    VARCHAR(50)  NOT NULL DEFAULT 'emergency',
    password_enc    TEXT         NOT NULL,   -- Fernet-krypteret
    public_key      TEXT,                    -- Admin's SSH public key

    -- Livscyklus
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ,
    last_used_by    VARCHAR(100),
    rotated_at      TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,

    -- Audit
    checkout_count  INTEGER      NOT NULL DEFAULT 0,
    rotation_reason TEXT,

    CONSTRAINT uq_breakglass_device_admin UNIQUE (device_id, admin_username)
);

CREATE INDEX IF NOT EXISTS ix_break_glass_device_id
    ON break_glass_accounts (device_id);


-- ── updated_at auto-trigger ─────────────────────────────────────────────────
-- Holder updated_at synkroniseret uden at SQLAlchemy onupdate skal bruges
-- (onupdate virker ikke altid ved direkte SQL-opdateringer)

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_device_inventory_updated_at ON device_inventory;
CREATE TRIGGER trg_device_inventory_updated_at
    BEFORE UPDATE ON device_inventory
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── Verifikation ─────────────────────────────────────────────────────────────

DO $$
DECLARE
    t1 BOOLEAN := EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'device_inventory');
    t2 BOOLEAN := EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'break_glass_accounts');
BEGIN
    RAISE NOTICE 'device_inventory: %', CASE WHEN t1 THEN '✅ OK' ELSE '❌ MANGLER' END;
    RAISE NOTICE 'break_glass_accounts: %', CASE WHEN t2 THEN '✅ OK' ELSE '❌ MANGLER' END;
END $$;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- Kør migration:
--   cd ~/timelapse-pro/headend
--   psql -U postgres -d timelapse_db -f migrations/v2_8_cmdb.sql
--
-- Verifikér:
--   psql -U postgres -d timelapse_db -c "\d device_inventory"
--   psql -U postgres -d timelapse_db -c "\d break_glass_accounts"
-- ═══════════════════════════════════════════════════════════════════════════
