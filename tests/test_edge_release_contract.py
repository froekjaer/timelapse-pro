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

    assert '(root / "edge").glob("*.py")' in collector
    for runtime_path in (
        'root / "edge" / "ai"',
        'root / "edge" / "hal"',
        'root / "edge" / "scripts"',
        'root / "edge" / "tools"',
        'root / "edge" / "utils"',
    ):
        assert runtime_path in collector


def test_edge_release_artifact_globs_top_level_edge_modules_not_a_hand_list():
    """Regression: a hand-listed top-level module set went stale on 2026-08-16 —
    edge/update_lifecycle.py shipped in agent.py's hard-required imports without
    ever being added to the artifact manifest, crash-looping TL-043EB9E72EFD on
    its first artifact-based update. Executes the real collector against the
    real tree so any *future* top-level edge/*.py module is caught the same way.
    """
    import ast
    import hashlib

    source = _source("headend/main.py")
    tree = ast.parse(source)
    func = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_collect_release_outputs"
    )
    code = compile(ast.Module(body=[func], type_ignores=[]), "<collector>", "exec")
    ns = {
        "Path": Path,
        "list": list,
        "_file_sha256": lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
    }
    exec(code, ns)
    outputs = {o["path"] for o in ns["_collect_release_outputs"](ROOT)}

    expected_top_level = {
        f"edge/{p.name}" for p in (ROOT / "edge").glob("*.py")
    }
    missing = expected_top_level - outputs
    assert not missing, f"top-level edge/*.py modules missing from release artifact: {missing}"


def test_edge_release_artifact_includes_all_of_edge_tools_not_a_hand_list():
    """Regression: edge/tools was hand-listed down to a single file
    (bootstrap_cli.py) while every sibling runtime directory (edge/ai,
    edge/scripts, ...) was a full directory candidate. edge_qa_npu_runner.py
    lived in edge/tools/ but was never in that hand-list, so it never shipped
    in a release artifact — NPU QA silently never ran on TL-043EB9E72EFD,
    found 2026-08-19. Executes the real collector against the real tree so
    any *future* edge/tools/*.py script is caught the same way.
    """
    import ast
    import hashlib

    source = _source("headend/main.py")
    tree = ast.parse(source)
    func = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_collect_release_outputs"
    )
    code = compile(ast.Module(body=[func], type_ignores=[]), "<collector>", "exec")
    ns = {
        "Path": Path,
        "list": list,
        "_file_sha256": lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
    }
    exec(code, ns)
    outputs = {o["path"] for o in ns["_collect_release_outputs"](ROOT)}

    expected_tools = {
        f"edge/tools/{p.name}" for p in (ROOT / "edge" / "tools").glob("*.py")
    }
    missing = expected_tools - outputs
    assert not missing, f"edge/tools/*.py scripts missing from release artifact: {missing}"


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
    # 2026-08-25: the narrow per-unit-file grant was folded into a broader
    # /etc ReadWritePaths grant (useradd/chpasswd need write access to the
    # containing directory for their atomic-rename temp files, not just
    # specific filenames — see edge/scripts/timelapse-edge.service's own
    # comment). The self-update capability this line originally guarded is
    # still covered: /etc/systemd/system/timelapse-edge.service is a
    # subpath of /etc.
    assert "ReadWritePaths=/data /opt/timelapse /opt/timelapse/edge /run/timelapse /etc" in unit


def test_rolled_back_update_can_be_explicitly_reapproved():
    source = _source("headend/main.py")
    approve_block = source[source.index("def approve_update("):source.index("def _user_can_approve_update(")]
    target_block = source[source.index("def _ensure_update_targets("):source.index("def _update_flow_stage(")]

    assert '"rolled_back"' in approve_block
    assert 'existing.status in {"pending", "failed", "rolled_back"}' in target_block
    assert "existing.completed_at = None" in target_block


def test_already_current_update_target_cannot_remain_queued():
    source = _source("headend/main.py")
    supersession_source = _source("headend/services/update_supersession.py")
    target_block = source[source.index("def _ensure_update_targets("):source.index("def _update_flow_stage(")]

    assert "from services.update_supersession import device_already_at_update_version" in source
    assert "def device_already_at_update_version" in supersession_source
    assert "already_current = device_already_at_update_version(device, update)" in target_block
    assert 'existing.status in {"pending", "queued", "approved", "authorized"}' in target_block
    assert 'existing.status = "deployed"' in target_block
    assert 'status="deployed" if already_current else' in target_block
    assert 'update.status = "deployed"' in target_block


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


