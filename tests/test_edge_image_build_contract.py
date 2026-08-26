from pathlib import Path
import importlib.util

import pytest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "edge_image_builder", ROOT / "headend" / "tools" / "build_edge_disk_image.py"
)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(builder)

INJECT_SPEC = importlib.util.spec_from_file_location(
    "edge_image_injector", ROOT / "headend" / "tools" / "inject_edge_image.py"
)
injector = importlib.util.module_from_spec(INJECT_SPEC)
assert INJECT_SPEC.loader
INJECT_SPEC.loader.exec_module(injector)


def test_image_manifest_cannot_fall_back_to_hash_only_trust() -> None:
    with pytest.raises(RuntimeError, match="GPG release-nøgle mangler"):
        builder._sign_manifest("{}", None, lambda _message: None)


def test_flashable_image_manifest_cannot_fall_back_to_hash_only_trust() -> None:
    with pytest.raises(RuntimeError, match="GPG release-nøgle mangler"):
        injector._sign_manifest("{}", None, lambda _message: None)


def test_base_image_requires_pinned_checksum() -> None:
    with pytest.raises(RuntimeError, match="mangler en valideret SHA-256"):
        injector._require_pinned_base_image(
            {"id": "unsafe", "base_image": {"url": "https://vendor.invalid/latest.img.xz"}}
        )


def test_reverse_tunnel_rejects_reserved_headend_port() -> None:
    with pytest.raises(ValueError, match="reserverede porte"):
        injector._validate_tunnel_settings(
            device_private_key="private",
            remote_port=2201,
            headend_host="backend.timelapse-pro.dk",
            headend_port=22,
            headend_user="tunnel",
        )


def test_dockerfile_contains_edge_qa_and_management_runtime() -> None:
    source = (ROOT / "headend" / "tools" / "Dockerfile.edge").read_text()
    assert "edge/requirements.txt" in source
    assert "gphoto2" in source
    for unit in ("timelapse-edge", "timelapse-bt-pan", "timelapse-bt-agent", "timelapse-captive", "timelapse-totp"):
        assert f"{unit}.service" in source
    assert "avahi-daemon" in source
    assert "libnss-mdns" in source


def test_flashable_injection_copies_and_enables_all_local_management_units() -> None:
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    for unit in (
        "timelapse-bt-pan.service",
        "timelapse-bt-agent.service",
        "timelapse-captive.service",
        "timelapse-totp.service",
    ):
        assert f'"etc/systemd/system/{unit}"' in source
        assert unit in source
    assert "INTERACTIVE_SHELL_ENABLED" in source
    assert "/etc/timelapse/bt-config.yaml" in source
    assert "BT_TOTP_SECRET" in source
    assert "BT_TOTP_SID" in source
    assert "LOCAL_MGMT_HOSTNAME" in source
    assert "local-mgmt.key" in source
    assert "centralt CA-udstedt lokalt TLS-certifikat" in source
    assert "forventet fysisk Edge-ID til MAC-binding" in source
    assert "expected_device_id" in source


def test_flashable_image_refuses_shared_or_unprovisioned_local_access() -> None:
    injector_source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    portal_source = (ROOT / "edge" / "scripts" / "totp-service.py").read_text()

    assert "Flashable image kræver en unik, provisioneret BT TOTP-secret" in injector_source
    assert '"secret": "JBSWY3DPEHPK3PXP"' not in portal_source
    assert '"sid": "unprovisioned"' in portal_source


def test_flashable_image_binds_the_public_build_api_to_the_expected_edge_identity() -> None:
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    public_api = source.split("def inject_edge_image(", 1)[1].split("    \"\"\"", 1)[0]
    assert "expected_device_id: str" in public_api
    assert '"expected_device_id": expected_device_id.strip()' in source
    assert "expected_device_id   = expected_device_id" in source


def test_dockerfile_removes_device_credentials_from_build_context() -> None:
    source = (ROOT / "headend" / "tools" / "Dockerfile.edge").read_text()
    for sensitive in ("api_token.txt", "bootstrap.yaml", "config.yaml", "keys"):
        assert sensitive in source


def test_dockerfile_excludes_training_and_development_only_edge_content() -> None:
    source = (ROOT / "headend" / "tools" / "Dockerfile.edge").read_text()
    for excluded in ("/ai/tests", "/training", "/npu_viplite", "technician_ui.py"):
        assert excluded in source
    assert "! -name bootstrap_cli.py -delete" in source


def test_edge_injection_has_no_default_debug_credential_or_online_install() -> None:
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    for forbidden in (
        "TLdebug2026",
        "Match User tl-debug",
        "apt-get update -qq",
        "pip\", \"install",
        'TUNNEL_HEADEND_USER:-peter',
        'TUNNEL_HEADEND_PORT:-22',
    ):
        assert forbidden not in source
    assert "PermitRootLogin no" in source
    assert "ExecStartPre=/usr/bin/test -x /usr/bin/autossh" in source


