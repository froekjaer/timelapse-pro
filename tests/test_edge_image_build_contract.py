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


def test_dockerfile_removes_device_credentials_from_build_context() -> None:
    source = (ROOT / "headend" / "tools" / "Dockerfile.edge").read_text()
    for sensitive in ("api_token.txt", "bootstrap.yaml", "config.yaml", "keys"):
        assert sensitive in source


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
    source = (ROOT / "headend" / "main.py").read_text()
    assert "Kilde-artifact {artifact_id} mangler signatur eller manifest" in source
    assert '"schema": "timelapse.flashable_image.reconfiguration.v1"' in source
    assert "signature=signature" in source
    assert "signed_by=signed_by" in source


def test_edge_target_catalog_uses_the_module_imported_by_main() -> None:
    source = (ROOT / "headend" / "main.py").read_text()
    assert "base_pinned = bool(_re.fullmatch" in source
    assert "base_pinned = bool(re.fullmatch" not in source


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
