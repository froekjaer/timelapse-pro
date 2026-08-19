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

APP_VERSION = "2.8.0"    # Fallback for unprovisioned/development installations
RELEASE_METADATA_FILE = Path("/opt/timelapse/edge/.timelapse-release.json")
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


def _primary_ip(interface: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", interface],
            capture_output=True, text=True, timeout=3
        )
        m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", result.stdout)
        return m.group(1) if m else None
    except Exception:
        return None


def _ip_addresses() -> dict[str, list[str]]:
    addresses: dict[str, list[str]] = {}
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr"],
            capture_output=True, text=True, timeout=5
        )
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


def _firmware_version() -> Optional[str]:
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


def _os_packages() -> tuple[str, dict[str, str]]:
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}=${Version}\\n"],
            capture_output=True, text=True, timeout=25
        )
        packages = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                name, version = line.split("=", 1)
                packages[name] = version
        return "apt/dpkg", packages
    except Exception as e:
        log.debug("dpkg package inventory fejl: %s", e)
        return "apt/dpkg", {}


def _software_inventory() -> dict[str, str]:
    inventory = {
        "timelapse_pro": APP_VERSION,
        "python": platform.python_version(),
    }
    for name, cmd in {
        "gphoto2": ["gphoto2", "--version"],
        "libgphoto2": ["gphoto2", "--version"],
    }.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            line = (result.stdout or result.stderr).strip().splitlines()
            if line:
                inventory[name] = line[0]
        except Exception:
            pass
    return inventory


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


# ── Lokale brugere ────────────────────────────────────────────────────────────

def _local_users() -> list[dict]:
    """Returnerer liste over lokale, ikke-system brugere (UID >= 1000)."""
    users = []
    try:
        for line in Path("/etc/passwd").read_text().splitlines():
            parts = line.split(":")
            if len(parts) < 7:
                continue
            username, _, uid_s, gid_s, gecos, home, shell = parts[:7]
            try:
                uid = int(uid_s)
            except ValueError:
                continue
            if uid < 1000 or uid == 65534:  # skip system + nobody
                continue
            users.append({
                "username": username,
                "uid":      uid,
                "gid":      int(gid_s) if gid_s.isdigit() else None,
                "home":     home,
                "shell":    shell,
                "gecos":    gecos,
                "has_home": Path(home).exists() if home else False,
            })
    except Exception as exc:
        log.debug("local_users fejl: %s", exc)
    return users


def _sudo_users() -> list[str]:
    """Returnerer liste over brugere med sudo-rettigheder."""
    sudoers: list[str] = []
    try:
        result = subprocess.run(
            ["getent", "group", "sudo"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(":")
            if len(parts) >= 4 and parts[3].strip():
                sudoers.extend(u.strip() for u in parts[3].split(",") if u.strip())
    except Exception:
        pass
    return sudoers


# ── Systemd services ──────────────────────────────────────────────────────────

# Nøgleservices vi altid rapporterer status for
_TRACKED_SERVICES = [
    "timelapse-edge.service",
    "timelapse-edge-watchdog.service",
    "ssh.service",
    "sshd.service",
    "systemd-timesyncd.service",
    "chrony.service",
    "NetworkManager.service",
    "networking.service",
]


def _systemd_services() -> list[dict]:
    """Returnerer status for relevante systemd-services."""
    services = []
    try:
        # Hent alle units der indeholder "timelapse" + de trackede
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all",
             "--no-pager", "--no-legend", "--output=json"],
            capture_output=True, text=True, timeout=15
        )
        units: list[dict] = []
        if result.returncode == 0:
            try:
                units = json.loads(result.stdout) or []
            except Exception:
                pass
        # Fallback: parse tekstoutput
        if not units and result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    units.append({
                        "unit": parts[0],
                        "load": parts[1],
                        "active": parts[2],
                        "sub": parts[3],
                        "description": " ".join(parts[4:]),
                    })

        wanted = {s.lower() for s in _TRACKED_SERVICES}
        for unit in units:
            name = str(unit.get("unit", ""))
            is_wanted = name.lower() in wanted or "timelapse" in name.lower()
            if is_wanted:
                services.append({
                    "name":        name,
                    "load":        unit.get("load", ""),
                    "active":      unit.get("active", ""),
                    "sub":         unit.get("sub", ""),
                    "description": unit.get("description", ""),
                })
    except Exception as exc:
        log.debug("systemd_services fejl: %s", exc)
    return services


