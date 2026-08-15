"""F-005 Edge artifact verification must reject hash-only production trust."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

from security import artifact_manifest_sha, verify_update_artifact  # noqa: E402


def _update_with_artifact(*, signed_by: str, signature: str) -> dict:
    manifest = {
        "schema": "timelapse.update_artifact.v1",
        "artifact_id": "TL-ART-F005",
        "artifact_type": "app",
        "source": {"commit": "abc123", "dirty_worktree": False},
    }
    return {
        "update_type": "app_updates",
        "artifact": {
            "artifact_id": "TL-ART-F005",
            "artifact_type": "app",
            "sha256": artifact_manifest_sha(manifest),
            "manifest": manifest,
            "signature": signature,
            "signed_by": signed_by,
            "signer_fingerprint": "trusted-headend-fingerprint",
        },
    }


def _security_policy() -> dict:
    return {
        "artifact_verification_required": True,
        "trusted_release_signers": [{"fingerprint": "trusted-headend-fingerprint"}],
    }


def test_edge_rejects_system_hash_artifact_even_with_trusted_fingerprint():
    update = _update_with_artifact(
        signed_by="system-hash",
        signature="sha256:" + ("a" * 64),
    )

    ok, reason = verify_update_artifact(update, _security_policy())

    assert ok is False
    assert "hash-bundet" in reason


def test_edge_rejects_hash_only_signature_under_named_signer():
    update = _update_with_artifact(
        signed_by="release-key",
        signature="sha256:" + ("b" * 64),
    )

    ok, reason = verify_update_artifact(update, _security_policy())

    assert ok is False
    assert "hash-only" in reason