def test_wifi_reconfiguration_requires_signed_artifact() -> None:
    source = (ROOT / "headend" / "edge_provisioning_security.py").read_text()
    assert "Kilde-artifact {artifact_id} mangler signatur eller manifest" in source
    assert '"schema": "timelapse.flashable_image.reconfiguration.v1"' in source
    assert '"signature": signature' in source
    assert '"signed_by": signed_by' in source


def test_edge_target_catalog_uses_the_module_imported_by_main() -> None:
    source = (ROOT / "headend" / "edge_provisioning_security.py").read_text()
    assert "base_pinned = bool(re.fullmatch" in source
    # Moved to api/edge_disk_image_api.py (2026-08-26, Phase 1 of the main.py
    # modularization plan) along with the rest of the disk-image/wifi-inject
    # domain — no longer inline in main.py.
    assert "_edge_provisioning.load_hardware_targets(hw_dir, log)" in (
        ROOT / "headend" / "api" / "edge_disk_image_api.py"
    ).read_text()


def test_edge_target_ui_has_no_unauthoritative_static_fallback() -> None:
    source = (ROOT / "timelapse-ui" / "src" / "pages" / "BackupPage.tsx").read_text()
    assert "STATIC_TARGETS" not in source
    assert "Build er deaktiveret, så en lokal fallback ikke kan omgå trust-kontrollen" in source


def test_wifi_injection_has_no_root_key_or_online_autossh_install() -> None:
    source = (ROOT / "headend" / "tools" / "inject_wifi_image.py").read_text()
    assert "/mnt/root/root" not in source
    assert "apt-get install" not in source
    assert "StrictHostKeyChecking=no" not in source
    assert "ExecStartPre=/usr/bin/test -x /usr/bin/autossh" in source


def test_jetson_installer_is_offline_and_release_verified() -> None:
    source = (
        ROOT
        / "headend"
        / "tools"
        / "hardware"
        / "jetson-orin-nano"
        / "install_timelapse_edge.sh"
    ).read_text()
    assert "git -C \"$RELEASE_DIR\" verify-tag" in source
    assert "--bootstrap-token-file" in source
    assert "--no-index" in source
    assert "apt-get" not in source
    assert "pip\" install --quiet --upgrade pip" not in source


@pytest.mark.parametrize("target", ["orangepi4pro", "orangepi-pc-plus", "rpi4"])
def test_supported_base_images_are_checksum_pinned(target: str) -> None:
    import yaml

    config = yaml.safe_load(
        (ROOT / "headend" / "tools" / "hardware" / target / "target.yaml").read_text()
    )
    checksum = config["base_image"]["sha256"]
    assert isinstance(checksum, str)
    assert len(checksum) == 64


def test_flashable_injection_provisions_servicetekniker_account() -> None:
    """RBAC technician SSH access (PR #79) needs a real, scoped account on
    the device for sshd's AuthorizedKeysCommand to serve keys for — this is
    the device-side half. Must be pubkey-only (locked shadow entry) and
    scoped sudo (never the blanket sudo group orangepi has)."""
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    assert 'echo "servicetekniker:x:${SVCTECH_UID}:${SVCTECH_UID}' in source
    assert "servicetekniker:!:${SVCTECH_UID}:" in source
    assert 'servicetekniker:!:19000' in source  # locked shadow entry
    assert "/etc/sudoers.d/servicetekniker" in source
    assert "chmod 440 /mnt/root/etc/sudoers.d/servicetekniker" in source
    # Scoped to bootstrap_cli.py only — never blanket sudo like orangepi.
    assert "servicetekniker ALL=(root) NOPASSWD: /opt/timelapse/venv/bin/python3 /opt/timelapse/edge/tools/bootstrap_cli.py*" in source


def test_flashable_injection_does_not_hardcode_servicetekniker_uid() -> None:
    """Regression: UID 1002 collided with the pre-existing "emergency"
    break-glass account on a live device (manually provisioned, no code
    creates it yet — see BreakGlassAccount's own TODO), so useradd/the
    raw passwd append must never assume a fixed UID is free."""
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    assert "SVCTECH_UID=1003" in source
    assert '"servicetekniker:x:1002:1002' not in source


def test_flashable_injection_wires_sshd_match_block_for_servicetekniker() -> None:
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    assert "Match User servicetekniker" in source
    assert "AuthorizedKeysCommand /usr/bin/python3 /opt/timelapse/edge/scripts/technician_authorized_keys.py" in source
    assert "AuthorizedKeysCommandUser nobody" in source
    # The Match block is appended via >>, after global PasswordAuthentication
    # no is already set — must never appear before the global hardening sed.
    match_idx = source.index("Match User servicetekniker")
    global_hardening_idx = source.index("PasswordAuthentication.*/PasswordAuthentication no/")
    assert global_hardening_idx < match_idx
