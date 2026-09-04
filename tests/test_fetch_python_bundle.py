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
