"""
TimeLapse Pro — Camera Driver Registry
========================================
Auto-selects and instantiates the correct camera driver
based on configuration or USB auto-detection.

To add a new driver:
  1. Create camera/drivers/my_driver.py implementing CameraBase
  2. Import it here and add to DRIVERS list
  3. Populate its supported_models property
"""

from __future__ import annotations

import logging
from typing import Type

from camera.base import CameraBase, CameraNotFoundError
from camera.drivers.gphoto2_driver import GPhoto2Driver

log = logging.getLogger(__name__)

# Ordered list — first matching driver wins
DRIVERS: list[Type[CameraBase]] = [
    GPhoto2Driver,
    # Future: CanonSDKDriver, SonyDriver, NikonDriver, ...
]


def get_driver(config: dict) -> CameraBase:
    """
    Return an instantiated (but not yet connected) camera driver.

    Selection order:
      1. If config['camera']['driver'] is set explicitly, use that.
      2. Otherwise try each driver's supported_models list against
         config['camera']['model'] (if set).
      3. Otherwise return GPhoto2Driver as the universal fallback
         (it does its own detection at connect() time).

    Args:
        config: the full config dict (camera section read via
                config['camera'])

    Returns:
        An instantiated CameraBase subclass, not yet connected.

    Raises:
        CameraNotFoundError: if an explicitly named driver is unknown.
    """
    cam_cfg = dict(config.get("camera", {}))
    # Inject device identity for structured filenames
    device_cfg = config.get("device", {})
    cam_cfg.setdefault("device_id",     device_cfg.get("device_id", "unknown"))
    cam_cfg.setdefault("customer_name", device_cfg.get("customer_name", ""))
    cam_cfg.setdefault("site_name",     device_cfg.get("site_name", ""))
    cam_cfg.setdefault("camera_name",   device_cfg.get("camera_name", ""))
    # Inject schedule and location so driver can use timezone etc.
    cam_cfg["schedule"] = config.get("schedule", {})
    cam_cfg["location"] = config.get("location", {})

    explicit_driver = cam_cfg.get("driver", "").lower()
    if explicit_driver:
        for cls in DRIVERS:
            if cls(cam_cfg).driver_name == explicit_driver:
                log.info("Using explicitly configured driver: %s", explicit_driver)
                return cls(cam_cfg)
        raise CameraNotFoundError(
            f"Driver '{explicit_driver}' not found. "
            f"Available: {[cls(cam_cfg).driver_name for cls in DRIVERS]}"
        )

    model = cam_cfg.get("model", "").strip()
    if model:
        for cls in DRIVERS:
            instance = cls(cam_cfg)
            if any(model.lower() in m.lower() or m.lower() in model.lower()
                   for m in instance.supported_models):
                log.info(
                    "Auto-selected driver '%s' for model '%s'",
                    instance.driver_name, model
                )
                return instance

    log.info("No specific driver matched — using gPhoto2 (universal fallback)")
    return GPhoto2Driver(cam_cfg)


def list_drivers() -> list[str]:
    """Return names of all registered drivers."""
    return [cls({}).driver_name for cls in DRIVERS]
