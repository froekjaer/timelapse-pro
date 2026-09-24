"""Golden Edge Baseline — the minimum an Edge image must provide from a fresh
boot, with no dependency on a subsequent app-update, to be considered a
reproducible, deployable device.

Built 2026-09-24 during P0/P1 closure ahead of the Travbyen deployment, after
independent verification (two research passes plus a concurrent z.ai audit,
cross-checked live against TL-C87FF9587CA0/TL-043EB9E72EFD) found that the
builder silently produced images missing NetworkManager, chrony, the
timesync/watchdog services, and the totp-service.py's own Python
dependencies (fastapi/uvicorn/pyotp) — each of those only ever "worked" on
the two physical edges because someone had patched the live device by hand,
never once producible by re-running the pipeline. See
Dokumentation/HANDOVER_LOG.md, 2026-09-24 entry, for the full evidence trail.

This module is deliberately a manifest, not a policy engine: it lists what
MUST be true, and `verify_golden_edge_baseline()` checks real build output
(actual dpkg/pip package lists and the actual rootfs tar contents) against
it — not source-code strings, which can drift from what a build truly
produces.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

# OS packages a fresh image must have installed for first-boot capabilities
# that must not depend on a later app-update.
GOLDEN_EDGE_REQUIRED_OS_PACKAGES: tuple[str, ...] = (
    "network-manager",   # WiFi client connectivity
    "chrony",            # NTP fallback; hard dependency of sync-time.sh
    "gphoto2",           # camera capture
    "bluez",             # Bluetooth/BLE technician transport
    "avahi-daemon",      # mDNS discovery
    "hostapd",           # WiFi AP fallback
    "dnsmasq",           # Bluetooth PAN DHCP/DNS + AP fallback
    "gpsd",              # GPS time reference
    "openssh-server",    # remote management/tunnel
)

# Python (venv) packages required for first-boot capabilities. Missing any of
# these means the corresponding service crash-loops from boot until an app
# update happens to install it into the persistent venv.
GOLDEN_EDGE_REQUIRED_PIP_PACKAGES: tuple[str, ...] = (
    "pyyaml",
    "requests",
    "paramiko",
    "cryptography",
    "qrcode",
    "fastapi",   # local technician TOTP portal (totp-service.py)
    "uvicorn",   # ^ serves it
    "pyotp",     # ^ generates/verifies the TOTP codes themselves
)

# systemd units that must exist in the rootfs tar's /etc/systemd/system/,
# regardless of whether they're statically enabled at flash time or
# dynamically enabled post-enrollment (timelapse-edge.service and
# timelapse-bootstrap.service are enabled dynamically by design — see
# edge/scripts/bootstrap_agent.py — but the unit files themselves must still
# ship in every image).
GOLDEN_EDGE_REQUIRED_SYSTEMD_UNITS: tuple[str, ...] = (
    "timelapse-edge.service",
    "timelapse-bootstrap.service",
    "timelapse-bt-pan.service",
    "timelapse-bt-agent.service",
    "timelapse-ble-technician.service",
    "timelapse-captive.service",
    "timelapse-wifi-ap.service",
    "timelapse-totp.service",
    "timelapse-timesync.service",
    "timelapse-timesync.timer",
    "timelapse-watchdog.service",
)

# Non-systemd-unit files that must exist in the rootfs tar at these exact
# paths for first-boot capabilities that must not depend on a later
# app-update (GPIO relay permissions, agent self-restart sudo).
GOLDEN_EDGE_REQUIRED_FILES: tuple[str, ...] = (
    "etc/udev/rules.d/99-timelapse-gpio.rules",
    "etc/sudoers.d/timelapse-edge",
)


def _normalized_names(packages: list[dict], key: str) -> set[str]:
    return {str(p.get(key, "")).strip().lower() for p in packages if p.get(key)}


def _tar_members(rootfs_tar_path: Path) -> set[str]:
    with tarfile.open(rootfs_tar_path, "r:gz") as tar:
        return set(tar.getnames())


def verify_golden_edge_baseline(
    sbom_packages: list[dict],
    pip_packages: list[dict],
    rootfs_tar_path: Path,
) -> list[str]:
    """Check real build output against the Golden Edge Baseline.

    Returns a list of human-readable violation messages — empty means the
    baseline is satisfied. Never raises itself; the caller decides whether a
    non-empty result should fail the build (build_edge_disk_image.py does).
    """
    violations: list[str] = []

    os_names = _normalized_names(sbom_packages, "name")
    for pkg in GOLDEN_EDGE_REQUIRED_OS_PACKAGES:
        if pkg.lower() not in os_names:
            violations.append(f"OS package missing from built image: {pkg}")

    pip_names = _normalized_names(pip_packages, "name")
    for pkg in GOLDEN_EDGE_REQUIRED_PIP_PACKAGES:
        if pkg.lower() not in pip_names:
            violations.append(f"Python (venv) package missing from built image: {pkg}")

    tar_members = _tar_members(rootfs_tar_path)

    def _in_tar(path: str) -> bool:
        return path in tar_members or f"./{path}" in tar_members

    for unit in GOLDEN_EDGE_REQUIRED_SYSTEMD_UNITS:
        expected_path = f"etc/systemd/system/{unit}"
        if not _in_tar(expected_path):
            violations.append(f"systemd unit missing from rootfs tar: {unit}")

    for required_file in GOLDEN_EDGE_REQUIRED_FILES:
        if not _in_tar(required_file):
            violations.append(f"required file missing from rootfs tar: {required_file}")

    return violations
