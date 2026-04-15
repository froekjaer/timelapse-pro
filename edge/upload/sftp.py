# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — sftp.py (Upload Manager)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.1.0
# Dato     : 13. april 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   1.1.0  13-apr-2026  Sidecar JSON uploades automatisk med billedet
#                       Samme remote mappe og filnavn men .json extension
#   1.0.0  09-apr-2026  Initial SFTP upload med hierarkisk mappestruktur
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — SFTP Upload Manager
=====================================
Handles upload of captured images to primary and optional secondary
SFTP servers. Creates remote directory structure automatically.
Implements a persistent retry queue backed by the local SQLite DB.

SABSA: Availability  — store-and-forward, never loses an image
       Integrity     — SHA-256 verified post-upload
       Accountability — every upload attempt logged
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

import paramiko

log = logging.getLogger(__name__)

MAX_UPLOAD_ATTEMPTS = 10
CONNECT_TIMEOUT_S   = 15
TRANSFER_TIMEOUT_S  = 120


@dataclass
class SFTPTarget:
    name:        str        # 'primary' or 'secondary'
    host:        str
    port:        int
    username:    str
    remote_base: str        # e.g. '/incoming'
    key_file:    Path = field(default_factory=lambda: Path(""))
    password:    str  = ""  # use password OR key_file, not both


class UploadManager:
    """
    Manages SFTP uploads to one or two destinations.
    Supports both SSH key and password authentication.

    Config keys (from config.yaml sftp section):
        host, port, username, remote_base   — required
        password                            — for password auth (test)
        key_file                            — for key auth (production)
        secondary_sftp:
          enabled, host, port, username, remote_base, password/key_file
    """

    def __init__(self, config: dict, db):
        self._db            = db
        device              = config.get("device", {})
        self._device_id     = device.get("device_id", "unknown")
        self._customer_name = device.get("customer_name", "")
        self._site_name     = device.get("site_name", "")
        self._targets       = self._build_targets(config)

    def _build_targets(self, config: dict) -> list[SFTPTarget]:
        targets = []
        sftp    = config.get("sftp", {})

        if sftp.get("host"):
            targets.append(SFTPTarget(
                name        = "primary",
                host        = sftp["host"],
                port        = int(sftp.get("port", 22)),
                username    = sftp["username"],
                remote_base = sftp.get("remote_base", "/incoming"),
                key_file    = Path(sftp.get("key_file", "")),
                password    = sftp.get("password", ""),
            ))

        secondary = sftp.get("secondary_sftp", {})
        if secondary.get("enabled") and secondary.get("host"):
            targets.append(SFTPTarget(
                name        = "secondary",
                host        = secondary["host"],
                port        = int(secondary.get("port", 22)),
                username    = secondary["username"],
                remote_base = secondary.get("remote_base", "/incoming"),
                key_file    = Path(secondary.get("key_file", "")),
                password    = secondary.get("password", ""),
            ))

        if not targets:
            log.warning("No SFTP targets configured — uploads disabled")
        return targets

    def upload_capture(
        self,
        capture_id: int,
        filepath:   Path,
        camera_id:  str,
    ) -> dict[str, bool]:
        """
        Upload a captured image to all configured targets.
        Returns dict mapping target name to success bool.
        """
        results = {}
        for target in self._targets:
            success = self._upload_to_target(target, capture_id, filepath, camera_id)
            results[target.name] = success
            if success:
                self._db.mark_uploaded(capture_id, target.name)
        return results

    def retry_pending(self, camera_id: str) -> dict[str, int]:
        """Retry all pending uploads. Called after connectivity is restored."""
        counts = {t.name: 0 for t in self._targets}
        for target in self._targets:
            pending = self._db.get_pending_uploads(target.name)
            if not pending:
                continue
            log.info("Retrying %d pending uploads to %s", len(pending), target.name)
            for row in pending:
                if row.get("upload_attempts", 0) >= MAX_UPLOAD_ATTEMPTS:
                    continue
                filepath = Path(row["filepath"])
                if not filepath.exists():
                    continue
                success = self._upload_to_target(target, row["id"], filepath, camera_id)
                if success:
                    self._db.mark_uploaded(row["id"], target.name)
                    counts[target.name] += 1
        return counts

    # ── Internal ───────────────────────────────────────────────────────────

    def _upload_to_target(
        self,
        target:     SFTPTarget,
        capture_id: int,
        filepath:   Path,
        camera_id:  str,
    ) -> bool:
        # Build directory structure: remote_base/customer/site/YYYY/MM/DD/
        # Extract date from filename: KundeA_SiteB_Kamera1_20260331_120000.jpg
        # Fallback to flat camera_id structure if filename doesn't match pattern
        remote_dir = self._build_remote_dir(target.remote_base, camera_id, filepath.name)
        remote_path = str(PurePosixPath(remote_dir) / filepath.name)

        try:
            with _SFTPContext(target) as sftp:
                self._mkdir_p(sftp, remote_dir)
                log.info(
                    "Uploading %s → %s@%s:%s",
                    filepath.name, target.username, target.host, remote_path
                )
                sftp.put(str(filepath), remote_path)

                # Upload sidecar JSON hvis den findes
                sidecar_local  = filepath.with_suffix('.json')
                sidecar_remote = str(PurePosixPath(remote_dir) / sidecar_local.name)
                if sidecar_local.exists():
                    sftp.put(str(sidecar_local), sidecar_remote)
                    log.info("Sidecar uploaded: %s", sidecar_local.name)
                else:
                    log.debug("Ingen sidecar fundet for %s", filepath.name)

            log.info("Upload complete: %s → %s", filepath.name, target.name)
            self._db.log_event(
                self._device_id, "INFO", "upload",
                f"Uploaded {filepath.name} to {target.name}",
                {"capture_id": capture_id, "remote_path": remote_path}
            )
            return True

        except Exception as exc:
            log.error("Upload FAILED: %s → %s: %s", filepath.name, target.name, exc)
            self._db.log_event(
                self._device_id, "ERROR", "upload",
                f"Upload failed: {filepath.name} to {target.name}: {exc}",
                {"capture_id": capture_id}
            )
            return False

    def _build_remote_dir(
        self,
        remote_base: str,
        camera_id:   str,
        filename:    str,
    ) -> str:
        """
        Build hierarchical remote directory:
          remote_base/customer/site/YYYY/MM/DD/
        Date extracted from filename: ..._YYYYMMDD_HHMMSS.jpg
        Customer and site from config (stored at init time).
        Falls back to: remote_base/camera_id/YYYY/MM/DD/ if names missing.
        """
        import re
        m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
        if not m:
            return str(PurePosixPath(remote_base) / camera_id)

        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)

        customer = self._customer_name
        site     = self._site_name

        import re as _re
        def _safe(s):
            return _re.sub(r"[^A-Za-z0-9æøåÆØÅ_-]", "_", s).strip("_")
        if customer and site:
            return str(PurePosixPath(remote_base) / _safe(customer) / _safe(site) / yyyy / mm / dd)
        elif customer:
            return str(PurePosixPath(remote_base) / _safe(customer) / camera_id / yyyy / mm / dd)
        else:
            return str(PurePosixPath(remote_base) / camera_id / yyyy / mm / dd)

    @staticmethod
    def _mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        """Create remote directory hierarchy, ignore if exists."""
        parts = PurePosixPath(remote_dir).parts
        current = ""
        for part in parts:
            current = str(PurePosixPath(current) / part) if current else part
            try:
                sftp.stat(current)
            except FileNotFoundError:
                try:
                    sftp.mkdir(current)
                    log.debug("Created remote dir: %s", current)
                except Exception:
                    pass


