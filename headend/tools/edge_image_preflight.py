#!/usr/bin/env python3
"""Fail-closed preflight of an Edge rootfs before disk-image injection.

This tool is Headend-side only. It checks the archive actually contains the
mandatory application paths the injector is expected to transfer. It cannot
prove the vendor base image boots, nor that services start on hardware.
"""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

REQUIRED_PATHS = (
    "opt/timelapse/edge/agent.py",
    "opt/timelapse/edge/update_lifecycle.py",
    "opt/timelapse/edge/scripts/totp-service.py",
    "opt/timelapse/venv/bin/python",
    "etc/systemd/system/timelapse-edge.service",
    "etc/systemd/system/timelapse-bootstrap.service",
    "etc/systemd/system/timelapse-totp.service",
    "etc/systemd/system/timelapse-watchdog.service",
    "etc/systemd/system/timelapse-timesync.timer",
    "etc/systemd/system/timelapse-system-baseline.service",
)


def inspect_rootfs(path: Path) -> dict:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {member.name.removeprefix("./").lstrip("/"): member for member in archive}
    except (OSError, tarfile.TarError) as exc:
        return {"status": "BLOCK", "missing": list(REQUIRED_PATHS), "error": type(exc).__name__}
    missing = [name for name in REQUIRED_PATHS if name not in members]
    unsafe = [name for name, member in members.items() if name.startswith("../") or "/../" in name or member.isdev()]
    return {"status": "PASS_PREFLIGHT" if not missing and not unsafe else "BLOCK",
            "missing": missing, "unsafe": unsafe,
            "note": "Preflight only: verify actual injected image and physical boot separately."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rootfs", type=Path)
    args = parser.parse_args()
    result = inspect_rootfs(args.rootfs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS_PREFLIGHT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
