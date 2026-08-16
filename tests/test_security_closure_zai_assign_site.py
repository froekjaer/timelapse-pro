from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _main() -> str:
    return (ROOT / "headend" / "main.py").read_text(encoding="utf-8")


def _route_block(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_unassigned_device_inventory_requires_admin_and_is_tenant_scoped():
    source = _main()
    block = _route_block(
        source,
        'def list_unassigned_devices(',
        '@app.put("/api/admin/devices/{device_id}/assign-site")',
    )
    assert '_user=require_role("admin")' in block
    assert 'if not _is_platform_admin(_user):' in block
    assert 'Device.customer_id == _user.customer_id' in block
    assert 'Depends(get_current_user)' not in block


def test_assign_site_requires_admin_and_checks_both_current_device_and_target_site_tenants():
    source = _main()
    block = _route_block(
        source,
        'def assign_device_to_site(',
        '# ── API Token auth',
    )
    assert '_user=require_role("admin")' in block
    assert 'Depends(get_current_user)' not in block
    assert '_ensure_customer_access(_user, device.customer_id)' in block
    assert 'site = _ensure_site_access(db, _user, site_id)' in block

    device_access_i = block.index('_ensure_customer_access(_user, device.customer_id)')
    site_access_i = block.index('site = _ensure_site_access(db, _user, site_id)')
    mutate_site_i = block.index('device.site_id')
    mutate_customer_i = block.index('device.customer_id')
    # The first device.customer_id occurrence is the access check itself; the
    # assignment must occur after both tenant boundaries have succeeded.
    assignment_customer_i = block.index('device.customer_id      =', device_access_i)
    assert device_access_i < mutate_site_i
    assert site_access_i < mutate_site_i
    assert device_access_i < assignment_customer_i
    assert site_access_i < assignment_customer_i


def test_assign_site_no_longer_performs_unscoped_site_query():
    source = _main()
    block = _route_block(
        source,
        'def assign_device_to_site(',
        '# ── API Token auth',
    )
    assert 'db.query(Site).filter_by(id=site_id).first()' not in block
