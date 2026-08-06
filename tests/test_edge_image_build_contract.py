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


def test_flashable_injection_enables_the_core_capture_agent_and_watchdog() -> None:
    """Regression test (2026-08-06): timelapse-edge.service — the actual capture
    agent — was extracted from the rootfs tar but never symlinked into
    multi-user.target.wants, so a freshly-flashed device would never start
    capturing and could never reach its first artifact-based update (the
    normal channel watchdog/timesync would otherwise arrive through).
    timelapse-watchdog.service and timelapse-timesync.timer had the same
    gap — present only on TL-C87FF9587CA0 because that device was set up
    manually, outside this pipeline."""
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()

    # Extracted from the rootfs tar.
    for path in (
        "etc/systemd/system/timelapse-edge.service",
        "etc/systemd/system/timelapse-watchdog.service",
        "etc/systemd/system/timelapse-timesync.service",
        "etc/systemd/system/timelapse-timesync.timer",
    ):
        assert f'"{path}"' in source

    # Enabled — services into multi-user.target.wants, the timer into
    # timers.target.wants (matches each unit's own [Install] WantedBy=).
    enable_loop = source.split("for UNIT in ", 1)[1].split("done\n", 1)[0]
    assert "timelapse-edge.service" in enable_loop
    assert "timelapse-watchdog.service" in enable_loop
    assert "timers.target.wants" in source
    assert 'TIMERS_WANTS_DIR/timelapse-timesync.timer"' in source

    # The unit file itself must exist in the repo (it didn't, previously —
    # only watchdog.sh and the timesync units were tracked).
    assert (ROOT / "edge" / "scripts" / "timelapse-watchdog.service").is_file()


def test_dockerfile_pins_gphoto2_to_a_specific_version() -> None:
    """Regression test (2026-08-06): gphoto2/libgphoto2 were installed
    unpinned (repo-default), risking a silent camera-compatibility drift
    between images built at different times.

    NOT pinned to 2.5.28 (the version field-proven on TL-C87FF9587CA0) —
    that version doesn't exist in this Dockerfile's Ubuntu 22.04 (jammy)
    repos at all (confirmed via `apt-cache policy` against a clean jammy
    image: candidate is 2.5.27-1). Pinned to jammy's actual available
    version instead — see the Dockerfile comment for the deeper jammy vs.
    noble base-image mismatch this surfaces."""
    dockerfile = (ROOT / "headend" / "tools" / "Dockerfile.edge").read_text()
    assert "gphoto2=2.5.27-1 " in dockerfile
    assert "libgphoto2-6=2.5.27-1ubuntu0.1" in dockerfile
    assert "libgphoto2-port12=2.5.27-1ubuntu0.1" in dockerfile


def test_inject_edge_image_extracts_gphoto2s_cli_dependencies() -> None:
    """Regression test (2026-08-06): first real boot test of LAB mode on
    physical hardware (TL-043EB9E72EFD) showed gphoto2 could not even start —
    "error while loading shared libraries: libcdk.so.5" — because the
    hand-picked file list injecting gphoto2 into the flashed image (see
    inject_edge_image.py, right after the timelapse-specific TAR_PATH loop)
    copied libgphoto2's own libraries but missed libcdk.so.5, a transitive
    dependency of the gphoto2 CLI binary itself (distinct from the
    libgphoto2 library) — already apt-installed inside the Docker rootfs as
    a declared dependency of the gphoto2 package, just never selected for
    extraction into the final image. Same failure class Dockerfile.edge's
    own comment predicted ("Treat any noble-target boot failure around
    camera detection as the first place to look"). Fixing libcdk alone only
    revealed the next missing library (libaa.so.1), so `ldd
    /usr/bin/gphoto2` was run inside the cached Docker image to get gphoto2's
    complete non-glibc dependency closure — all 15 must be present, or the
    same whack-a-mole recurs on the next device/re-flash."""
    source = (ROOT / "headend" / "tools" / "inject_edge_image.py").read_text()
    assert "--wildcards" in source
    for lib in [
        "libcdk.so.5",
        "libaa.so.1",
        "libjpeg.so.8",
        "libexif.so.12",
        "libreadline.so.8",
        "libpopt.so.0",
        "libltdl.so.7",
        "libslang.so.2",
        "libX11.so.6",
        "libgpm.so.2",
        "libxcb.so.1",
        "libXau.so.6",
        "libXdmcp.so.6",
        "libbsd.so.0",
        "libmd.so.0",
        "libncurses.so.6",
    ]:
        assert lib in source, f"{lib} missing from gphoto2 CLI dependency extraction list"


def test_dockerfile_copies_watchdog_and_timesync_units() -> None:
    dockerfile = (ROOT / "headend" / "tools" / "Dockerfile.edge").read_text()
    for unit in (
        "timelapse-watchdog.service",
        "timelapse-timesync.service",
        "timelapse-timesync.timer",
    ):
        assert f"edge/scripts/{unit} /etc/systemd/system/{unit}" in dockerfile


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


def test_flashable_injection_passes_the_expected_edge_identity_to_docker() -> None:
    source = Path("headend/tools/inject_edge_image.py").read_text(encoding="utf-8")
    helper = source.split("def _inject_via_docker(", 1)[1].split("def inject_edge_image(", 1)[0]

    assert 'expected_device_id: str = ""' in helper
    assert 'f"EXPECTED_DEVICE_ID={expected_device_id}"' in helper
    assert 'bootstrap.yaml matcher ikke forventet fysisk Edge-ID' in source


def test_flashable_image_credentials_are_owned_by_the_physical_edge() -> None:
    source = (ROOT / "headend" / "main.py").read_text()
    request = source.split("class DiskImageBuildRequest", 1)[1].split("def _edge_image_storage_dir", 1)[0]
    build = source.split("def _run_edge_disk_image_build", 1)[1].split("@app.post(\"/api/admin/edge-provisioning/build-disk-image\")", 1)[0]
    endpoint = source.split("def trigger_edge_disk_image_build", 1)[1].split("@app.get(\"/api/admin/edge-provisioning/disk-image-status\")", 1)[0]

    assert "camera_id" not in request
    assert "_ensure_device_provisioning_credentials" in build
    assert "_db_ssh.query(Device).filter_by(device_id=_resolved_device_id)" in build
    assert "body.mode == \"flashable\" and not body.camera_id" not in endpoint


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
    assert '"expected_device_id": expected_device_id' in source


def test_wifi_reconfiguration_keeps_the_original_physical_edge_binding() -> None:
    source = (ROOT / "headend" / "main.py").read_text()
    wifi = source.split("def _run_wifi_inject", 1)[1].split("@app.post(\"/api/admin/edge-provisioning/inject-wifi\")", 1)[0]
    assert "source_manifest.get(\"local_management\", {}).get(\"expected_device_id\", \"\")" in wifi
    assert "matcher ikke kilde-imagets signerede device-binding" in wifi


def test_edge_target_catalog_uses_the_module_imported_by_main() -> None:
    source = (ROOT / "headend" / "edge_provisioning_security.py").read_text()
    assert "base_pinned = bool(re.fullmatch" in source
    assert "_edge_provisioning.load_hardware_targets(hw_dir, log)" in (
        ROOT / "headend" / "main.py"
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
