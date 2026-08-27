from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "headend" / "main.py"
# download_camera_ssh_key/get_camera_bt_totp_qr moved to
# api/cameras_api.py (2026-08-27, Phase 2 of the main.py modularization plan).
CAMERAS_API = ROOT / "headend" / "api" / "cameras_api.py"


def _source() -> str:
    return MAIN.read_text(encoding="utf-8")


def _cameras_api_source() -> str:
    return CAMERAS_API.read_text(encoding="utf-8")


def _function_block(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_legacy_camera_private_key_download_is_retired_fail_closed():
    source = _cameras_api_source()
    block = _function_block(
        source,
        '@router.get("/api/admin/cameras/{camera_id}/ssh-key")',
        '@router.post("/api/admin/cameras")',
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
    assert 'entity_type == "edge" and key_type in {"ssh", "signing"}' in block
    assert "payload.generate_keypair" in block
    assert "Edge-leveret public key" in block


def test_key_management_rejects_edge_signing_keypair_generation():
    """C-09 regression: this guard used to only cover key_type=="ssh" — a
    request with key_type=="signing" fell through to _generate_ed25519_keypair()
    and Headend generated + returned an Edge private key, violating the WP-4
    Edge-owns-its-private-keys principle. Behavioral test, not just a source
    string check, so a future refactor that keeps the SAME bug under different
    wording still gets caught."""
    import sys
    from pathlib import Path
    from unittest.mock import MagicMock

    import pytest
    from fastapi import HTTPException

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "headend"))
    import main

    payload = main.KeyCredentialPayload(
        entity_type="edge",
        entity_id="TL-TESTDEVICE-C09",
        key_type="signing",
        generate_keypair=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        main.create_key_credential(payload, current_user=MagicMock(username="admin"), db=MagicMock())
    assert exc_info.value.status_code == 409


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
    source = _cameras_api_source()
    block = _function_block(
        source,
        '@router.get("/api/admin/cameras/{camera_id}/bt-totp-qr")',
        'secret, sid, source = _resolve_camera_bt_totp(db, cam)',
    )
    assert "_ensure_site_access(db, current_user, cam.site_id)" in block
    assert "_ensure_customer_access(current_user, cam.customer_id)" in block
    assert "_is_platform_admin(current_user)" in block
