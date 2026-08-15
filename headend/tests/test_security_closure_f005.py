"""F-005 security closure: release artifacts must be truly signed."""
import json
import os
import pathlib
import sys
import tempfile
from types import SimpleNamespace

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"

from services.artifact_trust import is_deployable_artifact, sign_release_artifact_payload  # noqa: E402


def _clear_signer_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHANGE_TICKET_GPG_KEY", raising=False)
    monkeypatch.delenv("TIMELAPSE_GPG_KEY", raising=False)
    monkeypatch.delenv("TIMELAPSE_ALLOW_LAB_SYSTEM_HASH_ARTIFACTS", raising=False)


def _artifact(*, signed_by: str, signature: str) -> SimpleNamespace:
    manifest = {
        "schema": "timelapse.update_artifact.v1",
        "source": {"dirty_worktree": False},
    }
    return SimpleNamespace(
        sha256="a" * 64,
        signature=signature,
        signed_by=signed_by,
        storage_path="/tmp/timelapse-artifact",
        manifest_json=json.dumps(manifest),
    )


def test_release_artifact_signing_requires_configured_signer_outside_lab(monkeypatch):
    _clear_signer_env(monkeypatch)
    monkeypatch.setenv("TIMELAPSE_ENV", "production")

    with pytest.raises(RuntimeError, match="Release artifact signing key missing"):
        sign_release_artifact_payload('{"artifact_id":"prod"}')


def test_hash_only_artifact_signing_requires_explicit_lab_flag(monkeypatch):
    _clear_signer_env(monkeypatch)
    monkeypatch.setenv("TIMELAPSE_ENV", "lab")

    with pytest.raises(RuntimeError, match="TIMELAPSE_ALLOW_LAB_SYSTEM_HASH_ARTIFACTS=1"):
        sign_release_artifact_payload('{"artifact_id":"lab-without-flag"}')


def test_explicit_lab_hash_marker_is_not_deployable(monkeypatch):
    _clear_signer_env(monkeypatch)
    monkeypatch.setenv("TIMELAPSE_ENV", "lab")
    monkeypatch.setenv("TIMELAPSE_ALLOW_LAB_SYSTEM_HASH_ARTIFACTS", "1")

    signature, signed_by = sign_release_artifact_payload('{"artifact_id":"lab"}')

    assert signed_by == "system-hash"
    assert signature.startswith("sha256:")
    assert is_deployable_artifact(_artifact(signed_by=signed_by, signature=signature)) is False


def test_system_hash_artifact_is_not_deployable_even_with_clean_manifest():
    artifact = _artifact(signed_by="system-hash", signature="sha256:" + ("b" * 64))

    assert is_deployable_artifact(artifact) is False
