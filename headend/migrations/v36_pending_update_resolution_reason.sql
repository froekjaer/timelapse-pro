-- TimeLapse Pro - v36 Explicit resolution_reason on pending_updates
-- Peter (2026-09-03): "Der er en række opdateringer der er afviste, blokeret og
-- rullet tilbage. Kan du forklare årsagen?" — the reason for a status change was
-- only ever available by reading free-text prose stuffed into `description`.
-- This adds a short, dedicated field set at every write site that blocks,
-- rejects, rolls back, or supersedes a PendingUpdate, so the UI/API can surface
-- "why" without parsing description. NULL for rows written before this column
-- existed. See Dokumentation/UPDATE_GOVERNANCE_DIAGNOSIS_2026-09-01.md.

ALTER TABLE pending_updates ADD COLUMN IF NOT EXISTS resolution_reason TEXT;
