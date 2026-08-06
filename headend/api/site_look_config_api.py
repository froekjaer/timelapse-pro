"""
Site-Wide Look Matching Configuration API Endpoints (FastAPI)

Provides REST API for hierarchical configuration management.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from services.site_look_config_service import SiteLookConfigService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/site-look", tags=["site-look-config"])


def _actor_username(request: Request, db: Session = Depends(get_db)) -> str:
    """Resolve the actual logged-in username for audit attribution, AND
    re-check the super_admin role directly on the mutating endpoints as
    defense in depth.

    The router is currently mounted with
    `dependencies=[require_role("super_admin")]` (headend/main.py), which
    already enforces the role/MFA check — but that mount-level dependency
    doesn't inject the resolved user into individual endpoints (so every
    mutation here was writing the literal string 'admin' as
    updated_by/deleted_by/reset_by regardless of which admin actually made
    the change — see HANDOVER_LOG 2026-08-05), and it's a single point of
    failure: if this router is ever re-mounted, split into a sub-app, or the
    `dependencies=[...]` line is dropped in a future edit, site-look config
    for every customer/site/camera silently reverts to unauthenticated
    read/write. Re-checking here on the write paths means that mistake can't
    silently reopen this router.
    """
    from main import get_current_user
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Kræver rolle: super_admin")
    return user.username


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
    neutral_kelvin: Optional[int] = Field(None, ge=1000, le=20000)
    warm_lab_threshold: Optional[float] = Field(None, ge=-128, le=127)
    cool_lab_threshold: Optional[float] = Field(None, ge=-128, le=127)
    warm_kelvin_multiplier: Optional[float] = Field(None, ge=0, le=1000)
    cool_kelvin_multiplier: Optional[float] = Field(None, ge=0, le=1000)
    kelvin_min: Optional[int] = Field(None, ge=1000, le=20000)
    kelvin_max: Optional[int] = Field(None, ge=1000, le=20000)


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
    import os
    db_url = os.getenv("SITE_LOOK_DB_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL eller SITE_LOOK_DB_URL mangler")
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
    actor: str = Depends(_actor_username),
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
        neutral_kelvin=data.neutral_kelvin,
        warm_lab_threshold=data.warm_lab_threshold,
        cool_lab_threshold=data.cool_lab_threshold,
        warm_kelvin_multiplier=data.warm_kelvin_multiplier,
        cool_kelvin_multiplier=data.cool_kelvin_multiplier,
        kelvin_min=data.kelvin_min,
        kelvin_max=data.kelvin_max,
        customer_id=data.customer_id,
        site_id=data.site_id,
        camera_id=data.camera_id,
        updated_by=actor,
    )
    return result


@router.delete("/config")
def delete_config(
    level: str = Query(...),
    customer_id: Optional[str] = Query(None),
    site_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    service: SiteLookConfigService = Depends(get_config_service),
    actor: str = Depends(_actor_username),
):
    """Delete configuration at a hierarchy level (fallback to parent)."""
    if level == 'global':
        raise HTTPException(status_code=400, detail="Cannot delete global config")

    success = service.delete_config(
        level=level,
        customer_id=customer_id,
        site_id=site_id,
        camera_id=camera_id,
        deleted_by=actor,
    )

    if success:
        return {'status': 'deleted'}
    else:
        raise HTTPException(status_code=404, detail="Config not found")


@router.post("/config/reset")
def reset_config(
    data: ConfigReset,
    service: SiteLookConfigService = Depends(get_config_service),
    actor: str = Depends(_actor_username),
):
    """Reset configuration at a level to defaults."""
    result = service.reset_to_defaults(
        level=data.level,
        customer_id=data.customer_id,
        site_id=data.site_id,
        camera_id=data.camera_id,
        reset_by=actor,
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
