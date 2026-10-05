"""Headend camera page offers the camera's OWN values (Peter, 2026-10-04).

"det er rigtigt svært at sætte parametrene rigtigt": the camera page must not
only offer generic ISO/shutter/aperture lists, but the choices the camera
reported in the latest LAB "Hent parametre" scan (camera_params), mapped via
the profile's config_commands path — and the focus command fields get a
builder that picks a writable parameter and one of its values.
"""

from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "timelapse-ui" / "src"
LIB = (UI / "lib" / "cameraScan.ts").read_text(encoding="utf-8")
BUILDER = (UI / "components" / "CameraCommandBuilder.tsx").read_text(encoding="utf-8")
PAGE = (UI / "pages" / "CameraPage.tsx").read_text(encoding="utf-8")


def test_scan_read_from_stored_lab_parameters():
    assert "getDeviceRawConfig" in LIB
    assert "camera_params" in LIB and "camera_params_updated_at" in LIB
    assert "camera_profile?.config_commands" in LIB


def test_logical_key_mapped_through_profile_path_and_skip_respected():
    assert "spec?.path && p.path === spec.path" in LIB
    assert "spec?.skip" in LIB
    # The Edge sends value_map/skip_values first; camera labels follow.
    assert "skip_values" in LIB and "value_map" in LIB


def test_existing_override_never_silently_dropped():
    assert "if (current && !seen.has(current.toLowerCase())) out.unshift(current)" in LIB


def test_camera_page_uses_camera_options_and_explains_readonly():
    assert "cameraOptionsFor(cameraScan, param.key, val)" in PAGE
    assert "Skrivebeskyttet på dette kamera" in PAGE
    assert "Kameraets egne valg" in PAGE
    assert 'tryk "Hent parametre" i LAB' in PAGE


def test_focus_command_fields_get_builder_with_writable_params_only():
    assert "param.key.endsWith('_commands')" in PAGE
    assert "<CommandBuilder" in PAGE
    assert "filter(p => !p.readonly)" in BUILDER
    # Same key replaced, not duplicated, in the "k=v; k=v" string.
    assert "replace same key" in BUILDER
