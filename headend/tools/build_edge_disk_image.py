"""
TimeLapse Pro — Edge Disk Image Builder
=======================================
Bruger Docker buildx (linux/arm64) til at bygge et signeret edge rootfs-image.

Output:
  timelapse-edge-rootfs-{timestamp}.tar.gz   — ARM64 rootfs tarball
  timelapse-edge-rootfs-{timestamp}.manifest.json — GPG-signeret manifest + SBOM

Bruges til:
  • Flash over base OrangePi-image på SD-kort/eMMC
  • Verificer integritet via manifest-signatur inden deployment

Kald fra Python:
  from headend.tools.build_edge_disk_image import build_edge_image
  result = build_edge_image(
      headend_url="https://timelapse.froekjaer.dk/api",
      gpg_key_id="EE347E3F8E89F2FFD5EC4A36F8DEEDDDC2A03552",
      progress_cb=print,
  )
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _run(cmd: list[str], progress: Callable[[str], None], **kwargs) -> subprocess.CompletedProcess:
    """Kør kommando og stream stdout/stderr til progress callback."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **kwargs,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            progress(line)
    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return subprocess.CompletedProcess(cmd, proc.returncode)


def _sign_manifest(manifest_json: str, gpg_key_id: str | None, progress: Callable[[str], None]) -> tuple[str, str]:
    """GPG-signér manifest, returner (signature_or_hash, signed_by)."""
    digest = _sha256_text(manifest_json)
    if not gpg_key_id:
        progress("ℹ️  Ingen GPG nøgle — bruger SHA-256 hash-binding")
        return f"sha256:{digest}", "system-hash"
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(manifest_json)
            tmp = f.name
        result = subprocess.run(
            ["gpg", "--batch", "--yes", "--armor",
             "--local-user", gpg_key_id,
             "--detach-sign", "--output", "-", tmp],
            capture_output=True, text=True, timeout=20,
        )
        os.unlink(tmp)
        if result.returncode == 0 and result.stdout.strip():
            progress(f"✅ GPG-signatur OK (nøgle {gpg_key_id[:16]}…)")
            return result.stdout.strip(), gpg_key_id
        progress(f"⚠️  GPG fejlede ({result.stderr[-200:]}), bruger hash-binding")
    except Exception as exc:
        progress(f"⚠️  GPG utilgængelig ({exc}), bruger hash-binding")
    return f"sha256:{digest}", "system-hash"


