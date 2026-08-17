from pathlib import Path


MAIN = Path(__file__).resolve().parents[1] / "headend" / "main.py"


def _source() -> str:
    return MAIN.read_text(encoding="utf-8")


def _function_block(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_legacy_camera_private_key_download_is_retired_fail_closed():
    source = _source()
    block = _function_block(
        source,
        '@app.get("/api/admin/cameras/{camera_id}/ssh-key")',
        '@app.get("/api/admin/headend/ssh-public-key")',
    )
    assert "status_code=410" in block
    assert "_ensure_site_access" in block
    assert "_ensure_customer_access" in block
    assert "ssh_private_key" not in block
    assert "PlainTextResponse" not in block


def test_headend_no_longer_creates_or_reads_edge_ssh_private_keys_for_provisioning():
    source = _source()
    forbidden = (
        'cam_rec.ssh_private_key =',
        'getattr(_cam, "ssh_private_key"',
        'getattr(cam_ssh, "ssh_private_key"',
        'device_ssh_privkey=_device_ssh_privkey',
        'ssh_private_key=ssh_private_key',
    )
    for needle in forbidden:
        assert needle not in source, needle


def test_bt_totp_qr_enforces_tenant_boundary_before_secret_resolution():
    source = _source()
    block = _function_block(
        source,
        '@app.get("/api/admin/cameras/{camera_id}/bt-totp-qr")',
        '    secret = ""',
    )
    assert "_ensure_site_access(db, current_user, cam.site_id)" in block
    assert "_ensure_customer_access(current_user, cam.customer_id)" in block
    assert "_is_platform_admin(current_user)" in block
