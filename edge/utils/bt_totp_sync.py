"""
TimeLapse Pro — BT-TOTP local config sync
============================================
Shared logic for writing a Headend-resolved BT-TOTP secret into the local
management portal's config file (/etc/timelapse/bt-config.yaml).

Used by two callers:
  - edge/agent.py — automatic sync on every fetched config (SEC-016-BOOTSTRAP-GAP)
  - edge/tools/bootstrap_cli.py --totp-sync — manual/on-demand trigger for a
    technician with local shell access, e.g. to recover a device that never
    applied a secret change (see history below)

History: originally only reachable from agent.py, called exclusively from
inside the config-version-changed branch of _apply_config_changes(). That
gate is an optimization appropriate for expensive/disruptive changes, but
wrong for this one: a device whose locally-cached config_version already
happened to equal Headend's current hash (e.g. because a prior fetch's
version write succeeded while the BT-TOTP write itself failed or never ran)
would never get a chance to sync BT-TOTP again — the version compare would
keep matching forever, even though the file was silently wrong the entire
time. This function is written to be cheap and idempotent (a file read plus
string compare when nothing has changed) specifically so callers can run it
unconditionally on every poll instead of gating it behind a version diff.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULT_BT_TOTP_CONFIG_PATH = Path("/etc/timelapse/bt-config.yaml")


def sync_bt_totp_config(
    bt_totp: dict,
    config_path: Path = DEFAULT_BT_TOTP_CONFIG_PATH,
    *,
    restart_service: bool = True,
) -> str:
    """Write a resolved BT-TOTP secret/sid into config_path if it differs.

    Returns one of:
      "no-secret"  — bt_totp had no usable secret/sid; nothing touched
      "unchanged"  — config_path already matches; nothing written
      "synced"     — config_path was written (and the local totp-service
                     restarted, unless restart_service=False)

    Never raises for expected failure modes (missing/corrupt existing file);
    those are treated the same as "no local config yet". Filesystem errors
    on write (e.g. permission denied) propagate to the caller — the two
    current callers already wrap this in their own try/except.
    """
    new_secret = str(bt_totp.get("secret") or "")
    new_sid = str(bt_totp.get("sid") or "")
    if not new_secret or not new_sid or new_sid == "unprovisioned":
        return "no-secret"

    try:
        current = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    except Exception:
        current = {}
    current = current if isinstance(current, dict) else {}
    current_totp = current.get("totp") or {}
    if current_totp.get("sid") == new_sid and current_totp.get("secret") == new_secret:
        return "unchanged"

    current["totp"] = {**current_totp, "secret": new_secret, "sid": new_sid}

    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = config_path.with_name(f".{config_path.name}.tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        yaml.safe_dump(current, fh, allow_unicode=True, default_flow_style=False)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, config_path)
    os.chmod(config_path, 0o600)

    log.info("BT-TOTP synkroniseret fra headend (sid=%s)", new_sid)
    if restart_service:
        log.info("Genstarter timelapse-totp efter BT-TOTP sync")
        # Popen, not run(): totp-service.py itself is one of this function's
        # callers, restarting its own systemd unit from inside a request
        # handler. A blocking call here would wait on a process (itself)
        # that can't finish responding until this call returns — fire and
        # forget, same as the original totp-service.py implementation did.
        subprocess.Popen(
            ["systemctl", "restart", "timelapse-totp.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return "synced"
