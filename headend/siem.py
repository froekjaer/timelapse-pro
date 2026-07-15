# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — siem.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Mini-SIEM API.
Montér i main.py:
    from siem import router as siem_router
    app.include_router(siem_router, prefix="/api/siem")

Endpoints:
    POST /api/siem/events/{device_id}   → node agent poster events
    GET  /api/siem/events               → alle events (filtreret)
    GET  /api/siem/summary              → tæller pr. type/severity/enhed
    GET  /api/siem/threats              → brute force detektion (top IPs)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque

# ── Notifikations-cooldown (undgår alert storm) ───────────────────────────────
# Nøgle: (device_id, event_type) → timestamp for sidst sendte notifikation
_notify_cooldown: dict[tuple, float] = {}
_notify_cooldown_lock = threading.Lock()
NOTIFY_COOLDOWN_SECONDS = 300  # maks 1 email per type per enhed per 5 min
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import Column, DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Session

from database import Base, Device, get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["SIEM"])
_COLLECTOR_STARTED = False
_API_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


# ── Auth-broer (2026-07-03 hærdning) ──────────────────────────────────────────
# SIEM-routeren havde tidligere INGEN autentificering på nogen endpoints — hverken
# på de menneskevendte GET-endpoints (events/summary/threats, som eksponerer
# source-IP'er, brugernavne og brute-force-data) eller på det maskinvendte
# POST-ingest-endpoint (som accepterede events for et vilkårligt device_id uden
# nogen form for token-tjek). Se Claude_Kritisk_Statusgennemgang_2026-07-03.md §2.1.
#
# Lazy import af main (samme mønster som cmdb.py::_require_cmdb_role) for at
# undgå cirkulær import ved modul-indlæsning.

def _require_siem_role(*roles: str):
    """RBAC-bro til denne router — inkl. MFA-håndhævelse (modsat cmdb.py/itim.py's
    bro, som IKKE tjekker MFA, jf. §2.2 i statusgennemgangen)."""
    def _check(request: Request, db: Session = Depends(get_db)):
        from main import (
            _ROLE_HIERARCHY,
            _mfa_required_for_user,
            _session_is_mfa_verified,
            _session_payload,
            get_current_user,
        )

        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
        return user

    return Depends(_check)


def _visible_event_query(db: Session, user):
    """Apply the same device/tenant boundary used by CMDB."""
    from main import _is_platform_admin, _visible_device_query

    q = db.query(SecurityEvent)
    if _is_platform_admin(user):
        return q
    device_ids = [row[0] for row in _visible_device_query(db, user)
                  .with_entities(Device.device_id).all()]
    return q.filter(SecurityEvent.device_id.in_(device_ids)) if device_ids else q.filter(False)


async def _require_device_auth(
    device_id: str,
    request: Request,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    """Genbruger samme device-Bearer-token-verifikation som alle andre
    edge-vendte endpoints (main._verify_device_token) — samme HMAC/attestation-
    kæde, ingen ny, separat tillidsmodel for SIEM-ingest."""
    from main import _verify_device_token

    await _verify_device_token(device_id=device_id, request=request, authorization=authorization, db=db)


# ── Model ─────────────────────────────────────────────────────────────────

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id          = Column(Integer, primary_key=True)
    device_id   = Column(String(50),  nullable=False, index=True)
    event_type  = Column(String(50),  nullable=False)
    severity    = Column(String(20),  nullable=False, default="info")
    username    = Column(String(100))
    source_ip   = Column(String(45))
    raw_message = Column(Text)
    source      = Column(String(50))
    category    = Column(String(80))
    logger      = Column(String(160))
    process     = Column(String(160))
    normalized  = Column(Text)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc))
    dedup_hash  = Column(String(64), unique=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


_SCHEMA_READY = False


def _ensure_schema(db: Session) -> None:
    """Best-effort additive migration for SIEM enrichment columns."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    # Postgres-only (sqlite bruges ikke i TimeLapse Pro — død gren fjernet).
    for column, ddl in [
        ("source",     "ALTER TABLE security_events ADD COLUMN source VARCHAR(50)"),
        ("category",   "ALTER TABLE security_events ADD COLUMN category VARCHAR(80)"),
        ("logger",     "ALTER TABLE security_events ADD COLUMN logger VARCHAR(160)"),
        ("process",    "ALTER TABLE security_events ADD COLUMN process VARCHAR(160)"),
        ("normalized", "ALTER TABLE security_events ADD COLUMN normalized TEXT"),
    ]:
        exists = db.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='security_events' AND column_name=:column
        """), {"column": column}).fetchone()
        if not exists:
            db.execute(text(ddl))
    db.commit()
    _SCHEMA_READY = True


