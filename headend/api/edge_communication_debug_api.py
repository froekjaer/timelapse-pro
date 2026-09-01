"""Edge/Headend communication debug API and sanitized request logger."""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from auth import require_role
from database import Device, EdgeApiCommunicationLog, EdgeCommunicationCaptureSession, SessionLocal, get_db

router = APIRouter(prefix="/api/admin/edge-communications", tags=["Edge Communications"])

_EDGE_PATHS = (
    "/api/edge/",
    "/api/config/",
    "/api/heartbeat/",
    "/api/captures/",
    "/api/updates/report",
    "/api/siem/events/",
)
_MAX_BODY_BYTES = 64 * 1024
_SECRET_RE = re.compile(r"(token|secret|password|private_key|api_key|authorization|credential)", re.I)
_PRIVATE_KEY_VALUE_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)


def _path_is_edge_api(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _EDGE_PATHS)


def _device_id_from_path(path: str) -> str | None:
    patterns = (
        r"^/api/edge/sync/([^/?#]+)",
        r"^/api/config/([^/?#]+)",
        r"^/api/heartbeat/([^/?#]+)",
        r"^/api/captures/([^/?#]+)",
        r"^/api/siem/events/([^/?#]+)",
    )
    for pattern in patterns:
        match = re.match(pattern, path)
        if match:
            return match.group(1)
    return None


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_RE.search(str(key)):
                redacted[str(key)] = "[redacted]"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value[:200]]
    if isinstance(value, str) and _PRIVATE_KEY_VALUE_RE.search(value):
        return "[redacted]"
    if isinstance(value, str) and len(value) > 2000:
        return value[:2000] + "...[truncated]"
    return value


def _redact_query_string(query: str) -> str | None:
    if not query:
        return None
    pairs = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        pairs.append((key, "[redacted]" if _SECRET_RE.search(key) else value))
    return urlencode(pairs)


def _safe_int(value: str | int | None, fallback: int = 0) -> int:
    try:
        return int(value if value is not None else fallback)
    except (TypeError, ValueError):
        return fallback


def _transport_security(request: Request) -> tuple[str, str]:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    scheme = forwarded_proto or request.url.scheme
    if scheme == "https":
        return scheme, "encrypted"
    if scheme == "http":
        return scheme, "unencrypted"
    return scheme or "unknown", "unknown"


def _interpret(path: str, status_code: int | None, transport_security: str, body: dict | None) -> str:
    parts: list[str] = []
    if path.startswith("/api/edge/sync/"):
        parts.append("Samlet Edge-sync: diagnostik, SIEM, inventory og update-policy i samme poll.")
    elif path.startswith("/api/config/"):
        parts.append("Konfigurationskald fra Edge; bruges stadig som kompatibilitet/legacy-path.")
    elif path.startswith("/api/heartbeat/"):
        parts.append("Heartbeat fra Edge; viser at enheden stadig kan nå Headend.")
    elif path.startswith("/api/captures/") and path.endswith("/files"):
        parts.append("Billedfil-upload fra Edge; kun request-metadata logges, ikke billeddata.")
    elif path.startswith("/api/captures/"):
        parts.append("Capture-metadata fra Edge; bruges til billedhistorik, kvalitet og upload-status.")
    elif path.startswith("/api/updates/report"):
        parts.append("Edge rapporterer status på software-/pakkeopdatering.")
    elif path.startswith("/api/siem/events/"):
        parts.append("Edge uploader sikkerheds-/SIEM-events.")
    else:
        parts.append("API-kald fra eller til Edge-rettet Headend-endpoint.")

    if transport_security == "unencrypted":
        parts.append("Transport ser ukrypteret ud ved Headend-ingress; bør kun være intern loopback/reverse-proxy trafik.")
    elif transport_security == "encrypted":
        parts.append("Transport rapporterer HTTPS/TLS ved ingress.")
    else:
        parts.append("Transportkryptering kunne ikke afgøres ud fra request-metadata.")

    if status_code is not None and status_code >= 400:
        parts.append(f"HTTP status {status_code}; gennemgå payload og serverlog.")
    if body and "post_restart_health" in body:
        parts.append("Indeholder post-restart health-evidence efter opdatering.")
    return " ".join(parts)


