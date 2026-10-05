"""Required-but-missing Edge Python packages (Peter, 2026-10-04).

The Python bundle track only ever compared *installed* venv packages against
PyPI (outdated → update). A package that `edge/requirements.txt` requires but
that was never installed was invisible to it — that is how Edge1 ran for
months without `qrcode` (technician QR) and `websockets` (local browser
terminal), while Edge2, built by the image builder, had both.

This module only computes the gap; the caller adds the result to the same
`dependency_updates` plan so it goes through the normal signed-bundle +
approval flow (nothing is installed without approval).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    """PEP 503 name normalisation (qrcode == QRCode, pydantic_core == pydantic-core)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def required_names(requirements_text: str) -> list[str]:
    """Base package names from a requirements file (extras/markers/pins dropped,
    comments and pip options ignored)."""
    names: list[str] = []
    for raw in requirements_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if ";" in line:
            spec, marker = line.split(";", 1)
            # Edge is always Linux; skip packages limited to other platforms.
            if "sys_platform" in marker and "linux" not in marker:
                continue
            line = spec
        match = _NAME_RE.match(line)
        if match and match.group(1) not in names:
            names.append(match.group(1))
    return names


def missing_required_packages(
    installed: dict,
    requirements_text: str,
    latest_version: Callable[[str], str | None],
) -> list[dict]:
    """Packages required by requirements_text but absent from `installed`
    (Edge's `pip list`), with the latest PyPI version to bundle."""
    have = {normalize(str(k)) for k in (installed or {})}
    out: list[dict] = []
    for name in required_names(requirements_text):
        if normalize(name) in have:
            continue
        version = latest_version(name)
        if not version:
            continue
        out.append({
            "name": name,
            "installed_version": "",
            "available_version": version,
            "source_repo": "pypi",
            "reason": "required_missing",
        })
    return out


def edge_requirements_text(repo_root: Path) -> str:
    try:
        return (repo_root / "edge" / "requirements.txt").read_text(encoding="utf-8")
    except OSError:
        return ""