def _dedup_hash(device_id: str, event_type: str,
                occurred_at: str, source_ip: str = "", raw_message: str = "") -> str:
    """Hash til deduplicering uden at kollidere støj-events fra samme sekund."""
    raw_short = hashlib.sha256((raw_message or "").encode()).hexdigest()[:16]
    raw = f"{device_id}:{event_type}:{occurred_at[:19]}:{source_ip}:{raw_short}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _parse_dt(s: str) -> datetime:
    """Parser ISO8601 timestamp → aware datetime."""
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return _now()


def _redact_message(raw: str) -> str:
    """Fjern oplagte hemmeligheder før loglinjer gemmes i SIEM."""
    msg = raw or ""
    patterns = [
        (r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/\-]+=*", r"\1[REDACTED]"),
        (r"(?i)(password\s*[=:]\s*)\S+", r"\1[REDACTED]"),
        (r"(?i)(token\s*[=:]\s*)\S+", r"\1[REDACTED]"),
        (r"(?i)(api[_-]?key\s*[=:]\s*)\S+", r"\1[REDACTED]"),
        (r"(?i)(jwt_secret\s*[=:]\s*)\S+", r"\1[REDACTED]"),
    ]
    for pattern, repl in patterns:
        msg = re.sub(pattern, repl, msg)
    return msg


def _normalize_event(ev: dict) -> dict:
    raw = _redact_message(ev.get("raw_message") or ev.get("message") or "")[:2000]
    severity = str(ev.get("severity", "info")).lower()
    event_type = str(ev.get("event_type", "unknown")).lower()
    logger_name = str(ev.get("logger") or "")

    if event_type == "log":
        lowered = raw.lower()
        if "camera not found" in lowered or "no camera found" in lowered:
            event_type = "camera_detection_failed"
            severity = max_severity(severity, "error")
        elif "remote port forwarding failed" in lowered:
            event_type = "ssh_tunnel_remote_port_busy"
            severity = max_severity(severity, "error")
        elif "connect fejlede" in lowered and "ssh tunnel" in lowered:
            event_type = "ssh_tunnel_connect_failed"
            severity = max_severity(severity, "warning")
        elif "config drift" in lowered:
            event_type = "camera_config_drift"
            severity = max_severity(severity, "warning")
        elif "traceback" in lowered or "exception" in lowered:
            event_type = "application_exception"
            severity = max_severity(severity, "error")
        elif logger_name:
            event_type = f"log_{logger_name.split('.')[0]}".lower()

    category = ev.get("category")
    if event_type.startswith("ssh_tunnel"):
        category = "connectivity"
    elif event_type.startswith("camera"):
        category = "camera"
    elif event_type == "application_exception":
        category = "application"
    elif not category:
        category = "application" if event_type.startswith("log_") else "security"

    return {
        "event_type": event_type,
        "severity": severity,
        "category": category,
        "raw_message": raw,
        "normalized": {
            "source": ev.get("source"),
            "logger": logger_name or None,
            "process": ev.get("process"),
            "original_event_type": ev.get("event_type"),
            "syslog": ev.get("syslog"),
        },
    }


def max_severity(a: str, b: str) -> str:
    order = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
    return a if order.get(a.lower(), 0) >= order.get(b.lower(), 0) else b


