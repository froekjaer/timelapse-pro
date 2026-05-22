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
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Session

from database import Base, get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["SIEM"])


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
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc))
    dedup_hash  = Column(String(64), unique=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dedup_hash(device_id: str, event_type: str,
                occurred_at: str, source_ip: str = "") -> str:
    """Hash til deduplicering — samme event inden for samme sekund ignoreres."""
    raw = f"{device_id}:{event_type}:{occurred_at[:19]}:{source_ip}"
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


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/events/{device_id}")
def ingest_events(device_id: str, payload: dict, db: Session = Depends(get_db)):
    """
    Node agent poster security events hertil.
    Body: { "events": [ { event_type, severity, username, source_ip,
                           raw_message, occurred_at }, ... ] }
    """
    events = payload.get("events", [])
    inserted = 0
    duplicates = 0

    for ev in events:
        try:
            occurred = _parse_dt(ev.get("occurred_at", _now().isoformat()))
            h = _dedup_hash(
                device_id,
                ev.get("event_type", "unknown"),
                occurred.isoformat(),
                ev.get("source_ip", ""),
            )

            row = SecurityEvent(
                device_id   = device_id,
                event_type  = ev.get("event_type", "unknown"),
                severity    = ev.get("severity", "info"),
                username    = ev.get("username"),
                source_ip   = ev.get("source_ip"),
                raw_message = ev.get("raw_message", "")[:500],
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

        # Notifikation ved kritiske SIEM-events
        try:
            from datetime import datetime, timezone
            from ai.notify import notify, get_notification_config
            config = get_notification_config(db)
            if config:
                for ev in events:
                    if ev.get("severity") in ("CRITICAL", "ERROR"):
                        notify({
                            "rule_name":   f"SIEM: {ev.get('event_type', ev.get('category', 'event'))}",
                            "rule_id":     "siem",
                            "severity":    "critical" if ev.get("severity") == "CRITICAL" else "warning",
                            "device_id":   device_id,
                            "description": ev.get("raw_message") or ev.get("message", ""),
                            "matched_on":  [
                                f"severity:{ev.get('severity')}",
                                f"type:{ev.get('event_type', '?')}",
                            ],
                            "confidence":  1.0,
                            "triggered_at": datetime.now(timezone.utc).isoformat(),
                            "capture_id":  None,
                        }, db)
        except Exception as _sn:
            log.debug("SIEM notify fejl (ikke kritisk): %s", _sn)

    return {"inserted": inserted, "duplicates": duplicates}


@router.get("/events")
def get_events(
    device_id:  Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity:   Optional[str] = Query(None),
    source_ip:  Optional[str] = Query(None),
    hours:      int           = Query(24, ge=1, le=8760),
    limit:      int           = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db)
):
    """Hent security events med filtrering."""
    since = _now() - timedelta(hours=hours)
    q = db.query(SecurityEvent).filter(SecurityEvent.occurred_at >= since)

    if device_id:  q = q.filter(SecurityEvent.device_id  == device_id)
    if event_type: q = q.filter(SecurityEvent.event_type == event_type)
    if severity:   q = q.filter(SecurityEvent.severity   == severity)
    if source_ip:  q = q.filter(SecurityEvent.source_ip  == source_ip)

    rows = q.order_by(SecurityEvent.occurred_at.desc()).limit(limit).all()

    return [_serialize(r) for r in rows]


@router.get("/summary")
def get_summary(
    hours: int = Query(24, ge=1, le=8760),
    db: Session = Depends(get_db)
):
    """Tæller pr. device / event_type / severity — til SIEM-dashboard."""
    since = _now() - timedelta(hours=hours)

    # Total pr. severity
    severity_counts = db.execute(text("""
        SELECT severity, COUNT(*) as count
        FROM security_events
        WHERE occurred_at >= :since
        GROUP BY severity
        ORDER BY count DESC
    """), {"since": since}).fetchall()

    # Total pr. event_type
    type_counts = db.execute(text("""
        SELECT event_type, COUNT(*) as count
        FROM security_events
        WHERE occurred_at >= :since
        GROUP BY event_type
        ORDER BY count DESC
    """), {"since": since}).fetchall()

    # Total pr. device
    device_counts = db.execute(text("""
        SELECT device_id, COUNT(*) as count
        FROM security_events
        WHERE occurred_at >= :since
        GROUP BY device_id
        ORDER BY count DESC
    """), {"since": since}).fetchall()

    # Seneste kritiske event
    latest_critical = db.query(SecurityEvent).filter(
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
    db: Session = Depends(get_db)
):
    """
    Brute force detektion — IPs med mere end `threshold` SSH-fejl.
    Returnerer også geografisk info hvis tilgængeligt (fremtidigt).
    """
    since = _now() - timedelta(hours=hours)

    rows = db.execute(text("""
        SELECT source_ip, device_id, COUNT(*) as attempts,
               MIN(occurred_at) as first_seen,
               MAX(occurred_at) as last_seen
        FROM security_events
        WHERE event_type = 'ssh_failure'
          AND source_ip IS NOT NULL
          AND occurred_at >= :since
        GROUP BY source_ip, device_id
        HAVING COUNT(*) >= :threshold
        ORDER BY attempts DESC
        LIMIT 100
    """), {"since": since, "threshold": threshold}).fetchall()

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
        "occurred_at":  r.occurred_at.isoformat() if r.occurred_at else None,
        "received_at":  r.received_at.isoformat() if r.received_at else None,
    }
