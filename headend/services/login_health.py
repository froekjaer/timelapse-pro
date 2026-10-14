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
   from /api/auth/*, completed passkey logins, and failed Touch ID attempts
   as reported by the login page itself (#303: client-report with
   stage=touch-id — refused by the browser, cancelled, or the page's 75 s
   deadline). Since #302 the Touch ID click sends no login-begin (the
   challenge is prefetched), so the browser's own report is the only signal
   of a failed attempt. Probe requests are excluded. In memory only.
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
_COMPLETE = "/api/auth/webauthn/login-complete"
_REPORT = "/api/auth/webauthn/client-report"    # login page → browser-side errors (#303)
_BEGIN = "/api/auth/webauthn/login-begin"


# ── Telemetry ───────────────────────────────────────────────────────────────

class _Telemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.errors: deque[tuple[float, str, int]] = deque(maxlen=500)     # (ts, path, status)
        self.completes: deque[float] = deque(maxlen=2000)
        self.failures: deque[tuple[float, str]] = deque(maxlen=500)         # (ts, error name)

    def record(self, path: str, status: int, now: float | None = None, report: dict | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            if status >= 500:
                self.errors.append((now, path, status))
            if path == _COMPLETE and 200 <= status < 300:
                self.completes.append(now)
            elif path == _REPORT and report and report.get("stage") == "touch-id" \
                    and report.get("name") != "AbortError":
                # A Touch ID attempt the browser refused, the user cancelled, or
                # that hit the page's 75 s deadline — the login page reports it.
                self.failures.append((now, str(report.get("name") or "?")[:60]))

    def snapshot(self, now: float | None = None) -> dict[str, float]:
        now = time.time() if now is None else now
        cutoff = now - WINDOW_S
        with self._lock:
            return {
                "auth_5xx_30m": float(sum(1 for ts, _p, _s in self.errors if ts >= cutoff)),
                "passkey_complete_30m": float(sum(1 for ts in self.completes if ts >= cutoff)),
                "passkey_failed_30m": float(sum(1 for ts, _n in self.failures if ts >= cutoff)),
            }

    def last_errors(self, limit: int = 3) -> list[str]:
        with self._lock:
            return [f"{p} {s}" for _ts, p, s in list(self.errors)[-limit:]]

    def last_failures(self, limit: int = 3) -> list[str]:
        with self._lock:
            return [name for _ts, name in list(self.failures)[-limit:]]


TELEMETRY = _Telemetry()


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
            if path == _REPORT and message.get("type") == "http.request" and len(body) < 4096:
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
                TELEMETRY.record(path, status["code"], report=_report(bytes(body)) if path == _REPORT else None)
            except Exception:
                pass


def _report(body: bytes) -> dict | None:
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


# ── nginx-side failures ─────────────────────────────────────────────────────

# Known locations: deploy/install/install_headend.sh writes
# /var/log/timelapse/nginx-access.log; the current Mac mini uses the Homebrew
# path. TIMELAPSE_NGINX_ACCESS_LOG overrides both.
_NGINX_LOG_CANDIDATES = ("/var/log/timelapse/nginx-access.log", "/opt/homebrew/var/log/nginx-timelapse-access.log")


def nginx_access_log_path() -> str | None:
    configured = os.getenv("TIMELAPSE_NGINX_ACCESS_LOG", "").strip()
    if configured:
        return configured
    return next((p for p in _NGINX_LOG_CANDIDATES if os.path.isfile(p)), None)
_NGINX_LINE = re.compile(r'\[(?P<t>[^\]]+)\] "(?P<m>[A-Z]+) (?P<p>\S+)[^"]*" (?P<s>\d{3})')


def nginx_auth_errors(log_path: str | None = None, now: float | None = None,
                      window_s: int = WINDOW_S, tail_bytes: int = 4_000_000) -> int | None:
    """/api/auth requests answered 5xx or 429 by nginx or the app in the last
    window, excluding the probe. None when the log cannot be read."""
    now = time.time() if now is None else now
    log_path = log_path or nginx_access_log_path()
    if not log_path:
        return None
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


def effective_rp_ids(db, get_setting) -> set[str]:
    """The RP IDs users actually authenticate against — the same resolution as
    the WebAuthn endpoints (services.webauthn_origin): one per allowed origin
    when an allow-list is configured, otherwise the configured/derived RP."""
    from services.webauthn_origin import _csv_settings, _default_rp_id_for_origin, resolve_webauthn_settings

    allowed = _csv_settings(get_setting(db, "webauthn_allowed_origins", os.environ.get("WEBAUTHN_ALLOWED_ORIGINS", "")))
    if allowed:
        return {_default_rp_id_for_origin(origin) for origin in allowed}
    return {resolve_webauthn_settings(db, None, get_setting)[0]}


def passkey_rp_mismatch_users(db, rp_ids: set[str]) -> int:
    """Active users whose passkeys are all bound to an RP ID outside the
    effective set — they can only log in with a password here (the
    2026-10-03 Safari cause). Legacy rows without rp_id count as usable."""
    from database import User, WebAuthnCredential

    count = 0
    for user in db.query(User).filter(User.is_active.is_(True)).all():
        creds = db.query(WebAuthnCredential).filter_by(user_id=user.id).all()
        if creds and not any(c.rp_id is None or c.rp_id in rp_ids for c in creds):
            count += 1
    return count