def test_edge_installer_writes_verified_receipt_before_post_restart_health_gate():
    source = _source("edge/agent.py")
    install_block = source.split("def _run_artifact_app_update", 1)[1].split("def _run_artifact_os_update", 1)[0]
    reconcile_block = source.split("def _reconcile_pending_app_update", 1)[1].split("def _finalize_pending_app_update_health", 1)[0]

    assert '"schema": "timelapse.edge.release.v1"' in install_block
    assert 'receipt_path = repo / "edge" / ".timelapse-release.json"' in install_block
    assert '_os.fsync(handle.fileno())' in install_block
    assert '_os.replace(receipt_tmp, receipt_path)' in install_block
    assert 'persisted_receipt != release_receipt' in install_block
    assert 'release_receipt_readback_mismatch' in install_block
    assert "backup_receipt = backup / \"edge\" / receipt_path.name" in install_block
    assert 'restore_previous_app_release(repo, artifact)' in install_block

    receipt_i = install_block.index('persisted_receipt =')
    pending_i = install_block.index('write_pending_app_update(')
    guard_i = install_block.index('write_post_restart_guard(')
    restart_i = install_block.index('_sp.Popen(["systemctl", "restart", "timelapse-edge"])')
    assert receipt_i < pending_i < guard_i < restart_i
    assert 'self._report_update(update_id, "deployed")' not in install_block
    assert 'awaiting_post_restart_health' in install_block
    assert 'self._report_update(update_id, "deployed", "post_restart_health_confirmed")' in reconcile_block
    assert reconcile_block.index('post_restart_health_confirmed') < reconcile_block.index('cleanup_pending_app_update(pending_path)')


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
    # 2026-08-19: on_site_service (boolean) replaced by field_role (tag:
    # none|installer|technician) — same orthogonal-capability intent, more
    # granular. See headend.database.User.field_role and main._has_field_access.
    database = _source("headend/database.py")
    headend = _source("headend/main.py")
    users_ui = _source("timelapse-ui/src/pages/UsersPage.tsx")

    assert "field_role = Column(String(20)" in database
    assert "field_role:  Optional[str]" in headend
    assert 'FIELD_ROLES = ("none", "installer", "technician")' in headend
    assert "Felt-rolle (on-site adgang)" in users_ui
    assert "Brugeren mangler capability: On-site idriftsættelse og service" in headend


def test_local_totp_qr_never_returns_a_shared_factory_secret() -> None:
    headend = _source("headend/main.py")
    camera_ui = _source("timelapse-ui/src/pages/CameraPage.tsx")
    endpoint = headend.split("def get_camera_bt_totp_qr", 1)[1].split("def regenerate_camera_bt_totp", 1)[0]

    assert 'secret = "JBSWY3DPEHPK3PXP"' not in endpoint
    assert "Lokal adgang er ikke provisioneret" in endpoint
    assert "_has_field_access(current_user)" in endpoint  # 2026-08-19: replaces the old on_site_service check
    assert "account_name = f\"{device_label} - {camera_label}\"" in endpoint
    assert "Åbn i Apple Adgangskoder" in camera_ui
    assert "Kopiér opsætningsnøgle" in camera_ui
    assert "window.location.assign(btTotp.uri)" in camera_ui


def test_bt_totp_qr_response_includes_a_live_rotating_code() -> None:
    """Regression: a live, computed 6-digit code (not the raw secret text)
    used to sit next to the QR code and was lost in an undocumented refactor
    (a51ee8b4, 2026-08-03). Rebuilt 2026-08-19 per Peter. Must be a *computed*
    code (pyotp.TOTP(secret).now()), never the raw secret itself.
    """
    headend = _source("headend/main.py")
    endpoint = headend.split("def get_camera_bt_totp_qr", 1)[1].split("def regenerate_camera_bt_totp", 1)[0]
    camera_ui = _source("timelapse-ui/src/pages/CameraPage.tsx")

    assert '"current_code": totp.now()' in endpoint
    assert '"seconds_remaining"' in endpoint
    assert "btTotp.current_code" in camera_ui
    assert "btTotpCountdown" in camera_ui


def test_local_access_overview_lists_all_visible_cameras_with_rbac() -> None:
    """The admin submenu Peter asked for: all cameras a user can see, with
    their resolved BT-TOTP source layer — never the secret/QR/code itself
    (those stay behind the per-camera endpoint, fetched on demand)."""
    local_access = _source("headend/local_access.py")
    nav = _source("timelapse-ui/src/components/Navbar.tsx")
    app_routes = _source("timelapse-ui/src/App.tsx")

    assert '@router.get("/local-access")' in local_access
    assert "_visible_camera_query" in local_access
    assert '"secret"' not in local_access
    assert '"qr_code"' not in local_access
    assert "/local-access" in nav
    assert "/local-access" in app_routes
    # Ratchet guard: this must live on its own APIRouter, not @app. directly —
    # see tests/test_architecture_ratchet.py.
    assert "@router.get" in local_access
    assert "@app.get" not in local_access


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