def _expire_if_due(session: EdgeCommunicationCaptureSession, now: datetime) -> bool:
    """Mark a session stopped if its bound was reached. Returns True if it
    is (now) inactive."""
    if session.stopped_at is not None:
        return True
    started_at = session.started_at
    # SQLite (tests) round-trips DateTime(timezone=True) as naive UTC — Postgres
    # (production) preserves tz-awareness. Normalise so this comparison never
    # raises regardless of backend.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if session.duration_minutes and now >= started_at + timedelta(minutes=session.duration_minutes):
        session.stopped_at = now
        session.stop_reason = "duration_expired"
        return True
    if session.max_packets and session.packet_count >= session.max_packets:
        session.stopped_at = now
        session.stop_reason = "packet_limit_reached"
        return True
    return False


def _any_capture_session_might_be_active(db: Session) -> bool:
    """Cheap existence check — lets an idle Headend skip body-parsing/redaction
    entirely for every Edge request when no one asked for a capture."""
    return db.query(
        db.query(EdgeCommunicationCaptureSession)
        .filter(EdgeCommunicationCaptureSession.stopped_at.is_(None))
        .exists()
    ).scalar()


def _match_active_capture_session(db: Session, device_id: str | None) -> EdgeCommunicationCaptureSession | None:
    """Return the capture session (device-specific or all-devices) that
    covers this request, expiring any session whose time/count bound was
    reached along the way."""
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(EdgeCommunicationCaptureSession)
        .filter(EdgeCommunicationCaptureSession.stopped_at.is_(None))
        .all()
    )
    matched = None
    for session in candidates:
        if _expire_if_due(session, now):
            continue
        if session.device_id and session.device_id != device_id:
            continue
        if matched is None:
            matched = session
    if candidates:
        db.commit()
    return matched


def _capture_session_dict(session: EdgeCommunicationCaptureSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "device_id": session.device_id,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "started_by": session.started_by,
        "duration_minutes": session.duration_minutes,
        "max_packets": session.max_packets,
        "packet_count": session.packet_count,
        "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
        "stop_reason": session.stop_reason,
        "active": session.stopped_at is None,
    }


def install_edge_communication_logger(app) -> None:
    @app.middleware("http")
    async def _edge_communication_logger(request: Request, call_next):
        path = request.url.path
        if not _path_is_edge_api(path):
            return await call_next(request)

        # No active capture session anywhere → skip body-parsing/redaction
        # entirely and just pass the request through. This is the common
        # case (2026-08-31, Peter: the always-on logger wrote a DB row for
        # every single Edge call, forever — real cost with no bound as the
        # fleet grows). Only a deliberately started, time- and/or
        # count-bounded session causes any logging or extra work here.
        with SessionLocal() as db:
            any_session = _any_capture_session_might_be_active(db)
        if not any_session:
            return await call_next(request)

        content_type = request.headers.get("content-type", "")
        raw_body = b""
        parsed_body: dict | None = None
        truncated = False
        if "application/json" in content_type.lower():
            raw_body = await request.body()
            async def receive():
                return {"type": "http.request", "body": raw_body, "more_body": False}
            request = Request(request.scope, receive)
            truncated = len(raw_body) > _MAX_BODY_BYTES
            if raw_body and not truncated:
                try:
                    candidate = json.loads(raw_body.decode("utf-8"))
                    parsed_body = _redact(candidate) if isinstance(candidate, dict) else {"payload": _redact(candidate)}
                except Exception:
                    parsed_body = {"_parse_error": "invalid_json"}

        response = await call_next(request)

        try:
            device_id = _device_id_from_path(path)
            if not device_id and parsed_body:
                body_device = parsed_body.get("device_id")
                device_id = str(body_device) if body_device else None
            scheme, security = _transport_security(request)
            with SessionLocal() as db:
                session = _match_active_capture_session(db, device_id)
                if session is None:
                    return response
                session.packet_count += 1
                _expire_if_due(session, datetime.now(timezone.utc))
                db.add(EdgeApiCommunicationLog(
                    device_id=device_id,
                    method=request.method,
                    path=path,
                    query_string=_redact_query_string(request.url.query),
                    status_code=response.status_code,
                    transport_scheme=scheme,
                    transport_security=security,
                    client_host=request.client.host if request.client else None,
                    user_agent=(request.headers.get("user-agent") or "")[:300] or None,
                    request_content_type=content_type[:120] or None,
                    request_bytes=_safe_int(request.headers.get("content-length"), len(raw_body)),
                    request_body_json=json.dumps(parsed_body, ensure_ascii=False) if parsed_body is not None else None,
                    request_body_truncated=truncated,
                    interpretation=_interpret(path, response.status_code, security, parsed_body),
                ))
                db.commit()
        except Exception:
            pass
        return response


