"""Contracts for starting the macOS Headend without an interactive login."""

from pathlib import Path
import plistlib


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "deploy/macos/timelapse-headend-start.sh"
MOUNT_SCRIPT = ROOT / "deploy/macos/timelapse-mount-data"
PLISTS = (
    ROOT / "deploy/launchd/macos/dk.froekjaer.timelapse-headend.plist",
    ROOT / "deploy/launchd/dk.froekjaer.timelapse-headend.plist",
)
MOUNT_PLIST = ROOT / "deploy/launchd/macos/dk.froekjaer.timelapse-mount.plist"
CA_HELPER_SOURCE = ROOT / "deploy/macos/timelapse-ca-keychain.c"
CA_HELPER_INSTALLER = ROOT / "deploy/macos/install_timelapse_ca_keychain_helper.sh"


def test_headend_waits_for_real_writable_volume():
    source = START_SCRIPT.read_text()
    assert "wait_for_data_volume" in source
    assert "/sbin/mount" in source
    assert "-w \"$WORKDIR\"" in source
    assert 'wait_for_path "/Volumes/data-fast"' not in source


def test_headend_retries_after_transient_boot_dependency_failure():
    for path in PLISTS:
        plist = plistlib.loads(path.read_bytes())
        assert plist["RunAtLoad"] is True
        assert plist["KeepAlive"] is True
        assert plist["ThrottleInterval"] >= 10


def test_external_volume_mount_retries_after_late_boot_visibility():
    plist = plistlib.loads(MOUNT_PLIST.read_bytes())
    assert plist["RunAtLoad"] is True
    assert "KeepAlive" not in plist
    assert plist["StartInterval"] <= 60


def test_mount_script_rejects_apfs_physical_store_as_volume():
    source = MOUNT_SCRIPT.read_text()
    assert "diskutil info" in source
    assert "Volume Name" in source
    assert "expected_volume_device" in source


def test_mtls_ca_keychain_helper_is_narrow_and_noninteractive():
    source = CA_HELPER_SOURCE.read_text(encoding="utf-8")
    installer = CA_HELPER_INSTALLER.read_text(encoding="utf-8")

    assert '"/Library/Keychains/System.keychain"' in source
    assert '"dk.froekjaer.timelapse.headend-api-mtls-ca"' in source
    assert '"timelapse-headend"' in source
    assert 'HEADEND_RUNTIME_USER "peter"' in source
    assert "SecKeychainSetUserInteractionAllowed(false)" in source
    assert '"--read"' in source
    assert '"--probe"' in source
    assert "/usr/bin/security" not in source

    assert "-framework Security" in installer
    assert "/usr/local/libexec/timelapse-ca-keychain" in installer
    assert "/Library/Application Support/TimeLapse Pro/pki/headend-api-mtls-ca" in installer
    assert 'install -d -o root -g wheel -m 0755 "$APP_DIR"' in installer
    assert 'install -d -o root -g wheel -m 0755 "$PKI_DIR"' in installer
    assert '/usr/bin/tmutil addexclusion -p "$CA_DIR"' in installer
    assert "Keychain item was NOT created or modified" in installer


def test_headend_launchd_declares_non_secret_mtls_ca_paths():
    plist = plistlib.loads(PLISTS[0].read_bytes())
    env = plist["EnvironmentVariables"]

    assert env["TIMELAPSE_HEADEND_API_MTLS_CA_DIR"] == (
        "/Library/Application Support/TimeLapse Pro/pki/headend-api-mtls-ca"
    )
    assert env["TIMELAPSE_HEADEND_API_MTLS_KEYCHAIN_HELPER"] == (
        "/usr/local/libexec/timelapse-ca-keychain"
    )
