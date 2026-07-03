#!/usr/bin/env python3
"""
TimeLapse Pro — Local Management TOTP captive portal
Kører på br-bt (192.168.42.1:8443 HTTPS + 8080 HTTP→redirect)

Flow:
  1. Telefon forbinder til BT PAN → får IP 192.168.42.x
  2. iptables blokerer alt undtagen port 8080/8443
  3. Browser åbner → redirect til HTTPS TOTP-login
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
import yaml
import pyotp

from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
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


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


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
    import urllib.request, json as _json
    device_id = cfg.get("device", {}).get("device_id", "")
    headend = cfg.get("management", {}).get("headend_url", "")
    if not device_id or not headend:
        return {}
    try:
        url = f"{headend}/api/config/{device_id}"
        with urllib.request.urlopen(url, timeout=4) as r:
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
  <a href="/mgmt/technician" class="{'active' if section == 'technician' else ''}">Tekniker</a>
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


def _run_tech_cli(*args: str, timeout: int = 45) -> tuple[bool, str]:
    """Run the shared edge technician CLI and return safe text output."""
    if not TECH_CLI.exists():
        return False, f"Tekniker CLI findes ikke: {TECH_CLI}"
    cmd = [os.environ.get("PYTHON", "/opt/timelapse/venv/bin/python3"), str(TECH_CLI), *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
        return result.returncode == 0, output.strip() or "(intet output)"
    except Exception as exc:
        return False, str(exc)


def _technician_snapshot() -> dict:
    """Use bootstrap_cli's shared status collector when available."""
    try:
        import sys
        tools_dir = str(EDGE_ROOT / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import bootstrap_cli
        return bootstrap_cli.collect_local_status(EDGE_ROOT)
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


def _technician_page(msg: str = "", output: str = "") -> str:
    status = _technician_snapshot()
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
<meta http-equiv="refresh" content="45">
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
  button, input {{ border-radius: 7px; border: 1px solid #334; padding: 0.62rem 0.7rem; font-size: 0.85rem; }}
  button {{ background: #4fc3f7; color: #001018; font-weight: 700; cursor: pointer; }}
  button.secondary {{ background: #26385a; color: #dbeafe; border-color: #3b5279; }}
  input {{ width: 100%; background: #0f3460; color: #fff; margin-bottom: 0.5rem; }}
  form.inline {{ margin: 0; }}
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
  <a href="/mgmt/technician" class="active">Tekniker</a>
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
      <div class="actions">
        <form class="inline" method="post" action="/mgmt/technician/action"><input type="hidden" name="action" value="doctor"><button>Doctor</button></form>
        <form class="inline" method="post" action="/mgmt/technician/action"><input type="hidden" name="action" value="camera-summary"><button>Kamera status</button></form>
        <form class="inline" method="post" action="/mgmt/technician/action"><input type="hidden" name="action" value="gps"><button>GPS status</button></form>
        <form class="inline" method="post" action="/mgmt/technician/action"><input type="hidden" name="action" value="npu"><button>NPU status</button></form>
        <form class="inline" method="post" action="/mgmt/technician/action"><input type="hidden" name="action" value="logs"><button>Service logs</button></form>
        <form class="inline" method="post" action="/mgmt/technician/action"><input type="hidden" name="action" value="headend"><button>Headend test</button></form>
      </div>
    </div>
    <div class="card">
      <h2>Fokus</h2>
      <form method="post" action="/mgmt/technician/focus">
        <input name="value" placeholder="Focus drive, fx Near 1, Far 1 eller 500">
        <button>Koer focus drive</button>
      </form>
      <form method="post" action="/mgmt/technician/action" style="margin-top:0.5rem">
        <input type="hidden" name="action" value="autofocus">
        <button class="secondary">Autofokus</button>
      </form>
    </div>
    <div class="card">
      <h2>Kamera config</h2>
      <form method="post" action="/mgmt/technician/config">
        <input name="path" placeholder="/main/capturesettings/exposurecompensation">
        <input name="value" placeholder="Ny vaerdi">
        <button>Saet config</button>
      </form>
    </div>
    <div class="card">
      <h2>Testbillede</h2>
      <form method="post" action="/mgmt/technician/capture">
        <input name="out_dir" value="/tmp/timelapse-tech-captures">
        <button>Tag testbillede + QA</button>
      </form>
    </div>
    {output_html}
  </div>
</div>
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


@app.post("/mgmt/technician/action", response_class=HTMLResponse)
async def mgmt_technician_action(request: Request, action: str = Form(...)):
    mapping = {
        "doctor": ["--doctor"],
        "camera-summary": ["--camera-summary"],
        "gps": ["--gps-status"],
        "npu": ["--npu-status"],
        "logs": [],
        "headend": ["--test-headend"],
        "autofocus": ["--autofocus"],
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
async def mgmt_technician_focus(request: Request, value: str = Form(...)):
    ok, output = _run_tech_cli("--focus-drive", value, timeout=30)
    return HTMLResponse(_technician_page("Focus drive sendt" if ok else "Focus drive fejlede", output))


@app.post("/mgmt/technician/config", response_class=HTMLResponse)
async def mgmt_technician_config(request: Request, path: str = Form(...), value: str = Form(...)):
    ok, output = _run_tech_cli("--set-camera-config", path, value, timeout=30)
    return HTMLResponse(_technician_page("Kamera config sat" if ok else "Kamera config fejlede", output))


@app.post("/mgmt/technician/capture", response_class=HTMLResponse)
async def mgmt_technician_capture(request: Request, out_dir: str = Form("/tmp/timelapse-tech-captures")):
    ok, output = _run_tech_cli("--capture-test", out_dir, timeout=120)
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

    import tempfile, shutil
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    shutil.move(tmp, CONFIG_FILE)
    log.info(f"Tidskonfiguration gemt af {request.client.host}")

    hcfg = _fetch_headend_config(cfg)
    return HTMLResponse(_mgmt_page("time", hcfg, _get_time_status(), msg="✓ Gemt"))


@app.get("/mgmt/system", response_class=HTMLResponse)
async def mgmt_system(request: Request):
    import subprocess
    uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True).stdout.strip()
    cfg = load_config()
    hcfg = _fetch_headend_config(cfg)
    # Simpel system-side — udvides i næste iteration
    return HTMLResponse(_mgmt_page("system", hcfg, _get_time_status()) + f"""
<script>
// Indsæt uptime i DOM — midlertidig løsning
document.querySelector('.content').insertAdjacentHTML('afterbegin',
  '<div class="card"><h2>System</h2><div class="meta">Uptime: {uptime}</div></div>');
</script>""")


@app.post("/mgmt/totp-sync", response_class=HTMLResponse)
async def mgmt_totp_sync(request: Request):
    """Eksplicit TOTP-sync fra headend — kræver aktiv netværksforbindelse.
    Opdaterer bt-config.yaml og genstarter totp-service hvis secret er ændret.
    """
    if not _valid_token(request.cookies.get(SESSION_COOKIE, ""), request.client.host):
        return RedirectResponse("/", status_code=303)
    result = _sync_totp_from_headend()
    msg = result if isinstance(result, str) else "TOTP synkroniseret fra CMDB"
    hcfg = _fetch_headend_config(load_config())
    return HTMLResponse(_mgmt_page("system", hcfg, _get_time_status(), msg))


# ── HTTP → HTTPS redirect (simpel http.server, port 80 + 8080) ───────────────
from http.server import HTTPServer, BaseHTTPRequestHandler

class _RedirectHandler(BaseHTTPRequestHandler):
    https_port = 8443

    def do_GET(self):
        host = self.headers.get("Host", self.server.server_address[0]).split(":")[0]
        location = f"https://{host}:{self.https_port}{self.path}"
        self.send_response(301)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = do_GET
    do_HEAD = do_GET

    def log_message(self, fmt, *args):
        log.info(f"[http-redirect] {fmt % args}")


# ── Entrypoint ────────────────────────────────────────────────────────────────
def _sync_totp_from_headend() -> str:
    """Hent TOTP secret fra headend (via config-hierarki) og opdater bt-config.yaml.
    Kaldes KUN ved eksplicit brugerhandling — aldrig automatisk ved boot.
    Returnerer statusbesked til management-UI.
    """
    import urllib.request, json as _json, re as _re
    try:
        device_id   = os.environ.get("DEVICE_ID", "")
        headend_url = os.environ.get("HEADEND_URL", "")
        main_cfg_path = "/etc/timelapse/config.yaml"
        if os.path.exists(main_cfg_path):
            try:
                with open(main_cfg_path) as _f:
                    _mcfg = yaml.safe_load(_f) or {}
                device_id   = device_id   or _mcfg.get("device_id", "")
                headend_url = headend_url or _mcfg.get("headend_url", "")
            except Exception:
                pass
        if not device_id or not headend_url:
            msg = "Ingen forbindelse til CMDB — device_id eller headend_url mangler"
            log.warning("TOTP sync: %s", msg)
            return msg
        url = f"{headend_url}/api/config/{device_id}"
        with urllib.request.urlopen(url, timeout=5) as r:
            hcfg = _json.loads(r.read())
        bt_totp    = hcfg.get("bt_totp", {})
        new_secret = bt_totp.get("secret", "")
        new_sid    = bt_totp.get("sid", "")
        if not new_secret:
            return "CMDB returnerede intet TOTP-secret — ingen ændring"
        cfg = load_config()
        if cfg["totp"].get("secret") == new_secret and cfg["totp"].get("sid") == new_sid:
            return f"Allerede opdateret (sid={new_sid}) — ingen ændring nødvendig"
        # Opdater bt-config.yaml in-place (bevarer kommentarer)
        with open(CONFIG_FILE) as f:
            raw = f.read()
        raw = _re.sub(r'(secret:\s*")[^"]*(")', f'\\g<1>{new_secret}\\2', raw)
        raw = _re.sub(r'(sid:\s*")[^"]*(")', f'\\g<1>{new_sid}\\2', raw)
        with open(CONFIG_FILE, "w") as f:
            f.write(raw)
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
    import threading
    import uvicorn
    # TOTP synces IKKE automatisk ved boot — fabriksstandard forbliver under hele
    # installationen. Rotation sker KUN ved eksplicit handling:
    #   • Tekniker trykker "Synkroniser TOTP fra CMDB" i management-UI
    #   • Admin pusher via headend (fremtidig funktion)
    cfg = load_config()
    mgmt = cfg["management"]
    https_port = mgmt.get("https_port", 8443)
    http_port = 8080  # HTTP redirect port (iptables sender port 80 hertil)

    _RedirectHandler.https_port = https_port

    def run_http_redirect(port):
        srv = HTTPServer(("0.0.0.0", port), _RedirectHandler)
        log.info(f"HTTP redirect server lytter på port {port} → HTTPS:{https_port}")
        srv.serve_forever()

    # Port 80 håndteres af iptables NAT redirect → port 8080
    t = threading.Thread(target=run_http_redirect, args=(http_port,), daemon=True)
    t.start()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=https_port,
        ssl_keyfile=mgmt["key_file"],
        ssl_certfile=mgmt["cert_file"],
        log_level="info",
    )
