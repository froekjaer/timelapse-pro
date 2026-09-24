"""Tests for headend/tools/golden_edge_baseline.py — added 2026-09-24 during
P0/P1 closure ahead of Travbyen. This is the manifest of what a fresh Edge
image must provide without depending on a later app-update; see the
module's own docstring and Dokumentation/HANDOVER_LOG.md (2026-09-24) for
the evidence trail (a build was silently missing NetworkManager, chrony,
timesync/watchdog units, and totp-service.py's own Python deps).
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "headend" / "tools"))

from golden_edge_baseline import (  # noqa: E402
    GOLDEN_EDGE_REQUIRED_FILES,
    GOLDEN_EDGE_REQUIRED_OS_PACKAGES,
    GOLDEN_EDGE_REQUIRED_PIP_PACKAGES,
    GOLDEN_EDGE_REQUIRED_SYSTEMD_UNITS,
    verify_golden_edge_baseline,
)


def _make_rootfs_tar(tmp_path: Path, tar_paths: list[str]) -> Path:
    tar_path = tmp_path / "rootfs.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for path in tar_paths:
            info = tarfile.TarInfo(name=path)
            info.size = 0
            tar.addfile(info, fileobj=None)
    return tar_path


def _all_compliant_tar_paths() -> list[str]:
    return [f"etc/systemd/system/{u}" for u in GOLDEN_EDGE_REQUIRED_SYSTEMD_UNITS] + list(
        GOLDEN_EDGE_REQUIRED_FILES
    )


def _sbom(names: list[str]) -> list[dict]:
    return [{"name": n, "version": "1.0", "arch": "arm64"} for n in names]


def _pip(names: list[str]) -> list[dict]:
    return [{"name": n, "version": "1.0"} for n in names]


def test_fully_compliant_build_has_no_violations(tmp_path):
    rootfs = _make_rootfs_tar(tmp_path, _all_compliant_tar_paths())
    violations = verify_golden_edge_baseline(
        _sbom(list(GOLDEN_EDGE_REQUIRED_OS_PACKAGES)),
        _pip(list(GOLDEN_EDGE_REQUIRED_PIP_PACKAGES)),
        rootfs,
    )
    assert violations == []


def test_missing_os_package_is_flagged(tmp_path):
    rootfs = _make_rootfs_tar(tmp_path, _all_compliant_tar_paths())
    os_packages = [p for p in GOLDEN_EDGE_REQUIRED_OS_PACKAGES if p != "chrony"]
    violations = verify_golden_edge_baseline(
        _sbom(os_packages),
        _pip(list(GOLDEN_EDGE_REQUIRED_PIP_PACKAGES)),
        rootfs,
    )
    assert any("chrony" in v for v in violations)


def test_missing_pip_package_is_flagged(tmp_path):
    """This is the exact class of bug that shipped: totp-service.py's own
    fastapi/pyotp/uvicorn dependencies were never declared anywhere."""
    rootfs = _make_rootfs_tar(tmp_path, _all_compliant_tar_paths())
    pip_packages = [p for p in GOLDEN_EDGE_REQUIRED_PIP_PACKAGES if p != "fastapi"]
    violations = verify_golden_edge_baseline(
        _sbom(list(GOLDEN_EDGE_REQUIRED_OS_PACKAGES)),
        _pip(pip_packages),
        rootfs,
    )
    assert any("fastapi" in v for v in violations)


def test_missing_systemd_unit_is_flagged(tmp_path):
    paths = [p for p in _all_compliant_tar_paths() if not p.endswith("timelapse-watchdog.service")]
    rootfs = _make_rootfs_tar(tmp_path, paths)
    violations = verify_golden_edge_baseline(
        _sbom(list(GOLDEN_EDGE_REQUIRED_OS_PACKAGES)),
        _pip(list(GOLDEN_EDGE_REQUIRED_PIP_PACKAGES)),
        rootfs,
    )
    assert any("timelapse-watchdog.service" in v for v in violations)


def test_missing_required_file_is_flagged(tmp_path):
    """Covers the GPIO udev rule / self-restart sudoers class of gap — files
    that must ship in the image but aren't systemd units."""
    paths = [p for p in _all_compliant_tar_paths() if "99-timelapse-gpio.rules" not in p]
    rootfs = _make_rootfs_tar(tmp_path, paths)
    violations = verify_golden_edge_baseline(
        _sbom(list(GOLDEN_EDGE_REQUIRED_OS_PACKAGES)),
        _pip(list(GOLDEN_EDGE_REQUIRED_PIP_PACKAGES)),
        rootfs,
    )
    assert any("99-timelapse-gpio.rules" in v for v in violations)


def test_package_name_matching_is_case_insensitive(tmp_path):
    """pip list --format=json commonly title-cases names (e.g. "PyYAML")."""
    rootfs = _make_rootfs_tar(tmp_path, _all_compliant_tar_paths())
    pip_packages = _pip([p.upper() for p in GOLDEN_EDGE_REQUIRED_PIP_PACKAGES])
    violations = verify_golden_edge_baseline(
        _sbom(list(GOLDEN_EDGE_REQUIRED_OS_PACKAGES)),
        pip_packages,
        rootfs,
    )
    assert violations == []


def test_baseline_lists_are_non_empty_and_hashable():
    """Sanity guard against an accidental empty manifest silently passing
    every check."""
    assert len(GOLDEN_EDGE_REQUIRED_OS_PACKAGES) > 5
    assert len(GOLDEN_EDGE_REQUIRED_PIP_PACKAGES) > 5
    assert len(GOLDEN_EDGE_REQUIRED_SYSTEMD_UNITS) > 5
    assert "fastapi" in GOLDEN_EDGE_REQUIRED_PIP_PACKAGES
    assert "chrony" in GOLDEN_EDGE_REQUIRED_OS_PACKAGES
    assert "timelapse-watchdog.service" in GOLDEN_EDGE_REQUIRED_SYSTEMD_UNITS


def test_build_edge_disk_image_calls_the_baseline_gate_before_signing():
    """Wiring check: the baseline must actually gate the build, not just
    exist as an unused importable module."""
    source = (Path(__file__).resolve().parents[1] / "headend" / "tools" / "build_edge_disk_image.py").read_text()
    assert "verify_golden_edge_baseline(sbom_packages, pip_packages, rootfs_path)" in source
    gate_idx = source.index("verify_golden_edge_baseline(sbom_packages")
    manifest_idx = source.index('progress_cb(f"\\n🔏 Step 4/4')
    assert gate_idx < manifest_idx, "baseline gate must run before the image is signed"
