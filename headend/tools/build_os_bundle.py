#!/usr/bin/env python3
"""
Build a TimeLapse Pro offline OS update bundle on a lab Debian/OrangePi host.

The output folder is copied to Headend and catalogued through
POST /api/updates/artifacts/catalog-os-bundle. Production Edge nodes then pull
only Headend-signed files and install without direct Internet access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an offline OS bundle from a Headend-generated catalog/plan"
    )
    parser.add_argument("--output", required=True, help="Output bundle directory")
    parser.add_argument("--device-id", required=True, help="Target/lab device id")
    parser.add_argument(
        "--catalog",
        help="Headend-generated update catalog, OS update plan or bundle request JSON",
    )
    parser.add_argument(
        "--category",
        choices=["os_security", "os_updates"],
        help="Only include packages from this OS update category when the catalog contains multiple decisions.",
    )
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        help="Package spec name=version. May be repeated. Used in addition to --catalog.",
    )
    parser.add_argument("--architecture", default=None, help="Expected dpkg architecture, e.g. arm64")
    parser.add_argument("--target-os", default="debian/orangepi")
    parser.add_argument("--source-ref", default="lab-apt")
    parser.add_argument("--dry-run", action="store_true", help="Do not run apt-get download")
    parser.add_argument(
        "--include-dependencies",
        action="store_true",
        help="Use apt-get install --download-only so the bundle includes dependency closure",
    )
    parser.add_argument("--force", action="store_true", help="Replace output directory if it exists")
    args = parser.parse_args()

    packages = []
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

    apt_get = shutil.which("apt-get")
    if not apt_get and not args.dry_run:
        raise SystemExit("apt-get not found. Build OS bundles on a Debian/OrangePi lab host.")

    for package in packages:
        package["download_spec"] = f"{package['name']}={package['available_version']}"

    if args.dry_run:
        pass
    elif args.include_dependencies:
        run(
            [
                apt_get,
                "-o",
                f"Dir::Cache::archives={packages_dir}",
                "-o",
                f"Dir::Cache::archives::partial={packages_dir / 'partial'}",
                "install",
                "--download-only",
                "--reinstall",
                "-y",
                *[package["download_spec"] for package in packages],
            ]
        )
    else:
        for package in packages:
            run([apt_get, "download", package["download_spec"]], cwd=packages_dir)

    package_files = sorted(packages_dir.glob("*.deb"))
    if not args.dry_run and not package_files:
        raise SystemExit("apt-get completed but no .deb files were downloaded")

    expected_arch = args.architecture or dpkg_architecture()
    package_file_entries = [deb_metadata(path, expected_arch) for path in package_files]
    package_manifest = {
        "schema": "timelapse.os_package_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_id": args.device_id,
        "target_os": args.target_os,
        "architecture": expected_arch,
        "source_ref": args.source_ref,
        "packages_requested": packages,
        "package_files": package_file_entries,
        "install_model": "offline dpkg; apt-get --no-download fix install only",
    }
    write_json(output / "package-manifest.json", package_manifest)
    write_text(output / "install-offline.sh", install_script())
    write_text(output / "verify-installed.sh", verify_script(packages))
    os.chmod(output / "install-offline.sh", 0o755)
    os.chmod(output / "verify-installed.sh", 0o755)
    write_json(output / "bundle-summary.json", bundle_summary(output))

    # P2-08 (2026-07-07): Generate SBOM for OS bundle
    bundle_id = hashlib.sha256(json.dumps(package_manifest, sort_keys=True).encode()).hexdigest()[:16]
    sbom = generate_sbom(packages_dir, bundle_id, args.device_id, args.target_os)
    write_json(output / "sbom.json", sbom)

    print(json.dumps({
        "ok": True,
        "bundle": str(output),
        "packages_requested": len(packages),
        "deb_files": len(package_file_entries),
        "sbom_generated": True,
        "next": "Copy folder to Headend and register it in Updates > OS bundle",
    }, indent=2))
    return 0


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
    seen = set()
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


def run(argv: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(argv, text=True, capture_output=True, timeout=1800, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed rc={result.returncode}: {' '.join(argv)}\n"
            f"{(result.stdout + result.stderr)[-2000:]}"
        )


def dpkg_architecture() -> str:
    dpkg = shutil.which("dpkg")
    if not dpkg:
        return "unknown"
    result = subprocess.run([dpkg, "--print-architecture"], text=True, capture_output=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def deb_metadata(path: Path, expected_arch: str) -> dict[str, Any]:
    sha = sha256_file(path)
    metadata = {
        "path": f"packages/{path.name}",
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha,
    }
    dpkg_deb = shutil.which("dpkg-deb")
    if dpkg_deb:
        result = subprocess.run(
            [dpkg_deb, "-f", str(path), "Package", "Version", "Architecture"],
            text=True,
            capture_output=True,
            timeout=20,
        )
        if result.returncode == 0:
            lines = [line.strip().split(":", 1)[-1].strip() for line in result.stdout.splitlines()]
            if len(lines) >= 3:
                metadata.update({"name": lines[0], "version": lines[1], "architecture": lines[2]})
                if expected_arch not in {"unknown", lines[2], "all"} and lines[2] != "all":
                    raise SystemExit(f"{path.name} architecture {lines[2]} does not match {expected_arch}")
    return metadata


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def write_text(path: Path, content: str) -> None:
    path.write_text(content)


def install_script() -> str:
    return """#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
dpkg -i packages/*.deb || apt-get --no-download -f install -y
./verify-installed.sh
"""


def verify_script(packages: list[dict[str, Any]]) -> str:
    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
    ]
    for package in packages:
        name = shell_quote(package["name"])
        version = shell_quote(package["available_version"])
        lines.extend([
            f"actual=$(dpkg-query -W -f='${{Version}}' {name})",
            f"test \"$actual\" = {version}",
        ])
    return "\n".join(lines) + "\n"


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def bundle_summary(root: Path) -> dict[str, Any]:
    files = []
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
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


def generate_sbom(packages_dir: Path, bundle_id: str, device_id: str, target_os: str) -> dict[str, Any]:
    """Generate CycloneDX 1.5 SBOM for OS bundle packages.

    P2-08 (2026-07-07): SBOM auto-generering for OS bundles.
    Extracts package metadata from .deb files and creates a standards-compliant SBOM.
    """
    deb_files = sorted(packages_dir.glob("*.deb"))
    components = []

    for deb_path in deb_files:
        metadata = deb_metadata(deb_path, expected_arch="unknown")
        component = {
            "type": "library",
            "name": metadata.get("name", deb_path.stem),
            "version": metadata.get("version", "unknown"),
            "purl": f"pkg:deb/debian/{metadata.get('name', deb_path.stem)}@{metadata.get('version', 'unknown')}?arch={metadata.get('architecture', 'unknown')}",
            "properties": [
                {"name": "timelapse:sha256", "value": metadata.get("sha256", "")},
                {"name": "timelapse:size_bytes", "value": str(metadata.get("size_bytes", 0))},
                {"name": "timelapse:filename", "value": metadata.get("filename", deb_path.name)},
            ],
        }
        components.append(component)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:timelapse-os-bundle-{bundle_id}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": "operating-system",
                "name": target_os,
                "version": "offline-bundle",
            },
            "properties": [
                {"name": "timelapse:device_id", "value": device_id},
                {"name": "timelapse:bundle_id", "value": bundle_id},
                {"name": "timelapse:packages_count", "value": str(len(components))},
            ],
        },
        "components": components,
    }


if __name__ == "__main__":
    raise SystemExit(main())
