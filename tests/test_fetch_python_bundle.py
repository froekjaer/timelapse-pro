from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "headend" / "tools" / "fetch_python_bundle.py"
SPEC = importlib.util.spec_from_file_location("fetch_python_bundle_test", MODULE_PATH)
fetch = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(fetch)


def test_cpython_tag_from_python_version():
    assert fetch._cpython_tag("3.10.12") == "cp310"
    assert fetch._cpython_tag("3.12.3") == "cp312"


def test_universal_wheel_matches_any_arch():
    assert fetch.wheel_is_compatible("pyyaml-6.0.1-py3-none-any.whl", "cp310", "arm64")
    assert fetch.wheel_is_compatible("pyyaml-6.0.1-cp310-none-any.whl", "cp310", "arm64")


def test_arch_specific_wheel_requires_matching_platform_tag():
    # aarch64 wheel, requesting arm64 -> compatible
    assert fetch.wheel_is_compatible(
        "cryptography-42.0.5-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", "cp310", "arm64"
    )
    # x86_64-only wheel, requesting arm64 -> not compatible
    assert not fetch.wheel_is_compatible(
        "cryptography-42.0.5-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", "cp310", "arm64"
    )


def test_abi3_wheel_matches_forward_compatible_cpython():
    # cp39-abi3 wheel is usable on cp310+ (stable ABI)
    assert fetch.wheel_is_compatible(
        "cryptography-42.0.5-cp39-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", "cp310", "arm64"
    )


def test_wrong_cpython_tag_without_abi3_is_incompatible():
    assert not fetch.wheel_is_compatible(
        "somepkg-1.0-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", "cp310", "arm64"
    )


def test_macos_wheel_is_not_compatible_with_linux_default():
    # Regression for update #271 (2026-09-09): "macosx_12_0_arm64" contains
    # "arm64" and used to pass the (OS-blind) arch check, so pip on a real
    # Linux Edge device got handed a macOS-only scipy wheel and refused it.
    assert not fetch.wheel_is_compatible(
        "scipy-1.18.1-cp312-cp312-macosx_12_0_arm64.whl", "cp312", "arm64", "linux"
    )
    assert fetch.wheel_is_compatible(
        "scipy-1.18.1-cp312-cp312-macosx_12_0_arm64.whl", "cp312", "arm64", "macos"
    )


def test_linux_wheel_is_not_compatible_with_macos():
    assert not fetch.wheel_is_compatible(
        "cryptography-42.0.5-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", "cp310", "arm64", "macos"
    )
    assert fetch.wheel_is_compatible(
        "cryptography-42.0.5-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", "cp310", "arm64", "linux"
    )


def test_universal_wheel_matches_regardless_of_os_family():
    assert fetch.wheel_is_compatible("pyyaml-6.0.1-py3-none-any.whl", "cp310", "arm64", "macos")
    assert fetch.wheel_is_compatible("pyyaml-6.0.1-py3-none-any.whl", "cp310", "arm64", "linux")


def test_select_wheel_skips_macos_wheel_for_linux_device():
    urls = [
        {"packagetype": "bdist_wheel", "filename": "pkg-1.0-cp310-cp310-macosx_12_0_arm64.whl"},
        {"packagetype": "sdist", "filename": "pkg-1.0.tar.gz"},
    ]
    assert fetch.select_wheel(urls, "cp310", "arm64", "linux") is None


def test_select_wheel_prefers_universal_over_platform_specific():
    urls = [
        {"packagetype": "bdist_wheel", "filename": "pkg-1.0-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"},
        {"packagetype": "bdist_wheel", "filename": "pkg-1.0-py3-none-any.whl"},
        {"packagetype": "sdist", "filename": "pkg-1.0.tar.gz"},
    ]
    chosen = fetch.select_wheel(urls, "cp310", "arm64")
    assert chosen["filename"] == "pkg-1.0-py3-none-any.whl"


def test_select_wheel_returns_none_when_no_compatible_wheel():
    urls = [
        {"packagetype": "bdist_wheel", "filename": "pkg-1.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"},
        {"packagetype": "sdist", "filename": "pkg-1.0.tar.gz"},
    ]
    assert fetch.select_wheel(urls, "cp310", "arm64") is None


