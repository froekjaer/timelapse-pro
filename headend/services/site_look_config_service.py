"""
Site-Wide Look Matching Configuration Service

Handles hierarchical configuration: global > customer > site > camera
With edge caching support for offline operation.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

log = logging.getLogger(__name__)


class SiteLookConfigService:
    """Service for managing Site-Wide Look Matching configuration."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def _get_conn(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)

    # ============================================================================
    # Configuration Resolution (with fallback)
    # ============================================================================

    def get_config(
        self,
        customer_id: Optional[str] = None,
        site_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        for_edge_node: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get resolved configuration with hierarchical fallback.

        Priority: camera > site > customer > global

        Args:
            customer_id: Customer identifier
            site_id: Site identifier
            camera_id: Camera identifier
            for_edge_node: If set, returns format suitable for edge node caching

        Returns:
            Resolved configuration dictionary
        """
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Start with global config
                config = self._get_level_config(cur, level='global') or {}

                # Apply customer override if exists
                if customer_id:
                    customer_config = self._get_level_config(cur, level='customer', customer_id=customer_id)
                    if customer_config:
                        config.update(customer_config)

                # Apply site override if exists
                if site_id:
                    site_config = self._get_level_config(cur, level='site', customer_id=customer_id, site_id=site_id)
                    if site_config:
                        config.update(site_config)

                # Apply camera override if exists
                if camera_id:
                    camera_config = self._get_level_config(
                        cur, level='camera',
                        customer_id=customer_id, site_id=site_id, camera_id=camera_id
                    )
                    if camera_config:
                        config.update(camera_config)

                # Add metadata
                config['resolved_at'] = datetime.now(timezone.utc).isoformat()
                config['hierarchy'] = {
                    'customer_id': customer_id,
                    'site_id': site_id,
                    'camera_id': camera_id,
                }

                # If for edge node, return cacheable format
                if for_edge_node:
                    return self._format_for_edge(config, for_edge_node)

                return config

    def _get_level_config(
        self, cur, level: str,
        customer_id: Optional[str] = None,
        site_id: Optional[str] = None,
        camera_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get config at specific hierarchy level."""
        query = """
            SELECT
                enabled,
                storage_path,
                reference_quality_threshold,
                auto_create_reference,
                auto_update_reference,
                lut_auto_generate,
                lut_regeneration_interval_hours,
                config_poll_interval_seconds,
                config_cache_ttl_seconds
            FROM site_look_config
            WHERE level = %s
              AND customer_id IS NOT DISTINCT FROM %s
              AND site_id IS NOT DISTINCT FROM %s
              AND camera_id IS NOT DISTINCT FROM %s
        """

        params = [level, customer_id, site_id, camera_id]
        cur.execute(query, params)
        row = cur.fetchone()

        if row:
            return dict(row)
        return None

    def _format_for_edge(self, config: Dict[str, Any], edge_node_id: str) -> Dict[str, Any]:
        """Format configuration for edge node consumption."""
        # Convert datetime and Decimal to JSON-serializable types
        def sanitize(obj):
            from decimal import Decimal
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [sanitize(item) for item in obj]
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        ttl = config.get('config_cache_ttl_seconds', 86400)
        return {
            'version': int(datetime.now(timezone.utc).timestamp()),
            'edge_node_id': edge_node_id,
            'config': sanitize(config),
            'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat(),
        }

    # ============================================================================
    # CRUD Operations
    # ============================================================================

    def upsert_config(
        self,
        level: str,
        enabled: Optional[bool] = None,
        storage_path: Optional[str] = None,
        reference_quality_threshold: Optional[float] = None,
        auto_create_reference: Optional[bool] = None,
        auto_update_reference: Optional[bool] = None,
        lut_auto_generate: Optional[bool] = None,
        lut_regeneration_interval_hours: Optional[int] = None,
        config_poll_interval_seconds: Optional[int] = None,
        config_cache_ttl_seconds: Optional[int] = None,
        neutral_kelvin: Optional[int] = None,
        warm_lab_threshold: Optional[float] = None,
        cool_lab_threshold: Optional[float] = None,
        warm_kelvin_multiplier: Optional[float] = None,
        cool_kelvin_multiplier: Optional[float] = None,
        kelvin_min: Optional[int] = None,
        kelvin_max: Optional[int] = None,
        customer_id: Optional[str] = None,
        site_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        updated_by: str = 'admin',
    ) -> Dict[str, Any]:
        """Create or update configuration at a hierarchy level."""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get old values for logging
                old_values = self._get_level_config(
                    cur, level, customer_id, site_id, camera_id
                )

                # Upsert
                query = """
                    INSERT INTO site_look_config (
                        level, customer_id, site_id, camera_id,
                        enabled, storage_path, reference_quality_threshold,
                        auto_create_reference, auto_update_reference,
                        lut_auto_generate, lut_regeneration_interval_hours,
                        config_poll_interval_seconds, config_cache_ttl_seconds,
                        neutral_kelvin, warm_lab_threshold, cool_lab_threshold,
                        warm_kelvin_multiplier, cool_kelvin_multiplier,
                        kelvin_min, kelvin_max,
                        updated_by, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, NOW()
                    )
                    ON CONFLICT (level, customer_id, site_id, camera_id)
                    DO UPDATE SET
                        enabled = COALESCE(EXCLUDED.enabled, site_look_config.enabled),
                        storage_path = COALESCE(EXCLUDED.storage_path, site_look_config.storage_path),
                        reference_quality_threshold = COALESCE(EXCLUDED.reference_quality_threshold, site_look_config.reference_quality_threshold),
                        auto_create_reference = COALESCE(EXCLUDED.auto_create_reference, site_look_config.auto_create_reference),
                        auto_update_reference = COALESCE(EXCLUDED.auto_update_reference, site_look_config.auto_update_reference),
                        lut_auto_generate = COALESCE(EXCLUDED.lut_auto_generate, site_look_config.lut_auto_generate),
                        lut_regeneration_interval_hours = COALESCE(EXCLUDED.lut_regeneration_interval_hours, site_look_config.lut_regeneration_interval_hours),
                        config_poll_interval_seconds = COALESCE(EXCLUDED.config_poll_interval_seconds, site_look_config.config_poll_interval_seconds),
                        config_cache_ttl_seconds = COALESCE(EXCLUDED.config_cache_ttl_seconds, site_look_config.config_cache_ttl_seconds),
                        neutral_kelvin = COALESCE(EXCLUDED.neutral_kelvin, site_look_config.neutral_kelvin),
                        warm_lab_threshold = COALESCE(EXCLUDED.warm_lab_threshold, site_look_config.warm_lab_threshold),
                        cool_lab_threshold = COALESCE(EXCLUDED.cool_lab_threshold, site_look_config.cool_lab_threshold),
                        warm_kelvin_multiplier = COALESCE(EXCLUDED.warm_kelvin_multiplier, site_look_config.warm_kelvin_multiplier),
                        cool_kelvin_multiplier = COALESCE(EXCLUDED.cool_kelvin_multiplier, site_look_config.cool_kelvin_multiplier),
                        kelvin_min = COALESCE(EXCLUDED.kelvin_min, site_look_config.kelvin_min),
                        kelvin_max = COALESCE(EXCLUDED.kelvin_max, site_look_config.kelvin_max),
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    RETURNING *
                """

                params = [
                    level, customer_id, site_id, camera_id,
                    enabled, storage_path, reference_quality_threshold,
                    auto_create_reference, auto_update_reference,
                    lut_auto_generate, lut_regeneration_interval_hours,
                    config_poll_interval_seconds, config_cache_ttl_seconds,
                    neutral_kelvin, warm_lab_threshold, cool_lab_threshold,
                    warm_kelvin_multiplier, cool_kelvin_multiplier,
                    kelvin_min, kelvin_max,
                    updated_by
                ]

                cur.execute(query, params)
                new_values = dict(cur.fetchone())

                # Log the change
                self._log_change(
                    cur, 'upsert', level, customer_id, site_id, camera_id,
                    old_values, new_values, updated_by
                )

                conn.commit()

                # A change can affect several devices. Purging this small
                # cache is safer than serving a stale policy for a full TTL.
                self.invalidate_edge_cache()

                log.info(f"Config upserted: level={level}, customer={customer_id}, site={site_id}, camera={camera_id}")
                return new_values

    def delete_config(
        self,
        level: str,
        customer_id: Optional[str] = None,
        site_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        deleted_by: str = 'admin',
    ) -> bool:
        """Delete configuration at a hierarchy level."""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get old values for logging
                old_values = self._get_level_config(
                    cur, level, customer_id, site_id, camera_id
                )

                query = """
                    DELETE FROM site_look_config
                    WHERE level = %s
                      AND (customer_id = %s OR customer_id IS NULL)
                      AND (site_id = %s OR site_id IS NULL)
                      AND (camera_id = %s OR camera_id IS NULL)
                """

                params = [level, customer_id, site_id, camera_id]
                cur.execute(query, params)
                affected = cur.rowcount

                if affected > 0:
                    self._log_change(
                        cur, 'deleted', level, customer_id, site_id, camera_id,
                        old_values, None, deleted_by
                    )

                conn.commit()
                if affected > 0:
                    self.invalidate_edge_cache()
                return affected > 0

    def get_all_configs(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all configurations, optionally filtered by level."""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if level:
                    query = "SELECT * FROM site_look_config WHERE level = %s ORDER BY level, customer_id, site_id, camera_id"
                    cur.execute(query, [level])
                else:
                    query = "SELECT * FROM site_look_config ORDER BY level, customer_id, site_id, camera_id"
                    cur.execute(query)

                return [dict(row) for row in cur.fetchall()]

    # ============================================================================
    # Edge Node Caching
    # ============================================================================

    def get_edge_cache(self, edge_node_id: str) -> Optional[Dict[str, Any]]:
        """Get cached configuration for an edge node."""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT config_json, cached_at, expires_at, version
                    FROM edge_config_cache
                    WHERE edge_node_id = %s AND expires_at > NOW()
                """
                cur.execute(query, [edge_node_id])
                row = cur.fetchone()

                if row:
                    payload = row['config_json']
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    if not isinstance(payload, dict):
                        return None
                    payload = dict(payload)
                    # New entries store the complete Edge response envelope.
                    # Early entries stored the resolved config directly; keep
                    # those readable until their normal expiry/refresh cycle.
                    if not isinstance(payload.get('config'), dict):
                        payload = {'config': payload}
                    payload['version'] = int(row['version'] or payload.get('version') or 0)
                    payload['cached_at'] = row['cached_at'].isoformat()
                    payload['expires_at'] = row['expires_at'].isoformat()
                    return payload
                return None

    def update_edge_cache(self, edge_node_id: str, config: Dict[str, Any]) -> None:
        """Update cached configuration for an edge node."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                resolved = config.get('config', config)
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=resolved.get('config_cache_ttl_seconds', 86400)
                )

                query = """
                    INSERT INTO edge_config_cache (edge_node_id, config_json, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (edge_node_id)
                    DO UPDATE SET
                        config_json = EXCLUDED.config_json,
                        cached_at = NOW(),
                        expires_at = EXCLUDED.expires_at,
                        version = edge_config_cache.version + 1
                """
                cur.execute(query, [edge_node_id, json.dumps(config), expires_at])

                conn.commit()
                log.info(f"Edge cache updated: {edge_node_id}")

    def invalidate_edge_cache(self, edge_node_id: Optional[str] = None) -> int:
        """Invalidate cache for specific edge node or all edge nodes."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                if edge_node_id:
                    query = "DELETE FROM edge_config_cache WHERE edge_node_id = %s"
                    cur.execute(query, [edge_node_id])
                else:
                    query = "DELETE FROM edge_config_cache"
                    cur.execute(query)

                affected = cur.rowcount
                conn.commit()
                log.info(f"Edge cache invalidated: {affected} nodes")
                return affected

    # ============================================================================
    # Audit Logging
    # ============================================================================

    def _log_change(
        self,
        cur,
        action: str,
        level: str,
        customer_id: Optional[str],
        site_id: Optional[str],
        camera_id: Optional[str],
        old_values: Optional[Dict],
        new_values: Optional[Dict],
        changed_by: str,
    ) -> None:
        """Log configuration change for audit trail."""
        # Convert Decimals to floats for JSON serialization
        def convert_for_json(obj):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_for_json(item) for item in obj]
            if isinstance(obj, (int, float, str, bool)):
                return float(obj) if isinstance(obj, float) else obj  # Handles Decimal subclass
            from decimal import Decimal
            if isinstance(obj, Decimal):
                return float(obj)
            return str(obj)  # Fallback for other types

        query = """
            INSERT INTO site_look_config_log (
                action, config_level, customer_id, site_id, camera_id,
                old_values, new_values, changed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cur.execute(query, [
            action, level, customer_id, site_id, camera_id,
            json.dumps(convert_for_json(old_values)) if old_values else None,
            json.dumps(convert_for_json(new_values)) if new_values else None,
            changed_by
        ])

    def get_config_log(
        self,
        limit: int = 100,
        customer_id: Optional[str] = None,
        site_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get configuration change log."""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT * FROM site_look_config_log
                    WHERE (%s IS NULL OR customer_id = %s)
                      AND (%s IS NULL OR site_id = %s)
                    ORDER BY changed_at DESC
                    LIMIT %s
                """
                cur.execute(query, [customer_id, customer_id, site_id, site_id, limit])
                return [dict(row) for row in cur.fetchall()]

    # ============================================================================
    # Helpers
    # ============================================================================

    def reset_to_defaults(
        self,
        level: str,
        customer_id: Optional[str] = None,
        site_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        reset_by: str = 'admin',
    ) -> Dict[str, Any]:
        """Reset configuration at a level to defaults (delete level-specific config)."""
        if self.delete_config(level, customer_id, site_id, camera_id, reset_by):
            # Return global defaults
            return self.get_config(customer_id, site_id, camera_id)
        return {}
