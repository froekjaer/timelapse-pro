"""Regression contracts for Edge release completeness and local management."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "edge"))
from utils import inventory


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_edge_release_artifact_contains_all_active_runtime_paths():
    source = _source("headend/main.py")
    collector = source.split("def _collect_release_outputs", 1)[1].split("def _find_artifact_for_update", 1)[0]

    for runtime_path in (
        'root / "edge" / "frame_push.py"',
        'root / "edge" / "ai"',
        'root / "edge" / "hal"',
        'root / "edge" / "scripts"',
        'root / "edge" / "tools" / "bootstrap_cli.py"',
        'root / "edge" / "utils"',
    ):
        assert runtime_path in collector


def test_release_artifacts_use_immutable_artifact_scoped_storage():
    source = _source("headend/main.py")
    snapshot = source.split("def _materialize_release_snapshot", 1)[1].split("\n\ndef ", 1)[0]
    tag_builder = source.split("def _build_artifact_from_git_tag", 1)[1].split("def _git_tag_poller_loop", 1)[0]

    assert 'storage_root / artifact_id' in snapshot
    assert '_verify_snapshot(staging_root)' in snapshot
    assert '0o550 if snapshot_file.is_dir() else 0o440' in snapshot
    assert 'staging_root.rename(final_root)' in snapshot
    assert '_materialize_release_snapshot(tmp_path, artifact_id, outputs)' in tag_builder
    assert 'storage_path=str(snapshot_root)' in tag_builder


def test_dirty_worktree_artifacts_are_fail_closed_everywhere():
    source = _source("headend/main.py")
    current_catalog = source.split("def catalog_current_release_artifact", 1)[1].split("\n\n@app.", 1)[0]
    finder = source.split("def _find_artifact_for_update", 1)[1].split("\n\ndef ", 1)[0]
    binder = source.split("def bind_artifact_to_update", 1)[1].split("\n\n@app.", 1)[0]

    assert 'if _release_worktree_dirty():' in current_catalog
    assert 'status_code=409' in current_catalog
    assert finder.count('is_deployable_artifact(') >= 3
    assert 'if not is_deployable_artifact(artifact):' in binder


def test_updates_ui_catalogs_only_from_signed_git_tags():
    source = _source("timelapse-ui/src/pages/UpdatesPage.tsx")

    assert "Registrer seneste signerede tag" in source
    assert "'/api/updates/artifacts/catalog-from-git-tag'" in source


def test_edge_artifact_download_is_scoped_to_the_authenticated_device():
    source = _source("headend/main.py")
    endpoint = source.split("def download_update_artifact_file", 1)[1].split('@app.get("/api/updates/artifacts")', 1)[0]

    assert "_update_applies_to_device(candidate, device, inventory)" in endpoint
    assert 'detail="Artifact er ikke godkendt til denne Edge"' in endpoint


def test_headend_matches_full_gpg_fingerprint_and_64_bit_key_id():
    source = _source("headend/main.py")
    matcher = source.split("def _release_signer_matches", 1)[1].split("\n\ndef ", 1)[0]

    assert "len(key_id) >= 16" in matcher
    assert "fingerprint.endswith(key_id)" in matcher
    assert "_release_signer_matches(artifact.signed_by, signer)" in source


def test_site_look_configuration_router_is_not_public():
    source = _source("headend/main.py")

    assert 'app.include_router(site_look_router, dependencies=[require_role("super_admin")])' in source


def test_site_look_edge_policy_uses_device_auth_and_active_camera_binding():
    source = _source("headend/main.py")
    endpoint = source.split("def get_edge_site_look_config", 1)[1].split('@app.get("/api/admin/devices/{device_id}/config")', 1)[0]

    assert 'Depends(_verify_device_token)' in endpoint
    assert 'camera = _active_camera_for_device(db, device_id)' in endpoint
    assert 'service.get_config(' in endpoint
    assert 'for_edge_node=device_id' in endpoint


def test_site_look_edge_client_is_signed_and_uses_an_atomic_private_cache():
    source = _source("edge/ai/site_look_config_client.py")

    assert 'path = f"/edge/site-look/{self._edge_node_id}/config"' in source
    assert 'request_signature_headers(self._api_token, "GET", path)' in source
    assert 'edge_attestation_headers(' in source
    assert 'os.replace(temp_path, self._cache_path)' in source
    assert 'os.chmod(self._cache_path, 0o600)' in source


def test_edge_agent_starts_and_stops_the_site_look_policy_client():
    source = _source("edge/agent.py")

    assert 'self._site_look_config_client = self._init_site_look_config_client()' in source
    shutdown = source.split('def _shutdown(self)', 1)[1].split('# ── Helpers', 1)[0]
    assert 'self._site_look_config_client.stop_polling()' in shutdown


def test_lab_mode_keeps_signed_update_poll_active():
    source = _source("edge/agent.py")
    lab_tick = source.split("def _lab_tick", 1)[1].split("\n    def ", 1)[0]

    assert "self._check_and_apply_updates_if_due()" in lab_tick


def test_artifact_install_activates_and_verifies_local_management_services():
    source = _source("edge/agent.py")
    install_block = source.split("def _run_artifact_app_update", 1)[1].split("def _run_artifact_os_update", 1)[0]
    unit = _source("edge/scripts/timelapse-edge.service")

    assert '"timelapse-bt-pan.service"' in install_block
    assert '"timelapse-bt-agent.service"' in install_block
    assert '"timelapse-captive.service"' in install_block
    assert '"timelapse-totp.service"' in install_block
    assert 'managed_unit_files = (*managed_units, "timelapse-edge.service")' in install_block
    assert '["systemctl", "daemon-reload"]' in install_block
    assert '["systemctl", "restart", service]' in install_block
    assert '["systemctl", "is-active", "--quiet", service]' in install_block
    assert '["systemctl", "try-restart", service]' in install_block
    assert "bt_pan_active" in install_block
    assert "captive firewall afventer PAN-recovery" in install_block
    assert "User=root" in unit
    assert "Type=simple" in unit
    assert "WatchdogSec=" not in unit
    assert "ReadWritePaths=/etc/systemd/system/timelapse-edge.service" in unit


def test_rolled_back_update_can_be_explicitly_reapproved():
    source = _source("headend/main.py")
    approve_block = source[source.index("def approve_update("):source.index("def _user_can_approve_update(")]
    target_block = source[source.index("def _ensure_update_targets("):source.index("def _update_flow_stage(")]

    assert '"rolled_back"' in approve_block
    assert 'existing.status in {"pending", "failed", "rolled_back"}' in target_block
    assert "existing.completed_at = None" in target_block


def test_legacy_edge_update_and_time_scripts_cannot_use_direct_internet_channels():
    legacy_executor = _source("edge/cmdb/executor.py")
    direct_deploy = _source("edge/scripts/deploy-totp.sh")
    gps_setup = _source("edge/scripts/setup-gps-time.sh")
    time_sync = _source("edge/scripts/sync-time.sh")

    assert "apt-get" not in legacy_executor
    assert "import subprocess" not in legacy_executor
    assert "_apply_git" not in legacy_executor
    assert "scp " not in direct_deploy
    assert "apt-get" not in gps_setup
    assert "pool pool.ntp.org" not in gps_setup
    assert "http://192.168.86.125" not in time_sync
    assert '[[ ! "$HEADEND_URL" =~ ^https:// ]]' in time_sync


def test_artifact_receipt_is_cmdb_version_source_of_truth(tmp_path, monkeypatch):
    receipt = tmp_path / ".timelapse-release.json"
    receipt.write_text(
        '{"schema":"timelapse.edge.release.v1","artifact_id":"TL-ART-1",'
        '"source_commit":"deadbeef","version":"v2.8.1-lab.4",'
        '"installed_at":"2026-07-14T12:00:00+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(inventory, "RELEASE_METADATA_FILE", receipt)

    assert inventory._artifact_release_metadata()["source_commit"] == "deadbeef"


def test_edge_installer_writes_a_verified_artifact_receipt():
    source = _source("edge/agent.py")
    install_block = source.split("def _run_artifact_app_update", 1)[1].split("def _run_artifact_os_update", 1)[0]

    assert '"schema": "timelapse.edge.release.v1"' in install_block
    assert 'receipt_path = repo / "edge" / ".timelapse-release.json"' in install_block
    assert '_os.fsync(handle.fileno())' in install_block
    assert '_os.replace(receipt_tmp, receipt_path)' in install_block
    assert 'persisted_receipt != release_receipt' in install_block
    assert 'release_receipt_readback_mismatch' in install_block
    assert install_block.index('persisted_receipt =') < install_block.index('self._report_update(update_id, "deployed")')
    assert "backup_receipt = backup / \"edge\" / receipt_path.name" in install_block
    assert 'elif receipt_path.exists()' in install_block
    assert 'receipt_path.unlink()' in install_block


def test_local_management_is_totp_https_only_and_has_no_interactive_shell_by_default():
    service = _source("edge/scripts/totp-service.py")
    captive = _source("edge/scripts/timelapse-captive.sh")

    assert '"https_port": 8443' in service
    assert '"enable_interactive_shell": False' in service
    assert '"sid": "unprovisioned"' in service
    assert '"secret": "JBSWY3DPEHPK3PXP"' not in service
    assert 'if not load_config()["management"].get("enable_interactive_shell", False):' in service
    assert "HTTPServer" not in service
    assert 'http_port = 8080' not in service

    start_block = captive.split("start)", 1)[1].split("stop)", 1)[0]
    assert "-t nat -A PREROUTING" not in start_block
    assert '--dport "$HTTPS_PORT"' in start_block


def test_edge_cli_exposes_a_visible_terminal_navigation_entry():
    service = _source("edge/scripts/totp-service.py")

    assert 'href="/mgmt/cli#terminal">Terminal</a>' in service
    assert 'id="terminal"' in service


def test_edge_terminal_translates_common_control_keys_to_ansi():
    service = _source("edge/scripts/totp-service.py")

    for sequence in ("\\x1b[A", "\\x1b[B", "\\x1b[C", "\\x1b[D", "\\x1b[3~", "\\x1b[H", "\\x1b[F"):
        assert sequence in service


def test_flashable_edge_rejects_a_mac_that_does_not_match_its_bound_identity() -> None:
    bootstrap = _source("edge/scripts/bootstrap_agent.py")

    assert "expected_device_id" in bootstrap
    assert "MAC-binding afvist" in bootstrap
    assert "Enrollment stoppes" in bootstrap


def test_broad_local_totp_tolerance_has_a_bruteforce_lockout() -> None:
    service = _source("edge/scripts/totp-service.py")

    assert "AUTH_FAILURE_LIMIT = 5" in service
    assert "AUTH_LOCKOUT_S = 15 * 60" in service
    assert "_totp_login_allowed(client_ip)" in service
    assert "_record_totp_failure(client_ip)" in service
    assert "max(0, min(int(totp_valid_window), 10))" in service


def test_authenticated_local_portal_can_set_date_and_time() -> None:
    service = _source("edge/scripts/totp-service.py")

    assert 'async def mgmt_time_set' in service
    assert '"/mgmt/time/set"' in service
    assert "def _set_local_time" in service
    assert '["timedatectl", "set-time"' in service
    assert "Ret dato og tid manuelt" in service


def test_service_shell_is_explicitly_centrally_controllable() -> None:
    router = _source("headend/api/service_access_api.py")
    admin_ui = _source("timelapse-ui/src/pages/SystemAdminPage.tsx")
    portal = _source("edge/scripts/totp-service.py")

    assert '"interactive_shell_enabled"' in router
    assert "interactive_shell_enabled: interactiveShellEnabled" in admin_ui
    assert 'cfg["management"]["enable_interactive_shell"]' in portal
    shell_handler = portal.split('async def mgmt_cli_bash_ws', 1)[1].split('@app.get("/mgmt/technician/image', 1)[0]
    assert shell_handler.count("await websocket.accept()") == 1


def test_local_management_portal_serves_bluetooth_wifi_and_ethernet_interfaces() -> None:
    service = _source("edge/scripts/totp-service.py")
    captive = _source("edge/scripts/timelapse-captive.sh")

    assert 'host="0.0.0.0"' in service
    assert 'HTTPS_PORT="8443"' in captive
    assert 'BT_BRIDGE="br-bt"' in captive
    assert "Terminal og SSH-klient" in service


def test_on_site_service_is_a_capability_not_a_new_role() -> None:
    database = _source("headend/database.py")
    headend = _source("headend/main.py")
    users_ui = _source("timelapse-ui/src/pages/UsersPage.tsx")

    assert "on_site_service = Column(Boolean" in database
    assert "on_site_service: Optional[bool]" in headend
    assert "On-site idriftsættelse og service" in users_ui
    assert "Brugeren mangler capability: On-site idriftsættelse og service" in headend


def test_local_totp_qr_never_returns_a_shared_factory_secret() -> None:
    headend = _source("headend/main.py")
    camera_ui = _source("timelapse-ui/src/pages/CameraPage.tsx")
    endpoint = headend.split("def get_camera_bt_totp_qr", 1)[1].split("def regenerate_camera_bt_totp", 1)[0]

    assert 'secret = "JBSWY3DPEHPK3PXP"' not in endpoint
    assert "Lokal adgang er ikke provisioneret" in endpoint
    assert "on_site_service" in endpoint
    assert "account_name = f\"{device_label} - {camera_label}\"" in endpoint
    assert "Åbn i Apple Adgangskoder" in camera_ui
    assert "Kopiér opsætningsnøgle" in camera_ui
    assert "window.location.assign(btTotp.uri)" in camera_ui


def test_legacy_local_http_technician_surfaces_cannot_be_started():
    cli = _source("edge/tools/bootstrap_cli.py")
    legacy_ui = _source("edge/technician_ui.py")

    assert "ThreadingHTTPServer" not in cli
    assert "erstattet af TOTP-portalen" in cli
    retired_block = legacy_ui.split("def serve_technician_ui", 1)[1].split('if __name__ == "__main__"', 1)[0]
    assert "HTTPServer(" not in retired_block
    assert "retired; use TOTP HTTPS on port 8443" in retired_block


def test_totp_configuration_writes_are_atomic_and_root_only():
    service = _source("edge/scripts/totp-service.py")
    helper = service.split("def save_config", 1)[1].split("# ── Session", 1)[0]

    assert "os.replace(temp_path, config_path)" in helper
    assert "os.chmod(config_path, 0o600)" in helper
    assert "yaml.safe_dump" in helper


def test_thumbnail_display_paths_never_generate_images_synchronously():
    source = _source("headend/main.py")
    thumbnail_endpoint = source.split("def get_thumbnail", 1)[1].split("def request_thumbnail_generation", 1)[0]
    preview_endpoint = source.split("def get_preview_thumb", 1)[1].split("@app.post(\"/api/admin/devices/{device_id}/lab-clear-command\")", 1)[0]

    assert "_lazy_generate_thumbnail" not in thumbnail_endpoint
    assert "_generate_edge_thumbnail" not in thumbnail_endpoint
    assert "Image.open" not in preview_endpoint
    assert '"X-Thumbnail-Source": "lab-preview-fallback"' in preview_endpoint
