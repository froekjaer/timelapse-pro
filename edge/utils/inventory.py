# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — edge/utils/inventory.py
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.0.0
# Dato     : 2026-05-11
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   1.0.0  11-maj-2026  Initial inventar-rapportering ved edge startup
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — Edge Inventar-Rapportering
==========================================
Samler hardwareinformation og sender det til headend ved agent-startup.

Kaldes fra agent.py i _startup():
    from utils.inventory import report_inventory
    report_inventory(self._cfg, self._api)

Ikke-blokerende: fejl logges men stopper ikke agenten.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

APP_VERSION = "2.8.0"    # Opdateres ved release (TODO: læs fra VERSION-fil)
GPG_KEY_UID = "timelapse@froekjaer.dk"  # Til fingerprint-opslag


# ── Hardware-detection ────────────────────────────────────────────────────────

def _detect_hardware_model() -> tuple[str, str]:
    """
    Returnerer (hardware_model, soc_model).
    Eksempel: ("Orange Pi 4 Pro", "RK3588S")
    """
    try:
        dt = Path("/proc/device-tree/compatible").read_bytes() \
               .replace(b"\x00", b"\n").decode(errors="ignore")
        if "orangepi-4-pro" in dt:
            return "Orange Pi 4 Pro", "RK3588S"
        if "orangepi-pc-plus" in dt:
            return "Orange Pi PC Plus", "Allwinner H3"
        if "orangepi-zero" in dt:
            return "Orange Pi Zero 2W", "Allwinner H616"
    except OSError:
        pass

    try:
        info = Path("/proc/cpuinfo").read_text()
        if "RK3588" in info:
            return "Orange Pi 4 Pro", "RK3588S"
        if "Allwinner" in info:
            return "Orange Pi PC Plus", "Allwinner H3"
    except OSError:
        pass

    return "Ukendt", "Ukendt"


def _cpu_cores() -> Optional[int]:
    try:
        return os.cpu_count()
    except Exception:
        return None


def _ram_mb() -> Optional[int]:
    try:
        info = Path("/proc/meminfo").read_text()
        m = re.search(r"MemTotal:\s+(\d+)\s+kB", info)
        return int(m.group(1)) // 1024 if m else None
    except OSError:
        return None


def _serial_number() -> Optional[str]:
    """Henter serienummer fra /proc/cpuinfo (ARM-boards)."""
    try:
        info = Path("/proc/cpuinfo").read_text()
        m = re.search(r"Serial\s*:\s*([0-9a-fA-F]+)", info)
        return m.group(1) if m else None
    except OSError:
        return None


def _primary_mac(interface: str) -> Optional[str]:
    try:
        return (Path("/sys/class/net") / interface / "address").read_text().strip()
    except OSError:
        return None


def _primary_interface() -> str:
    """Finder primær ethernet-interface (end0 > eth0 > første fund)."""
    net = Path("/sys/class/net")
    for preferred in ("end0", "eth0"):
        if (net / preferred).exists():
            return preferred
    for iface in sorted(net.iterdir()):
        name = iface.name
        if name == "lo" or name.startswith("wl"):
            continue
        real = os.path.realpath(iface)
        if "usb" not in real.lower():
            return name
    return "eth0"


def _wifi_info() -> tuple[bool, Optional[str]]:
    """Returnerer (wifi_capable, ssid_eller_None)."""
    # Tjek om WiFi-interface eksisterer
    net = Path("/sys/class/net")
    wifi_iface = None
    for iface in net.iterdir():
        if iface.name.startswith("wl"):
            wifi_iface = iface.name
            break

    if not wifi_iface:
        return False, None

    # Forsøg at hente SSID
    try:
        result = subprocess.run(
            ["iwgetid", wifi_iface, "--raw"],
            capture_output=True, text=True, timeout=3
        )
        ssid = result.stdout.strip() or None
        return True, ssid
    except Exception:
        return True, None


# ── Storage-detection ─────────────────────────────────────────────────────────

def _storage_info(path: str = "/") -> tuple[Optional[str], Optional[float], Optional[float]]:
    """
    Returnerer (storage_type, total_gb, used_pct) for et mount-punkt.
    storage_type detekteres ud fra enhedsnavnet.
    """
    try:
        usage = shutil.disk_usage(path)
        total_gb = usage.total / (1024 ** 3)
        used_pct = (usage.used / usage.total * 100) if usage.total else 0

        # Find enhedsnavn for mount-punkt
        result = subprocess.run(
            ["findmnt", "--noheadings", "--output", "SOURCE", path],
            capture_output=True, text=True, timeout=3
        )
        source = result.stdout.strip()

        storage_type = "unknown"
        if "mmcblk" in source and "p" in source:
            # Skelne eMMC fra SD: eMMC er typisk mmcblk0, SD er mmcblk1
            # Men det afhænger af boardet — vi tjekker /sys/block
            dev = re.sub(r"p\d+$", "", source.lstrip("/dev/"))
            uevent = Path(f"/sys/block/{dev}/device/uevent")
            if uevent.exists():
                content = uevent.read_text()
                if "MMC_TYPE=SD" in content:
                    storage_type = "sd"
                elif "MMC_TYPE=MMC" in content:
                    storage_type = "emmc"
                else:
                    storage_type = "mmc"
            else:
                storage_type = "mmc"
        elif "nvme" in source:
            storage_type = "nvme"
        elif "sda" in source or "sdb" in source:
            storage_type = "ssd"

        return storage_type, round(total_gb, 1), round(used_pct, 1)
    except Exception as e:
        log.debug("Storage-detection fejl for %s: %s", path, e)
        return None, None, None


