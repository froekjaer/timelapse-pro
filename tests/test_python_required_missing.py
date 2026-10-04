"""Required-but-missing Edge Python packages reach the bundle plan (2026-10-04).

Edge1 lacked qrcode + websockets for months: the Python track only updated
installed-but-outdated packages and never saw required-but-missing ones.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from services import python_requirements as pr  # noqa: E402

REQ = (ROOT / "edge" / "requirements.txt").read_text(encoding="utf-8")
# Edge1's actual pip freeze names (2026-10-04), abbreviated.
EDGE1 = {"annotated-doc": "0.0.5", "fastapi": "0.141.1", "opencv-python-headless": "5.0.0.93",
         "paramiko": "5.0.0", "PyOTP": "2.10.0", "python-multipart": "0.0.32", "PyYAML": "6.0.3",
         "requests": "2.34.2", "cryptography": "50.0.1", "uvicorn": "0.52.4", "onnxruntime": "1.30.0"}


def test_requirements_cover_what_the_technician_portal_imports():
    names = {pr.normalize(n) for n in pr.required_names(REQ)}
    assert {"fastapi", "uvicorn", "pyotp", "qrcode", "websockets", "python-multipart"} <= names


def test_edge1_gap_is_exactly_qrcode_and_websockets():
    missing = pr.missing_required_packages(EDGE1, REQ, lambda name: "9.9")
    assert [m["name"] for m in missing] == ["qrcode", "websockets"]
    assert all(m["installed_version"] == "" and m["available_version"] == "9.9"
               and m["reason"] == "required_missing" for m in missing)


def test_names_are_pep503_normalised_and_extras_markers_comments_ignored():
    text = "PyYAML>=6\nuvicorn[standard]>=0.4  # web\n# x\n-r other.txt\npywin32; sys_platform == 'win32'\npydantic_core\n"
    assert pr.required_names(text) == ["PyYAML", "uvicorn", "pydantic_core"]
    assert pr.missing_required_packages({"pyyaml": "6", "Uvicorn": "1", "pydantic-core": "2"}, text, lambda n: "1") == []


def test_unknown_on_pypi_is_skipped_not_planned():
    assert pr.missing_required_packages({}, "nosuchpkg\n", lambda n: None) == []


def test_main_wires_missing_into_the_same_plan_and_cmdb_into_release_manifest():
    src = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
    assert "outdated = _missing_required_packages(installed, _edge_requirements_text(_repo_root()), _latest)" in src
    assert 'root / "edge" / "cmdb",' in src
