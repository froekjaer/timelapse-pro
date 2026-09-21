"""TimeLapse Pro — deterministic Bluetooth device-name computation.

Builds the `DEVICE_NAME_SSID_IPV4` (or `DEVICE_NAME_CONNECTING`) name from a
hostname and an `edge.network_status.NetworkStatus`, for both:

- the *full* name (classic BR/EDR adapter Alias / inquiry name / GAP "Device
  Name" GATT characteristic, all of which are read via D-Bus properties or
  GATT after discovery, not squeezed into a single broadcast packet — BlueZ's
  Adapter1.Alias comfortably holds hundreds of bytes), and
- the *advertisement* name: the LE `LEAdvertisement1.LocalName` property that
  BlueZ broadcasts in the (legacy, non-extended) advertising/scan-response
  PDU. That PDU has a hard 31-byte payload budget shared with every other AD
  structure in the same advertisement (Flags, ServiceUUIDs, tx-power — see
  edge/scripts/ble-technician-gatt.py's Advertisement.GetAll). The prior code
  already truncated to 26 bytes (`os.uname().nodename[:26]`) as a conservative
  fit alongside those other structures; this module keeps that same
  evidence-based budget rather than inventing a new one, since verifying the
  exact spare-byte count (and whether the Orange Pi 4 Pro's BT chipset/BlueZ
  version even negotiates BT5 Extended Advertising, which relaxes this limit)
  requires physical hardware access this session doesn't have. See
  RUNTIME_VERIFICATION_NEEDED in HANDOVER_LOG.md for the follow-up.

Because of that hard budget, a full `hostname_ssid_ipv4` string frequently
will not fit in the advertisement name even before considering the SSID
(hostname + IPv4 alone can already exceed 26 bytes). Per the product
requirement ("device identity and IP must never become ambiguous"), the SSID
is the only component ever shortened or dropped for the advertisement name;
the hostname and IPv4 are always kept whole there. The *full* name (adapter
Alias / GATT Device Name) is never truncated by this module — a technician
who needs to disambiguate an over-long SSID can always read it there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from network_status import NetworkStatus

# Conservative fit alongside Flags + ServiceUUIDs + tx-power in a single
# legacy (31-byte) LE advertising/scan-response PDU. See module docstring.
ADVERTISEMENT_NAME_MAX_BYTES = 26

_SANITIZE_DISALLOWED = re.compile(r"[^A-Za-z0-9._-]+")
_SANITIZE_COLLAPSE = re.compile(r"[-_]{2,}")


@dataclass(frozen=True)
class BluetoothNames:
    full: str
    advertisement: str


def sanitize_ssid(ssid: str) -> str:
    """Deterministically map an arbitrary SSID (spaces, unicode, punctuation,
    control characters) to a safe token for a Bluetooth name component.

    Not reversible and not required to be — only required to be safe and
    deterministic (same SSID always sanitizes the same way) so a technician
    can recognise it.
    """
    # Strip control/non-printable characters before anything else.
    printable = "".join(ch for ch in ssid if ch.isprintable())
    replaced = _SANITIZE_DISALLOWED.sub("-", printable.strip())
    collapsed = _SANITIZE_COLLAPSE.sub("-", replaced).strip("-_")
    return collapsed or "unknown-ssid"


def _truncate_ssid_to_fit(hostname: str, ssid: str, ipv4: str, max_bytes: int) -> str:
    """Shrink only the SSID component so `hostname_ssid_ipv4` fits in
    `max_bytes`. Never shortens hostname or ipv4 — see module docstring.
    Falls back to a two-part `hostname_ipv4` name (still unambiguous) if the
    SSID has to be dropped entirely, and as a last resort marks the name as
    over-budget rather than silently truncating the IP.
    """
    fixed_len = len(hostname) + len(ipv4) + 2  # two separating underscores
    budget = max_bytes - fixed_len
    if budget <= 0:
        # Even the SSID-less form doesn't fit. Truncating hostname or IP
        # would make the device or its address ambiguous, which the product
        # requirement explicitly forbids — so this module intentionally does
        # not fit anything here rather than guess. Emit the full two-part
        # name; the caller is responsible for handling the (measured, logged)
        # over-length case at the transport layer if it ever occurs.
        return f"{hostname}_{ipv4}"
    if len(ssid) <= budget:
        return f"{hostname}_{ssid}_{ipv4}"
    return f"{hostname}_{ssid[:budget]}_{ipv4}"


def compute_bluetooth_names(hostname: str, status: NetworkStatus) -> BluetoothNames:
    """Compute both the full and advertisement-safe Bluetooth names for the
    given hostname and current network status.
    """
    hostname = sanitize_ssid(hostname) or "device"

    if status.mode in ("wifi_client", "ap") and status.has_usable_ip and status.ssid:
        ssid = sanitize_ssid(status.ssid)
        full = f"{hostname}_{ssid}_{status.ipv4}"
        advertisement = full
        if len(full.encode("utf-8")) > ADVERTISEMENT_NAME_MAX_BYTES:
            advertisement = _truncate_ssid_to_fit(
                hostname, ssid, status.ipv4, ADVERTISEMENT_NAME_MAX_BYTES
            )
        return BluetoothNames(full=full, advertisement=advertisement)

    # "connecting" and "none" both render as the same deterministic
    # transitional name — see edge/network_status.py's NetworkStatus.mode
    # docstring for why they're kept distinct internally (logging/metrics)
    # even though the product requirement only calls for one visible label.
    connecting_name = f"{hostname}_CONNECTING"
    if len(connecting_name.encode("utf-8")) <= ADVERTISEMENT_NAME_MAX_BYTES:
        advertisement = connecting_name
    else:
        # Same priority as the connected case: the hostname (device
        # identity) is never shortened, only the fixed "CONNECTING" label.
        budget = ADVERTISEMENT_NAME_MAX_BYTES - len(hostname) - 1
        advertisement = f"{hostname}_{'CONNECTING'[:budget]}" if budget > 0 else hostname[:ADVERTISEMENT_NAME_MAX_BYTES]
    return BluetoothNames(full=connecting_name, advertisement=advertisement)