def _enabled_service_names() -> list[str]:
    """Returnerer navne på ALLE enabled systemd service-units, ikke kun den
    trackede/tidligere filtrerede delmængde i _systemd_services(). Bruges til
    baseline-drift-sammenligning (FIND-CMDB-MISSING-PACKAGE-DETECTION og
    -UNTRACKED-DOCKER-CE-CHANNEL, udvidet til services+accounts jf. Peter
    2026-08-16) — skal kunne opdage services der ER enabled men IKKE burde
    være det, hvilket den gamle allowlist-filtrerede liste ikke kunne.
    """
    names: list[str] = []
    try:
        result = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--state=enabled",
             "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts:
                    names.append(parts[0])
    except Exception as exc:
        log.debug("enabled_service_names fejl: %s", exc)
    return sorted(set(names))


# ── Tilgængelige OS-opdateringer ──────────────────────────────────────────────

def _apt_updates_available() -> dict:
    """
    Returnerer dict med tilgængelige apt-opdateringer.
    Bruger cached apt-data (apt-get -s upgrade) — kræver ikke netværk.

    Eksempel apt-get -s upgrade output:
        Inst docker-ce [5:29.2.1-1~ubuntu.24.04~noble] (5:29.5.2-1~ubuntu.24.04~noble download.docker.com:443 [arm64])
        Inst curl [7.81.0-1ubuntu1.16] (7.81.0-1ubuntu1.17 Ubuntu:22.04/jammy-security [amd64])

    Felter i hvert pakke-element:
        name        - pakkens navn
        old_ver     - installeret version (fra [...])
        new_ver     - ny version (første token efter '(')
        source_repo - repo-base-URL (andet token efter '(', uden port)
        security    - True hvis "security" optræder i linjen
    """
    updates: list[dict] = []
    security_count = 0
    # Regex: Inst <name> [<old_ver>] (<new_ver> <repo>[:port] [<arch>])
    # Alle felter undtagen name er valgfrie
    _re_inst = re.compile(
        r"^Inst\s+(\S+)"         # 1: pakkenavn
        r"(?:\s+\[([^\]]*)\])?"  # 2: gammel version (valgfri)
        r"(?:\s+\((\S+)"         # 3: ny version (valgfri)
        r"\s+(\S+)"              # 4: repo-URL inkl. evt. :port (trimmes nedenfor)
        r")?",
        re.IGNORECASE
    )
    try:
        result = subprocess.run(
            ["apt-get", "-s", "--just-print", "upgrade"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line.startswith("Inst "):
                    continue
                m = _re_inst.match(line)
                if not m:
                    continue
                name    = m.group(1)
                old_ver = m.group(2) or ""
                new_ver = m.group(3) or ""
                repo    = m.group(4) or ""
                is_sec  = "security" in line.lower()
                # Rens repo: strip port (":443", ":80") fra slutningen
                repo = re.sub(r":\d+$", "", repo)
                # Tilføj https:// hvis det er et tomt hostname-format
                if repo and not repo.startswith("http"):
                    repo = f"https://{repo}"
                updates.append({
                    "name":        name,
                    "old_ver":     old_ver,
                    "new_ver":     new_ver,
                    "source_repo": repo,
                    "security":    is_sec,
                })
                if is_sec:
                    security_count += 1
    except Exception as exc:
        log.debug("apt_updates_available fejl: %s", exc)
    return {
        "total":    len(updates),
        "security": security_count,
        "packages": updates[:200],  # max 200 pakker for at holde payloaden lille
    }


def _git_env() -> dict:
    """Git-miljø der tillader root at læse repos ejet af anden bruger."""
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    return env


def _git_app_version() -> Optional[str]:
    """Aktuel git-commit af /opt/timelapse (kort SHA)."""
    try:
        result = subprocess.run(
            ["git", "-C", "/opt/timelapse", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, env=_git_env()
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _git_app_tag() -> Optional[str]:
    """Seneste git-tag på HEAD i /opt/timelapse."""
    try:
        result = subprocess.run(
            ["git", "-C", "/opt/timelapse", "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True, text=True, timeout=10, env=_git_env()
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _artifact_release_metadata() -> dict[str, str]:
    """Read the release identity written after a verified artifact install.

    Artifact deployment deliberately copies files without changing the local Git
    checkout. Git HEAD therefore describes the checkout, not necessarily the
    running code. This small, non-secret receipt is the CMDB source of truth.
    """
    try:
        raw = json.loads(RELEASE_METADATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(raw, dict) or raw.get("schema") != "timelapse.edge.release.v1":
        return {}
    return {
        key: str(raw[key]).strip()
        for key in ("artifact_id", "source_commit", "version", "installed_at")
        if raw.get(key) is not None and str(raw[key]).strip()
    }


def current_app_version() -> str:
    """Best-known identity of the code actually running on this device.

    Shared by collect_inventory() (daily /api/inventory report) and the
    agent's own consolidated sync poll (POST /api/edge/sync, every
    sync_poll_interval_minutes — see edge/agent.py::_run_sync()) so Headend's
    app-update auto-detection (_process_update_report) has a real app_version
    to compare against on every poll, not just once a day. See
    Dokumentation/HANDOVER_LOG.md 2026-08-19 for the incident this closes:
    heartbeat never carried an "updates" block at all, so a newer Headend
    release was never auto-detected outside of a manual DB insert.
    """
    release = _artifact_release_metadata()
    git_commit = _git_app_version()
    git_tag    = _git_app_tag()
    return release.get("source_commit") or release.get("version") or git_tag or git_commit or APP_VERSION


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
    data_path = config.get("storage", {}).get("base_dir", "/data")
    data_type, data_gb, data_pct = _storage_info(data_path) if Path(data_path).exists() else (None, None, None)
    package_manager, os_packages = _os_packages()

    # A verified artifact receipt takes precedence over Git. Artifact installs
    # intentionally do not mutate the Edge checkout's Git HEAD. The raw pieces
    # are also reported individually below (software["git_commit"], etc.), so
    # they're kept alongside current_app_version()'s precedence result.
    release = _artifact_release_metadata()
    git_commit = _git_app_version()
    git_tag    = _git_app_tag()
    app_ver    = current_app_version()

    # Bruger + services (ikke-blokerende)
    local_users: list[dict] = []
    sudo_users:  list[str]  = []
    services:    list[dict] = []
    enabled_services: list[str] = []
    apt_updates: dict       = {}
    try:
        local_users = _local_users()
    except Exception as exc:
        log.debug("_local_users fejl: %s", exc)
    try:
        sudo_users = _sudo_users()
    except Exception as exc:
        log.debug("_sudo_users fejl: %s", exc)
    try:
        services = _systemd_services()
    except Exception as exc:
        log.debug("_systemd_services fejl: %s", exc)
    try:
        enabled_services = _enabled_service_names()
    except Exception as exc:
        log.debug("_enabled_service_names fejl: %s", exc)
    try:
        apt_updates = _apt_updates_available()
    except Exception as exc:
        log.debug("_apt_updates_available fejl: %s", exc)

    software = _software_inventory()
    software["timelapse_pro"] = app_ver
    software["git_commit"] = git_commit
    software["git_tag"]    = git_tag
    if release:
        software["release_artifact_id"] = release.get("artifact_id", "")
        software["release_installed_at"] = release.get("installed_at", "")

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
        "app_version":              app_ver,
        "release_artifact_id":      release.get("artifact_id"),
        "release_source_commit":    release.get("source_commit"),
        "release_installed_at":     release.get("installed_at"),
        "git_commit":               git_commit,
        "git_tag":                  git_tag,
        "package_manager":          package_manager,
        "os_packages":              os_packages,
        "venv_packages":            _venv_packages(),
        "software_inventory":       software,

        # Tilgængelige OS-opdateringer (fra apt-cache)
        "os_updates_available":     apt_updates,

        # Lokale brugere og adgangsrettigheder
        "local_users":              local_users,
        "sudo_users":               sudo_users,

        # Systemd services
        "services":                 services,
        "enabled_services":         enabled_services,

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

def report_inventory(config: dict, api_client, extra: dict | None = None) -> None:
    """
    Samler inventar og sender det til headend.
    Ikke-blokerende: fejl logges og ignoreres.

    extra: valgfri dict der merges ind i payload (bruges til HAL-capabilities).

    Kaldes fra agent._startup():
        from utils.inventory import report_inventory
        report_inventory(self._cfg, self._api, extra={"hal": hal_caps})
    """
    device_id = config.get("device", {}).get("device_id", "unknown")
    log.info("Inventar-rapportering starter for %s", device_id)

    try:
        payload = collect_inventory(config)

        # Merge ekstra data (HAL capabilities, etc.)
        if extra:
            for k, v in extra.items():
                payload[k] = v

        # Tilføj hardware_model fra HAL hvis ikke allerede sat af collect_inventory
        if extra and "hal" in extra and not payload.get("hardware_model"):
            payload["hardware_model"] = extra["hal"].get("hal_id")

        log.debug("Inventar samlet: hw=%s soc=%s os=%s hal=%s",
                  payload.get("hardware_model"),
                  payload.get("soc_model"),
                  payload.get("os_name"),
                  payload.get("hal", {}).get("hal_id") if isinstance(payload.get("hal"), dict) else None)

        ok, resp = api_client._post(f"/inventory/{device_id}", payload)
        if ok:
            log.info("Inventar rapporteret til headend: %s", device_id)
        else:
            log.warning("Inventar-rapportering fejlede (headend svarede ikke): %s", resp)

    except Exception as exc:
        # Aldrig blokér agent-startup pga. inventar
        log.warning("Inventar-rapportering fejlede (uventet): %s", exc)
