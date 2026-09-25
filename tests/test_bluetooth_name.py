"""Tests for edge.bluetooth_name — deterministic DEVICE_NAME_SSID_IPV4
computation and BlueZ advertisement length handling."""

from __future__ import annotations

from edge.bluetooth_name import (
    ADVERTISEMENT_NAME_MAX_BYTES,
    compute_bluetooth_names,
    sanitize_ssid,
)
from edge.network_status import NetworkStatus


def _status(**overrides) -> NetworkStatus:
    base = {
        "mode": "wifi_client",
        "interface": "wlan0",
        "ssid": "KirkbiWiFi",
        "ipv4": "192.168.86.144",
        "connected": True,
        "checked_at": 0.0,
    }
    base.update(overrides)
    return NetworkStatus(**base)


def test_connected_wifi_produces_device_ssid_ip():
    names = compute_bluetooth_names("tl-modbaggarddlvc", _status())

    assert names.full == "tl-modbaggarddlvc_KirkbiWiFi_192.168.86.144"


def test_autonomous_ap_produces_device_ssid_ip():
    status = _status(mode="ap", ssid="TL-Service-A7C3", ipv4="192.168.4.1")

    names = compute_bluetooth_names("tl-modbaggarddlvc", status)

    assert names.full == "tl-modbaggarddlvc_TL-Service-A7C3_192.168.4.1"


def test_transitional_state_uses_deterministic_connecting_label():
    names = compute_bluetooth_names("tl-short", _status(mode="connecting", ssid=None, ipv4=None, connected=False))

    assert names.full == "tl-short_CONNECTING"
    assert names.advertisement == "tl-short_CONNECTING"


def test_transitional_state_shortens_label_not_hostname_when_over_budget():
    # "tl-modbaggarddlvc_CONNECTING" is 29 bytes, over the 26-byte legacy
    # advertisement budget — the fixed CONNECTING label is shortened, the
    # hostname (device identity) never is.
    names = compute_bluetooth_names("tl-modbaggarddlvc", _status(mode="connecting", ssid=None, ipv4=None, connected=False))

    assert names.full == "tl-modbaggarddlvc_CONNECTING"
    assert names.advertisement.startswith("tl-modbaggarddlvc_")
    assert len(names.advertisement.encode("utf-8")) <= ADVERTISEMENT_NAME_MAX_BYTES


def test_no_network_uses_same_deterministic_connecting_label():
    names = compute_bluetooth_names("tl-modbaggarddlvc", _status(mode="none", interface=None, ssid=None, ipv4=None, connected=False))

    assert names.full == "tl-modbaggarddlvc_CONNECTING"


def test_ssid_with_spaces_and_punctuation_is_sanitized_deterministically():
    status = _status(ssid="Kirkbi Guest WiFi! (5G)")

    names = compute_bluetooth_names("tl-modbaggarddlvc", status)

    assert " " not in names.full
    assert "!" not in names.full
    assert "(" not in names.full
    # Deterministic: same input always sanitizes the same way.
    again = compute_bluetooth_names("tl-modbaggarddlvc", status)
    assert names == again


def test_sanitize_ssid_is_deterministic_and_safe():
    assert sanitize_ssid("Kirkbi Guest WiFi! (5G)") == sanitize_ssid("Kirkbi Guest WiFi! (5G)")
    assert sanitize_ssid("") == "unknown-ssid"
    assert sanitize_ssid("   ") == "unknown-ssid"
    assert sanitize_ssid("a\x00b\x01c") == "abc"
    # Never introduces underscores/hyphens at the edges that would blur the
    # DEVICE_SSID_IP field boundaries.
    sanitized = sanitize_ssid("__weird--ssid__")
    assert not sanitized.startswith(("-", "_"))
    assert not sanitized.endswith(("-", "_"))


def test_sanitize_ssid_handles_unicode():
    result = sanitize_ssid("Café_Wörld 网络")
    assert result  # non-empty, deterministic, no exception
    assert sanitize_ssid("Café_Wörld 网络") == result


def test_long_ssid_is_truncated_for_advertisement_but_full_name_is_untouched():
    # A short hostname leaves enough budget that shortening only the SSID
    # (not dropping it) is achievable within ADVERTISEMENT_NAME_MAX_BYTES.
    long_ssid = "A" * 60
    status = _status(ssid=long_ssid, ipv4="10.0.0.5")

    names = compute_bluetooth_names("tl-x", status)

    assert names.full == f"tl-x_{long_ssid}_10.0.0.5"
    assert len(names.advertisement.encode("utf-8")) <= ADVERTISEMENT_NAME_MAX_BYTES
    # Device identity and IP are never ambiguous: both fully present.
    assert names.advertisement.startswith("tl-x_")
    assert names.advertisement.endswith("_10.0.0.5")


def test_long_hostname_and_ip_alone_already_exceed_budget_ssid_dropped_deterministically():
    # A realistic device hostname + a max-length IPv4 can already exceed the
    # legacy 26-byte advertisement budget before any SSID is even
    # considered (18 + 1 + 15 = 34 > 26). Known, documented limitation: see
    # edge/bluetooth_name.py's module docstring and the PR description.
    # SSID is still the only thing ever sacrificed — hostname and IP are
    # never shortened, even though that means this name won't fit the
    # legacy advertisement PDU. The *full* name (adapter Alias / GATT
    # Device Name) is unaffected and always carries the complete name.
    status = _status(ssid="AnySSID", ipv4="255.255.255.255")

    names = compute_bluetooth_names("tl-modbaggarddlvc", status)

    assert names.full == "tl-modbaggarddlvc_AnySSID_255.255.255.255"
    assert names.advertisement == "tl-modbaggarddlvc_255.255.255.255"  # SSID dropped, not truncated mid-word
    assert "AnySSID" not in names.advertisement
    assert len(names.advertisement.encode("utf-8")) > ADVERTISEMENT_NAME_MAX_BYTES  # documented limitation


def test_short_ssid_fits_within_advertisement_budget_unmodified():
    status = _status(ssid="AB", ipv4="10.0.0.5")

    names = compute_bluetooth_names("tl-short", status)

    assert names.advertisement == names.full == "tl-short_AB_10.0.0.5"
    assert len(names.advertisement.encode("utf-8")) <= ADVERTISEMENT_NAME_MAX_BYTES


def test_hostname_itself_is_sanitized():
    status = _status()
    names = compute_bluetooth_names("weird hostname!!", status)

    assert names.full.startswith("weird-hostname")
