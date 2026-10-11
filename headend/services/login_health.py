"""Login health: an end-to-end probe plus live login telemetry (2026-10-11).

Peter: "Det er den første oplevelse en bruger har, og det SKAL bare virke
ALTID!!!" — after passkey AutoFill had returned 500 for a day and a half
without anyone noticing (settings.key length, PR #300).

Two signals, both reported through ITIM (itim._probe_login), so the existing
alert rules, e-mail notification and ITIM dashboard apply:

1. probe_login(): every ITIM cycle, walk the same path a browser takes —
   TLS to the public login host (via local nginx, certificate verified),
   the login page itself, and the usernameless passkey start (which writes to
   Postgres). No username-bound call is made: that would replace a real
   user's pending challenge.
2. LoginTelemetryMiddleware: counts what real browsers experience — any 5xx
   from /api/auth/*, and passkey ceremonies the user explicitly started (the
   username + Touch ID button: login-begin with a username) that never
   completed (no login-complete 200 from the same client within
   ABANDON_AFTER_S). The usernameless AutoFill begin fires on every page
   load before the user picks anything, so it is not an attempt and is not
   counted. Probe requests are excluded. In memory only; no usernames or IP
   addresses leave this module (client key is a short hash).
3. nginx_auth_errors(): failures nginx itself returns (502/503/504, rate
   limiting) never reach the app or the middleware; they are read from the
   nginx access log so the 5xx alert covers what browsers actually saw.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse

PROBE_HEADER = "x-timelapse-login-probe"
WINDOW_S = 30 * 60
ABANDON_AFTER_S = 120
_BEGIN = "/api/auth/webauthn/login-begin"
_COMPLETE = "/api/auth/webauthn/login-complete"


# ── Telemetry ───────────────────────────────────────────────────────────────

class _Telemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.errors: deque[tuple[float, str, int]] = deque(maxlen=500)     # (ts, path, status)
        self.begins: dict[str, float] = {}                                   # client -> last begin ts
        self.completes: deque[float] = deque(maxlen=2000)
        self.abandoned: deque[float] = deque(maxlen=2000)
        self.begun: deque[float] = deque(maxlen=2000)

    def record(self, path: str, status: int, client: str, now: float | None = None,
               explicit_begin: bool = True) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._expire(now)
            if status >= 500:
                self.errors.append((now, path, status))
            if path == _BEGIN and explicit_begin and 200 <= status < 300:
                self.begun.append(now)
                self.begins[client] = now
            elif path == _COMPLETE and 200 <= status < 300:
                self.completes.append(now)
                self.begins.pop(client, None)

    def _expire(self, now: float) -> None:
        for client, started in list(self.begins.items()):
            if now - started > ABANDON_AFTER_S:
                self.abandoned.append(started)
                del self.begins[client]

    def snapshot(self, now: float | None = None) -> dict[str, float]:
        now = time.time() if now is None else now
        cutoff = now - WINDOW_S
        with self._lock:
            self._expire(now)
            return {
                "auth_5xx_30m": float(sum(1 for ts, _p, _s in self.errors if ts >= cutoff)),
                "passkey_begin_30m": float(sum(1 for ts in self.begun if ts >= cutoff)),
                "passkey_complete_30m": float(sum(1 for ts in self.completes if ts >= cutoff)),
                "passkey_abandoned_30m": float(sum(1 for ts in self.abandoned if ts >= cutoff)),
            }

    def last_errors(self, limit: int = 3) -> list[str]:
        with self._lock:
            return [f"{p} {s}" for _ts, p, s in list(self.errors)[-limit:]]


TELEMETRY = _Telemetry()


def _client_key(scope) -> str:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}
    ip = headers.get("x-real-ip") or headers.get("x-forwarded-for", "").split(",")[0].strip() \
        or (scope.get("client") or ("", 0))[0]
    raw = f"{ip}|{headers.get('user-agent', '')}"
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]


class LoginTelemetryMiddleware:
    """Pure ASGI: sees the real status, including unhandled exceptions (500)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "") if scope.get("type") == "http" else ""
        if not path.startswith("/api/auth/"):
            return await self.app(scope, receive, send)
        if any(k.lower() == PROBE_HEADER.encode() for k, _v in scope.get("headers") or []):
            return await self.app(scope, receive, send)
        status = {"code": 500}
        body = bytearray()

        async def receive_wrapper():
            message = await receive()
            if path == _BEGIN and message.get("type") == "http.request" and len(body) < 4096:
                body.extend(message.get("body", b"")[:4096])
            return message

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status["code"] = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        finally:
            try:
                TELEMETRY.record(path, status["code"], _client_key(scope),
                                 explicit_begin=_names_a_user(bytes(body)))
            except Exception:
                pass


def _names_a_user(body: bytes) -> bool:
    """login-begin with a username = the user pressed the Touch ID button."""
    try:
        return bool(str(json.loads(body or b"{}").get("username") or "").strip())
    except (ValueError, AttributeError):
        return False


