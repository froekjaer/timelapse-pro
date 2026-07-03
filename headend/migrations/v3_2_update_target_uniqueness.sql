-- TimeLapse Pro v3.2
-- Ensure one deployment target row per update/device.

DELETE FROM update_targets ut
WHERE NOT EXISTS (
  SELECT 1 FROM pending_updates pu WHERE pu.id = ut.pending_update_id
);

WITH ranked AS (
  SELECT
    id,
    row_number() OVER (
      PARTITION BY pending_update_id, device_id
      ORDER BY id DESC
    ) AS rn
  FROM update_targets
)
DELETE FROM update_targets ut
USING ranked r
WHERE ut.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_update_targets_update_device
ON update_targets(pending_update_id, device_id);
