-- ═══════════════════════════════════════════════════════════════════════════
-- TimeLapse Pro — Migration v2.9.0: Security Events (Mini-SIEM)
-- ───────────────────────────────────────────────────────────────────────────
-- Kør: psql -d timelapse_db -f v2_9_security.sql
-- Idempotent: ja
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS security_events (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(50)     NOT NULL,
    event_type      VARCHAR(50)     NOT NULL,
    -- ssh_failure | ssh_success | sudo_use | sudo_failure
    -- service_crash | new_user | passwd_change
    severity        VARCHAR(20)     NOT NULL DEFAULT 'info',
    -- info | warning | critical
    username        VARCHAR(100),
    source_ip       VARCHAR(45),    -- IPv4 + IPv6
    raw_message     TEXT,
    occurred_at     TIMESTAMPTZ     NOT NULL,
    received_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    -- Deduplicering: samme event fra samme node inden for 5 sek ignoreres
    dedup_hash      VARCHAR(64)     UNIQUE
);

-- Indeks til hurtige queries
CREATE INDEX IF NOT EXISTS ix_sec_events_device_id
    ON security_events (device_id);
CREATE INDEX IF NOT EXISTS ix_sec_events_occurred_at
    ON security_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_sec_events_severity
    ON security_events (severity);
CREATE INDEX IF NOT EXISTS ix_sec_events_event_type
    ON security_events (event_type);
CREATE INDEX IF NOT EXISTS ix_sec_events_source_ip
    ON security_events (source_ip)
    WHERE source_ip IS NOT NULL;

-- Rettigheder
GRANT ALL PRIVILEGES ON TABLE security_events TO timelapse;
GRANT USAGE, SELECT ON SEQUENCE security_events_id_seq TO timelapse;

-- Automatisk oprydning: behold kun 90 dage (kør via pg_cron eller manuelt)
-- DELETE FROM security_events WHERE occurred_at < now() - interval '90 days';

-- Verifikation
DO $$
BEGIN
    RAISE NOTICE 'security_events: %',
        CASE WHEN EXISTS (
            SELECT FROM information_schema.tables WHERE table_name = 'security_events'
        ) THEN '✅ OK' ELSE '❌ MANGLER' END;
END $$;

COMMIT;
