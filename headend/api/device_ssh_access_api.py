"""Per-device SSH access: download a device's own key, backfill it onto
already-flashed units, and toggle the shared Headend operator key.

The shared Headend key is a break-glass fallback baked into every device's
authorized_keys by default (see inject_edge_image.py). It is a single key
valid for the whole fleet, so an admin can disable it per-device here once
that device's own key is confirmed to work — a leaked download then only
ever opens the one device it belongs to.
"""

from __future__ import annotations

import io
import logging
import re
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Device, Event, get_db


log = logging.getLogger(__name__)

_CANDIDATE_USERNAMES = ["timelapse", "orangepi", "ubuntu", "pi"]
_SSH_TIMEOUT_S = 8
_HEADEND_KEY_PATH = Path.home() / ".ssh" / "timelapse_headend_ed25519"


def _sanitize_device_id(device_id: str) -> str:
    """Sanitér device_id — samme regel som headend/main.py::_sanitize_device_id."""
    if not device_id:
        raise HTTPException(status_code=400, detail="Ugyldigt device_id")
    device_id = device_id.strip().upper()
    if not re.match(r'^[A-Za-z0-9_-]{3,60}$', device_id):
        raise HTTPException(status_code=400, detail="Ugyldigt device_id format")
    if '..' in device_id or '/' in device_id or '\\' in device_id:
        raise HTTPException(status_code=400, detail="Ugyldigt device_id")
    return device_id


def _load_pkey(private_key_pem: str):
    import paramiko
    return paramiko.Ed25519Key.from_private_key(io.StringIO(private_key_pem))


def _connect(host: str, pkey, usernames: list[str]):
    """Try each candidate username; return (client, username) for the first that authenticates."""
    import paramiko

    last_exc: Exception | None = None
    for username in usernames:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                host, username=username, pkey=pkey,
                timeout=_SSH_TIMEOUT_S, banner_timeout=_SSH_TIMEOUT_S,
                auth_timeout=_SSH_TIMEOUT_S, look_for_keys=False, allow_agent=False,
            )
            return client, username
        except Exception as exc:
            last_exc = exc
            client.close()
    raise RuntimeError(f"Kunne ikke SSH-forbinde til {host} som nogen af {usernames}: {last_exc}")


def _run(client, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(command, timeout=_SSH_TIMEOUT_S)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")


def _set_authorized_key_present(client, pubkey_line: str, present: bool) -> None:
    pubkey_line = pubkey_line.strip()
    if present:
        cmd = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            f"grep -qxF '{pubkey_line}' ~/.ssh/authorized_keys 2>/dev/null || "
            f"echo '{pubkey_line}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
        )
    else:
        cmd = (
            f"grep -vxF '{pubkey_line}' ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp 2>/dev/null "
            "&& mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys; true"
        )
    exit_code, _out, err = _run(client, cmd)
    if exit_code != 0:
        raise RuntimeError(f"Kommando fejlede (exit {exit_code}): {err.strip()}")


class BackfillSshKeyRequest(BaseModel):
    ip_override: str = ""


class SharedSshKeyToggleRequest(BaseModel):
    disabled: bool
    ip_override: str = ""


