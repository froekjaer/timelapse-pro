"""Filesystem path confinement helpers for Headend-served evidence/preview files."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote


class UnsafePath(ValueError):
    """Raised when a user-controlled path component escapes its allowed root."""


def _safe_component(value: str, *, label: str) -> str:
    raw = str(value or "")
    decoded = unquote(raw)
    if not decoded or "\x00" in decoded:
        raise UnsafePath(f"invalid {label}")
    if decoded in {".", ".."} or Path(decoded).name != decoded:
        raise UnsafePath(f"invalid {label}")
    if Path(decoded).is_absolute():
        raise UnsafePath(f"invalid {label}")
    return decoded


def resolve_lab_preview_path(
    sftp_base: str | Path,
    device_id: str,
    filename: str,
    *,
    thumbnail: bool = False,
) -> Path:
    """Resolve a LAB preview path and prove it remains under the device LAB root.

    FastAPI normally percent-decodes route parameters, but this helper also
    decodes defensively so encoded traversal is rejected if it reaches this
    layer through another caller or framework behavior.
    """
    safe_device = _safe_component(device_id, label="device_id")
    safe_filename = _safe_component(filename, label="filename")

    root = (Path(sftp_base) / "_lab" / safe_device).resolve()
    if thumbnail:
        root = (root / ".thumbs").resolve()
    candidate = (root / safe_filename).resolve()

    if candidate.parent != root:
        raise UnsafePath("path escapes LAB preview root")
    return candidate