def test_bundle_installer_uses_offline_pip_with_exact_versions(tmp_path, monkeypatch):
    releases = {
        ("demo", "2.0"): {"urls": [{"packagetype": "bdist_wheel", "filename": "demo-2.0-py3-none-any.whl",
                                     "url": "https://files.pythonhosted.org/demo-2.0-py3-none-any.whl",
                                     "digests": {"sha256": ""}, "size": 10}]},
        ("helper", "3.0"): {"urls": [{"packagetype": "bdist_wheel", "filename": "helper-3.0-py3-none-any.whl",
                                       "url": "https://files.pythonhosted.org/helper-3.0-py3-none-any.whl",
                                       "digests": {"sha256": ""}, "size": 10}]},
    }
    monkeypatch.setattr(fetch, "fetch_release_metadata", lambda name, version, verbose=False: releases[(name, version)])

    def fake_download(entry, dest_dir, verbose=False):
        path = dest_dir / entry["filename"]
        path.write_bytes(b"whl")
        return path

    monkeypatch.setattr(fetch, "download_wheel", fake_download)
    fetch.build_bundle(
        [
            {"name": "demo", "available_version": "2.0"},
            {"name": "helper", "available_version": "3.0"},
        ],
        tmp_path / "bundle",
        "TL-TEST",
    )

    installer = (tmp_path / "bundle" / "install-offline.sh").read_text()
    assert "pip install --no-index --find-links=packages" in installer
    assert "'demo==2.0'" in installer
    assert "'helper==3.0'" in installer
    assert "pip install " in installer and "--index-url" not in installer
    # Regression guard for the same PATH bug fixed in edge/utils/inventory.py's
    # _venv_packages() (2026-09-04): must target Edge's own venv interpreter
    # explicitly, never bare "python3"/"pip3" resolved via systemd's default PATH.
    assert fetch.EDGE_VENV_PYTHON in installer
    assert not installer.lstrip().startswith("python3 ")
    verify = (tmp_path / "bundle" / "verify-installed.sh").read_text()
    assert fetch.EDGE_VENV_PYTHON in verify


def test_exact_pins_from_requires_dist_extracts_unconditional_pins():
    pins = fetch.exact_pins_from_requires_dist([
        "annotated-types>=0.6.0",
        "pydantic-core==2.46.5",
        "typing-extensions>=4.14.1",
        'email-validator>=2.0.0; extra == "email"',
    ])
    assert pins == {"pydantic-core": "2.46.5"}


def test_exact_pins_from_requires_dist_normalizes_names():
    pins = fetch.exact_pins_from_requires_dist(["Pydantic_Core==2.46.5"])
    assert pins == {"pydantic-core": "2.46.5"}


def test_exact_pins_from_requires_dist_ignores_missing_or_range_specifiers():
    assert fetch.exact_pins_from_requires_dist(None) == {}
    assert fetch.exact_pins_from_requires_dist(["foo>=1.0,<2.0"]) == {}


def test_build_bundle_repins_transitive_dependency_to_the_version_its_own_dependent_requires(tmp_path, monkeypatch):
    # Regression for update #271 (2026-09-09): pydantic and pydantic_core were
    # each independently flagged outdated and fetched at their own "latest on
    # PyPI" version, but pydantic 2.13.5 requires pydantic-core==2.46.5
    # exactly — not the independently-latest 2.48.0 — so pip's resolver
    # refused to install the pair as originally requested.
    releases = {
        ("pydantic", "2.13.5"): {
            "info": {"requires_dist": ["pydantic-core==2.46.5", "annotated-types>=0.6.0"]},
            "urls": [{"packagetype": "bdist_wheel", "filename": "pydantic-2.13.5-py3-none-any.whl",
                       "url": "https://files.pythonhosted.org/pydantic-2.13.5-py3-none-any.whl",
                       "digests": {"sha256": ""}, "size": 10}],
        },
        ("pydantic_core", "2.48.0"): {
            "info": {"requires_dist": []},
            "urls": [{"packagetype": "bdist_wheel", "filename": "pydantic_core-2.48.0-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl",
                       "url": "https://files.pythonhosted.org/pydantic_core-2.48.0.whl",
                       "digests": {"sha256": ""}, "size": 10}],
        },
        ("pydantic_core", "2.46.5"): {
            "info": {"requires_dist": []},
            "urls": [{"packagetype": "bdist_wheel", "filename": "pydantic_core-2.46.5-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl",
                       "url": "https://files.pythonhosted.org/pydantic_core-2.46.5.whl",
                       "digests": {"sha256": ""}, "size": 10}],
        },
    }
    monkeypatch.setattr(fetch, "fetch_release_metadata", lambda name, version, verbose=False: releases.get((name, version)))

    def fake_download(entry, dest_dir, verbose=False):
        path = dest_dir / entry["filename"]
        path.write_bytes(b"whl")
        return path

    monkeypatch.setattr(fetch, "download_wheel", fake_download)
    result = fetch.build_bundle(
        [
            {"name": "pydantic", "available_version": "2.13.5"},
            {"name": "pydantic_core", "available_version": "2.48.0"},
        ],
        tmp_path / "bundle",
        "TL-TEST",
        python_version="3.12.3",
        arch="arm64",
        os_family="linux",
    )
    assert result["wheel_files"] == 2
    assert result["not_found"] == []
    installer = (tmp_path / "bundle" / "install-offline.sh").read_text()
    assert "'pydantic==2.13.5'" in installer
    assert "'pydantic_core==2.46.5'" in installer
    assert "2.48.0" not in installer


