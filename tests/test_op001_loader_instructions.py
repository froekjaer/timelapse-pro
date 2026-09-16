"""Regression protection for the mandatory OP-001 integrity-establishment
instruction across all four loader surfaces.

These tests check for stable required concepts/markers, not exact prose -
the four loaders are allowed to phrase things differently, but must all
gate consequential work on the actual reported state of
refresh_op001_cache.py, with the same four state -> action mapping. This
exists because an earlier version of the wording only said "run the
script" without tying any consequence to its output, which was a real,
exploitable compliant-but-hostile reading (an agent could run the script,
ignore what it reported, and proceed anyway).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]

LOADER_FILES = [
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "GEMINI.md",
    REPO_ROOT / "Dokumentation" / "CHATGPT-PROJECT-INSTRUCTIONS.md",
]

# Each loader must instruct running the actual mechanism, not just reading
# the cached file.
REQUIRED_COMMAND_MARKER = "python3 Dokumentation/mission-framework/refresh_op001_cache.py"

# Each loader must map all four reported states to a required action - not
# just mention the state names, but tie each to what the agent must do.
REQUIRED_STATE_ACTION_MARKERS = [
    "VERIFIED",
    "STALE",
    "UNKNOWN",
    "CORRUPTED",
    "do not treat the cache as current",  # STALE consequence
    "never silently treat it as VERIFIED",  # UNKNOWN consequence
    "do not use the cache as normative OP-001",  # CORRUPTED consequence
    "OP-001-dependent consequential work stops",  # CORRUPTED hard-stop consequence
]

# The instruction must not be reducible to "run it" with no gate - reject a
# regression back to prose that only says the file-read alone is
# insufficient without pairing it with an actual action requirement.
FORBIDDEN_UNGATED_PHRASING = "reading the file directly does not itself verify it"


def test_all_loaders_exist():
    for path in LOADER_FILES:
        assert path.is_file(), f"expected loader file missing: {path}"


def test_all_loaders_instruct_running_the_actual_mechanism():
    for path in LOADER_FILES:
        text = path.read_text(encoding="utf-8")
        assert REQUIRED_COMMAND_MARKER in text, f"{path.name} does not instruct running refresh_op001_cache.py"


def test_all_loaders_gate_on_every_reported_state():
    for path in LOADER_FILES:
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_STATE_ACTION_MARKERS if marker not in text]
        assert not missing, f"{path.name} is missing required state/action markers: {missing}"


def test_no_loader_regressed_to_ungated_phrasing_only():
    """The old wording ("run the script" with no consequence attached) must
    not silently come back - if this marker is present, verify it is
    accompanied by the actual state-action mapping, not used alone."""
    for path in LOADER_FILES:
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN_UNGATED_PHRASING in text:
            # Presence alone isn't necessarily wrong (it's still true prose),
            # but it must not be the ONLY instruction - the gated mapping
            # must also be present in the same file.
            missing = [marker for marker in REQUIRED_STATE_ACTION_MARKERS if marker not in text]
            assert not missing, (
                f"{path.name} contains the old ungated phrasing without the required "
                f"state-action mapping alongside it: missing {missing}"
            )


def test_loaders_are_semantically_consistent_with_each_other():
    """All four loaders must answer the same four test scenarios
    (VERIFIED / STALE / UNKNOWN-offline / CORRUPTED-no-backup) the same way.
    Checked by requiring the same marker set in every file - a loader that
    drops or contradicts one of these would fail here."""
    per_file_markers = {}
    for path in LOADER_FILES:
        text = path.read_text(encoding="utf-8")
        per_file_markers[path.name] = frozenset(m for m in REQUIRED_STATE_ACTION_MARKERS if m in text)

    reference = next(iter(per_file_markers.values()))
    for name, markers in per_file_markers.items():
        assert markers == reference, f"{name} has different state/action coverage than the others: {markers} vs {reference}"
