"""Tests for edge.network_status — the canonical management-path network
status used by Bluetooth naming, the technician CLI and (via the CLI) the
technician portal. All subprocess calls are mocked; nothing here touches a
real network stack or requires root."""

from __future__ import annotations

from pathlib import Path

from edge.network_status import (
    NetworkStatus,
    _ap_ssid,
    _wifi_interfaces,
    get_network_status,
)


def _make_sys_class_net(tmp_path: Path, ifaces: dict[str, dict]) -> Path:
    """Build a fake /sys/class/net tree. `ifaces` maps name -> {"wireless": bool}."""
    root = tmp_path / "sys_class_net"
    root.mkdir()
    for name, opts in ifaces.items():
        iface_dir = root / name
        iface_dir.mkdir()
        if opts.get("wireless"):
            (iface_dir / "wireless").mkdir()
    return root


def _mock_run(monkeypatch, responses: dict[tuple, str]) -> None:
    """responses maps a tuple(cmd) -> stdout text. Unmatched commands return ''."""

    def fake_run(cmd, timeout=3.0):
        return responses.get(tuple(cmd), "")

    monkeypatch.setattr("edge.network_status._run", fake_run)


def test_wifi_client_connected_with_ipv4(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}, "lo": {}})
    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "Interface wlan0\n\ttype managed\n",
            ("iw", "dev", "wlan0", "link"): "Connected to aa:bb:cc:dd:ee:ff\n\tSSID: KirkbiWiFi\n\tfreq: 5180\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "2: wlan0    inet 192.168.86.144/24 brd 192.168.86.255 scope global wlan0\n",
        },
    )

    status = get_network_status(sys_class_net=sys_net)

    assert status == NetworkStatus(
        mode="wifi_client",
        interface="wlan0",
        ssid="KirkbiWiFi",
        ipv4="192.168.86.144",
        connected=True,
        checked_at=status.checked_at,
    )
    assert status.has_usable_ip


def test_autonomous_ap_active_with_ap_ipv4(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    hostapd_conf = tmp_path / "hostapd.conf"
    hostapd_conf.write_text("interface=wlan0\ndriver=nl80211\nssid=TL-C87FF9587CA0\nhw_mode=g\n")
    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "Interface wlan0\n\ttype AP\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "2: wlan0    inet 192.168.43.1/24 scope global wlan0\n",
        },
    )

    status = get_network_status(sys_class_net=sys_net, hostapd_conf_paths=(hostapd_conf,))

    assert status.mode == "ap"
    assert status.ssid == "TL-C87FF9587CA0"
    assert status.ipv4 == "192.168.43.1"
    assert status.connected is True


def test_dhcp_ip_change_reflected_on_next_call(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    base_responses = {
        ("iw", "dev", "wlan0", "info"): "type managed\n",
        ("iw", "dev", "wlan0", "link"): "Connected to aa:bb\n\tSSID: KirkbiWiFi\n",
    }

    _mock_run(monkeypatch, {**base_responses, ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.86.144/24\n"})
    first = get_network_status(sys_class_net=sys_net)
    assert first.ipv4 == "192.168.86.144"

    _mock_run(monkeypatch, {**base_responses, ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.86.200/24\n"})
    second = get_network_status(sys_class_net=sys_net)
    assert second.ipv4 == "192.168.86.200"
    assert second.ssid == first.ssid == "KirkbiWiFi"


def test_ssid_change_reflected_on_next_call(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    ip_response = {("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.86.144/24\n"}

    _mock_run(
        monkeypatch,
        {**ip_response, ("iw", "dev", "wlan0", "info"): "type managed\n", ("iw", "dev", "wlan0", "link"): "Connected\n\tSSID: OldNetwork\n"},
    )
    first = get_network_status(sys_class_net=sys_net)
    assert first.ssid == "OldNetwork"

    _mock_run(
        monkeypatch,
        {**ip_response, ("iw", "dev", "wlan0", "info"): "type managed\n", ("iw", "dev", "wlan0", "link"): "Connected\n\tSSID: NewNetwork\n"},
    )
    second = get_network_status(sys_class_net=sys_net)
    assert second.ssid == "NewNetwork"


def test_transition_wifi_client_to_ap(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    hostapd_conf = tmp_path / "hostapd.conf"
    hostapd_conf.write_text("ssid=TL-C87FF9587CA0\n")

    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type managed\n",
            ("iw", "dev", "wlan0", "link"): "Connected\n\tSSID: KirkbiWiFi\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.86.144/24\n",
        },
    )
    before = get_network_status(sys_class_net=sys_net, hostapd_conf_paths=(hostapd_conf,))
    assert before.mode == "wifi_client"

    # Router Wi-Fi drops; the existing bash fallback (timelapse-wifi-ap.sh)
    # brings wlan0 up as an AP instead.
    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type AP\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.43.1/24\n",
        },
    )
    after = get_network_status(sys_class_net=sys_net, hostapd_conf_paths=(hostapd_conf,))
    assert after.mode == "ap"
    assert after.ssid == "TL-C87FF9587CA0"
    assert after.ipv4 == "192.168.43.1"


def test_transition_ap_to_wifi_client(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    hostapd_conf = tmp_path / "hostapd.conf"
    hostapd_conf.write_text("ssid=TL-C87FF9587CA0\n")

    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type AP\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.43.1/24\n",
        },
    )
    before = get_network_status(sys_class_net=sys_net, hostapd_conf_paths=(hostapd_conf,))
    assert before.mode == "ap"

    # Router Wi-Fi comes back; the fallback AP tears itself down and wlan0
    # reassociates as a client.
    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type managed\n",
            ("iw", "dev", "wlan0", "link"): "Connected\n\tSSID: KirkbiWiFi\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.86.144/24\n",
        },
    )
    after = get_network_status(sys_class_net=sys_net, hostapd_conf_paths=(hostapd_conf,))
    assert after.mode == "wifi_client"
    assert after.ssid == "KirkbiWiFi"


def test_no_network_interfaces_at_all(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"lo": {}, "eth0": {}})
    _mock_run(monkeypatch, {})

    status = get_network_status(sys_class_net=sys_net)

    assert status.mode == "none"
    assert status.interface is None
    assert status.ssid is None
    assert status.ipv4 is None
    assert status.connected is False


