"""
TimeLapse Pro — In-browser SSH terminal over the reverse tunnel
==================================================================
2026-08-06 (Claude, Peter): "faktisk tænker jeg at vi skal indsætte en ssh
klient på samme måde som i UI'en på edgen" — the edge already has an
in-browser terminal (edge/scripts/totp-service.py, xterm.js + a local PTY
bridge for break-glass shell access). This is the same idea for the HEADEND
side: click a terminal icon next to an active tunnel in Admin -> SSH Tunnels
and get a real interactive shell on that device, no local `ssh` command
needed.

Architecture differs from the edge's version out of necessity: the edge
bridges a WebSocket straight to a LOCAL bash process (pty.openpty() +
subprocess.Popen) — there is no SSH involved, it's the same machine. Here,
headend must actually BE the SSH client, connecting through the already-
established reverse tunnel (localhost:<remote_port> on the headend host
itself) using the shared timelapse_headend_ed25519 key (see
api/device_ssh_access_api.py — same key, same "break-glass fallback baked
into every device by default" model Peter asked about). paramiko's
invoke_shell() gives an interactive PTY channel directly (recv/send/
resize_pty), which is simpler and safer here than shelling out to the `ssh`
binary and managing a second pty ourselves.

New module (not added onto main.py) per the same-day lesson: the
architecture-ratchet baseline exists to force this, not to be repeatedly
raised instead of it.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import Device, Event, get_db

log = logging.getLogger("headend")

router = APIRouter()

_ROLE_HIERARCHY = {
    "super_admin": {"super_admin", "admin", "operator", "viewer"},
    "admin":       {"admin", "operator", "viewer"},
    "operator":    {"operator", "viewer"},
    "viewer":      {"viewer"},
}

_HEADEND_KEY_PATH = Path.home() / ".ssh" / "timelapse_headend_ed25519"
_TERMINAL_USERNAMES = ["orangepi", "timelapse", "ubuntu", "pi"]
_RESIZE_PREFIX = "\x01RESIZE:"  # SOH — never typed by a human or emitted by a shell prompt


def _require_role(*roles: str):
    """Local re-implementation of main.require_role() — see
    api/thumbnails_api.py's identical helper for the full rationale."""
    def _check(request: Request, db: Session = Depends(get_db)):
        from main import _mfa_required_for_user, _session_is_mfa_verified, _session_payload, get_current_user
        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
        return user
    return Depends(_check)


def _sanitize_device_id(device_id: str) -> str:
    from main import _sanitize_device_id as _impl
    return _impl(device_id)


@router.websocket("/api/admin/ssh-tunnel/{device_id}/terminal")
async def ssh_tunnel_terminal(websocket: WebSocket, device_id: str, db: Session = Depends(get_db)):
    # WebSocket connections don't carry the require_role() Depends() the same
    # way HTTP routes do (there is no response to attach a 401/403 to before
    # the handshake), so auth is checked manually here — get_current_user()
    # only touches request.cookies, which WebSocket also exposes (both
    # inherit from Starlette's HTTPConnection), so it works unmodified
    # despite its Request type hint.
    from main import get_current_user
    user = get_current_user(websocket, db)
    if user is None or user.role not in ("super_admin", "admin"):
        await websocket.close(code=1008)
        return

    try:
        device_id = _sanitize_device_id(device_id)
    except HTTPException:
        await websocket.close(code=1008)
        return

    device = db.query(Device).filter_by(device_id=device_id).first()
    if not device or not device.reverse_tunnel_port:
        await websocket.close(code=1008)
        return
    if not _HEADEND_KEY_PATH.exists():
        await websocket.close(code=1011)
        return

    await websocket.accept()

    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        pkey = paramiko.Ed25519Key.from_private_key_file(str(_HEADEND_KEY_PATH))
    except Exception as exc:
        await websocket.send_text(f"\r\n\x1b[31m[Kunne ikke læse Headend SSH-nøgle: {exc}]\x1b[0m\r\n")
        await websocket.close(code=1011)
        return

    # 2026-08-07 (Claude, Peter — Kamera 1's terminal): trying all 4 candidate
    # usernames back-to-back (3 of which are guaranteed-wrong guesses on any
    # single device) sends 4 failed-publickey lines to the device's sshd
    # within under a second. Reproduced live: Kamera 1 authenticated cleanly
    # twice in a row, then every attempt through THIS endpoint failed —
    # including with the username that had just worked — and stayed broken
    # for the rest of the night. That matches a fail2ban-style burst ban on
    # the tunnel's forwarded source, not an actual key/config problem; it's
    # very likely what caused the original "Authentication failed for all 4
    # usernames" Peter saw on Kamera 1 much earlier, and it will recur on any
    # device whose real username isn't first in the list. Spacing attempts
    # out keeps them inside a normal "mistyped once or twice" pattern instead
    # of a burst — typical jails ban on rate within a findtime window, not on
    # total attempts over minutes.
    channel = None
    connected_username = None
    last_exc: Exception | None = None
    for attempt_index, username in enumerate(_TERMINAL_USERNAMES):
        if attempt_index > 0:
            await asyncio.sleep(1.5)
        try:
            client.connect(
                "localhost", port=int(device.reverse_tunnel_port), username=username,
                pkey=pkey, timeout=10, banner_timeout=10, auth_timeout=10,
                look_for_keys=False, allow_agent=False,
            )
            connected_username = username
            break
        except Exception as exc:
            last_exc = exc
            client.close()
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if not connected_username:
        await websocket.send_text(
            f"\r\n\x1b[31m[Kunne ikke SSH-forbinde via tunnel (port {device.reverse_tunnel_port}): {last_exc}]\x1b[0m\r\n"
        )
        await websocket.close(code=1011)
        return

    channel = client.invoke_shell(term="xterm-256color", width=80, height=24)
    channel.settimeout(0.0)

    db.add(Event(
        device_id=device.device_id, level="INFO", category="security",
        message=f"SSH-terminal åbnet via reverse tunnel (bruger={connected_username}) af {user.username}",
    ))
    db.commit()
    log.info("SSH terminal opened for %s (user=%s) by %s", device.device_id, connected_username, user.username)

    async def pump() -> None:
        try:
            while True:
                if channel.closed:
                    break
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if not data:
                        break
                    await websocket.send_text(data.decode(errors="replace"))
                else:
                    await asyncio.sleep(0.02)
        except Exception:
            pass

    pump_task = asyncio.create_task(pump())
    try:
        while not channel.closed:
            msg = await websocket.receive_text()
            if msg.startswith(_RESIZE_PREFIX):
                try:
                    cols_s, rows_s = msg[len(_RESIZE_PREFIX):].split(",")
                    channel.resize_pty(width=int(cols_s), height=int(rows_s))
                except Exception:
                    pass
            else:
                channel.send(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        pump_task.cancel()
        try:
            channel.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
        try:
            db.add(Event(
                device_id=device.device_id, level="INFO", category="security",
                message=f"SSH-terminal lukket ({user.username})",
            ))
            db.commit()
        except Exception:
            pass
