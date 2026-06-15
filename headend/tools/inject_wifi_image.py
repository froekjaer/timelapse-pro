"""
inject_wifi_image.py — Post-process WiFi-injektion i eksisterende .img.gz

Flowet:
  1. Dekomprimér .img.gz → temp .img
  2. Start privileged Docker-container
  3. docker cp: .img → container
  4. Læs MBR partition-offset (Python-side, ingen tools i container)
  5. docker exec: mount + skriv WiFi-config + unmount
  6. docker cp: modificeret .img ← container
  7. Komprimér → ny .img.gz (filnavn: originalname-wifi-YYYYMMDD.img.gz)
  8. Returnér sti til ny .img.gz

Understøtter:
  - wpa_supplicant  (Armbian/Debian)
  - netplan         (Ubuntu — RPi4, OrangePi 4 Pro)

Auto-detekterer metode fra target.yaml hvis target_id angives,
ellers bruges fallback-argument `wifi_method`.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


# ── Inject-script der kører inde i Docker-containeren ────────────────────────

_WIFI_INJECT_SCRIPT = r"""#!/bin/bash
set -euo pipefail

BASE_IMG="/work/base.img"

echo "[wifi-inject] Partition offset (fra MBR): ${OFFSET_BYTES} bytes"
LOOP=$(losetup -f --show -o "${OFFSET_BYTES}" "$BASE_IMG")
echo "[wifi-inject] Loop device: $LOOP"

echo "[wifi-inject] Mounter root-partition..."
mkdir -p /mnt/root
mount "$LOOP" /mnt/root

# ── WiFi konfiguration ───────────────────────────────────────────────────────
WIFI_COUNTRY="${WIFI_COUNTRY:-DK}"
echo "[wifi-inject] Konfigurerer WiFi (SSID: ${WIFI_SSID}, metode: ${WIFI_METHOD:-wpa_supplicant})..."

if [ "${WIFI_METHOD:-wpa_supplicant}" = "netplan" ]; then
    # Ubuntu/netplan metode
    mkdir -p /mnt/root/etc/netplan
    # Slet eventuel eksisterende WiFi-netplan config
    rm -f /mnt/root/etc/netplan/60-wifi.yaml /mnt/root/etc/netplan/50-cloud-init.yaml 2>/dev/null || true
    cat > /mnt/root/etc/netplan/60-wifi.yaml << NETPLAN_EOF
network:
  version: 2
  renderer: networkd
  wifis:
    wlan0:
      dhcp4: true
      dhcp6: false
      regulatory-domain: ${WIFI_COUNTRY}
      access-points:
        "${WIFI_SSID}":
          password: "${WIFI_PASSWORD}"
NETPLAN_EOF
    chmod 600 /mnt/root/etc/netplan/60-wifi.yaml
    echo "[wifi-inject]   WiFi netplan skrevet: /etc/netplan/60-wifi.yaml"

else
    # wpa_supplicant metode (Debian/Armbian)
    mkdir -p /mnt/root/etc/wpa_supplicant
    cat > /mnt/root/etc/wpa_supplicant/wpa_supplicant.conf << WPA_EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=${WIFI_COUNTRY}

network={
    ssid="${WIFI_SSID}"
    psk="${WIFI_PASSWORD}"
    key_mgmt=WPA-PSK
    scan_ssid=1
}
WPA_EOF
    chmod 600 /mnt/root/etc/wpa_supplicant/wpa_supplicant.conf
    echo "[wifi-inject]   wpa_supplicant.conf skrevet"

    # Aktivér wpa_supplicant service hvis systemd er tilgængeligt
    WANTS_DIR=/mnt/root/etc/systemd/system/multi-user.target.wants
    mkdir -p "$WANTS_DIR"
    if [ -f /mnt/root/lib/systemd/system/wpa_supplicant@.service ]; then
        ln -sf /lib/systemd/system/wpa_supplicant@.service \
            "$WANTS_DIR/wpa_supplicant@wlan0.service" 2>/dev/null || true
        echo "[wifi-inject]   wpa_supplicant@wlan0.service aktiveret"
    fi
fi

