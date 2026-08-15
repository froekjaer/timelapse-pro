"""Cryptographic artifact verification contracts for the Edge acceptance gate."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from edge.security import artifact_manifest_sha, canonical_json, verify_update_artifact
from headend.services.artifact_trust import is_deployable_artifact


@pytest.fixture(scope="module")
def release_signer(tmp_path_factory):
    if shutil.which("gpg") is None:
        pytest.fail("gpg is required by the Edge artifact trust contract")
    home = tmp_path_factory.mktemp("release-gpg")
    home.chmod(0o700)
    uid = "TimeLapse CI Release <release-ci@timelapse.invalid>"
    generated = subprocess.run(
        [
            "gpg", "--batch", "--no-tty", "--homedir", str(home),
            "--passphrase", "", "--quick-generate-key", uid, "ed25519", "sign", "0",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr

    listing = subprocess.run(
        ["gpg", "--batch", "--homedir", str(home), "--with-colons", "--list-keys", uid],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout
    fingerprint = next(
        line.split(":")[9]
        for line in listing.splitlines()
        if line.startswith("fpr:")
    )
    public_key = subprocess.run(
        ["gpg", "--batch", "--homedir", str(home), "--armor", "--export", fingerprint],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()
    assert public_key.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----")
    return home, fingerprint, public_key


def _signed_update(release_signer, manifest: dict) -> tuple[dict, dict]:
    home, gpg_fingerprint, public_key = release_signer
    manifest_path = Path(home) / "manifest.json"
    signature_path = Path(home) / "manifest.asc"
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    subprocess.run(
        [
            "gpg", "--batch", "--yes", "--no-tty", "--homedir", str(home),
            "--armor", "--detach-sign", "--local-user", gpg_fingerprint,
            "--output", str(signature_path), str(manifest_path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    signature = signature_path.read_text(encoding="utf-8")
    material_fingerprint = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    update = {
        "update_type": "app_updates",
        "artifact": {
            "artifact_id": "TL-ART-CRYPTO-TEST",
            "artifact_type": "app",
            "manifest": manifest,
            "sha256": artifact_manifest_sha(manifest),
            "signature": signature,
            "signed_by": gpg_fingerprint[-16:],
            "signer_fingerprint": material_fingerprint,
        },
    }
    security = {
        "artifact_verification_required": True,
        "trusted_release_signers": [{
            "fingerprint": material_fingerprint,
            "gpg_fingerprint": gpg_fingerprint,
            "public_key": public_key,
            "algorithm": "openpgp",
        }],
    }
    return update, security


def test_real_openpgp_signature_is_verified(release_signer):
    manifest = {
        "schema": "timelapse.update_artifact.v1",
        "artifact_id": "TL-ART-CRYPTO-TEST",
        "source": {"commit": "abc123", "dirty_worktree": False},
    }
    update, security = _signed_update(release_signer, manifest)
    ok, reason = verify_update_artifact(update, security)
    assert ok is True, reason
    assert "OpenPGP signature verified" in reason


def test_tampered_manifest_with_recomputed_hash_still_fails_signature(release_signer):
    manifest = {
        "schema": "timelapse.update_artifact.v1",
        "artifact_id": "TL-ART-CRYPTO-TEST",
        "source": {"commit": "abc123", "dirty_worktree": False},
    }
    update, security = _signed_update(release_signer, manifest)
    update["artifact"]["manifest"]["source"]["commit"] = "attacker-controlled"
    # This is the exact weakness in the old implementation: an attacker could
    # recompute the self-consistency hash. The detached signature must still fail.
    update["artifact"]["sha256"] = artifact_manifest_sha(update["artifact"]["manifest"])
    ok, reason = verify_update_artifact(update, security)
    assert ok is False
    assert "signaturverifikation fejlede" in reason


def test_hash_only_marker_is_rejected_before_crypto(release_signer):
    manifest = {"schema": "timelapse.update_artifact.v1", "source": {"dirty_worktree": False}}
    update, security = _signed_update(release_signer, manifest)
    update["artifact"]["signed_by"] = "system-hash"
    update["artifact"]["signature"] = "sha256:" + ("a" * 64)
    ok, reason = verify_update_artifact(update, security)
    assert ok is False
    assert "hash-only" in reason


def test_code_update_cannot_disable_artifact_verification(release_signer):
    manifest = {"schema": "timelapse.update_artifact.v1", "source": {"dirty_worktree": False}}
    update, security = _signed_update(release_signer, manifest)
    security["artifact_verification_required"] = False
    ok, reason = verify_update_artifact(update, security)
    assert ok is False
    assert "kan ikke deaktiveres" in reason


def test_headend_never_marks_hash_only_artifact_deployable():
    artifact = SimpleNamespace(
        sha256="a" * 64,
        signature="sha256:" + ("b" * 64),
        signed_by="system-hash",
        manifest_json='{"source":{"dirty_worktree":false}}',
    )
    assert is_deployable_artifact(artifact) is False
