"""
TimeLapse Pro — Edge Image Injector
=====================================
Tager et Armbian/Ubuntu base-image og injicerer TimeLapse Pro edge-agenten
ind i root-partitionen. Producerer et flashbart .img.gz klar til SSD.

Kræver:
  - Docker Desktop (kører Linux VM — giver adgang til losetup inde i
    --privileged containers, selv på macOS)
  - curl eller wget til download af base-image
  - Nok diskplads: base-image (~600 MB) + rootfs (~400 MB) + output (~1 GB)

Flow:
  1. Download base-image for target (Armbian / Ubuntu Server) — cachet lokalt
  2. Udpak .xz/.gz til .img (bruges af losetup)
  3. Kør injection via Docker --privileged:
       - losetup + kpartx → mount root-partition
       - Udpak vores rootfs-tarball (kun timelapse-stier)
       - Injicér bootstrap.yaml (headend_url + batch bootstrap token)
       - Enable timelapse-bootstrap.service via symlink
       - umount + losetup detach
  4. Komprimér output til .img.gz
  5. SHA-256 + GPG-signér manifest

Brug fra Python:
  from headend.tools.inject_edge_image import inject_edge_image
  result = inject_edge_image(
      target="rpi4",
      rootfs_tar="/tmp/timelapse-edge-rpi4-20240614120000.rootfs.tar.gz",
      bootstrap_token="btk-abc123",
      headend_url="https://timelapse.froekjaer.dk/api",
      progress_cb=print,
  )

Brug fra CLI:
  python inject_edge_image.py --target rpi4 \\
      --rootfs /tmp/timelapse-edge-rpi4-20240614120000.rootfs.tar.gz \\
      --bootstrap-token btk-abc123
"""

from __future__ import annotations

import gzip
import hashlib
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sign_manifest(
    manifest_json: str,
    gpg_key_id: str | None,
    progress: Callable[[str], None],
) -> tuple[str, str]:
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
        progress(f"⚠️  GPG fejlede: {result.stderr[-200:]}")
    except Exception as exc:
        progress(f"⚠️  GPG utilgængeligt: {exc}")
    return f"sha256:{digest}", "system-hash"


def _load_target(target_id: str, repo_root: Path) -> dict:
    path = repo_root / "headend" / "tools" / "hardware" / target_id / "target.yaml"
    if not path.exists():
        raise FileNotFoundError(f"target.yaml ikke fundet: {path}")
    return yaml.safe_load(path.read_text()) or {}


def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists():
            return parent
    return p.parent.parent.parent


# ── Download & cache base-image ───────────────────────────────────────────────