def record_events(db: Session, device_id: str, events: list[dict]) -> dict:
    """Gem SIEM-events med normalisering og dedup. Bruges af API og lokale collectors."""
    _ensure_schema(db)
    inserted = 0
    duplicates = 0

    for ev in events:
        try:
            norm = _normalize_event(ev)
            occurred = _parse_dt(ev.get("occurred_at", _now().isoformat()))
            h = _dedup_hash(
                device_id,
                norm["event_type"],
                occurred.isoformat(),
                ev.get("source_ip", ""),
                norm["raw_message"],
            )

            row = SecurityEvent(
                device_id   = device_id,
                event_type  = norm["event_type"],
                severity    = norm["severity"],
                username    = ev.get("username"),
                source_ip   = ev.get("source_ip"),
                raw_message = norm["raw_message"][:2000],
                source      = ev.get("source"),
                category    = norm["category"],
                logger      = ev.get("logger"),
                process     = ev.get("process"),
                normalized  = json.dumps(norm["normalized"], ensure_ascii=False),
                occurred_at = occurred,
                dedup_hash  = h,
            )
            try:
                db.add(row)
                db.flush()
                inserted += 1
            except Exception:
                db.rollback()
                duplicates += 1
                continue

        except Exception as e:
            log.warning("Event-ingest fejl: %s — %s", e, ev)

    if inserted:
        db.commit()
        log.info("SIEM: %d events fra %s (%d duplikater ignoreret)",
                 inserted, device_id, duplicates)
    return {"inserted": inserted, "duplicates": duplicates}


def prune_old_events(db: Session) -> int:
    """Opt-in retention på security_events. DEFAULT SLÅET FRA
    (TIMELAPSE_SIEM_RETENTION_DAYS=0 → ingen sletning). Sættes >0 for at begrænse
    ubegrænset vækst. Additiv + flag-styret, så den ikke rører data før den bevidst
    aktiveres (jf. aftalt forløb: ingen destruktive ændringer før ITIM live-verificeret)."""
    try:
        days = int(os.getenv("TIMELAPSE_SIEM_RETENTION_DAYS", "0"))
    except ValueError:
        days = 0
    if days <= 0:
        return 0
    cutoff = _now() - timedelta(days=days)
    res = db.execute(text("DELETE FROM security_events WHERE occurred_at < :c"), {"c": cutoff})
    db.commit()
    deleted = res.rowcount or 0
    if deleted:
        log.info("SIEM retention: %d events ældre end %d dage slettet", deleted, days)
    return deleted


def _severity_rank(level: str) -> int:
    return {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}.get(str(level).lower(), 1)


def _check_api_rate_limit(device_id: str, event_count: int) -> None:
    """Server-side SIEM API guard. Edge may buffer, Headend still enforces limits."""
    max_batch = int(os.getenv("TIMELAPSE_SIEM_API_MAX_BATCH", "500"))
    max_events_per_minute = int(os.getenv("TIMELAPSE_SIEM_API_MAX_EVENTS_PER_DEVICE_PER_MINUTE", "2000"))
    if event_count > max_batch:
        from fastapi import HTTPException
        raise HTTPException(status_code=413, detail=f"SIEM batch too large: {event_count}>{max_batch}")

    now = time.monotonic()
    bucket = _API_RATE_BUCKETS[device_id]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) + event_count > max_events_per_minute:
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail="SIEM rate limit exceeded")
    bucket.extend([now] * event_count)


