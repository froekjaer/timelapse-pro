from __future__ import annotations

import json
import shutil
from pathlib import Path


RELEASE_SCHEMA = "timelapse.edge.release.v1"


def _expected_release_identity(artifact: dict | None) -> tuple[str, str, str]:
    artifact = artifact if isinstance(artifact, dict) else {}
    manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
    return (
        str(artifact.get("artifact_id") or ""),
        str(artifact.get("source_commit") or manifest.get("source_commit") or ""),
        str(artifact.get("version") or manifest.get("version") or ""),
    )


def release_receipt_matches_artifact(receipt_path: Path, artifact: dict | None) -> bool:
    """Return True only when the durable local receipt identifies this exact artifact."""
    artifact_id, source_commit, version = _expected_release_identity(artifact)
    if not artifact_id or not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(receipt, dict):
        return False
    if receipt.get("schema") != RELEASE_SCHEMA:
        return False
    if str(receipt.get("artifact_id") or "") != artifact_id:
        return False
    if source_commit and str(receipt.get("source_commit") or "") != source_commit:
        return False
    if version and str(receipt.get("version") or "") != version:
        return False
    return True


def _safe_edge_output_paths(artifact: dict | None) -> list[Path]:
    artifact = artifact if isinstance(artifact, dict) else {}
    manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
    outputs: list[Path] = []
    for item in manifest.get("outputs", []):
        if not isinstance(item, dict):
            continue
        raw = str(item.get("path") or "")
        if not raw.startswith("edge/"):
            continue
        rel = Path(raw)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe rollback artifact path: {raw}")
        outputs.append(rel)
    return outputs


def restore_previous_app_release(repo: Path, artifact: dict | None = None) -> dict:
    """Restore the previous app release without shell expansion.

    Files present in ``prev`` are copied recursively (including dotfiles). Files
    introduced only by the current artifact are removed when that artifact's
    output list is available. The previous release receipt is restored and read
    back before success is returned.
    """
    repo = repo.resolve()
    previous = (repo / "prev").resolve()
    if not previous.is_dir():
        raise FileNotFoundError("rollback_source_missing")
    try:
        previous.relative_to(repo)
    except ValueError as exc:
        raise ValueError("rollback source escaped repository") from exc

    removed_new_files = 0
    for rel in _safe_edge_output_paths(artifact):
        current = repo / rel
        prior = previous / rel
        if prior.exists():
            continue
        if current.is_symlink() or current.is_file():
            current.unlink()
            removed_new_files += 1

    restored_files = 0
    for source in previous.rglob("*"):
        if not source.is_file():
            continue
        rel = source.relative_to(previous)
        destination = repo / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored_files += 1

    receipt_path = repo / "edge" / ".timelapse-release.json"
    previous_receipt = previous / "edge" / receipt_path.name
    receipt = None
    if previous_receipt.is_file():
        try:
            expected = json.loads(previous_receipt.read_text(encoding="utf-8"))
            actual = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("rollback_receipt_readback_failed") from exc
        if expected != actual:
            raise RuntimeError("rollback_receipt_readback_mismatch")
        receipt = actual
    else:
        receipt_path.unlink(missing_ok=True)

    return {
        "restored_files": restored_files,
        "removed_new_files": removed_new_files,
        "receipt": receipt,
    }
