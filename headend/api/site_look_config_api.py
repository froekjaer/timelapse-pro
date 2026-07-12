"""
Site-Wide Look Matching Configuration API Endpoints (FastAPI)

Provides REST API for hierarchical configuration management.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from services.site_look_config_service import SiteLookConfigService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/site-look", tags=["site-look-config"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class ConfigUpsert(BaseModel):
    """Request model for upserting configuration."""
    level: str  # 'global' | 'customer' | 'site' | 'camera'
    customer_id: Optional[str] = None
    site_id: Optional[str] = None
    camera_id: Optional[str] = None
    enabled: Optional[bool] = None
    storage_path: Optional[str] = None
    reference_quality_threshold: Optional[float] = None
    auto_create_reference: Optional[bool] = None
    auto_update_reference: Optional[bool] = None
    lut_auto_generate: Optional[bool] = None
    lut_regeneration_interval_hours: Optional[int] = None
    config_poll_interval_seconds: Optional[int] = None
    config_cache_ttl_seconds: Optional[int] = None


class ConfigReset(BaseModel):
    """Request model for resetting configuration."""
    level: str  # 'customer' | 'site' | 'camera'
    customer_id: Optional[str] = None
    site_id: Optional[str] = None
    camera_id: Optional[str] = None


class ConfigDelete(BaseModel):
    """Request model for deleting configuration."""
    level: str  # 'customer' | 'site' | 'camera'
    customer_id: Optional[str] = None
    site_id: Optional[str] = None
    camera_id: Optional[str] = None


# ============================================================================
# Dependencies
# ============================================================================

def get_config_service() -> SiteLookConfigService:
    """Get config service instance."""
    # In production, this would come from app config
    # For now, use environment variable or default
    import os
    db_url = os.getenv("SITE_LOOK_DB_URL", "postgresql://timelapse@localhost/timelapse_db")
    return SiteLookConfigService(db_url)


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("/config")
def get_config(
    customer_id: Optional[str] = Query(None),
    site_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Get resolved configuration for a hierarchy level."""
    config = service.get_config(customer_id, site_id, camera_id)
    return config


@router.put("/config")
def upsert_config(
    data: ConfigUpsert,
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Create or update configuration at a hierarchy level."""
    if data.level not in ['global', 'customer', 'site', 'camera']:
        raise HTTPException(status_code=400, detail=f"Invalid level: {data.level}")

    # Validate required IDs based on level
    if data.level in ['customer', 'site', 'camera'] and not data.customer_id:
        raise HTTPException(status_code=400, detail="customer_id required for this level")
    if data.level in ['site', 'camera'] and not data.site_id:
        raise HTTPException(status_code=400, detail="site_id required for this level")
    if data.level == 'camera' and not data.camera_id:
        raise HTTPException(status_code=400, detail="camera_id required for camera level")

    result = service.upsert_config(
        level=data.level,
        enabled=data.enabled,
        storage_path=data.storage_path,
        reference_quality_threshold=data.reference_quality_threshold,
        auto_create_reference=data.auto_create_reference,
        auto_update_reference=data.auto_update_reference,
        lut_auto_generate=data.lut_auto_generate,
        lut_regeneration_interval_hours=data.lut_regeneration_interval_hours,
        config_poll_interval_seconds=data.config_poll_interval_seconds,
        config_cache_ttl_seconds=data.config_cache_ttl_seconds,
        customer_id=data.customer_id,
        site_id=data.site_id,
        camera_id=data.camera_id,
        updated_by='admin',  # TODO: get from auth context
    )
    return result


@router.delete("/config")
def delete_config(
    level: str = Query(...),
    customer_id: Optional[str] = Query(None),
    site_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Delete configuration at a hierarchy level (fallback to parent)."""
    if level == 'global':
        raise HTTPException(status_code=400, detail="Cannot delete global config")

    success = service.delete_config(
        level=level,
        customer_id=customer_id,
        site_id=site_id,
        camera_id=camera_id,
        deleted_by='admin',  # TODO: get from auth context
    )

    if success:
        return {'status': 'deleted'}
    else:
        raise HTTPException(status_code=404, detail="Config not found")


@router.post("/config/reset")
def reset_config(
    data: ConfigReset,
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Reset configuration at a level to defaults."""
    result = service.reset_to_defaults(
        level=data.level,
        customer_id=data.customer_id,
        site_id=data.site_id,
        camera_id=data.camera_id,
        reset_by='admin',  # TODO: get from auth context
    )
    return result


@router.get("/configs")
def list_configs(
    level: Optional[str] = Query(None),
    service: SiteLookConfigService = Depends(get_config_service),
):
    """List all configurations, optionally filtered by level."""
    configs = service.get_all_configs(level=level)
    return configs


# ============================================================================
# Edge Node Endpoints
# ============================================================================

@router.get("/edge/{edge_node_id}/config")
def get_edge_config(
    edge_node_id: str,
    service: SiteLookConfigService = Depends(get_config_service),
):
    """
    Get configuration for an edge node.

    Returns cached config if available and valid, otherwise generates new cache.
    Edge nodes call this periodically based on their poll interval.
    """
    # Try cache first
    cached = service.get_edge_cache(edge_node_id)
    if cached:
        log.debug(f"Cache hit for edge node: {edge_node_id}")
        return cached

    # Cache miss or expired - generate new config
    config = service.get_config(for_edge_node=edge_node_id)

    # Update cache
    service.update_edge_cache(edge_node_id, config)

    return config


@router.delete("/edge/{edge_node_id}/cache")
def invalidate_edge_cache(
    edge_node_id: str,
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Invalidate cache for a specific edge node."""
    service.invalidate_edge_cache(edge_node_id)
    return {'status': 'cache invalidated'}


@router.post("/edge/cache/invalidate")
def invalidate_all_edge_cache(
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Invalidate cache for all edge nodes."""
    count = service.invalidate_edge_cache()
    return {'status': 'cache invalidated', 'nodes_affected': count}


# ============================================================================
# Audit Log Endpoints
# ============================================================================

@router.get("/audit/log")
def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    customer_id: Optional[str] = Query(None),
    site_id: Optional[str] = Query(None),
    service: SiteLookConfigService = Depends(get_config_service),
):
    """Get configuration change log."""
    log_entries = service.get_config_log(limit, customer_id, site_id)
    return log_entries


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
def health_check(service: SiteLookConfigService = Depends(get_config_service)):
    """Health check endpoint."""
    try:
        config = service.get_config()
        return {
            'status': 'healthy',
            'global_config_enabled': config.get('enabled'),
        }
    except Exception as e:
        log.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
        }, 503
