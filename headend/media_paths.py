"""
TimeLapse Pro — Headend Media Path Resolution
================================================
Locates capture image files on disk given a device_id + filename, across the
several directory layouts that have existed historically (canonical, legacy
chroot, legacy site, flat/device, and imported captures).

2026-08-06 (Claude): extracted from headend/main.py. This is a low-level,
storage-layout utility used far beyond the thumbnail subsystem (image
download, export, deletion, retention audits, ...) — kept separate from
headend/api/thumbnails_api.py so that module (and any other caller) can
import _find_image() without pulling in thumbnail-specific machinery.
"""

from __future__ import annotations

import functools as _functools
import os
import re as _re
from datetime import datetime, timedelta
from pathlib import Path as _Path
from typing import Optional

from sqlalchemy.orm import Session

from database import SessionLocal, _get_setting


def _sftp_base_path(db: Session | None = None) -> _Path:
    """Canonical image root. DB setting wins, so NAS mount changes do not require restart."""
    fallback = os.getenv("SFTP_BASE", "/Volumes/data-fast")
    if db is not None:
        from storage_registry import CAPTURES, resolve_storage
        return resolve_storage(db, CAPTURES, _get_setting(db, "sftp_base", fallback), writable=True)
    local_db = SessionLocal()
    try:
        from storage_registry import CAPTURES, resolve_storage
        return resolve_storage(local_db, CAPTURES, _get_setting(local_db, "sftp_base", fallback), writable=True)
    finally:
        local_db.close()


def _configured_storage_roots(db: Session | None = None) -> list[_Path]:
    """Primary image root plus optional legacy/search roots for NAS migrations."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        roots = [_sftp_base_path(db)]
        raw = _get_setting(db, "sftp_legacy_roots", os.getenv("SFTP_LEGACY_ROOTS", ""))
        for item in _re.split(r"[\n,]+", raw or ""):
            item = item.strip()
            if item:
                roots.append(_Path(item).expanduser())
        deduped: list[_Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root)
            if key not in seen:
                seen.add(key)
                deduped.append(root)
        return deduped
    finally:
        if close_db:
            db.close()


@_functools.lru_cache(maxsize=100_000)
def _find_image_cached(device_id: str, filename: str, roots_key: tuple[str, ...]) -> str:
    """
    Find image — håndterer flere strukturer:
      1. Canonical data root: SFTP_BASE/{customer}/{site}/{camera}/YYYY/MM/DD/filename
      2. Legacy chroot:      SFTP_BASE/timelapse-incoming/{sftp_user}/data/{customer}/{site}/{camera}/YYYY/MM/DD/filename
      3. Legacy site:        SFTP_BASE/{customer}/{site}/YYYY/MM/DD/filename
      4. Flad/device:        SFTP_BASE/{device_id}/filename eller SFTP_BASE/{device_id}/YYYY/MM/DD/filename
    """
    m = _re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    for root in roots_key:
        sftp_base = _Path(root)
        if m:
            yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
            date_parts = [(yyyy, mm, dd)]
            try:
                filename_day = datetime(int(yyyy), int(mm), int(dd))
                for delta_days in (-1, 1):
                    adjacent = filename_day + timedelta(days=delta_days)
                    adjacent_parts = (f"{adjacent.year:04d}", f"{adjacent.month:02d}", f"{adjacent.day:02d}")
                    if adjacent_parts not in date_parts:
                        date_parts.append(adjacent_parts)
            except Exception:
                pass

            for yyyy, mm, dd in date_parts:

                # Struktur 1 — canonical: customer/site/camera/YYYY/MM/DD/
                canonical_glob = f"*/*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(canonical_glob))
                if matches:
                    return str(matches[0])

                # Struktur 2 — legacy chroot under timelapse-incoming/sftp_user/data/
                legacy_chroot_glob = f"timelapse-incoming/*/data/*/*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(legacy_chroot_glob))
                if matches:
                    return str(matches[0])

                legacy_site_chroot_glob = f"timelapse-incoming/*/data/*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(legacy_site_chroot_glob))
                if matches:
                    return str(matches[0])

                # Struktur 3 — gammel hierarkisk: customer/site/YYYY/MM/DD/
                old_glob = f"*/*/{yyyy}/{mm}/{dd}/{filename}"
                matches = list(sftp_base.glob(old_glob))
                if matches:
                    return str(matches[0])

                # Struktur 4 — device_id/YYYY/MM/DD/
                p = sftp_base / device_id / yyyy / mm / dd / filename
                if p.exists():
                    return str(p)

        # Flad struktur sftp_base/device_id/filename
        flat = sftp_base / device_id / filename
        if flat.exists():
            return str(flat)

    # Sidste udvej. Rekursiv søgning på NAS-roots er dyr og kan gøre
    # thumbnail-grids meget langsomme, så den er opt-in når strukturerne ovenfor
    # ikke dækker en særlig import.
    if os.getenv("TIMELAPSE_IMAGE_R_GLOB_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}:
        for root in roots_key:
            matches = list(_Path(root).rglob(filename))
            if matches:
                return str(matches[0])

    return ""


def _find_image(device_id: str, filename: str) -> Optional[_Path]:
    roots_key = tuple(str(root) for root in _configured_storage_roots())
    found = _find_image_cached(device_id, filename, roots_key)
    return _Path(found) if found else None
