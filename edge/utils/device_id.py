"""
TimeLapse Pro — Device ID
=========================
Derives a stable Device ID from the built-in ethernet MAC address.

Format: TL-XXXXXXXXXXXX  (TL- prefix + 12 hex chars, uppercase)

Robust against:
  - USB WiFi adapters      (wlan* excluded)
  - USB ethernet dongles   (usb in sysfs path excluded)
  - Multiple interfaces    (prefers end0/eth0)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def _get_builtin_ethernet_mac() -> str:
    candidates = []

    for iface in sorted(os.listdir('/sys/class/net')):
        if iface == 'lo':
            continue
        if iface.startswith('wlan') or iface.startswith('wl'):
            continue

        iface_path = Path('/sys/class/net') / iface
        try:
            real_path = os.path.realpath(iface_path)
            if 'usb' in real_path.lower():
                log.debug("Skipping %s — USB interface", iface)
                continue
        except OSError:
            continue

        try:
            mac = (iface_path / 'address').read_text().strip()
            if mac and mac != '00:00:00:00:00:00':
                candidates.append((iface, mac))
                log.debug("Candidate: %s → %s", iface, mac)
        except OSError:
            continue

    if not candidates:
        raise RuntimeError("No built-in ethernet interface found for Device ID")

    for preferred in ('end0', 'eth0'):
        for iface, mac in candidates:
            if iface == preferred:
                log.info("Using %s MAC: %s", iface, mac)
                return mac

    iface, mac = candidates[0]
    log.info("Using %s MAC (fallback): %s", iface, mac)
    return mac


def get_device_id() -> str:
    """Returns Device ID as TL-XXXXXXXXXXXX."""
    mac = _get_builtin_ethernet_mac()
    clean = mac.replace(':', '').upper()
    device_id = f'TL-{clean}'
    log.info("Device ID: %s", device_id)
    return device_id


if __name__ == '__main__':
    print(get_device_id())
