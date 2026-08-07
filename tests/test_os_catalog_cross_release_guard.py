"""Regression test (2026-08-07): TL-043EB9E72EFD OS-update incident.

Every OS-catalog-refresh call site (the nightly scheduled job, the manual
"Refresh fra CMDB/Mac-builder" UI button, and the Pydantic payload default)
hardcoded `image="ubuntu:24.04"` regardless of the target device's actual OS
release. TL-043EB9E72EFD is Jammy underneath (glibc 2.35-0ubuntu3.10,
base-files 12ubuntu4.7, both installed since 2025-06-12) — comparing it
against Noble's live package index made almost every installed package look
"upgradable" from release-line drift alone, producing a 503-package catalog
(67% of ~750 installed packages). The device's auto-approval policy then
waved it straight through, and it partially unpacked ~90 Noble packages
before dpkg aborted on libacl1 (Noble's build needs glibc 2.38), breaking
cp/mv/tar/rsync/install on a live device — all of which dynamically link
libacl.so.1.

Two independent fixes, tested here:
1. _resolve_os_catalog_image() derives the comparison release from the
   device's own CMDB inventory instead of a hardcoded default (source-level
   check — the function itself requires DB access to test behaviourally).
2. _reconcile_os_catalog() rejects an implausibly large fraction of
   installed packages appearing "upgradable" in a single catalog — a
   release-mismatch signature — regardless of what produced it. This is
   the actual backstop for THIS device, since its own CMDB os_name
   ("Ubuntu 24.04.4 LTS") is itself wrong (a mislabeled base image, not an
   edge agent reporting bug — see _resolve_os_catalog_image's docstring),
   so trusting device-reported os_name alone would not have caught it.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))
os.environ.setdefault("DATABASE_URL", os.getenv("TIMELAPSE_TEST_DATABASE_URL", "postgresql://timelapse@localhost/timelapse_test"))
os.environ.setdefault("TIMELAPSE_ENV", "test")

MAIN_SOURCE = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
REFRESH_SOURCE = (ROOT / "headend" / "services" / "os_catalog_refresh.py").read_text(encoding="utf-8")


def test_os_catalog_builder_payload_no_longer_defaults_to_a_hardcoded_release() -> None:
    assert 'image: Optional[str] = "ubuntu:24.04"' not in MAIN_SOURCE
    assert 'image: Optional[str] = None' in MAIN_SOURCE


def test_resolver_exists_and_is_used_by_every_catalog_entry_point() -> None:
    assert "def _resolve_os_catalog_image(" in MAIN_SOURCE
    # every place that used to hardcode the image now routes through the resolver
    assert MAIN_SOURCE.count("_resolve_os_catalog_image(") >= 5


def test_reconcile_rejects_implausible_upgrade_fraction() -> None:
    from fastapi import HTTPException
    from main import _reconcile_os_catalog

    # 750 installed packages, 503 of them "upgradable" — the actual shape
    # of the TL-043EB9E72EFD incident.
    installed = {f"pkg{i}": "1.0-1" for i in range(750)}
    catalog_packages = [
        {
            "name": f"pkg{i}",
            "available_version": "2.0-1",
            "category": "os_updates",
            "severity": "low",
            "architecture": "arm64",
            "source_repo": "noble-updates",
        }
        for i in range(503)
    ]
    with pytest.raises(HTTPException) as exc_info:
        _reconcile_os_catalog(installed, catalog_packages)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "implausible_upgrade_fraction"


def test_reconcile_accepts_a_plausible_security_patch_batch() -> None:
    from main import _reconcile_os_catalog

    installed = {f"pkg{i}": "1.0-1" for i in range(750)}
    catalog_packages = [
        {
            "name": f"pkg{i}",
            "available_version": "1.0-2",
            "category": "os_security",
            "severity": "high",
            "architecture": "arm64",
            "source_repo": "jammy-security",
        }
        for i in range(12)
    ]
    decisions = _reconcile_os_catalog(installed, catalog_packages)
    assert decisions["os_security"]["package_count"] == 12
