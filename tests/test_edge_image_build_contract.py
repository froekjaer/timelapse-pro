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


def test_image_manifest_cannot_fall_back_to_hash_only_trust() -> None:
    with pytest.raises(RuntimeError, match="GPG release-nøgle mangler"):
        builder._sign_manifest("{}", None, lambda _message: None)


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