def create_device_ssh_access_router(require_role: Callable) -> APIRouter:
    """Build the router with the application's established auth hook."""
    router = APIRouter(prefix="/api/admin/devices", tags=["device-ssh-access"])

    def _resolve_host(device: Device, ip_override: str) -> str:
        host = (ip_override or device.ip_address or "").strip()
        if not host:
            raise HTTPException(
                status_code=400,
                detail="Ingen kendt IP-adresse for enheden endnu — angiv ip_override.",
            )
        return host

    @router.get("/{device_id}/ssh-private-key")
    def download_device_ssh_private_key(
        device_id: str,
        current_user=require_role("super_admin", "admin"),
        db: Session = Depends(get_db),
    ):
        """Download denne enheds EGEN SSH-privatnøgle (ikke den delte Headend-nøgle)."""
        device = db.query(Device).filter_by(device_id=_sanitize_device_id(device_id)).first()
        if not device:
            raise HTTPException(status_code=404, detail="Edge ikke fundet")
        if not device.ssh_private_key:
            raise HTTPException(status_code=404, detail="Enheden har ikke en genereret SSH-nøgle endnu")
        db.add(Event(
            device_id=device.device_id,
            level="INFO",
            category="security",
            message="SSH-privatnøgle downloadet",
            extra=None,
        ))
        db.commit()
        log.info("SSH private key downloaded for %s by %s", device.device_id, current_user.username)
        filename = f"{device.device_id}_id_ed25519"
        return Response(
            content=device.ssh_private_key,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/{device_id}/backfill-ssh-key")
    def backfill_device_ssh_key(
        device_id: str,
        body: BackfillSshKeyRequest,
        current_user=require_role("super_admin", "admin"),
        db: Session = Depends(get_db),
    ):
        """Injicér denne enheds egen public key i dens authorized_keys via den
        eksisterende delte Headend-nøgle — til allerede-flashede enheder, som
        aldrig fik den enheds-specifikke nøgle bagt ind ved build."""
        device = db.query(Device).filter_by(device_id=_sanitize_device_id(device_id)).first()
        if not device:
            raise HTTPException(status_code=404, detail="Edge ikke fundet")
        if not device.ssh_pubkey:
            raise HTTPException(status_code=400, detail="Enheden har ikke en genereret SSH-nøgle endnu")
        if not _HEADEND_KEY_PATH.exists():
            raise HTTPException(status_code=500, detail="Delt Headend SSH-nøgle findes ikke lokalt på Headend-maskinen")

        host = _resolve_host(device, body.ip_override)
        headend_pkey = _load_pkey(_HEADEND_KEY_PATH.read_text())
        try:
            client, username = _connect(host, headend_pkey, _CANDIDATE_USERNAMES)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        try:
            _set_authorized_key_present(client, device.ssh_pubkey, present=True)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Kunne ikke opdatere authorized_keys: {exc}") from exc
        finally:
            client.close()

        db.add(Event(
            device_id=device.device_id,
            level="INFO",
            category="security",
            message=f"Enhedens egen SSH-nøgle efterinstalleret (bruger={username}, host={host})",
            extra=None,
        ))
        db.commit()
        log.info("Backfilled own SSH key on %s (user=%s host=%s) by %s", device.device_id, username, host, current_user.username)
        return {"device_id": device.device_id, "username": username, "host": host, "status": "ok"}

    @router.post("/{device_id}/shared-ssh-key")
    def set_shared_ssh_key_disabled(
        device_id: str,
        body: SharedSshKeyToggleRequest,
        current_user=require_role("super_admin", "admin"),
        db: Session = Depends(get_db),
    ):
        """Slå den delte Headend-nøgle til/fra i denne enheds authorized_keys.

        Deaktivering kræver et forudgående, succesfuldt SSH-tjek med enhedens
        EGEN nøgle — vi strander aldrig en enhed ved at fjerne den delte nøgle,
        før vi har bekræftet at den enhedsspecifikke nøgle reelt virker.
        """
        device = db.query(Device).filter_by(device_id=_sanitize_device_id(device_id)).first()
        if not device:
            raise HTTPException(status_code=404, detail="Edge ikke fundet")
        if not _HEADEND_KEY_PATH.exists():
            raise HTTPException(status_code=500, detail="Delt Headend SSH-nøgle findes ikke lokalt på Headend-maskinen")
        host = _resolve_host(device, body.ip_override)
        headend_pubkey = _HEADEND_KEY_PATH.with_suffix(".pub").read_text().strip()

        if body.disabled:
            if not device.ssh_private_key:
                raise HTTPException(status_code=400, detail="Enheden har ingen egen nøgle — kan ikke sikkert deaktivere den delte nøgle")
            device_pkey = _load_pkey(device.ssh_private_key)
            try:
                client, username = _connect(host, device_pkey, _CANDIDATE_USERNAMES)
            except Exception as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"Enhedens egen nøgle virker ikke endnu — deaktiverer IKKE den delte nøgle for at undgå at låse enheden ude ({exc})",
                ) from exc
            try:
                _set_authorized_key_present(client, headend_pubkey, present=False)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Kunne ikke fjerne delt nøgle: {exc}") from exc
            finally:
                client.close()
        else:
            headend_pkey = _load_pkey(_HEADEND_KEY_PATH.read_text())
            try:
                client, username = _connect(host, headend_pkey, _CANDIDATE_USERNAMES)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            try:
                _set_authorized_key_present(client, headend_pubkey, present=True)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Kunne ikke tilføje delt nøgle: {exc}") from exc
            finally:
                client.close()

        device.shared_ssh_key_disabled = body.disabled
        db.add(Event(
            device_id=device.device_id,
            level="INFO",
            category="security",
            message=f"Delt Headend SSH-nøgle {'deaktiveret' if body.disabled else 'aktiveret'} (bruger={username}, host={host})",
            extra=None,
        ))
        db.commit()
        log.info(
            "Shared SSH key disabled=%s for %s (user=%s host=%s) by %s",
            body.disabled, device.device_id, username, host, current_user.username,
        )
        return {
            "device_id": device.device_id,
            "shared_ssh_key_disabled": device.shared_ssh_key_disabled,
            "username": username,
            "host": host,
        }

    return router
