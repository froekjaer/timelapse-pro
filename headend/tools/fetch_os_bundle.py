#!/usr/bin/env python3
"""
Fetch a TimeLapse Pro offline OS update bundle by downloading .deb files
directly from Ubuntu/Debian package mirrors over HTTP.

Drop-in companion to build_os_bundle.py for use on macOS (headend) where
apt-get is unavailable. Produces an identical output bundle that can be
catalogued through POST /api/updates/artifacts/catalog-os-bundle.

Usage:
    python3 fetch_os_bundle.py \\
        --output /tmp/os-bundle-noble-2026-06 \\
        --device-id TL-C87FF9587CA0 \\
        --catalog /path/to/os-update-plan.json \\
        --suite noble \\
        --architecture arm64

The bundle is then copied to the Headend and registered:
    POST /api/updates/artifacts/catalog-os-bundle
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Ubuntu mirror configuration ──────────────────────────────────────────────

# arm64 uses ports mirror; amd64 uses the regular archive
MIRROR_ARM64 = "http://ports.ubuntu.com/ubuntu-ports"
MIRROR_AMD64 = "http://archive.ubuntu.com/ubuntu"

# Components and pockets to search, in priority order
COMPONENTS = ["main", "restricted", "universe", "multiverse"]
POCKETS: list[str] = []  # Populated per suite in fetch_package_index()


def _mirror(arch: str) -> str:
    return MIRROR_ARM64 if arch == "arm64" else MIRROR_AMD64


def _pockets_for_suite(suite: str) -> list[str]:
    return [suite, f"{suite}-security", f"{suite}-updates", f"{suite}-backports"]


# ── Package index fetching ────────────────────────────────────────────────────

def fetch_package_index(suite: str, arch: str, verbose: bool = False) -> dict[str, dict]:
    """
    Download and parse Ubuntu Packages.gz indices for the given suite and arch.
    Returns a dict keyed by package name → best available candidate dict.
    """
    mirror = _mirror(arch)
    pockets = _pockets_for_suite(suite)
    index: dict[str, dict] = {}

    for pocket in pockets:
        for component in COMPONENTS:
            url = f"{mirror}/dists/{pocket}/{component}/binary-{arch}/Packages.gz"
            if verbose:
                print(f"Fetching index: {url}", file=sys.stderr)
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    raw = gzip.decompress(resp.read())
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue  # pocket/component doesn't exist
                raise
            for entry in _parse_packages(raw.decode("utf-8", errors="replace")):
                name = entry.get("Package", "")
                if not name:
                    continue
                # Prefer security/updates pockets (they come later in our loop)
                index[name] = entry

    return index


def _parse_packages(text: str) -> list[dict]:
    """Parse a Packages file into a list of dicts."""
    packages = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if line == "":
            if current:
                packages.append(current)
                current = {}
        elif line.startswith(" "):
            # Continuation of previous field
            pass
        elif ": " in line:
            key, _, value = line.partition(": ")
            current[key] = value.strip()
    if current:
        packages.append(current)
    return packages


# ── Download helpers ──────────────────────────────────────────────────────────

def download_deb(
    entry: dict,
    dest_dir: Path,
    mirror: str,
    verbose: bool = False,
) -> Path:
    """Download a .deb file from the Ubuntu archive to dest_dir."""
    filename = entry.get("Filename", "")
    if not filename:
        raise ValueError(f"No Filename in package entry for {entry.get('Package')}")
    url = f"{mirror}/{filename}"
    dest = dest_dir / Path(filename).name
    if dest.exists():
        # Verify SHA256 if already downloaded
        if entry.get("SHA256") and sha256_file(dest) == entry["SHA256"]:
            if verbose:
                print(f"  cached: {dest.name}", file=sys.stderr)
            return dest
        dest.unlink()

    if verbose:
        size = int(entry.get("Size", 0))
        print(f"  downloading: {dest.name} ({size // 1024} KB)", file=sys.stderr)

    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()

    # Verify SHA256 from index
    expected_sha = entry.get("SHA256", "")
    if expected_sha:
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"SHA256 mismatch for {dest.name}: "
                f"expected {expected_sha}, got {actual_sha}"
            )

    dest.write_bytes(data)
    return dest


# ── Catalog / spec parsing (shared with build_os_bundle.py) ─────────────────

def parse_catalog(path: Path, category: str | None = None) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    candidates: list[dict[str, Any]] = []
    if isinstance(data.get("packages"), list):
        candidates.extend(
            item for item in data["packages"]
            if not category or item.get("category") == category
        )
    if isinstance(data.get("decisions"), dict):
        for decision_key, decision in data["decisions"].items():
            if category and decision_key != category:
                continue
            if isinstance(decision, dict) and isinstance(decision.get("packages"), list):
                candidates.extend(decision["packages"])
    if isinstance(data.get("bundle_requests"), list):
        for request in data["bundle_requests"]:
            if category and request.get("category") != category:
                continue
            if isinstance(request, dict) and isinstance(request.get("packages"), list):
                candidates.extend(request["packages"])

    packages = []
    seen: set[tuple] = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if category and item.get("category") not in {None, category}:
            continue
        name = str(item.get("name") or "").strip()
        available = str(item.get("available_version") or "").strip()
        if not name or not available:
            continue
        key = (name, available)
        if key in seen:
            continue
        seen.add(key)
        packages.append({
            "name": name,
            "installed_version": item.get("installed_version"),
            "available_version": available,
            "architecture": item.get("architecture"),
            "category": item.get("category") or "os_updates",
            "source_repo": item.get("source_repo") or item.get("catalog_source"),
        })
    return packages


def parse_package_spec(spec: str) -> dict[str, Any]:
    if "=" not in spec:
        raise SystemExit(f"Invalid --package {spec!r}; expected name=version")
    name, version = spec.split("=", 1)
    name = name.strip()
    version = version.strip()
    if not name or not version:
        raise SystemExit(f"Invalid --package {spec!r}; expected name=version")
    return {
        "name": name,
        "installed_version": None,
        "available_version": version,
        "architecture": None,
        "category": "os_updates",
        "source_repo": "manual",
    }


# ── Deb metadata extraction ───────────────────────────────────────────────────

def deb_metadata_from_index(entry: dict, deb_path: Path) -> dict[str, Any]:
    """Build deb metadata from index entry + downloaded file."""
    return {
        "path": f"packages/{deb_path.name}",
        "filename": deb_path.name,
        "size_bytes": deb_path.stat().st_size,
        "sha256": sha256_file(deb_path),
        "name": entry.get("Package"),
        "version": entry.get("Version"),
        "architecture": entry.get("Architecture"),
        "description": (entry.get("Description", "").splitlines() or [""])[0],
    }


# ── Bundle file writers ───────────────────────────────────────────────────────

def install_script() -> str:
    return """#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
