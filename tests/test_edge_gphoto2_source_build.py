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
    assert 'LD_LIBRARY_PATH="${PREFIX}/lib" "$pcl" udev-rules' in SCRIPT
    # pipefail-safe Z30 check (grep -q on a pipe aborts the producer)
    assert 'grep -q \'"Nikon Z30"\' <<<"$cams"' in SCRIPT


def test_dockerfile_uses_source_build_not_jammy_packages():
    assert "install_gphoto2_from_source.sh --remove-build-deps" in DOCKERFILE
    apt_block = DOCKERFILE.split("# ── Base packages", 1)[1].split("rm -rf /var/lib/apt/lists/*", 1)[0]
    assert "gphoto2" not in apt_block and "libgphoto2" not in apt_block


def test_build_deps_removed_including_libc6_dev():
    assert 'apt-get remove -y -qq $BUILD_DEPS' in SCRIPT and "libc6-dev" in SCRIPT.split("BUILD_DEPS=", 1)[1].split("\n", 1)[0]


def test_artifact_sbom_and_provenance_include_source_build():
    import sys
    sys.path.insert(0, str(ROOT / "headend" / "tools"))
    src = (ROOT / "headend/tools/build_edge_disk_image.py").read_text(encoding="utf-8")
    assert '"deploy/edge/install_gphoto2_from_source.sh",' in src.split("def _git_provenance", 1)[1]
    import importlib.util
    spec = importlib.util.spec_from_file_location("bedi", ROOT / "headend/tools/build_edge_disk_image.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    out = "gphoto2 2.5.32\n\ngphoto2         2.5.32         gcc\nlibgphoto2      2.5.34         standard camlibs\n"
    comps = {c["name"]: c for c in mod._source_built_sbom_components(out, "arm64")}
    assert comps["gphoto2"]["version"] == "2.5.32" and comps["libgphoto2"]["version"] == "2.5.34"
    assert comps["libgphoto2"]["license"] == "LGPL-2.1-or-later"


def test_baseline_drift_accepts_source_build():
    import sys
    sys.path.insert(0, str(ROOT / "headend"))
    from services.cmdb_baseline_drift import compute_package_drift
    exp = ["gphoto2", "libgphoto2-6", "libgphoto2-port12", "gpsd"]
    assert compute_package_drift(exp, {"gpsd": "1"}).missing == ["gphoto2", "libgphoto2-6", "libgphoto2-port12"]
    assert compute_package_drift(exp, {"gpsd": "1"}, {"_gphoto2_source": "source-build"}).missing == []
    assert compute_package_drift(exp, {}, {"_gphoto2_source": "distro"}).missing == sorted(exp)


def test_field_edge_install_needs_no_apt_or_internet():
    body = SCRIPT.split('if [[ "$MODE" == install-artifact ]]; then', 1)[1].split("\nfi\n", 1)[0]
    assert "sha256sum -c" in body and "apt-get install" not in body and "curl" not in body
    assert "ldconfig -p" in body  # refuses if runtime libs are missing instead of fetching them


def test_no_pipe_into_early_exiting_grep_or_head_under_pipefail():
    """`cmd | grep -q` / `| head` under `set -o pipefail` SIGPIPEs the producer
    and reports a match as failure — hit on Edge2 2026-10-01 (ldconfig -p)."""
    code = [l for l in SCRIPT.splitlines() if not l.lstrip().startswith("#")]
    offenders = [l for l in code if re.search(r"\|\s*(grep\s+-q|head\b)", l)]
    assert offenders == []
