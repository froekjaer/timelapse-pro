# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — edge/cmdb/executor.py
# ───────────────────────────────────────────────────────────────────────────
# DEPRECATED / IKKE I BRUG — 2026-06-14
#
# Denne fil er ikke tilsluttet og bruges ikke.
# Det autoritative edge-opdateringsflow er i agent.py:
#
#   EdgeAgent._check_and_apply_updates()
#     → GET /api/updates/policy/{device_id}
#     → EdgeAgent._run_update()
#       → _run_artifact_app_update()   (timelapse_* updates)
#       → _run_artifact_os_update()    (os_* updates via offline bundle)
#       → legacy git pull              (LAB: TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1)
#
# Artifact-flow:
#   Headend bygger signeret artifact (catalog-current / catalog-from-git-tag)
#   Admin godkender PendingUpdate
#   Edge poller policy, downloader via download_artifact_file()
#   SHA-256 verificeres fil-for-fil inden installation
#
# Filen beholdes midlertidigt for historik — kan slettes i næste sprint.
# ═══════════════════════════════════════════════════════════════════════════
"""DEPRECATED — se agent.py for det aktuelle opdateringsflow."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("cmdb.executor")

REPO_DIR = "/opt/timelapse"
PREV_REF = Path("/opt/timelapse/prev_ref")
GIT = "/usr/bin/git"


def _git_env() -> dict:
    env = os.environ.copy()
    env["HOME"] = "/home/orangepi"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    return env


def _run(cmd: list[str], env=None, timeout: int = 300) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           env=env, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as exc:
        return 1, "", str(exc)


# ── git-baserede opdateringer (timelapse / app_*) ──────────────────────────

def _apply_git(target_version: str) -> tuple[bool, str, str]:
    """git pull til target_version (eller origin/main). Returnerer (ok, ver, msg)."""
    env = _git_env()
    rc, current, _ = _run([GIT, "-C", REPO_DIR, "rev-parse", "HEAD"], env=env, timeout=30)
    current = current.strip()

    rc, _, err = _run([GIT, "-C", REPO_DIR, "fetch", "origin", "main", "--quiet"],
                      env=env, timeout=120)
    if rc != 0:
        return False, current[:7], f"fetch fejlede: {err.strip()}"

    rc, remote, _ = _run([GIT, "-C", REPO_DIR, "rev-parse", "origin/main"],
                         env=env, timeout=30)
    remote = remote.strip()
    if current == remote:
        return True, current[:7], "allerede opdateret"

    # Gem rollback-punkt
    try:
        PREV_REF.write_text(current)
    except Exception:
        pass

    rc, _, err = _run([GIT, "-C", REPO_DIR, "pull", "origin", "main", "--quiet"],
                      env=env, timeout=180)
    if rc != 0:
        return False, current[:7], f"pull fejlede: {err.strip()}"

    _run(["find", f"{REPO_DIR}/edge", "-name", "__pycache__",
          "-exec", "rm", "-rf", "{}", "+"], timeout=30)
    rc, newhead, _ = _run([GIT, "-C", REPO_DIR, "rev-parse", "HEAD"], env=env, timeout=30)
    return True, newhead.strip()[:7], f"opdateret {current[:7]} → {newhead.strip()[:7]}"


# ── apt-baserede opdateringer (os_security / os_update) ────────────────────

def _apply_apt(components: list[dict]) -> tuple[bool, str, str]:
    """Installér navngivne apt-pakker non-interactive.

    Forudsætter at apt allerede peger på apt-proxy (headend) for .deb-filer,
    så ingen direkte internetadgang kræves fra edge.
    """
    names = [c["name"] for c in components if c.get("kind") in ("os_package", "os")]
    if not names:
        return True, "", "ingen apt-komponenter"
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    # apt-get update mod proxy
    _run(["apt-get", "update", "-qq"], env=env, timeout=180)
    rc, out, err = _run(
        ["apt-get", "install", "-y", "--only-upgrade",
         "-o", "Dpkg::Options::=--force-confold"] + names,
        env=env, timeout=600)
    if rc != 0:
        return False, "", f"apt fejlede: {err.strip()[:300]}"
    return True, "", f"apt opgraderede {len(names)} pakker"


# ── Rollback ───────────────────────────────────────────────────────────────

def rollback_git() -> tuple[bool, str]:
    if not PREV_REF.exists():
        return False, "ingen rollback-reference"
    prev = PREV_REF.read_text().strip()
    if not prev:
        return False, "tom rollback-reference"
    env = _git_env()
    rc, _, err = _run([GIT, "-C", REPO_DIR, "reset", "--hard", prev],
                      env=env, timeout=120)
    if rc != 0:
        return False, f"reset fejlede: {err.strip()}"
    _run(["find", f"{REPO_DIR}/edge", "-name", "__pycache__",
          "-exec", "rm", "-rf", "{}", "+"], timeout=30)
    return True, f"rullet tilbage til {prev[:7]}"


# ── Hovedindgang ───────────────────────────────────────────────────────────

def process_targets(api, device_id: str, lab_active: bool) -> int:
    """Hent QUEUED targets fra headend og installér dem.

    `api` er HeadendClient (har ._get/._post). Returnerer antal installerede.
    Genstart af timelapse-edge sker KUN hvis applikationskode ændredes.
    """
    if lab_active:
        log.info("CMDB: LAB mode aktiv — springer opdateringer over")
        return 0

    ok, data = api._get(f"/cmdb/edge/{device_id}/pending")
    if not ok or not data:
        return 0
    targets = data.get("targets", [])
    if not targets:
        return 0

    log.info("CMDB: %d opdateringspakke(r) i kø", len(targets))
    installed = 0
    needs_restart = False

    for t in targets:
        cat = t.get("category", "")
        comps = t.get("components", [])
        tid = t.get("target_id")
        try:
            if cat in ("timelapse", "app_security", "app_update"):
                success, ver, msg = _apply_git(t.get("target_version", ""))
                needs_restart = needs_restart or success
            elif cat in ("os_security", "os_update"):
                success, ver, msg = _apply_apt(comps)
            else:
                success, ver, msg = False, "", f"ukendt kategori {cat}"
            log.info("CMDB target %s (%s): %s", tid, cat, msg)
        except Exception as exc:
            success, ver, msg = False, "", str(exc)
            log.warning("CMDB target %s fejl: %s", tid, exc)

        api._post(f"/cmdb/edge/{device_id}/result", {
            "target_id": tid, "success": success,
            "installed_version": ver, "reason": msg,
        })
        if success:
            installed += 1

    if needs_restart:
        log.info("CMDB: applikationskode ændret — genstarter timelapse-edge")
        _run(["systemctl", "restart", "timelapse-edge"], timeout=30)
    return installed
