-- TimeLapse Pro - v37 Per-package detail on batch-style pending_updates rows
-- Peter (2026-09-07): CMDB page showed everything as "current version" even
-- though hundreds of known-outdated OS/Python packages exist. Root cause:
-- os_security/os_updates/dependency_updates/dependency_security bundle many
-- packages into ONE PendingUpdate row with an aggregate "N pakker" version
-- string, and the CMDB page's per-component table can only parse a
-- "name version -> version" style string (Homebrew's per-package format) —
-- batch rows were silently dropped from that table entirely.
-- See Dokumentation/HANDOVER_LOG.md, 2026-09-07 entry.

ALTER TABLE pending_updates ADD COLUMN IF NOT EXISTS package_details TEXT;