def _line_to_headend_event(source: str, line: str, min_severity: str) -> Optional[dict]:
    raw = line.strip()
    if not raw or "SIEM:" in raw or "/api/siem/" in raw:
        return None

    severity = "info"
    logger_name = None
    message = raw
    occurred = _now()

    pylog = re.match(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([A-Z]+)\s+([^\s]+)\s+(.*)$",
        raw,
    )
    if pylog:
        try:
            local_tz = datetime.now().astimezone().tzinfo
            occurred = (
                datetime.strptime(pylog.group(1), "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=local_tz)
                .astimezone(timezone.utc)
            )
        except Exception:
            occurred = _now()
        severity = pylog.group(2).lower()
        if severity == "warn":
            severity = "warning"
        logger_name = pylog.group(3)
        message = pylog.group(4)
    elif "nginx" in source:
        if re.search(r"\s5\d\d\s", raw):
            severity = "error"
        elif re.search(r"\s4\d\d\s", raw):
            severity = "warning"
        else:
            severity = "info"
        logger_name = "nginx"

    lowered = message.lower()
    if "traceback" in lowered or "exception" in lowered:
        severity = max_severity(severity, "error")
    if "permission denied" in lowered or "unauthorized" in lowered:
        severity = max_severity(severity, "warning")

    if _severity_rank(severity) < _severity_rank(min_severity):
        return None

    return {
        "event_type": "log",
        "severity": severity,
        "category": "headend_log",
        "source": source,
        "logger": logger_name,
        "process": "headend",
        "raw_message": message,
        "occurred_at": occurred.isoformat(),
    }


def start_headend_log_collector() -> None:
    """Start letvægtscollector for headend/nginx logs på lab-headend."""
    global _COLLECTOR_STARTED
    if _COLLECTOR_STARTED:
        return
    if os.getenv("TIMELAPSE_SIEM_HEADEND_ENABLED", "true").lower() not in ("1", "true", "yes", "on"):
        return
    _COLLECTOR_STARTED = True

    mode = os.getenv("TIMELAPSE_ENV", "lab").lower()
    min_severity = os.getenv(
        "TIMELAPSE_SIEM_HEADEND_MIN_SEVERITY",
        "info" if mode in ("lab", "rd") else "warning",
    ).lower()
    interval_s = int(os.getenv("TIMELAPSE_SIEM_HEADEND_INTERVAL_S", "30"))
    max_lines = int(os.getenv("TIMELAPSE_SIEM_HEADEND_MAX_LINES", "200"))
    state_path = Path(os.getenv("TIMELAPSE_SIEM_HEADEND_STATE", "/private/tmp/timelapse-siem-headend-state.json"))
    sources = [
        Path(p) for p in os.getenv(
            "TIMELAPSE_SIEM_HEADEND_LOGS",
            "/var/log/timelapse-headend.log,/opt/homebrew/var/log/nginx-timelapse-error.log,/opt/homebrew/var/log/nginx-timelapse-access.log",
        ).split(",")
        if p.strip()
    ]

    def load_state() -> dict:
        try:
            return json.loads(state_path.read_text())
        except Exception:
            return {}

    def save_state(state: dict) -> None:
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state))
        except Exception as exc:
            log.debug("SIEM collector state write failed: %s", exc)

    def read_new_lines(path: Path, state: dict) -> tuple[list[str], dict]:
        key = str(path)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return [], state
        previous = state.get(key, {})
        inode_changed = previous.get("inode") != stat.st_ino
        offset = 0 if inode_changed else int(previous.get("offset", 0))
        if offset > stat.st_size:
            offset = 0

        with path.open("r", encoding="utf-8", errors="replace") as fh:
            if offset == 0 and stat.st_size > 0:
                # Første kørsel tager kun halen, så vi ikke importerer hele historikken.
                fh.seek(0, os.SEEK_END)
                end = fh.tell()
                fh.seek(max(0, end - 128_000))
            else:
                fh.seek(offset)
            lines = fh.readlines()[-max_lines:]
            state[key] = {"inode": stat.st_ino, "offset": fh.tell()}
        return lines, state

    def loop() -> None:
        log.info("SIEM headend log collector started: min_severity=%s sources=%d", min_severity, len(sources))
        _last_prune = [0.0]
        while True:
            try:
                state = load_state()
                batch: list[dict] = []
                for path in sources:
                    lines, state = read_new_lines(path, state)
                    for line in lines:
                        ev = _line_to_headend_event(path.name, line, min_severity)
                        if ev:
                            batch.append(ev)
                if batch:
                    from database import SessionLocal
                    db = SessionLocal()
                    try:
                        record_events(db, "HEADEND-LOCAL", batch[-max_lines:])
                    finally:
                        db.close()
                save_state(state)
                # Opt-in retention, maks én gang i timen (no-op når deaktiveret)
                if time.time() - _last_prune[0] > 3600:
                    _last_prune[0] = time.time()
                    from database import SessionLocal
                    _pdb = SessionLocal()
                    try:
                        prune_old_events(_pdb)
                    finally:
                        _pdb.close()
            except Exception as exc:
                log.debug("SIEM headend log collector failed: %s", exc)
            time.sleep(interval_s)

    threading.Thread(target=loop, name="siem-headend-log-collector", daemon=True).start()


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/events/{device_id}")
async def ingest_events(
    device_id: str,
    payload: dict,
    _auth: None = Depends(_require_device_auth),
    db: Session = Depends(get_db),
):
    """
    Node agent poster security events hertil.
    Body: { "events": [ { event_type, severity, username, source_ip,
                           raw_message, occurred_at }, ... ] }

    Kræver gyldigt device-token (samme verifikation som øvrige edge-endpoints) —
    tidligere kunne events for et vilkårligt device_id postes uden nogen auth.
    """
    events = payload.get("events", [])
    _check_api_rate_limit(device_id, len(events))
    result = record_events(db, device_id, events)

    # Notifikation ved kritiske SIEM-events
    if result["inserted"]:
        try:
            from datetime import datetime, timezone
            from ai.notify import notify, get_notification_config
            config = get_notification_config(db)
            if config:
                for ev in events:
                    norm = _normalize_event(ev)
                    sev = str(norm.get("severity", "")).upper()
                    if sev in ("CRITICAL", "ERROR"):
                        ev_type = norm.get("event_type", ev.get("category", "event"))
                        cooldown_key = (device_id, ev_type)
                        now_ts = time.time()
                        with _notify_cooldown_lock:
                            last_sent = _notify_cooldown.get(cooldown_key, 0)
                            if now_ts - last_sent < NOTIFY_COOLDOWN_SECONDS:
                                log.debug(
                                    "SIEM notify suppressed (cooldown): %s / %s",
                                    device_id, ev_type,
                                )
                                continue
                            _notify_cooldown[cooldown_key] = now_ts
                        notify({
                            "rule_name":   f"SIEM: {ev_type}",
                            "rule_id":     "siem",
                            "severity":    "critical" if sev == "CRITICAL" else "warning",
                            "device_id":   device_id,
                            "description": norm.get("raw_message") or ev.get("message", ""),
                            "matched_on":  [
                                f"severity:{sev}",
                                f"type:{ev_type}",
                            ],
                            "confidence":  1.0,
                            "triggered_at": datetime.now(timezone.utc).isoformat(),
                            "capture_id":  None,
                        }, db)
        except Exception as _sn:
            log.debug("SIEM notify fejl (ikke kritisk): %s", _sn)

    return result


