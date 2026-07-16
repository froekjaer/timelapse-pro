import json
import importlib.util
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
