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

_SSH_INJECT_SCRIPT = r"""#!/bin/bash
set -euo pipefail

BASE_IMG="/work/base.img"
LOOP=$(losetup -f --show -o "${OFFSET_BYTES}" "$BASE_IMG")
echo "[ssh-inject] Loop device: $LOOP"
mkdir -p /mnt/root
mount "$LOOP" /mnt/root

# ── SSH authorized_keys (headend → edge) ─────────────────────────────────────
if [ -n "${HEADEND_SSH_PUBLIC_KEY:-}" ]; then
    echo "[ssh-inject] Injecterer headend public key..."
    for USER_HOME in /mnt/root/home/orangepi /mnt/root/home/ubuntu /mnt/root/home/pi /mnt/root/root; do
        if [ -d "$USER_HOME" ]; then
            mkdir -p "$USER_HOME/.ssh"
            grep -qxF "${HEADEND_SSH_PUBLIC_KEY}" "$USER_HOME/.ssh/authorized_keys" 2>/dev/null \
                || echo "${HEADEND_SSH_PUBLIC_KEY}" >> "$USER_HOME/.ssh/authorized_keys"
            chmod 700 "$USER_HOME/.ssh"
            chmod 600 "$USER_HOME/.ssh/authorized_keys"
            [ "$USER_HOME" = "/mnt/root/root" ] && chown -R 0:0 "$USER_HOME/.ssh" || chown -R 1000:1000 "$USER_HOME/.ssh" || true
            echo "[ssh-inject]   Key tilføjet: $USER_HOME/.ssh/authorized_keys"
        fi
    done
fi

# ── Device private key + reverse tunnel service ───────────────────────────────
if [ -n "${SSH_PRIVATE_KEY:-}" ] && [ -n "${TUNNEL_PORT:-}" ]; then
    echo "[ssh-inject] Injecterer device SSH private key..."
    mkdir -p /mnt/root/etc/timelapse/ssh
    printf '%s' "${SSH_PRIVATE_KEY}" > /mnt/root/etc/timelapse/ssh/tunnel_id_ed25519
    chmod 600 /mnt/root/etc/timelapse/ssh/tunnel_id_ed25519

    HEADEND_HOST="${HEADEND_HOST:-}"
    HEADEND_PORT="${HEADEND_PORT:-22}"
    HEADEND_USER="${HEADEND_USER:-peter}"

    cat > /mnt/root/etc/timelapse/ssh/tunnel.conf << CONF_EOF
TUNNEL_PORT=${TUNNEL_PORT}
HEADEND_HOST=${HEADEND_HOST}
HEADEND_PORT=${HEADEND_PORT}
HEADEND_USER=${HEADEND_USER}
CONF_EOF

    cat > /mnt/root/etc/systemd/system/timelapse-tunnel.service << SVC_EOF
[Unit]
Description=TimeLapse Pro SSH Reverse Tunnel
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Environment="AUTOSSH_GATETIME=0"
ExecStartPre=/bin/bash -c 'which autossh || apt-get install -y -q autossh'
ExecStart=/usr/bin/autossh -M 0 -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=no \
  -o ExitOnForwardFailure=yes \
  -o BatchMode=yes \
  -i /etc/timelapse/ssh/tunnel_id_ed25519 \
  -R ${TUNNEL_PORT}:localhost:22 \
  ${HEADEND_USER}@${HEADEND_HOST} -p ${HEADEND_PORT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SVC_EOF

    mkdir -p /mnt/root/etc/systemd/system/multi-user.target.wants
    ln -sf /etc/systemd/system/timelapse-tunnel.service \
        /mnt/root/etc/systemd/system/multi-user.target.wants/timelapse-tunnel.service
    echo "[ssh-inject]   timelapse-tunnel.service aktiveret (port ${TUNNEL_PORT})"
fi

sync
umount /mnt/root
losetup -d "$LOOP"
echo "[ssh-inject] SSH_INJECT_OK"
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


def _read_partition_offset(img_path: Path, part_num: int, log: Callable[[str], None] = lambda _: None) -> int:
    """Auto-detect MBR vs GPT og returnér byte-offset til partition part_num."""
    with open(img_path, "rb") as f:
        f.seek(512)
        is_gpt = f.read(8) == b"EFI PART"

        if is_gpt:
            log(f"   Partitionstabel: GPT")
            f.seek(512)
            hdr = f.read(92)
            pe_lba   = int.from_bytes(hdr[72:80], "little")
            pe_size  = int.from_bytes(hdr[84:88], "little")
            entry_offset = pe_lba * 512 + (part_num - 1) * pe_size
            f.seek(entry_offset)
            entry = f.read(pe_size)
            if entry[:16] == b"\x00" * 16:
                raise RuntimeError(f"GPT partition {part_num} er tom")
            first_lba = int.from_bytes(entry[32:40], "little")
        else:
            log(f"   Partitionstabel: MBR")
            f.seek(446 + (part_num - 1) * 16)
            entry = f.read(16)
            first_lba = int.from_bytes(entry[8:12], "little")

    offset_bytes = first_lba * 512
    if offset_bytes == 0:
        raise RuntimeError(f"Partition {part_num} LBA=0 — ikke et gyldigt disk-image")
    log(f"   Partition {part_num} offset: {offset_bytes} bytes (LBA {first_lba})")
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
    # SSH inject (v8)
    ssh_private_key: str | None = None,
    headend_ssh_public_key: str | None = None,
    reverse_tunnel_port: int | None = None,
    headend_host: str = os.getenv("TIMELAPSE_TUNNEL_HOST", ""),
    headend_port: int = 22,
    headend_user: str = os.getenv("TIMELAPSE_TUNNEL_USER", ""),
) -> dict:
    """
    Injectér WiFi-konfiguration (og valgfrit SSH-nøgler + reverse tunnel) i et eksisterende flashbart image.

    Args:
        gz_path:                Sti til eksisterende .img.gz eller .img
        wifi_ssid:              WiFi SSID
        wifi_password:          WiFi adgangskode
        wifi_country:           Landekode (default: DK)
        wifi_method:            "wpa_supplicant" | "netplan" | "auto"
        target_id:              Hardware target ID til auto-detect af wifi_method
        root_partition:         Root-partition nummer (default: 1)
        output_dir:             Output-mappe (None = samme som input)
        progress_cb:            Callback for statusbeskeder
        repo_root:              Git-repo root (None = auto-detect)
        ssh_private_key:        Device Ed25519 private key (PEM) — til reverse tunnel
        headend_ssh_public_key: Headend public key — tilføjes device's authorized_keys
        reverse_tunnel_port:    Port på headend til reverse tunnel (fx 2202)
        headend_host:           Headend hostname (default: TIMELAPSE_TUNNEL_HOST)
        headend_port:           Headend SSH port (default: 22)
        headend_user:           Headend SSH bruger (default: TIMELAPSE_TUNNEL_USER)

    Returnerer dict med:
        output_path, filename, sha256, size_bytes
    """
    gz_path = Path(gz_path)
    if not gz_path.exists():
        raise FileNotFoundError(f"Input-fil ikke fundet: {gz_path}")
    is_compressed = gz_path.suffix in (".gz",) or gz_path.name.endswith(".img.gz")

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
    for ext in (".img.gz", ".img", ".gz"):
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

        # ── Step 1: Forbered .img ─────────────────────────────────────────────
        if is_compressed:
            progress_cb(f"\n📦 Step 1/4: Dekomprimerer {gz_path.name}...")
            gz_size_mb = gz_path.stat().st_size // (1024 * 1024)
            progress_cb(f"   Størrelse: {gz_size_mb} MB (komprimeret)")
            with gzip.open(gz_path, "rb") as f_in, open(tmp_img, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        else:
            progress_cb(f"\n📦 Step 1/4: Kopierer ukomprimeret {gz_path.name}...")
            shutil.copy2(gz_path, tmp_img)
        img_size_mb = tmp_img.stat().st_size // (1024 * 1024)
        progress_cb(f"   Ukomprimeret: {img_size_mb} MB")

        # ── Step 2: Læs MBR partition-offset ─────────────────────────────────
        progress_cb(f"\n🔍 Step 2/4: Læser partition-tabel (p{effective_root_partition})...")
        offset_bytes = _read_partition_offset(tmp_img, effective_root_partition, progress_cb)
        progress_cb(f"   Partition {effective_root_partition} offset: {offset_bytes} bytes")

        # Afgør hvad der skal injectes
        do_ssh = bool(ssh_private_key or headend_ssh_public_key)
        step_label = "WiFi+SSH" if do_ssh else "WiFi"
        progress_cb(f"\n🔨 Step 3/4: Injecterer {step_label} via Docker --privileged...")

        docker_cmd = [
            "docker", "run", "-d", "--privileged",
            "-e", f"OFFSET_BYTES={offset_bytes}",
            "-e", f"WIFI_METHOD={effective_method}",
            "-e", f"WIFI_SSID={wifi_ssid}",
            "-e", f"WIFI_PASSWORD={wifi_password}",
            "-e", f"WIFI_COUNTRY={wifi_country or 'DK'}",
            # SSH env vars (tomme strenge hvis ikke angivet)
            "-e", f"HEADEND_SSH_PUBLIC_KEY={headend_ssh_public_key or ''}",
            "-e", f"SSH_PRIVATE_KEY={ssh_private_key or ''}",
            "-e", f"TUNNEL_PORT={reverse_tunnel_port or ''}",
            "-e", f"HEADEND_HOST={headend_host}",
            "-e", f"HEADEND_PORT={headend_port}",
            "-e", f"HEADEND_USER={headend_user}",
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

            # ── SSH inject (køres i samme container, image allerede mounted) ──
            if do_ssh:
                progress_cb(f"   Kører SSH inject-script...")
                ssh_result = subprocess.run(
                    ["docker", "exec", "-i", container_id, "bash", "-s"],
                    input=_SSH_INJECT_SCRIPT,
                    capture_output=True, text=True, timeout=120,
                )
                for line in (ssh_result.stdout + ssh_result.stderr).splitlines():
                    if line.strip():
                        progress_cb(f"   {line}")
                if ssh_result.returncode != 0:
                    raise RuntimeError(f"SSH injection fejlede (rc={ssh_result.returncode})")
                if "SSH_INJECT_OK" not in ssh_result.stdout:
                    raise RuntimeError("SSH injection script returnerede ikke SSH_INJECT_OK")

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