def build_edge_image(
    headend_url: str = "https://timelapse.froekjaer.dk/api",
    gpg_key_id: str | None = None,
    progress_cb: Callable[[str], None] = print,
    repo_root: str | None = None,
    output_dir: str | None = None,
) -> dict:
    """
    Byg arm64 edge rootfs-image via Docker buildx.

    Returnerer dict med:
      artifact_id, filename, output_path, sha256,
      manifest_path, manifest_sha256, signature, signed_by,
      sbom (package liste fra image), created_at
    """
    root = Path(repo_root or _find_repo_root())
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="timelapse-edge-build-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    artifact_id = f"TL-EDGE-IMG-{timestamp}"
    image_tag = f"timelapse-edge:{timestamp}"
    rootfs_name = f"timelapse-edge-rootfs-{timestamp}.tar.gz"
    rootfs_path = out_dir / rootfs_name

    # Get current git commit for version stamp
    try:
        version = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception:
        version = "unknown"

    progress_cb(f"🔨 Starter Edge image build [{artifact_id}]")
    progress_cb(f"   Repo: {root}")
    progress_cb(f"   Version: {version}")
    progress_cb(f"   Headend URL: {headend_url}")
    progress_cb(f"   Output: {rootfs_path}")

    # ── Step 1: Docker buildx ──────────────────────────────────────
    progress_cb("\n📦 Step 1/4: Docker buildx build (linux/arm64)...")
    dockerfile = root / "headend" / "tools" / "Dockerfile.edge"
    if not dockerfile.exists():
        raise FileNotFoundError(f"Dockerfile.edge ikke fundet: {dockerfile}")

    _run([
        "docker", "buildx", "build",
        "--platform", "linux/arm64",
        "--file", str(dockerfile),
        "--build-arg", f"HEADEND_URL={headend_url}",
        "--build-arg", f"TIMELAPSE_VERSION={version}",
        "--tag", image_tag,
        "--load",
        str(root),
    ], progress=progress_cb)
    progress_cb(f"✅ Docker image bygget: {image_tag}")

    # ── Step 2: Export rootfs ──────────────────────────────────────
    progress_cb("\n📤 Step 2/4: Eksporterer rootfs tarball...")
    container_id = subprocess.check_output(
        ["docker", "create", "--platform", "linux/arm64", image_tag],
        text=True,
    ).strip()
    progress_cb(f"   Container: {container_id[:12]}")

    try:
        export_proc = subprocess.Popen(
            ["docker", "export", container_id],
            stdout=subprocess.PIPE,
        )
        gz_proc = subprocess.Popen(
            ["gzip", "-9"],
            stdin=export_proc.stdout,
            stdout=open(rootfs_path, "wb"),
        )
        export_proc.stdout.close()  # type: ignore
        gz_proc.wait()
        export_proc.wait()
        if export_proc.returncode != 0 or gz_proc.returncode != 0:
            raise RuntimeError("docker export / gzip fejlede")
    finally:
        subprocess.run(["docker", "rm", container_id], capture_output=True)

    size_mb = rootfs_path.stat().st_size // (1024 * 1024)
    progress_cb(f"✅ Rootfs exporteret: {rootfs_name} ({size_mb} MB)")

    # ── Step 3: SBOM fra image ─────────────────────────────────────
    progress_cb("\n📋 Step 3/4: Genererer SBOM (pakkeliste fra image)...")
    sbom_packages: list[dict] = []
    try:
        dpkg_out = subprocess.check_output(
            ["docker", "run", "--rm", "--platform", "linux/arm64", image_tag,
             "dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Architecture}\\n"],
            text=True, timeout=30,
        )
        for line in dpkg_out.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                sbom_packages.append({"name": parts[0], "version": parts[1], "arch": parts[2] if len(parts) > 2 else "arm64"})
        progress_cb(f"   {len(sbom_packages)} OS-pakker i SBOM")
    except Exception as exc:
        progress_cb(f"   ⚠️  SBOM dpkg fejlede: {exc}")

    pip_packages: list[dict] = []
    try:
        pip_out = subprocess.check_output(
            ["docker", "run", "--rm", "--platform", "linux/arm64", image_tag,
             "/opt/timelapse-node-agent/venv/bin/pip", "list", "--format=json"],
            text=True, timeout=30,
        )
        pip_packages = json.loads(pip_out)
        progress_cb(f"   {len(pip_packages)} Python-pakker (venv) i SBOM")
    except Exception as exc:
        progress_cb(f"   ⚠️  SBOM pip fejlede: {exc}")

    # ── Step 4: Manifest + signatur ────────────────────────────────
    progress_cb("\n🔏 Step 4/4: Bygger og signerer manifest...")
    sha256 = _sha256_file(rootfs_path)
    progress_cb(f"   sha256: {sha256[:32]}…")

    manifest = {
        "schema": "timelapse.edge_disk_image.v1",
        "artifact_id": artifact_id,
        "artifact_type": "edge_disk_image",
        "image": {
            "filename": rootfs_name,
            "format": "rootfs_tarball_gzip",
            "platform": "linux/arm64",
            "base": "arm64v8/ubuntu:22.04",
            "sha256": sha256,
            "size_bytes": rootfs_path.stat().st_size,
        },
        "version": version,
        "headend_url": headend_url,
        "hardening": {
            "root_locked": True,
            "ssh_password_auth": "disabled",
            "ssh_root_login": "disabled",
            "service_user": "timelapse",
        },
        "call_home": {
            "endpoint": f"{headend_url}/bootstrap",
            "auth": "short-lived bootstrap token",
        },
        "sbom": {
            "os_packages": sbom_packages,
            "venv_packages": pip_packages,
        },
        "edge_constraints": {
            "edge_requires_direct_internet": False,
            "edge_requires_direct_github": False,
            "headend_is_update_authority": True,
        },
        "controls": ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        "created_at": _now_utc(),
    }

    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    manifest_sha = _sha256_text(manifest_json)
    signature, signed_by = _sign_manifest(manifest_json, gpg_key_id, progress_cb)

    manifest["signature"] = signature
    manifest["signed_by"] = signed_by
    manifest_json_signed = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)

    manifest_path = out_dir / f"{artifact_id}.manifest.json"
    manifest_path.write_text(manifest_json_signed, encoding="utf-8")
    progress_cb(f"✅ Manifest skrevet: {manifest_path.name}")

    # Cleanup Docker image
    subprocess.run(["docker", "rmi", image_tag], capture_output=True)
    progress_cb(f"   Docker image {image_tag} fjernet (lokal kopi)")

    result = {
        "artifact_id": artifact_id,
        "filename": rootfs_name,
        "output_path": str(rootfs_path),
        "sha256": sha256,
        "size_bytes": rootfs_path.stat().st_size,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "signature": signature,
        "signed_by": signed_by,
        "sbom_os_count": len(sbom_packages),
        "sbom_venv_count": len(pip_packages),
        "created_at": manifest["created_at"],
    }
    progress_cb(f"\n🎉 Build færdig! {rootfs_name} ({rootfs_path.stat().st_size // (1024*1024)} MB)")
    progress_cb(f"   Artifact ID: {artifact_id}")
    progress_cb(f"   Signeret af: {signed_by}")
    return result


def _find_repo_root() -> Path:
    """Find git-repo root fra denne fils placering."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists():
            return parent
    return p.parent.parent.parent
