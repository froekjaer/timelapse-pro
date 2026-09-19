"""TimeLapse Pro — canonical network-status service.

Single authoritative answer to "what interface/SSID/IPv4 is the Edge's current
management path actually using right now" — Wi-Fi client, this device's own
autonomous fallback AP, wired ethernet, a transitional/associating state, or
none. Consumers (Bluetooth advertisement naming, the technician portal, the
technician CLI) are adapters over this module; they must not reimplement
interface/SSID/IP discovery themselves.

Context (see HANDOVER_LOG.md 2026-09-19): before this module existed, at
least four call sites independently reimplemented interface/SSID/IP
discovery for different purposes (edge/service_operations.py::network_status
— raw diagnostic dump for the BLE technician session; edge/diagnostics/wifi.py
— LAB wifi_scan/wifi_connect/wifi_forget headend commands; edge/utils/
inventory.py — CMDB/heartbeat primary-interface detection; edge/tools/
bootstrap_cli.py::print_network_status — raw nmcli/ip dump for the technician
CLI). None of those were changed by this module: they serve established,
already-wired call sites (agent heartbeat, LAB commands, BLE diagnostics) and
touching them was judged higher blast-radius than this feature warrants. This
module is the new, single source of truth for the *specific* question "what
SSID/IPv4 identifies the current management path" — the technician CLI's
`print_network_status()` now also prints this module's structured summary
line (see edge/tools/bootstrap_cli.py) alongside its existing raw dump, so
Bluetooth naming, the technician UI (which shells out to the same CLI via
`_run_tech_cli`) and the technician CLI all read the same computed answer.

Deliberately excludes: docker*, veth*, br-*  (incl. the BT-PAN bridge
br-bt — that is a *transport*, not a network with an SSID/IP of its own),
tun*/tap*, wg*, tailscale*, virbr*, cni*/flannel* and loopback. Only real
Wi-Fi-capable interfaces are considered, since only Wi-Fi (client or this
device's own AP) has an SSID; a future ethernet-primary mode would report
mode="ethernet" with ssid=None (not currently exercised by any known Edge
hardware profile, but kept for forward compatibility).
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_EXCLUDED_IFACE_PREFIXES = (
    "lo",
    "docker",
    "veth",
    "br-",
    "tun",
    "tap",
    "wg",
    "tailscale",
    "virbr",
    "cni",
    "flannel",
)

# Autonomous-AP hostapd config locations, in priority order. The bash fallback
# AP (edge/scripts/timelapse-wifi-ap.sh) writes its live config here; kept as
# a tuple so tests/future refactors can point at a fixture path.
_HOSTAPD_CONF_CANDIDATES = (
    Path("/run/timelapse/wifi-ap/hostapd.conf"),
)

_IPV4_RE = re.compile(r"inet (\d{1,3}(?:\.\d{1,3}){3})/")
_IW_TYPE_RE = re.compile(r"\btype (\w+)")
_IW_SSID_RE = re.compile(r"SSID:\s*(.+)")


@dataclass(frozen=True)
class NetworkStatus:
    """The Edge's current management-path network state."""

    mode: str  # "wifi_client" | "ap" | "ethernet" | "connecting" | "none"
    interface: str | None
    ssid: str | None
    ipv4: str | None
    connected: bool
    checked_at: float

    @property
    def has_usable_ip(self) -> bool:
        return bool(self.connected and self.ipv4)


def _run(cmd: list[str], timeout: float = 3.0) -> str:
    """Best-effort shell out. Never raises — callers must be able to reason
    about missing tools/permissions without crashing anything else, in
    particular the capture plane, which never calls into this module."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout or ""
    except Exception:
        return ""


def _is_candidate_iface(name: str) -> bool:
    return not any(name.startswith(prefix) for prefix in _EXCLUDED_IFACE_PREFIXES)


def _wifi_interfaces(sys_class_net: Path = Path("/sys/class/net")) -> list[str]:
    """Real, non-virtual Wi-Fi-capable interfaces, deterministically ordered."""
    if not sys_class_net.is_dir():
        return []
    found = []
    for entry in sorted(sys_class_net.iterdir(), key=lambda p: p.name):
        name = entry.name
        if not _is_candidate_iface(name):
            continue
        if (entry / "wireless").exists() or name.startswith(("wl", "wlan")):
            found.append(name)
    return found


def _ipv4_for_interface(iface: str) -> str | None:
    out = _run(["ip", "-4", "-o", "addr", "show", iface])
    match = _IPV4_RE.search(out)
    return match.group(1) if match else None


def _iface_type(iface: str) -> str | None:
    """'managed' (Wi-Fi client / station) or 'AP', via `iw dev <iface> info`."""
    out = _run(["iw", "dev", iface, "info"])
    match = _IW_TYPE_RE.search(out)
    return match.group(1) if match else None

def _client_ssid(iface: str) -> str | None:
    out = _run(["iw", "dev", iface, "link"])
    if "Not connected" in out:
        return None
    match = _IW_SSID_RE.search(out)
    return match.group(1).strip() if match else None


def _ap_ssid(hostapd_conf_paths: tuple[Path, ...] = _HOSTAPD_CONF_CANDIDATES) -> str | None:
    for conf_path in hostapd_conf_paths:
        try:
            for line in conf_path.read_text().splitlines():
                if line.startswith("ssid="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            continue
    return None


def get_network_status(
    wifi_iface: str | None = None,
    *,
    sys_class_net: Path = Path("/sys/class/net"),
    hostapd_conf_paths: tuple[Path, ...] = _HOSTAPD_CONF_CANDIDATES,
) -> NetworkStatus:
    """Return the current management-path network status.

    `wifi_iface` / `sys_class_net` / `hostapd_conf_paths` are injectable for
    tests; production callers should use the defaults.
    """
    now = time.time()
    candidates = [wifi_iface] if wifi_iface else _wifi_interfaces(sys_class_net)

    for iface in candidates:
        if not iface:
            continue
        itype = _iface_type(iface)
        ipv4 = _ipv4_for_interface(iface)

        if itype == "AP":
            ssid = _ap_ssid(hostapd_conf_paths)
            if ipv4:
                return NetworkStatus("ap", iface, ssid, ipv4, True, now)
            return NetworkStatus("connecting", iface, ssid, None, False, now)

        if itype == "managed":
            ssid = _client_ssid(iface)
            if ssid and ipv4:
                return NetworkStatus("wifi_client", iface, ssid, ipv4, True, now)
            if ssid or itype:
                # Associated-but-no-IP, or interface up but not yet associated:
                # a real transitional state, not "no network at all".
                return NetworkStatus("connecting", iface, ssid, None, False, now)

    return NetworkStatus("none", None, None, None, False, now)