@router.get("/events")
def get_events(
    device_id:  Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity:   Optional[str] = Query(None),
    source_ip:  Optional[str] = Query(None),
    source:     Optional[str] = Query(None),
    hours:      int           = Query(24, ge=1, le=8760),
    limit:      int           = Query(500, ge=1, le=2000),
    _user=_require_siem_role("viewer"),
    db: Session = Depends(get_db)
):
    """Hent security events med filtrering. Kræver mindst viewer-rolle."""
    _ensure_schema(db)
    since = _now() - timedelta(hours=hours)
    q = _visible_event_query(db, _user).filter(SecurityEvent.occurred_at >= since)

    if device_id:  q = q.filter(SecurityEvent.device_id  == device_id)
    if event_type: q = q.filter(SecurityEvent.event_type == event_type)
    if severity:   q = q.filter(SecurityEvent.severity   == severity)
    if source_ip:  q = q.filter(SecurityEvent.source_ip  == source_ip)
    if source:     q = q.filter(SecurityEvent.source     == source)

    rows = q.order_by(SecurityEvent.occurred_at.desc()).limit(limit).all()

    return [_serialize(r) for r in rows]


@router.get("/summary")
def get_summary(
    hours: int = Query(24, ge=1, le=8760),
    _user=_require_siem_role("viewer"),
    db: Session = Depends(get_db)
):
    """Tæller pr. device / event_type / severity — til SIEM-dashboard. Kræver mindst viewer-rolle."""
    _ensure_schema(db)
    since = _now() - timedelta(hours=hours)

    visible = _visible_event_query(db, _user).filter(SecurityEvent.occurred_at >= since)
    severity_counts = visible.with_entities(SecurityEvent.severity, func.count(SecurityEvent.id)).group_by(SecurityEvent.severity).all()
    type_counts = visible.with_entities(SecurityEvent.event_type, func.count(SecurityEvent.id)).group_by(SecurityEvent.event_type).all()
    device_counts = visible.with_entities(SecurityEvent.device_id, func.count(SecurityEvent.id)).group_by(SecurityEvent.device_id).all()

    # Seneste kritiske event
    latest_critical = _visible_event_query(db, _user).filter(
        SecurityEvent.occurred_at >= since,
        SecurityEvent.severity == "critical"
    ).order_by(SecurityEvent.occurred_at.desc()).first()

    return {
        "period_hours":     hours,
        "by_severity":      {r[0]: r[1] for r in severity_counts},
        "by_event_type":    {r[0]: r[1] for r in type_counts},
        "by_device":        {r[0]: r[1] for r in device_counts},
        "total":            sum(r[1] for r in severity_counts),
        "latest_critical":  _serialize(latest_critical) if latest_critical else None,
    }


