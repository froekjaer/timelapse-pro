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


def test_edge_artifact_download_is_scoped_to_the_authenticated_device():
    source = _source("headend/main.py")
    endpoint = source.split("def download_update_artifact_file", 1)[1].split('@app.get("/api/updates/artifacts")', 1)[0]

    assert "_update_applies_to_device(candidate, device, inventory)" in endpoint
    assert 'detail="Artifact er ikke godkendt til denne Edge"' in endpoint


def test_site_look_configuration_router_is_not_public():
    source = _source("headend/main.py")

    assert 'app.include_router(site_look_router, dependencies=[require_role("super_admin")])' in source


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
    assert "receipt_tmp.replace(receipt_path)" in install_block
    assert "backup_receipt = backup / \"edge\" / receipt_path.name" in install_block


def test_local_management_is_totp_https_only_and_has_no_interactive_shell_by_default():
    service = _source("edge/scripts/totp-service.py")
    captive = _source("edge/scripts/timelapse-captive.sh")

    assert '"https_port": 8443' in service
    assert '"enable_interactive_shell": False' in service
    assert 'if not load_config()["management"].get("enable_interactive_shell", False):' in service
    assert "HTTPServer" not in service
    assert 'http_port = 8080' not in service

    start_block = captive.split("start)", 1)[1].split("stop)", 1)[0]
    assert "-t nat -A PREROUTING" not in start_block
    assert '--dport "$HTTPS_PORT"' in start_block


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
