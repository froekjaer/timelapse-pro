"""Mission Platform contracts (ADR-002) — the platform/payload seam.

Landed tests-only in TimeLapse Pro: nothing in headend/ or edge/ imports this
package at runtime yet. It exists so the modular framework has a single,
versioned, machine-guarded contract surface that future extraction (P2-01 /
platform-payload split) migrates toward. Timelapse is the first payload.

INVARIANT (machine-enforced by tests/test_contracts_architecture.py):
this package imports nothing from headend/ or edge/.
"""
from .control import CONTROL_CONTRACT_VERSION
from .data import DATA_CONTRACT_VERSION
from .manifest import MANIFEST_VERSION

CONTRACT_VERSIONS = {
    "control": CONTROL_CONTRACT_VERSION,
    "data": DATA_CONTRACT_VERSION,
    "manifest": str(MANIFEST_VERSION),
}