def test_connecting_when_associated_but_no_ip_yet(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type managed\n",
            ("iw", "dev", "wlan0", "link"): "Not connected\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "",
        },
    )

    status = get_network_status(sys_class_net=sys_net)

    assert status.mode == "connecting"
    assert status.connected is False
    assert status.ipv4 is None


def test_multiple_interfaces_ignores_docker_and_virtual(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(
        tmp_path,
        {
            "lo": {},
            "docker0": {},
            "veth1234": {},
            "br-abcdef123456": {},
            "tun0": {},
            "wg0": {},
            "wlan0": {"wireless": True},
        },
    )
    ifaces = _wifi_interfaces(sys_net)

    assert ifaces == ["wlan0"]

    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type managed\n",
            ("iw", "dev", "wlan0", "link"): "Connected\n\tSSID: KirkbiWiFi\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 192.168.86.144/24\n",
        },
    )
    status = get_network_status(sys_class_net=sys_net)
    assert status.interface == "wlan0"


def test_multiple_wifi_interfaces_prefers_deterministic_order(monkeypatch, tmp_path):
    sys_net = _make_sys_class_net(tmp_path, {"wlan1": {"wireless": True}, "wlan0": {"wireless": True}})
    assert _wifi_interfaces(sys_net) == ["wlan0", "wlan1"]  # sorted, deterministic


def test_ssid_with_spaces_and_special_chars_is_passed_through_raw(monkeypatch, tmp_path):
    """network_status returns the raw SSID; sanitization is bluetooth_name's job."""
    sys_net = _make_sys_class_net(tmp_path, {"wlan0": {"wireless": True}})
    _mock_run(
        monkeypatch,
        {
            ("iw", "dev", "wlan0", "info"): "type managed\n",
            ("iw", "dev", "wlan0", "link"): "Connected\n\tSSID: Kirkbi Guest WiFi! (5G)\n",
            ("ip", "-4", "-o", "addr", "show", "wlan0"): "inet 10.0.0.5/24\n",
        },
    )

    status = get_network_status(sys_class_net=sys_net)

    assert status.ssid == "Kirkbi Guest WiFi! (5G)"


def test_ap_ssid_missing_hostapd_conf_returns_none(tmp_path):
    assert _ap_ssid((tmp_path / "does-not-exist.conf",)) is None


def test_run_never_raises_on_missing_binary(monkeypatch):
    from edge.network_status import _run

    # No mocking here: exercise the real function against a command that
    # cannot exist, to prove subprocess failures never propagate as
    # exceptions — required so a network-status glitch can never affect
    # anything else on the Edge (see product requirement #9).
    assert _run(["definitely-not-a-real-binary-xyz"]) == ""
