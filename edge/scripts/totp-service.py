#!/usr/bin/env python3
"""
TimeLapse Pro — Local Management TOTP captive portal
Kører på br-bt (192.168.42.1:8443 HTTPS)

Flow:
  1. Telefon forbinder til BT PAN → får IP 192.168.42.x
  2. iptables blokerer alt undtagen port 8443
  3. Teknikeren åbner direkte HTTPS TOTP-login på port 8443
  4. Bruger indtaster TOTP-kode fra authenticator app
  5. Ved success: klient-IP whitelistes i iptables (session_timeout)
  6. Management UI tilgængeligt
"""

import os
import ssl
import time
import hmac
import html
import hashlib
import logging
import ipaddress
import subprocess
import shlex
import asyncio
import json
import pty
import select
import yaml
import pyotp

from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, Response, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from typing import Optional

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [totp] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("totp")

# ── Konfiguration ─────────────────────────────────────────────────────────────
CONFIG_FILE = "/etc/timelapse/bt-config.yaml"
SESSION_COOKIE = "tl_session"
IPTABLES_CHAIN = "TL_MGMT"
EDGE_ROOT = Path(os.getenv("TIMELAPSE_EDGE_ROOT", "/opt/timelapse/edge"))
TECH_CLI = EDGE_ROOT / "tools" / "bootstrap_cli.py"
TECH_CAPTURE_DIR = Path(os.getenv("TIMELAPSE_TECH_CAPTURE_DIR", "/tmp/timelapse-tech-captures"))
VIDEO_FRAME_DIR = Path(os.getenv("TIMELAPSE_TECH_VIDEO_DIR", "/tmp/timelapse-tech-video"))
BASH_PATH = os.getenv("TIMELAPSE_TECH_SHELL", "/bin/bash")
CLI_ALLOWED_FLAGS = {
    "--status",
    "--test-headend",
    "--doctor",
    "--network-status",
    "--network-preference",
    "--static-routes",
    "--camera-detect",
    "--camera-summary",
    "--camera-config",
    "--set-camera-config",
    "--photo-status",
    "--photo-setting",
    "--autofocus",
    "--focus-drive",
    "--capture-test",
    "--gps-status",
    "--npu-status",
    "--qa-image",
    "--maintenance",
}
PHOTO_VALUE_OPTIONS = {
    "exposure_comp": ["-2", "-1.7", "-1.3", "-1", "-0.7", "-0.3", "0", "+0.3", "+0.7", "+1", "+1.3", "+1.7", "+2"],
    "iso": ["Auto", "100", "200", "400", "800", "1600", "3200"],
    "white_balance": ["Auto", "Daylight", "Cloudy", "Shade", "Tungsten", "Fluorescent", "Flash"],
    "shutter_speed": ["auto", "1/30", "1/60", "1/125", "1/250", "1/500", "1/1000"],
    "aperture": ["f/4", "f/5.6", "f/8", "f/11", "f/16"],
    "focus_mode": ["Manual", "MF", "AF-S", "AF-C", "AF-A", "One Shot", "AI Servo"],
    "image_format": ["JPEG", "Large Fine JPEG", "RAW", "RAW + JPEG"],
}
CAMERA_CONFIG_OPTIONS = [
    ("/main/capturesettings/exposurecompensation", "Eksponeringskompensation"),
    ("/main/imgsettings/iso", "ISO"),
    ("/main/imgsettings/whitebalance", "Hvidbalance"),
    ("/main/capturesettings/shutterspeed", "Lukkertid"),
    ("/main/capturesettings/f-number", "Blænde"),
    ("/main/capturesettings/focusmode", "Fokusmode"),
    ("/main/imgsettings/imageformat", "Billedformat"),
    ("/main/actions/autofocusdrive", "Autofokus action"),
    ("/main/actions/manualfocusdrive", "Manuel focus drive"),
]
FOCUS_DRIVE_OPTIONS = ["Near 1", "Near 2", "Near 3", "Far 1", "Far 2", "Far 3", "500", "-500", "1000", "-1000"]


def _default_config() -> dict:
    return {
        "totp": {
            "secret": "JBSWY3DPEHPK3PXP",
            "sid": "factory-default",
            "valid_window": 3,
        },
        "management": {
            "https_port": 8443,
            "enable_interactive_shell": False,
            "session_timeout": 3600,
            "cert_file": "/etc/timelapse/certs/mgmt.crt",
            "key_file": "/etc/timelapse/certs/mgmt.key",
            "headend_url": "",
        },
    }


def load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        cfg = {}
    except Exception as exc:
        log.warning("Kunne ikke læse %s: %s", CONFIG_FILE, exc)
        cfg = {}
    defaults = _default_config()
    merged = defaults | cfg
    merged["totp"] = defaults["totp"] | (cfg.get("totp") or {})
    merged["management"] = defaults["management"] | (cfg.get("management") or {})
    return merged


def save_config(cfg: dict) -> None:
    """Atomically persist local management configuration as root-only data."""
    config_path = Path(CONFIG_FILE)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_name(f".{config_path.name}.tmp")
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(cfg, handle, allow_unicode=True, default_flow_style=False)
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, config_path)
        os.chmod(config_path, 0o600)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ── Session store (in-memory) ─────────────────────────────────────────────────
# { token: {"ip": str, "expires": float} }
_sessions: dict = {}
_SECRET_KEY = os.urandom(32)


def _make_token(ip: str) -> str:
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET_KEY, f"{ip}:{ts}".encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def _valid_token(token: str, ip: str) -> bool:
    if token not in _sessions:
        return False
    sess = _sessions[token]
    if sess["ip"] != ip:
        return False
    cfg = load_config()
    timeout = cfg["management"].get("session_timeout", 3600)
    if timeout > 0 and time.time() > sess["expires"]:
        _sessions.pop(token, None)
        _iptables_remove(ip)
        return False
    return True


# ── iptables helpers ──────────────────────────────────────────────────────────
def _iptables_add(ip: str) -> None:
    """Whitelist client-IP i TL_MGMT chain."""
    try:
        subprocess.run(
            ["iptables", "-I", IPTABLES_CHAIN, "1", "-s", ip, "-j", "ACCEPT"],
            check=True, capture_output=True
        )
        log.info(f"iptables: whitelisted {ip}")
    except subprocess.CalledProcessError as e:
        log.warning(f"iptables add fejlede for {ip}: {e.stderr.decode()}")


def _iptables_remove(ip: str) -> None:
    """Fjern whitelist for client-IP."""
    try:
        subprocess.run(
            ["iptables", "-D", IPTABLES_CHAIN, "-s", ip, "-j", "ACCEPT"],
            check=True, capture_output=True
        )
        log.info(f"iptables: fjernede {ip}")
    except subprocess.CalledProcessError:
        pass


