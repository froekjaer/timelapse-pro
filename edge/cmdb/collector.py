# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — edge/cmdb/collector.py
# Version  : 1.0.0   |   12. juni 2026
# ───────────────────────────────────────────────────────────────────────────
# Edge CMDB-collector: indsamler installeret OS/apt/pip/git-inventory på
# Orange Pi (Ubuntu noble arm64) og opdager tilgængelige apt-opdateringer.
# Resultatet sendes til headend via heartbeat (embed) eller dedikeret POST.
# ═══════════════════════════════════════════════════════════════════════════
"""Edge-collector. Designet til at være billig nok til at køre 1×/heartbeat.

apt-listen er den dyre del; den caches og genberegnes maks. hver N. time.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger("cmdb.collector")

REPO_DIR = "/opt/timelapse"
_CACHE_PATH = Path("/run/timelapse/cmdb_inventory.json")
_CACHE_TTL = 6 * 3600  # 6 timer
_CMD_TIMEOUT = 60


def _run(cmd: list[str], timeout: int = _CMD_TIMEOUT) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""
    except Exception as exc:
        log.debug("cmd-fejl %s: %s", cmd, exc)
        return 1, ""


def _os_info() -> list[dict]:
    items = []
    # OS-version fra /etc/os-release
    ver, pretty = "", ""
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("VERSION_ID="):
                ver = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("PRETTY_NAME="):
                pretty = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    # Kerne
    rc, kver = _run(["uname", "-r"], timeout=5)
    arch = ""
    rc2, a = _run(["dpkg", "--print-architecture"], timeout=5)
    if rc2 == 0:
        arch = a.strip()
    items.append({"kind": "os", "name": "ubuntu", "installed_ver": ver or pretty,
                  "source": "system", "architecture": arch or "arm64"})
    if kver:
        items.append({"kind": "os_package", "name": "linux-kernel",
                      "installed_ver": kver.strip(), "source": "apt",
                      "architecture": arch or "arm64"})
    return items


def _app_info() -> list[dict]:
    rc, out = _run(["git", "-C", REPO_DIR, "rev-parse", "--short", "HEAD"], timeout=15)
    if rc == 0 and out.strip():
        return [{"kind": "application", "name": "timelapse-edge",
                 "installed_ver": out.strip(), "source": "git",
                 "architecture": "noarch"}]
    return []


def _apt_installed() -> list[dict]:
    """Liste over manuelt installerede apt-pakker (ikke hele dybden)."""
    rc, out = _run(["apt-mark", "showmanual"], timeout=_CMD_TIMEOUT)
    names = [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []
    items = []
    if names:
        rc2, ver_out = _run(["dpkg-query", "-W", "-f=${Package}\t${Version}\n"] + names,
                            timeout=_CMD_TIMEOUT)
        if rc2 == 0:
            for line in ver_out.splitlines():
                if "\t" in line:
                    name, ver = line.split("\t", 1)
                    items.append({"kind": "os_package", "name": name.strip(),
                                  "installed_ver": ver.strip(), "source": "apt",
                                  "architecture": "arm64"})
    return items


def _pip_installed() -> list[dict]:
    rc, out = _run(["python3", "-m", "pip", "list", "--format=json"], timeout=_CMD_TIMEOUT)
    items = []
    if rc == 0:
        try:
            for pkg in json.loads(out):
                items.append({"kind": "python_package", "name": pkg["name"],
                              "installed_ver": pkg["version"], "source": "pip",
                              "architecture": "noarch"})
        except Exception:
            pass
    return items


def _apt_updates() -> dict[str, tuple[str, bool]]:
    """Returnér {pakke: (ny_version, er_security)} fra apt.

    Kører IKKE apt-get update (det styres separat/af apt-proxy) — bruger den
    cache der allerede findes, så collector aldrig hænger på netværk.
    """
    out_map: dict[str, tuple[str, bool]] = {}
    rc, out = _run(["apt-get", "-s", "upgrade"], timeout=_CMD_TIMEOUT)
    if rc != 0:
        return out_map
    for line in out.splitlines():
        # "Inst openssl [1.1] (1.2 Ubuntu:24.04/noble-security [arm64])"
        if line.startswith("Inst "):
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                is_sec = "security" in line.lower()
                newver = ""
                if "(" in line:
                    seg = line.split("(", 1)[1]
                    newver = seg.split()[0]
                out_map[name] = (newver, is_sec)
    return out_map


def collect(force: bool = False) -> dict:
    """Saml fuld inventory. Bruger cache hvis < TTL og ikke force."""
    if not force and _CACHE_PATH.exists():
        try:
            age = time.time() - _CACHE_PATH.stat().st_mtime
            if age < _CACHE_TTL:
                return json.loads(_CACHE_PATH.read_text())
        except Exception:
            pass

    items: list[dict] = []
    items += _os_info()
    items += _app_info()
    items += _apt_installed()
    items += _pip_installed()

    # Markér tilgængelige apt-opdateringer
    updates = _apt_updates()
    for it in items:
        if it["source"] == "apt" and it["name"] in updates:
            newver, is_sec = updates[it["name"]]
            it["available_ver"] = newver
            it["update_available"] = True

    payload = {"items": items, "collected_at": time.time(),
               "apt_security_count": sum(1 for v in updates.values() if v[1])}
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(payload))
    except Exception:
        pass
    return payload
