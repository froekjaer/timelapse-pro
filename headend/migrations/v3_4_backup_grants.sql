-- TimeLapse Pro v3.4 - Headend backup grants
-- Ensures a dedicated backup database role can dump all public tables.
--
-- Compliance rationale:
--   ISO 27001/NIS2/CRA: backup evidence must cover the full operational DB.
--   IEC 62443: restore capability requires complete configuration and audit data.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'timelapse_backup') THEN
        CREATE ROLE timelapse_backup LOGIN BYPASSRLS;
    ELSE
        ALTER ROLE timelapse_backup BYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO timelapse;
GRANT USAGE ON SCHEMA public TO timelapse_backup;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO timelapse;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO timelapse_backup;

GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO timelapse;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO timelapse_backup;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO timelapse;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO timelapse_backup;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO timelapse;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO timelapse_backup;
