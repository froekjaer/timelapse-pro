#!/usr/bin/python3
"""Root helper for closing one TimeLapse reverse-SSH listener on macOS."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time


CONFIG_PATH = "/etc/timelapse/tunnel-control.conf"
LSOF = "/usr/sbin/lsof"
PS = "/bin/ps"


def fail(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def tunnel_account() -> str:
    try:
        value = open(CONFIG_PATH, encoding="utf-8").read().strip()
    except OSError as exc:
        raise RuntimeError(f"cannot read {CONFIG_PATH}: {exc}") from exc
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,31}", value):
        raise RuntimeError("invalid tunnel account configuration")
    return value


def listener_pids(port: int) -> list[int]:
    result = subprocess.run(
        [LSOF, "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("lsof failed")
    return sorted({int(line) for line in result.stdout.splitlines() if line.isdigit()})


def verified_session_pid(pid: int, expected_user: str) -> bool:
    result = subprocess.run(
        [PS, "-p", str(pid), "-o", "user=,args="],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    fields = result.stdout.strip().split(None, 1)
    if len(fields) != 2:
        return False
    user, arguments = fields
    return (
        user == expected_user
        and arguments.startswith(f"sshd-session: {expected_user}")
    )


def main() -> int:
    if os.geteuid() != 0:
        return fail("must run as root")
    if len(sys.argv) != 3 or sys.argv[1] != "close" or not sys.argv[2].isdigit():
        return fail("usage: timelapse-tunnel-control close PORT", 2)
    port = int(sys.argv[2])
    if not 1024 <= port <= 65535:
        return fail("port out of range", 2)
    try:
        expected_user = tunnel_account()
        pids = listener_pids(port)
        if not pids:
            return fail("no listener on requested port", 3)
        if not all(verified_session_pid(pid, expected_user) for pid in pids):
            return fail("listener is not a verified TimeLapse sshd-session", 4)
        for pid in pids:
            os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            remaining = [pid for pid in pids if verified_session_pid(pid, expected_user)]
            if not remaining:
                print(json.dumps({"status": "closed", "port": port, "terminated_pids": pids}))
                return 0
            time.sleep(0.1)
        return fail("verified sshd-session did not terminate", 5)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
