#!/usr/bin/env python3
"""Unique Bluetooth address per Edge (Peter, 2026-10-04).

The Orange Pi 4 Pro's AIC8800 Bluetooth chip comes up with the vendor's
placeholder address 10:11:12:13:14:15 on every board (seen on Edge2), so two
Edges look like the same Bluetooth device to a technician's phone. Edge1 had
a hand-made bt-set-addr.service with a fixed address; nothing in the repo or
the image builder did this.

Address source, in order:
  1. /etc/timelapse/bt-address (persisted; Edge1's old address is migrated
     here by timelapse_system_baseline.py, so its pairings keep working)
  2. derived from the Edge's device id (config.yaml device.device_id, else a
     hardware MAC, else /etc/machine-id): a locally administered unicast address, stable for
     the device, then persisted to (1)

Applied with the AIC8800 vendor command (HCI 0x3f/0x0070, address LSB first)
followed by an hci0 reset — the same commands Edge1's unit used.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path

ADDRESS_FILE = Path("/etc/timelapse/bt-address")
CONFIG = Path("/opt/timelapse/edge/config.yaml")
MACHINE_ID = Path("/etc/machine-id")
VENDOR_PLACEHOLDER = "10:11:12:13:14:15"
_ADDR = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def derive_address(seed: str) -> str:
    digest = bytearray(hashlib.sha256(f"timelapse-bt:{seed}".encode()).digest()[:6])
    digest[0] = (digest[0] & 0xFC) | 0x02          # locally administered, unicast
    return ":".join(f"{b:02X}" for b in digest)


def vendor_command(address: str) -> list[str]:
    return ["hcitool", "cmd", "0x3f", "0x0070", *reversed(address.split(":"))]


def _device_seed() -> str:
    """Device id, else a hardware MAC. machine-id is the last resort: images
    built from the Orange Pi base all carried the same one (2026-10-04)."""
    try:
        import yaml
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        device_id = str((cfg.get("device") or {}).get("device_id") or "").strip()
        if device_id and device_id.lower() != "unknown":
            return device_id
    except Exception:
        pass
    for iface in ("end0", "eth0", "wlan0"):
        mac = Path(f"/sys/class/net/{iface}/address")
        if mac.is_file():
            value = mac.read_text(encoding="utf-8").strip()
            if value and value != "00:00:00:00:00:00":
                return value
    return MACHINE_ID.read_text(encoding="utf-8").strip() if MACHINE_ID.exists() else ""


def wanted_address() -> str | None:
    if ADDRESS_FILE.is_file():
        stored = ADDRESS_FILE.read_text(encoding="utf-8").strip().upper()
        if _ADDR.match(stored) and stored != VENDOR_PLACEHOLDER:
            return stored
    seed = _device_seed()
    if not seed:
        return None
    address = derive_address(seed)
    ADDRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ADDRESS_FILE.write_text(address + "\n", encoding="utf-8")
    return address


def current_address() -> str | None:
    out = subprocess.run(["hciconfig", "hci0"], capture_output=True, text=True, timeout=10).stdout
    match = re.search(r"BD Address:\s*([0-9A-F:]{17})", out)
    return match.group(1) if match else None


def main() -> int:
    for _ in range(15):                     # hci0 can appear a little after bluetooth.service
        if current_address():
            break
        time.sleep(1)
    current = current_address()
    if not current:
        print("[bt-address] hci0 findes ikke — springer over")
        return 0
    wanted = wanted_address()
    if not wanted:
        print("[bt-address] intet device-id/machine-id — kan ikke udlede adresse")
        return 0
    if current == wanted:
        print(f"[bt-address] {current} (uændret)")
        return 0
    subprocess.run(vendor_command(wanted), capture_output=True, text=True, timeout=10)
    subprocess.run(["hciconfig", "hci0", "reset"], capture_output=True, text=True, timeout=10)
    time.sleep(1)
    after = current_address()
    print(f"[bt-address] {current} -> {after} (ønsket {wanted})")
    return 0 if after == wanted else 1


if __name__ == "__main__":
    sys.exit(main())
