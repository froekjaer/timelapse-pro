from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "headend" / "tools" / "fetch_os_bundle.py"
SPEC = importlib.util.spec_from_file_location("fetch_os_bundle_test", MODULE_PATH)
fetch = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(fetch)


def test_ubuntu_mirrors_use_tls():
    assert fetch.MIRROR_ARM64.startswith("https://")
    assert fetch.MIRROR_AMD64.startswith("https://")


def test_version_drift_is_recorded_when_current_security_version_is_used(tmp_path, monkeypatch):
    entry = {"Package": "demo", "Version": "2.0", "Filename": "pool/demo.deb",
             "Architecture": "arm64", "SHA256": ""}
    monkeypatch.setattr(fetch, "fetch_all_indices", lambda *_args, **_kwargs: {"demo": entry})

    def fake_download(_entry, dest, _mirror, verbose=False):
        path = dest / "demo_2.0_arm64.deb"
        path.write_bytes(b"deb")
        return path

    monkeypatch.setattr(fetch, "download_deb", fake_download)
    result = fetch.build_bundle(
        [{"name": "demo", "available_version": "1.0"}], tmp_path / "bundle",
        "TL-TEST", strict_versions=False,
    )
    assert result["deb_files"] == 1
    assert result["version_drifts"] == [{"name": "demo", "requested": "1.0", "resolved": "2.0"}]
    assert "2.0" in (tmp_path / "bundle" / "verify-installed.sh").read_text()


def test_bundle_installer_uses_offline_apt_with_exact_versions(tmp_path, monkeypatch):
    entries = {
        "demo": {"Package": "demo", "Version": "2.0", "Filename": "pool/demo.deb", "Architecture": "arm64", "SHA256": ""},
        "helper": {"Package": "helper", "Version": "3.0", "Filename": "pool/helper.deb", "Architecture": "arm64", "SHA256": ""},
    }
    monkeypatch.setattr(fetch, "fetch_all_indices", lambda *_args, **_kwargs: entries)

    def fake_download(entry, dest, _mirror, verbose=False):
        path = dest / f"{entry['Package']}_{entry['Version']}_arm64.deb"
        path.write_bytes(b"deb")
        return path

    monkeypatch.setattr(fetch, "download_deb", fake_download)
    fetch.build_bundle(
        [
            {"name": "demo", "available_version": "2.0"},
            {"name": "helper", "available_version": "3.0"},
        ],
        tmp_path / "bundle",
        "TL-TEST",
    )

    installer = (tmp_path / "bundle" / "install-offline.sh").read_text()
    assert '"$PWD"/packages/*.deb' in installer
    assert "apt-get --no-download" in installer
    assert "dpkg-scanpackages" not in installer
    assert "Dir::Etc::sourcelist" not in installer
    assert "dpkg -i" not in installer


def test_install_script_uses_absolute_local_deb_paths():
    # APT 2.8 rejects relative Filename entries from a temporary file://
    # index with "Pathname to install is not absolute".  Expanding the glob
    # after cd gives APT absolute paths to the signed bundle files.
    script = fetch.install_script([
        {"name": "libpam-modules", "version": "1.4.0-11ubuntu2.8"},
    ])
    assert 'install "$PWD"/packages/*.deb' in script
    assert "--no-download" in script
    assert "apt-get update" not in script
    assert "/etc/apt" not in script


def test_install_script_never_contains_a_literal_network_url():
    script = fetch.install_script([{"name": "demo", "version": "1.0"}])
    assert "http://" not in script
    assert "https://" not in script
    assert "ftp://" not in script
