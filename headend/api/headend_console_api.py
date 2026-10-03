"""Browser console to the Headend itself, through the admin SSH door (Peter, 2026-10-03).

Peter's rule from #270: password + TOTP on the admin sshd (port 9122) is the
only remote way into the Headend. This console does not add a second door: it
runs the ordinary `ssh` client in a pseudo-terminal against 127.0.0.1:9122, so
sshd/PAM ask for the macOS password and the TOTP code exactly as from a laptop.
The admin sshd host key is pinned (StrictHostKeyChecking=yes against the key
read from /etc/ssh/timelapse-admin), and the button itself requires a
super_admin whose UI session is MFA-verified. Every session is written to SIEM.
"""

from __future__ import annotations

import asyncio
import fcntl
import getpass
import logging
import os
import pty
import secrets
import select
import signal
import struct
import tempfile
import termios
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import get_db

log = logging.getLogger("headend")

ADMIN_SSH_HOST = "127.0.0.1"
ADMIN_SSH_PORT = int(os.getenv("TIMELAPSE_ADMIN_SSH_PORT", "9122"))
ADMIN_HOST_KEY_PUB = Path(os.getenv("TIMELAPSE_ADMIN_SSH_HOST_KEY_PUB", "/etc/ssh/timelapse-admin/ssh_host_ed25519_key.pub"))
SSH_BIN = os.getenv("TIMELAPSE_SSH_BIN", "/usr/bin/ssh")
OPEN_WINDOW_S = 60          # the browser must open the websocket within this window
MAX_SESSION_S = 30 * 60     # hard cap on a console session
RESIZE_PREFIX = "\x01RESIZE:"

# session_id -> {"principal": str, "expires": float}; single use.
_pending: dict[str, dict] = {}


def admin_ssh_user() -> str:
    return os.getenv("TIMELAPSE_ADMIN_SSH_USER") or getpass.getuser()


def ssh_command(known_hosts: Path) -> list[str]:
    return [
        SSH_BIN, "-tt",
        "-p", str(ADMIN_SSH_PORT),
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=keyboard-interactive",
        "-o", "NumberOfPasswordPrompts=1",
        "-o", "ServerAliveInterval=60",
        f"{admin_ssh_user()}@{ADMIN_SSH_HOST}",
    ]


