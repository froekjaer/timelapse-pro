"""Headend-only Golden Edge build-output validator tests."""
import io
import tarfile
from pathlib import Path

from headend.tools.golden_edge_baseline import REQUIRED_PIP, REQUIRED_UNITS, verify_golden_edge_baseline


def _tar(path: Path, units: tuple[str, ...]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for unit in units:
            name = f"./etc/systemd/system/{unit}"
            info = tarfile.TarInfo(name)
            info.size = 0
            archive.addfile(info, io.BytesIO(b""))


def test_complete_manifest_and_rootfs_pass(tmp_path):
    path = tmp_path / "rootfs.tar.gz"
    _tar(path, REQUIRED_UNITS)
    os_packages = [{"name": x} for x in ("chrony", "gphoto2", "bluez", "gpsd", "openssh-server")]
    pip_packages = [{"name": x} for x in REQUIRED_PIP]
    assert verify_golden_edge_baseline(os_packages, pip_packages, path) == []


def test_missing_dependencies_and_unit_fail_closed(tmp_path):
    path = tmp_path / "rootfs.tar.gz"
    _tar(path, ())
    errors = verify_golden_edge_baseline([], [], path)
    assert any("missing OS package" in x for x in errors)
    assert any("missing venv package" in x for x in errors)
    assert any("missing systemd unit" in x for x in errors)


def test_unreadable_tar_fails_closed(tmp_path):
    assert any("unreadable rootfs" in x for x in verify_golden_edge_baseline([], [], tmp_path / "absent.tar.gz"))