def test_build_bundle_leaves_version_alone_when_pins_conflict(tmp_path, monkeypatch):
    # Two dependents pin the same transitive package to different exact
    # versions — auto-resolving would be a guess, so leave the originally
    # requested version untouched rather than silently picking one.
    releases = {
        ("a", "1.0"): {
            "info": {"requires_dist": ["shared==1.0"]},
            "urls": [{"packagetype": "bdist_wheel", "filename": "a-1.0-py3-none-any.whl",
                       "url": "https://files.pythonhosted.org/a-1.0-py3-none-any.whl",
                       "digests": {"sha256": ""}, "size": 10}],
        },
        ("b", "1.0"): {
            "info": {"requires_dist": ["shared==2.0"]},
            "urls": [{"packagetype": "bdist_wheel", "filename": "b-1.0-py3-none-any.whl",
                       "url": "https://files.pythonhosted.org/b-1.0-py3-none-any.whl",
                       "digests": {"sha256": ""}, "size": 10}],
        },
        ("shared", "3.0"): {
            "info": {"requires_dist": []},
            "urls": [{"packagetype": "bdist_wheel", "filename": "shared-3.0-py3-none-any.whl",
                       "url": "https://files.pythonhosted.org/shared-3.0-py3-none-any.whl",
                       "digests": {"sha256": ""}, "size": 10}],
        },
    }
    monkeypatch.setattr(fetch, "fetch_release_metadata", lambda name, version, verbose=False: releases.get((name, version)))

    def fake_download(entry, dest_dir, verbose=False):
        path = dest_dir / entry["filename"]
        path.write_bytes(b"whl")
        return path

    monkeypatch.setattr(fetch, "download_wheel", fake_download)
    result = fetch.build_bundle(
        [
            {"name": "a", "available_version": "1.0"},
            {"name": "b", "available_version": "1.0"},
            {"name": "shared", "available_version": "3.0"},
        ],
        tmp_path / "bundle",
        "TL-TEST",
    )
    installer = (tmp_path / "bundle" / "install-offline.sh").read_text()
    assert "'shared==3.0'" in installer


def test_unresolvable_package_is_reported_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "fetch_release_metadata", lambda name, version, verbose=False: None)
    monkeypatch.setattr(fetch, "fetch_release_metadata", lambda name, version, verbose=False: {
        "urls": [{"packagetype": "bdist_wheel", "filename": "demo-2.0-py3-none-any.whl",
                   "url": "https://files.pythonhosted.org/demo-2.0-py3-none-any.whl",
                   "digests": {"sha256": ""}, "size": 10}]
    } if name == "demo" else None)

    def fake_download(entry, dest_dir, verbose=False):
        path = dest_dir / entry["filename"]
        path.write_bytes(b"whl")
        return path

    monkeypatch.setattr(fetch, "download_wheel", fake_download)
    result = fetch.build_bundle(
        [
            {"name": "demo", "available_version": "2.0"},
            {"name": "ghost", "available_version": "9.9"},
        ],
        tmp_path / "bundle",
        "TL-TEST",
    )
    assert result["wheel_files"] == 1
    assert result["not_found"] == ["ghost==9.9"]