@router.get("/threats")
def get_threats(
    hours:     int = Query(24, ge=1, le=168),
    threshold: int = Query(5,  ge=1),
    _user=_require_siem_role("viewer"),
    db: Session = Depends(get_db)
):
    """
    Brute force detektion — IPs med mere end `threshold` SSH-fejl.
    Returnerer også geografisk info hvis tilgængeligt (fremtidigt).
    Kræver mindst viewer-rolle.
    """
    _ensure_schema(db)
    since = _now() - timedelta(hours=hours)

    # FIX: normaliseringen udsender aldrig 'ssh_failure' — den producerer
    # 'ssh_tunnel_*', og syslog-ingress producerer 'network_auth_failed'. Den
    # gamle query ramte derfor reelt ingenting. Matchsættet er nu KONFIGURERBART
    # (additivt: legacy + de faktiske typer), så detektionen kan udvides uden
    # kodeændring. Default-værdien er strengt additiv ift. den gamle adfærd.
    default_types = ("ssh_failure,ssh_tunnel_connect_failed,ssh_tunnel_remote_port_busy,"
                     "network_auth_failed,ssh_auth_failed,auth_failure")
    threat_types = [t.strip() for t in
                    os.getenv("TIMELAPSE_SIEM_THREAT_EVENT_TYPES", default_types).split(",")
                    if t.strip()]

    rows = (_visible_event_query(db, _user)
            .with_entities(
                SecurityEvent.source_ip,
                SecurityEvent.device_id,
                func.count(SecurityEvent.id).label("attempts"),
                func.min(SecurityEvent.occurred_at).label("first_seen"),
                func.max(SecurityEvent.occurred_at).label("last_seen"),
            )
            .filter(
                SecurityEvent.event_type.in_(threat_types),
                SecurityEvent.source_ip.isnot(None),
                SecurityEvent.occurred_at >= since,
            )
            .group_by(SecurityEvent.source_ip, SecurityEvent.device_id)
            .having(func.count(SecurityEvent.id) >= threshold)
            .order_by(func.count(SecurityEvent.id).desc())
            .limit(100).all())

    return [
        {
            "source_ip":  r[0],
            "device_id":  r[1],
            "attempts":   r[2],
            "first_seen": r[3].isoformat() if r[3] else None,
            "last_seen":  r[4].isoformat() if r[4] else None,
            "threat_level": (
                "critical" if r[2] >= 50 else
                "warning"  if r[2] >= 10 else
                "info"
            ),
        }
        for r in rows
    ]


def _serialize(r: SecurityEvent) -> dict:
    return {
        "id":           r.id,
        "device_id":    r.device_id,
        "event_type":   r.event_type,
        "severity":     r.severity,
        "username":     r.username,
        "source_ip":    r.source_ip,
        "raw_message":  r.raw_message,
        "source":       getattr(r, "source", None),
        "category":     getattr(r, "category", None),
        "logger":       getattr(r, "logger", None),
        "process":      getattr(r, "process", None),
        "normalized":   getattr(r, "normalized", None),
        "occurred_at":  r.occurred_at.isoformat() if r.occurred_at else None,
        "received_at":  r.received_at.isoformat() if r.received_at else None,
    }