dpkg -i packages/*.deb || apt-get --no-download -f install -y
./verify-installed.sh
"""


def verify_script(packages: list[dict[str, Any]]) -> str:
    lines = ["#!/bin/bash", "set -euo pipefail"]
    for package in packages:
        name = _shell_quote(package["name"])
        version = _shell_quote(package["available_version"])
        lines.extend([
            f"actual=$(dpkg-query -W -f='${{Version}}' {name})",
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


def bundle_summary(root: Path) -> dict[str, Any]:
    files = []
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        files.append({
            "path": str(file_path.relative_to(root)),
            "size_bytes": file_path.stat().st_size,
            "sha256": sha256_file(file_path),
        })
    return {
        "schema": "timelapse.os_bundle_summary.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch an offline OS bundle from Ubuntu mirrors — no apt-get required. "
            "Works on macOS Headend. Produces identical output to build_os_bundle.py."
        )
    )
    parser.add_argument("--output", required=True, help="Output bundle directory")
    parser.add_argument("--device-id", required=True, help="Target device ID")
    parser.add_argument(
        "--catalog",
        help="Headend-generated update catalog / OS update plan JSON",
    )
    parser.add_argument(
        "--category",
        choices=["os_security", "os_updates"],
        help="Only include packages from this category",
    )
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        metavar="name=version",
        help="Explicit package spec. May be repeated.",
    )
    parser.add_argument(
        "--suite",
        default="noble",
        help="Ubuntu suite (default: noble for Ubuntu 24.04)",
    )
    parser.add_argument(
        "--architecture",
        default="arm64",
        help="Target architecture (default: arm64)",
    )
    parser.add_argument("--target-os", default="debian/orangepi")
    parser.add_argument("--source-ref", default="ubuntu-http")
    parser.add_argument("--force", action="store_true", help="Replace output dir if it exists")
    parser.add_argument("--dry-run", action="store_true", help="Resolve packages but do not download")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Collect requested packages
    packages: list[dict[str, Any]] = []
    if args.catalog:
        packages.extend(parse_catalog(Path(args.catalog), category=args.category))
    for spec in args.package:
        packages.append(parse_package_spec(spec))
    if not packages:
        parser.error("No packages supplied. Use --catalog and/or --package name=version")

    output = Path(args.output).expanduser().resolve()
    packages_dir = output / "packages"

    if output.exists():
        if not args.force:
            raise SystemExit(f"{output} already exists; use --force to replace it")
        shutil.rmtree(output)
    packages_dir.mkdir(parents=True)

    # Fetch package index
    print(f"Fetching Ubuntu {args.suite} {args.architecture} package index…", file=sys.stderr)
    index = fetch_package_index(args.suite, args.architecture, verbose=args.verbose)
    print(f"  {len(index)} packages indexed", file=sys.stderr)

    mirror = _mirror(args.architecture)
    package_file_entries: list[dict[str, Any]] = []
    not_found: list[str] = []

    for pkg in packages:
        name = pkg["name"]
        wanted_version = pkg["available_version"]
        entry = index.get(name)

        if not entry:
            print(f"  WARNING: {name} not found in index", file=sys.stderr)
            not_found.append(name)
            continue

        index_version = entry.get("Version", "")
        if index_version != wanted_version:
            print(
                f"  WARNING: {name} wanted {wanted_version}, "
                f"index has {index_version} — using index version",
                file=sys.stderr,
            )

        if args.dry_run:
            print(f"  dry-run: would download {name}={index_version}", file=sys.stderr)
            package_file_entries.append({
                "path": f"packages/{name}_{index_version}_{args.architecture}.deb (dry-run)",
                "filename": f"{name}_{index_version}_{args.architecture}.deb",
                "size_bytes": int(entry.get("Size", 0)),
                "sha256": entry.get("SHA256", ""),
                "name": name,
                "version": index_version,
                "architecture": entry.get("Architecture"),
            })
        else:
            try:
                deb_path = download_deb(entry, packages_dir, mirror, verbose=args.verbose)
                package_file_entries.append(deb_metadata_from_index(entry, deb_path))
                print(f"  ✓ {name}={index_version}", file=sys.stderr)
            except Exception as exc:
                print(f"  ERROR downloading {name}: {exc}", file=sys.stderr)
                not_found.append(name)

    if not_found:
        print(f"\nWARNING: {len(not_found)} package(s) could not be resolved:", file=sys.stderr)
        for n in not_found:
            print(f"  - {n}", file=sys.stderr)

    if not args.dry_run and not package_file_entries:
        raise SystemExit("No .deb files downloaded — aborting bundle creation")

    # Write bundle files
    package_manifest = {
        "schema": "timelapse.os_package_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_id": args.device_id,
        "target_os": args.target_os,
        "architecture": args.architecture,
        "suite": args.suite,
        "source_ref": args.source_ref,
        "mirror": mirror,
        "packages_requested": packages,
        "package_files": package_file_entries,
        "install_model": "offline dpkg; apt-get --no-download -f install only",
        "fetch_tool": "fetch_os_bundle.py",
    }
    write_json(output / "package-manifest.json", package_manifest)

    install_sh = output / "install-offline.sh"
    install_sh.write_text(install_script())
    install_sh.chmod(0o755)

    verify_sh = output / "verify-installed.sh"
    verify_sh.write_text(verify_script(packages))
    verify_sh.chmod(0o755)

    write_json(output / "bundle-summary.json", bundle_summary(output))

    result = {
        "ok": True,
        "bundle": str(output),
        "suite": args.suite,
        "architecture": args.architecture,
        "packages_requested": len(packages),
        "deb_files": len(package_file_entries),
        "not_found": not_found,
        "next": (
            "Copy bundle folder to Headend and register it: "
            "POST /api/updates/artifacts/catalog-os-bundle"
        ),
    }
    print(json.dumps(result, indent=2))
    return 0 if not not_found else 1


if __name__ == "__main__":
    raise SystemExit(main())
