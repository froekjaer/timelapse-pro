"""
TimeLapse Pro — Edge Disk Image Builder (multi-hardware)
=========================================================
Bygger et flashbart edge-image til et givet hardware-target.

Understøttede targets:
  orangepi4pro      — OrangePi 4 Pro (RK3399, arm64)
  orangepi-pc-plus  — OrangePi PC Plus (H3, armhf/32-bit)
  rpi4              — Raspberry Pi 4 (BCM2711, arm64)
  rpi5              — Raspberry Pi 5 (BCM2712, arm64)
  jetson-orin-nano  — Se install_timelapse_edge.sh i stedet

Output:
  timelapse-edge-{target}-{version}.rootfs.tar.gz  — platform rootfs
  timelapse-edge-{target}-{version}.manifest.json  — GPG-signeret manifest + SBOM

Brug (fra Python):
  from headend.tools.build_edge_disk_image import build_edge_image
  result = build_edge_image(
      target="rpi4",
      headend_url="https://timelapse.froekjaer.dk/api",
      gpg_key_id="EE347E3F8E89F2FFD5EC4A36F8DEEDDDC2A03552",
      progress_cb=print,
  )

Brug (CLI):
  python build_edge_disk_image.py --target rpi4
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

import yaml


# ── Target-definition loader ──────────────────────────────────────────────────

def _load_target(target_id: str, repo_root: Path) -> dict:
    """Indlæs hardware/target.yaml for det givne target."""
    target_path = repo_root / "headend" / "tools" / "hardware" / target_id / "target.yaml"
    if not target_path.exists():
        available = [
            p.parent.name
            for p in (repo_root / "headend" / "tools" / "hardware").glob("*/target.yaml")
        ]
        raise FileNotFoundError(
            f"Intet target '{target_id}' — tilgængelige: {sorted(available)}"
        )
    return yaml.safe_load(target_path.read_text()) or {}


def _list_targets(repo_root: Path) -> list[str]:
    hw_dir = repo_root / "headend" / "tools" / "hardware"
    return sorted(p.parent.name for p in hw_dir.glob("*/target.yaml"))


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _find_docker() -> str:
    """Returner fuld sti til docker-binæren.

    launchd-services kører med minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin).
    Docker Desktop installerer docker i /usr/local/bin — ikke i standard PATH.
    Vi søger kendte steder, så `docker buildx` virker uanset om processen er
    startet via launchd, systemd eller fra terminalen.
    """
    # 1) Prøv shutil.which (respekterer os.environ["PATH"])
    found = shutil.which("docker")
    if found:
        return found
    # 2) Kendte faste steder (Docker Desktop på macOS / Linux)
    for candidate in (
        "/usr/local/bin/docker",      # Docker Desktop macOS / Homebrew
        "/opt/homebrew/bin/docker",   # Homebrew Apple-Silicon
        "/usr/bin/docker",            # Docker via apt/rpm
        "/snap/bin/docker",           # Snap (Ubuntu)
    ):
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        "docker ikke fundet. Tilføj Docker Desktop til PATH, eller installer Docker."
    )


def _docker_build_cmd(docker_bin: str, progress: Callable[[str], None]) -> list[str]:
    """Returner [docker, buildx, build] hvis buildx er tilgængeligt,
    ellers [docker, build] med DOCKER_BUILDKIT-env (sættes i _run_docker_build).

    Grunden til at vi tjekker: launchd kan have en ældre docker-wrapper i PATH
    der ikke kender til buildx-subcommanden.
    """
    try:
        r = subprocess.run(
            [docker_bin, "buildx", "version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            progress(f"   docker buildx tilgængeligt: {r.stdout.strip().splitlines()[0]}")
            return [docker_bin, "buildx", "build"]
    except Exception as exc:
        progress(f"   ⚠️  buildx check fejlede ({exc}) — falder tilbage til BuildKit build")
    progress("   Bruger 'docker build' med DOCKER_BUILDKIT=1 (buildx ikke tilgængeligt)")
    return [docker_bin, "build"]


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


def _sign_manifest(
    manifest_json: str,
    gpg_key_id: str | None,
    progress: Callable[[str], None],
) -> tuple[str, str]:
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


# ── Dockerfile selection ──────────────────────────────────────────────────────

def _get_dockerfile(target: dict, repo_root: Path) -> Path:
    """Returner Dockerfile til dette target (arm64 eller armhf variant)."""
    arch = target.get("arch", "arm64")
    # armhf-specifik Dockerfile
    if arch == "armhf":
        armhf_df = repo_root / "headend" / "tools" / "Dockerfile.edge.armhf"
        if armhf_df.exists():
            return armhf_df
        # Fald tilbage til standard Dockerfile og ret base-image on-the-fly
    return repo_root / "headend" / "tools" / "Dockerfile.edge"


def _dockerfile_for_target(target: dict, repo_root: Path, progress: Callable[[str], None]) -> Path:
    """
    Returner (evt. dynamisk genereret) Dockerfile korrekt til target.
    For armhf genereres en variant med arm32v7/ubuntu:22.04 som base.
    """
    arch = target.get("arch", "arm64")
    std_df = repo_root / "headend" / "tools" / "Dockerfile.edge"

    if arch != "armhf":
        return std_df

    # Generer armhf-variant med arm32v7 base
    armhf_df = repo_root / "headend" / "tools" / "Dockerfile.edge.armhf"
    if not armhf_df.exists():
        progress("📄 Genererer Dockerfile.edge.armhf (arm32v7 base)...")
        content = std_df.read_text()
        content = content.replace(
            "FROM arm64v8/ubuntu:22.04",
            "FROM arm32v7/ubuntu:22.04",
        )
        armhf_df.write_text(content)
        progress(f"✅ Dockerfile.edge.armhf genereret")
    return armhf_df


# ── Build pipeline ────────────────────────────────────────────────────────────

def build_edge_image(
    target: str = "orangepi4pro",
    headend_url: str = "https://timelapse.froekjaer.dk/api",
    gpg_key_id: str | None = None,
    progress_cb: Callable[[str], None] = print,
    repo_root: str | None = None,
    output_dir: str | None = None,
) -> dict:
    """
    Byg edge rootfs-image til et specifikt hardware-target.

    Args:
        target:      Hardware target ID (se hardware/ directory)
        headend_url: URL til headend API
        gpg_key_id:  GPG-nøgle til signering (None = hash-binding)
        progress_cb: Callback for build-output (stream til UI/log)
        repo_root:   Sti til git-repo root (None = auto-detect)
        output_dir:  Output-mappe (None = tmp)

    Returnerer dict med artifact_id, paths, sha256, manifest, SBOM etc.
    """
    root = Path(repo_root or _find_repo_root())
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix=f"timelapse-edge-{target}-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Load target definition ──────────────────────────────────────────────
    tgt = _load_target(target, root)

    # Jetson: ikke et image, brug install-script
    if tgt.get("base_image", {}).get("type") == "install_script":
        raise RuntimeError(
            f"Target '{target}' understøttes ikke af build_edge_image().\n"
            f"Brug i stedet: headend/tools/hardware/{target}/install_timelapse_edge.sh\n"
            f"Installer på et eksisterende JetPack-system."
        )

    arch          = tgt.get("arch", "arm64")
    docker_platform = tgt.get("docker_platform", "linux/arm64")
    display_name  = tgt.get("display_name", target)

    timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    artifact_id = f"TL-EDGE-IMG-{target.upper()}-{timestamp}"
    image_tag   = f"timelapse-edge:{target}-{timestamp}"
    rootfs_name = f"timelapse-edge-{target}-{timestamp}.rootfs.tar.gz"
    rootfs_path = out_dir / rootfs_name

    # ── Git version ────────────────────────────────────────────────────────
    try:
        version = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception:
        version = "unknown"

    progress_cb(f"🔨 Starter Edge image build [{artifact_id}]")
    progress_cb(f"   Target:   {display_name} ({arch})")
    progress_cb(f"   Platform: {docker_platform}")
    progress_cb(f"   Repo:     {root}")
    progress_cb(f"   Version:  {version}")
    progress_cb(f"   Headend:  {headend_url}")
    progress_cb(f"   Output:   {rootfs_path}")

    # ── Step 1: Docker build ───────────────────────────────────────────────
    progress_cb(f"\n📦 Step 1/4: Docker image build ({docker_platform})...")
    dockerfile = _dockerfile_for_target(tgt, root, progress_cb)
    if not dockerfile.exists():
        raise FileNotFoundError(f"Dockerfile ikke fundet: {dockerfile}")

    docker_bin = _find_docker()
    progress_cb(f"   Docker:     {docker_bin}")
    progress_cb(f"   Dockerfile: {dockerfile.name}")

    build_cmd = _docker_build_cmd(docker_bin, progress_cb)
    build_env = {**os.environ, "DOCKER_BUILDKIT": "1"}

    _run(
        build_cmd + [
            "--platform", docker_platform,
            "--file", str(dockerfile),
            "--build-arg", f"HEADEND_URL={headend_url}",
            "--build-arg", f"TIMELAPSE_VERSION={version}",
            "--tag", image_tag,
            "--load",
            str(root),
        ],
        progress=progress_cb,
        env=build_env,
    )
    progress_cb(f"✅ Docker image bygget: {image_tag}")

    # ── Step 2: Export rootfs ──────────────────────────────────────────────
    progress_cb(f"\n📤 Step 2/4: Eksporterer rootfs tarball...")
    container_id = subprocess.check_output(
        [docker_bin, "create", "--platform", docker_platform, image_tag],
        text=True,
    ).strip()
    progress_cb(f"   Container: {container_id[:12]}")

    try:
        export_proc = subprocess.Popen(
            [docker_bin, "export", container_id],
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
        subprocess.run([docker_bin, "rm", container_id], capture_output=True)

    size_mb = rootfs_path.stat().st_size // (1024 * 1024)
    progress_cb(f"✅ Rootfs exporteret: {rootfs_name} ({size_mb} MB)")

    # ── Step 3: SBOM fra image ─────────────────────────────────────────────
    progress_cb(f"\n📋 Step 3/4: Genererer SBOM (pakkeliste fra image)...")
    sbom_packages: list[dict] = []
    try:
        dpkg_out = subprocess.check_output(
            [docker_bin, "run", "--rm", "--platform", docker_platform, image_tag,
             "dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Architecture}\\n"],
            text=True, timeout=60,
        )
        for line in dpkg_out.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                sbom_packages.append({
                    "name":    parts[0],
                    "version": parts[1],
                    "arch":    parts[2] if len(parts) > 2 else arch,
                })
        progress_cb(f"   {len(sbom_packages)} OS-pakker i SBOM")
    except Exception as exc:
        progress_cb(f"   ⚠️  SBOM dpkg fejlede: {exc}")

    pip_packages: list[dict] = []
    try:
        pip_out = subprocess.check_output(
            [docker_bin, "run", "--rm", "--platform", docker_platform, image_tag,
             "/opt/timelapse/venv/bin/pip", "list", "--format=json"],
            text=True, timeout=60,
        )
        pip_packages = json.loads(pip_out)
        progress_cb(f"   {len(pip_packages)} Python-pakker (venv) i SBOM")
    except Exception as exc:
        progress_cb(f"   ⚠️  SBOM pip fejlede: {exc}")

    # ── Step 4: Manifest + signatur ────────────────────────────────────────
    progress_cb(f"\n🔏 Step 4/4: Bygger og signerer manifest...")
    sha256 = _sha256_file(rootfs_path)
    progress_cb(f"   sha256: {sha256[:32]}…")

    manifest = {
        "schema":        "timelapse.edge_disk_image.v2",
        "artifact_id":   artifact_id,
        "artifact_type": "edge_disk_image",
        "target": {
            "id":             tgt.get("id", target),
            "display_name":   display_name,
            "arch":           arch,
            "docker_platform": docker_platform,
            "soc":            tgt.get("soc"),
            "hal_class":      tgt.get("hal_class"),
        },
        "image": {
            "filename":   rootfs_name,
            "format":     "rootfs_tarball_gzip",
            "platform":   docker_platform,
            "base":       tgt.get("docker_base"),
            "sha256":     sha256,
            "size_bytes": rootfs_path.stat().st_size,
        },
        "version":     version,
        "headend_url": headend_url,
        "hardening": {
            "root_locked":          True,
            "ssh_password_auth":    "disabled",
            "ssh_root_login":       "disabled",
            "service_user":         "timelapse",
        },
        "enrollment": {
            "method":   "zero_touch",
            "endpoint": f"{headend_url}/devices/enroll",
            "auth":     "short-lived bootstrap token",
        },
        "sbom": {
            "os_packages":   sbom_packages,
            "venv_packages": pip_packages,
        },
        "edge_constraints": {
            "edge_requires_direct_internet": False,
            "edge_requires_direct_github":   False,
            "headend_is_update_authority":   True,
        },
        "controls":   ["SABSA", "IEC62443", "ISO27000", "NIS2", "CRA"],
        "created_at": _now_utc(),
    }

    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    manifest_sha  = _sha256_text(manifest_json)
    signature, signed_by = _sign_manifest(manifest_json, gpg_key_id, progress_cb)

    manifest["signature"] = signature
    manifest["signed_by"] = signed_by
    manifest_json_signed = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)

    manifest_path = out_dir / f"{artifact_id}.manifest.json"
    manifest_path.write_text(manifest_json_signed, encoding="utf-8")
    progress_cb(f"✅ Manifest skrevet: {manifest_path.name}")

    # ── Cleanup Docker image ───────────────────────────────────────────────
    subprocess.run([docker_bin, "rmi", image_tag], capture_output=True)
    progress_cb(f"   Docker image {image_tag} fjernet (lokal kopi)")

    result = {
        "artifact_id":      artifact_id,
        "target":           target,
        "display_name":     display_name,
        "arch":             arch,
        "filename":         rootfs_name,
        "output_path":      str(rootfs_path),
        "sha256":           sha256,
        "size_bytes":       rootfs_path.stat().st_size,
        "manifest_path":    str(manifest_path),
        "manifest_sha256":  manifest_sha,
        "signature":        signature,
        "signed_by":        signed_by,
        "sbom_os_count":    len(sbom_packages),
        "sbom_venv_count":  len(pip_packages),
        "created_at":       manifest["created_at"],
    }
    progress_cb(f"\n🎉 Build færdig! {rootfs_name} ({size_mb} MB)")
    progress_cb(f"   Artifact ID: {artifact_id}")
    progress_cb(f"   Target:      {display_name}")
    progress_cb(f"   Signeret af: {signed_by}")
    return result


def _find_repo_root() -> Path:
    """Find git-repo root fra denne fils placering."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists():
            return parent
    return p.parent.parent.parent


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    root = _find_repo_root()
    targets = _list_targets(root)

    parser = argparse.ArgumentParser(
        description="Byg TimeLapse Pro Edge disk image"
    )
    parser.add_argument(
        "--target", required=True,
        choices=targets,
        help=f"Hardware target: {', '.join(targets)}",
    )
    parser.add_argument(
        "--headend-url",
        default="https://timelapse.froekjaer.dk/api",
    )
    parser.add_argument(
        "--gpg-key",
        default=os.environ.get("TIMELAPSE_GPG_KEY"),
        help="GPG nøgle ID til signering",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output mappe (default: /tmp/timelapse-edge-{target}-…)",
    )
    args = parser.parse_args()

    result = build_edge_image(
        target      = args.target,
        headend_url = args.headend_url,
        gpg_key_id  = args.gpg_key,
        progress_cb = print,
        output_dir  = args.output_dir,
    )
    print(json.dumps(result, indent=2))
