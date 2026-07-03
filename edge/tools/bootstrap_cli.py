#!/usr/bin/env python3
"""
TimeLapse Pro - local Edge bootstrap CLI.

Local-only network bootstrap for a new Edge before it can reach Headend.
Production operational configuration must still come from Headend/RBAC.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
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


def main() -> int:
    parser = argparse.ArgumentParser(description="TimeLapse Pro Edge local bootstrap")
    parser.add_argument("--base-dir", default=str(EDGE_DIR), help="Edge config directory")
    parser.add_argument("--status", action="store_true", help="Print local network/bootstrap status")
    parser.add_argument("--test-headend", action="store_true", help="Test Headend /api/health")
    parser.add_argument("--doctor", action="store_true", help="Run local commissioning/troubleshooting checks")
    parser.add_argument("--qa-image", help="Run Edge CV QA against a local JPEG")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if args.status:
        print_status(base_dir)
        return 0
    if args.test_headend:
        return 0 if test_headend(base_dir) else 1
    if args.doctor:
        return 0 if run_doctor(base_dir) else 1
    if args.qa_image:
        return 0 if qa_image(Path(args.qa_image), base_dir) else 1
    return menu(base_dir)


def menu(base_dir: Path) -> int:
    while True:
        print()
        print("TimeLapse Pro Edge lokal opsaetning")
        print("------------------------------------")
        print("1. Vis status")
        print("2. Konfigurer Headend URL / bootstrap token")
        print("3. Scan og tilslut WiFi")
        print("4. Konfigurer Ethernet")
        print("5. Konfigurer 4G USB modem")
        print("6. Test Headend forbindelse")
        print("7. Koer lokal doctor / fejlfinding")
        print("8. QA-test lokalt billede")
        print("9. Afslut")
        choice = input("Valg: ").strip()

        if choice == "1":
            print_status(base_dir)
        elif choice == "2":
            configure_bootstrap(base_dir)
        elif choice == "3":
            configure_wifi()
        elif choice == "4":
            configure_ethernet(base_dir)
        elif choice == "5":
            configure_gsm(base_dir)
        elif choice == "6":
            test_headend(base_dir)
        elif choice == "7":
            run_doctor(base_dir)
        elif choice == "8":
            raw = input("Sti til JPEG: ").strip()
            if raw:
                qa_image(Path(raw), base_dir)
        elif choice == "9":
            return 0
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


def configure_wifi() -> None:
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

    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd.extend(["password", password])
    result = run(cmd, check=False, timeout=45)
    if result.returncode == 0:
        print("WiFi tilsluttet")
    else:
        print("WiFi tilslutning fejlede:")
        print(result.stderr or result.stdout)


def configure_ethernet(base_dir: Path) -> None:
    if not command_exists("nmcli"):
        print("nmcli findes ikke. Ethernet kan stadig virke via OS default DHCP.")
        return

    devices = nmcli_devices("ethernet")
    if not devices:
        print("Ingen Ethernet interface fundet")
        return
    device = choose_device(devices)
    if not device:
        return

    mode = input("Ethernet mode: [1] DHCP, [2] Static: ").strip() or "1"
    con_name = f"timelapse-ethernet-{device}"
    if mode == "1":
        run(["nmcli", "connection", "delete", con_name], check=False)
        run([
            "nmcli", "connection", "add", "type", "ethernet",
            "ifname", device, "con-name", con_name,
            "ipv4.method", "auto", "ipv6.method", "ignore",
        ])
    elif mode == "2":
        address = input("IPv4/CIDR, fx 192.168.1.50/24: ").strip()
        gateway = input("Gateway: ").strip()
        dns = input("DNS, komma-separeret [1.1.1.1,8.8.8.8]: ").strip() or "1.1.1.1,8.8.8.8"
        run(["nmcli", "connection", "delete", con_name], check=False)
        run([
            "nmcli", "connection", "add", "type", "ethernet",
            "ifname", device, "con-name", con_name,
            "ipv4.method", "manual", "ipv4.addresses", address,
            "ipv4.gateway", gateway, "ipv4.dns", dns,
            "ipv6.method", "ignore",
        ])
    else:
        print("Afbrudt")
        return

    run(["nmcli", "connection", "up", con_name], check=False, timeout=20)
    update_network_preference(base_dir, "ethernet")
    print(f"Ethernet konfigureret: {device}")


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


def print_status(base_dir: Path) -> None:
    print("Config directory:", base_dir)
    bootstrap = read_yaml(base_dir / BOOTSTRAP_FILE)
    network = read_yaml(base_dir / NETWORK_FILE)
    print("Device ID:", bootstrap.get("device_id") or derive_device_id_fallback())
    print("Headend URL:", bootstrap.get("headend_url", "(ikke sat)"))
    print("Bootstrap token:", "sat" if bootstrap.get("bootstrap_token") else "mangler")
    print("Network preference:", network.get("connectivity", {}).get("preferred_order", ["ethernet", "wifi"]))
    if command_exists("nmcli"):
        print()
        print(run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], check=False).stdout)
    else:
        print("nmcli: ikke installeret")


def run_doctor(base_dir: Path) -> bool:
    """Run local checks useful during Edge commissioning and support calls."""
    checks: list[tuple[str, bool, str]] = []
    bootstrap_path = base_dir / BOOTSTRAP_FILE
    network_path = base_dir / NETWORK_FILE
    bootstrap = read_yaml(bootstrap_path)
    config = read_yaml(base_dir / "config.yaml")
    edge_ai = ((config.get("quality", {}) or {}).get("edge_ai", {}) or {})

    checks.append(("config directory", base_dir.exists(), str(base_dir)))
    checks.append(("bootstrap.yaml", bootstrap_path.exists(), str(bootstrap_path)))
    checks.append(("bootstrap token", bool(bootstrap.get("bootstrap_token")), "sat" if bootstrap.get("bootstrap_token") else "mangler"))
    checks.append(("headend url", bool(bootstrap.get("headend_url")), bootstrap.get("headend_url", "mangler")))
    checks.append(("local_network.yaml", network_path.exists(), str(network_path)))

    for name in ["nmcli", "ip", "systemctl", "gphoto2"]:
        path = shutil.which(name)
        checks.append((f"kommando: {name}", path is not None, path or "mangler"))

    runner = edge_ai.get("runner") or os.getenv("TIMELAPSE_EDGE_AI_RUNNER", "")
    model_path = edge_ai.get("model_path") or os.getenv("TIMELAPSE_EDGE_AI_MODEL", "")
    vendor_binary = edge_ai.get("vendor_binary") or os.getenv("TIMELAPSE_EDGE_AI_VENDOR_BINARY", "")
    if edge_ai.get("enabled") or runner or model_path or vendor_binary:
        runner_path = shutil.which(str(runner)) if runner and "/" not in str(runner) else str(runner)
        vendor_cmd = shlex.split(str(vendor_binary)) if vendor_binary else []
        vendor_path = (
            shutil.which(vendor_cmd[0])
            if vendor_cmd and "/" not in vendor_cmd[0]
            else (vendor_cmd[0] if vendor_cmd else "")
        )
        checks.append(("edge QA AI", bool(edge_ai.get("enabled", False)), "enabled" if edge_ai.get("enabled") else "disabled"))
        checks.append(("NPU runner", bool(runner_path and Path(runner_path).exists()), runner_path or "mangler"))
        checks.append(("NPU model", bool(model_path and Path(str(model_path)).exists()), str(model_path) or "mangler"))
        checks.append(("VIPLite wrapper", bool(vendor_path and Path(vendor_path).exists()), str(vendor_binary) or "mangler"))

    checks.append(("python", True, platform.python_version()))
    checks.append(("platform", True, platform.platform()))

    if command_exists("systemctl"):
        svc = run(["systemctl", "is-active", "timelapse-edge"], check=False, timeout=5)
        checks.append(("timelapse-edge service", svc.stdout.strip() == "active", svc.stdout.strip() or svc.stderr.strip() or "ukendt"))

    if command_exists("ip"):
        route = run(["ip", "route", "get", "8.8.8.8"], check=False, timeout=5)
        checks.append(("default route", route.returncode == 0, first_line(route.stdout or route.stderr)))

    headend_ok = False
    if bootstrap.get("headend_url"):
        headend_ok = test_headend(base_dir)
        checks.append(("headend health", headend_ok, "ok" if headend_ok else "fejl"))

    print()
    print("TimeLapse Edge doctor")
    print("---------------------")
    for label, ok, detail in checks:
        status = "OK" if ok else "FEJL"
        print(f"{status:4} {label:24} {detail}")

    failed = [label for label, ok, _ in checks if not ok]
    if failed:
        print()
        print("Anbefalet naeste skridt:")
        for label in failed[:6]:
            print(f"- Ret/tjek: {label}")
    return not failed


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


def test_headend(base_dir: Path) -> bool:
    bootstrap = read_yaml(base_dir / BOOTSTRAP_FILE)
    headend_url = (bootstrap.get("headend_url") or "").rstrip("/")
    if not headend_url:
        print("Headend URL mangler i bootstrap.yaml")
        return False
    health_url = headend_url[:-4] + "/health" if headend_url.endswith("/api") else headend_url + "/health"
    try:
        import requests

        response = requests.get(health_url, timeout=8)
        print(f"{health_url} -> HTTP {response.status_code}")
        if response.text:
            print(response.text[:300])
        return response.ok
    except Exception as exc:
        print(f"Headend test fejlede: {exc}")
        return False


def nmcli_devices(device_type: str) -> list[str]:
    result = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"], check=False)
    devices = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == device_type:
            devices.append(parts[0])
    return devices


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
    with path.open("r") as fh:
        text = fh.read()
    if yaml is not None:
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return parse_simple_yaml(text)


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
