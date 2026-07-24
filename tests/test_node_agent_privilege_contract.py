from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "node-agent" / "install" / "macos.sh"
ENROLLER = ROOT / "deploy" / "install" / "enroll_headend_cmdb.sh"


def test_macos_node_agent_installer_drops_root_privileges():
    source = INSTALLER.read_text(encoding="utf-8")

    assert "<key>UserName</key>" in source
    assert "<string>$SERVICE_USER</string>" in source
    assert "<key>GroupName</key>" in source
    assert "<string>$SERVICE_GROUP</string>" in source
    assert '"$(id -u "$SERVICE_USER")" != "0"' in source


def test_macos_node_agent_remains_boot_managed():
    source = INSTALLER.read_text(encoding="utf-8")

    assert 'PLIST_PATH="/Library/LaunchDaemons/$PLIST_NAME.plist"' in source
    assert "<key>RunAtLoad</key>" in source
    assert "<key>KeepAlive</key>" in source


def test_macos_installer_has_no_environment_specific_identity_defaults():
    source = INSTALLER.read_text(encoding="utf-8")

    assert 'DEVICE_ID=""' in source
    assert 'HEADEND_URL=""' in source
    assert "timelapse.froekjaer.dk" not in source
    assert "TL-MACMINI-HEADEND-TEST-1" not in source
    assert "--api-token-file" in source
    assert "chmod 640" in source


def test_headend_enrollment_is_file_secret_and_fail_closed():
    source = ENROLLER.read_text(encoding="utf-8")

    assert "--bootstrap-token-file" in source
    assert '"node_type": "headend"' in source
    assert "Inventar rapporteret OK" in source
    assert "Ingen ny inventory-kvittering" in source
    assert "curl -k" not in source
    assert 'tail -n "+$LOG_START_LINE"' in source
