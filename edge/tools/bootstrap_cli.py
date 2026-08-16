#!/usr/bin/env python3
"""
TimeLapse Pro - local Edge bootstrap CLI.

Local-only network bootstrap for a new Edge before it can reach Headend.
Production operational configuration must still come from Headend/RBAC.
"""
from __future__ import annotations

import argparse
import getpass
import html
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - used on minimal bootstrap images
    yaml = None

EDGE_DIR = Path(os.getenv("TIMELAPSE_EDGE_DIR", "/opt/timelapse/edge"))
EDGE_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_FILE = "bootstrap.yaml"
NETWORK_FILE = "local_network.yaml"
SERVICE_NAME = os.getenv("TIMELAPSE_EDGE_SERVICE", "timelapse-edge")
DOCTOR_SCHEMA = "timelapse.edge.doctor.v1"
EXPECTED_SERVICES = (
    "timelapse-edge",
    "timelapse-bt-pan",
    "timelapse-bt-agent",
    "timelapse-captive",
    "timelapse-totp",
)
PHOTO_SETTINGS = {
    "exposure_comp": {
        "label": "Eksponeringskompensation",
        "path": "/main/capturesettings/exposurecompensation",
        "hint": "Typisk -2..+2 EV eller kameravalg som -1, 0, +1.",
    },
    "iso": {
        "label": "ISO",
        "path": "/main/imgsettings/iso",
        "hint": "Auto eller fast ISO, fx 100/200/400.",
    },
    "white_balance": {
        "label": "Hvidbalance",
        "path": "/main/imgsettings/whitebalance",
        "hint": "Auto, Daylight, Cloudy mv. afhænger af kamera.",
    },
    "shutter_speed": {
        "label": "Lukkertid",
        "path": "/main/capturesettings/shutterspeed",
        "hint": "Kameravalg, fx 1/125, 1/250.",
    },
    "aperture": {
        "label": "Blaende",
        "path": "/main/capturesettings/f-number",
        "hint": "Kameravalg, fx f/5.6, f/8, f/11.",
    },
    "focus_mode": {
        "label": "Fokusmode",
        "path": "/main/capturesettings/focusmode",
        "hint": "AF/MF afhænger af kamera og objektiv.",
    },
    "image_format": {
        "label": "Billedformat",
        "path": "/main/imgsettings/imageformat",
        "fallback_paths": ["/main/capturesettings/imagequality"],
        "hint": "JPEG anbefales til hurtig onsite QA.",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="TimeLapse Pro Edge local bootstrap")
    parser.add_argument("--base-dir", default=str(EDGE_DIR), help="Edge config directory")
    parser.add_argument("--status", action="store_true", help="Print local network/bootstrap status")
    parser.add_argument("--test-headend", action="store_true", help="Test Headend /api/health")
    parser.add_argument("--doctor", action="store_true", help="Run local commissioning/troubleshooting checks")
    parser.add_argument("--doctor-json", action="store_true", help="Print read-only commissioning evidence as JSON")
    parser.add_argument("--network-status", action="store_true", help="Print network interfaces, connections, routes and DNS")
    parser.add_argument("--wifi-connect", metavar="SSID", help="Connect WiFi SSID; password from TIMELAPSE_WIFI_PASSWORD")
    parser.add_argument("--ipv4-config", nargs=6, metavar=("DEVICE", "MODE", "ADDRESS", "GATEWAY", "DNS", "METRIC"), help="Configure IPv4 via NetworkManager. MODE is dhcp or static; use '-' for blank fields")
    parser.add_argument("--static-routes", nargs=2, metavar=("DEVICE", "ROUTES"), help="Set IPv4 static routes on active NetworkManager connection; comma-separated routes or '-' to clear")
    parser.add_argument("--network-preference", choices=["ethernet", "wifi", "4g"], help="Set preferred TimeLapse connectivity order")
    parser.add_argument("--qa-image", help="Run Edge CV QA against a local JPEG")
    parser.add_argument("--technician-report", action="store_true", help="Write local technician HTML report")
    parser.add_argument("--serve-ui", action="store_true", help="Retired; use the TOTP portal on HTTPS port 8443")
    parser.add_argument("--camera-detect", action="store_true", help="Run gphoto2 --auto-detect")
    parser.add_argument("--camera-summary", action="store_true", help="Print camera status/config summary")
    parser.add_argument("--camera-config", help="Print one gphoto2 config path")
    parser.add_argument("--set-camera-config", nargs=2, metavar=("PATH", "VALUE"), help="Set one gphoto2 config value")
    parser.add_argument("--photo-setting", nargs=2, metavar=("KEY", "VALUE"), help="Set named photo setting: exposure_comp, iso, white_balance, shutter_speed, aperture, focus_mode, image_format")
    parser.add_argument("--photo-status", action="store_true", help="Print photo technical camera settings")
    parser.add_argument("--autofocus", action="store_true", help="Trigger gphoto2 autofocus action if supported")
    parser.add_argument("--focus-drive", help="Trigger gphoto2 manual focus drive value, e.g. Near 1 or 500")
    parser.add_argument("--capture-test", nargs="?", const="", metavar="DIR", help="Capture a local test image to DIR")
    parser.add_argument("--gps-status", action="store_true", help="Print gpsd/gpspipe status")
    parser.add_argument("--npu-status", action="store_true", help="Print Edge AI/NPU status")
    parser.add_argument("--maintenance", action="store_true", help="Pause edge service and manage camera relay for camera commands")
    parser.add_argument("--service-status", action="store_true", help="Print unified local Service Session status")
    parser.add_argument("--service-operation", help="Run a canonical Service Operation through the shared backend")
    parser.add_argument("--service-param", action="append", default=[], metavar="KEY=VALUE", help="Parameter for --service-operation")
    parser.add_argument("--commissioning-report", action="store_true", help="Run CommissioningReport v1 through Service Operations")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if args.status:
        print_status(base_dir)
        return 0
    if args.test_headend:
        return 0 if test_headend(base_dir) else 1
    if args.doctor:
        return 0 if run_doctor(base_dir) else 1
    if args.doctor_json:
        evidence = collect_doctor_evidence(base_dir)
        print(json.dumps(evidence, indent=2, ensure_ascii=False))
        return 0 if evidence["status"] == "ok" else 1
    if args.network_status:
        print_network_status(detailed=True)
        return 0
    if args.wifi_connect:
        password = os.getenv("TIMELAPSE_WIFI_PASSWORD", "")
        return 0 if connect_wifi(args.wifi_connect, password) else 1
    if args.ipv4_config:
        device, mode, address, gateway, dns, metric = ["" if v == "-" else v for v in args.ipv4_config]
        return 0 if configure_ipv4(base_dir, device, mode, address, gateway, dns, metric) else 1
    if args.static_routes:
        device, routes = ["" if v == "-" else v for v in args.static_routes]
        return 0 if configure_static_routes(device, routes) else 1
    if args.network_preference:
        update_network_preference(base_dir, args.network_preference)
        print(f"Netvaerksprioritet: {', '.join(read_yaml(base_dir / NETWORK_FILE).get('connectivity', {}).get('preferred_order', []))}")
        return 0
    if args.qa_image:
        return 0 if qa_image(Path(args.qa_image), base_dir) else 1
    if args.technician_report:
        path = write_technician_report(base_dir)
        print(path)
        return 0
    if args.serve_ui:
        print("Lokal tekniker-UI er erstattet af TOTP-portalen: https://192.168.42.1:8443")
        return 2
    if args.camera_detect:
        return 0 if run_camera_operation("camera.hardware.inventory", lambda: camera_detect(), base_dir, args.maintenance) else 1
    if args.camera_summary:
        return 0 if run_camera_operation("camera.diagnostics", lambda: camera_summary(base_dir), base_dir, args.maintenance) else 1
    if args.camera_config:
        return 0 if run_camera_operation("camera.config.read", lambda: camera_get_config(args.camera_config), base_dir, args.maintenance, {"path": args.camera_config}) else 1
    if args.set_camera_config:
        path, value = args.set_camera_config
        return 0 if run_camera_operation("camera.config.set_temporary", lambda: camera_set_config(path, value), base_dir, args.maintenance, {"path": path, "value": value}) else 1
    if args.photo_setting:
        key, value = args.photo_setting
        return 0 if run_camera_operation("camera.config.set_temporary", lambda: camera_set_photo_setting(key, value), base_dir, args.maintenance) else 1
    if args.photo_status:
        return 0 if run_camera_operation("camera.config.read", lambda: print_photo_status(), base_dir, args.maintenance) else 1
    if args.autofocus:
        return 0 if run_camera_operation("camera.focus.auto", lambda: camera_autofocus(), base_dir, args.maintenance) else 1
    if args.focus_drive:
        return 0 if run_camera_operation("camera.focus.manual", lambda: camera_focus_drive(args.focus_drive), base_dir, args.maintenance, {"value": args.focus_drive}) else 1
    if args.capture_test is not None:
        out_dir = Path(args.capture_test or "/tmp/timelapse-tech-captures")
        return 0 if run_camera_operation("camera.capture.test", lambda: capture_test(out_dir, base_dir), base_dir, True, {"out_dir": str(out_dir)}) else 1
    if args.gps_status:
        print_gps_status()
        return 0
    if args.npu_status:
        print_npu_status(base_dir)
        return 0
    if args.service_status:
        print_service_session_status()
        return 0
    if args.commissioning_report:
        return 0 if print_service_operation("commissioning.run", base_dir, {"capture": False}) else 1
    if args.service_operation:
        return 0 if print_service_operation(args.service_operation, base_dir, parse_service_params(args.service_param)) else 1
    return menu(base_dir)


def menu(base_dir: Path) -> int:
    while True:
        print()
        print("TimeLapse Pro Edge servicetekniker")
        print("-----------------------------------")
        print("1. Overblik / status")
        print("2. Installation")
        print("3. Netvaerk og forbindelse")
        print("4. Fototeknik, kamera og testbilleder")
        print("5. Fejlsoegning og logs")
        print("6. Lokal tekniker-UI")
        print("7. Afslut")
        choice = input("Valg: ").strip()

        if choice == "1":
            print_status(base_dir, detailed=True)
        elif choice == "2":
            installation_menu(base_dir)
        elif choice == "3":
            network_menu(base_dir)
        elif choice == "4":
            camera_menu(base_dir)
        elif choice == "5":
            troubleshooting_menu(base_dir)
        elif choice == "6":
            ui_menu(base_dir)
        elif choice == "7":
            return 0
        else:
            print("Ugyldigt valg")


def installation_menu(base_dir: Path) -> None:
    while True:
        print()
        print("Installation")
        print("------------")
        print("1. Konfigurer Headend URL / bootstrap token")
        print("2. Test Headend forbindelse")
        print("3. Koer commissioning doctor")
        print("4. Generer tekniker-rapport")
        print("5. Tilbage")
        choice = input("Valg: ").strip()
        if choice == "1":
            configure_bootstrap(base_dir)
        elif choice == "2":
            test_headend(base_dir)
        elif choice == "3":
            run_doctor(base_dir)
        elif choice == "4":
            print(f"Rapport: {write_technician_report(base_dir)}")
        elif choice == "5":
            return
        else:
            print("Ugyldigt valg")


def network_menu(base_dir: Path) -> None:
    while True:
        print()
        print("Netvaerk og forbindelse")
        print("-----------------------")
        print("1. Netvaerksstatus, DNS og routing")
        print("2. Scan og tilslut WiFi")
        print("3. Konfigurer Ethernet IPv4")
        print("4. Konfigurer WiFi IPv4")
        print("5. Konfigurer 4G USB modem")
        print("6. Saet forbindelsesprioritet")
        print("7. Test Headend forbindelse")
        print("8. Tilbage")
        choice = input("Valg: ").strip()
        if choice == "1":
            print_network_status(detailed=True)
        elif choice == "2":
            configure_wifi(base_dir)
        elif choice == "3":
            configure_interface_ipv4(base_dir, "ethernet")
        elif choice == "4":
            configure_interface_ipv4(base_dir, "wifi")
        elif choice == "5":
            configure_gsm(base_dir)
        elif choice == "6":
            configure_network_preference(base_dir)
        elif choice == "7":
            test_headend(base_dir)
        elif choice == "8":
            return
        else:
            print("Ugyldigt valg")


def camera_menu(base_dir: Path) -> None:
    while True:
        print()
        print("Fototeknik, kamera og testbilleder")
        print("----------------------------------")
        print("1. Detect kamera via gphoto2")
        print("2. Fototeknisk status")
        print("3. Saet fototeknisk parameter")
        print("4. Autofokus")
        print("5. Manuel focus drive")
        print("6. Tag testbillede + lokal QA")
        print("7. QA-test eksisterende JPEG")
        print("8. Kamera status og config")
        print("9. Vis alle kamera config paths")
        print("10. Laes kamera config path")
        print("11. Saet ra gphoto2 config path")
        print("12. Tilbage")
        choice = input("Valg: ").strip()
        if choice == "1":
            camera_detect()
        elif choice == "2":
            print_photo_status()
        elif choice == "3":
            choose_photo_setting()
        elif choice == "4":
            camera_autofocus()
        elif choice == "5":
            value = input("Focus drive value, fx 'Near 1', 'Far 1' eller '500': ").strip()
            if value:
                camera_focus_drive(value)
        elif choice == "6":
            raw = input("Output mappe [/tmp/timelapse-tech-captures]: ").strip()
            capture_test(Path(raw or "/tmp/timelapse-tech-captures"), base_dir)
        elif choice == "7":
            raw = input("Sti til JPEG: ").strip()
            if raw:
                qa_image(Path(raw), base_dir)
        elif choice == "8":
            camera_summary(base_dir)
        elif choice == "9":
            camera_list_config()
        elif choice == "10":
            raw = input("gphoto2 path, fx /main/capturesettings/focusmode: ").strip()
            if raw:
                camera_get_config(raw)
        elif choice == "11":
            path = input("gphoto2 path: ").strip()
            value = input("Ny vaerdi: ").strip()
            if path and value:
                camera_set_config(path, value)
        elif choice == "12":
            return
        else:
            print("Ugyldigt valg")


def troubleshooting_menu(base_dir: Path) -> None:
    while True:
        print()
        print("Fejlsoegning og logs")
        print("--------------------")
        print("1. Koer lokal doctor")
        print("2. Service status")
        print("3. Seneste service logs")
        print("4. Upload-koe og lokal storage")
        print("5. GPS status")
        print("6. NPU / Edge AI status")
        print("7. System journal fejl")
        print("8. Tilbage")
        choice = input("Valg: ").strip()
        if choice == "1":
            run_doctor(base_dir)
        elif choice == "2":
            print_service_status()
        elif choice == "3":
            show_logs(SERVICE_NAME, lines=120)
        elif choice == "4":
            print_storage_status(base_dir)
        elif choice == "5":
            print_gps_status()
        elif choice == "6":
            print_npu_status(base_dir)
        elif choice == "7":
            show_logs("", lines=80, priority="warning")
        elif choice == "8":
            return
        else:
            print("Ugyldigt valg")


def ui_menu(base_dir: Path) -> None:
    while True:
        print()
        print("Lokal tekniker-UI")
        print("-----------------")
        print("1. Generer HTML statusrapport")
        print("2. Vis lokal TOTP-adresse")
        print("3. Tilbage")
        choice = input("Valg: ").strip()
        if choice == "1":
            print(f"Rapport: {write_technician_report(base_dir)}")
        elif choice == "2":
            print("Brug den beskyttede lokale management-portal: https://192.168.42.1:8443")
        elif choice == "3":
            return
        else:
            print("Ugyldigt valg")


def configure_bootstrap(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_path = base_dir / BOOTSTRAP_FILE
    data = read_yaml(bootstrap_path)

    current_url = data.get("headend_url", "https://timelapse.example.com/api")
    headend_url = input(f"Headend API URL [{current_url}]: ").strip() or current_url
    parsed = urlparse(headend_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        print("Fejl: Headend URL skal ligne https://host/api")
        return
    if parsed.scheme != "https":
        confirm = input("HTTP er kun til LAB. Fortsaet? [nej/ja]: ").strip().lower()
        if confirm != "ja":
            print("Afbrudt")
            return

    current_device_id = data.get("device_id") or derive_device_id_fallback()
    device_id = input(f"Device ID [{current_device_id}]: ").strip() or current_device_id
    token_prompt = "Bootstrap token [behold eksisterende hvis tom]: "
    token = getpass.getpass(token_prompt).strip()

    data["headend_url"] = headend_url.rstrip("/")
    data["device_id"] = device_id
    if token:
        data["bootstrap_token"] = token
    elif "bootstrap_token" not in data:
        print("Advarsel: ingen bootstrap_token gemt endnu")

    write_yaml(bootstrap_path, data, mode=0o600)
    print(f"Gemt: {bootstrap_path}")


def configure_wifi(base_dir: Path | None = None) -> None:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. Installer/aktiver NetworkManager paa Edge.")
        return

    print("Scanner WiFi...")
    run(["nmcli", "device", "wifi", "rescan"], check=False, timeout=15)
    result = run([
        "nmcli", "--escape", "no", "-t", "-f",
        "IN-USE,SSID,SIGNAL,SECURITY",
        "device", "wifi", "list",
    ], check=False, timeout=20)
    networks = parse_wifi_list(result.stdout)
    if not networks:
        print("Ingen WiFi-netvaerk fundet")
        return

    for idx, net in enumerate(networks, 1):
        active = "*" if net["active"] else " "
        print(f"{idx:2d}. {active} {net['ssid']}  {net['signal']}%  {net['security']}")

    raw = input("Vaelg netvaerk nummer eller skriv SSID: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(networks):
        ssid = networks[int(raw) - 1]["ssid"]
        security = networks[int(raw) - 1]["security"]
    else:
        ssid = raw
        security = "unknown"
    if not ssid:
        print("Afbrudt")
        return

    password = ""
    if security and security != "--":
        password = getpass.getpass("WiFi password (gemmes kun i NetworkManager): ")

    if connect_wifi(ssid, password) and base_dir is not None:
        update_network_preference(base_dir, "wifi")


def configure_interface_ipv4(base_dir: Path, device_type: str) -> None:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. Installer/aktiver NetworkManager paa Edge.")
        return

    devices = nmcli_devices(device_type)
    if not devices:
        print(f"Ingen {device_type} interface fundet")
        return
    device = choose_device(devices)
    if not device:
        return

    mode_raw = input("IPv4 mode: [1] DHCP, [2] Static: ").strip() or "1"
    mode = "dhcp" if mode_raw == "1" else "static" if mode_raw == "2" else mode_raw.lower()
    address = gateway = dns = metric = ""
    if mode == "static":
        address = input("IPv4/CIDR, fx 192.168.1.50/24: ").strip()
        gateway = input("Gateway: ").strip()
        dns = input("DNS, komma-separeret [1.1.1.1,8.8.8.8]: ").strip() or "1.1.1.1,8.8.8.8"
    metric = input("Route metric [tom=auto, lavere prioriteres]: ").strip()
    configure_ipv4(base_dir, device, mode, address, gateway, dns, metric)


def configure_ethernet(base_dir: Path) -> None:
    configure_interface_ipv4(base_dir, "ethernet")


def connect_wifi(ssid: str, password: str = "") -> bool:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. Installer/aktiver NetworkManager paa Edge.")
        return False
    ssid = (ssid or "").strip()
    if not ssid:
        print("SSID mangler")
        return False
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd.extend(["password", password])
    result = run(cmd, check=False, timeout=45)
    if result.returncode == 0:
        print("WiFi tilsluttet")
        return True
    print("WiFi tilslutning fejlede:")
    print(result.stderr or result.stdout)
    return False


def configure_ipv4(base_dir: Path, device: str, mode: str, address: str = "", gateway: str = "", dns: str = "", metric: str = "") -> bool:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. Installer/aktiver NetworkManager paa Edge.")
        return False
    device = (device or "").strip()
    mode = (mode or "").strip().lower()
    if not device or mode not in {"dhcp", "static"}:
        print("Brug: DEVICE og MODE=dhcp|static")
        return False

    info = nmcli_device_info(device)
    device_type = info.get("type") or "ethernet"
    con_name = info.get("connection") or ""
    if con_name and con_name != "--":
        cmd = ["nmcli", "connection", "modify", con_name, "ipv6.method", "ignore"]
    else:
        if device_type == "wifi":
            print("WiFi har ingen aktiv forbindelse at ændre. Tilslut SSID først.")
            return False
        con_name = f"timelapse-{device_type}-{device}"
        run(["nmcli", "connection", "delete", con_name], check=False)
        cmd = [
            "nmcli", "connection", "add", "type", device_type,
            "ifname", device, "con-name", con_name,
            "ipv6.method", "ignore",
        ]
    if mode == "dhcp":
        cmd.extend(["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
    else:
        if not address:
            print("Statisk IPv4 kraever address i CIDR-format")
            return False
        cmd.extend(["ipv4.method", "manual", "ipv4.addresses", address])
        if gateway:
            cmd.extend(["ipv4.gateway", gateway])
        if dns:
            cmd.extend(["ipv4.dns", dns])
    if metric:
        cmd.extend(["ipv4.route-metric", metric])

    result = run(cmd, check=False, timeout=20)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return False
    up = run(["nmcli", "connection", "up", con_name], check=False, timeout=30)
    if up.returncode != 0:
        print(up.stderr or up.stdout)
        return False
    if device_type in {"ethernet", "wifi", "gsm"}:
        update_network_preference(base_dir, "4g" if device_type == "gsm" else device_type)
    print(f"IPv4 {mode} konfigureret for {device} ({con_name})")
    return True


def configure_static_routes(device: str, routes: str) -> bool:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. Installer/aktiver NetworkManager paa Edge.")
        return False
    info = nmcli_device_info((device or "").strip())
    con_name = info.get("connection") or ""
    if not con_name or con_name == "--":
        print("Ingen aktiv NetworkManager connection fundet for interface")
        return False
    normalized = " ".join(part.strip() for part in (routes or "").replace(",", ";").split(";") if part.strip())
    cmd = ["nmcli", "connection", "modify", con_name, "ipv4.routes", normalized]
    result = run(cmd, check=False, timeout=15)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return False
    up = run(["nmcli", "connection", "up", con_name], check=False, timeout=30)
    if up.returncode != 0:
        print(up.stderr or up.stdout)
        return False
    print(f"Statiske IPv4 routes opdateret for {device}: {normalized or '(ryddet)'}")
    return True


def configure_network_preference(base_dir: Path) -> None:
    print("Forbindelsesprioritet")
    print("1. Ethernet foerst")
    print("2. WiFi foerst")
    print("3. 4G foerst")
    raw = input("Valg: ").strip()
    mapping = {"1": "ethernet", "2": "wifi", "3": "4g"}
    first = mapping.get(raw, raw.lower())
    if first not in {"ethernet", "wifi", "4g"}:
        print("Afbrudt")
        return
    update_network_preference(base_dir, first)
    print(f"Prioritet: {', '.join(read_yaml(base_dir / NETWORK_FILE).get('connectivity', {}).get('preferred_order', []))}")


def configure_gsm(base_dir: Path) -> None:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. 4G USB modem kraever NetworkManager/ModemManager.")
        return

    devices = nmcli_devices("gsm")
    if not devices:
        print("Ingen GSM/4G modem fundet via nmcli. Tjek USB, SIM og ModemManager.")
        return
    device = choose_device(devices)
    if not device:
        return

    apn = input("APN: ").strip()
    if not apn:
        print("APN er paakraevet")
        return
    username = input("APN brugernavn [tom hvis ikke brugt]: ").strip()
    password = getpass.getpass("APN password [tom hvis ikke brugt]: ").strip()
    con_name = f"timelapse-4g-{device}"

    run(["nmcli", "connection", "delete", con_name], check=False)
    cmd = [
        "nmcli", "connection", "add", "type", "gsm",
        "ifname", device, "con-name", con_name,
        "apn", apn,
    ]
    if username:
        cmd.extend(["user", username])
    if password:
        cmd.extend(["password", password])
    run(cmd)
    run(["nmcli", "connection", "up", con_name], check=False, timeout=45)
    update_network_preference(base_dir, "4g")
    print(f"4G modem konfigureret: {device}")


def print_status(base_dir: Path, detailed: bool = False) -> None:
    print("Config directory:", base_dir)
    bootstrap = read_yaml(base_dir / BOOTSTRAP_FILE)
    network = read_yaml(base_dir / NETWORK_FILE)
    print("Device ID:", bootstrap.get("device_id") or derive_device_id_fallback())
    print("Headend URL:", bootstrap.get("headend_url", "(ikke sat)"))
    print("Bootstrap token:", "sat" if bootstrap.get("bootstrap_token") else "mangler")
    print("Network preference:", network.get("connectivity", {}).get("preferred_order", ["ethernet", "wifi"]))
    print("Service:", service_state(SERVICE_NAME).get("active", "ukendt"))
    diag = collect_local_status(base_dir)
    if diag.get("system"):
        sysinfo = diag["system"]
        print("Platform:", sysinfo.get("platform"))
        print("Uptime:", format_seconds(sysinfo.get("uptime_s")))
    if diag.get("storage"):
        storage = diag["storage"]
        print("Disk:", summarize_storage(storage))
        print("Upload-koe:", storage.get("upload_queue_size", "ukendt"))
    if command_exists("nmcli"):
        print()
        print(run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], check=False).stdout)
    else:
        print("nmcli: ikke installeret")
    if detailed:
        print()
        print("Kamera:")
        camera_summary(base_dir, compact=True)
        print()
        print("GPS:")
        print_gps_status(compact=True)
        print()
        print("NPU / AI:")
        print_npu_status(base_dir, compact=True)


def run_doctor(base_dir: Path) -> bool:
    """Run local checks useful during Edge commissioning and support calls."""
    evidence = collect_doctor_evidence(base_dir)

    print()
    print("TimeLapse Edge doctor")
    print("---------------------")
    for check in evidence["checks"]:
        status = "OK" if check["ok"] else "FEJL"
        print(f"{status:4} {check['label']:24} {check['detail']}")

    failed = [check["label"] for check in evidence["checks"] if not check["ok"]]
    if failed:
        print()
        print("Anbefalet naeste skridt:")
        for label in failed[:6]:
            print(f"- Ret/tjek: {label}")
    return evidence["status"] == "ok"


def collect_doctor_evidence(base_dir: Path) -> dict[str, Any]:
    """Collect bounded, read-only commissioning evidence without secret values."""
    checks: list[dict[str, Any]] = []

    def add(check_id: str, label: str, ok: bool, detail: Any) -> None:
        checks.append({
            "id": check_id,
            "label": label,
            "ok": bool(ok),
            "detail": str(detail),
        })

    bootstrap_path = base_dir / BOOTSTRAP_FILE
    network_path = base_dir / NETWORK_FILE
    bootstrap = read_yaml(bootstrap_path)
    config = read_yaml(base_dir / "config.yaml")
    edge_ai = ((config.get("quality", {}) or {}).get("edge_ai", {}) or {})

    add("config.directory", "config directory", base_dir.exists(), base_dir)
    add("config.bootstrap", "bootstrap.yaml", bootstrap_path.exists(), bootstrap_path)
    add("identity.credential", "bootstrap token", bool(bootstrap.get("bootstrap_token")), "sat" if bootstrap.get("bootstrap_token") else "mangler")
    add("config.headend_url", "headend url", bool(bootstrap.get("headend_url")), bootstrap.get("headend_url", "mangler"))
    add("config.network", "local_network.yaml", network_path.exists(), network_path)

    for name in ["nmcli", "ip", "systemctl", "gphoto2"]:
        path = shutil.which(name)
        add(f"command.{name}", f"kommando: {name}", path is not None, path or "mangler")

    receipt_path = base_dir / ".timelapse-release.json"
    receipt = read_json_object(receipt_path)
    receipt_ok = receipt.get("schema") == "timelapse.edge.release.v1" and bool(
        receipt.get("artifact_id") and (receipt.get("source_commit") or receipt.get("version"))
    )
    release_detail = receipt.get("artifact_id") or "mangler/ugyldig"
    add("release.receipt", "release receipt", receipt_ok, release_detail)

    runner = edge_ai.get("runner") or os.getenv("TIMELAPSE_EDGE_AI_RUNNER", "")
    model_path = edge_ai.get("model_path") or os.getenv("TIMELAPSE_EDGE_AI_MODEL", "")
    vendor_binary = edge_ai.get("vendor_binary") or os.getenv("TIMELAPSE_EDGE_AI_VENDOR_BINARY", "")
    if edge_ai.get("enabled") or runner or model_path or vendor_binary:
        runner_cmd = shlex.split(str(runner)) if runner else []
        runner_executable = runner_cmd[0] if runner_cmd else ""
        runner_path = (
            shutil.which(runner_executable)
            if runner_executable and "/" not in runner_executable
            else runner_executable
        )
        runner_script = next(
            (item for item in runner_cmd[1:] if item.endswith(".py")),
            "",
        )
        runner_ok = bool(runner_path and Path(runner_path).exists())
        if runner_script:
            runner_ok = runner_ok and Path(runner_script).exists()
        vendor_cmd = shlex.split(str(vendor_binary)) if vendor_binary else []
        vendor_path = (
            shutil.which(vendor_cmd[0])
            if vendor_cmd and "/" not in vendor_cmd[0]
            else (vendor_cmd[0] if vendor_cmd else "")
        )
        add("ai.enabled", "edge QA AI", bool(edge_ai.get("enabled", False)), "enabled" if edge_ai.get("enabled") else "disabled")
        add("ai.runner", "NPU runner", runner_ok, str(runner) or "mangler")
        add("ai.model", "NPU model", bool(model_path and Path(str(model_path)).exists()), str(model_path) or "mangler")
        add("ai.vendor_wrapper", "VIPLite wrapper", bool(vendor_path and Path(vendor_path).exists()), str(vendor_binary) or "mangler")

    add("runtime.python", "python", True, platform.python_version())
    add("runtime.platform", "platform", True, platform.platform())

    if command_exists("systemctl"):
        for service in EXPECTED_SERVICES:
            state = service_state(service)
            active = state.get("active", "ukendt")
            add(f"service.{service}", f"service: {service}", active == "active", active)

    if command_exists("ip"):
        route = run(["ip", "route", "show", "default"], check=False, timeout=5)
        add("network.default_route", "default route", route.returncode == 0 and bool(route.stdout.strip()), first_line(route.stdout or route.stderr) or "mangler")

    failed_count = sum(1 for check in checks if not check["ok"])
    return {
        "schema": DOCTOR_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_id": bootstrap.get("device_id") or derive_device_id_fallback(),
        "status": "ok" if failed_count == 0 else "degraded",
        "summary": {"passed": len(checks) - failed_count, "failed": failed_count},
        "checks": checks,
    }


def qa_image(path: Path, base_dir: Path) -> bool:
    """Run deterministic Edge CV QA for a local image."""
    if not path.exists():
        print(f"Billedfil findes ikke: {path}")
        return False
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        print("QA-testen forventer JPEG (.jpg/.jpeg)")
        return False

    sys.path.insert(0, str(EDGE_ROOT))
    try:
        from capture.quality import QualityChecker
    except Exception as exc:
        print(f"Kunne ikke importere QualityChecker: {exc}")
        return False

    cfg = read_yaml(base_dir / "config.yaml")
    if not cfg:
        cfg = {
            "quality": {
                "check_enabled": True,
                "blur_threshold": 80,
                "dark_threshold": 25,
                "bright_threshold": 230,
            }
        }
    report = QualityChecker(cfg).qa_report(path)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return bool(report.get("flag") != "error")


def run_camera_operation(operation_name: str, operation=None, base_dir: Path | None = None, maintenance: bool = False, operation_kwargs: dict[str, Any] | None = None) -> bool:
    """Run a camera operation through the shared Service Operations backend."""
    if callable(operation_name):
        operation, operation_name, base_dir = operation_name, "camera.diagnostics", operation
    if operation is None or base_dir is None:
        raise TypeError("run_camera_operation requires an operation and base_dir")
    if not maintenance:
        return bool(operation())

    sys.path.insert(0, str(EDGE_ROOT))
    from camera.maintenance import CameraMaintenanceLease
    from service_operations import create_service_platform

    with CameraMaintenanceLease(timeout_s=45):
        state_dir = os.getenv("TIMELAPSE_SERVICE_STATE_DIR")
        platform = create_service_platform(base_dir=base_dir, state_dir=Path(state_dir) if state_dir else None)
        session = platform.current_session()
        if not session:
            print("Service Session kræver en aktiv EdgeServiceGrant eller eksplicit offline-recovery session.")
            return False
        result = platform.call(operation_name, session=session, release_after=True, **(operation_kwargs or {}))
        return bool(result.get("ok", True))


def _run_camera_maintenance_callback(operation, base_dir: Path, already_powered: bool) -> bool:
    was_active = is_service_active(SERVICE_NAME)
    should_restore_service = was_active or is_service_enabled(SERVICE_NAME)
    relay = None
    print("Vedligeholdelsestilstand: pauser edge-agent og overtager kamera midlertidigt")
    try:
        if was_active:
            systemctl("stop", SERVICE_NAME, timeout=120)
            wait_for_service_state(SERVICE_NAME, "inactive", timeout_s=20)
        relay = build_relay(base_dir)
        if relay is not None and not already_powered:
            relay.camera.power_on()
        elif already_powered:
            print("Service Session: kamera er allerede tændt — ingen ny warmup")
        else:
            print("Relæ kunne ikke initialiseres; fortsætter uden power-control")
            time.sleep(3)
        return bool(operation())
    finally:
        if relay is not None and not already_powered:
            try:
                relay.camera.force_off()
            except Exception as exc:
                print(f"Advarsel: kunne ikke slukke kamerarelæ: {exc}")
            try:
                relay.cleanup(camera=True, modem=False)
            except Exception:
                pass
        if should_restore_service:
            systemctl("start", SERVICE_NAME, timeout=60)
            wait_for_service_state(SERVICE_NAME, "active", timeout_s=30)
            print("Edge-agent startet igen")


def print_service_session_status() -> None:
    sys.path.insert(0, str(EDGE_ROOT))
    from service_platform import ServicePlatform

    status = ServicePlatform().status()
    rows = [
        ("logged in", status.get("logged_in")),
        ("camera relay", "ON" if status.get("camera_relay_on") else "OFF"),
        ("camera detected", status.get("camera_detected")),
        ("PTP connected", status.get("ptp_connected")),
        ("Live View", status.get("live_view")),
        ("Config dirty", f"{status.get('config_dirty_count', 0)} changes"),
        ("Session expires", _format_seconds(status.get("session_expires_in_s"))),
        ("Grant expires", _format_seconds(status.get("grant_expires_in_s"))),
        ("Last activity", _format_seconds(status.get("last_activity_s"), suffix="ago")),
    ]
    print("Service Session")
    print("---------------")
    for label, value in rows:
        print(f"{label}: {value}")


def print_service_operation(operation: str, base_dir: Path, params: dict[str, Any] | None = None) -> bool:
    sys.path.insert(0, str(EDGE_ROOT))
    from service_operations import create_service_platform

    state_dir = os.getenv("TIMELAPSE_SERVICE_STATE_DIR")
    platform = create_service_platform(base_dir=base_dir, state_dir=Path(state_dir) if state_dir else None)
    session = platform.current_session()
    if not session:
        print("Service Session kræver en aktiv EdgeServiceGrant eller eksplicit offline-recovery session.")
        return False
    result = platform.call(operation, session=session, release_after=True, **(params or {}))
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return bool(result.get("ok", True) or result.get("result") in {"PASS", "PASS WITH DEVIATIONS"})


def parse_service_params(raw: list[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in raw or []:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        lowered = value.lower()
        if lowered in {"true", "false"}:
            params[key] = lowered == "true"
        else:
            params[key] = value
    return params


def _format_seconds(value, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    minutes = max(0, int(value)) // 60
    rendered = f"{minutes} min" if minutes else f"{max(0, int(value))} sec"
    return f"{rendered} {suffix}".strip()


def build_relay(base_dir: Path):
    try:
        sys.path.insert(0, str(EDGE_ROOT))
        from camera.relay import RelayController
        cfg = read_yaml(base_dir / "config.yaml")
        return RelayController(cfg or {})
    except Exception as exc:
        print(f"Relæ-init fejlede: {exc}")
        return None


def is_service_active(service: str) -> bool:
    if not command_exists("systemctl"):
        return False
    result = run(["systemctl", "is-active", service], check=False, timeout=5)
    return result.stdout.strip() == "active"


def is_service_enabled(service: str) -> bool:
    if not command_exists("systemctl"):
        return False
    result = run(["systemctl", "is-enabled", service], check=False, timeout=5)
    return result.stdout.strip() in {"enabled", "enabled-runtime"}


def systemctl(action: str, service: str, timeout: int = 30) -> None:
    if not command_exists("systemctl"):
        return
    cmd = ["systemctl", action, service]
    if os.geteuid() != 0 and command_exists("sudo"):
        cmd.insert(0, "sudo")
    try:
        result = run(cmd, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        if action == "stop":
            print(f"systemctl stop timeout efter {timeout}s; bruger systemctl kill")
            kill_cmd = ["systemctl", "kill", service]
            if os.geteuid() != 0 and command_exists("sudo"):
                kill_cmd.insert(0, "sudo")
            run(kill_cmd, check=False, timeout=20)
            return
        raise
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"systemctl {action} {service} fejlede")


def wait_for_service_state(service: str, expected: str, timeout_s: int = 20) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = run(["systemctl", "is-active", service], check=False, timeout=5)
        state = result.stdout.strip()
        if state == expected or (expected == "inactive" and state in {"inactive", "failed", "unknown"}):
            return
        time.sleep(1)
    raise RuntimeError(f"Service {service} nåede ikke tilstand {expected} inden {timeout_s}s")


def camera_detect() -> bool:
    result = run(["gphoto2", "--auto-detect"], check=False, timeout=20)
    print(result.stdout or result.stderr or "(intet output)")
    return result.returncode == 0 and "usb:" in (result.stdout or "").lower()


def camera_summary(base_dir: Path, compact: bool = False) -> bool:
    if not command_exists("gphoto2"):
        print("gphoto2 mangler")
        return False
    ok = camera_detect()
    paths = [
        "/main/status/batterylevel",
        "/main/status/lensname",
        "/main/status/eosserialnumber",
        "/main/status/shuttercounter",
        "/main/status/availableshots",
        "/main/capturesettings/focusmode",
        "/main/capturesettings/exposurecompensation",
        "/main/capturesettings/shutterspeed",
        "/main/capturesettings/f-number",
        "/main/imgsettings/iso",
        "/main/imgsettings/whitebalance",
        "/main/imgsettings/imageformat",
    ]
    for path in paths:
        value = read_gphoto_current(path)
        if value is not None:
            print(f"{path}: {value}")
    if not compact:
        print()
        print("Tip: Brug 'Vis alle kamera config paths' for at se mulige fokus- og eksponeringsvalg.")
    return ok


def camera_list_config() -> bool:
    result = run(["gphoto2", "--list-all-config"], check=False, timeout=30)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return False
    current_path = ""
    for line in result.stdout.splitlines():
        if line.startswith("/main/"):
            current_path = line.strip()
            print()
            print(current_path)
        elif line.startswith(("Label:", "Readonly:", "Current:", "Choice:", "Bottom:", "Top:", "Step:")):
            print("  " + line.strip())
    return True


def camera_get_config(path: str) -> bool:
    result = run(["gphoto2", "--get-config", path], check=False, timeout=10)
    print(result.stdout or result.stderr)
    return result.returncode == 0


def camera_set_config(path: str, value: str) -> bool:
    print(f"Saetter {path} = {value}")
    result = run(["gphoto2", "--set-config", f"{path}={value}"], check=False, timeout=15)
    if result.returncode == 0:
        print("OK")
        return True
    print(result.stderr or result.stdout)
    return False


def print_photo_status() -> bool:
    if not command_exists("gphoto2"):
        print("gphoto2 mangler")
        return False
    ok = camera_detect()
    for key, spec in PHOTO_SETTINGS.items():
        value = None
        for path in [spec["path"], *spec.get("fallback_paths", [])]:
            value = read_gphoto_current(path)
            if value is not None:
                break
        print(f"{key:16} {spec['label']}: {value if value is not None else '(ikke fundet)'}")
    return ok


def choose_photo_setting() -> bool:
    keys = list(PHOTO_SETTINGS)
    for idx, key in enumerate(keys, 1):
        spec = PHOTO_SETTINGS[key]
        current = read_gphoto_current(spec["path"])
        print(f"{idx}. {spec['label']} ({key}) = {current if current is not None else 'ikke fundet'}")
        print(f"   {spec['hint']}")
    raw = input("Vaelg parameter nummer eller key: ").strip()
    key = keys[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(keys) else raw
    if key not in PHOTO_SETTINGS:
        print("Ukendt fototeknisk parameter")
        return False
    value = input("Ny vaerdi: ").strip()
    if not value:
        print("Afbrudt")
        return False
    return camera_set_photo_setting(key, value)


def camera_set_photo_setting(key: str, value: str) -> bool:
    spec = PHOTO_SETTINGS.get((key or "").strip())
    if not spec:
        print(f"Ukendt fototeknisk parameter: {key}")
        print("Mulige keys:", ", ".join(PHOTO_SETTINGS))
        return False
    print(f"{spec['label']}: {value}")
    for path in [spec["path"], *spec.get("fallback_paths", [])]:
        if gphoto_config_exists(path):
            return camera_set_config(path, value)
    print(f"Ingen understøttet config-path fundet for {spec['label']}")
    return False


def camera_autofocus() -> bool:
    candidates = [
        "/main/actions/autofocusdrive",
        "/main/actions/autofocus",
    ]
    for path in candidates:
        if not gphoto_config_exists(path):
            continue
        if camera_set_config(path, "1"):
            return True
    print("Autofokus-action blev ikke fundet. Tjek kameraets fokusmode og liveview.")
    return False


def camera_focus_drive(value: str) -> bool:
    candidates = [
        "/main/actions/manualfocusdrive",
        "/main/actions/manualfocusdrive2",
    ]
    for path in candidates:
        if not gphoto_config_exists(path):
            continue
        if camera_set_config(path, value):
            return True
    print("Manual focus drive blev ikke fundet. Kamera/objektiv understoetter muligvis ikke remote focus.")
    return False


def capture_test(out_dir: Path, base_dir: Path) -> bool:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Tager testbillede til {out_dir} ...")
    sys.path.insert(0, str(EDGE_ROOT))
    try:
        from camera.registry import get_driver
    except Exception as exc:
        print(f"Kunne ikke importere kameradriver: {exc}")
        return False

    cfg = read_yaml(base_dir / "config.yaml")
    if not cfg:
        cfg = {"device": {"device_id": derive_device_id_fallback()}, "camera": {}, "schedule": {}, "location": {}}
    driver = get_driver(cfg)
    try:
        driver.connect()
        if not hasattr(driver, "capture_preview"):
            raise RuntimeError("Driveren understøtter ikke preview-capture")
        print("Tager preview-capture til fokus/QA ...")
        image = driver.capture_preview(out_dir)
    except Exception as exc:
        print(f"Testcapture fejlede: {exc}")
        try:
            driver.disconnect()
        except Exception:
            pass
        return False
    finally:
        try:
            driver.disconnect()
        except Exception:
            pass

    print(f"Testbillede: {image} ({image.stat().st_size / 1_000_000:.1f} MB)")
    if image.suffix.lower() in {".jpg", ".jpeg"}:
        qa_image(image, base_dir)
    else:
        print("QA springes over: filen er ikke JPEG")
    return True


def read_gphoto_current(path: str) -> str | None:
    result = run(["gphoto2", "--get-config", path], check=False, timeout=8)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Current:"):
            return line.split(":", 1)[1].strip()
    return ""


def gphoto_config_exists(path: str) -> bool:
    """Return True when gphoto2 exposes a config/action path.

    Action widgets do not always have a meaningful "Current:" value, so using
    read_gphoto_current() as an existence probe caused valid autofocus/focus
    actions to be skipped on some cameras.
    """
    result = run(["gphoto2", "--get-config", path], check=False, timeout=8)
    return result.returncode == 0


def print_network_status(detailed: bool = False) -> None:
    if command_exists("nmcli"):
        print("NetworkManager devices")
        print("----------------------")
        print(run(["nmcli", "device", "status"], check=False).stdout)
        print("Aktive forbindelser")
        print("-------------------")
        print(run(["nmcli", "connection", "show", "--active"], check=False).stdout)
        if detailed:
            print("IPv4 detaljer")
            print("-------------")
            print(run(["nmcli", "-f", "GENERAL.DEVICE,GENERAL.TYPE,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP4.ROUTE", "device", "show"], check=False, timeout=15).stdout)
    if command_exists("ip"):
        print("Interfaces")
        print("----------")
        print(run(["ip", "-brief", "addr"], check=False).stdout)
        print("Routing")
        print("-------")
        print(run(["ip", "route"], check=False).stdout)
    if detailed and command_exists("resolvectl"):
        print("DNS")
        print("---")
        print(run(["resolvectl", "status"], check=False, timeout=10).stdout)


def print_service_status() -> None:
    state = service_state(SERVICE_NAME)
    for key, value in state.items():
        print(f"{key}: {value}")


def show_logs(service: str, lines: int = 100, priority: str | None = None) -> None:
    if not command_exists("journalctl"):
        print("journalctl findes ikke")
        return
    cmd = ["journalctl", "--no-pager", "-n", str(lines)]
    if service:
        cmd.extend(["-u", service])
    if priority:
        cmd.extend(["-p", priority])
    result = run(cmd, check=False, timeout=15)
    print(result.stdout or result.stderr)


def print_storage_status(base_dir: Path) -> None:
    status = collect_local_status(base_dir)
    print(json.dumps(status.get("storage", {}), indent=2, ensure_ascii=False))


def print_gps_status(compact: bool = False) -> None:
    if not command_exists("gpspipe"):
        print("gpspipe mangler")
        return
    result = run(["gpspipe", "-w", "-n", "8"], check=False, timeout=12)
    fix = None
    classes: list[str] = []
    for line in result.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("class"):
            classes.append(msg["class"])
        if msg.get("class") == "TPV" and msg.get("lat") is not None and msg.get("lon") is not None:
            fix = msg
    if fix:
        print(f"GPS fix: lat={fix.get('lat')} lon={fix.get('lon')} mode={fix.get('mode')} alt={fix.get('altHAE') or fix.get('altMSL')}")
    else:
        print("GPS fix: ikke fundet i kort probe")
        if not compact and result.stderr:
            print(result.stderr)
    if not compact:
        print("gpspipe classes:", ", ".join(classes) or "(ingen)")


def print_npu_status(base_dir: Path, compact: bool = False) -> None:
    cfg = read_yaml(base_dir / "config.yaml")
    edge_ai = ((cfg.get("quality", {}) or {}).get("edge_ai", {}) or {})
    items = {
        "enabled": edge_ai.get("enabled", False),
        "runner": edge_ai.get("runner") or os.getenv("TIMELAPSE_EDGE_AI_RUNNER", ""),
        "model_path": edge_ai.get("model_path") or os.getenv("TIMELAPSE_EDGE_AI_MODEL", ""),
        "vendor_binary": edge_ai.get("vendor_binary") or os.getenv("TIMELAPSE_EDGE_AI_VENDOR_BINARY", ""),
    }
    for key, value in items.items():
        print(f"{key}: {value or '(ikke sat)'}")
    for key in ("runner", "model_path"):
        value = str(items.get(key) or "")
        if value:
            path = shutil.which(value) if "/" not in value else value
            print(f"{key}_exists: {bool(path and Path(path).exists())} ({path})")
    probe = EDGE_ROOT / "tools" / "probe_orangepi_npu.py"
    if probe.exists() and not compact:
        python = sys.executable or "python3"
        result = run([python, str(probe), "--pretty"], check=False, timeout=20)
        print(result.stdout or result.stderr)


def collect_local_status(base_dir: Path, include_camera: bool = False) -> dict[str, Any]:
    bootstrap = read_yaml(base_dir / BOOTSTRAP_FILE)
    network = read_yaml(base_dir / NETWORK_FILE)
    config = read_yaml(base_dir / "config.yaml")
    status: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device": {
            "device_id": bootstrap.get("device_id") or derive_device_id_fallback(),
            "headend_url": bootstrap.get("headend_url", ""),
            "bootstrap_token_present": bool(bootstrap.get("bootstrap_token")),
            "network_preference": network.get("connectivity", {}).get("preferred_order", []),
        },
        "service": service_state(SERVICE_NAME),
        "system": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uptime_s": read_uptime(),
        },
        "network": {},
        "storage": {},
        "camera": {},
        "ai": {},
    }
    if command_exists("ip"):
        status["network"]["route"] = first_line(run(["ip", "route", "get", "8.8.8.8"], check=False, timeout=5).stdout)
    if command_exists("nmcli"):
        status["network"]["devices"] = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], check=False).stdout.splitlines()
    status["storage"].update(disk_usage(Path(config.get("storage", {}).get("local_path", "/data"))))
    status["storage"]["upload_queue_size"] = upload_queue_size(config)
    if include_camera and command_exists("gphoto2"):
        detected = run(["gphoto2", "--auto-detect"], check=False, timeout=15)
        status["camera"]["auto_detect"] = detected.stdout.strip()
        for key, path in {
            "battery": "/main/status/batterylevel",
            "lens": "/main/status/lensname",
            "focus_mode": "/main/capturesettings/focusmode",
            "exposure_comp": "/main/capturesettings/exposurecompensation",
            "iso": "/main/imgsettings/iso",
            "white_balance": "/main/imgsettings/whitebalance",
        }.items():
            status["camera"][key] = read_gphoto_current(path)
    elif command_exists("gphoto2"):
        status["camera"]["probe"] = "springes over i hurtigt overblik"
        status["camera"]["hint"] = "Brug 'Kamera status' for aktiv gphoto2-probe."
    else:
        status["camera"]["gphoto2"] = "mangler"
    edge_ai = ((config.get("quality", {}) or {}).get("edge_ai", {}) or {})
    status["ai"] = {
        "edge_ai_enabled": edge_ai.get("enabled", False),
        "runner": edge_ai.get("runner") or os.getenv("TIMELAPSE_EDGE_AI_RUNNER", ""),
        "model_path": edge_ai.get("model_path") or os.getenv("TIMELAPSE_EDGE_AI_MODEL", ""),
    }
    return status


def write_technician_report(base_dir: Path) -> Path:
    status = collect_local_status(base_dir, include_camera=True)
    out_dir = Path(os.getenv("TIMELAPSE_TECH_REPORT_DIR", "/tmp/timelapse-technician"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render_technician_html(status), encoding="utf-8")
    return path


def render_technician_html(status: dict[str, Any]) -> str:
    def card(title: str, data: Any) -> str:
        if isinstance(data, dict):
            body = "".join(
                f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(format_value(v))}</td></tr>"
                for k, v in data.items()
            )
            content = f"<table>{body}</table>"
        elif isinstance(data, list):
            content = "<ul>" + "".join(f"<li>{html.escape(format_value(v))}</li>" for v in data) + "</ul>"
        else:
            content = f"<p>{html.escape(format_value(data))}</p>"
        return f"<section><h2>{html.escape(title)}</h2>{content}</section>"

    return f"""<!doctype html>
<html lang="da">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>TimeLapse Pro Edge Tekniker</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #172033; }}
    header {{ background: #101827; color: white; padding: 18px 22px; }}
    h1 {{ margin: 0; font-size: 22px; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; padding: 16px; }}
    section {{ background: white; border: 1px solid #dde3ee; border-radius: 8px; padding: 14px; }}
    h2 {{ margin: 0 0 10px; font-size: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ width: 42%; text-align: left; color: #53637c; font-weight: 600; vertical-align: top; }}
    td, th {{ border-top: 1px solid #edf1f6; padding: 7px 4px; word-break: break-word; }}
    ul {{ margin: 0; padding-left: 18px; }}
    .ok {{ color: #087f5b; }}
  </style>
</head>
<body>
  <header>
    <h1>TimeLapse Pro Edge Tekniker</h1>
    <div>Genereret {html.escape(status.get("generated_at", ""))} UTC · opdaterer hvert 30. sekund</div>
  </header>
  <main>
    {card("Device", status.get("device", {}))}
    {card("Service", status.get("service", {}))}
    {card("System", status.get("system", {}))}
    {card("Netvaerk", status.get("network", {}))}
    {card("Storage og upload", status.get("storage", {}))}
    {card("Kamera", status.get("camera", {}))}
    {card("Edge AI / NPU", status.get("ai", {}))}
  </main>
</body>
</html>
"""


def service_state(service: str) -> dict[str, str]:
    if not command_exists("systemctl"):
        return {"active": "systemctl mangler"}
    props = run([
        "systemctl", "show", service,
        "--property=ActiveState,SubState,NRestarts,ExecMainStatus,FragmentPath",
    ], check=False, timeout=5)
    state: dict[str, str] = {}
    for line in props.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            state[key] = value
    active = run(["systemctl", "is-active", service], check=False, timeout=5)
    state["active"] = active.stdout.strip() or active.stderr.strip() or "ukendt"
    return state


def disk_usage(path: Path) -> dict[str, Any]:
    paths = [path, Path("/"), Path("/data")]
    result: dict[str, Any] = {}
    for p in paths:
        if not p.exists():
            continue
        try:
            st = os.statvfs(str(p))
            total = st.f_blocks * st.f_frsize / 1e9
            free = st.f_bavail * st.f_frsize / 1e9
            used = total - free
            key = "data" if str(p) == str(path) else str(p).strip("/") or "root"
            result[f"{key}_total_gb"] = round(total, 2)
            result[f"{key}_free_gb"] = round(free, 2)
            result[f"{key}_used_pct"] = round(100 * used / total, 1) if total else 0
        except Exception:
            pass
    return result


def upload_queue_size(config: dict) -> int | None:
    candidates = [
        Path(config.get("storage", {}).get("local_path", "/data")) / "timelapse_edge.db",
        Path("/data/timelapse_edge.db"),
    ]
    for db_path in candidates:
        if not db_path.exists():
            continue
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            try:
                return int(conn.execute("SELECT COUNT(*) FROM captures WHERE uploaded_primary = 0").fetchone()[0])
            finally:
                conn.close()
        except Exception:
            continue
    return None


def read_uptime() -> int | None:
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception:
        return None


def format_seconds(value: Any) -> str:
    try:
        seconds = int(value)
    except Exception:
        return "ukendt"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}t {minutes}m"
    return f"{hours}t {minutes}m"


def format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def summarize_storage(storage: dict[str, Any]) -> str:
    for prefix in ("data", "root"):
        used = storage.get(f"{prefix}_used_pct")
        free = storage.get(f"{prefix}_free_gb")
        if used is not None and free is not None:
            return f"{used}% brugt, {free} GB fri ({prefix})"
    return "ukendt"


def test_headend(base_dir: Path) -> bool:
    headend_url = resolve_headend_url(base_dir)
    if not headend_url:
        print("Headend URL mangler i bootstrap.yaml/config.yaml")
        return False
    health_urls = [f"{headend_url}/health"]
    if headend_url.endswith("/api"):
        health_urls.append(f"{headend_url[:-4]}/health")
    try:
        import requests

        last_response = None
        for health_url in health_urls:
            response = requests.get(health_url, timeout=8)
            last_response = response
            print(f"{health_url} -> HTTP {response.status_code}")
            if response.text:
                print(response.text[:300])
            if response.ok:
                return True
        return bool(last_response and last_response.ok)
    except Exception as exc:
        print(f"Headend test fejlede: {exc}")
        return False


def resolve_headend_url(base_dir: Path) -> str:
    bootstrap = read_yaml(base_dir / BOOTSTRAP_FILE)
    config = read_yaml(base_dir / "config.yaml")
    candidates = [
        bootstrap.get("headend_url"),
        config.get("headend_url"),
        (config.get("management", {}) or {}).get("headend_url"),
        os.getenv("HEADEND_URL"),
    ]
    for value in candidates:
        value = str(value or "").strip().rstrip("/")
        if value:
            return value
    return ""


def nmcli_devices(device_type: str) -> list[str]:
    result = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"], check=False)
    devices = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == device_type:
            devices.append(parts[0])
    return devices


def nmcli_device_info(device: str) -> dict[str, str]:
    result = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], check=False)
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if parts and parts[0] == device:
            return {
                "device": parts[0],
                "type": parts[1] if len(parts) > 1 else "",
                "state": parts[2] if len(parts) > 2 else "",
                "connection": parts[3] if len(parts) > 3 else "",
            }
    return {"device": device, "type": "", "state": "", "connection": ""}


