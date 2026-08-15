"""Fail-closed trust rules for update artifacts."""

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from typing import Any

log = logging.getLogger("timelapse.headend.artifact_trust")


def is_deployable_artifact(artifact: Any) -> bool:
    """Only immutable release sources may enter approval or deployment flows."""
    if not artifact:
        return False
    if not getattr(artifact, "sha256", None):
        return False
    if not getattr(artifact, "signature", None) or not getattr(artifact, "signed_by", None):
        return False
    if str(getattr(artifact, "signed_by", "")).strip() == "system-hash":
        return False
    if str(getattr(artifact, "signature", "")).strip().startswith("sha256:"):
        return False
    try:
        manifest = json.loads(artifact.manifest_json or "{}")
    except (TypeError, ValueError):
        return False
    return not bool((manifest.get("source") or {}).get("dirty_worktree"))


def _explicit_lab_system_hash_artifacts_allowed() -> bool:
    return (
        os.getenv("TIMELAPSE_ENV", "").strip().lower() == "lab"
        and os.getenv("TIMELAPSE_ALLOW_LAB_SYSTEM_HASH_ARTIFACTS", "").strip() == "1"
    )


def sign_release_artifact_payload(payload: str) -> tuple[str, str]:
    """Sign a deployable artifact manifest; hash-only signing is LAB-only."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    key_id = os.getenv("CHANGE_TICKET_GPG_KEY") or os.getenv("TIMELAPSE_GPG_KEY")
    if not key_id:
        if _explicit_lab_system_hash_artifacts_allowed():
            return f"sha256:{digest}", "system-hash"
        raise RuntimeError(
            "Release artifact signing key missing; configure CHANGE_TICKET_GPG_KEY "
            "or TIMELAPSE_GPG_KEY. Hash-only system-hash artifacts are LAB-only "
            "and require TIMELAPSE_ENV=lab plus TIMELAPSE_ALLOW_LAB_SYSTEM_HASH_ARTIFACTS=1."
        )
    payload_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(payload)
            payload_path = f.name
        result = subprocess.run(
            [
                "gpg", "--batch", "--yes", "--armor",
                "--local-user", key_id,
                "--detach-sign", "--output", "-", payload_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), key_id
        if _explicit_lab_system_hash_artifacts_allowed():
            log.warning("LAB artifact GPG signing failed; using hash-only marker: %s", result.stderr[-300:])
            return f"sha256:{digest}", "system-hash"
        raise RuntimeError(f"Release artifact GPG signing failed: {result.stderr[-300:]}")
    except RuntimeError:
        raise
    except Exception as exc:
        if _explicit_lab_system_hash_artifacts_allowed():
            log.warning("LAB artifact GPG signing unavailable; using hash-only marker: %s", exc)
            return f"sha256:{digest}", "system-hash"
        raise RuntimeError(f"Release artifact GPG signing unavailable: {exc}") from exc
    finally:
        if payload_path:
            try:
                os.unlink(payload_path)
            except OSError:
                pass
