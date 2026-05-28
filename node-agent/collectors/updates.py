from __future__ import annotations

import logging
import platform
import re
import subprocess

log = logging.getLogger(__name__)


def _run(cmd: list[str], timeout: int = 45) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def collect_available_updates(cfg) -> dict:
    """Collect host OS update signals without requiring inbound access."""
    payload = {
        "device_id": cfg.device_id,
        "os_security_count": 0,
        "os_updates_count": 0,
        "app_version": "2.8.0",
        "app_behind_commits": 0,
        "app_security": False,
    }

    if platform.system() == "Darwin":
        try:
            result = _run(["softwareupdate", "-l"], timeout=60)
            text = f"{result.stdout}\n{result.stderr}"
            items = [
                line.strip()
                for line in text.splitlines()
                if line.strip().startswith("*")
            ]
            security = [
                item for item in items
                if re.search(r"security|safari|rapid security response|xprotect|gatekeeper", item, re.I)
            ]
            payload["os_security_count"] = len(security)
            payload["os_updates_count"] = max(0, len(items) - len(security))
        except Exception as exc:
            log.debug("macOS softwareupdate scan fejlede: %s", exc)
        return payload

    try:
        result = _run(["apt", "list", "--upgradable"], timeout=30)
        lines = [line for line in result.stdout.splitlines() if "/" in line and "upgradable" in line]
        security = [line for line in lines if "security" in line.lower()]
        payload["os_security_count"] = len(security)
        payload["os_updates_count"] = max(0, len(lines) - len(security))
    except Exception as exc:
        log.debug("apt update scan fejlede: %s", exc)

    return payload