def choose_device(devices: list[str]) -> str:
    if len(devices) == 1:
        return devices[0]
    for idx, device in enumerate(devices, 1):
        print(f"{idx}. {device}")
    raw = input("Vaelg interface: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(devices):
        return devices[int(raw) - 1]
    print("Afbrudt")
    return ""


def update_network_preference(base_dir: Path, first: str) -> None:
    path = base_dir / NETWORK_FILE
    data = read_yaml(path)
    preferred = [first] + [x for x in ["ethernet", "wifi", "4g"] if x != first]
    data.setdefault("connectivity", {})["preferred_order"] = preferred
    write_yaml(path, data, mode=0o600)


def parse_wifi_list(output: str) -> list[dict[str, Any]]:
    networks = []
    seen = set()
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        active, ssid, signal, security = parts[0], parts[1], parts[2], ":".join(parts[3:])
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        networks.append({
            "active": active == "*",
            "ssid": ssid,
            "signal": int(signal) if signal.isdigit() else 0,
            "security": security or "--",
        })
    return sorted(networks, key=lambda n: -n["signal"])


def first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r") as fh:
            text = fh.read()
    except PermissionError:
        text = _read_root_only_file_via_sudo(path)
        if text is None:
            return {}
    if yaml is not None:
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return parse_simple_yaml(text)


def _read_root_only_file_via_sudo(path: Path) -> str | None:
    """Best-effort fallback when a config file is root-only (e.g. bootstrap.yaml).

    Uses non-interactive sudo so a status check never blocks on a password
    prompt mid-menu; falls back to a one-line hint instead of a stack trace.
    """
    if os.geteuid() == 0 or not command_exists("sudo"):
        print(f"(kraever sudo for at laese {path} - koer vaerktoejet med sudo)")
        return None
    try:
        result = subprocess.run(
            ["sudo", "-n", "cat", str(path)],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        result = None
    if result is None or result.returncode != 0:
        print(f"(kraever sudo for at laese {path} - koer vaerktoejet med sudo)")
        return None
    return result.stdout


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        if yaml is not None:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
        else:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    tmp.chmod(mode)
    tmp.replace(path)


def derive_device_id_fallback() -> str:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from utils.device_id import get_device_id

        return get_device_id()
    except Exception:
        return "TL-UNKNOWN"


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Tiny fallback parser for simple bootstrap/local_network YAML files."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if not value:
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
            continue
        if value.startswith("[") and value.endswith("]"):
            current[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
        else:
            current[key] = value.strip("'\"")
    return root


def command_exists(name: str) -> bool:
    return subprocess.run(["/usr/bin/env", "which", name], capture_output=True).returncode == 0


def run(cmd: list[str], check: bool = True, timeout: int = 15) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"Command failed: {' '.join(cmd)}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
