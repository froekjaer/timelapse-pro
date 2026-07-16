"""Fail-closed trust rules for update artifacts."""

import json
from typing import Any


def is_deployable_artifact(artifact: Any) -> bool:
    """Only immutable release sources may enter approval or deployment flows."""
    if not artifact:
        return False
    try:
        manifest = json.loads(artifact.manifest_json or "{}")
    except (TypeError, ValueError):
        return False
    return not bool((manifest.get("source") or {}).get("dirty_worktree"))