echo "[wifi-inject] Unmounter..."
sync
umount /mnt/root
losetup -d "$LOOP"
echo "[wifi-inject] WIFI_INJECT_OK"
"""


def _find_repo_root() -> Path:
    """Find git-repo root fra denne fils placering."""
    p = Path(__file__).resolve()
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("Kan ikke finde git-repo root")


def _load_target_yaml(target_id: str, repo_root: Path) -> dict:
    """Indlæs target.yaml for et givet target."""
    try:
        import yaml
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"], check=True)
        import yaml  # type: ignore

    yaml_path = repo_root / "headend" / "tools" / "hardware" / target_id / "target.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"target.yaml ikke fundet: {yaml_path}")
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_mbr_partition_offset(img_path: Path, partition_num: int) -> int:
    """Læs partition-offset fra MBR partition-tabel."""
    entry_offset = 446 + (partition_num - 1) * 16
    with open(img_path, "rb") as f:
        f.seek(entry_offset)
        entry = f.read(16)
    lba_start = int.from_bytes(entry[8:12], "little")
    offset_bytes = lba_start * 512
    if offset_bytes == 0:
        raise RuntimeError(f"MBR partition {partition_num} LBA=0 — ikke et gyldigt MBR-image")
    return offset_bytes


def inject_wifi_image(
    gz_path: str | Path,
    wifi_ssid: str,
    wifi_password: str,
    wifi_country: str = "DK",
    wifi_method: str = "auto",
    target_id: str | None = None,
    root_partition: int = 1,
    output_dir: str | Path | None = None,
    progress_cb: Callable[[str], None] = print,
    repo_root: str | Path | None = None,
) -> dict:
    """
    Injectér WiFi-konfiguration i et eksisterende flashbart .img.gz.

    Args:
        gz_path:        Sti til eksisterende .img.gz
        wifi_ssid:      WiFi SSID
        wifi_password:  WiFi adgangskode
        wifi_country:   Landekode (default: DK)
        wifi_method:    "wpa_supplicant" | "netplan" | "auto"
                        "auto" aflæser fra target.yaml hvis target_id angives
        target_id:      Hardware target ID til auto-detect af wifi_method
        root_partition: Root-partition nummer (default: 1)
        output_dir:     Output-mappe (None = samme som input)
        progress_cb:    Callback for statusbeskeder
        repo_root:      Git-repo root (None = auto-detect)

    Returnerer dict med:
        output_path, filename, sha256, size_bytes
    """
    gz_path = Path(gz_path)
    if not gz_path.exists():
        raise FileNotFoundError(f"Input .img.gz ikke fundet: {gz_path}")

    root = Path(repo_root or _find_repo_root())

    # Auto-detect wifi_method fra target.yaml
    effective_method = wifi_method
    effective_root_partition = root_partition
    if wifi_method == "auto" and target_id:
        try:
            tgt = _load_target_yaml(target_id, root)
            effective_method = tgt.get("wifi_method", "wpa_supplicant")
            cfg_partition = tgt.get("base_image", {}).get("root_partition", root_partition)
            effective_root_partition = int(cfg_partition) if cfg_partition is not None else root_partition
            progress_cb(f"   Target {target_id}: wifi_method={effective_method}, root_partition={effective_root_partition}")
        except Exception as e:
            progress_cb(f"   ⚠️  Kan ikke læse target.yaml ({e}) — bruger defaults")
            effective_method = "wpa_supplicant"
    elif wifi_method == "auto":
        effective_method = "wpa_supplicant"

    # Bestem output-sti
    out_dir = Path(output_dir) if output_dir else gz_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    stem = gz_path.name
    for ext in (".img.gz", ".gz"):
        if stem.endswith(ext):
            stem = stem[:-len(ext)]
            break
    out_filename = f"{stem}-wifi-{timestamp}.img.gz"
    out_gz_path = out_dir / out_filename

    progress_cb(f"📶 WiFi-injektion starter")
    progress_cb(f"   Input:   {gz_path.name}")
    progress_cb(f"   SSID:    {wifi_ssid}")
    progress_cb(f"   Metode:  {effective_method}")
    progress_cb(f"   Land:    {wifi_country}")
    progress_cb(f"   Output:  {out_filename}")

    with tempfile.TemporaryDirectory(prefix="timelapse-wifi-inject-") as tmpdir:
        tmp = Path(tmpdir)
        tmp_img = tmp / "base.img"

        # ── Step 1: Dekomprimér .img.gz → temp .img ──────────────────────────
        progress_cb(f"\n📦 Step 1/4: Dekomprimerer {gz_path.name}...")
        gz_size_mb = gz_path.stat().st_size // (1024 * 1024)
        progress_cb(f"   Størrelse: {gz_size_mb} MB (komprimeret)")
        with gzip.open(gz_path, "rb") as f_in, open(tmp_img, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        img_size_mb = tmp_img.stat().st_size // (1024 * 1024)
        progress_cb(f"   Ukomprimeret: {img_size_mb} MB")

        # ── Step 2: Læs MBR partition-offset ─────────────────────────────────
        progress_cb(f"\n🔍 Step 2/4: Læser MBR partition-tabel (p{effective_root_partition})...")
        offset_bytes = _read_mbr_partition_offset(tmp_img, effective_root_partition)
        progress_cb(f"   Partition {effective_root_partition} offset: {offset_bytes} bytes")

        # ── Step 3: Docker WiFi-injektion ─────────────────────────────────────
        progress_cb(f"\n🔨 Step 3/4: Injecterer WiFi via Docker --privileged...")

        docker_cmd = [
            "docker", "run", "-d", "--privileged",
            "-e", f"OFFSET_BYTES={offset_bytes}",
            "-e", f"WIFI_METHOD={effective_method}",
            "-e", f"WIFI_SSID={wifi_ssid}",
            "-e", f"WIFI_PASSWORD={wifi_password}",
            "-e", f"WIFI_COUNTRY={wifi_country or 'DK'}",
            "ubuntu:22.04", "sleep", "300",
        ]
        start = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
        container_id = start.stdout.strip()
        progress_cb(f"   Container: {container_id[:12]}")

        try:
            subprocess.run(
                ["docker", "exec", container_id, "mkdir", "-p", "/work"],
                check=True, capture_output=True,
            )
            progress_cb(f"   Kopierer image til container ({img_size_mb} MB)...")
            subprocess.run(
                ["docker", "cp", str(tmp_img), f"{container_id}:/work/base.img"],
                check=True, capture_output=True,
            )

            progress_cb(f"   Kører WiFi inject-script...")
            result = subprocess.run(
                ["docker", "exec", "-i", container_id, "bash", "-s"],
                input=_WIFI_INJECT_SCRIPT,
                capture_output=True, text=True, timeout=300,
            )

            for line in (result.stdout + result.stderr).splitlines():
                if line.strip():
                    progress_cb(f"   {line}")

            if result.returncode != 0:
                raise RuntimeError(f"WiFi injection fejlede (rc={result.returncode})")
            if "WIFI_INJECT_OK" not in result.stdout:
                raise RuntimeError("WiFi injection script returnerede ikke WIFI_INJECT_OK")

            progress_cb(f"   Kopierer modificeret image fra container...")
            subprocess.run(
                ["docker", "cp", f"{container_id}:/work/base.img", str(tmp_img)],
                check=True, capture_output=True,
            )

        finally:
            subprocess.run(["docker", "stop", container_id], capture_output=True)
            subprocess.run(["docker", "rm", container_id], capture_output=True)

        # ── Step 4: Komprimér → ny .img.gz ──────────────────────────────────
        progress_cb(f"\n📦 Step 4/4: Komprimerer til {out_filename}...")
        compressor = "pigz" if shutil.which("pigz") else "gzip"
        progress_cb(f"   Bruger: {compressor}")
        with open(out_gz_path, "wb") as out_f:
            subprocess.run(
                [compressor, "-9", "-c", str(tmp_img)],
                stdout=out_f, check=True,
            )

    out_size_mb = out_gz_path.stat().st_size // (1024 * 1024)
    progress_cb(f"✅ WiFi-injiceret image: {out_filename} ({out_size_mb} MB)")

    # SHA256
    import hashlib
    h = hashlib.sha256()
    with open(out_gz_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    sha256 = h.hexdigest()

    return {
        "output_path": str(out_gz_path),
        "filename": out_filename,
        "sha256": sha256,
        "size_bytes": out_gz_path.stat().st_size,
        "wifi_ssid": wifi_ssid,
        "wifi_method": effective_method,
        "wifi_country": wifi_country,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Injectér WiFi i eksisterende .img.gz")
    ap.add_argument("gz_path", help="Sti til .img.gz")
    ap.add_argument("--ssid", required=True, help="WiFi SSID")
    ap.add_argument("--password", required=True, help="WiFi adgangskode")
    ap.add_argument("--country", default="DK", help="WiFi landekode (default: DK)")
    ap.add_argument("--method", default="auto", help="wpa_supplicant | netplan | auto")
    ap.add_argument("--target", default=None, help="Target ID til auto-detect af wifi_method")
    ap.add_argument("--partition", type=int, default=1, help="Root partition nummer (default: 1)")
    ap.add_argument("--output-dir", default=None, help="Output-mappe (default: samme som input)")
    args = ap.parse_args()

    result = inject_wifi_image(
        gz_path=args.gz_path,
        wifi_ssid=args.ssid,
        wifi_password=args.password,
        wifi_country=args.country,
        wifi_method=args.method,
        target_id=args.target,
        root_partition=args.partition,
        output_dir=args.output_dir,
    )
    print(f"\nOutput: {result['output_path']}")
    print(f"SHA256: {result['sha256']}")
    print(f"Størrelse: {result['size_bytes'] // (1024*1024)} MB")
