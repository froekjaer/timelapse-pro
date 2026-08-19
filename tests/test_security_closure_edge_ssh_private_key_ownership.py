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
        "SSH privkey hentet",
        "har ingen SSH privkey — kald /prepare",
    )
    for needle in forbidden:
        assert needle not in source, needle


def test_generic_key_management_cannot_generate_edge_ssh_private_keys():
    source = _source()
    block = _function_block(
        source,
        '@app.post("/api/admin/key-management/credentials")',
        '@app.post("/api/admin/key-management/credentials/{credential_id}/revoke")',
    )
    assert 'entity_type == "edge" and key_type == "ssh"' in block
    assert "payload.generate_keypair" in block
    assert "Edge-leveret public key" in block


def test_legacy_provision_package_is_retired_instead_of_exporting_private_keys():
    source = _source()
    block = _function_block(
        source,
        '@app.post("/api/admin/provision-package")',
        '# ── Reverse SSH',
    )
    assert "status_code=410" in block
    assert "/api/admin/edge-provisioning/prepare" in block
    for needle in (
        "_generate_ed25519_keypair()",
        "tunnel_priv",
        "sftp_priv",
        'writestr("tunnel_key"',
        'writestr("sftp_key"',
    ):
        assert needle not in block, needle


def test_bt_totp_qr_enforces_tenant_boundary_before_secret_resolution():
    # 2026-08-19: secret resolution moved into _resolve_camera_bt_totp()
    # (shared with the new local-access overview endpoint), so the end
    # marker changed from the old inline "secret = ''" to the call site.
    source = _source()
    block = _function_block(
        source,
        '@app.get("/api/admin/cameras/{camera_id}/bt-totp-qr")',
        'secret, sid, source = _resolve_camera_bt_totp(db, cam)',
    )
    assert "_ensure_site_access(db, current_user, cam.site_id)" in block
    assert "_ensure_customer_access(current_user, cam.customer_id)" in block
    assert "_is_platform_admin(current_user)" in block
