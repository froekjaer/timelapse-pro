"""Login health probe + telemetry (2026-10-11). See services/login_health.py."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from services import login_health as lh


# ── telemetry ──────────────────────────────────────────────────────────────────

def test_failed_touch_id_reports_are_counted_and_age_out():
    t = lh._Telemetry()
    t.record(lh._REPORT, 204, now=1000, report={"stage": "touch-id", "name": "Error"})
    t.record(lh._REPORT, 204, now=1001, report={"stage": "touch-id", "name": "NotAllowedError"})
    assert t.snapshot(now=1002)["passkey_failed_30m"] == 2
    assert t.last_failures() == ["Error", "NotAllowedError"]
    assert t.snapshot(now=1000 + lh.WINDOW_S + 5)["passkey_failed_30m"] == 0


def test_aborts_and_prefetch_reports_are_not_failed_attempts():
    # AbortError = page left / next click took over; prefetch = no attempt yet.
    t = lh._Telemetry()
    t.record(lh._REPORT, 204, now=1000, report={"stage": "touch-id", "name": "AbortError"})
    t.record(lh._REPORT, 204, now=1000, report={"stage": "prefetch", "name": "TypeError"})
    assert t.snapshot(now=1001)["passkey_failed_30m"] == 0


def test_completed_logins_and_server_errors_are_counted():
    t = lh._Telemetry()
    t.record(lh._COMPLETE, 200, now=1000)
    t.record(lh._BEGIN, 500, now=1000)
    snap = t.snapshot(now=1001)
    assert snap["passkey_complete_30m"] == 1 and snap["auth_5xx_30m"] == 1
    assert t.snapshot(now=1000 + lh.WINDOW_S + 1)["auth_5xx_30m"] == 0


def _run_middleware(app, path, headers=(), body=b""):
    sent = []

    async def receive():
        return {"type": "http.request", "body": body}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "path": path, "headers": list(headers), "client": ("10.0.0.1", 1)}
    try:
        asyncio.run(lh.LoginTelemetryMiddleware(app)(scope, receive, send))
    except RuntimeError:
        pass
    return sent


def test_middleware_counts_unhandled_exception_as_500(monkeypatch):
    t = lh._Telemetry()
    monkeypatch.setattr(lh, "TELEMETRY", t)

    async def crashing_app(scope, receive, send):
        raise RuntimeError("db error")

    _run_middleware(crashing_app, lh._BEGIN)
    assert t.snapshot()["auth_5xx_30m"] == 1


def test_middleware_ignores_probe_requests_and_other_paths(monkeypatch):
    t = lh._Telemetry()
    monkeypatch.setattr(lh, "TELEMETRY", t)

    async def failing_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 500, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    _run_middleware(failing_app, lh._BEGIN, headers=[(lh.PROBE_HEADER.encode(), b"1")])
    _run_middleware(failing_app, "/api/devices")
    assert t.snapshot()["auth_5xx_30m"] == 0
    _run_middleware(failing_app, lh._BEGIN)
    assert t.snapshot()["auth_5xx_30m"] == 1


def test_middleware_reads_the_login_page_error_report(monkeypatch):
    t = lh._Telemetry()
    monkeypatch.setattr(lh, "TELEMETRY", t)

    async def report_app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    _run_middleware(report_app, lh._REPORT, body=b'{"stage": "touch-id", "name": "Error", "message": "svarede ikke"}')
    _run_middleware(report_app, lh._REPORT, body=b"not json")
    assert t.snapshot()["passkey_failed_30m"] == 1


def test_nginx_log_path_follows_the_installer_or_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TIMELAPSE_NGINX_ACCESS_LOG", str(tmp_path / "x.log"))
    assert lh.nginx_access_log_path() == str(tmp_path / "x.log")
    monkeypatch.delenv("TIMELAPSE_NGINX_ACCESS_LOG")
    assert "/var/log/timelapse/nginx-access.log" in lh._NGINX_LOG_CANDIDATES   # deploy/install/install_headend.sh
    monkeypatch.setattr(lh, "_NGINX_LOG_CANDIDATES", (str(tmp_path / "missing.log"),))
    assert lh.nginx_access_log_path() is None and lh.nginx_auth_errors() is None


def test_nginx_log_counts_auth_5xx_and_429_but_not_probe_or_other_paths(tmp_path):
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 10, 11, 18, 30, tzinfo=timezone(timedelta(hours=2)))
    def line(minutes_ago, path, status, ua="Safari"):
        t = (now - timedelta(minutes=minutes_ago)).strftime("%d/%b/%Y:%H:%M:%S %z")
        return f'1.2.3.4 - - [{t}] "POST {path} HTTP/2.0" {status} 21 rt=0.1 "-" "{ua}"'
    log = tmp_path / "access.log"
    log.write_text("\n".join([
        line(1, "/api/auth/webauthn/login-begin", 500),
        line(2, "/api/auth/login", 503),
        line(3, "/api/auth/login", 429),
        line(4, "/api/auth/webauthn/login-begin", 200),
        line(5, "/api/devices", 500),
        line(6, "/api/auth/webauthn/login-begin", 500, ua="TimeLapse-login-probe"),
        line(45, "/api/auth/webauthn/login-begin", 500),
    ]) + "\n")
    assert lh.nginx_auth_errors(str(log), now=now.timestamp()) == 3
    assert lh.nginx_auth_errors(str(tmp_path / "missing.log")) is None

# ── end-to-end probe against a local HTTP server ────────────────────────────────

def _serve(begin_status=200, page=b'<div id="root"></div>', options=None):
    options = options or {"challenge": "abc", "userVerification": "required", "rpId": "localhost"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200 if self.path == "/login" else 404)
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            assert self.headers.get(lh.PROBE_HEADER) == "1"
            self.send_response(begin_status)
            self.end_headers()
            self.wfile.write(json.dumps(options).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.mark.parametrize("kwargs,expected", [
    ({}, None),
    ({"begin_status": 500}, "passkey_autofill_begin_500"),
    ({"page": b"nginx default page"}, "login_page"),
    ({"options": {"challenge": "abc", "userVerification": "preferred", "rpId": "x"}}, "passkey_autofill_options"),
])
def test_probe_detects_each_broken_step(kwargs, expected):
    server = _serve(**kwargs)
    try:
        result = lh.probe_login(f"http://localhost:{server.server_port}")
    finally:
        server.shutdown()
    assert result["failed_step"] == expected
    assert result["ok"] is (expected is None)
    assert result["metrics"]["up"] == (1.0 if expected is None else 0.0)


def test_probe_reports_unreachable_host():
    result = lh.probe_login("http://localhost:9", timeout=1)
    assert result["ok"] is False and result["metrics"]["up"] == 0.0


# ── ITIM wiring ────────────────────────────────────────────────────────────────

def test_itim_runs_login_probe_and_has_login_alert_rules():
    import itim
    import inspect
    assert "_probe_login" in inspect.getsource(itim.run_collection_cycle)
    names = {rule[0] for rule in itim._DEFAULT_RULES}
    assert {"Login: serverfejl", "Login: Touch ID fejler i browseren", "Login: passkey til forkert domæne",
            "Login: certifikat udløber"} <= names
    service_down = next(r for r in itim._DEFAULT_RULES if r[0] == "Service nede")
    assert service_down[1] == "service" and service_down[2] is None   # covers svc:login up==0


def test_itim_login_probe_warns_on_rp_mismatch(monkeypatch):
    import itim
    from database import Base, SessionLocal, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        monkeypatch.setattr(itim, "_setting", lambda _db, key, default="": "https://example.test")
        monkeypatch.setattr(lh, "probe_login", lambda url: {"ok": True, "failed_step": None, "metrics": {"up": 1.0}})
        monkeypatch.setattr(lh, "nginx_auth_errors", lambda *a, **k: 0)
        monkeypatch.setattr(lh, "TELEMETRY", lh._Telemetry())
        monkeypatch.setattr(lh, "passkey_rp_mismatch_users", lambda _db, rp: 2)
        itim._probe_login(db)
        db.commit()
        target = db.query(itim.ItimTarget).filter_by(target_key="svc:login").one()
        health = db.query(itim.ItimHealthStatus).filter_by(target_id=target.id).one()
        assert health.state == "warning" and "andet domæne" in health.summary
    finally:
        db.close()


def test_itim_login_probe_records_critical_health_on_failure(monkeypatch):
    import itim
    from database import Base, SessionLocal, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        monkeypatch.setattr(itim, "_setting", lambda _db, key, default="": "https://example.test")
        monkeypatch.setattr(lh, "probe_login", lambda url: {
            "ok": False, "failed_step": "passkey_autofill_begin_500", "metrics": {"up": 0.0, "latency_ms": 5.0}})
        itim._probe_login(db)
        db.commit()
        target = db.query(itim.ItimTarget).filter_by(target_key="svc:login").one()
        health = db.query(itim.ItimHealthStatus).filter_by(target_id=target.id).one()
        assert health.state == "critical" and "passkey_autofill_begin_500" in health.summary
        assert itim._latest_value(db, target.id, "up") == 0.0
    finally:
        db.close()


def test_browser_failure_rule_never_mails_but_server_rules_do():
    # Codex review: browser reports are unauthenticated, so they must not page.
    import itim
    assert "Login: Touch ID fejler i browseren" in itim._DEFAULT_RULES_NO_NOTIFY
    assert "Login: serverfejl" not in itim._DEFAULT_RULES_NO_NOTIFY


def test_effective_rp_ids_follow_the_webauthn_settings():
    settings = {"webauthn_allowed_origins": "https://backend.timelapse-pro.dk:8443,https://timelapse.froekjaer.dk"}
    get = lambda _db, key, default="": settings.get(key, default)
    assert lh.effective_rp_ids(None, get) == {"timelapse-pro.dk", "timelapse.froekjaer.dk"}
    settings.clear()
    settings.update({"base_url": "https://backend.example.com", "webauthn_rp_id": "example.com"})
    assert lh.effective_rp_ids(None, get) == {"example.com"}


def test_rp_mismatch_counts_users_with_only_foreign_passkeys():
    from database import Base, SessionLocal, User, WebAuthnCredential, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        names = ("rp-ok", "rp-foreign", "rp-legacy")
        db.query(User).filter(User.username.in_(names)).delete(synchronize_session=False)
        db.commit()
        users = {n: User(username=n, password_hash="x", role="viewer", is_active=True) for n in names}
        db.add_all(users.values())
        db.flush()
        for name, rp in (("rp-ok", "example.com"), ("rp-foreign", "old.example"), ("rp-legacy", None)):
            db.add(WebAuthnCredential(user_id=users[name].id, credential_id=name.encode(), public_key=b"k",
                                      sign_count=0, rp_id=rp))
        db.commit()
        # rp-foreign is the only one of the three that cannot log in under example.com;
        # adding its RP to the effective set removes exactly that one.
        with_foreign = lh.passkey_rp_mismatch_users(db, {"example.com", "old.example"})
        assert lh.passkey_rp_mismatch_users(db, {"example.com"}) == with_foreign + 1
    finally:
        db.query(WebAuthnCredential).filter(WebAuthnCredential.credential_id.in_([n.encode() for n in names])).delete(synchronize_session=False)
        db.query(User).filter(User.username.in_(names)).delete(synchronize_session=False)
        db.commit()
        db.close()
