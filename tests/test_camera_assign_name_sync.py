from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _main() -> str:
    # assign_camera_to_device moved to headend/api/cameras_api.py (2026-08-27,
    # Phase 2 of the main.py modularization plan).
    return (ROOT / "headend" / "api" / "cameras_api.py").read_text(encoding="utf-8")


def _route_block(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_camera_assign_syncs_site_and_customer_name_not_just_ids():
    """Regression test: `assign_camera_to_device` synced site_id/customer_id
    onto the device row but left the separate site_name/customer_name text
    columns stale — a device page header (and DevicePage's new
    Enhedsidentitet dropdowns) would keep showing the OLD customer/site
    name after a correct reassignment, since get_device_detail returns the
    stored text columns verbatim rather than a live join. See
    Dokumentation/HANDOVER_LOG.md, 2026-08-16 entry."""
    source = _main()
    block = _route_block(
        source,
        'def assign_camera_to_device(',
        '@router.get("/api/admin/cameras/{camera_id}/history")',
    )
    assert 'device.site_id       = camera.site_id' in block
    assert 'device.customer_id   = camera.customer_id' in block
    assert 'device.site_name' in block
    assert 'device.customer_name' in block
    # The names must be resolved from the Site/Customer rows the camera
    # actually belongs to, not copied verbatim from request payload or left
    # as some other stale source.
    site_lookup_i = block.index('db.query(Site).filter_by(id=camera.site_id)')
    site_name_i = block.index('device.site_name = site.name')
    customer_lookup_i = block.index('db.query(Customer).filter_by(id=camera.customer_id)')
    customer_name_i = block.index('device.customer_name =')
    assert site_lookup_i < site_name_i
    assert customer_lookup_i < customer_name_i
