"""Pinned, verified gphoto2 source build used by Edge2 and Dockerfile.edge
(Peter 2026-10-01: 'A nu, B senere' — temporary until the 24.04 baseline)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "deploy/edge/install_gphoto2_from_source.sh").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "headend/tools/Dockerfile.edge").read_text(encoding="utf-8")


def test_versions_and_hashes_pinned():
    assert 'LIBGPHOTO2_VERSION="2.5.34"' in SCRIPT and 'GPHOTO2_VERSION="2.5.32"' in SCRIPT
    for var in ("LIBGPHOTO2_SHA256", "GPHOTO2_SHA256"):
        assert re.search(rf'{var}="[0-9a-f]{{64}}"', SCRIPT)
    assert "sha256sum -c" in SCRIPT and "7C4A FD61 D8AA E757 0796  A517 2209 D690 2F96 9C95" in SCRIPT


def test_cli_uses_new_library_and_rules_from_new_library():
    assert '-Wl,-rpath,${PREFIX}/lib' in SCRIPT
    assert 'LD_LIBRARY_PATH="${PREFIX}/lib" "$PCL" udev-rules' in SCRIPT
    # pipefail-safe Z30 check (grep -q on a pipe aborts the producer)
    assert 'grep -q \'"Nikon Z30"\' <<<"$cams"' in SCRIPT


def test_dockerfile_uses_source_build_not_jammy_packages():
    assert "install_gphoto2_from_source.sh --remove-build-deps" in DOCKERFILE
    apt_block = DOCKERFILE.split("# ── Base packages", 1)[1].split("rm -rf /var/lib/apt/lists/*", 1)[0]
    assert "gphoto2" not in apt_block and "libgphoto2" not in apt_block