# ── Venv-pakker ───────────────────────────────────────────────────────────────

def _venv_packages() -> dict[str, str]:
    """
    Returnerer dict af installerede venv-pakker: {navn: version}.
    Kører `pip list --format=json` i aktive venv.
    """
    try:
        result = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=10
        )
        pkgs = json.loads(result.stdout)
        return {p["name"]: p["version"] for p in pkgs}
    except Exception as e:
        log.debug("venv_packages fejl: %s", e)
        return {}


# ── GPG fingerprint ───────────────────────────────────────────────────────────

def _gpg_fingerprint() -> Optional[str]:
    """Henter fingerprint for TimeLapse Pro GPG-nøglen."""
    try:
        result = subprocess.run(
            ["gpg", "--list-keys", "--with-colons", GPG_KEY_UID],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if line.startswith("fpr"):
                return line.split(":")[9]
    except Exception:
        pass
    return None


# ── Samlet inventar ───────────────────────────────────────────────────────────

def collect_inventory(config: dict) -> dict:
    """
    Samler alt inventar og returnerer en dict klar til POST.
    Robust: fejl i ét felt stopper ikke resten.
    """
    hw_model, soc = _detect_hardware_model()
    iface = _primary_interface()
    mac = _primary_mac(iface)
    wifi_cap, wifi_ssid = _wifi_info()
    boot_type, boot_gb, boot_pct = _storage_info("/")
    data_path = config.get("storage", {}).get("base_dir", "/data")
    data_type, data_gb, data_pct = _storage_info(data_path) if Path(data_path).exists() else (None, None, None)

    return {
        # Hardware
        "hardware_model":           hw_model,
        "soc_model":                soc,
        "cpu_cores":                _cpu_cores(),
        "ram_mb":                   _ram_mb(),
        "mac_address":              mac,
        "serial_number":            _serial_number(),
        "hostname":                 platform.node(),

        # OS / Software
        "os_name":                  _os_name(),
        "kernel_version":           platform.release(),
        "python_version":           platform.python_version(),
        "app_version":              APP_VERSION,
        "venv_packages":            _venv_packages(),

        # Storage (boot)
        "boot_storage_type":        boot_type,
        "boot_storage_total_gb":    boot_gb,
        "boot_storage_used_pct":    boot_pct,

        # Storage (data)
        "data_partition_path":      data_path,
        "data_partition_total_gb":  data_gb,
        "data_partition_used_pct":  data_pct,

        # Netværk
        "primary_interface":        iface,
        "wifi_capable":             wifi_cap,
        "wifi_ssid":                wifi_ssid,

        # Signering
        "gpg_fingerprint":          _gpg_fingerprint(),
    }


def _os_name() -> str:
    """Læser /etc/os-release for korrekt OS-navn."""
    try:
        lines = Path("/etc/os-release").read_text().splitlines()
        pretty = next((l.split("=", 1)[1].strip('"') for l in lines if l.startswith("PRETTY_NAME=")), None)
        if pretty:
            return pretty
    except OSError:
        pass
    return platform.system() + " " + platform.release()


# ── Rapportering til headend ──────────────────────────────────────────────────

def report_inventory(config: dict, api_client) -> None:
    """
    Samler inventar og sender det til headend.
    Ikke-blokerende: fejl logges og ignoreres.

    Kaldes fra agent._startup():
        from utils.inventory import report_inventory
        report_inventory(self._cfg, self._api)
    """
    device_id = config.get("device", {}).get("device_id", "unknown")
    log.info("Inventar-rapportering starter for %s", device_id)

    try:
        payload = collect_inventory(config)
        log.debug("Inventar samlet: hw=%s soc=%s os=%s",
                  payload.get("hardware_model"),
                  payload.get("soc_model"),
                  payload.get("os_name"))

        ok, resp = api_client._post(f"/inventory/{device_id}", payload)
        if ok:
            log.info("Inventar rapporteret til headend: %s", device_id)
        else:
            log.warning("Inventar-rapportering fejlede (headend svarede ikke): %s", resp)

    except Exception as exc:
        # Aldrig blokér agent-startup pga. inventar
        log.warning("Inventar-rapportering fejlede (uventet): %s", exc)
