#!/usr/bin/env python3
"""sshd AuthorizedKeysCommand backend for the shared 'servicetekniker' account.

Wired into sshd via (sshd_config, root-owned, not part of this update
artifact — see provisioning):

    Match User servicetekniker
        AuthorizedKeysCommand /usr/bin/python3 /opt/timelapse/edge/scripts/technician_authorized_keys.py
        AuthorizedKeysCommandUser nobody

sshd calls this with the requested username as argv[1] on every login
attempt for that account and expects an authorized_keys-formatted list on
stdout. Only 'servicetekniker' is served — everything else (including the
break-glass account) must NOT go through this path, so a misconfigured
Match block can never widen who this script's keys apply to.

Reads a local cache written by edge/agent.py::_apply_technician_keys(),
populated by the consolidated sync poll (headend/edge_sync.py,
technician_keys.resolve_authorized_technician_keys()) — no live headend
round-trip at login time, so this keeps working while the device is
offline, using whatever was last synced.

Fails closed: any error (missing/corrupt cache, wrong username) prints
nothing, which sshd treats as "no keys from this command" — never a stack
trace, never a default-allow. See Dokumentation/HANDOVER_LOG.md 2026-08-19
for the break-glass/RBAC redesign this is the first slice of.
"""
import json
import os
import sys
from pathlib import Path

TECHNICIAN_ACCOUNT = "servicetekniker"
CACHE_PATH = Path("/etc/timelapse/authorized_technicians.json")
DEBUG_LOG = Path("/tmp/technician_authorized_keys_debug.log")


def _debug(msg: str) -> None:
    # TEMPORARY diagnostic — 2026-08-24, remove once the sshd-invocation
    # identity mismatch behind Peter's Permission denied is confirmed.
    try:
        with DEBUG_LOG.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


def main() -> int:
    requested_user = sys.argv[1] if len(sys.argv) > 1 else ""
    _debug(
        f"uid={os.getuid()} gid={os.getgid()} argv={sys.argv!r} "
        f"cwd={os.getcwd()!r} cache_exists={CACHE_PATH.exists()}"
    )
    if requested_user != TECHNICIAN_ACCOUNT:
        _debug(f"requested_user mismatch: {requested_user!r} != {TECHNICIAN_ACCOUNT!r}")
        return 0

    try:
        entries = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        _debug(f"cache read/parse failed: {exc!r}")
        return 0
    if not isinstance(entries, list):
        _debug(f"cache content not a list: {entries!r}")
        return 0

    printed = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        public_key = str(entry.get("public_key") or "").strip()
        identity = str(entry.get("identity") or "").strip()
        if not public_key:
            continue
        print(f"{public_key} {identity}".rstrip())
        printed += 1
    _debug(f"printed {printed} key(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
