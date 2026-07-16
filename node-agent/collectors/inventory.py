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

APP_VERSION = "unknown"
RELEASE_METADATA_FILES = (
    Path("/opt/timelapse-node-agent/.timelapse-release.json"),
    Path("/opt/timelapse/edge/.timelapse-release.json"),
)
GPG_KEY_UID = "timelapse@froekjaer.dk"  # Til fingerprint-opslag


def _run(cmd: list[str], timeout: int = 5, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    runtime_env = os.environ.copy()
    if env:
        runtime_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=runtime_env)


def _cfg_value(config, key: str, default=None):
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _app_version() -> str:
    """Return deployed release identity without relying on a mutable checkout."""
    configured = os.getenv("TIMELAPSE_APP_VERSION", "").strip()
    if configured:
        return configured
    for path in RELEASE_METADATA_FILES:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(receipt, dict):
            continue
        if receipt.get("schema") not in {"timelapse.node.release.v1", "timelapse.edge.release.v1"}:
            continue
        value = receipt.get("version") or receipt.get("source_commit") or receipt.get("artifact_id")
        if value and str(value).strip():
            return str(value).strip()
    return APP_VERSION


# ── Hardware-detection ────────────────────────────────────────────────────────

def _detect_hardware_model() -> tuple[str, str]:
    """
    Returnerer (hardware_model, soc_model).
    Eksempel: ("Orange Pi 4 Pro", "RK3588S")
    """
    if platform.system() == "Darwin":
        try:
            model = _run(["sysctl", "-n", "hw.model"], timeout=3).stdout.strip()
            if model:
                return model, platform.machine()
        except Exception:
            pass
        try:
            out = _run(["system_profiler", "SPHardwareDataType"], timeout=10).stdout
            m = re.search(r"Model Name:\s*(.+)", out)
            return (m.group(1).strip() if m else "Mac"), platform.machine()
        except Exception:
            return "Mac", platform.machine()

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
    if platform.system() == "Darwin":
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages and page_size:
                return int(pages * page_size) // (1024 * 1024)
        except Exception:
            pass
        try:
            out = _run(["sysctl", "-n", "hw.memsize"], timeout=3).stdout.strip()
            return int(out) // (1024 * 1024) if out else None
        except Exception:
            return None

    try:
        info = Path("/proc/meminfo").read_text()
        m = re.search(r"MemTotal:\s+(\d+)\s+kB", info)
        return int(m.group(1)) // 1024 if m else None
    except OSError:
        return None


def _serial_number() -> Optional[str]:
    """Henter serienummer fra /proc/cpuinfo (ARM-boards)."""
    if platform.system() == "Darwin":
        try:
            out = _run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], timeout=3).stdout
            m = re.search(r'"IOPlatformSerialNumber"\s+=\s+"([^"]+)"', out)
            return m.group(1) if m else None
        except Exception:
            return None

    try:
        info = Path("/proc/cpuinfo").read_text()
        m = re.search(r"Serial\s*:\s*([0-9a-fA-F]+)", info)
        return m.group(1) if m else None
    except OSError:
        return None


def _primary_mac(interface: str) -> Optional[str]:
    if platform.system() == "Darwin":
        out = _run(["ifconfig", interface], timeout=3).stdout
        m = re.search(r"ether\s+([0-9a-f:]{17})", out)
        return m.group(1) if m else None
    try:
        return (Path("/sys/class/net") / interface / "address").read_text().strip()
    except OSError:
        return None


def _primary_ip(interface: str) -> Optional[str]:
    if platform.system() == "Darwin":
        try:
            out = _run(["ipconfig", "getifaddr", interface], timeout=3).stdout.strip()
            if out:
                return out
        except Exception:
            pass
        try:
            out = _run(["ifconfig", interface], timeout=3).stdout
            m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", out)
            return m.group(1) if m else None
        except Exception:
            return None

    try:
        result = _run(["ip", "-4", "-o", "addr", "show", "dev", interface], timeout=3)
        m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", result.stdout)
        return m.group(1) if m else None
    except Exception:
        return None


