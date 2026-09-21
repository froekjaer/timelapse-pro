"""Controlled browser SSH terminal for existing reverse tunnels."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from database import (
    Device,
    EdgeServiceGrant,
    Event,
    SshTunnelLog,
    SshHostKeyTrust,
    SshTerminalSessionAudit,
    ensure_utc,
    get_db,
    now_utc,
)
from services.ssh_host_trust_migration import migrate_legacy_known_host_trust
from trust.grants import GrantDenied, issue_edge_service_grant, validate_edge_service_grant
from trust.models import GrantRequest
from trust.policy import evaluate_legacy_role_capability_check, principal_from_legacy_user


log = logging.getLogger("headend")

CAPABILITY = "edge.shell.remote"
TERMINAL_TTL_SECONDS = int(os.getenv("TIMELAPSE_SSH_TERMINAL_TTL_SECONDS", "900"))
TUNNEL_STALE_SECONDS = int(os.getenv("TIMELAPSE_SSH_TUNNEL_STALE_SECONDS", "300"))
TUNNEL_TCP_TIMEOUT_SECONDS = float(os.getenv("TIMELAPSE_SSH_TUNNEL_TCP_TIMEOUT_SECONDS", "0.5"))
TUNNEL_CONTROL_HELPER = os.getenv(
    "TIMELAPSE_TUNNEL_CONTROL_HELPER",
    "/usr/local/libexec/timelapse-tunnel-control",
)
RESIZE_PREFIX = "\x01RESIZE:"
TRUSTED_HOST_STATES = {"trusted", "verified"}


def ssh_identity_display_path() -> str:
    return os.getenv("TIMELAPSE_HEADEND_SSH_IDENTITY_DISPLAY", "~/.ssh/timelapse_headend_ed25519")


def ssh_identity_private_path() -> Path:
    configured = os.getenv("TIMELAPSE_HEADEND_SSH_IDENTITY_PATH", ssh_identity_display_path())
    return Path(configured).expanduser()


def ssh_login_user() -> str:
    return os.getenv("TIMELAPSE_TUNNEL_SSH_USER", "orangepi")


def ssh_client_command(remote_port: int, *, key_path: str | None = None, username: str | None = None) -> str:
    return f"ssh -p {int(remote_port)} -i {key_path or ssh_identity_display_path()} {username or ssh_login_user()}@localhost"


def _trusted_host_key(db: Session, device_id: str) -> SshHostKeyTrust | None:
    return (
        db.query(SshHostKeyTrust)
        .filter(SshHostKeyTrust.device_id == device_id)
        .filter(SshHostKeyTrust.trusted_state.in_(sorted(TRUSTED_HOST_STATES)))
        .order_by(SshHostKeyTrust.trusted_at.desc().nullslast(), SshHostKeyTrust.created_at.desc())
        .first()
    )


def terminal_trust_status(
    db: Session,
    device_id: str,
    *,
    tunnel_reachable: bool | None = None,
) -> dict:
    trusted = _trusted_host_key(db, device_id)
    if not trusted:
        trusted = migrate_legacy_known_host_trust(db, device_id)
    if not trusted:
        return {
            "allowed": False,
            "reason": "SSH server host identity is not trusted/verified",
            "required_state": sorted(TRUSTED_HOST_STATES),
        }
    if tunnel_reachable is None:
        tunnel_reachable = _active_reverse_tunnel(db, device_id) is not None
    if not tunnel_reachable:
        return {
            "allowed": False,
            "reason": "No active reverse SSH tunnel",
            "key_type": trusted.key_type,
            "fingerprint": trusted.fingerprint_sha256,
            "trusted_state": trusted.trusted_state,
        }
    return {
        "allowed": True,
        "reason": "SSH server host identity trusted and reverse tunnel reachable",
        "key_type": trusted.key_type,
        "fingerprint": trusted.fingerprint_sha256,
        "trusted_state": trusted.trusted_state,
    }


def _localhost_ssh_banner_reachable(port: int) -> bool:
    # Reverse-forward listeners can be exposed on IPv6 localhost only (or on
    # IPv4 depending on sshd). Probe the same localhost name SSH uses rather
    # than assuming 127.0.0.1, while keeping the check local and bounded.
    for family, socktype, proto, _, sockaddr in socket.getaddrinfo(
        "localhost", int(port), type=socket.SOCK_STREAM
    ):
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(TUNNEL_TCP_TIMEOUT_SECONDS)
                sock.connect(sockaddr)
                return sock.recv(255).startswith(b"SSH-")
        except OSError:
            continue
    return False


# Compatibility for older callers. The check is intentionally stronger than
# its historical name: a listener must now return an SSH protocol banner.
_localhost_tcp_reachable = _localhost_ssh_banner_reachable


def _active_reverse_tunnel(db: Session, device_id: str):
    latest = (
        db.query(SshTunnelLog)
        .filter(SshTunnelLog.device_id == device_id)
        .filter(SshTunnelLog.event == "connected")
        .order_by(SshTunnelLog.event_at.desc())
        .first()
    )
    if not latest or not latest.remote_port:
        return None
    if not _localhost_tcp_reachable(int(latest.remote_port)):
        return None
    event_at = ensure_utc(latest.event_at)
    if not event_at:
        return None
    return latest


def active_reverse_tunnels(db: Session) -> list[dict]:
    """Return only reverse forwards that complete an SSH banner exchange."""
    rows = db.execute(sql_text("""
        SELECT s.device_id, s.remote_port, s.local_port, s.event_at, s.extra
        FROM ssh_tunnel_log s
        INNER JOIN (
            SELECT device_id, MAX(event_at) as max_at
            FROM ssh_tunnel_log
            WHERE event = 'connected'
            GROUP BY device_id
        ) latest ON s.device_id = latest.device_id AND s.event_at = latest.max_at
        WHERE s.event = 'connected'
        ORDER BY s.event_at DESC
    """)).fetchall()
    verified_rows = [
        (row, now_utc())
        for row in rows
        if row[1] and _localhost_ssh_banner_reachable(int(row[1]))
    ]
    device_ips = {
        d.device_id: d.ip_address
        for d in db.query(Device)
        .filter(Device.device_id.in_([row[0] for row, _ in verified_rows]))
        .all()
    }
    identity = ssh_identity_display_path()
    return [{
        "device_id": row[0],
        "remote_port": row[1],
        "local_port": row[2],
        "connected_at": row[3],
        "last_verified_at": verified_at,
        "verification_method": "headend_ssh_banner_probe",
        "ssh_user": ssh_login_user(),
        "ssh_identity_path": identity,
        "ssh_command": ssh_client_command(row[1]),
        "terminal": terminal_trust_status(db, row[0], tunnel_reachable=True),
        "device_ip": device_ips.get(row[0]),
        "servicetekniker_command": (
            f"ssh -i <din-private-nøgle> servicetekniker@{device_ips[row[0]]}"
            if device_ips.get(row[0]) else None
        ),
    } for row, verified_at in verified_rows]


def _force_close_reverse_tunnel(port: int) -> dict:
    """Ask the root-owned, narrowly-scoped helper to terminate one listener."""
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "-n", TUNNEL_CONTROL_HELPER, "close", str(int(port))],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"tunnel-control helper unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "tunnel-control failed").strip()
        raise RuntimeError(detail[:500])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("tunnel-control returned invalid output") from exc
    if payload.get("status") != "closed":
        raise RuntimeError("tunnel-control did not confirm closure")
    return payload


def _deny_terminal(db: Session, session: SshTerminalSessionAudit | None, reason: str, status: str = "denied") -> None:
    if session:
        grant = db.query(EdgeServiceGrant).filter_by(grant_id=session.grant_id).first()
        if grant and grant.status == "active":
            if status == "expired" or (grant.expires_at and ensure_utc(grant.expires_at) <= now_utc()):
                grant.status = "expired"
            else:
                grant.status = "revoked"
                grant.revoked_at = now_utc()
                grant.revoked_by = "ssh_terminal"
                grant.revoke_reason = reason
        session.status = status
        session.reason = reason
        session.ended_at = now_utc()
        db.commit()


def create_ssh_tunnel_terminal_router(
    get_current_user: Callable,
    ensure_device_access: Callable,
    session_payload: Callable,
    session_is_mfa_verified: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/admin/ssh-tunnel", tags=["ssh-tunnel-terminal"])

    def _require_terminal_user(request: Request, db: Session):
        user = get_current_user(request, db)
        if user is None or not getattr(user, "is_active", False):
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        if getattr(user, "role", "") == "viewer":
            raise HTTPException(status_code=403, detail="viewer denied terminal")
        mfa_verified = session_is_mfa_verified(session_payload(request))
        if not mfa_verified:
            raise HTTPException(status_code=403, detail="MFA kræves for browserterminal")
        decision = evaluate_legacy_role_capability_check(
            user,
            action="grant.issue",
            resource="edge:remote-shell",
            capability=CAPABILITY,
            tenant_id=getattr(user, "customer_id", None),
            mfa_verified=True,
            context={"route": "ssh_tunnel_terminal_start", "mfa_verified": bool(mfa_verified)},
        )
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason)
        return user

    def _check(request: Request, db: Session = Depends(get_db)):
        return _require_terminal_user(request, db)

    @router.post("/{device_id}/force-close")
    def force_close_tunnel(
        device_id: str,
        request: Request,
        user=Depends(_check),
        db: Session = Depends(get_db),
    ):
        ensure_device_access(db, user, device_id)
        if getattr(user, "role", "") not in {"super_admin", "admin"}:
            raise HTTPException(status_code=403, detail="Admin-rolle kræves for at lukke tunnel")
        tunnel = (
            db.query(SshTunnelLog)
            .filter(SshTunnelLog.device_id == device_id)
            .filter(SshTunnelLog.event == "connected")
            .order_by(SshTunnelLog.event_at.desc())
            .first()
        )
        if not tunnel or not tunnel.remote_port:
            raise HTTPException(status_code=409, detail="Ingen registreret tunnelport for enheden")
        try:
            outcome = _force_close_reverse_tunnel(int(tunnel.remote_port))
        except RuntimeError as exc:
            db.add(Event(
                device_id=device_id,
                level="ERROR",
                category="security",
                message=f"Reverse SSH tunnel force-close failed by {user.username}",
                extra=json.dumps({"remote_port": tunnel.remote_port, "error": str(exc)}),
            ))
            db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        db.add(SshTunnelLog(
            device_id=device_id,
            event="force_closed",
            remote_port=tunnel.remote_port,
            local_port=tunnel.local_port,
            initiated_by=f"admin:{user.username}",
            extra=json.dumps({"terminated_pids": outcome.get("terminated_pids", [])}),
        ))
        db.add(Event(
            device_id=device_id,
            level="WARNING",
            category="security",
            message=f"Reverse SSH tunnel force-closed by {user.username}",
            extra=json.dumps({"remote_port": tunnel.remote_port}),
        ))
        db.commit()
        return {
            "status": "closed",
            "device_id": device_id,
            "remote_port": tunnel.remote_port,
            "ready_for_reconnect": True,
        }

    @router.post("/{device_id}/terminal-sessions")
    def start_terminal_session(device_id: str, request: Request, user=Depends(_check), db: Session = Depends(get_db)):
        ensure_device_access(db, user, device_id)
        device = db.query(Device).filter_by(device_id=device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        tunnel = _active_reverse_tunnel(db, device_id)
        if not tunnel:
            raise HTTPException(status_code=409, detail="No active reverse SSH tunnel")
        trusted = _trusted_host_key(db, device_id)
        if not trusted:
            trusted = migrate_legacy_known_host_trust(db, device_id)
        if not trusted:
            raise HTTPException(status_code=403, detail="untrusted or mismatched SSH host key denied")

        try:
            token, grant = issue_edge_service_grant(db, GrantRequest(
                principal=principal_from_legacy_user(user, mfa_verified=True),
                edge_id=device_id,
                tenant_id=getattr(user, "customer_id", None),
                resource=f"edge:{device_id}:remote-shell",
                purpose="browser_ssh_terminal",
                capabilities=frozenset({CAPABILITY}),
                ttl_seconds=min(max(60, TERMINAL_TTL_SECONDS), 900),
                mfa_required=True,
                context={
                    "headend_principal": getattr(user, "username", ""),
                    "device_id": device_id,
                    "remote_port": tunnel.remote_port,
                },
            ))
        except GrantDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        session_id = f"TLTERM-{secrets.token_urlsafe(18)}"
        audit = SshTerminalSessionAudit(
            session_id=session_id,
            grant_id=grant.grant_id,
            device_id=device_id,
            principal=getattr(user, "username", ""),
            role=getattr(user, "role", ""),
            capability=CAPABILITY,
            remote_port=tunnel.remote_port,
            identity_key_path=ssh_identity_display_path(),
            host_fingerprint=trusted.fingerprint_sha256,
            status="created",
            reason="awaiting websocket",
            expires_at=grant.expires_at,
        )
        db.add(audit)
        db.commit()
        return {
            "session_id": session_id,
            "grant_id": grant.grant_id,
            "expires_at": grant.expires_at.isoformat(),
            "timeout_seconds": int((grant.expires_at - now_utc()).total_seconds()),
            "websocket_path": f"/api/admin/ssh-tunnel/{device_id}/terminal?session_id={session_id}",
            "identity_key_path": ssh_identity_display_path(),
            "remote_port": tunnel.remote_port,
            "host_fingerprint": trusted.fingerprint_sha256,
            "capability": CAPABILITY,
        }

    @router.websocket("/{device_id}/terminal")
    async def terminal_websocket(websocket: WebSocket, device_id: str, db: Session = Depends(get_db)):
        user = get_current_user(websocket, db)
        if user is None or not getattr(user, "is_active", False):
            await websocket.close(code=1008)
            return
        session_id = websocket.query_params.get("session_id") or ""
        audit = db.query(SshTerminalSessionAudit).filter_by(session_id=session_id, device_id=device_id).first()
        if not audit or audit.principal != getattr(user, "username", ""):
            await websocket.close(code=1008)
            return
        if audit.expires_at <= now_utc():
            _deny_terminal(db, audit, "terminal session expired before websocket", "expired")
            await websocket.close(code=1008)
            return
        grant = db.query(EdgeServiceGrant).filter_by(grant_id=audit.grant_id).first()
        if not grant or grant.status != "active":
            _deny_terminal(db, audit, "EdgeServiceGrant revoked before websocket", "revoked")
            await websocket.close(code=1008)
            return
        validation = validate_edge_service_grant(
            db,
            grant.signature,
            edge_id=device_id,
            tenant_id=getattr(user, "customer_id", None),
            capability=CAPABILITY,
            resource=f"edge:{device_id}:remote-shell",
            challenge_id=session_id,
        )
        if not validation.allowed:
            _deny_terminal(db, audit, validation.reason)
            await websocket.close(code=1008)
            return
        tunnel = _active_reverse_tunnel(db, device_id)
        trusted = _trusted_host_key(db, device_id)
        key_path = ssh_identity_private_path()
        if not tunnel or not trusted or not key_path.exists():
            _deny_terminal(db, audit, "missing active tunnel, trusted host key or identity key")
            await websocket.close(code=1008)
            return

        await websocket.accept()
        audit.status = "active"
        audit.started_at = now_utc()
        audit.reason = "websocket accepted"
        db.add(Event(
            device_id=device_id,
            level="INFO",
            category="security",
            message=f"SSH terminal opened by {audit.principal}; grant={audit.grant_id}; session={audit.session_id}",
        ))
        db.commit()

        import paramiko

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        channel = None
        try:
            pkey = paramiko.Ed25519Key.from_private_key_file(str(key_path))
            client.connect(
                "localhost",
                port=int(tunnel.remote_port),
                username=ssh_login_user(),
                pkey=pkey,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            channel = client.invoke_shell(term="xterm-256color", width=80, height=24)
            channel.settimeout(0.0)
        except Exception as exc:
            _deny_terminal(db, audit, f"SSH host-key verified connection failed: {exc}")
            await websocket.send_text("\r\n[SSH connection failed; host-key verification is required]\r\n")
            await websocket.close(code=1011)
            client.close()
            return

        async def revoke_watch() -> None:
            while True:
                await asyncio.sleep(1.0)
                db.expire_all()
                grant_row = db.query(EdgeServiceGrant).filter_by(grant_id=audit.grant_id).first()
                session_row = db.query(SshTerminalSessionAudit).filter_by(session_id=audit.session_id).first()
                if not grant_row or grant_row.status != "active":
                    raise RuntimeError("EdgeServiceGrant revoked")
                if grant_row.expires_at <= now_utc() or session_row.expires_at <= now_utc():
                    raise RuntimeError("EdgeServiceGrant expired")

        async def pump() -> None:
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

        pump_task = asyncio.create_task(pump())
        revoke_task = asyncio.create_task(revoke_watch())
        close_reason = "client closed"
        try:
            while not channel.closed:
                receive_task = asyncio.create_task(websocket.receive_text())
                done, _pending = await asyncio.wait(
                    {receive_task, revoke_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if revoke_task in done:
                    receive_task.cancel()
                    close_reason = str(revoke_task.exception() or "grant closed")
                    break
                msg = receive_task.result()
                if msg.startswith(RESIZE_PREFIX):
                    try:
                        cols_s, rows_s = msg[len(RESIZE_PREFIX):].split(",", 1)
                        channel.resize_pty(width=int(cols_s), height=int(rows_s))
                    except Exception:
                        pass
                else:
                    channel.send(msg)
        except WebSocketDisconnect:
            close_reason = "websocket disconnected"
        except Exception as exc:
            close_reason = str(exc)
        finally:
            pump_task.cancel()
            revoke_task.cancel()
            try:
                channel.close()
            except Exception:
                pass
            client.close()
            audit.status = "closed"
            audit.reason = close_reason
            audit.ended_at = now_utc()
            db.add(Event(
                device_id=device_id,
                level="INFO",
                category="security",
                message=f"SSH terminal closed by {audit.principal}; grant={audit.grant_id}; session={audit.session_id}; reason={close_reason}",
            ))
            db.commit()

    return router
