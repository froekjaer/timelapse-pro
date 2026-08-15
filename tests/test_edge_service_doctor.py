import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


bootstrap_cli = _load_module("edge_bootstrap_cli_test", ROOT / "edge" / "tools" / "bootstrap_cli.py")
node_inventory = _load_module("node_inventory_test", ROOT / "node-agent" / "collectors" / "inventory.py")


def _commissioned_edge(tmp_path: Path) -> Path:
    base = tmp_path / "edge"
    base.mkdir()
    (base / "bootstrap.yaml").write_text(
        "device_id: TL-TEST-EDGE\n"
        "headend_url: https://headend.example.test/api\n"
        "bootstrap_token: top-secret-token\n",
        encoding="utf-8",
    )
    (base / "local_network.yaml").write_text("connectivity: {}\n", encoding="utf-8")
    (base / "config.yaml").write_text("quality: {}\n", encoding="utf-8")
    (base / ".timelapse-release.json").write_text(
        json.dumps({
            "schema": "timelapse.edge.release.v1",
            "artifact_id": "TL-ART-TEST",
            "source_commit": "a" * 40,
        }),
        encoding="utf-8",
    )
    return base


def test_doctor_json_is_versioned_read_only_and_redacts_credentials(tmp_path, monkeypatch):
    base = _commissioned_edge(tmp_path)
    commands = []

    monkeypatch.setattr(bootstrap_cli, "command_exists", lambda _name: False)
    monkeypatch.setattr(
        bootstrap_cli,
        "run",
        lambda command, **_kwargs: commands.append(command),
    )

    evidence = bootstrap_cli.collect_doctor_evidence(base)

    assert evidence["schema"] == "timelapse.edge.doctor.v1"
    assert evidence["device_id"] == "TL-TEST-EDGE"
    assert "top-secret-token" not in json.dumps(evidence)
    assert any(c["id"] == "release.receipt" and c["ok"] for c in evidence["checks"])
    assert commands == []


def test_doctor_checks_complete_local_service_chain(tmp_path, monkeypatch):
    base = _commissioned_edge(tmp_path)
    monkeypatch.setattr(bootstrap_cli, "command_exists", lambda name: name == "systemctl")
    monkeypatch.setattr(bootstrap_cli, "service_state", lambda service: {"active": "active"})

    evidence = bootstrap_cli.collect_doctor_evidence(base)
    service_ids = {c["id"] for c in evidence["checks"] if c["id"].startswith("service.")}

    assert service_ids == {f"service.{service}" for service in bootstrap_cli.EXPECTED_SERVICES}


def test_doctor_accepts_python_plus_runner_script_command(tmp_path, monkeypatch):
    base = _commissioned_edge(tmp_path)
    runner = tmp_path / "edge_qa_runner.py"
    runner.write_text("print('{}')\n", encoding="utf-8")
    (base / "config.yaml").write_text(
        "quality:\n"
        "  edge_ai:\n"
        "    enabled: true\n"
        f"    runner: {sys.executable} {runner}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap_cli, "command_exists", lambda _name: False)

    evidence = bootstrap_cli.collect_doctor_evidence(base)
    runner_check = next(check for check in evidence["checks"] if check["id"] == "ai.runner")

    assert runner_check["ok"] is True
    assert str(runner) in runner_check["detail"]


def test_nikon_image_quality_fallback_is_used_when_generic_path_is_absent(monkeypatch):
    configured = []
    monkeypatch.setattr(
        bootstrap_cli,
        "gphoto_config_exists",
        lambda path: path == "/main/capturesettings/imagequality",
    )
    monkeypatch.setattr(
        bootstrap_cli,
        "camera_set_config",
        lambda path, value: configured.append((path, value)) or True,
    )

    assert bootstrap_cli.camera_set_photo_setting("image_format", "JPEG Fine") is True
    assert configured == [("/main/capturesettings/imagequality", "JPEG Fine")]


def test_camera_maintenance_restores_enabled_edge_even_if_initially_inactive(tmp_path, monkeypatch):
    base = _commissioned_edge(tmp_path)
    actions = []
    service_state_dir = tmp_path / "service-state"
    monkeypatch.setenv("TIMELAPSE_SERVICE_STATE_DIR", str(service_state_dir))
    if str(ROOT / "edge") not in sys.path:
        sys.path.insert(0, str(ROOT / "edge"))
    from service_platform import ServicePlatform

    ServicePlatform(state_dir=service_state_dir).start_offline_recovery_session()
    monkeypatch.setenv("TIMELAPSE_CAMERA_MAINTENANCE_LOCK", str(tmp_path / "camera.lock"))
    monkeypatch.setattr(bootstrap_cli, "is_service_active", lambda _service: False)
    monkeypatch.setattr(bootstrap_cli, "is_service_enabled", lambda _service: True)
    monkeypatch.setattr(bootstrap_cli, "build_relay", lambda _base: None)
    monkeypatch.setattr(bootstrap_cli.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        bootstrap_cli,
        "systemctl",
        lambda action, service, timeout=30: actions.append((action, service, timeout)),
    )
    monkeypatch.setattr(bootstrap_cli, "wait_for_service_state", lambda *_args, **_kwargs: None)

    assert bootstrap_cli.run_camera_operation(lambda: True, base, maintenance=True) is True
    assert actions == [("start", bootstrap_cli.SERVICE_NAME, 60)]


def test_node_inventory_prefers_deployed_release_receipt(tmp_path, monkeypatch):
    receipt = tmp_path / ".timelapse-release.json"
    receipt.write_text(json.dumps({
        "schema": "timelapse.node.release.v1",
        "source_commit": "b" * 40,
    }), encoding="utf-8")
    monkeypatch.delenv("TIMELAPSE_APP_VERSION", raising=False)
    monkeypatch.setattr(node_inventory, "RELEASE_METADATA_FILES", (receipt,))

    assert node_inventory._app_version() == "b" * 40


def test_node_inventory_allows_explicit_release_version(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_APP_VERSION", "v3.0.0-test.1")

    assert node_inventory._app_version() == "v3.0.0-test.1"
