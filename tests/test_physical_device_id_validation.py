"""Regression test (2026-08-06): MOD-BAGGARD-DLVC crash-looped forever from
its very first boot with "MAC-binding afvist: forventet MOD-BAGGARD-DLVC, men
denne Edge er TL-043EB9E72EFD" (edge/scripts/bootstrap_agent.py). Root cause:
the "Fysisk Edge-ID" ("expected_device_id") field, which gets baked into a
flashable image as a hard MAC-binding check, accepted ANY string of 3+ safe
characters — including a human-typed CMDB-draft-style name that could never
match the physical board's real MAC-derived identity.

Peter, after the incident: "Så skal vi fjerne muligheden for at tilføje et
navn, hvis det giver problemer" — remove the ability to type a name where
only the real MAC-derived ID can ever work.

_validate_physical_device_id() enforces the strict TL-<12 HEX> format used
everywhere else for real, MAC-derived device_ids (see
edge/scripts/bootstrap_agent.py::_derive_device_id) — distinct from the
looser _sanitize_device_id() (still needed for CMDB draft names and
TL-IMPORT-* virtual device_ids, which are legitimately free-form).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
BACKUP_PAGE = (ROOT / "timelapse-ui" / "src" / "pages" / "BackupPage.tsx").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = MAIN.index(f"def {name}(")
    end = MAIN.index("\n@app.", start + 1)
    return MAIN[start:end]


def test_validate_physical_device_id_enforces_strict_mac_format() -> None:
    section = _function_source("_validate_physical_device_id")
    assert r"^TL-[0-9A-F]{12}$" in section


def test_disk_image_build_uses_strict_validation_for_expected_device_id() -> None:
    start = MAIN.index('def trigger_edge_disk_image_build(')
    end = MAIN.index("\ndef ", start + 1)
    section = MAIN[start:end]
    assert "_validate_physical_device_id(body.expected_device_id)" in section


def test_wifi_inject_endpoint_uses_strict_validation_for_expected_device_id() -> None:
    start = MAIN.index('def inject_wifi_endpoint(')
    end = MAIN.index("\n@app.", start + 1)
    section = MAIN[start:end]
    assert "_validate_physical_device_id(body.expected_device_id)" in section


def test_frontend_enforces_physical_device_id_pattern_before_allowing_build() -> None:
    assert "const PHYSICAL_DEVICE_ID_PATTERN = /^TL-[0-9A-F]{12}$/" in BACKUP_PAGE
    assert "PHYSICAL_DEVICE_ID_PATTERN.test(diskBuildExpectedDeviceId.trim())" in BACKUP_PAGE
    assert "PHYSICAL_DEVICE_ID_PATTERN.test(wifiInjectDeviceId.trim())" in BACKUP_PAGE
