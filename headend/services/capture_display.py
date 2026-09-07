"""Human-facing capture assignment metadata for list responses."""

from __future__ import annotations

from sqlalchemy.orm import Session

from database import Camera, Capture, Customer, Device, Site


def names(db: Session, captures: list[Capture]) -> dict[int, dict[str, str | None]]:
    """Resolve capture assignment names in one batch for thumbnail grids."""
    device_ids = {c.device_id for c in captures if c.device_id}
    camera_ids = {c.camera_id for c in captures if getattr(c, "camera_id", None)}
    site_ids = {c.site_id for c in captures if getattr(c, "site_id", None)}
    customer_ids = {c.customer_id for c in captures if getattr(c, "customer_id", None)}
    devices = {row.device_id: row for row in db.query(Device).filter(Device.device_id.in_(device_ids)).all()} if device_ids else {}
    cameras = {row.id: row for row in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()} if camera_ids else {}
    site_ids.update(row.site_id for row in cameras.values() if row.site_id)
    customer_ids.update(row.customer_id for row in cameras.values() if row.customer_id)
    sites = {row.id: row for row in db.query(Site).filter(Site.id.in_(site_ids)).all()} if site_ids else {}
    customers = {row.id: row for row in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()} if customer_ids else {}
    result: dict[int, dict[str, str | None]] = {}
    for capture in captures:
        device = devices.get(capture.device_id)
        camera = cameras.get(getattr(capture, "camera_id", None))
        site = sites.get((camera.site_id if camera else None) or getattr(capture, "site_id", None))
        customer = customers.get((camera.customer_id if camera else None) or getattr(capture, "customer_id", None))
        result[capture.id] = {
            "customer_name": (customer.name if customer else None) or (device.customer_name if device else None),
            "site_name": (site.name if site else None) or (device.site_name if device else None),
            "camera_name": (camera.camera_name if camera else None) or (device.camera_name if device else None),
        }
    return result
