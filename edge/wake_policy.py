"""Whether this Edge may be woken by the Headend through its SSH tunnel.

`system.headend_wake` in the configuration hierarchy (global → device →
customer → site → camera; default on — Peter 2026-10-10: configurable "lige
som SSH tunnel"). Enforced here on the Edge: with it on, the `tlwake`
account's authorized_keys holds the shared wake key, locked to the tunnel
(from="127.0.0.1,::1"), `restrict` and a forced command that only asks the
agent to sync; with it off the file is empty, so sshd refuses the key.
"""
from __future__ import annotations

import os
from pathlib import Path

WAKE_USER = "tlwake"
WAKE_AUTHORIZED_KEYS = Path("/var/lib/tlwake/.ssh/authorized_keys")
WAKE_PUBKEY = Path(__file__).resolve().parent / "config" / "timelapse-wake.pub"
WAKE_COMMAND = "/opt/timelapse/edge/scripts/timelapse_wake_request.sh"


def wake_allowed(config: dict) -> bool:
    value = ((config or {}).get("system") or {}).get("headend_wake", True)
    return str(value).strip().lower() not in {"false", "0", "no", "off", "none"}


def authorized_keys_line(pubkey: str) -> str:
    key = " ".join(pubkey.split()[:2])
    return f'from="127.0.0.1,::1",restrict,command="{WAKE_COMMAND}" {key} timelapse-edge-wake\n'


def apply(config: dict, target: Path = WAKE_AUTHORIZED_KEYS, pubkey: Path = WAKE_PUBKEY,
          chown: bool = True) -> str | None:
    """Make authorized_keys match the policy. Returns "enabled"/"disabled" when
    it changed something, None when already in place or not provisioned."""
    if not target.parent.is_dir():          # account not provisioned yet (baseline)
        return None
    allowed = wake_allowed(config) and pubkey.is_file()
    wanted = authorized_keys_line(pubkey.read_text(encoding="utf-8")) if allowed else ""
    try:
        if target.is_file() and target.read_text(encoding="utf-8") == wanted:
            return None
    except OSError:
        pass
    target.write_text(wanted, encoding="utf-8")
    target.chmod(0o600)
    if chown:
        import pwd
        entry = pwd.getpwnam(WAKE_USER)
        os.chown(target, entry.pw_uid, entry.pw_gid)
    return "enabled" if allowed else "disabled"