# ── nginx-side failures ─────────────────────────────────────────────────────

NGINX_ACCESS_LOG = os.getenv("TIMELAPSE_NGINX_ACCESS_LOG", "/opt/homebrew/var/log/nginx-timelapse-access.log")
_NGINX_LINE = re.compile(r'\[(?P<t>[^\]]+)\] "(?P<m>[A-Z]+) (?P<p>\S+)[^"]*" (?P<s>\d{3})')


def nginx_auth_errors(log_path: str = NGINX_ACCESS_LOG, now: float | None = None,
                      window_s: int = WINDOW_S, tail_bytes: int = 4_000_000) -> int | None:
    """/api/auth requests answered 5xx or 429 by nginx or the app in the last
    window, excluding the probe. None when the log cannot be read."""
    now = time.time() if now is None else now
    try:
        with open(log_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - tail_bytes))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    count = 0
    for line in lines:
        if "/api/auth/" not in line or "TimeLapse-login-probe" in line:
            continue
        m = _NGINX_LINE.search(line)
        if not m or not m.group("p").startswith("/api/auth/"):
            continue
        status = int(m.group("s"))
        if status < 500 and status != 429:
            continue
        try:
            ts = datetime.strptime(m.group("t"), "%d/%b/%Y:%H:%M:%S %z").timestamp()
        except ValueError:
            continue
        if now - ts <= window_s:
            count += 1
    return count


# ── End-to-end probe ────────────────────────────────────────────────────────

class _LocalHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to the public host name (SNI + certificate check), but dialled
    on the local nginx — the probe must not depend on outside DNS/routing."""

    def __init__(self, host: str, port: int, dial: str, **kw) -> None:
        super().__init__(host, port, **kw)
        self._dial = dial

    def connect(self) -> None:
        sock = socket.create_connection((self._dial, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _request(conn_factory, method: str, path: str, body: dict | None = None, origin: str = "") -> tuple[int, bytes]:
    conn = conn_factory()
    try:
        headers = {PROBE_HEADER: "1", "User-Agent": "TimeLapse-login-probe"}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            headers.update({"Content-Type": "application/json", "Origin": origin})
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read(200_000)
    finally:
        conn.close()


def probe_login(base_url: str, dial: str = "127.0.0.1", timeout: float = 5.0,
                context: ssl.SSLContext | None = None) -> dict:
    """Return {"ok": bool, "failed_step": str|None, "metrics": {...}}."""
    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    origin = f"{parsed.scheme}://{parsed.netloc}"
    metrics: dict[str, float] = {}
    started = time.monotonic()

    def fail(step: str) -> dict:
        metrics["up"] = 0.0
        metrics["latency_ms"] = (time.monotonic() - started) * 1000.0
        return {"ok": False, "failed_step": step, "metrics": metrics}

    if parsed.scheme == "https":
        ctx = context or ssl.create_default_context()
        port = parsed.port or 443
        factory = lambda: _LocalHTTPSConnection(host, port, dial, timeout=timeout, context=ctx)  # noqa: E731
        try:
            conn = factory()
            conn.connect()
            cert = conn.sock.getpeercert()
            conn.close()
            not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            metrics["cert_days_left"] = round((not_after - datetime.now(timezone.utc)).total_seconds() / 86400, 1)
        except (ssl.SSLError, ssl.CertificateError):
            return fail("tls_certificate")
        except Exception:
            return fail("tls_connect")
    else:
        port = parsed.port or 80
        factory = lambda: http.client.HTTPConnection(dial, port, timeout=timeout)  # noqa: E731

    try:
        status, body = _request(factory, "GET", "/login")
        if status != 200 or b'id="root"' not in body:
            return fail("login_page")
        status, body = _request(factory, "POST", _BEGIN, {}, origin)
        if status != 200:
            return fail(f"passkey_autofill_begin_{status}")
        options = json.loads(body)
        if not options.get("challenge") or options.get("userVerification") != "required" or not options.get("rpId"):
            return fail("passkey_autofill_options")
    except Exception:
        return fail("login_request")
    metrics["up"] = 1.0
    metrics["latency_ms"] = (time.monotonic() - started) * 1000.0
    return {"ok": True, "failed_step": None, "metrics": metrics}


def passkey_rp_mismatch_users(db, rp_id: str) -> int:
    """Active users whose passkeys are all bound to another RP ID — they can
    only log in with a password here (the 2026-10-03 Safari cause)."""
    from database import User, WebAuthnCredential

    count = 0
    for user in db.query(User).filter(User.is_active.is_(True)).all():
        creds = db.query(WebAuthnCredential).filter_by(user_id=user.id).all()
        if creds and not any((c.rp_id or rp_id) == rp_id for c in creds):
            count += 1
    return count
