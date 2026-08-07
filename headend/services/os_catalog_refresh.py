"""Nightly Headend-side OS catalogue discovery for offline Edge updates."""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import timedelta


log = logging.getLogger("headend.os_catalog_refresh")


def start_os_catalog_refresh() -> None:
    """Start the scheduled catalog refresh after the Headend is ready."""
    interval_hours = float(os.getenv("TIMELAPSE_OS_CATALOG_REFRESH_INTERVAL_HOURS", "24"))
    threading.Thread(
        target=os_catalog_refresh_loop,
        args=(interval_hours,),
        name="os-catalog-refresh",
        daemon=True,
    ).start()
    log.info("OS-katalogopdagelse startet (interval=%.1fh)", interval_hours)


def refresh_os_catalogs_from_cmdb() -> None:
    """Create or refresh current OS candidates from CMDB inventories.

    Imports from ``main`` are intentionally delayed: this service is started
    after FastAPI has completed module initialization, avoiding a circular
    import while keeping domain orchestration out of the application module.
    """
    from main import (
        DeviceInventory,
        OsCatalogBuilderPayload,
        SessionLocal,
        User,
        now_utc,
        refresh_os_catalog_from_mac_builder,
    )

    db = SessionLocal()
    try:
        system_user = (
            db.query(User).filter(User.role == "super_admin").order_by(User.id).first()
        )
        if not system_user:
            log.warning("OS-katalogopdagelse: ingen super_admin fundet — springer over")
            return
        max_age_hours = float(os.getenv("TIMELAPSE_OS_CATALOG_MAX_INVENTORY_AGE_HOURS", "72"))
        freshness_cutoff = now_utc() - timedelta(hours=max(1, max_age_hours))
        inventories = (
            db.query(DeviceInventory)
            .filter(DeviceInventory.package_manager.ilike("%apt%"))
            .order_by(DeviceInventory.device_id)
            .all()
        )
        for inventory in inventories:
            if not inventory.os_packages:
                continue
            if not inventory.inventory_reported_at or inventory.inventory_reported_at < freshness_cutoff:
                log.info(
                    "OS-katalogopdagelse: springer stale inventory over for %s (%s)",
                    inventory.device_id,
                    inventory.inventory_reported_at,
                )
                continue
            try:
                # 2026-08-07 (Claude, Peter — TL-043EB9E72EFD OS-update-incident):
                # was hardcoded image="ubuntu:24.04" here, applied to EVERY
                # device's nightly refresh regardless of its actual OS release —
                # the unattended, no-human-in-the-loop entry point that produced
                # a 503-package cross-release catalog for a Jammy device. Leave
                # image unset so refresh_os_catalog_from_mac_builder derives it
                # from this device's own CMDB inventory (see
                # _resolve_os_catalog_image's docstring for the full incident).
                refresh_os_catalog_from_mac_builder(
                    OsCatalogBuilderPayload(
                        device_id=inventory.device_id,
                        environment=inventory.environment or "lab",
                        architecture="arm64",
                        source=f"headend-scheduled-cmdb-refresh:{now_utc():%Y-%m-%d}",
                        create_updates=True,
                    ),
                    system_user,
                    db,
                )
                log.info("OS-katalogopdagelse: opdateret for %s", inventory.device_id)
            except Exception as exc:
                db.rollback()
                log.warning("OS-katalogopdagelse: %s fejlede: %s", inventory.device_id, exc)
    finally:
        db.close()


def os_catalog_refresh_loop(interval_hours: float = 24.0) -> None:
    """Run after startup and then at the configured Headend interval."""
    interval_seconds = max(3600, interval_hours * 3600)
    time.sleep(60)
    while True:
        try:
            refresh_os_catalogs_from_cmdb()
        except Exception as exc:
            log.warning("OS-katalogopdagelse fejlede: %s", exc)
        time.sleep(interval_seconds)