# ── HTML templates ────────────────────────────────────────────────────────────
def _login_page(error: str = "") -> str:
    err_html = f'<p class="error">{error}</p>' if error else ""
    # Vis TOTP-kilde badge — factory-default = gul advarsel, CMDB = grøn
    try:
        _cfg = load_config()
        _sid = _cfg["totp"].get("sid", "factory-default")
    except Exception:
        _sid = "factory-default"
    _is_factory = (_sid == "factory-default")
    _badge_color = "#4fc3f7"   # blå/neutral
    if _is_factory:
        _badge_text = "🔑 Fabriksstandard QR-kode"
        _badge_hint = "Brug den medfølgende QR-kode fra kameraæsken eller CMDB"
    else:
        _badge_text = f"🔑 QR-kode: {_sid}"
        _badge_hint = "Brug den QR-kode fra CMDB der svarer til dette kamera/site/kunde"

    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeLapse Pro — Adgang</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee;
          display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ background: #16213e; border-radius: 12px; padding: 2rem; width: 320px; box-shadow: 0 4px 24px #0008; }}
  h1 {{ font-size: 1.2rem; margin: 0 0 0.3rem; color: #4fc3f7; }}
  p {{ font-size: 0.85rem; color: #aaa; margin: 0 0 1.2rem; }}
  .badge {{ display: inline-block; padding: 0.25rem 0.6rem; border-radius: 6px;
            font-size: 0.78rem; font-weight: 600; margin-bottom: 1rem;
            background: {_badge_color}22; color: {_badge_color}; border: 1px solid {_badge_color}44; }}
  .badge-hint {{ font-size: 0.72rem; color: #888; margin-top: -0.7rem; margin-bottom: 1rem; }}
  input {{ width: 100%; box-sizing: border-box; padding: 0.75rem; border-radius: 8px;
           border: 1px solid #334; background: #0f3460; color: #fff; font-size: 1.1rem;
           letter-spacing: 0.2em; text-align: center; margin-bottom: 1rem; }}
  button {{ width: 100%; padding: 0.75rem; border-radius: 8px; border: none;
            background: #4fc3f7; color: #000; font-size: 1rem; font-weight: 600; cursor: pointer; }}
  button:hover {{ background: #81d4fa; }}
  .error {{ color: #ef5350; font-size: 0.85rem; margin-bottom: 1rem; text-align: center; }}
  .hostname {{ font-size: 0.75rem; color: #555; text-align: center; margin-top: 1.5rem; }}
</style>
</head>
<body>
<div class="card">
  <h1>TimeLapse Pro</h1>
  <p>Indtast din 6-cifrede TOTP-kode for at få adgang til lokal management</p>
  <div class="badge">{_badge_text}</div>
  <p class="badge-hint">{_badge_hint}</p>
  {err_html}
  <form method="post" action="/verify">
    <input type="text" name="code" inputmode="numeric" pattern="[0-9]{{6}}"
           maxlength="6" placeholder="000000" autocomplete="off" autofocus required>
    <button type="submit">Log ind</button>
  </form>
  <div class="hostname">{os.uname().nodename}</div>
</div>
</body>
</html>"""


def _success_page() -> str:
    return """<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeLapse Pro — Adgang godkendt</title>
<meta http-equiv="refresh" content="2;url=/">
<style>
  body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
  .card { background: #16213e; border-radius: 12px; padding: 2rem; width: 320px; text-align: center; }
  h1 { color: #66bb6a; }
</style>
</head>
<body>
<div class="card">
  <h1>✓ Adgang godkendt</h1>
  <p>Omdirigerer til management UI...</p>
</div>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Tillad /verify og statiske ressourcer — alt andet kræver gyldig session."""
    path = request.url.path
    if path in ("/verify", "/health"):
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE)
    client_ip = request.client.host
    cfg = load_config()

    if not cfg["totp"].get("enabled", True):
        return await call_next(request)

    if token and _valid_token(token, client_ip):
        return await call_next(request)

    # Ikke autentificeret → vis login
    if request.method == "GET":
        return HTMLResponse(_login_page())
    return RedirectResponse("/", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def index():
    return _login_page()


@app.post("/verify")
async def verify(request: Request, code: str = Form(...)):
    cfg = load_config()
    totp_cfg = cfg["totp"]
    client_ip = request.client.host

    if not totp_cfg.get("enabled", True):
        return RedirectResponse("/mgmt/", status_code=303)

    totp = pyotp.TOTP(totp_cfg["secret"])
    valid_window = totp_cfg.get("valid_window", 1)

    if not totp.verify(code, valid_window=valid_window):
        log.warning(f"TOTP fejl fra {client_ip}")
        return HTMLResponse(_login_page(error="Forkert kode — prøv igen"), status_code=401)

    # Success — opret session og whitelist IP
    token = _make_token(client_ip)
    timeout = cfg["management"].get("session_timeout", 3600)
    _sessions[token] = {
        "ip": client_ip,
        "expires": time.time() + timeout if timeout > 0 else float("inf"),
    }
    _iptables_add(client_ip)
    log.info(f"TOTP verificeret fra {client_ip} (sid={totp_cfg.get('sid', '?')})")

    response = RedirectResponse("/mgmt/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, token,
        httponly=True, secure=True, samesite="strict",
        max_age=timeout if timeout > 0 else None
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ── Management UI ─────────────────────────────────────────────────────────────

def _get_time_status() -> dict:
    """Hent aktuel tidsstatus fra chrony."""
    import subprocess
    result = {"source": "ukendt", "offset_ms": None, "synced": False, "stratum": None}
    try:
        out = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=3)
        lines = out.stdout.splitlines()
        for line in lines:
            if "Reference ID" in line:
                parts = line.split("(")
                result["source"] = parts[1].rstrip(")") if len(parts) > 1 else line.split()[-1]
            if "System time" in line:
                val = line.split(":")[1].strip().split()[0]
                result["offset_ms"] = round(float(val) * 1000, 2)
            if "Stratum" in line:
                result["stratum"] = line.split(":")[1].strip().split()[0]
            if "Leap status" in line:
                result["synced"] = "Normal" in line
    except Exception:
        result["source"] = "NTP (systemd)" if _systemd_ntp_active() else "Ingen"
    return result


def _systemd_ntp_active() -> bool:
    import subprocess
    try:
        out = subprocess.run(["timedatectl", "show", "--property=NTPSynchronized"],
                             capture_output=True, text=True, timeout=2)
        return "yes" in out.stdout
    except Exception:
        return False


def _fetch_headend_config(cfg: dict) -> dict:
    """Hent merged config fra headend (inkl. hierarki-lag)."""
    import json as _json
    import sys
    import urllib.request

    edge_config_path = EDGE_ROOT / "config.yaml"
    edge_config = {}
    try:
        if edge_config_path.exists():
            edge_config = yaml.safe_load(edge_config_path.read_text()) or {}
    except Exception:
        edge_config = {}
    device_id = edge_config.get("device", {}).get("device_id", "")
    headend = edge_config.get("device", {}).get("headend_url", "")
    token_path = EDGE_ROOT / "api_token.txt"
    token = token_path.read_text().strip() if token_path.exists() else ""
    if not device_id or not headend:
        return {}
    try:
        api_base = headend.rstrip("/")
        if not api_base.endswith("/api"):
            api_base = f"{api_base}/api"
        path = f"/config/{device_id}"
        url = f"{api_base}{path}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        edge_module_dir = str(EDGE_ROOT)
        if edge_module_dir not in sys.path:
            sys.path.insert(0, edge_module_dir)
        try:
            from security import edge_attestation_headers, request_signature_headers
            headers.update(request_signature_headers(token, "GET", path))
            headers.update(edge_attestation_headers(EDGE_ROOT, device_id, "GET", path))
        except Exception as signing_exc:
            log.warning("Headend config request kører uden Edge-signatur: %s", signing_exc)
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=4) as r:
            return _json.loads(r.read())
    except Exception:
        return {}


def _mgmt_page(section: str = "time", headend_cfg: dict = None, time_status: dict = None, msg: str = "") -> str:
    cfg = load_config()
    ts = time_status or _get_time_status()
    hcfg = headend_cfg or {}
    time_cfg = hcfg.get("time", {})
    dev = hcfg.get("device", {})

    sync_color = "#66bb6a" if ts["synced"] else "#ef5350"
    sync_label = "Synkroniseret" if ts["synced"] else "Ikke synkroniseret"
    offset_str = f"{ts['offset_ms']} ms" if ts["offset_ms"] is not None else "–"
    stratum_str = ts.get("stratum") or "–"

    # Tidskonfiguration — vis kilde pr. felt (global/kunde/site/kamera)
    gps_dev  = time_cfg.get("sources", {}).get("gps", {}).get("device", "/dev/ttyS3")
    gps_baud = time_cfg.get("sources", {}).get("gps", {}).get("baud", 9600)
    gps_en   = time_cfg.get("sources", {}).get("gps", {}).get("enabled", True)
    hend_en  = time_cfg.get("sources", {}).get("headend", {}).get("enabled", True)
    hend_int = time_cfg.get("sources", {}).get("headend", {}).get("interval_minutes", 6)
    ntp_en   = time_cfg.get("sources", {}).get("ntp", {}).get("enabled", True)
    ntp_srv  = ", ".join(time_cfg.get("sources", {}).get("ntp", {}).get("servers", ["pool.ntp.org"]))
    tw       = cfg["totp"].get("valid_window", 3)
    tz       = time_cfg.get("timezone", "Europe/Copenhagen")
    node     = os.uname().nodename
    customer = dev.get("customer_name", "–")
    site     = dev.get("site_name", "–")
    camera   = dev.get("camera_name", "–")

    msg_html = f'<p class="msg ok">{msg}</p>' if msg else ""

    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeLapse Pro — Management</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #ddd; min-height: 100vh; }}
  header {{ background: #16213e; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid #234; }}
  header h1 {{ font-size: 1rem; color: #4fc3f7; flex: 1; }}
  header .loc {{ font-size: 0.75rem; color: #666; }}
  nav {{ background: #0f3460; display: flex; gap: 0; border-bottom: 1px solid #234; overflow-x: auto; }}
  nav a {{ color: #aaa; text-decoration: none; padding: 0.75rem 1.25rem; font-size: 0.85rem; white-space: nowrap; }}
  nav a.active {{ color: #4fc3f7; border-bottom: 2px solid #4fc3f7; }}
  .content {{ padding: 1.5rem; max-width: 600px; }}
  .card {{ background: #16213e; border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; }}
  .card h2 {{ font-size: 0.9rem; color: #4fc3f7; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .status-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; background: {sync_color}; flex-shrink: 0; }}
  .status-label {{ font-size: 0.95rem; }}
  .meta {{ font-size: 0.75rem; color: #666; margin-top: 0.25rem; }}
  .field {{ margin-bottom: 1rem; }}
  .field label {{ font-size: 0.75rem; color: #888; display: block; margin-bottom: 0.3rem; }}
  .field .source {{ font-size: 0.65rem; color: #556; float: right; }}
  input[type=text], input[type=number], select {{ width: 100%; padding: 0.6rem 0.75rem; border-radius: 6px;
    border: 1px solid #334; background: #0f3460; color: #fff; font-size: 0.9rem; }}
  .toggle {{ display: flex; align-items: center; gap: 0.5rem; }}
  .toggle input {{ width: auto; }}
  button[type=submit] {{ width: 100%; padding: 0.75rem; border-radius: 8px; border: none;
    background: #4fc3f7; color: #000; font-size: 0.95rem; font-weight: 600; cursor: pointer; margin-top: 0.5rem; }}
  .msg.ok {{ color: #66bb6a; font-size: 0.85rem; margin-bottom: 1rem; }}
  .section-sep {{ border-top: 1px solid #234; margin: 1rem 0; }}
  .hierarchy {{ display: flex; gap: 0.3rem; font-size: 0.7rem; color: #556; margin-bottom: 1.25rem; flex-wrap: wrap; }}
  .hierarchy span {{ background: #1e2d4a; padding: 0.2rem 0.5rem; border-radius: 4px; }}
  .hierarchy span.active {{ color: #4fc3f7; border: 1px solid #4fc3f7; }}
</style>
</head>
<body>
<header>
  <h1>TimeLapse Pro</h1>
  <span class="loc">{node}</span>
</header>
<nav>
  <a href="/mgmt/" class="{'active' if section == 'time' else ''}">Tid</a>
  <a href="/mgmt/network" class="{'active' if section == 'network' else ''}">Netværk</a>
  <a href="/mgmt/technician" class="{'active' if section == 'technician' else ''}">Tekniker</a>
  <a href="/mgmt/cli" class="{'active' if section == 'cli' else ''}">CLI</a>
  <a href="/mgmt/system" class="{'active' if section == 'system' else ''}">System</a>
</nav>
<div class="content">
  <div class="hierarchy">
    <span>Global</span><span>›</span>
    <span>Kunde: {customer}</span><span>›</span>
    <span>Site: {site}</span><span>›</span>
    <span class="active">Kamera: {camera}</span>
  </div>

  {msg_html}

  <div class="card">
    <h2>Tidsstatus</h2>
    <div class="status-row">
      <div class="dot"></div>
      <div>
        <div class="status-label">{sync_label}</div>
        <div class="meta">Kilde: {ts['source']} · Offset: {offset_str} · Stratum: {stratum_str}</div>
        <div class="meta">Lokalt ur: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Tidssynkronisering</h2>
    <form method="post" action="/mgmt/time/save">
      <div class="field">
        <label>Tidszone <span class="source">arvet · site</span></label>
        <input type="text" name="timezone" value="{tz}">
      </div>
      <div class="field">
        <label>TOTP tolerance (±vinduer á 30 sek) <span class="source">kamera</span></label>
        <input type="number" name="totp_valid_window" value="{tw}" min="1" max="10">
      </div>
      <div class="section-sep"></div>
      <div class="field">
        <label>GPS <span class="source">global</span></label>
        <div class="toggle">
          <input type="checkbox" name="gps_enabled" {'checked' if gps_en else ''}>
          <span>Aktiveret</span>
        </div>
      </div>
      <div class="field">
        <label>GPS device <span class="source">kamera</span></label>
        <input type="text" name="gps_device" value="{gps_dev}">
      </div>
      <div class="field">
        <label>GPS baudrate <span class="source">global</span></label>
        <input type="number" name="gps_baud" value="{gps_baud}">
      </div>
      <div class="section-sep"></div>
      <div class="field">
        <label>Headend tidssynk <span class="source">global</span></label>
        <div class="toggle">
          <input type="checkbox" name="headend_enabled" {'checked' if hend_en else ''}>
          <span>Aktiveret</span>
        </div>
      </div>
      <div class="field">
        <label>Headend synk-interval (minutter) <span class="source">global</span></label>
        <input type="number" name="headend_interval" value="{hend_int}" min="1" max="60">
      </div>
      <div class="section-sep"></div>
      <div class="field">
        <label>NTP fallback <span class="source">global</span></label>
        <div class="toggle">
          <input type="checkbox" name="ntp_enabled" {'checked' if ntp_en else ''}>
          <span>Aktiveret</span>
        </div>
      </div>
      <div class="field">
        <label>NTP servere <span class="source">global</span></label>
        <input type="text" name="ntp_servers" value="{ntp_srv}">
      </div>
      <button type="submit">Gem kamera-overrides</button>
    </form>
  </div>

  <div class="card">
    <h2>TOTP QR-kode</h2>
    <div class="meta" style="margin-bottom:0.8rem">
      Aktivt secret: <strong>{cfg["totp"].get("sid", "factory-default")}</strong>
      <span class="source" style="margin-left:0.5rem">{'fabriksstandard' if cfg["totp"].get("sid","factory-default") == "factory-default" else 'CMDB-synkroniseret'}</span>
    </div>
    <p style="font-size:0.82rem;color:#aaa;margin-bottom:1rem">
      QR-koden ændres kun ved eksplicit opdatering. Teknikeren skal have
      den nye QR fra CMDB inden opdatering aktiveres.
    </p>
    <form method="post" action="/mgmt/totp-sync" onsubmit="return confirm('Hent og opdater TOTP-secret fra CMDB? Service genstarter automatisk.')">
      <button type="submit" style="background:#f59e0b;color:#000">
        ↻ Opdater TOTP fra CMDB
      </button>
    </form>
  </div>
</div>
</body>
</html>"""


def _run_tech_cli(*args: str, timeout: int = 45, env: dict | None = None) -> tuple[bool, str]:
    """Run the shared edge technician CLI and return safe text output."""
    if not TECH_CLI.exists():
        return False, f"Tekniker CLI findes ikke: {TECH_CLI}"
    cmd = [os.environ.get("PYTHON", "/opt/timelapse/venv/bin/python3"), str(TECH_CLI), *args]
    try:
        run_env = os.environ.copy()
        if env:
            run_env.update({k: v for k, v in env.items() if v is not None})
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=run_env)
        output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
        return result.returncode == 0, output.strip() or "(intet output)"
    except Exception as exc:
        return False, str(exc)


def _parse_cli_args(raw: str) -> tuple[bool, list[str], str]:
    try:
        args = shlex.split(raw or "")
    except ValueError as exc:
        return False, [], f"Kunne ikke parse CLI-argumenter: {exc}"
    if not args:
        return False, [], "Skriv argumenter til bootstrap_cli.py, fx --network-status"
    if args[0].endswith("bootstrap_cli.py"):
        args = args[1:]
    for arg in args:
        if arg.startswith("-") and arg not in CLI_ALLOWED_FLAGS:
            return False, [], f"Flag ikke tilladt i lokal UI: {arg}"
    return True, args, ""


def _wifi_network_options() -> str:
    try:
        result = subprocess.run(
            ["nmcli", "--escape", "no", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return ""
    seen: set[str] = set()
    options = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if not parts or not parts[0] or parts[0] in seen:
            continue
        seen.add(parts[0])
        label = f"{parts[0]} ({parts[1] if len(parts) > 1 else '?'}%)"
        if len(parts) > 2 and parts[2]:
            label += f" {parts[2]}"
        options.append(f'<option value="{html.escape(parts[0])}">{html.escape(label)}</option>')
    return "".join(options)


def _latest_tech_image() -> Path | None:
    for root in (TECH_CAPTURE_DIR, VIDEO_FRAME_DIR):
        try:
            images = sorted(
                [p for p in root.glob("*") if p.suffix.lower() in {".jpg", ".jpeg"}],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            images = []
        if images:
            return images[0]
    return None


def _tech_image_url(path: Path | None) -> str:
    if not path:
        return ""
    try:
        if path.resolve().is_relative_to(TECH_CAPTURE_DIR.resolve()):
            return f"/mgmt/technician/image/{html.escape(path.name)}?t={int(path.stat().st_mtime)}"
        if path.resolve().is_relative_to(VIDEO_FRAME_DIR.resolve()):
            return f"/mgmt/technician/video-frame/{html.escape(path.name)}?t={int(path.stat().st_mtime)}"
    except Exception:
        return ""
    return ""


def _image_panel(title: str = "Seneste test-/fokusbillede") -> str:
    image = _latest_tech_image()
    url = _tech_image_url(image)
    if not url:
        return '<p class="empty">Intet testbillede endnu</p>'
    size = ""
    try:
        size = f"{image.stat().st_size / 1_000_000:.1f} MB"
    except Exception:
        pass
    return (
        f'<div class="preview"><img src="{url}" alt="{html.escape(title)}">'
        f'<div class="meta">{html.escape(image.name)} {html.escape(size)}</div></div>'
    )


def _safe_image_from(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    root_resolved = root.resolve()
    if not path.is_relative_to(root_resolved) or path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise HTTPException(status_code=404)
    if not path.exists():
        raise HTTPException(status_code=404)
    return path


def _technician_snapshot() -> dict:
    """Use bootstrap_cli's shared status collector when available."""
    try:
        import sys
        tools_dir = str(EDGE_ROOT / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import bootstrap_cli
        return bootstrap_cli.collect_local_status(EDGE_ROOT, include_camera=False)
    except Exception as exc:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "error": str(exc),
            "device": {},
            "service": {},
            "system": {},
            "network": {},
            "storage": {},
            "camera": {},
            "ai": {},
        }


def _kv_table(data: dict) -> str:
    if not data:
        return '<p class="empty">Ingen data</p>'
    rows = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = yaml.safe_dump(value, allow_unicode=True, default_flow_style=False).strip()
        rows.append(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value or ''))}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def _system_snapshot() -> dict:
    return _technician_snapshot()


def _run_system_action(action: str) -> tuple[bool, str]:
    commands = {
        "status-edge": ["systemctl", "status", "timelapse-edge", "--no-pager", "-l"],
        "status-totp": ["systemctl", "status", "timelapse-totp", "--no-pager", "-l"],
        "restart-edge": ["sudo", "systemctl", "restart", "timelapse-edge"],
        "restart-totp": ["sudo", "systemctl", "restart", "timelapse-totp"],
        "journal-edge": ["journalctl", "--no-pager", "-u", "timelapse-edge", "-n", "180"],
        "journal-totp": ["journalctl", "--no-pager", "-u", "timelapse-totp", "-n", "120"],
        "disk": ["df", "-h", "/", "/data"],
        "network": ["sh", "-c", "ip -brief addr; printf '\\n'; ip route"],
    }
    cmd = commands.get(action)
    if not cmd:
        return False, f"Ukendt systemhandling: {action}"
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
        return result.returncode == 0, output.strip() or "(intet output)"
    except Exception as exc:
        return False, str(exc)


def _system_page(msg: str = "", output: str = "") -> str:
    status = _system_snapshot()
    generated = status.get("generated_at", "")
    msg_html = f'<p class="msg ok">{html.escape(msg)}</p>' if msg else ""
    output_html = (
        f'<div class="card wide"><h2>Output</h2><pre>{html.escape(output)}</pre></div>'
        if output else ""
    )
    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="45; url=/mgmt/system">
<title>TimeLapse Pro — System</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #ddd; min-height: 100vh; }}
  header {{ background: #16213e; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid #234; }}
  header h1 {{ font-size: 1rem; color: #4fc3f7; flex: 1; }}
  header .loc {{ font-size: 0.75rem; color: #777; }}
  nav {{ background: #0f3460; display: flex; border-bottom: 1px solid #234; overflow-x: auto; }}
  nav a {{ color: #aaa; text-decoration: none; padding: 0.75rem 1.25rem; font-size: 0.85rem; white-space: nowrap; }}
  nav a.active {{ color: #4fc3f7; border-bottom: 2px solid #4fc3f7; }}
  .content {{ padding: 1rem; max-width: 1180px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
  .card {{ background: #16213e; border-radius: 10px; padding: 1rem; border: 1px solid #26385a; }}
  .card.wide {{ grid-column: 1 / -1; }}
  h2 {{ font-size: 0.82rem; color: #4fc3f7; margin-bottom: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
  th {{ width: 38%; color: #8aa0bf; text-align: left; font-weight: 600; vertical-align: top; }}
  td, th {{ border-top: 1px solid #26385a; padding: 0.42rem 0.2rem; word-break: break-word; }}
  .actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem; }}
  button {{ border-radius: 7px; border: 1px solid #334; padding: 0.62rem 0.7rem; font-size: 0.85rem; background: #4fc3f7; color: #001018; font-weight: 700; cursor: pointer; }}
  button.secondary {{ background: #26385a; color: #dbeafe; border-color: #3b5279; }}
  button.warn {{ background: #f59e0b; color: #101010; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.78rem; background: #0b1220; border-radius: 8px; padding: 0.8rem; color: #d6e4ff; max-height: 420px; overflow: auto; }}
  .msg.ok {{ color: #66bb6a; font-size: 0.85rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
<header>
  <h1>TimeLapse Pro</h1>
  <span class="loc">{html.escape(os.uname().nodename)} · {html.escape(generated)} UTC</span>
</header>
<nav>
  <a href="/mgmt/">Tid</a>
  <a href="/mgmt/network">Netværk</a>
  <a href="/mgmt/technician">Tekniker</a>
  <a href="/mgmt/cli">CLI</a>
  <a href="/mgmt/system" class="active">System</a>
</nav>
<div class="content">
  {msg_html}
  <div class="grid">
    <div class="card"><h2>System</h2>{_kv_table(status.get("system", {}))}</div>
    <div class="card"><h2>Service</h2>{_kv_table(status.get("service", {}))}</div>
    <div class="card"><h2>Netvaerk</h2>{_kv_table(status.get("network", {}))}</div>
    <div class="card"><h2>Storage / upload</h2>{_kv_table(status.get("storage", {}))}</div>
    <div class="card wide">
      <h2>Systemhandlinger</h2>
      <form method="post" action="/mgmt/system/action" class="actions">
        <button name="action" value="status-edge">Edge status</button>
        <button name="action" value="status-totp">TOTP status</button>
        <button name="action" value="journal-edge">Edge logs</button>
        <button name="action" value="journal-totp">TOTP logs</button>
        <button name="action" value="disk">Disk</button>
        <button name="action" value="network">Netvaerk</button>
        <button class="warn" name="action" value="restart-edge" onclick="return confirm('Genstart timelapse-edge?')">Genstart Edge</button>
        <button class="warn" name="action" value="restart-totp" onclick="return confirm('Genstart lokal TOTP UI?')">Genstart TOTP UI</button>
      </form>
    </div>
    {output_html}
  </div>
</div>
</body>
</html>"""


def _network_page(msg: str = "", output: str = "") -> str:
    status = _technician_snapshot()
    generated = status.get("generated_at", "")
    msg_html = f'<p class="msg ok">{html.escape(msg)}</p>' if msg else ""
    output_html = (
        f'<div class="card wide"><h2>Output</h2><pre>{html.escape(output)}</pre></div>'
        if output else ""
    )
    devices = status.get("network", {}).get("devices", []) or []
    device_options = "".join(
        f'<option value="{html.escape(str(line).split(":")[0])}">{html.escape(str(line))}</option>'
        for line in devices
    )
    if not device_options:
        device_options = '<option value="">Ingen nmcli devices fundet</option>'
    wifi_options = _wifi_network_options()
    if not wifi_options:
        wifi_options = '<option value="">Ingen SSID fundet - skriv manuelt nedenfor</option>'
    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60; url=/mgmt/network">
<title>TimeLapse Pro — Netværk</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #ddd; min-height: 100vh; }}
  header {{ background: #16213e; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid #234; }}
  header h1 {{ font-size: 1rem; color: #4fc3f7; flex: 1; }}
  header .loc {{ font-size: 0.75rem; color: #777; }}
  nav {{ background: #0f3460; display: flex; border-bottom: 1px solid #234; overflow-x: auto; }}
  nav a {{ color: #aaa; text-decoration: none; padding: 0.75rem 1.25rem; font-size: 0.85rem; white-space: nowrap; }}
  nav a.active {{ color: #4fc3f7; border-bottom: 2px solid #4fc3f7; }}
  .content {{ padding: 1rem; max-width: 1180px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
  .card {{ background: #16213e; border-radius: 10px; padding: 1rem; border: 1px solid #26385a; }}
  .card.wide {{ grid-column: 1 / -1; }}
  h2 {{ font-size: 0.82rem; color: #4fc3f7; margin-bottom: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
  th {{ width: 38%; color: #8aa0bf; text-align: left; font-weight: 600; vertical-align: top; }}
  td, th {{ border-top: 1px solid #26385a; padding: 0.42rem 0.2rem; word-break: break-word; }}
  label {{ display: block; color: #8aa0bf; font-size: 0.76rem; margin: 0.55rem 0 0.25rem; }}
  input, select {{ width: 100%; background: #0f3460; color: #fff; border: 1px solid #334; border-radius: 7px; padding: 0.58rem 0.65rem; font-size: 0.85rem; }}
  .actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem; }}
  button {{ border-radius: 7px; border: 1px solid #334; padding: 0.62rem 0.7rem; font-size: 0.85rem; background: #4fc3f7; color: #001018; font-weight: 700; cursor: pointer; margin-top: 0.7rem; }}
  button.secondary {{ background: #26385a; color: #dbeafe; border-color: #3b5279; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.78rem; background: #0b1220; border-radius: 8px; padding: 0.8rem; color: #d6e4ff; max-height: 420px; overflow: auto; }}
  .msg.ok {{ color: #66bb6a; font-size: 0.85rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
<header>
  <h1>TimeLapse Pro</h1>
  <span class="loc">{html.escape(os.uname().nodename)} · {html.escape(generated)} UTC</span>
</header>
<nav>
  <a href="/mgmt/">Tid</a>
  <a href="/mgmt/network" class="active">Netværk</a>
  <a href="/mgmt/technician">Tekniker</a>
  <a href="/mgmt/cli">CLI</a>
  <a href="/mgmt/system">System</a>
</nav>
<div class="content">
  {msg_html}
  <div class="grid">
    <div class="card"><h2>Status</h2>{_kv_table(status.get("network", {}))}</div>
    <div class="card">
      <h2>WiFi</h2>
      <form method="post" action="/mgmt/network/wifi">
        <label>SSID fra scan</label>
        <select name="ssid_select">{wifi_options}</select>
        <label>SSID manuelt</label>
        <input name="ssid_manual" placeholder="Netværksnavn hvis det ikke står på listen">
        <label>Password</label>
        <input name="password" type="password" placeholder="Gemmes i NetworkManager">
        <button>Tilslut WiFi</button>
      </form>
    </div>
    <div class="card">
      <h2>IPv4</h2>
      <form method="post" action="/mgmt/network/ipv4">
        <label>Interface</label>
        <select name="device">{device_options}</select>
        <label>Mode</label>
        <select name="mode"><option value="dhcp">DHCP</option><option value="static">Statisk</option></select>
        <label>IPv4/CIDR</label>
        <input name="address" placeholder="192.168.1.50/24">
        <label>Gateway</label>
        <input name="gateway" placeholder="192.168.1.1">
        <label>DNS</label>
        <input name="dns" placeholder="1.1.1.1,8.8.8.8">
        <label>Route metric</label>
        <input name="metric" placeholder="100">
        <button>Gem IPv4</button>
      </form>
    </div>
    <div class="card">
      <h2>Statiske routes</h2>
      <form method="post" action="/mgmt/network/routes">
        <label>Interface</label>
        <select name="device">{device_options}</select>
        <label>Routes</label>
        <input name="routes" placeholder="10.10.0.0/16 192.168.1.1, 172.16.5.0/24 192.168.1.254">
        <button>Gem routes</button>
      </form>
    </div>
    <div class="card">
      <h2>Prioritet og test</h2>
      <form method="post" action="/mgmt/network/preference">
        <label>Foretrukken forbindelse</label>
        <select name="first"><option value="ethernet">Ethernet</option><option value="wifi">WiFi</option><option value="4g">4G</option></select>
        <button>Gem prioritet</button>
      </form>
      <form method="post" action="/mgmt/network/action" class="actions">
        <button class="secondary" name="action" value="status">Detaljeret status</button>
        <button class="secondary" name="action" value="headend">Headend test</button>
      </form>
    </div>
    {output_html}
  </div>
</div>
</body>
</html>"""


def _option_list(values: list[str], selected: str = "") -> str:
    return "".join(
        f'<option value="{html.escape(value)}" {"selected" if value == selected else ""}>{html.escape(value)}</option>'
        for value in values
    )


def _cli_page(msg: str = "", output: str = "", command: str = "") -> str:
    status = _technician_snapshot()
    generated = status.get("generated_at", "")
    msg_html = f'<p class="msg ok">{html.escape(msg)}</p>' if msg else ""
    output_html = (
        f'<div class="card wide"><h2>Output</h2><pre>{html.escape(output)}</pre></div>'
        if output else ""
    )
    buttons = [
        ("--status", "Overblik"),
        ("--network-status", "Netværk"),
        ("--test-headend", "Headend"),
        ("--camera-summary --maintenance", "Kamera"),
        ("--photo-status --maintenance", "Fotostatus"),
        ("--gps-status", "GPS"),
        ("--npu-status", "NPU"),
        ("--doctor", "Doctor"),
    ]
    quick = "".join(
        f'<button name="command" value="{html.escape(cmd)}">{html.escape(label)}</button>'
        for cmd, label in buttons
    )
    allowed = " ".join(sorted(CLI_ALLOWED_FLAGS))
    shell_enabled = bool(load_config()["management"].get("enable_interactive_shell", False))
    shell_panel = ""
    if shell_enabled:
        shell_panel = """
    <div class=\"card wide\">
      <h2>SSH bash</h2>
      <p class=\"hint\">Interaktiv lokal shell på edgen bag TOTP-sessionen. Luk terminalen når du er færdig.</p>
      <div class=\"actions\">
        <button type=\"button\" onclick=\"openShell()\">Åbn bash</button>
        <button class=\"secondary\" type=\"button\" onclick=\"closeShell()\">Luk bash</button>
      </div>
      <textarea id=\"term\" spellcheck=\"false\" autocomplete=\"off\" autocorrect=\"off\" autocapitalize=\"off\"></textarea>
    </div>"""
    shell_script = ""
    if shell_enabled:
        shell_script = """
let shellWs = null;
const term = document.getElementById('term');
function openShell() {
  if (shellWs && shellWs.readyState === WebSocket.OPEN) return;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  shellWs = new WebSocket(proto + '//' + location.host + '/mgmt/cli/bash/ws');
  shellWs.onopen = () => { term.value += '\\n[connected]\\n'; term.focus(); };
  shellWs.onmessage = (event) => { term.value += event.data; term.scrollTop = term.scrollHeight; };
  shellWs.onclose = () => { term.value += '\\n[closed]\\n'; };
}
function closeShell() { if (shellWs) shellWs.close(); }
term.addEventListener('keydown', (event) => {
  if (!shellWs || shellWs.readyState !== WebSocket.OPEN) return;
  if (event.key === 'Enter') { shellWs.send('\\n'); event.preventDefault(); }
  else if (event.key === 'Backspace') { shellWs.send('\\x7f'); event.preventDefault(); }
  else if (event.key === 'Tab') { shellWs.send('\\t'); event.preventDefault(); }
  else if (event.ctrlKey && event.key.length === 1) { shellWs.send(String.fromCharCode(event.key.toUpperCase().charCodeAt(0) - 64)); event.preventDefault(); }
  else if (!event.metaKey && !event.altKey && event.key.length === 1) { shellWs.send(event.key); event.preventDefault(); }
});"""
    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TimeLapse Pro — CLI</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #ddd; min-height: 100vh; }}
  header {{ background: #16213e; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid #234; }}
  header h1 {{ font-size: 1rem; color: #4fc3f7; flex: 1; }}
  header .loc {{ font-size: 0.75rem; color: #777; }}
  nav {{ background: #0f3460; display: flex; border-bottom: 1px solid #234; overflow-x: auto; }}
  nav a {{ color: #aaa; text-decoration: none; padding: 0.75rem 1.25rem; font-size: 0.85rem; white-space: nowrap; }}
  nav a.active {{ color: #4fc3f7; border-bottom: 2px solid #4fc3f7; }}
  .content {{ padding: 1rem; max-width: 1180px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
  .card {{ background: #16213e; border-radius: 10px; padding: 1rem; border: 1px solid #26385a; }}
  .card.wide {{ grid-column: 1 / -1; }}
  h2 {{ font-size: 0.82rem; color: #4fc3f7; margin-bottom: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  label {{ display: block; color: #8aa0bf; font-size: 0.76rem; margin: 0.55rem 0 0.25rem; }}
  input {{ width: 100%; background: #0f3460; color: #fff; border: 1px solid #334; border-radius: 7px; padding: 0.58rem 0.65rem; font-size: 0.85rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  textarea {{ width: 100%; min-height: 360px; background: #050812; color: #d6e4ff; border: 1px solid #26385a; border-radius: 8px; padding: 0.8rem; font-size: 0.82rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 0.5rem; }}
  button {{ border-radius: 7px; border: 1px solid #334; padding: 0.62rem 0.7rem; font-size: 0.85rem; background: #4fc3f7; color: #001018; font-weight: 700; cursor: pointer; margin-top: 0.7rem; }}
  button.secondary {{ background: #26385a; color: #dbeafe; border-color: #3b5279; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.78rem; background: #0b1220; border-radius: 8px; padding: 0.8rem; color: #d6e4ff; max-height: 520px; overflow: auto; }}
  .msg.ok {{ color: #66bb6a; font-size: 0.85rem; margin-bottom: 1rem; }}
  .hint {{ color: #8aa0bf; font-size: 0.76rem; line-height: 1.35; }}
</style>
</head>
<body>
<header>
  <h1>TimeLapse Pro</h1>
  <span class="loc">{html.escape(os.uname().nodename)} · {html.escape(generated)} UTC</span>
</header>
<nav>
  <a href="/mgmt/">Tid</a>
  <a href="/mgmt/network">Netværk</a>
  <a href="/mgmt/technician">Tekniker</a>
  <a href="/mgmt/cli" class="active">CLI</a>
  <a href="/mgmt/system">System</a>
</nav>
<div class="content">
  {msg_html}
  <div class="grid">
    <div class="card wide">
      <h2>Hurtigkommandoer</h2>
      <form method="post" action="/mgmt/cli/run" class="actions">{quick}</form>
    </div>
    <div class="card wide">
      <h2>Bootstrap CLI</h2>
      <form method="post" action="/mgmt/cli/run">
        <label>/opt/timelapse/edge/tools/bootstrap_cli.py</label>
        <input name="command" value="{html.escape(command)}" placeholder="--network-status">
        <button>Kør kommando</button>
      </form>
      <p class="hint">Tilladte flags: {html.escape(allowed)}</p>
    </div>
    {shell_panel}
    {output_html}
  </div>
</div>
<script>{shell_script}</script>
</body>
</html>"""


def _technician_page(msg: str = "", output: str = "") -> str:
    status = _technician_snapshot()
    generated = status.get("generated_at", "")
    photo_options = "".join(
        f'<option value="{key}">{label}</option>'
        for key, label in [
            ("exposure_comp", "Eksponeringskompensation"),
            ("iso", "ISO"),
            ("white_balance", "Hvidbalance"),
            ("shutter_speed", "Lukkertid"),
            ("aperture", "Blænde"),
            ("focus_mode", "Fokusmode"),
            ("image_format", "Billedformat"),
        ]
    )
    focus_options = _option_list(FOCUS_DRIVE_OPTIONS)
    config_options = "".join(
        f'<option value="{html.escape(path)}">{html.escape(label)} - {html.escape(path)}</option>'
        for path, label in CAMERA_CONFIG_OPTIONS
    )
    photo_values_json = json.dumps(PHOTO_VALUE_OPTIONS, ensure_ascii=False)
    latest_panel = _image_panel()
    msg_html = f'<p class="msg ok">{html.escape(msg)}</p>' if msg else ""
    output_html = (
        f'<div class="card wide"><h2>Output</h2><pre>{html.escape(output)}</pre></div>'
        if output else ""
    )
    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="45; url=/mgmt/technician">
<title>TimeLapse Pro — Tekniker</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #ddd; min-height: 100vh; }}
  header {{ background: #16213e; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid #234; }}
  header h1 {{ font-size: 1rem; color: #4fc3f7; flex: 1; }}
  header .loc {{ font-size: 0.75rem; color: #777; }}
  nav {{ background: #0f3460; display: flex; border-bottom: 1px solid #234; overflow-x: auto; }}
  nav a {{ color: #aaa; text-decoration: none; padding: 0.75rem 1.25rem; font-size: 0.85rem; white-space: nowrap; }}
  nav a.active {{ color: #4fc3f7; border-bottom: 2px solid #4fc3f7; }}
  .content {{ padding: 1rem; max-width: 1180px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
  .card {{ background: #16213e; border-radius: 10px; padding: 1rem; border: 1px solid #26385a; }}
  .card.wide {{ grid-column: 1 / -1; }}
  h2 {{ font-size: 0.82rem; color: #4fc3f7; margin-bottom: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
  th {{ width: 38%; color: #8aa0bf; text-align: left; font-weight: 600; vertical-align: top; }}
  td, th {{ border-top: 1px solid #26385a; padding: 0.42rem 0.2rem; word-break: break-word; }}
  .actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem; }}
  button, input, select {{ border-radius: 7px; border: 1px solid #334; padding: 0.62rem 0.7rem; font-size: 0.85rem; }}
  button {{ background: #4fc3f7; color: #001018; font-weight: 700; cursor: pointer; }}
  button.secondary {{ background: #26385a; color: #dbeafe; border-color: #3b5279; }}
  input, select {{ width: 100%; background: #0f3460; color: #fff; margin-bottom: 0.5rem; }}
  label {{ display: block; color: #8aa0bf; font-size: 0.76rem; margin: 0.45rem 0 0.25rem; }}
  form.inline {{ margin: 0; }}
  .hint {{ color: #8aa0bf; font-size: 0.76rem; line-height: 1.35; margin-bottom: 0.55rem; }}
  .preview img {{ width: 100%; max-height: 520px; object-fit: contain; background: #050812; border: 1px solid #26385a; border-radius: 8px; }}
  .stream {{ width: 100%; min-height: 220px; object-fit: contain; background: #050812; border: 1px solid #26385a; border-radius: 8px; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.78rem; background: #0b1220; border-radius: 8px; padding: 0.8rem; color: #d6e4ff; max-height: 420px; overflow: auto; }}
  .msg.ok {{ color: #66bb6a; font-size: 0.85rem; margin-bottom: 1rem; }}
  .empty {{ color: #777; font-size: 0.8rem; }}
</style>
</head>
<body>
<header>
  <h1>TimeLapse Pro</h1>
  <span class="loc">{html.escape(os.uname().nodename)} · {html.escape(generated)} UTC</span>
</header>
<nav>
  <a href="/mgmt/">Tid</a>
  <a href="/mgmt/network">Netværk</a>
  <a href="/mgmt/technician" class="active">Tekniker</a>
  <a href="/mgmt/cli">CLI</a>
  <a href="/mgmt/system">System</a>
</nav>
<div class="content">
  {msg_html}
  <div class="grid">
    <div class="card"><h2>Device</h2>{_kv_table(status.get("device", {}))}</div>
    <div class="card"><h2>Service</h2>{_kv_table(status.get("service", {}))}</div>
    <div class="card"><h2>Netvaerk</h2>{_kv_table(status.get("network", {}))}</div>
    <div class="card"><h2>Storage / upload</h2>{_kv_table(status.get("storage", {}))}</div>
    <div class="card"><h2>Kamera</h2>{_kv_table(status.get("camera", {}))}</div>
    <div class="card"><h2>Edge AI / NPU</h2>{_kv_table(status.get("ai", {}))}</div>
    <div class="card wide">
      <h2>Handlinger</h2>
      <form method="post" action="/mgmt/technician/action" class="actions">
        <button name="action" value="doctor">Doctor</button>
        <button name="action" value="camera-summary">Kamera status</button>
        <button name="action" value="gps">GPS status</button>
        <button name="action" value="npu">NPU status</button>
        <button name="action" value="logs">Service logs</button>
        <button name="action" value="headend">Headend test</button>
        <button name="action" value="photo-status">Fotostatus</button>
      </form>
    </div>
    <div class="card">
      <h2>Fototeknik</h2>
      <form method="post" action="/mgmt/technician/photo">
        <label>Parameter</label>
        <select name="key" id="photo-key" onchange="updatePhotoValues()">{photo_options}</select>
        <label>Ny værdi</label>
        <select name="value" id="photo-value"></select>
        <label>Manuel værdi</label>
        <input name="value_manual" placeholder="Skriv manuelt hvis værdien ikke står i listen">
        <button>Sæt fotoparameter</button>
      </form>
    </div>
    <div class="card">
      <h2>Fokus</h2>
      <p class="hint">Focus drive flytter objektivets fokusmotor i små trin. Brug Near for at flytte fokus tættere på kameraet og Far for længere væk. Tag testbillede efter små ændringer.</p>
      <form method="post" action="/mgmt/technician/focus">
        <label>Focus drive</label>
        <select name="value">{focus_options}</select>
        <button>Kør focus drive</button>
      </form>
      <form method="post" action="/mgmt/technician/action" style="margin-top:0.5rem">
        <button class="secondary" name="action" value="autofocus">Autofokus</button>
      </form>
    </div>
    <div class="card">
      <h2>Kamera config</h2>
      <form method="post" action="/mgmt/technician/config">
        <label>Config path</label>
        <select name="path">{config_options}</select>
        <label>Ny værdi</label>
        <input name="value" list="camera-config-values" placeholder="Vælg eller skriv værdi">
        <datalist id="camera-config-values">
          {_option_list(sorted(set(sum(PHOTO_VALUE_OPTIONS.values(), []))))}
        </datalist>
        <button>Sæt config</button>
      </form>
    </div>
    <div class="card">
      <h2>Testbillede</h2>
      <form method="post" action="/mgmt/technician/capture">
        <input name="out_dir" value="/tmp/timelapse-tech-captures">
        <button>Tag testbillede + QA</button>
      </form>
    </div>
    <div class="card wide">
      <h2>Aktuelt fokus-/testbillede</h2>
      {latest_panel}
    </div>
    <div class="card wide">
      <h2>Video preview</h2>
      <p class="hint">Preview bruger kameraets preview-capture gentaget som MJPEG. Stop siden eller skift væk når du er færdig, så kameraet frigives.</p>
      <button class="secondary" type="button" onclick="document.getElementById('preview-stream').src='/mgmt/technician/video.mjpg?t='+Date.now()">Start preview</button>
      <button class="secondary" type="button" onclick="document.getElementById('preview-stream').removeAttribute('src')">Stop preview</button>
      <img id="preview-stream" class="stream" alt="Live preview stream">
    </div>
    {output_html}
  </div>
</div>
<script>
const PHOTO_VALUES = {photo_values_json};
function updatePhotoValues() {{
  const key = document.getElementById('photo-key').value;
  const select = document.getElementById('photo-value');
  select.innerHTML = '';
  (PHOTO_VALUES[key] || []).forEach((value) => {{
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }});
}}
updatePhotoValues();
</script>
</body>
</html>"""


@app.get("/mgmt/", response_class=HTMLResponse)
@app.get("/mgmt", response_class=HTMLResponse)
async def mgmt_index(request: Request):
    cfg = load_config()
    hcfg = _fetch_headend_config(cfg)
    return HTMLResponse(_mgmt_page("time", hcfg, _get_time_status()))


@app.get("/mgmt/technician", response_class=HTMLResponse)
async def mgmt_technician(request: Request):
    return HTMLResponse(_technician_page())


@app.get("/mgmt/network", response_class=HTMLResponse)
async def mgmt_network(request: Request):
    return HTMLResponse(_network_page())


@app.get("/mgmt/cli", response_class=HTMLResponse)
async def mgmt_cli(request: Request):
    return HTMLResponse(_cli_page())


@app.get("/mgmt/cli/run")
async def mgmt_cli_run_get_fallback(request: Request):
    return RedirectResponse("/mgmt/cli", status_code=303)


@app.post("/mgmt/cli/run", response_class=HTMLResponse)
async def mgmt_cli_run(request: Request, command: str = Form(...)):
    ok_parse, args, error = _parse_cli_args(command)
    if not ok_parse:
        return HTMLResponse(_cli_page("CLI afvist", error, command), status_code=400)
    ok, output = _run_tech_cli(*args, timeout=120)
    rendered = f"$ bootstrap_cli.py {' '.join(args)}\n\n{output}"
    return HTMLResponse(_cli_page("OK" if ok else "Fejl", rendered, command))


@app.websocket("/mgmt/cli/bash/ws")
async def mgmt_cli_bash_ws(websocket: WebSocket):
    if not load_config()["management"].get("enable_interactive_shell", False):
        await websocket.close(code=1008)
        return
    token = websocket.cookies.get(SESSION_COOKIE, "")
    client_ip = websocket.client.host if websocket.client else ""
    if not _valid_token(token, client_ip):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    master_fd, slave_fd = pty.openpty()
    env = os.environ.copy()
    env.update({"TERM": "xterm-256color", "TIMELAPSE_EDGE_ROOT": str(EDGE_ROOT)})
    proc = subprocess.Popen(
        [BASH_PATH, "-l"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(EDGE_ROOT),
        env=env,
        close_fds=True,
    )
    os.close(slave_fd)

    async def pump_shell() -> None:
        try:
            while proc.poll() is None:
                readable, _, _ = select.select([master_fd], [], [], 0.05)
                if readable:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    await websocket.send_text(data.decode(errors="replace"))
                await asyncio.sleep(0.02)
        except Exception:
            pass

    pump_task = asyncio.create_task(pump_shell())
    try:
        while proc.poll() is None:
            msg = await websocket.receive_text()
            os.write(master_fd, msg.encode())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        pump_task.cancel()
        try:
            proc.terminate()
            await asyncio.sleep(0.2)
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            os.close(master_fd)
        except Exception:
            pass


@app.get("/mgmt/technician/image/{name}")
async def mgmt_technician_image(name: str):
    return FileResponse(_safe_image_from(TECH_CAPTURE_DIR, name), media_type="image/jpeg")


@app.get("/mgmt/technician/video-frame/{name}")
async def mgmt_technician_video_frame(name: str):
    return FileResponse(_safe_image_from(VIDEO_FRAME_DIR, name), media_type="image/jpeg")


@app.get("/mgmt/technician/video.mjpg")
async def mgmt_technician_video_stream():
    async def frames():
        VIDEO_FRAME_DIR.mkdir(parents=True, exist_ok=True)
        frame = VIDEO_FRAME_DIR / "preview.jpg"
        boundary = b"--frame\r\n"
        while True:
            result = subprocess.run(
                ["gphoto2", "--capture-preview", "--filename", str(frame), "--force-overwrite"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if result.returncode != 0 or not frame.exists():
                error = (result.stderr or result.stdout or "preview failed").encode(errors="replace")[:400]
                yield boundary + b"Content-Type: text/plain\r\n\r\n" + error + b"\r\n"
                await asyncio.sleep(2)
                continue
            data = frame.read_bytes()
            yield boundary + b"Content-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(0.8)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/mgmt/network/wifi")
@app.get("/mgmt/network/ipv4")
@app.get("/mgmt/network/routes")
@app.get("/mgmt/network/preference")
@app.get("/mgmt/network/action")
async def mgmt_network_post_target_get_fallback(request: Request):
    return RedirectResponse("/mgmt/network", status_code=303)


@app.post("/mgmt/network/wifi", response_class=HTMLResponse)
async def mgmt_network_wifi(request: Request, ssid_select: str = Form(""), ssid_manual: str = Form(""), password: str = Form("")):
    ssid = (ssid_manual or ssid_select or "").strip()
    if not ssid:
        return HTMLResponse(_network_page("SSID mangler", "Vælg et SSID fra listen eller skriv manuelt."), status_code=400)
    ok, output = _run_tech_cli("--wifi-connect", ssid.strip(), timeout=90, env={"TIMELAPSE_WIFI_PASSWORD": password})
    return HTMLResponse(_network_page("WiFi opdateret" if ok else "WiFi fejlede", output))


@app.post("/mgmt/network/ipv4", response_class=HTMLResponse)
async def mgmt_network_ipv4(
    request: Request,
    device: str = Form(...),
    mode: str = Form("dhcp"),
    address: str = Form(""),
    gateway: str = Form(""),
    dns: str = Form(""),
    metric: str = Form(""),
):
    values = [device.strip(), mode.strip(), address.strip() or "-", gateway.strip() or "-", dns.strip() or "-", metric.strip() or "-"]
    ok, output = _run_tech_cli("--ipv4-config", *values, timeout=90)
    return HTMLResponse(_network_page("IPv4 opdateret" if ok else "IPv4 fejlede", output))


@app.post("/mgmt/network/routes", response_class=HTMLResponse)
async def mgmt_network_routes(request: Request, device: str = Form(...), routes: str = Form("")):
    values = [device.strip(), routes.strip() or "-"]
    ok, output = _run_tech_cli("--static-routes", *values, timeout=90)
    return HTMLResponse(_network_page("Routes opdateret" if ok else "Routes fejlede", output))


@app.post("/mgmt/network/preference", response_class=HTMLResponse)
async def mgmt_network_preference(request: Request, first: str = Form(...)):
    ok, output = _run_tech_cli("--network-preference", first.strip(), timeout=30)
    return HTMLResponse(_network_page("Prioritet gemt" if ok else "Prioritet fejlede", output))


@app.post("/mgmt/network/action", response_class=HTMLResponse)
async def mgmt_network_action(request: Request, action: str = Form(...)):
    if action == "status":
        ok, output = _run_tech_cli("--network-status", timeout=45)
    elif action == "headend":
        ok, output = _run_tech_cli("--test-headend", timeout=30)
    else:
        return HTMLResponse(_network_page("Ukendt handling", action), status_code=400)
    return HTMLResponse(_network_page("OK" if ok else "Fejl", output))


@app.get("/mgmt/technician/action")
@app.get("/mgmt/technician/focus")
@app.get("/mgmt/technician/config")
@app.get("/mgmt/technician/capture")
@app.get("/mgmt/technician/photo")
async def mgmt_technician_post_target_get_fallback(request: Request):
    return RedirectResponse("/mgmt/technician", status_code=303)


@app.post("/mgmt/technician/action", response_class=HTMLResponse)
async def mgmt_technician_action(request: Request, action: str = Form(...)):
    mapping = {
        "doctor": ["--doctor"],
        "camera-summary": ["--camera-summary", "--maintenance"],
        "gps": ["--gps-status"],
        "npu": ["--npu-status"],
        "logs": [],
        "headend": ["--test-headend"],
        "autofocus": ["--autofocus", "--maintenance"],
        "photo-status": ["--photo-status", "--maintenance"],
    }
    if action == "logs":
        try:
            result = subprocess.run(
                ["journalctl", "--no-pager", "-u", "timelapse-edge", "-n", "160"],
                capture_output=True, text=True, timeout=15,
            )
            output = (result.stdout or result.stderr or "").strip()
            return HTMLResponse(_technician_page("Service logs hentet", output))
        except Exception as exc:
            return HTMLResponse(_technician_page("Service logs fejlede", str(exc)))
    args = mapping.get(action)
    if args is None:
        return HTMLResponse(_technician_page("Ukendt handling", action), status_code=400)
    ok, output = _run_tech_cli(*args, timeout=90)
    return HTMLResponse(_technician_page("OK" if ok else "Fejl", output))


@app.post("/mgmt/technician/focus", response_class=HTMLResponse)
async def mgmt_technician_focus(request: Request, value: str = Form("")):
    value = (value or "").strip()
    if not value:
        return HTMLResponse(_technician_page("Focus drive mangler", "Skriv fx Near 1, Far 1 eller 500 i feltet."))
    ok, output = _run_tech_cli("--focus-drive", value, "--maintenance", timeout=90)
    return HTMLResponse(_technician_page("Focus drive sendt" if ok else "Focus drive fejlede", output))


@app.post("/mgmt/technician/photo", response_class=HTMLResponse)
async def mgmt_technician_photo(request: Request, key: str = Form(...), value: str = Form(""), value_manual: str = Form("")):
    key = (key or "").strip()
    value = (value_manual or value or "").strip()
    if not key or not value:
        return HTMLResponse(_technician_page("Fotoparameter mangler", "Vælg parameter og skriv ny værdi."))
    ok, output = _run_tech_cli("--photo-setting", key, value, "--maintenance", timeout=90)
    return HTMLResponse(_technician_page("Fotoparameter sat" if ok else "Fotoparameter fejlede", output))


@app.post("/mgmt/technician/config", response_class=HTMLResponse)
async def mgmt_technician_config(request: Request, path: str = Form(...), value: str = Form(...)):
    ok, output = _run_tech_cli("--set-camera-config", path, value, "--maintenance", timeout=90)
    return HTMLResponse(_technician_page("Kamera config sat" if ok else "Kamera config fejlede", output))


@app.post("/mgmt/technician/capture", response_class=HTMLResponse)
async def mgmt_technician_capture(request: Request, out_dir: str = Form("/tmp/timelapse-tech-captures")):
    ok, output = _run_tech_cli("--capture-test", out_dir, "--maintenance", timeout=150)
    return HTMLResponse(_technician_page("Testbillede taget" if ok else "Testbillede fejlede", output))


@app.post("/mgmt/time/save")
async def mgmt_time_save(request: Request,
    timezone: str = Form("Europe/Copenhagen"),
    totp_valid_window: int = Form(3),
    gps_enabled: Optional[str] = Form(None),
    gps_device: str = Form("/dev/ttyS3"),
    gps_baud: int = Form(9600),
    headend_enabled: Optional[str] = Form(None),
    headend_interval: int = Form(6),
    ntp_enabled: Optional[str] = Form(None),
    ntp_servers: str = Form("pool.ntp.org")):

    # Opdater bt-config.yaml (kamera-niveau override)
    cfg = load_config()
    cfg["totp"]["valid_window"] = totp_valid_window
    if "time" not in cfg:
        cfg["time"] = {}
    cfg["time"]["timezone"] = timezone
    cfg["time"]["sources"] = {
        "gps": {"enabled": gps_enabled == "on", "device": gps_device, "baud": gps_baud},
        "headend": {"enabled": headend_enabled == "on", "interval_minutes": headend_interval},
        "ntp": {"enabled": ntp_enabled == "on", "servers": [s.strip() for s in ntp_servers.split(",")]},
    }

    save_config(cfg)
    log.info(f"Tidskonfiguration gemt af {request.client.host}")

    hcfg = _fetch_headend_config(cfg)
    return HTMLResponse(_mgmt_page("time", hcfg, _get_time_status(), msg="✓ Gemt"))


@app.get("/mgmt/system", response_class=HTMLResponse)
async def mgmt_system(request: Request):
    return HTMLResponse(_system_page())


@app.get("/mgmt/system/action")
async def mgmt_system_action_get_fallback(request: Request):
    return RedirectResponse("/mgmt/system", status_code=303)


@app.post("/mgmt/system/action", response_class=HTMLResponse)
async def mgmt_system_action(request: Request, action: str = Form(...)):
    ok, output = _run_system_action(action)
    return HTMLResponse(_system_page("OK" if ok else "Fejl", output))


@app.post("/mgmt/totp-sync", response_class=HTMLResponse)
async def mgmt_totp_sync(request: Request):
    """Eksplicit TOTP-sync fra headend — kræver aktiv netværksforbindelse.
    Opdaterer bt-config.yaml og genstarter totp-service hvis secret er ændret.
    """
    if not _valid_token(request.cookies.get(SESSION_COOKIE, ""), request.client.host):
        return RedirectResponse("/", status_code=303)
    result = _sync_totp_from_headend()
    msg = result if isinstance(result, str) else "TOTP synkroniseret fra CMDB"
    return HTMLResponse(_system_page(msg))


# ── Entrypoint ────────────────────────────────────────────────────────────────
def _sync_totp_from_headend() -> str:
    """Hent TOTP secret fra headend (via config-hierarki) og opdater bt-config.yaml.
    Kaldes KUN ved eksplicit brugerhandling — aldrig automatisk ved boot.
    Returnerer statusbesked til management-UI.
    """
    try:
        edge_cfg = _fetch_headend_config(load_config())
        if not edge_cfg:
            msg = "Ingen forbindelse til CMDB — device_id eller headend_url mangler"
            log.warning("TOTP sync: %s", msg)
            return msg
        bt_totp    = edge_cfg.get("bt_totp", {})
        new_secret = bt_totp.get("secret", "")
        new_sid    = bt_totp.get("sid", "")
        if not new_secret:
            return "CMDB returnerede intet TOTP-secret — ingen ændring"
        cfg = load_config()
        if cfg["totp"].get("secret") == new_secret and cfg["totp"].get("sid") == new_sid:
            return f"Allerede opdateret (sid={new_sid}) — ingen ændring nødvendig"
        cfg["totp"]["secret"] = new_secret
        cfg["totp"]["sid"] = new_sid
        save_config(cfg)
        log.info("TOTP sync: opdateret → sid=%s", new_sid)
        # Genstart totp-service så nyt secret træder i kraft (non-blocking)
        subprocess.Popen(
            ["sudo", "systemctl", "restart", "timelapse-totp.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return f"✓ TOTP opdateret til sid={new_sid} — service genstarter"
    except Exception as e:
        msg = f"Sync fejlede: {e}"
        log.warning("TOTP sync: %s", msg)
        return msg


if __name__ == "__main__":
    import uvicorn
    # TOTP synces IKKE automatisk ved boot — fabriksstandard forbliver under hele
    # installationen. Rotation sker KUN ved eksplicit handling:
    #   • Tekniker trykker "Synkroniser TOTP fra CMDB" i management-UI
    #   • Admin pusher via headend (fremtidig funktion)
    cfg = load_config()
    mgmt = cfg["management"]
    https_port = mgmt.get("https_port", 8443)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=https_port,
        ssl_keyfile=mgmt["key_file"],
        ssl_certfile=mgmt["cert_file"],
        log_level="info",
    )
