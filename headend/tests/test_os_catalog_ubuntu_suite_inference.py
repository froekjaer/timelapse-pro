"""_default_ubuntu_image_for_device() / _ubuntu_suite_for_version_label() —
derive the right Ubuntu release to compare a device's packages against,
instead of the hardcoded "ubuntu:24.04" that broke OS-security-update
candidates for Edge 2 (genuinely Ubuntu 22.04/jammy) on 2026-09-09.
"""
import main
from database import DeviceInventory


def test_default_image_matches_noble_device():
    inv = DeviceInventory(device_id="TL-TEST", os_name="Ubuntu 24.04.4 LTS")
    assert main._default_ubuntu_image_for_device(inv) == "ubuntu:24.04"


def test_default_image_matches_jammy_device():
    inv = DeviceInventory(device_id="TL-TEST", os_name="Ubuntu 22.04.5 LTS")
    assert main._default_ubuntu_image_for_device(inv) == "ubuntu:22.04"


def test_default_image_falls_back_to_noble_when_inventory_missing():
    assert main._default_ubuntu_image_for_device(None) == "ubuntu:24.04"


def test_ubuntu_suite_for_version_label_round_trips_with_version_label_for_suite():
    for suite in ("noble", "jammy", "focal", "bionic"):
        label = main._ubuntu_version_label_for_suite(suite)
        assert main._ubuntu_suite_for_version_label(label) == suite


def test_generate_os_update_catalog_candidates_fallback_uses_devices_suite(monkeypatch):
    # The Mac Docker builder path is exercised elsewhere; here we only need
    # to confirm the metadata fallback derives its suite from the resolved
    # `image`, not the function's own internal "noble" default.
    captured = {}

    def fake_mac_builder(**kwargs):
        raise main.HTTPException(status_code=409, detail="docker unavailable")

    def fake_metadata(*, installed, device_id, architecture, suite=None):
        captured["suite"] = suite
        return {"apt_list_text": "fake"}

    monkeypatch.setattr(main, "_generate_apt_list_from_mac_builder", fake_mac_builder)
    monkeypatch.setattr(main, "_generate_apt_list_from_ubuntu_metadata", fake_metadata)

    main._generate_os_update_catalog_candidates(
        installed={"nginx": "1.18.0"},
        device_id="TL-TEST",
        architecture="arm64",
        image="ubuntu:22.04",
    )
    assert captured["suite"] == "jammy"
