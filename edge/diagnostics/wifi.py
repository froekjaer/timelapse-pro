"""
TimeLapse Pro — WiFi Manager
Bruges af lab mode til at scanne, tilslutte og administrere WiFi netværk.
Kræver nmcli (NetworkManager) — kører som root via systemd service.
"""
from __future__ import annotations
import logging
import subprocess
import re
from typing import Optional

log = logging.getLogger(__name__)

def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -1, "", str(exc)

def scan() -> list[dict]:
    """Scan for available WiFi networks."""
    # Refresh scan
    _run(["nmcli", "device", "wifi", "rescan"], timeout=8)
    import time as _time; _time.sleep(2)  # Vent på scan
    rc, out, err = _run([
        "nmcli", "--escape", "no", "-t", "-f",
        "IN-USE,BSSID,SSID,MODE,CHAN,RATE,SIGNAL,SECURITY",
        "device", "wifi", "list"
    ], timeout=15)
    if rc != 0:
        log.warning("WiFi scan failed: %s", err)
        return []

    networks = []
    seen_ssids = set()
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 8:
            continue
        in_use   = parts[0] == "*"
        bssid    = ":".join(parts[1:3])   # BSSID er altid AA:BB format
        # Med --escape no er felterne: IN-USE:BSSID(6 dele):SSID:MODE:CHAN:RATE:SIGNAL:SECURITY
        # BSSID fylder 5 kolon-separerede dele ekstra
        # Lad os bruge simpel approach med field splitting
        # nmcli format: *:30:68:93:19:E5:79:p-froekjaer:Infra:40:270 Mbit/s:82:WPA2 WPA3
        if len(parts) < 12:
            continue
        in_use   = parts[0] == "*"
        bssid    = ":".join(parts[1:7])
        ssid     = parts[7]
        chan     = parts[9]
        signal   = int(parts[11]) if parts[11].isdigit() else 0
        security = parts[12] if len(parts) > 12 else ""

        if not ssid or ssid in seen_ssids:
            continue
        seen_ssids.add(ssid)

        networks.append({
            "ssid":     ssid,
            "bssid":    bssid,
            "in_use":   in_use,
            "channel":  chan,
            "signal":   signal,
            "bars":     _signal_bars(signal),
            "security": security,
            "saved":    False,  # set later
        })

    # Mark saved networks
    saved = list_saved()
    saved_ssids = {n["ssid"] for n in saved}
    for n in networks:
        n["saved"] = n["ssid"] in saved_ssids

    return sorted(networks, key=lambda x: -x["signal"])

def status() -> dict:
    """Get current WiFi connection status."""
    rc, out, err = _run([
        "nmcli", "-t", "-f",
        "DEVICE,TYPE,STATE,CONNECTION,CON-PATH",
        "device"
    ])
    wifi_dev = None
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[1] == "wifi":
            wifi_dev = {
                "device":     parts[0],
                "state":      parts[2],
                "connection": parts[3],
                "connected":  parts[2] == "connected",
            }
            break

    if not wifi_dev:
        return {"connected": False, "device": "unknown"}

    # Get IP if connected
    if wifi_dev["connected"]:
        rc2, out2, _ = _run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", wifi_dev["device"]])
        for line in out2.splitlines():
            if line.startswith("IP4.ADDRESS"):
                wifi_dev["ip"] = line.split(":")[1].split("/")[0]
                break

        # Get signal strength
        rc3, out3, _ = _run(["nmcli", "-t", "-f", "IN-USE,SIGNAL,SSID", "device", "wifi", "list"])
        for line in out3.splitlines():
            parts = line.split(":")
            if parts[0] == "*" and len(parts) >= 3:
                wifi_dev["signal"]  = int(parts[1]) if parts[1].isdigit() else 0
                wifi_dev["ssid"]    = parts[2]
                wifi_dev["bars"]    = _signal_bars(int(parts[1]) if parts[1].isdigit() else 0)
                break

    return wifi_dev

def connect(ssid: str, password: str = "") -> dict:
    """Connect to a WiFi network."""
    # Check if already saved
    saved = list_saved()
    already_saved = any(n["ssid"] == ssid for n in saved)

    if already_saved and not password:
        # Just activate existing connection
        rc, out, err = _run(["nmcli", "connection", "up", ssid], timeout=30)
    elif password:
        rc, out, err = _run([
            "nmcli", "device", "wifi", "connect", ssid,
            "password", password
        ], timeout=30)
    else:
        # Open network
        rc, out, err = _run([
            "nmcli", "device", "wifi", "connect", ssid
        ], timeout=30)

    success = rc == 0 and "successfully" in out.lower()
    return {
        "success": success,
        "ssid":    ssid,
        "message": out if success else err,
    }

def forget(ssid: str) -> dict:
    """Remove a saved WiFi network."""
    rc, out, err = _run(["nmcli", "connection", "delete", ssid])
    return {"success": rc == 0, "ssid": ssid}

def list_saved() -> list[dict]:
    """List saved WiFi connections."""
    rc, out, err = _run([
        "nmcli", "-t", "-f", "NAME,TYPE,DEVICE",
        "connection", "show"
    ])
    saved = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            saved.append({
                "ssid":   parts[0],
                "device": parts[2] if len(parts) > 2 else "",
                "active": bool(parts[2]) if len(parts) > 2 else False,
            })
    return saved

def _signal_bars(signal: int) -> str:
    if signal >= 80: return "▂▄▆█"
    if signal >= 60: return "▂▄▆_"
    if signal >= 40: return "▂▄__"
    if signal >= 20: return "▂___"
    return "____"
