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

    response = HTMLResponse(_success_page())
    response.set_cookie(
        SESSION_COOKIE, token,
        httponly=True, secure=True, samesite="strict",
        max_age=timeout if timeout > 0 else None
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


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
