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
import hashlib
import logging
import ipaddress
import subprocess
import yaml
import pyotp

from datetime import datetime
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
  p {{ font-size: 0.85rem; color: #aaa; margin: 0 0 1.5rem; }}
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
</div>
</body>
</html>"""


@app.get("/mgmt/", response_class=HTMLResponse)
@app.get("/mgmt", response_class=HTMLResponse)
async def mgmt_index(request: Request):
    cfg = load_config()
    hcfg = _fetch_headend_config(cfg)
    return HTMLResponse(_mgmt_page("time", hcfg, _get_time_status()))


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
if __name__ == "__main__":
    import threading
    import uvicorn
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
