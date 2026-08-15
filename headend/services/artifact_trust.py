"""Fail-closed trust rules for update artifacts."""

import json
from typing import Any


def is_deployable_artifact(artifact: Any) -> bool:
    """Only immutable, cryptographically signed release sources are deployable.

    Hash-only `system-hash` records may still exist as historical/LAB metadata,
    but they are never eligible for approval or installation.
    """
    if not artifact:
        return False
    if not getattr(artifact, "sha256", None):
        return False
    signature = str(getattr(artifact, "signature", "") or "").strip()
    signed_by = str(getattr(artifact, "signed_by", "") or "").strip()
    if not signature or not signed_by:
        return False
    if signed_by == "system-hash" or signature.startswith("sha256:"):
        return False
    if not signature.startswith("-----BEGIN PGP SIGNATURE-----"):
        return False
    try:
        manifest = json.loads(artifact.manifest_json or "{}")
    except (TypeError, ValueError):
        return False
    if not isinstance(manifest, dict) or not manifest:
        return False
    return not bool((manifest.get("source") or {}).get("dirty_worktree"))
