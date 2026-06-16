#!/usr/bin/env python3
"""
TimeLapse Pro — Bootstrap Agent (first-boot enrollment)
========================================================
Kører én gang ved første boot af et nyt edge-board.

Hvad den gør:
  1. Læser bootstrap.yaml (skabt af image-bygger / headend-admin)
  2. Detekterer hardware via HAL
  3. Udleder device_id fra primær MAC-adresse  (TL-AABBCCDDEEFF)
  4. Genererer ed25519 SSH-nøglepar → /etc/timelapse/device_keys/
  5. Kalder POST {headend_url}/api/devices/enroll
  6. Skriver /etc/timelapse/node-agent.conf
  7. Deaktiverer sig selv; aktiverer og starter timelapse-edge.service

Entry point:
  python3 /opt/timelapse/edge/scripts/bootstrap_agent.py

Systemd:
  timelapse-bootstrap.service  (Type=oneshot, RemainAfterExit=no)
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

# ── Paths ─────────────────────────────────────────────────────────────────────

BOOTSTRAP_YAML      = Path("/etc/timelapse/bootstrap.yaml")
NODE_AGENT_CONF     = Path("/etc/timelapse/node-agent.conf")
DEVICE_KEYS_DIR     = Path("/etc/timelapse/device_keys")
SSH_ID_KEY          = DEVICE_KEYS_DIR / "id_ed25519"
SSH_ID_KEY_PUB      = DEVICE_KEYS_DIR / "id_ed25519.pub"
ENROLL_DONE_MARKER  = Path("/etc/timelapse/.enrolled")

# Tilføj edge-koden til Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s bootstrap %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bootstrap")


# ── Hjælpefunktioner ──────────────────────────────────────────────────────────

def _read_bootstrap_yaml() -> dict:
    """Læs /etc/timelapse/bootstrap.yaml — påkrævet ved første boot."""
    if not BOOTSTRAP_YAML.exists():
        # Prøv template-filen fra image (bruges hvis ingen specifik yaml er kopieret ind)
        tpl = Path("/opt/timelapse/edge/bootstrap.yaml.template")
        if tpl.exists():
            log.info("Ingen bootstrap.yaml — bruger template: %s", tpl)
            text = tpl.read_text()
            # Erstat env-var placeholders  ${VARNAME}
            def _sub(m: re.Match) -> str:
                return os.environ.get(m.group(1), m.group(0))
            text = re.sub(r"\$\{(\w+)\}", _sub, text)
            BOOTSTRAP_YAML.parent.mkdir(parents=True, exist_ok=True)
            BOOTSTRAP_YAML.write_text(text)
        else:
            log.error("Ingen bootstrap.yaml og ingen template — afbryder")
            sys.exit(1)
    return yaml.safe_load(BOOTSTRAP_YAML.read_text()) or {}


def _primary_mac() -> str:
    """Returner primær (ikke-loopback) MAC-adresse som HEX uden separatorer."""
    PREFERRED = ("eth0", "end0", "enp1s0", "enp3s0", "wlan0")
    candidates: list[tuple[int, str, str]] = []

    sys_net = Path("/sys/class/net")
    for iface in sys_net.iterdir():
        mac_path = iface / "address"
        if not mac_path.exists():
            continue
        mac = mac_path.read_text().strip().replace(":", "").upper()
        if len(mac) != 12 or mac == "000000000000":
            continue
        # Tjek om det er loopback
        try:
            flags = int((iface / "flags").read_text().strip(), 16)
            if flags & 0x8:   # IFF_LOOPBACK
                continue
        except Exception:
            pass
        # Prioritér foretrukne interfacenavne
        prio = next((i for i, n in enumerate(PREFERRED) if iface.name == n), 99)
        candidates.append((prio, iface.name, mac))

    if not candidates:
        # Nødplan: brug socket
        try:
            import uuid
            raw = "%012X" % (uuid.getnode(),)
            if raw != "000000000000":
                return raw
        except Exception:
            pass
        log.error("Kan ikke finde MAC-adresse")
        sys.exit(1)

    candidates.sort()
    _, iface, mac = candidates[0]
    log.info("Primær interface: %s → MAC %s", iface, mac)
    return mac


def _derive_device_id(mac: str) -> str:
    """Konvertér MAC til TL-AABBCCDDEEFF device_id (matcher eksisterende konvention)."""
    return f"TL-{mac.upper()}"


def _generate_ssh_keypair() -> str:
    """Generer ed25519 SSH-nøglepar; returner public key string."""
    DEVICE_KEYS_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)

    if SSH_ID_KEY.exists() and SSH_ID_KEY_PUB.exists():
        log.info("SSH-nøgler eksisterer allerede — genbruger")
        return SSH_ID_KEY_PUB.read_text().strip()

    if SSH_ID_KEY.exists() and not SSH_ID_KEY_PUB.exists():
        # Privat nøgle injektet fra headend (image-injection), men .pub mangler — ekstraher den
        log.info("Privat nøgle fundet — ekstraherer public key...")
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(SSH_ID_KEY)],
            check=True, capture_output=True, text=True,
        )
        SSH_ID_KEY_PUB.write_text(result.stdout)
        SSH_ID_KEY_PUB.chmod(0o644)
        log.info("Public key ekstraheret: %s…", result.stdout.strip()[:40])
        return result.stdout.strip()

    log.info("Genererer ed25519 SSH-nøglepar...")
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "timelapse-edge",
         "-f", str(SSH_ID_KEY)],
        check=True, capture_output=True,
    )
    SSH_ID_KEY.chmod(0o600)
    SSH_ID_KEY_PUB.chmod(0o644)
    pubkey = SSH_ID_KEY_PUB.read_text().strip()
    log.info("SSH public key: %s…", pubkey[:40])
    return pubkey


def _detect_hardware() -> tuple[str, str]:
    """Returner (hal_id, model_name) for det aktuelle board."""
    try:
        from hal import get_adapter, hal_model_id, detect_hardware_string
        raw = detect_hardware_string()
        adapter = get_adapter()
        return adapter.hal_id(), adapter.model_name()
    except Exception as exc:
        log.warning("HAL-detektion fejlede: %s", exc)
        return "generic", "Unknown"


def _enroll(
    headend_url: str,
    bootstrap_token: str,
    device_id: str,
    hardware_model: str,
    ssh_pubkey: str,
    mac_address: str,
    retries: int = 10,
    delay_s: int = 15,
) -> dict:
    """
    Kald POST {headend_url}/api/devices/enroll og returner svaret.
    Forsøger op til `retries` gange med `delay_s` sekunders interval.
    """
    # Strip evt. /api-suffix fra headend_url så vi ikke får /api/api/...
    _base = headend_url.rstrip("/")
    if _base.endswith("/api"):
        _base = _base[:-4]
    url = _base + "/api/devices/enroll"
    payload = {
        "bootstrap_token": bootstrap_token,
        "device_id":       device_id,
        "hardware_model":  hardware_model,
        "ssh_pubkey":      ssh_pubkey,
        "mac_address":     mac_address,
    }
    for attempt in range(1, retries + 1):
        try:
            log.info("Enrollment forsøg %d/%d → %s", attempt, retries, url)
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                log.info("Enrollment OK: device_id=%s state=%s",
                         data.get("device_id"), data.get("enrollment_state"))
                return data
            log.warning("Enrollment HTTP %d: %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            log.warning("Enrollment netværksfejl: %s", exc)

        if attempt < retries:
            log.info("Venter %ds før næste forsøg...", delay_s)
            time.sleep(delay_s)

    log.error("Enrollment mislykkedes efter %d forsøg", retries)
    sys.exit(1)


def _write_node_agent_conf(
    device_id: str,
    api_token: str,
    headend_url: str,
    hardware_model: str,
) -> None:
    """Skriv /etc/timelapse/node-agent.conf."""
    NODE_AGENT_CONF.parent.mkdir(parents=True, exist_ok=True)

    conf = {
        "device": {
            "device_id":      device_id,
            "hardware_model": hardware_model,
        },
        "headend": {
            "url":       headend_url,
            "api_token": api_token,
        },
        "storage": {
            "db_path":          "/data/timelapse_edge.db",
            "capture_dir":      "/data/captures",
            "buffer_max_count": 200,
            "buffer_max_mb":    4096,
        },
        "diagnostics": {
            "heartbeat_interval_minutes":    60,
            "config_poll_interval_minutes":   5,
            "inventory_report_interval_hours": 24,
        },
    }
    NODE_AGENT_CONF.write_text(
        yaml.dump(conf, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    NODE_AGENT_CONF.chmod(0o600)
    log.info("Wrote %s", NODE_AGENT_CONF)


def _activate_edge_service() -> None:
    """Deaktivér bootstrap-service; aktivér og start edge-agent."""
    cmds = [
        ["systemctl", "disable", "timelapse-bootstrap.service"],
        ["systemctl", "enable",  "timelapse-edge.service"],
        ["systemctl", "start",   "timelapse-edge.service"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning("%s → rc=%d: %s", " ".join(cmd), result.returncode, result.stderr.strip())
        else:
            log.info("OK: %s", " ".join(cmd))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("TimeLapse Pro — Bootstrap Agent")
    log.info("=" * 60)

    # Allerede enrollet?
    if ENROLL_DONE_MARKER.exists():
        log.info("Enhed allerede enrollet — afslutter (marker: %s)", ENROLL_DONE_MARKER)
        _activate_edge_service()
        return

    # 1. Læs bootstrap config
    cfg = _read_bootstrap_yaml()
    headend_url     = cfg.get("headend_url", "").rstrip("/")
    bootstrap_token = cfg.get("bootstrap_token", "")

    if not headend_url or not bootstrap_token:
        log.error("bootstrap.yaml mangler headend_url eller bootstrap_token")
        sys.exit(1)

    log.info("Headend: %s", headend_url)

    # 2. Hardware-detektion
    hardware_model, model_name = _detect_hardware()
    log.info("Hardware: %s (%s)", hardware_model, model_name)

    # 3. MAC → device_id
    mac = _primary_mac()
    device_id = cfg.get("device_id") or _derive_device_id(mac)
    log.info("Device ID: %s", device_id)

    # 4. SSH-nøglepar
    ssh_pubkey = _generate_ssh_keypair()

    # 5. Enrollment
    result = _enroll(
        headend_url     = headend_url,
        bootstrap_token = bootstrap_token,
        device_id       = device_id,
        hardware_model  = hardware_model,
        ssh_pubkey      = ssh_pubkey,
        mac_address     = mac,
    )

    final_device_id = result.get("device_id", device_id)
    api_token       = result["api_token"]
    enrollment_state = result.get("enrollment_state", "active")

    # 6. Skriv node-agent.conf
    _write_node_agent_conf(
        device_id      = final_device_id,
        api_token      = api_token,
        headend_url    = headend_url,
        hardware_model = hardware_model,
    )

    # 7. Marker som enrollet
    ENROLL_DONE_MARKER.parent.mkdir(parents=True, exist_ok=True)
    ENROLL_DONE_MARKER.write_text(
        json.dumps({
            "device_id":       final_device_id,
            "hardware_model":  hardware_model,
            "enrollment_state": enrollment_state,
            "enrolled_at":     __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }, indent=2)
    )

    if enrollment_state == "unassigned":
        log.info("=" * 60)
        log.info("Enhed enrollet men IKKE tildelt en site endnu.")
        log.info("Gå til headend UI → Provisioning → Tildel enhed til site.")
        log.info("Enheden vil begynde at optage, når en site er tildelt.")
        log.info("=" * 60)
    else:
        log.info("Enhed enrollet og tildelt site. Starter edge-agent...")

    # 8. Aktiver edge-service (starter uanset enrollment_state)
    _activate_edge_service()

    log.info("Bootstrap færdig — device_id=%s state=%s", final_device_id, enrollment_state)


if __name__ == "__main__":
    main()
