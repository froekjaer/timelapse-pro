"""Logical storage resolution and health checks for local disks and NAS mounts."""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from database import StorageBinding

CAPTURES = "captures-primary"
BACKUPS = "backups-primary"
EDGE_ARTIFACTS = "edge-artifacts"
VALID_ROLES = {CAPTURES, BACKUPS, EDGE_ARTIFACTS, "application-data", "ai-models"}
VALID_BACKENDS = {"local", "smb", "nfs"}
VALID_MODES = {"read_write", "read_only", "replica"}


def resolve_storage(db: Session, logical_name: str, fallback: str | None = None, *, writable: bool = False) -> Path:
    query = db.query(StorageBinding).filter_by(logical_name=logical_name, active=True)
    if writable:
        query = query.filter(StorageBinding.access_mode == "read_write")
    rows = query.order_by(StorageBinding.priority, StorageBinding.id).all()
    for row in rows:
        path = Path(row.path).expanduser()
        if path.is_dir() and (not writable or os.access(path, os.W_OK)):
            return path
    if fallback:
        return Path(fallback).expanduser()
    if rows:
        return Path(rows[0].path).expanduser()
    raise RuntimeError(f"Ingen aktiv lagerbinding for {logical_name}")


def binding_status(row: StorageBinding) -> dict:
    path = Path(row.path).expanduser()
    result = {
        "id": row.id, "logical_name": row.logical_name, "backend_type": row.backend_type,
        "path": str(path), "access_mode": row.access_mode, "priority": row.priority,
        "active": row.active, "expected_volume_uuid": row.expected_volume_uuid,
        "actual_volume_uuid": None, "uuid_matches": None,
        "description": row.description, "exists": False, "is_dir": False,
        "readable": False, "writable": False, "free_bytes": None, "total_bytes": None,
        "healthy": False, "error": "",
    }
    try:
        result["exists"] = path.exists()
        result["is_dir"] = path.is_dir()
        result["readable"] = result["is_dir"] and os.access(path, os.R_OK)
        result["writable"] = result["is_dir"] and os.access(path, os.W_OK)
        if result["is_dir"]:
            usage = shutil.disk_usage(path)
            result["free_bytes"], result["total_bytes"] = usage.free, usage.total
            if sys.platform == "darwin" and row.expected_volume_uuid:
                df = subprocess.run(["/bin/df", "-P", str(path)], capture_output=True, text=True,
                                    timeout=5, check=False)
                device = df.stdout.strip().splitlines()[-1].split()[0] if df.returncode == 0 else str(path)
                proc = subprocess.run(["/usr/sbin/diskutil", "info", "-plist", device],
                                      capture_output=True, timeout=5, check=False)
                if proc.returncode == 0:
                    result["actual_volume_uuid"] = plistlib.loads(proc.stdout).get("VolumeUUID")
                    result["uuid_matches"] = result["actual_volume_uuid"] == row.expected_volume_uuid
        needs_write = row.access_mode == "read_write"
        identity_ok = result["uuid_matches"] is not False
        result["healthy"] = result["readable"] and (result["writable"] or not needs_write) and identity_ok
    except OSError as exc:
        result["error"] = str(exc)
    return result
