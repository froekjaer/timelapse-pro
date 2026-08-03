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


def test_bundle_installer_uses_two_phase_offline_dpkg_transaction(tmp_path, monkeypatch):
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
    assert "dpkg --force-confold --unpack packages/*.deb" in installer
    assert "dpkg --configure --pending" in installer
    assert "/bin/bash ./verify-installed.sh" in installer
    assert "apt-get" not in installer