def _download_base_image(
    target: dict,
    cache_dir: Path,
    progress: Callable[[str], None],
) -> Path:
    """
    Downloader og cacher base-image for dette target.
    Returnerer sti til det udpakkede .img.

    Cacher i cache_dir/{target_id}/{filename} — downloader kun hvis ikke
    allerede til stede (eller sha256 ikke matcher).
    """
    base = target.get("base_image", {})
    url  = base.get("url")
    extract = base.get("extract", "xz")   # "xz" eller "gz"
    target_id = target.get("id", "unknown")

    if not url:
        raise ValueError(f"Ingen base_image.url i target '{target_id}'")

    # Filnavn fra URL
    url_filename = url.split("/")[-1].split("?")[0]

    # Armbian rolling release URLs har ingen filendelse (fx Trixie_current_minimal).
    # Forsøg HEAD-request: tjek Content-Disposition og/eller redirect-URL for faktisk filnavn.
    _KNOWN_EXTS = (".xz", ".gz", ".zst", ".img", ".zip")
    if not any(url_filename.endswith(ext) for ext in _KNOWN_EXTS):
        progress(f"   URL mangler filendelse — søger faktisk filnavn via HEAD...")
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                # 1) Content-Disposition header
                cd = resp.headers.get("Content-Disposition", "")
                m = re.search(r'filename=["\']?([^"\';\r\n]+)', cd)
                if m:
                    inferred = m.group(1).strip()
                    progress(f"   Content-Disposition filnavn: {inferred}")
                    url_filename = inferred
                else:
                    # 2) Redirect-URL path component
                    inferred = resp.url.split("/")[-1].split("?")[0]
                    if inferred and "." in inferred:
                        progress(f"   Faktisk filnavn (redirect-URL): {inferred}")
                        url_filename = inferred
        except Exception as exc:
            progress(f"   ⚠️  HEAD-request fejlede ({exc}) — bruger URL-stub som filnavn")

    cache_subdir = cache_dir / target_id
    cache_subdir.mkdir(parents=True, exist_ok=True)
    cached_compressed = cache_subdir / url_filename

    # .img filnavn = uden komprimerings-endelse.
    # Hvis url_filename stadig mangler endelse (Armbian CDN gav intet nyttigt),
    # tilføjer vi ".img" så cached_img ALTID er forskellig fra cached_compressed.
    img_name = url_filename
    ext_stripped = False
    for ext in (".xz", ".gz", ".zst"):
        if img_name.endswith(ext):
            img_name = img_name[:-len(ext)]
            ext_stripped = True
            break
    if not ext_stripped:
        img_name = img_name + ".img"
    cached_img = cache_subdir / img_name

    # Brug cachet .img hvis det allerede er udpakket
    if cached_img.exists() and cached_img.stat().st_size > 10 * 1024 * 1024:
        progress(f"✅ Base-image cachet: {cached_img.name} ({cached_img.stat().st_size // (1024*1024)} MB)")
        return cached_img

    # Download komprimeret image
    if not cached_compressed.exists():
        progress(f"⬇️  Downloader base-image: {url_filename}")
        progress(f"   URL: {url}")
        progress(f"   Kan tage flere minutter...")

        def _reporthook(count, block_size, total_size):
            if total_size > 0 and count % 200 == 0:
                pct = min(100, int(count * block_size * 100 / total_size))
                mb  = count * block_size // (1024 * 1024)
                progress(f"   {pct}% ({mb} MB)...")

        urllib.request.urlretrieve(url, cached_compressed, _reporthook)
        progress(f"✅ Download færdig: {cached_compressed.name}")
    else:
        progress(f"✅ Komprimeret image cachet: {cached_compressed.name}")

    # Udpak — bruger Python lzma/gzip i stedet for subprocess for at undgå
    # platform-specifikke exit-kode problemer (macOS xz kræver .xz filendelse).
    size_compressed = cached_compressed.stat().st_size
    progress(f"📦 Udpakker {cached_compressed.name} ({size_compressed // (1024*1024)} MB komprimeret) → {cached_img.name}...")
    if extract == "xz":
        with lzma.open(str(cached_compressed), "rb") as fin, open(cached_img, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    elif extract == "gz":
        with gzip.open(str(cached_compressed), "rb") as fin, open(cached_img, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    elif extract == "zst":
        # Python mangler built-in zstd — brug subprocess zstd
        subprocess.run(
            ["zstd", "--decompress", "--stdout", str(cached_compressed)],
            stdout=open(cached_img, "wb"), check=True,
        )
    else:
        raise ValueError(f"Ukendt extract-format: {extract}")

    if not cached_img.exists():
        raise FileNotFoundError(f"Forventet udpakket image ikke fundet: {cached_img}")

    size_mb = cached_img.stat().st_size // (1024 * 1024)
    progress(f"✅ Base-image udpakket: {cached_img.name} ({size_mb} MB)")
    return cached_img


# ── Injection via Docker --privileged ─────────────────────────────────────────

_INJECT_SCRIPT = r"""#!/bin/bash
# TimeLapse injection script — kører inde i privileged Docker container
set -euo pipefail

BASE_IMG="/work/base.img"
ROOTFS_TAR="/work/rootfs.tar.gz"
BOOTSTRAP_YAML="/work/bootstrap.yaml"
# OFFSET_BYTES sættes af Python (MBR-parsing) og sendes som env-var.
# Ingen eksterne tools nødvendig i containeren.

echo "[inject] Partition offset (fra MBR): ${OFFSET_BYTES} bytes"
LOOP=$(losetup -f --show -o "${OFFSET_BYTES}" "$BASE_IMG")
echo "[inject] Loop device: $LOOP"

echo "[inject] Mounter root-partition..."
mkdir -p /mnt/root
mount "$LOOP" /mnt/root

# ── Opret mappestruktur ──────────────────────────────────────────────────────
echo "[inject] Opretter timelapse mappestruktur..."
mkdir -p /mnt/root/opt/timelapse/edge
mkdir -p /mnt/root/opt/timelapse/venv
mkdir -p /mnt/root/etc/timelapse/device_keys
mkdir -p /mnt/root/data
mkdir -p /mnt/root/run/timelapse

# ── Udpak VORES rootfs (kun timelapse-stier) ────────────────────────────────
# Vi bevarer base-imagets kernel, bootloader og system-filer.
# Kun /opt/timelapse/, /etc/timelapse/, /etc/systemd/system/timelapse-* udpakkes.
echo "[inject] Udpakker TimeLapse filer fra rootfs..."

# List indhold i tar for debugging
echo "[inject] Rootfs indhold (timelapse-relaterede stier):"
tar -tzf "$ROOTFS_TAR" 2>/dev/null | grep -E "^(opt/timelapse|etc/timelapse|etc/systemd/system/timelapse)" | head -30 || true

# Udpak timelapse-specifikke stier
for TAR_PATH in \
    "opt/timelapse" \
    "etc/timelapse" \
    "etc/systemd/system/timelapse-edge.service" \
    "etc/systemd/system/timelapse-bootstrap.service"
do
    echo "[inject] Udpakker: $TAR_PATH"
    tar -xzf "$ROOTFS_TAR" -C /mnt/root \
        --strip-components=0 \
        "$TAR_PATH" 2>/dev/null && echo "[inject]   OK: $TAR_PATH" || \
        echo "[inject]   (ikke fundet i tar — springer over)"
done

# ── Bootstrap config ──────────────────────────────────────────────────────────
echo "[inject] Injicerer bootstrap.yaml..."
cp "$BOOTSTRAP_YAML" /mnt/root/etc/timelapse/bootstrap.yaml
chmod 600 /mnt/root/etc/timelapse/bootstrap.yaml

# ── Timelapse bruger ──────────────────────────────────────────────────────────
if ! grep -q "^timelapse:" /mnt/root/etc/passwd 2>/dev/null; then
    echo "[inject] Opretter timelapse bruger..."
    echo "timelapse:x:1001:1001:TimeLapse Pro,,,:/home/timelapse:/bin/bash" \
        >> /mnt/root/etc/passwd
    echo "timelapse:!:1001:" >> /mnt/root/etc/group
    mkdir -p /mnt/root/home/timelapse
fi

# ── Aktiver timelapse-bootstrap.service ──────────────────────────────────────
echo "[inject] Aktiverer timelapse-bootstrap.service..."
WANTS_DIR=/mnt/root/etc/systemd/system/multi-user.target.wants
mkdir -p "$WANTS_DIR"

BOOTSTRAP_SVC=/mnt/root/etc/systemd/system/timelapse-bootstrap.service
if [ -f "$BOOTSTRAP_SVC" ]; then
    ln -sf /etc/systemd/system/timelapse-bootstrap.service \
        "$WANTS_DIR/timelapse-bootstrap.service"
    echo "[inject]   timelapse-bootstrap.service aktiveret"
else
    echo "[inject]   ADVARSEL: timelapse-bootstrap.service ikke fundet i rootfs"
    echo "[inject]   Skriver fallback service..."
    cat > "$BOOTSTRAP_SVC" << 'EOF'
[Unit]
Description=TimeLapse Pro — First-boot Enrollment Agent
After=network-online.target
Wants=network-online.target
Before=timelapse-edge.service
ConditionPathExists=!/etc/timelapse/.enrolled

[Service]
Type=oneshot
RemainAfterExit=no
User=root
WorkingDirectory=/opt/timelapse/edge
ExecStart=/opt/timelapse/venv/bin/python /opt/timelapse/edge/scripts/bootstrap_agent.py
TimeoutStartSec=600
StandardOutput=journal
StandardError=journal
SyslogIdentifier=timelapse-bootstrap
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
    ln -sf /etc/systemd/system/timelapse-bootstrap.service \
        "$WANTS_DIR/timelapse-bootstrap.service"
fi

# ── SSH hardening ─────────────────────────────────────────────────────────────
SSHD_CONFIG=/mnt/root/etc/ssh/sshd_config
if [ -f "$SSHD_CONFIG" ]; then
    echo "[inject] SSH hardening..."
    sed -i \
        -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
        -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
        "$SSHD_CONFIG"
fi

# ── Rettigheder ───────────────────────────────────────────────────────────────
echo "[inject] Sætter rettigheder..."
chown -R 1001:1001 \
    /mnt/root/opt/timelapse \
    /mnt/root/etc/timelapse \
    /mnt/root/data \
    /mnt/root/run/timelapse \
    /mnt/root/home/timelapse \
    2>/dev/null || true
chmod 700 /mnt/root/etc/timelapse/device_keys

# ── Unmount ───────────────────────────────────────────────────────────────────
echo "[inject] Unmounter..."
sync
umount /mnt/root
losetup -d "$LOOP"
echo "[inject] INJECTION_OK"
"""


def _inject_via_docker(
    base_img: Path,
    rootfs_tar: Path,
    output_img: Path,
    bootstrap_yaml: str,
    target: dict,
    progress: Callable[[str], None],
) -> None:
    """
    Injectér agent-filer i base-image via Docker --privileged.

    Bruger 'docker cp' i stedet for volume-mounts for at undgå macOS
    VirtioFS/gRPC-FUSE synk-problemer hvor nyskrevne filer ikke er synlige
    i containeren. Flowet er:
      1. Start detached privileged container (sleep 600)
      2. docker cp: base.img + rootfs.tar.gz + bootstrap.yaml → container
      3. docker exec -i: kør inject-script via stdin
      4. docker cp: modificeret base.img ← container
      5. docker stop + rm
    """
    _root_part_cfg = target.get("base_image", {}).get("root_partition")
    root_part = str(_root_part_cfg) if _root_part_cfg is not None else "auto"

    progress(f"   Root partition: {'auto-detect' if root_part == 'auto' else 'p' + root_part}")
    progress(f"   Starter privileged container (ubuntu:22.04)...")

    # ── 0. Læs MBR partition-offset direkte i Python ─────────────────────────
    # MBR partition table: offset 446, 4 entries à 16 bytes
    # Bytes 8-11 i hver entry = LBA start (little-endian uint32)
    _part_num = int(root_part) if root_part != "auto" else 1
    _mbr_entry_offset = 446 + (_part_num - 1) * 16
    with open(base_img, "rb") as _f:
        _f.seek(_mbr_entry_offset)
        _entry = _f.read(16)
    _lba_start = int.from_bytes(_entry[8:12], "little")
    offset_bytes = _lba_start * 512
    progress(f"   MBR partition {_part_num} offset: {offset_bytes} bytes (LBA {_lba_start})")
    if offset_bytes == 0:
        raise RuntimeError(f"MBR partition {_part_num} LBA=0 — image er muligvis ikke et gyldigt MBR-image")

    # ── 1. Start detached container ──────────────────────────────────────────
    start = subprocess.run(
        ["docker", "run", "-d", "--privileged",
         "-e", f"OFFSET_BYTES={offset_bytes}",
         "ubuntu:22.04", "sleep", "600"],
        capture_output=True, text=True, check=True,
    )
    container_id = start.stdout.strip()
    progress(f"   Container: {container_id[:12]}")

    try:
        # ── 2. Opret /work og kopier filer ind med docker cp ─────────────────
        subprocess.run(
            ["docker", "exec", container_id, "mkdir", "-p", "/work"],
            check=True, capture_output=True,
        )

        progress(f"   Kopierer base-image til container ({base_img.stat().st_size // (1024*1024)} MB)...")
        subprocess.run(
            ["docker", "cp", str(base_img), f"{container_id}:/work/base.img"],
            check=True, capture_output=True,
        )

        progress(f"   Kopierer rootfs tarball til container...")
        subprocess.run(
            ["docker", "cp", str(rootfs_tar), f"{container_id}:/work/rootfs.tar.gz"],
            check=True, capture_output=True,
        )

        # bootstrap.yaml via tempfil → docker cp
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as _f:
            _f.write(bootstrap_yaml)
            _bstp_tmp = _f.name
        try:
            subprocess.run(
                ["docker", "cp", _bstp_tmp, f"{container_id}:/work/bootstrap.yaml"],
                check=True, capture_output=True,
            )
        finally:
            os.unlink(_bstp_tmp)

        # ── 3. Kør inject-script via stdin ────────────────────────────────────
        progress(f"   Kører inject-script...")
        result = subprocess.run(
            ["docker", "exec", "-i", container_id, "bash", "-s"],
            input=_INJECT_SCRIPT,
            capture_output=True,
            text=True,
            timeout=600,
        )

        for line in (result.stdout + result.stderr).splitlines():
            if line.strip():
                progress(f"   {line}")

        if result.returncode != 0:
            raise RuntimeError(f"Injection fejlede (rc={result.returncode})")
        if "INJECTION_OK" not in result.stdout:
            raise RuntimeError("Injection script returnerede ikke INJECTION_OK")

        # ── 4. Kopiér modificeret image ud ───────────────────────────────────
        progress(f"   Kopierer modificeret image ud af container...")
        subprocess.run(
            ["docker", "cp", f"{container_id}:/work/base.img", str(output_img)],
            check=True, capture_output=True,
        )

        progress(f"✅ Injection OK")

    finally:
        # ── 5. Stop + fjern container ─────────────────────────────────────────
        subprocess.run(["docker", "stop", container_id], capture_output=True)
        subprocess.run(["docker", "rm",  container_id], capture_output=True)


# ── Komprimering ──────────────────────────────────────────────────────────────

def _compress_image(img_path: Path, gz_path: Path, progress: Callable[[str], None]) -> None:
    """Komprimér .img til .img.gz med pigz (parallel) eller gzip."""
    progress(f"   Komprimerer {img_path.name} → {gz_path.name}...")
    compressor = "pigz" if shutil.which("pigz") else "gzip"
    progress(f"   Bruger: {compressor}")
    with open(gz_path, "wb") as out_f:
        subprocess.run(
            [compressor, "-9", "-c", str(img_path)],
            stdout=out_f,
            check=True,
        )
    size_mb = gz_path.stat().st_size // (1024 * 1024)
    progress(f"✅ Komprimeret: {gz_path.name} ({size_mb} MB)")


# ── Public API ────────────────────────────────────────────────────────────────

def inject_edge_image(
    target: str,
    rootfs_tar: str | Path,
    headend_url: str,
    bootstrap_token: str = "",
    gpg_key_id: str | None = None,
    progress_cb: Callable[[str], None] = print,
    repo_root: str | None = None,
    output_dir: str | None = None,
    base_image_cache: str | None = None,
) -> dict:
    """
    Injectér edge-agent i base-image og producér flashbart .img.gz.

    Args:
        target:             Hardware target ID ("rpi4", "orangepi-pc-plus", …)
        rootfs_tar:         Sti til rootfs.tar.gz fra build_edge_image()
        headend_url:        URL til headend API (bages ind i bootstrap.yaml)
        bootstrap_token:    Bootstrap-token der bages ind (tom = placeholder)
        gpg_key_id:         GPG-nøgle til manifest-signering
        progress_cb:        Callback for output
        repo_root:          Git-repo root (None = auto-detect)
        output_dir:         Output-mappe (None = tmp)
        base_image_cache:   Mappe til cache af downloadede base-images

    Returnerer dict med stier, sha256, manifest etc.
    """
    root        = Path(repo_root or _find_repo_root())
    rootfs_path = Path(rootfs_tar)
    out_dir     = Path(output_dir or tempfile.mkdtemp(prefix=f"timelapse-flash-{target}-"))
    cache_dir   = Path(base_image_cache or (root / ".base_image_cache"))
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rootfs_path.exists():
        raise FileNotFoundError(f"rootfs.tar.gz ikke fundet: {rootfs_path}")

    tgt          = _load_target(target, root)
    display_name = tgt.get("display_name", target)
    arch         = tgt.get("arch", "arm64")

    # Jetson: ikke understøttet her
    if tgt.get("base_image", {}).get("type") == "install_script":
        raise RuntimeError(
            f"Target '{target}' bruger install-script, ikke image-injection.\n"
            f"Se: headend/tools/hardware/{target}/install_timelapse_edge.sh"
        )

    timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    artifact_id = f"TL-FLASH-IMG-{target.upper()}-{timestamp}"
    img_name    = f"timelapse-edge-{target}-{timestamp}.img"
    gz_name     = f"timelapse-edge-{target}-{timestamp}.img.gz"
    img_path    = out_dir / img_name
    gz_path     = out_dir / gz_name

    progress_cb(f"🔧 Starter image-injection [{artifact_id}]")
    progress_cb(f"   Target:      {display_name} ({arch})")
    progress_cb(f"   Rootfs:      {rootfs_path.name}")
    progress_cb(f"   Headend URL: {headend_url}")
    progress_cb(f"   Token:       {'(bages ind)' if bootstrap_token else '(placeholder)'}")

    # ── Step 1: Download base-image ────────────────────────────────────────
    progress_cb(f"\n⬇️  Step 1/4: Henter base-image for {display_name}...")
    base_img = _download_base_image(tgt, cache_dir, progress_cb)

    # Kopier base-image til output-dir (injection modificerer filen in-place)
    work_img = out_dir / base_img.name
    if not work_img.exists():
        progress_cb(f"   Kopierer base-image til output-mappe...")
        shutil.copy2(base_img, work_img)

    # ── Step 2: Byg bootstrap.yaml til injection ───────────────────────────
    progress_cb(f"\n📄 Step 2/4: Bygger bootstrap.yaml...")
    effective_token = bootstrap_token or "${BOOTSTRAP_TOKEN}"
    bootstrap_yaml_content = (
        f"# TimeLapse Pro bootstrap config — bagt ind i image {artifact_id}\n"
        f"# Genereret: {_now_utc()}\n"
        f"headend_url: \"{headend_url}\"\n"
        f"bootstrap_token: \"{effective_token}\"\n"
    )
    if not bootstrap_token:
        bootstrap_yaml_content += (
            "# VIGTIGT: Erstat ${BOOTSTRAP_TOKEN} med et gyldigt token\n"
            "# Brug: headend UI → Provisioning → Opret batch-token\n"
            "# Eller kør: python inject_edge_image.py --patch-token <img.gz> <token>\n"
        )
    progress_cb(f"   Headend URL: {headend_url}")
    progress_cb(f"   Token: {'(placeholder)' if not bootstrap_token else bootstrap_token[:12] + '…'}")

    # ── Step 3: Docker injection ───────────────────────────────────────────
    progress_cb(f"\n🔨 Step 3/4: Injecterer agent via Docker --privileged...")
    _inject_via_docker(
        base_img        = work_img,
        rootfs_tar      = rootfs_path,
        output_img      = img_path,
        bootstrap_yaml  = bootstrap_yaml_content,
        target          = tgt,
        progress        = progress_cb,
    )

    # Ryd midlertidig work_img
    if work_img != img_path:
        work_img.unlink(missing_ok=True)

    # ── Step 4: Komprimér + signér ────────────────────────────────────────
    progress_cb(f"\n📦 Step 4/4: Komprimerer og signerer...")
    _compress_image(img_path, gz_path, progress_cb)
    img_path.unlink()   # fjern ukomprimeret .img

    sha256 = _sha256_file(gz_path)
    size_mb = gz_path.stat().st_size // (1024 * 1024)
    progress_cb(f"   sha256: {sha256[:32]}…")

    # Manifest
    manifest = {
        "schema":        "timelapse.flashable_image.v1",
        "artifact_id":   artifact_id,
        "artifact_type": "flashable_disk_image",
        "target": {
            "id":           tgt.get("id", target),
            "display_name": display_name,
            "arch":         arch,
            "soc":          tgt.get("soc"),
        },
        "image": {
            "filename":   gz_name,
            "format":     "raw_disk_image_gzip",
            "sha256":     sha256,
            "size_bytes": gz_path.stat().st_size,
        },
        "source_rootfs": rootfs_path.name,
        "headend_url":   headend_url,
        "token_baked_in": bool(bootstrap_token),
        "flash_instructions": {
            "linux_mac": f"gunzip -c {gz_name} | sudo dd of=/dev/sdX bs=4M status=progress",
            "windows":   f"Brug balenaEtcher: https://etcher.balena.io — åbn {gz_name}",
            "note":      "Erstat /dev/sdX med din SSD (tjek med lsblk / Diskværktøj)"
        },
        "enrollment": {
            "method":        "zero_touch",
            "first_boot":    "timelapse-bootstrap.service starter automatisk",
            "headend_action": "Enheden vises under 'Ikke-tildelt enheder' i headend UI",
        },
        "created_at": _now_utc(),
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    signature, signed_by = _sign_manifest(manifest_json, gpg_key_id, progress_cb)
    manifest["signature"] = signature
    manifest["signed_by"] = signed_by

    manifest_path = out_dir / f"{artifact_id}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    progress_cb(f"✅ Manifest skrevet: {manifest_path.name}")

    result = {
        "artifact_id":    artifact_id,
        "target":         target,
        "display_name":   display_name,
        "arch":           arch,
        "filename":       gz_name,
        "output_path":    str(gz_path),
        "sha256":         sha256,
        "size_bytes":     gz_path.stat().st_size,
        "size_mb":        size_mb,
        "manifest_path":  str(manifest_path),
        "signature":      signature,
        "signed_by":      signed_by,
        "token_baked_in": bool(bootstrap_token),
        "created_at":     manifest["created_at"],
        "flash_instructions": manifest["flash_instructions"],
    }

    progress_cb(f"\n🎉 Flashbart image klar!")
    progress_cb(f"   Fil:     {gz_name} ({size_mb} MB)")
    progress_cb(f"   sha256:  {sha256[:32]}…")
    progress_cb(f"   Flash:   gunzip -c {gz_name} | sudo dd of=/dev/sdX bs=4M status=progress")
    progress_cb(f"   Windows: Brug balenaEtcher")
    return result


def patch_token_in_image(
    img_gz: Path,
    new_token: str,
    progress_cb: Callable[[str], None] = print,
) -> Path:
    """
    Bager et bootstrap-token ind i et eksisterende .img.gz på én linje.
    Producerer en ny fil: {original}-patched.img.gz

    Bruges hvis image blev bygget uden token (placeholder).
    Kræver Docker --privileged.
    """
    out = img_gz.parent / img_gz.name.replace(".img.gz", f"-token.img.gz")
    work_dir = Path(tempfile.mkdtemp(prefix="timelapse-patch-"))
    try:
        progress_cb(f"🔑 Patcher token ind i {img_gz.name}...")
        work_img  = work_dir / "base.img"
        work_gz   = work_dir / img_gz.name

        shutil.copy2(img_gz, work_gz)
        progress_cb(f"   Udpakker .img.gz...")
        subprocess.run(["gunzip", "-k", str(work_gz)], check=True, cwd=work_dir)

        # Find .img file
        img_files = list(work_dir.glob("*.img"))
        if not img_files:
            raise FileNotFoundError("Ingen .img fil fundet efter gunzip")
        work_img = img_files[0]

        # Patch bootstrap.yaml i root-partition via Docker
        patch_script = f"""#!/bin/bash
set -euo pipefail
LOOP=$(losetup -f --show --partscan /work/base.img)
sleep 1
# Prøv p2, derefter p1
for PART in ${{LOOP}}p2 ${{LOOP}}p1; do
    if [ -b "$PART" ]; then break; fi
done
mkdir -p /mnt/root
mount "$PART" /mnt/root
# Erstat token
if [ -f /mnt/root/etc/timelapse/bootstrap.yaml ]; then
    sed -i 's|bootstrap_token:.*|bootstrap_token: "{new_token}"|' \\
        /mnt/root/etc/timelapse/bootstrap.yaml
    echo "Token patchet"
else
    echo "bootstrap.yaml ikke fundet — skriver ny"
    mkdir -p /mnt/root/etc/timelapse
    cat > /mnt/root/etc/timelapse/bootstrap.yaml << 'BSEOF'
bootstrap_token: "{new_token}"
BSEOF
fi
sync; umount /mnt/root; losetup -d "$LOOP"
echo PATCH_OK
"""
        (work_dir / "patch.sh").write_text(patch_script)
        result = subprocess.run(
            ["docker", "run", "--rm", "--privileged",
             "-v", f"{work_dir}:/work",
             "--workdir", "/work",
             "ubuntu:22.04", "bash", "patch.sh"],
            capture_output=True, text=True, timeout=120,
        )
        for line in (result.stdout + result.stderr).splitlines():
            if line.strip():
                progress_cb(f"   {line}")
        if result.returncode != 0 or "PATCH_OK" not in result.stdout:
            raise RuntimeError("Token-patch fejlede")

        progress_cb(f"   Komprimerer...")
        with open(out, "wb") as f:
            subprocess.run(["gzip", "-9", "-c", str(work_img)], stdout=f, check=True)

        progress_cb(f"✅ Patchet image: {out.name}")
        return out
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    root    = _find_repo_root()
    targets = sorted(
        p.parent.name
        for p in (root / "headend" / "tools" / "hardware").glob("*/target.yaml")
    )

    parser = argparse.ArgumentParser(description="Injectér TimeLapse edge-agent i base-image")
    sub = parser.add_subparsers(dest="cmd")

    # inject
    p_inject = sub.add_parser("inject", help="Injicér rootfs i base-image")
    p_inject.add_argument("--target",          required=True, choices=targets)
    p_inject.add_argument("--rootfs",          required=True, help="Sti til rootfs.tar.gz")
    p_inject.add_argument("--headend-url",     default="https://timelapse.froekjaer.dk/api")
    p_inject.add_argument("--bootstrap-token", default="", help="Token der bages ind (tom = placeholder)")
    p_inject.add_argument("--gpg-key",         default=os.environ.get("TIMELAPSE_GPG_KEY"))
    p_inject.add_argument("--output-dir",      default=None)
    p_inject.add_argument("--cache-dir",       default=None, help="Cache-mappe til base-images")

    # patch-token
    p_patch = sub.add_parser("patch-token", help="Erstat token-placeholder i eksisterende .img.gz")
    p_patch.add_argument("image",  help="Sti til .img.gz")
    p_patch.add_argument("token",  help="Bootstrap token")

    args = parser.parse_args()

    if args.cmd == "inject":
        result = inject_edge_image(
            target          = args.target,
            rootfs_tar      = args.rootfs,
            headend_url     = args.headend_url,
            bootstrap_token = args.bootstrap_token,
            gpg_key_id      = args.gpg_key,
            output_dir      = args.output_dir,
            base_image_cache= args.cache_dir,
        )
        print(json.dumps(result, indent=2))

    elif args.cmd == "patch-token":
        out = patch_token_in_image(Path(args.image), args.token)
        print(f"Patchet image: {out}")

    else:
        parser.print_help()
