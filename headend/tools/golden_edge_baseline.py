"""Golden Edge build-output verification (Headend only).

Checks actual SBOM and rootfs contents; does not modify Edge devices.
This intentionally does not assert that a source manifest proves a successful
first boot or that network-manager is universally required by every target.
"""
from __future__ import annotations

import tarfile
from pathlib import Path

REQUIRED_PIP = ("pyyaml", "requests", "paramiko", "cryptography", "fastapi", "uvicorn", "pyotp")
REQUIRED_UNITS = (
    "timelapse-edge.service", "timelapse-bootstrap.service",
    "timelapse-bt-pan.service", "timelapse-bt-agent.service",
    "timelapse-ble-technician.service", "timelapse-captive.service",
    "timelapse-wifi-ap.service", "timelapse-totp.service",
    "timelapse-timesync.service", "timelapse-timesync.timer",
    "timelapse-watchdog.service",
)


def _names(packages: list[dict]) -> set[str]:
    return {str(p.get("name", "")).strip().lower().replace("_", "-") for p in packages}


def verify_golden_edge_baseline(
    os_packages: list[dict], pip_packages: list[dict], rootfs_tar_path: Path,
    *, required_os: tuple[str, ...] = ("chrony", "gphoto2", "bluez", "gpsd", "openssh-server"),
) -> list[str]:
    """Return explicit violations. Missing/unreadable artifacts fail closed."""
    violations: list[str] = []
    os_names, pip_names = _names(os_packages), _names(pip_packages)
    for pkg in required_os:
        if pkg.lower() not in os_names:
            violations.append(f"missing OS package: {pkg}")
    for pkg in REQUIRED_PIP:
        if pkg.lower() not in pip_names:
            violations.append(f"missing venv package: {pkg}")
    try:
        with tarfile.open(rootfs_tar_path, "r:gz") as tar:
            names = {name.removeprefix("./").lstrip("/") for name in tar.getnames()}
    except (OSError, tarfile.TarError) as exc:
        return violations + [f"unreadable rootfs: {type(exc).__name__}"]
    for unit in REQUIRED_UNITS:
        if f"etc/systemd/system/{unit}" not in names:
            violations.append(f"missing systemd unit: {unit}")
    return violations
