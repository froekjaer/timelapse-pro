-- =============================================================================
-- TimeLapse Pro - v3.2 CMDB installed-state inventory
-- Agents report installed hardware/firmware/OS/software state only. Headend
-- compares that state with signed/curated update catalogs and artifacts.
--
-- Compliance intent:
--   SABSA: business-risk traceability from CMDB asset state to update decisions.
--   IEC 62443: asset inventory, secure maintenance and controlled update channels.
--   ISO 27000: auditable change/configuration management evidence.
--   NIS2: operational resilience and vulnerability/update governance.
--   CRA: secure-by-design update handling, SBOM/package evidence and vulnerability response.
-- =============================================================================

ALTER TABLE device_inventory
    ADD COLUMN IF NOT EXISTS firmware_version   VARCHAR(200),
    ADD COLUMN IF NOT EXISTS package_manager    VARCHAR(50),
    ADD COLUMN IF NOT EXISTS os_packages        TEXT,
    ADD COLUMN IF NOT EXISTS software_inventory TEXT;

COMMENT ON COLUMN device_inventory.firmware_version IS
    'Installed firmware/boot ROM/board firmware reported by the node.';
COMMENT ON COLUMN device_inventory.package_manager IS
    'Primary local package manager observed on the node, e.g. apt, macos/softwareupdate, brew.';
COMMENT ON COLUMN device_inventory.os_packages IS
    'JSON object/list of installed OS packages. This is installed state, not update availability.';
COMMENT ON COLUMN device_inventory.software_inventory IS
    'JSON object of relevant installed applications/components. This is installed state, not update availability.';
