#!/usr/bin/env python3
"""
Fetch a TimeLapse Pro offline Python dependency bundle by downloading .whl
files directly from PyPI over HTTP, for pip-installed packages in Edge's venv
(edge/requirements.txt) that CMDB reconciliation has found outdated.

Mirrors headend/tools/fetch_os_bundle.py's model exactly, adapted to PyPI:
Edge has no internet, so Headend resolves and downloads the exact wheel file
here (using Headend's own internet access), and Edge later installs it fully
offline via `pip install --no-index --find-links=packages ...`.

Only wheels are supported (never sdist) — building a package from source on
an Orange Pi at install time would require a toolchain and network access to
fetch build dependencies, defeating the offline model. A package with no
compatible wheel for the device's architecture/Python version is skipped
(reported in `not_found`), not force-built.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/{version}/json"
HTTP_USER_AGENT = "TimeLapsePro-Headend-PythonBundle/1.0"

# The exact interpreter Edge's venv runs (matches edge/scripts/timelapse-edge.service's
# ExecStart). Must never be bare "python3"/"pip3" resolved via PATH — that would install
# into whatever system Python happens to be first on PATH, not Edge's actual venv (the
# same class of bug fixed 2026-09-04 in edge/utils/inventory.py's _venv_packages()).
EDGE_VENV_PYTHON = "/opt/timelapse/venv/bin/python3"

# manylinux/musllinux platform-tag substrings that indicate a wheel is
# compatible with the given architecture. "any" always matches (pure Python).
_ARCH_PLATFORM_MARKERS = {
    "arm64": ("aarch64", "arm64"),
    "amd64": ("x86_64",),
    "x86_64": ("x86_64",),
}

# OS-family platform-tag substrings. A platform tag like "macosx_12_0_arm64"
# contains "arm64" and would otherwise pass the arch check above even though
# it is a macOS-only wheel — found 2026-09-09 breaking Linux Edge device
# update #271, which installed a macOS scipy wheel pip then refused to use.
# Every real Edge device is Linux; only the Headend's own macOS pseudo-device
# (TL-MACMINI-HEADEND-TEST-1) needs "macos".
_OS_FAMILY_PLATFORM_MARKERS = {
    "linux": ("linux",),
    "macos": ("macosx",),
}


def _cpython_tag(python_version: str) -> str:
    """'3.10.12' -> 'cp310'."""
    parts = python_version.strip().split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid python_version: {python_version!r}")
    return f"cp{parts[0]}{parts[1]}"


def _parse_wheel_tags(filename: str) -> tuple[str, str, str] | None:
    """Return (python_tag, abi_tag, platform_tag) from a .whl filename, or None."""
    if not filename.endswith(".whl"):
        return None
    stem = filename[: -len(".whl")]
    parts = stem.split("-")
    if len(parts) < 5:
        return None
    return parts[-3], parts[-2], parts[-1]


def _cpython_tag_version(tag: str) -> tuple[int, int] | None:
    """'cp310' -> (3, 10), 'cp39' -> (3, 9). None if not a cpNNN tag.

    Assumes a single-digit major version, true for every CPython 3.x
    release to date (and 2.x is irrelevant here).
    """
    m = re.match(r"^cp(\d)(\d+)$", tag)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def wheel_is_compatible(filename: str, cpython_tag: str, arch: str, os_family: str = "linux") -> bool:
    """True if the wheel's tags are usable on this device.

    Pure-Python universal wheels (py3-none-any / cp3x-none-any) match anything —
    the platform tag is "any", so there's nothing OS-specific to check. Otherwise
    the platform tag must reference both the device's OS family and its
    architecture (checked separately: a tag like "macosx_12_0_arm64" contains
    "arm64" but is not Linux-compatible), and the python/abi tag must match
    exactly or be the stable ABI (abi3, forward-compatible across CPython 3.x
    minor versions from the wheel's own floor).
    """
    tags = _parse_wheel_tags(filename)
    if not tags:
        return False
    python_tag, abi_tag, platform_tag = tags
    if platform_tag == "any":
        return python_tag in ("py3", cpython_tag) or python_tag.startswith("py3")
    os_markers = _OS_FAMILY_PLATFORM_MARKERS.get(os_family, ("linux",))
    if not any(marker in platform_tag for marker in os_markers):
        return False
    arch_markers = _ARCH_PLATFORM_MARKERS.get(arch, (arch,))
    if not any(marker in platform_tag for marker in arch_markers):
        return False
    if python_tag == cpython_tag:
        return True
    if abi_tag == "abi3":
        # abi3 is forward-compatible from the wheel's OWN minimum Python
        # version upward, not universally compatible with any version — a
        # cp311-abi3 wheel requires Python >= 3.11 and fails to install on
        # an older interpreter. Found 2026-09-11 (update #292): a
        # cryptography cp311-abi3 wheel was accepted for Edge's cp310
        # device, downloaded fine, then pip on-device correctly refused it
        # ("Could not find a version that satisfies the requirement").
        wheel_version = _cpython_tag_version(python_tag)
        device_version = _cpython_tag_version(cpython_tag)
        if wheel_version and device_version and device_version >= wheel_version:
            return True
    return False


def python_version_satisfies_requires_python(python_version: str, requires_python: str | None) -> bool:
    """True if `requires_python` (PyPI's release-level constraint, e.g.
    ">=3.11") allows the device's actual interpreter.

    This is a SEPARATE check from wheel_is_compatible(): a release can ship
    a wheel whose filename tags look universally compatible (py3-none-any)
    while its PyPI metadata still declares a Requires-Python floor the
    wheel filename doesn't encode at all — pip enforces this metadata
    regardless of how permissive the filename tag looks. Found 2026-09-11
    (update #292): websockets==17.1 ships a py3-none-any wheel (passes
    every filename-tag check) but declares Requires-Python >=3.11; it
    downloaded fine and then pip on Edge's 3.10.12 device correctly
    refused it ("Package 'websockets' requires a different Python").
    """
    if not requires_python:
        return True
    try:
        return Version(python_version) in SpecifierSet(requires_python)
    except (InvalidVersion, InvalidSpecifier):
        return True


def select_wheel(urls: list[dict[str, Any]], cpython_tag: str, arch: str, os_family: str = "linux") -> dict[str, Any] | None:
    """Pick the best compatible wheel from a PyPI release's `urls` list.

    Prefers a pure-Python universal wheel over an architecture-specific one
    (smaller, simpler, works regardless of any future device architecture change).
    """
    wheels = [u for u in urls if u.get("packagetype") == "bdist_wheel"]
    universal = [u for u in wheels if wheel_is_compatible(u.get("filename", ""), cpython_tag, arch, os_family) and "-none-any" in u.get("filename", "")]
    if universal:
        return universal[0]
    specific = [u for u in wheels if wheel_is_compatible(u.get("filename", ""), cpython_tag, arch, os_family)]
    return specific[0] if specific else None


def _normalize_pypi_name(name: str) -> str:
    """PEP 503 normalization — PyPI treats "pydantic-core", "pydantic_core"
    and "Pydantic.Core" as the same distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def exact_pins_from_requires_dist(requires_dist: list[str] | None) -> dict[str, str]:
    """Extract unconditional exact-version pins ("pkg==1.2.3") from a
    release's requires_dist metadata.

    Skips anything with an environment marker (extras, platform/python
    conditionals — a ";" in the requirement) since those aren't
    unconditionally required, and anything that isn't a single bare "=="
    specifier (ranges, multiple specifiers) since those don't force one
    exact version.
    """
    pins: dict[str, str] = {}
    for raw in requires_dist or []:
        req = str(raw or "").strip()
        if ";" in req:
            continue
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*\(?==\s*([A-Za-z0-9][A-Za-z0-9._-]*)\)?$", req)
        if not match:
            continue
        pins[_normalize_pypi_name(match.group(1))] = match.group(2)
    return pins


def fetch_release_metadata(name: str, version: str, verbose: bool = False) -> dict[str, Any] | None:
    url = PYPI_JSON_URL.format(name=name, version=version)
    if verbose:
        print(f"Fetching PyPI metadata: {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def download_wheel(entry: dict[str, Any], dest_dir: Path, verbose: bool = False) -> Path:
    filename = str(entry.get("filename") or "")
    url = str(entry.get("url") or "")
    if not filename or not url:
        raise ValueError("PyPI release entry missing filename/url")
    dest = dest_dir / filename
    expected_sha = str((entry.get("digests") or {}).get("sha256") or "")
    if dest.exists() and expected_sha and sha256_file(dest) == expected_sha:
        if verbose:
            print(f"  cached: {filename}", file=sys.stderr)
        return dest
    if verbose:
        print(f"  downloading: {filename} ({int(entry.get('size') or 0) // 1024} KB)", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if expected_sha:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha:
            raise ValueError(f"SHA256 mismatch for {filename}: expected {expected_sha}, got {actual}")
    dest.write_bytes(data)
    return dest


def wheel_metadata(name: str, version: str, wheel_path: Path) -> dict[str, Any]:
    return {
        "path": f"packages/{wheel_path.name}",
        "filename": wheel_path.name,
        "size_bytes": wheel_path.stat().st_size,
        "sha256": sha256_file(wheel_path),
        "name": name,
        "version": version,
    }


# ── Bundle file writers ───────────────────────────────────────────────────────

def install_script(package_file_entries: list[dict[str, Any]]) -> str:
    """Generate the signed, offline-only pip installer for a bundle.

    Only wheels already present in packages/ are made available; --no-index
    means pip can never reach out to PyPI itself. Exact pinned versions, same
    fail-closed philosophy as the OS bundle's apt-get --no-download install.
    """
    requested = " ".join(
        _shell_quote(f"{entry['name']}=={entry['version']}")
        for entry in package_file_entries
    )
    return f"""#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
{EDGE_VENV_PYTHON} -m pip install --no-index --find-links=packages {requested}
./verify-installed.sh
"""


def verify_script(package_file_entries: list[dict[str, Any]]) -> str:
    lines = ["#!/bin/bash", "set -euo pipefail"]
    for entry in package_file_entries:
        name = _shell_quote(entry["name"])
        version = _shell_quote(entry["version"])
        lines.extend([
            f"actual=$({EDGE_VENV_PYTHON} -m pip show {name} 2>/dev/null | awk -F': ' '/^Version:/ {{print $2}}')",
            f'test "$actual" = {version}',
        ])
    return "\n".join(lines) + "\n"


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


# ── Python callable API ──────────────────────────────────────────────────────

def build_bundle(
    packages: list[dict[str, Any]],
    output: Path,
    device_id: str,
    python_version: str = "3.10.12",
    arch: str = "arm64",
    os_family: str = "linux",
    source_ref: str = "pypi-http",
    verbose: bool = False,
) -> dict[str, Any]:
    """
    High-level Python API: download .whl files and write a bundle directory.

    Each item in `packages` must have at least:
        {"name": "cryptography", "available_version": "42.0.5"}

    Returns a dict with keys: ok, wheel_files, not_found.
    Raises on fatal errors (e.g. no packages downloaded).
    """
    output = Path(output).expanduser().resolve()
    packages_dir = output / "packages"
    if output.exists():
        import shutil
        shutil.rmtree(output)
    packages_dir.mkdir(parents=True)

    cpython_tag = _cpython_tag(python_version)
    package_file_entries: list[dict[str, Any]] = []
    not_found: list[str] = []

    # Pass 1: fetch each candidate's own PyPI metadata at its independently
    # "latest" version, without downloading yet. Each package in `packages`
    # was flagged outdated purely by comparing its own installed vs. latest
    # PyPI version — with no awareness of any other package in this same
    # batch, so two packages that must be version-locked together (e.g. a
    # compiled-extension pair like pydantic/pydantic-core, which pydantic
    # pins to an exact version) can each get bumped to their own latest,
    # producing a pair pip's resolver correctly refuses to install together.
    # Found 2026-09-09 breaking update #271 (Edge 1): pydantic==2.13.5 was
    # requested alongside pydantic_core==2.48.0, but pydantic 2.13.5 itself
    # requires pydantic-core==2.46.5 exactly.
    candidate_names = {_normalize_pypi_name(str(p.get("name") or "")) for p in packages}
    requested: dict[str, tuple[str, str]] = {}  # normalized name -> (original name, version)
    metadata_by_name: dict[str, dict[str, Any]] = {}
    pins: dict[str, str] = {}
    pin_conflicts: set[str] = set()

    for pkg in packages:
        name = str(pkg.get("name") or "").strip()
        wanted_version = str(pkg.get("available_version") or "").strip()
        if not name or not wanted_version:
            continue
        try:
            metadata = fetch_release_metadata(name, wanted_version, verbose=verbose)
        except Exception as exc:
            print(f"  ERROR fetching metadata for {name}=={wanted_version}: {exc}", file=sys.stderr)
            not_found.append(f"{name}=={wanted_version}")
            continue
        if not metadata:
            print(f"  WARNING: {name}=={wanted_version} not found on PyPI", file=sys.stderr)
            not_found.append(f"{name}=={wanted_version}")
            continue
        normalized = _normalize_pypi_name(name)
        requested[normalized] = (name, wanted_version)
        metadata_by_name[normalized] = metadata
        for pinned_name, pinned_version in exact_pins_from_requires_dist(
            (metadata.get("info") or {}).get("requires_dist")
        ).items():
            if pinned_name not in candidate_names:
                continue  # not something we're independently bumping — irrelevant
            if pinned_name in pins and pins[pinned_name] != pinned_version:
                pin_conflicts.add(pinned_name)  # two packages disagree — don't guess
                continue
            pins[pinned_name] = pinned_version

    # Pass 2: apply pins onto any of our own candidates whose independently-
    # fetched "latest" version doesn't match what another candidate in this
    # same batch actually requires, then re-fetch metadata for the corrected
    # version before downloading.
    for normalized, (name, wanted_version) in list(requested.items()):
        pinned_version = pins.get(normalized)
        if not pinned_version or normalized in pin_conflicts or pinned_version == wanted_version:
            continue
        print(f"  pinning {name}=={pinned_version} (was {wanted_version}, required by another package in this bundle)", file=sys.stderr)
        try:
            corrected = fetch_release_metadata(name, pinned_version, verbose=verbose)
        except Exception as exc:
            print(f"  ERROR fetching pinned metadata for {name}=={pinned_version}: {exc}", file=sys.stderr)
            corrected = None
        if not corrected:
            print(f"  WARNING: pinned version {name}=={pinned_version} not found on PyPI — leaving at {wanted_version}", file=sys.stderr)
            continue
        requested[normalized] = (name, pinned_version)
        metadata_by_name[normalized] = corrected

    for normalized, (name, wanted_version) in requested.items():
        try:
            requires_python = (metadata_by_name[normalized].get("info") or {}).get("requires_python")
            if not python_version_satisfies_requires_python(python_version, requires_python):
                print(
                    f"  WARNING: {name}=={wanted_version} requires Python {requires_python}, "
                    f"device runs {python_version}",
                    file=sys.stderr,
                )
                not_found.append(f"{name}=={wanted_version}")
                continue
            entry = select_wheel(metadata_by_name[normalized].get("urls") or [], cpython_tag, arch, os_family)
            if not entry:
                print(f"  WARNING: no compatible wheel for {name}=={wanted_version} ({cpython_tag}/{arch}/{os_family})", file=sys.stderr)
                not_found.append(f"{name}=={wanted_version}")
                continue
            wheel_path = download_wheel(entry, packages_dir, verbose=verbose)
            package_file_entries.append(wheel_metadata(name, wanted_version, wheel_path))
            print(f"  ✓ {name}=={wanted_version}", file=sys.stderr)
        except Exception as exc:
            print(f"  ERROR downloading {name}=={wanted_version}: {exc}", file=sys.stderr)
            not_found.append(f"{name}=={wanted_version}")

    if not_found:
        print(f"\nWARNING: {len(not_found)} package(s) could not be resolved:", file=sys.stderr)
        for n in not_found:
            print(f"  - {n}", file=sys.stderr)

    if not package_file_entries:
        raise RuntimeError(f"No .whl files downloaded — aborting bundle creation for {output}")

    package_manifest = {
        "schema": "timelapse.python_package_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "python_version": python_version,
        "architecture": arch,
        "os_family": os_family,
        "source_ref": source_ref,
        "packages_requested": packages,
        "package_files": package_file_entries,
        "install_model": "signed local wheel cache; pip install --no-index --find-links exact-version install",
        "fetch_tool": "fetch_python_bundle.py",
    }
    write_json(output / "package-manifest.json", package_manifest)

    install_sh = output / "install-offline.sh"
    install_sh.write_text(install_script(package_file_entries))
    install_sh.chmod(0o755)

    verify_sh = output / "verify-installed.sh"
    verify_sh.write_text(verify_script(package_file_entries))
    verify_sh.chmod(0o755)

    return {
        "ok": True,
        "bundle": output,
        "packages_requested": packages,
        "wheel_files": len(package_file_entries),
        "not_found": not_found,
    }
