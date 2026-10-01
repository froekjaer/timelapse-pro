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


def test_field_edge_install_needs_no_apt_or_internet_and_requires_signature():
    body = SCRIPT.split('if [[ "$MODE" == install-artifact ]]; then', 1)[1].split("\nfi\n", 1)[0]
    assert "apt-get install" not in body and "curl" not in body
    assert 'verify_signature "$ARTIFACT" "$ARTIFACT_SIG"' in body          # pinned signer, not a bare sha
    assert "ldconfig -p" in body                                          # refuses if runtime libs are missing
    assert "platform_id" in body and 'cp -a "${STAGE}${PREFIX}/."' in body  # platform check + staged run before replace
    assert "trusted_release_signers" in SCRIPT and "VALIDSIG" in SCRIPT


def test_no_pipe_into_early_exiting_grep_or_head_under_pipefail():
    """`cmd | grep -q` / `| head` under `set -o pipefail` SIGPIPEs the producer
    and reports a match as failure — hit on Edge2 2026-10-01 (ldconfig -p)."""
    code = [l for l in SCRIPT.splitlines() if not l.lstrip().startswith("#")]
    offenders = [l for l in code if re.search(r"(?<!\|)\|(?!\|)\s*(grep\s+-q|head\b)", l)]
    assert offenders == []


def test_flashable_image_carries_source_build_into_vendor_base():
    """inject_edge_image.py copies only timelapse paths from the rootfs into the
    vendor base image; the /usr/local gphoto2 build + udev rules/hwdb must be
    copied too, as files only (dir + children breaks `tar -T` under set -e)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("inj", ROOT / "headend/tools/inject_edge_image.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    script = mod._INJECT_SCRIPT
    block = script.split("# ── gphoto2/libgphoto2 source build", 1)[1].split("# ── Bootstrap config", 1)[0]
    for needle in ("usr/local/bin/gphoto2$", "usr/local/lib/libgphoto2", "60-libgphoto2-local", "20-libgphoto2-local",
                   "grep -v '/$'", "tar -xzf \"$ROOTFS_TAR\" -C /mnt/root -T", "ldconfig -r /mnt/root"):
        assert needle in block, needle


def test_image_build_fails_closed():
    inj = (ROOT / "headend/tools/inject_edge_image.py").read_text(encoding="utf-8")
    assert "imaget bygges ikke\" >&2\n        exit 1" in inj
    bedi = (ROOT / "headend/tools/build_edge_disk_image.py").read_text(encoding="utf-8")
    assert "SBOM mangler source-built gphoto2/libgphoto2 — imaget signeres ikke" in bedi


def test_build_artifact_resolves_relative_output():
    assert 'ARTIFACT="$(cd "$(dirname "$out")" && pwd)/$(basename "$out")"' in SCRIPT


def test_signature_uses_venv_python_and_accepts_signing_subkeys():
    vs = SCRIPT.split("verify_signature() {", 1)[1].split("\n}\n", 1)[0]
    assert "/opt/timelapse/venv/bin/python" in vs
    assert "print $NF" in vs  # VALIDSIG primary-key fingerprint (subkey signatures)


def test_inject_scoped_to_targets_with_gphoto2_baseline():
    inj = (ROOT / "headend/tools/inject_edge_image.py").read_text(encoding="utf-8")
    assert 'grep -q " gphoto2 "' in inj and "source-build injiceres ikke" in inj