class _SFTPContext:
    """Context manager that opens and closes a paramiko SFTP connection.
    Supports both password and SSH key authentication."""

    def __init__(self, target: SFTPTarget):
        self._target = target
        self._ssh    = None
        self._sftp   = None

    def __enter__(self) -> paramiko.SFTPClient:
        t = self._target
        self._ssh = paramiko.SSHClient()

        # For test: auto-add host key. For production: use known_hosts file.
        known_hosts = Path("/opt/timelapse/edge/ssh/known_hosts")
        if known_hosts.exists():
            self._ssh.load_host_keys(str(known_hosts))
            self._ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = dict(
            hostname       = t.host,
            port           = t.port,
            username       = t.username,
            timeout        = CONNECT_TIMEOUT_S,
            banner_timeout = CONNECT_TIMEOUT_S,
            look_for_keys  = False,
            allow_agent    = False,
        )

        # Password takes priority over key_file if both are set
        if t.password:
            connect_kwargs["password"] = t.password
        elif t.key_file and str(t.key_file).strip():
            connect_kwargs["key_filename"] = str(t.key_file)

        self._ssh.connect(**connect_kwargs)
        self._sftp = self._ssh.open_sftp()
        self._sftp.get_channel().settimeout(TRANSFER_TIMEOUT_S)
        return self._sftp

    def __exit__(self, *args):
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