def _ip_addresses() -> dict[str, list[str]]:
    addresses: dict[str, list[str]] = {}
    try:
        if platform.system() == "Darwin":
            current_iface: str | None = None
            for line in _run(["ifconfig"], timeout=5).stdout.splitlines():
                if line and not line.startswith(("\t", " ")):
                    current_iface = line.split(":", 1)[0]
                elif current_iface and "\tinet " in line:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] != "127.0.0.1":
                        addresses.setdefault(current_iface, []).append(parts[1])
            return addresses

        result = _run(["ip", "-4", "-o", "addr"], timeout=5)
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                iface = parts[1]
                ip = parts[3].split("/", 1)[0]
                if ip != "127.0.0.1":
                    addresses.setdefault(iface, []).append(ip)
    except Exception:
        pass
    return addresses


def _primary_interface() -> str:
    """Finder primær ethernet-interface — platform-aware."""
    if platform.system() == "Darwin":
        out = _run(["route", "-n", "get", "default"], timeout=3).stdout
        for line in out.splitlines():
            if "interface:" in line:
                return line.split()[-1]
        return "en0"
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
    if platform.system() == "Darwin":
        # Prøv networksetup (virker på alle macOS versioner)
        try:
            out = _run(["networksetup", "-getairportnetwork", "en0"], timeout=3).stdout
            if "You are not associated" in out:
                return True, None
            m = re.search(r"Current Wi-Fi Network: (.+)", out)
            return True, m.group(1).strip() if m else None
        except Exception:
            return True, None

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

        if platform.system() == "Darwin":
            source = ""
            try:
                lines = _run(["df", path], timeout=3).stdout.splitlines()
                source = lines[1].split()[0] if len(lines) > 1 else ""
            except Exception:
                pass
            storage_type = "internal" if "disk" in source else "apfs"
            return storage_type, round(total_gb, 1), round(used_pct, 1)

        # Find enhedsnavn for mount-punkt
        result = _run(["findmnt", "--noheadings", "--output", "SOURCE", path], timeout=3)
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

def _venv_packages(config=None) -> dict[str, str]:
    """
    Returnerer dict af installerede venv-pakker: {navn: version}.
    Kører `pip list --format=json` i aktive venv.
    """
    try:
        candidates = []
        configured = _cfg_value(config, "python_bin") or _cfg_value(config, "venv_python")
        if configured:
            candidates.append(Path(configured))
        candidates.extend([
            Path("/Users/peter/projects/timelapse-pro/headend/venv/bin/python"),
            Path("/opt/timelapse-node-agent/venv/bin/python3"),
        ])
        which_python = shutil.which("python3")
        if which_python:
            candidates.append(Path(which_python))
        python_bin = next((p for p in candidates if p.exists()), None)
        cmd = [str(python_bin), "-m", "pip", "list", "--format=json"] if python_bin else ["pip", "list", "--format=json"]
        result = _run(cmd, timeout=15)
        if result.returncode != 0:
            log.debug("venv_packages kommando fejlede: %s", result.stderr[-300:])
            return {}
        pkgs = json.loads(result.stdout)
        return {p["name"]: p["version"] for p in pkgs}
    except Exception as e:
        log.debug("venv_packages fejl: %s", e)
        return {}


def _firmware_version() -> Optional[str]:
    if platform.system() == "Darwin":
        try:
            out = _run(["system_profiler", "SPHardwareDataType"], timeout=10).stdout
            boot = re.search(r"System Firmware Version:\s*(.+)", out)
            os_loader = re.search(r"OS Loader Version:\s*(.+)", out)
            parts = []
            if boot:
                parts.append(f"firmware={boot.group(1).strip()}")
            if os_loader:
                parts.append(f"os_loader={os_loader.group(1).strip()}")
            return "; ".join(parts) if parts else None
        except Exception:
            return None

    for path in (
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ):
        try:
            value = Path(path).read_bytes().replace(b"\x00", b"").decode(errors="ignore").strip()
            if value:
                return value
        except OSError:
            pass
    return None


def _os_packages() -> tuple[Optional[str], dict[str, str]]:
    if platform.system() == "Darwin":
        packages: dict[str, str] = {}
        try:
            result = _run(["pkgutil", "--pkgs"], timeout=15)
            for name in result.stdout.splitlines():
                name = name.strip()
                if name:
                    packages[name] = "installed"
            return "macos/pkgutil", packages
        except Exception as exc:
            log.debug("pkgutil package inventory fejl: %s", exc)
            return "macos/pkgutil", {}

    try:
        result = _run(["dpkg-query", "-W", "-f=${Package}=${Version}\\n"], timeout=25)
        packages = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                name, version = line.split("=", 1)
                packages[name] = version
        return "apt/dpkg", packages
    except Exception as exc:
        log.debug("dpkg package inventory fejl: %s", exc)
        return "apt/dpkg", {}


