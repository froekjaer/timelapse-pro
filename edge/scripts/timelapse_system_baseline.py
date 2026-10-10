#!/usr/bin/env python3
"""TimeLapse Pro Edge system baseline (Peter, 2026-10-04).

"Alt nødvendigt skal være til stede på begge Edges — og i ISO-builderen."
The Edge1/Edge2 comparison (Dokumentation/EDGE1_EDGE2_COMPARISON_2026-10-04_CLAUDE.md)
found system settings that only existed on one device because they had been
hand-patched there. This oneshot (timelapse-system-baseline.service) brings
every Edge to the same baseline, idempotently, at boot and after each app
update that ships it — and a fresh image gets it on first boot.

Steps (each reported in /run/timelapse/system-baseline.json):
  journald   — volatile journal + rate limit (Edge2/image default; spares the
               SD card; logs reach Headend via the agent's SIEM forwarding)
  sshd       — PermitRootLogin no + PasswordAuthentication no, exactly like
               headend/tools/inject_edge_image.py; validated with `sshd -t`
               before reload, restored on failure
  cron       — removes the hand-made nightly reboots (Edge1: /etc/cron.d/
               timelapse-reboot and `0 4 * * * /sbin/reboot` in orangepi's
               crontab); replaced by timelapse-nightly-reboot.timer, which
               is configurable from the Headend (system.nightly_reboot)
  ramlog     — keeps Orange Pi ramlog's `rsync --delete /var/log/ ->
               /var/log.hdd/` (runs every 15 min once /var/log passes 75 %)
               away from /var/log.hdd/timelapse, which holds break-glass
               session recordings and the SIEM pending-event queues. Without
               it they were deleted on Edge2 and the agent could not restart
               (lab.60, 2026-10-05)
  wake       — the `tlwake` account for the Headend's shared wake key (the
               key itself is applied live by the agent from
               system.headend_wake — edge/wake_policy.py)
  bt-address — migrates Edge1's hand-made bt-set-addr.service address to
               /etc/timelapse/bt-address and disables that unit
               (timelapse-bt-address.service applies the address each boot)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/")
STATUS_PATH = Path("/run/timelapse/system-baseline.json")

JOURNALD_DROPIN = "etc/systemd/journald.conf.d/50-timelapse.conf"
JOURNALD_CONTENT = """# TimeLapse Pro system baseline — managed by timelapse_system_baseline.py.
# Same values as the image-built Edges: keep the journal in RAM (spares the SD
# card) with a rate limit; the agent forwards logs to Headend SIEM.
[Journal]
Storage=volatile
Compress=yes
RateLimitIntervalSec=30s
RateLimitBurst=10000
"""
SSHD_CONFIG = "etc/ssh/sshd_config"
SSHD_SETTINGS = {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
LEGACY_CRON = "etc/cron.d/timelapse-reboot"
LEGACY_BT_UNIT = "etc/systemd/system/bt-set-addr.service"
BT_ADDRESS_FILE = "etc/timelapse/bt-address"
CRON_REBOOT_LINE = re.compile(r"^\s*[\d*/,-]+\s+[\d*/,-]+\s+\*\s+\*\s+\*\s+(/sbin/reboot|/sbin/shutdown -r now)\s*$")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def journald(root: Path, apply: bool = True) -> dict:
    path = root / JOURNALD_DROPIN
    if path.is_file() and path.read_text(encoding="utf-8") == JOURNALD_CONTENT:
        return {"status": "ok"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(JOURNALD_CONTENT, encoding="utf-8")
    if apply:
        _run(["systemctl", "restart", "systemd-journald"])
    return {"status": "changed"}


def _sshd_rewrite(text: str) -> str:
    """Set the global directives (before the first Match block) like inject does."""
    lines = text.splitlines(keepends=True)
    out, seen, in_match = [], set(), False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("match "):
            in_match = True
        key = re.match(r"^#?\s*(PermitRootLogin|PasswordAuthentication)\b", stripped)
        if key and not in_match and key.group(1) not in seen:
            seen.add(key.group(1))
            out.append(f"{key.group(1)} {SSHD_SETTINGS[key.group(1)]}\n")
            continue
        out.append(line)
    missing = [k for k in SSHD_SETTINGS if k not in seen]
    if missing:
        # Global directives must come before any Match block.
        insert_at = next((i for i, l in enumerate(out) if l.strip().lower().startswith("match ")), len(out))
        out[insert_at:insert_at] = [f"{k} {SSHD_SETTINGS[k]}\n" for k in missing]
    return "".join(out)


def sshd(root: Path, apply: bool = True) -> dict:
    path = root / SSHD_CONFIG
    if not path.is_file():
        return {"status": "skipped", "reason": "no sshd_config"}
    before = path.read_text(encoding="utf-8")
    after = _sshd_rewrite(before)
    if after == before:
        return {"status": "ok"}
    backup = path.with_name("sshd_config.timelapse-baseline-prev")
    shutil.copy2(path, backup)
    path.write_text(after, encoding="utf-8")
    if apply:
        test = _run(["sshd", "-t"])
        if test.returncode != 0:
            shutil.copy2(backup, path)
            return {"status": "failed", "reason": f"sshd -t: {test.stderr.strip()[:300]}", "restored": True}
        _run(["systemctl", "reload", "ssh"])
    return {"status": "changed"}


def legacy_reboot_cron(root: Path, apply: bool = True) -> dict:
    removed = []
    cron = root / LEGACY_CRON
    if cron.exists():
        cron.unlink()
        removed.append(str(LEGACY_CRON))
    if apply:
        for user in ("orangepi", "root", "timelapse"):
            current = _run(["crontab", "-u", user, "-l"])
            if current.returncode != 0:
                continue
            kept = [l for l in current.stdout.splitlines() if not CRON_REBOOT_LINE.match(l)]
            if len(kept) != len(current.stdout.splitlines()):
                subprocess.run(["crontab", "-u", user, "-"], input="\n".join(kept) + "\n",
                               text=True, capture_output=True, timeout=30)
                removed.append(f"crontab:{user}")
    return {"status": "changed" if removed else "ok", "removed": removed}


RAMLOG_DEFAULTS = "etc/default/orangepi-ramlog"
RAMLOG_MARKER = "# timelapse-system-baseline: keep /var/log.hdd/timelapse out of ramlog sync"
RAMLOG_LINES = (
    RAMLOG_MARKER,
    "XTRA_RSYNC_TO=(--exclude=/timelapse/)",
    "XTRA_RSYNC_FROM=(--exclude=/timelapse/)",
)


def ramlog_exclude(root: Path, apply: bool = True) -> dict:
    path = root / RAMLOG_DEFAULTS
    if not path.is_file():
        return {"status": "skipped", "reason": "no orangepi-ramlog"}
    text = path.read_text(encoding="utf-8")
    if RAMLOG_MARKER in text:
        return {"status": "ok"}
    # Appended last: in bash the last assignment wins over the vendor's.
    path.write_text(text.rstrip("\n") + "\n\n" + "\n".join(RAMLOG_LINES) + "\n", encoding="utf-8")
    return {"status": "changed"}


WAKE_USER = "tlwake"
WAKE_HOME = "var/lib/tlwake"


def wake_account(root: Path, apply: bool = True) -> dict:
    """The `tlwake` account and its .ssh dir. The key itself is managed live by
    the agent (edge/wake_policy.py) from system.headend_wake in the config
    hierarchy, so switching it off removes the key without a reboot."""
    changed = []
    if apply:
        import pwd
        try:
            pwd.getpwnam(WAKE_USER)
        except KeyError:
            subprocess.run(["useradd", "--system", "--create-home", "--home-dir", "/" + WAKE_HOME,
                            "--shell", "/bin/sh", WAKE_USER], check=True, capture_output=True, timeout=30)
            subprocess.run(["passwd", "-l", WAKE_USER], capture_output=True, timeout=30)
            changed.append("user")
    ssh_dir = root / WAKE_HOME / ".ssh"
    if not ssh_dir.is_dir():
        ssh_dir.mkdir(parents=True)
        changed.append("ssh_dir")
    ssh_dir.chmod(0o700)
    if apply:
        import pwd
        entry = pwd.getpwnam(WAKE_USER)
        for path in (ssh_dir.parent, ssh_dir):
            os.chown(path, entry.pw_uid, entry.pw_gid)
    return {"status": "changed" if changed else "ok", "changed": changed}


def _address_from_hcitool_cmd(unit_text: str) -> str | None:
    match = re.search(r"0x3f\s+0x0070((?:\s+[0-9A-Fa-f]{2}){6})", unit_text)
    if not match:
        return None
    octets = match.group(1).split()
    return ":".join(reversed([o.upper() for o in octets]))   # vendor cmd is LSB first


def migrate_bt_address(root: Path, apply: bool = True) -> dict:
    unit = root / LEGACY_BT_UNIT
    if not unit.is_file():
        return {"status": "ok"}
    target = root / BT_ADDRESS_FILE
    address = _address_from_hcitool_cmd(unit.read_text(encoding="utf-8"))
    if address and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(address + "\n", encoding="utf-8")
    if apply:
        _run(["systemctl", "disable", "bt-set-addr.service"])
    unit.unlink()
    return {"status": "changed", "address": address}


STEPS = (("journald", journald), ("sshd", sshd), ("cron", legacy_reboot_cron), ("ramlog", ramlog_exclude),
         ("wake", wake_account), ("bt_address", migrate_bt_address))


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else ROOT
    apply = root == ROOT
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": {}}
    for name, step in STEPS:
        try:
            report["steps"][name] = step(root, apply)
        except Exception as exc:   # one failing step must not block the others
            report["steps"][name] = {"status": "failed", "reason": str(exc)[:300]}
        print(f"[system-baseline] {name}: {json.dumps(report['steps'][name], ensure_ascii=False)}")
    if apply:
        try:
            STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATUS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError:
            pass
    return 1 if any(s.get("status") == "failed" for s in report["steps"].values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
