"""Integrity primitives for Headend backups.

Backup output is staged on the destination filesystem and is never published
until PostgreSQL and tar integrity checks have completed.
"""

from __future__ import annotations

import hashlib
import os
import tarfile
from pathlib import Path


PG_DUMP_COMPLETE_MARKER = b"PostgreSQL database dump complete"


def validate_plain_pg_dump(path: str | Path) -> dict:
    dump_path = Path(path)
    size = dump_path.stat().st_size
    if size < 1024:
        raise RuntimeError(f"PostgreSQL dump er uventet lille ({size} bytes)")
    with dump_path.open("rb") as handle:
        handle.seek(max(0, size - 16_384))
        trailer = handle.read()
    if PG_DUMP_COMPLETE_MARKER not in trailer:
        raise RuntimeError("PostgreSQL dump mangler completion-marker")
    return {"bytes": size, "sha256": sha256_file(dump_path)}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def publish_tar_gzip_atomically(source_dir: str | Path, final_path: str | Path) -> dict:
    source = Path(source_dir)
    final = Path(final_path)
    partial = final.with_name(f".{final.name}.partial")
    partial.unlink(missing_ok=True)
    try:
        with tarfile.open(partial, "w:gz") as archive:
            archive.add(source, arcname=source.name)
        with tarfile.open(partial, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise RuntimeError("Backup-arkivet er tomt")
        os.replace(partial, final)
    finally:
        partial.unlink(missing_ok=True)
    return {"bytes": final.stat().st_size, "sha256": sha256_file(final)}