def _brew_env() -> dict[str, str]:
    home = os.environ.get("HOME") or "/Users/peter"
    return {
        "HOME": home,
        "PATH": "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOMEBREW_NO_AUTO_UPDATE": "1",
        "HOMEBREW_NO_ENV_HINTS": "1",
    }


def _homebrew_formulae() -> dict[str, str]:
    brew = Path("/opt/homebrew/bin/brew")
    if not brew.exists():
        return {}
    result = _run([str(brew), "list", "--versions"], timeout=25, env=_brew_env())
    if result.returncode != 0:
        log.debug("brew list fejlede: %s", result.stderr[-300:])
        return {}
    formulae: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            formulae[parts[0]] = " ".join(parts[1:])
    return formulae


def _homebrew_outdated() -> list[dict[str, str]]:
    brew = Path("/opt/homebrew/bin/brew")
    if not brew.exists():
        return []
    result = _run([str(brew), "outdated", "--json=v2"], timeout=35, env=_brew_env())
    if result.returncode not in (0, 1):
        log.debug("brew outdated fejlede: %s", result.stderr[-300:])
        return []
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return []
    updates: list[dict[str, str]] = []
    for item in data.get("formulae", []):
        installed = item.get("installed_versions") or []
        updates.append({
            "name": str(item.get("name") or ""),
            "installed_version": ", ".join(str(v) for v in installed),
            "available_version": str(item.get("current_version") or ""),
            "manager": "homebrew",
            "kind": "formula",
            "pinned": str(bool(item.get("pinned", False))).lower(),
        })
    for item in data.get("casks", []):
        updates.append({
            "name": str(item.get("name") or item.get("token") or ""),
            "installed_version": str(item.get("installed_versions") or ""),
            "available_version": str(item.get("current_version") or ""),
            "manager": "homebrew",
            "kind": "cask",
            "pinned": "false",
        })
    return [u for u in updates if u["name"]]


def _software_inventory(config=None) -> dict[str, object]:
    inventory = {
        "timelapse_pro": _app_version(),
        "python": platform.python_version(),
    }
    if platform.system() == "Darwin":
        formulae = _homebrew_formulae()
        if formulae:
            inventory["homebrew_formulae"] = formulae
        outdated = _homebrew_outdated()
        if outdated:
            inventory["available_software_updates"] = outdated
        for name, cmd in {
            "nginx": ["/opt/homebrew/sbin/nginx", "-v"],
            "ollama": ["/opt/homebrew/bin/ollama", "--version"],
            "brew": ["/opt/homebrew/bin/brew", "--version"],
        }.items():
            try:
                result = _run(cmd, timeout=5, env=_brew_env())
                text = (result.stdout or result.stderr).strip().splitlines()
                if text:
                    inventory[name] = text[0]
            except Exception:
                pass
    return inventory


# ── GPG fingerprint ───────────────────────────────────────────────────────────

def _gpg_fingerprint() -> Optional[str]:
    """Henter fingerprint for TimeLapse Pro GPG-nøglen."""
    try:
        result = _run(["gpg", "--list-keys", "--with-colons", GPG_KEY_UID], timeout=5)
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
    ip = _primary_ip(iface)
    wifi_cap, wifi_ssid = _wifi_info()
    boot_type, boot_gb, boot_pct = _storage_info("/")
    if platform.system() == "Darwin":
        data_path = next(
            (path for path in ("/Volumes/data-fast", "/Volumes/data") if Path(path).exists()),
            "/data",
        )
    else:
        data_path = "/data"
    data_type, data_gb, data_pct = _storage_info(data_path) if Path(data_path).exists() else (None, None, None)
    package_manager, os_packages = _os_packages()

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
        "firmware_version":         _firmware_version(),
        "python_version":           platform.python_version(),
        "app_version":              _app_version(),
        "package_manager":          package_manager,
        "os_packages":              os_packages,
        "venv_packages":            _venv_packages(config),
        "software_inventory":       _software_inventory(config),

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
        "ip_address":               ip,
        "ip_addresses":             _ip_addresses(),
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
