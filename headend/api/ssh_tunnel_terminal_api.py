"""Controlled browser SSH terminal for existing reverse tunnels."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import (
    Device,
    EdgeServiceGrant,
    Event,
    SshHostKeyTrust,
    SshTerminalSessionAudit,
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


def terminal_trust_status(db: Session, device_id: str) -> dict:
    trusted = _trusted_host_key(db, device_id)
    if not trusted:
        trusted = migrate_legacy_known_host_trust(db, device_id)
    if not trusted:
        return {
            "allowed": False,
            "reason": "SSH server host identity is not trusted/verified",
            "required_state": sorted(TRUSTED_HOST_STATES),
        }
    return {
        "allowed": True,
        "reason": "SSH server host identity trusted",
        "key_type": trusted.key_type,
        "fingerprint": trusted.fingerprint_sha256,
        "trusted_state": trusted.trusted_state,
    }


def _active_reverse_tunnel(db: Session, device_id: str):
    from database import SshTunnelLog

    latest = (
        db.query(SshTunnelLog)
        .filter(SshTunnelLog.device_id == device_id)
        .order_by(SshTunnelLog.event_at.desc())
        .first()
    )
    if not latest or latest.event != "connected" or not latest.remote_port:
        return None
    return latest


def _deny_terminal(db: Session, session: SshTerminalSessionAudit | None, reason: str, status: str = "denied") -> None:
    if session:
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