def _row_dict(row: EdgeApiCommunicationLog) -> dict[str, Any]:
    body = None
    if row.request_body_json:
        try:
            body = json.loads(row.request_body_json)
        except Exception:
            body = row.request_body_json
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "device_id": row.device_id,
        "direction": row.direction,
        "method": row.method,
        "path": row.path,
        "query_string": row.query_string,
        "status_code": row.status_code,
        "transport_scheme": row.transport_scheme,
        "transport_security": row.transport_security,
        "client_host": row.client_host,
        "user_agent": row.user_agent,
        "request_content_type": row.request_content_type,
        "request_bytes": row.request_bytes,
        "request_body_truncated": bool(row.request_body_truncated),
        "request_body": body,
        "interpretation": row.interpretation,
    }


@router.get("/devices")
def list_devices(_user=require_role("admin"), db: Session = Depends(get_db)):
    rows = db.query(Device).order_by(Device.device_id).all()
    return [
        {
            "device_id": row.device_id,
            "label": row.camera_name or row.location_name or row.hostname or row.device_id,
            "customer_name": row.customer_name,
            "site_name": row.site_name,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in rows
    ]


@router.get("/capture/status")
def capture_status(_user=require_role("admin"), db: Session = Depends(get_db)):
    """Alle capture-sessioner der stadig er aktive lige nu (typisk 0 eller 1)."""
    now = datetime.now(timezone.utc)
    sessions = (
        db.query(EdgeCommunicationCaptureSession)
        .order_by(EdgeCommunicationCaptureSession.started_at.desc())
        .limit(20)
        .all()
    )
    changed = False
    for session in sessions:
        if _expire_if_due(session, now):
            changed = True
    if changed:
        db.commit()
    return [_capture_session_dict(s) for s in sessions]


@router.post("/capture/start")
def start_capture(
    device_id: str | None = None,
    duration_minutes: int | None = None,
    max_packets: int | None = None,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    if duration_minutes is None and max_packets is None:
        raise HTTPException(
            status_code=400,
            detail="Angiv varighed (minutter) og/eller maks. antal pakker — en ubegrænset capture-session er ikke tilladt",
        )
    if duration_minutes is not None and duration_minutes <= 0:
        raise HTTPException(status_code=400, detail="Varighed skal være positiv")
    if max_packets is not None and max_packets <= 0:
        raise HTTPException(status_code=400, detail="Maks. antal pakker skal være positivt")

    now = datetime.now(timezone.utc)
    existing = (
        db.query(EdgeCommunicationCaptureSession)
        .filter(EdgeCommunicationCaptureSession.stopped_at.is_(None))
        .all()
    )
    for session in existing:
        if _expire_if_due(session, now):
            continue
        if not session.device_id or not device_id or session.device_id == device_id:
            raise HTTPException(
                status_code=409,
                detail=f"En capture-session kører allerede (id={session.id}) — stop den først",
            )
    db.commit()

    session = EdgeCommunicationCaptureSession(
        device_id=device_id or None,
        started_by=_user.username,
        duration_minutes=duration_minutes,
        max_packets=max_packets,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _capture_session_dict(session)


@router.post("/capture/{session_id}/stop")
def stop_capture(session_id: int, _user=require_role("admin"), db: Session = Depends(get_db)):
    session = db.query(EdgeCommunicationCaptureSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Capture-session ikke fundet")
    if session.stopped_at is None:
        session.stopped_at = datetime.now(timezone.utc)
        session.stop_reason = "manual"
        db.commit()
        db.refresh(session)
    return _capture_session_dict(session)


@router.get("")
def list_communications(
    device_id: str | None = None,
    transport_security: str | None = None,
    limit: int = 200,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    q = db.query(EdgeApiCommunicationLog)
    if device_id:
        q = q.filter(EdgeApiCommunicationLog.device_id == device_id)
    if transport_security:
        q = q.filter(EdgeApiCommunicationLog.transport_security == transport_security)
    rows = q.order_by(EdgeApiCommunicationLog.created_at.desc()).limit(max(1, min(limit, 1000))).all()
    return [_row_dict(row) for row in rows]


@router.delete("")
def clear_communications(
    device_id: str | None = None,
    transport_security: str | None = None,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    """Ryd den loggede pakkeliste, så man kan starte forfra. Respekterer
    samme filtre som listevisningen — uden filtre ryddes alt. Rydder ikke
    capture-sessioner (de styrer om der logges noget nyt, ikke hvad der
    allerede er logget)."""
    q = db.query(EdgeApiCommunicationLog)
    if device_id:
        q = q.filter(EdgeApiCommunicationLog.device_id == device_id)
    if transport_security:
        q = q.filter(EdgeApiCommunicationLog.transport_security == transport_security)
    deleted = q.delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


def _xlsx_cell(value: Any) -> str:
    if value is None:
        value = ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return f"<c t=\"inlineStr\"><is><t>{escape(str(value))}</t></is></c>"


def _xlsx_response(rows: list[dict[str, Any]]) -> Response:
    headers = [
        "Tidspunkt", "Device", "Retning", "Metode", "Path", "Status",
        "Transport", "Klient", "Bytes", "Truncated", "Fortolkning", "Payload",
    ]
    data_rows = [
        [
            row.get("created_at"), row.get("device_id"), row.get("direction"), row.get("method"),
            row.get("path"), row.get("status_code"), row.get("transport_security"),
            row.get("client_host"), row.get("request_bytes"), row.get("request_body_truncated"),
            row.get("interpretation"), row.get("request_body"),
        ]
        for row in rows
    ]
    sheet_rows = []
    for index, values in enumerate([headers, *data_rows], start=1):
        sheet_rows.append(f"<row r=\"{index}\">{''.join(_xlsx_cell(v) for v in values)}</row>")
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Edge API" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    filename = f"timelapse-edge-api-debug-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.xlsx")
def export_communications(
    device_id: str | None = None,
    transport_security: str | None = None,
    limit: int = 1000,
    _user=require_role("admin"),
    db: Session = Depends(get_db),
):
    q = db.query(EdgeApiCommunicationLog)
    if device_id:
        q = q.filter(EdgeApiCommunicationLog.device_id == device_id)
    if transport_security:
        q = q.filter(EdgeApiCommunicationLog.transport_security == transport_security)
    rows = q.order_by(EdgeApiCommunicationLog.created_at.desc()).limit(max(1, min(limit, 5000))).all()
    return _xlsx_response([_row_dict(row) for row in rows])
