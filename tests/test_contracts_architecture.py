"""Architecture gates for the modular framework v1 (ADR-002).

These run with the normal suite (no heavy imports, no DB) and enforce the
platform/payload seam invariants BEFORE any runtime extraction happens, so the
codebase is guarded from day one.
"""
import ast
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACTS = REPO / "contracts"


# ---- 1. contracts/ is pure (imports nothing from headend/ or edge/) --------

def _imported_roots(package_dir: Path):
    roots = set()
    for py in package_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


def test_contracts_package_is_pure():
    forbidden = {"headend", "edge", "main"}
    assert not forbidden & _imported_roots(CONTRACTS), (
        "contracts/ must not import headend/edge/main — it is the neutral seam")


# ---- 2. contracts load and expose stable versions --------------------------

def test_contracts_import_and_versions():
    import contracts
    assert set(contracts.CONTRACT_VERSIONS) == {"control", "data", "manifest"}
    assert contracts.CONTRACT_VERSIONS["control"].startswith("1.")


# ---- 3. manifest validation is fail-closed ---------------------------------

def _good_manifest():
    return {
        "manifest_version": 1,
        "payload": {"name": "timelapse", "version": "1.0.0"},
        "contracts": {"control": "1.x", "data": "1.x"},
        "capabilities": ["camera.usb"],
        "quotas": {"cpu_pct": 50, "mem_mb": 512, "disk_mb": 64, "net_kbps": 0},
        "filesystem": {"readwrite": ["/var/spool/mission/timelapse"]},
        "channels": [
            {"name": "images", "kind": "blob", "classification": "personal-images",
             "retention_class": "customer-contract"},
            {"name": "capture-metrics", "kind": "timeseries",
             "classification": "operational", "retention_class": "ops-1y"},
        ],
    }


def test_good_manifest_parses():
    from contracts.manifest import parse_manifest
    m = parse_manifest(_good_manifest())
    assert m.name == "timelapse"
    assert m.channel("images").classification.value == "personal-images"


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d["capabilities"].append("actuator.valve"), "unknown capability"),
    (lambda d: d.__setitem__("rogue", 1), "unknown field"),
    (lambda d: d["channels"][1].__setitem__("classification", "personal-images"),
     "personal data forbidden"),
    (lambda d: d["channels"].append(dict(d["channels"][0])), "duplicate channel"),
    (lambda d: d["quotas"].__setitem__("mem_mb", -1), "non-negative"),
])
def test_manifest_fails_closed(mutate, match):
    from contracts.manifest import ManifestRejected, parse_manifest
    doc = _good_manifest()
    mutate(doc)
    with pytest.raises(ManifestRejected, match=match):
        parse_manifest(doc)


def test_policy_check_fails_closed_on_ungranted_capability():
    from contracts.manifest import Quotas, check_against_policy, parse_manifest, ManifestRejected
    m = parse_manifest(_good_manifest())
    with pytest.raises(ManifestRejected, match="not granted"):
        check_against_policy(
            m, allowed_capabilities=frozenset({"gpio.read"}),
            quota_ceilings=Quotas(100, 1024, 1024, 0),
            supported_majors={"control": 1, "data": 1})


# ---- 4. no actuation capability leaked into v1 (safety gate) ---------------

def test_no_actuation_capability_in_v1():
    from contracts.manifest import KNOWN_CAPABILITIES
    assert not any("actuat" in c or "write" in c or "valve" in c or "relay" in c
                   for c in KNOWN_CAPABILITIES), "v1 must remain monitoring-only"
