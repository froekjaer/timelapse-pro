"""Fail-closed migration of legacy OpenSSH known_hosts trust into the browser-terminal registry.

This module never writes known_hosts and never trusts an unauthenticated key by itself.
A key is promoted only when the current SSH server key observed through the active reverse
SSH tunnel byte-for-byte matches an entry that is already trusted in the Headend user's
OpenSSH known_hosts file.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from database import SshHostKeyTrust, SshTunnelLog, now_utc

log = logging.getLogger("headend")


def _fingerprint_sha256(key) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _active_tunnel_port(db: Session, device_id: str) -> int | None:
    latest = (
        db.query(SshTunnelLog)
        .filter(SshTunnelLog.device_id == device_id)
        .order_by(SshTunnelLog.event_at.desc())
        .first()
    )
    if not latest or latest.event != "connected" or not latest.remote_port:
        return None
    return int(latest.remote_port)


def migrate_legacy_known_host_trust(db: Session, device_id: str) -> SshHostKeyTrust | None:
    """Promote an existing Edge host key only if current key == trusted known_hosts key.

    Returns the verified trust row on success, otherwise None. All failures are fail-closed.
    """
    port = _active_tunnel_port(db, device_id)
    if not port:
        return None

    known_hosts_path = Path.home() / ".ssh" / "known_hosts"
    if not known_hosts_path.exists():
        return None

    try:
        import paramiko

        host_keys = paramiko.HostKeys()
        host_keys.load(str(known_hosts_path))

        aliases = (f"[localhost]:{port}", f"[127.0.0.1]:{port}")
        trusted_candidates = []
        for alias in aliases:
            entry = host_keys.lookup(alias)
            if entry:
                trusted_candidates.extend(entry.values())
        if not trusted_candidates:
            return None

        transport = paramiko.Transport(("127.0.0.1", port))
        try:
            transport.start_client(timeout=5.0)
            observed_key = transport.get_remote_server_key()
        finally:
            transport.close()

        matched = next(
            (
                candidate
                for candidate in trusted_candidates
                if candidate.get_name() == observed_key.get_name()
                and candidate.asbytes() == observed_key.asbytes()
            ),
            None,
        )
        if matched is None:
            log.warning(
                "Legacy SSH host trust migration denied for %s: current key does not match known_hosts on port %s",
                device_id,
                port,
            )
            return None

        fingerprint = _fingerprint_sha256(observed_key)
        key_type = observed_key.get_name()
        row = (
            db.query(SshHostKeyTrust)
            .filter_by(device_id=device_id, key_type=key_type, fingerprint_sha256=fingerprint)
            .first()
        )
        timestamp = now_utc()
        if row is None:
            row = SshHostKeyTrust(
                device_id=device_id,
                hostname="localhost",
                port=port,
                key_type=key_type,
                fingerprint_sha256=fingerprint,
                trusted_state="verified",
                evidence_source="legacy_known_hosts_exact_match",
                observed_at=timestamp,
                trusted_at=timestamp,
            )
            db.add(row)
        else:
            row.hostname = row.hostname or "localhost"
            row.port = port
            row.trusted_state = "verified"
            row.evidence_source = "legacy_known_hosts_exact_match"
            row.trusted_at = timestamp
            if row.observed_at is None:
                row.observed_at = timestamp

        db.commit()
        db.refresh(row)
        log.info(
            "Legacy SSH host trust verified for %s on port %s fingerprint=%s",
            device_id,
            port,
            fingerprint,
        )
        return row
    except Exception as exc:
        db.rollback()
        log.warning("Legacy SSH host trust migration failed closed for %s: %s", device_id, exc)
        return None