def pinned_known_hosts() -> Path:
    """Write a private known_hosts with exactly the admin sshd host key."""
    key = ADMIN_HOST_KEY_PUB.read_text(encoding="utf-8").split()
    if len(key) < 2:
        raise RuntimeError("admin sshd host key unreadable")
    fd, name = tempfile.mkstemp(prefix="tl-console-known-hosts-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"[{ADMIN_SSH_HOST}]:{ADMIN_SSH_PORT} {key[0]} {key[1]}\n")
    os.chmod(name, 0o600)
    return Path(name)


def create_headend_console_router(
    get_current_user: Callable,
    session_payload: Callable,
    session_is_mfa_verified: Callable,
    record_siem: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/admin/headend-console", tags=["headend-console"])

    def _audit(db: Session, event_type: str, username: str, message: str, severity: str = "info") -> None:
        try:
            record_siem(db, "HEADEND", [{
                "event_type": event_type,
                "severity": severity,
                "username": username,
                "source": "headend_console",
                "category": "identity_and_access",
                "raw_message": message,
                "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }])
            db.commit()
        except Exception as exc:  # audit must never break the console
            log.warning("Headend console audit failed: %s", exc)
        log.info("Headend console: %s", message)

    def _require_super_admin(request: Request, db: Session):
        user = get_current_user(request, db)
        if user is None or not getattr(user, "is_active", False):
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        if getattr(user, "role", "") != "super_admin":
            raise HTTPException(status_code=403, detail="Kun super admin")
        if not session_is_mfa_verified(session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for Headend-konsol")
        return user

    def _check(request: Request, db: Session = Depends(get_db)):
        # Same reviewed auth-dependency pattern as the Edge terminal router.
        return _require_super_admin(request, db)

    @router.post("/sessions")
    def start_console(request: Request, user=Depends(_check), db: Session = Depends(get_db)):
        now = time.time()
        for sid in [s for s, v in _pending.items() if v["expires"] < now]:
            _pending.pop(sid, None)
        session_id = f"TLHC-{secrets.token_urlsafe(18)}"
        _pending[session_id] = {"principal": user.username, "expires": now + OPEN_WINDOW_S}
        _audit(db, "headend_console_requested", user.username,
               f"Headend-konsol anmodet af {user.username} (session {session_id})")
        return {
            "session_id": session_id,
            "websocket_path": f"/api/admin/headend-console/ws?session_id={session_id}",
            "target": f"{admin_ssh_user()}@{ADMIN_SSH_HOST}:{ADMIN_SSH_PORT}",
            "max_seconds": MAX_SESSION_S,
        }

    @router.websocket("/ws")
    async def console_ws(websocket: WebSocket, db: Session = Depends(get_db)):
        user = get_current_user(websocket, db)
        session_id = websocket.query_params.get("session_id") or ""
        pending = _pending.pop(session_id, None)   # single use
        if (
            user is None or not getattr(user, "is_active", False)
            or getattr(user, "role", "") != "super_admin"
            or not pending or pending["principal"] != user.username
            or pending["expires"] < time.time()
        ):
            await websocket.close(code=1008)
            return
        try:
            known_hosts = pinned_known_hosts()
        except Exception as exc:
            _audit(db, "headend_console_denied", user.username, f"Headend-konsol afvist: {exc}", "warning")
            await websocket.close(code=1011)
            return

        await websocket.accept()
        _audit(db, "headend_console_opened", user.username,
               f"Headend-konsol åbnet af {user.username} mod {admin_ssh_user()}@{ADMIN_SSH_HOST}:{ADMIN_SSH_PORT} (session {session_id})")

        # Build everything BEFORE fork: in this multi-threaded process the child
        # must do nothing but exec (no Python locks taken after fork).
        argv = ssh_command(known_hosts)
        env = {"PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "LANG": "en_US.UTF-8"}
        child_pid, master_fd = pty.fork()
        if child_pid == 0:  # child: the real ssh client; sshd/PAM ask password + TOTP
            os.execve(argv[0], argv, env)

        deadline = time.monotonic() + MAX_SESSION_S
        close_reason = "client closed"

        def child_alive() -> bool:
            try:
                pid, _ = os.waitpid(child_pid, os.WNOHANG)
            except ChildProcessError:
                return False
            return pid == 0

        async def pump() -> None:
            while child_alive():
                readable, _, _ = select.select([master_fd], [], [], 0)
                if readable:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    await websocket.send_text(data.decode(errors="replace"))
                else:
                    await asyncio.sleep(0.02)

        pump_task = asyncio.create_task(pump())
        try:
            while child_alive():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    close_reason = f"max session time {MAX_SESSION_S}s reached"
                    await websocket.send_text("\r\n[Headend-konsol lukket: maksimal sessionstid nået]\r\n")
                    break
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=min(remaining, 5))
                except asyncio.TimeoutError:
                    continue
                if msg.startswith(RESIZE_PREFIX):
                    try:
                        cols, rows = (int(v) for v in msg[len(RESIZE_PREFIX):].split(",", 1))
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
                    except Exception:
                        pass
                else:
                    os.write(master_fd, msg.encode())
            else:
                close_reason = "ssh session ended"
        except WebSocketDisconnect:
            close_reason = "websocket disconnected"
        except Exception as exc:
            close_reason = str(exc)
        finally:
            pump_task.cancel()
            try:
                os.kill(child_pid, signal.SIGTERM)
                await asyncio.sleep(0.2)
                if child_alive():
                    os.kill(child_pid, signal.SIGKILL)
                os.waitpid(child_pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            known_hosts.unlink(missing_ok=True)
            try:
                await websocket.close()
            except Exception:
                pass
            _audit(db, "headend_console_closed", user.username,
                   f"Headend-konsol lukket for {user.username} (session {session_id}): {close_reason}")

    return router
