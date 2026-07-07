# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — redaction_api.py (Headend API)
# ───────────────────────────────────────────────────────────────────────────
# Version : 1.0.0
# Dato    : 2026-07-07
# ═══════════════════════════════════════════════════════════════════════════
"""
REST API endpoints for GDPR redaction workflow.

Endpoints:
  - POST /api/redaction/analyze/{capture_id} — Analyser billede for GDPR data
  - POST /api/redaction/redact/{capture_id} — Udfør redaction på billede
  - GET /api/redaction/status/{capture_id} — Hent redaction status
  - GET /api/redaction/pending — List billeder der afventer redaction
  - POST /api/redaction/approve/{capture_id} — Godkend redacted billede

Krav: UI-010 (GDPR redaction workflow)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Capture, get_db, now_utc
from redaction import detect_pii, redact_image, PIIDetections, BoundingBox

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/redaction", tags=["Redaction"])


# ── Request/Response models ─────────────────────────────────────────────────────

class BoundingBoxModel(BaseModel):
    x: int
    y: int
    w: int
    h: int
    confidence: float


class PIIDetectionsModel(BaseModel):
    faces: list[BoundingBoxModel]
    license_plates: list[BoundingBoxModel]
    has_pii: bool


class AnalyzeResponse(BaseModel):
    capture_id: int
    has_gdpr_data: bool
    detections: PIIDetectionsModel
    redaction_status: str


class RedactRequest(BaseModel):
    blur_kernel: int = 51
    blur_sigma: int = 30
    auto_approve: bool = False


class RedactResponse(BaseModel):
    capture_id: int
    success: bool
    redacted_path: Optional[str]
    metadata: dict
    message: str


class RedactionStatusResponse(BaseModel):
    capture_id: int
    device_id: str
    filename: str
    redaction_status: str
    has_gdpr_data: Optional[bool]
    gdpr_detections: Optional[dict]
    redacted_at: Optional[str]
    redacted_by: Optional[str]


class PendingListResponse(BaseModel):
    total: int
    pending_analysis: int
    detected_pii: int
    items: list[RedactionStatusResponse]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_image_path(capture: Capture, base_path: str = "/mnt/SFTP_DATA") -> Path:
    """Finder billedet baseret på capture record."""
    # Implementation similar til _find_image() i main.py
    from cmdb import _device_path

    device_path = _device_path(capture.device_id)
    if not device_path:
        raise HTTPException(status_code=404, detail=f"Device path not found for {capture.device_id}")

    # Parse captured_at for dato-sti
    captured_at = capture.captured_at or capture.received_at
    date_path = captured_at.strftime("%Y/%m/%d")

    image_path = Path(base_path) / device_path / date_path / capture.filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")

    return image_path


def _update_redaction_status(
    db: Session,
    capture: Capture,
    redaction_status: str,
    has_gdpr_data: Optional[bool] = None,
    detections: Optional[PIIDetections] = None,
    redacted_path: Optional[str] = None,
    redacted_by: str = "auto"
):
    """Opdaterer redaction status på capture record."""
    from sqlalchemy import cast, String

    # Cast redaction_status til proper type for database
    capture.redaction_status = redaction_status

    if has_gdpr_data is not None:
        capture.has_gdpr_data = has_gdpr_data

    if detections:
        capture.gdpr_detections = detections.to_dict()

    if redacted_path:
        capture.redaction_method = "opencv_blur"
        capture.redacted_at = now_utc()
        capture.redacted_by = redacted_by

    db.commit()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze/{capture_id}", response_model=AnalyzeResponse)
def analyze_capture(
    capture_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyser et billede for GDPR data (ansigter, nummerplader).

    Opdaterer capture.redaction_status og has_gdpr_data.
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    try:
        image_path = _find_image_path(capture)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error finding image for capture %s: %s", capture_id, e)
        _update_redaction_status(db, capture, "skipped")
        raise HTTPException(status_code=500, detail=str(e))

    try:
        detections = detect_pii(image_path)
        has_pii = detections.has_pii()

        # Opdater database
        new_status = "detected" if has_pii else "analyzed"
        _update_redaction_status(
            db, capture, new_status,
            has_gdpr_data=has_pii,
            detections=detections
        )

        db.refresh(capture)

        return AnalyzeResponse(
            capture_id=capture_id,
            has_gdpr_data=has_pii,
            detections=PIIDetectionsModel(
                faces=[BoundingBoxModel(**f.to_dict()) for f in detections.faces],
                license_plates=[BoundingBoxModel(**p.to_dict()) for p in detections.license_plates],
                has_pii=has_pii
            ),
            redaction_status=capture.redaction_status or "unknown"
        )

    except Exception as e:
        log.error("Analysis failed for capture %s: %s", capture_id, e)
        _update_redaction_status(db, capture, "skipped")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/redact/{capture_id}", response_model=RedactResponse)
def redact_capture(
    capture_id: int,
    request: RedactRequest,
    db: Session = Depends(get_db)
):
    """
    Udfør redaction på et billede (slør ansigter/nummerplader).

    Kræver at capture er analyseret først (redaction_status = 'detected').
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    if capture.redaction_status != "detected":
        raise HTTPException(
            status_code=400,
            detail=f"Capture must be in 'detected' status, current: {capture.redaction_status}"
        )

    try:
        image_path = _find_image_path(capture)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error finding image for capture %s: %s", capture_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Parse detections fra database
        gdpr_detections = capture.gdpr_detections or {}
        faces = [BoundingBox(**f) for f in gdpr_detections.get("faces", [])]
        plates = [BoundingBox(**p) for p in gdpr_detections.get("license_plates", [])]
        detections = PIIDetections(faces=faces, license_plates=plates)

        # Output sti: samme mappe men med .redacted før extension
        output_path = image_path.with_suffix(image_path.suffix + ".redacted" + image_path.suffix)

        # Udfør redaction
        redacted_path, metadata = redact_image(
            image_path,
            detections,
            output_path=output_path,
            blur_kernel=request.blur_kernel,
            blur_sigma=request.blur_sigma
        )

        # Opdater database
        final_status = "redacted" if request.auto_approve else "detected"
        _update_redaction_status(
            db, capture, final_status,
            redacted_path=str(redacted_path),
            redacted_by="auto" if request.auto_approve else "manual"
        )

        db.refresh(capture)

        return RedactResponse(
            capture_id=capture_id,
            success=True,
            redacted_path=str(redacted_path),
            metadata=metadata,
            message=f"Successfully redacted {metadata.get('redacted_count', 0)} regions"
        )

    except Exception as e:
        log.error("Redaction failed for capture %s: %s", capture_id, e)
        raise HTTPException(status_code=500, detail=f"Redaction failed: {str(e)}")


@router.get("/status/{capture_id}", response_model=RedactionStatusResponse)
def get_redaction_status(
    capture_id: int,
    db: Session = Depends(get_db)
):
    """Hent redaction status for en capture."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    return RedactionStatusResponse(
        capture_id=capture.id,
        device_id=capture.device_id,
        filename=capture.filename or "unknown",
        redaction_status=capture.redaction_status or "unknown",
        has_gdpr_data=capture.has_gdpr_data,
        gdpr_detections=capture.gdpr_detections,
        redacted_at=capture.redacted_at.isoformat() if capture.redacted_at else None,
        redacted_by=capture.redacted_by
    )


@router.get("/pending", response_model=PendingListResponse)
def list_pending(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List captures der afventer redaction.

    status_filter: 'pending', 'detected', 'analyzed', eller None for alle ikke-redacted
    """
    query = db.query(Capture).filter(
        Capture.redaction_status.isnot(None),
        Capture.redaction_status != "redacted"
    )

    if status_filter:
        query = query.filter(Capture.redaction_status == status_filter)

    total = query.count()
    captures = query.order_by(Capture.captured_at.desc()).offset(skip).limit(limit).all()

    pending_analysis = db.query(Capture).filter(Capture.redaction_status == "pending").count()
    detected_pii = db.query(Capture).filter(Capture.redaction_status == "detected").count()

    return PendingListResponse(
        total=total,
        pending_analysis=pending_analysis,
        detected_pii=detected_pii,
        items=[
            RedactionStatusResponse(
                capture_id=c.id,
                device_id=c.device_id,
                filename=c.filename or "unknown",
                redaction_status=c.redaction_status or "unknown",
                has_gdpr_data=c.has_gdpr_data,
                gdpr_detections=c.gdpr_detections,
                redacted_at=c.redacted_at.isoformat() if c.redacted_at else None,
                redacted_by=c.redacted_by
            )
            for c in captures
        ]
    )


@router.post("/approve/{capture_id}")
def approve_redaction(
    capture_id: int,
    db: Session = Depends(get_db)
):
    """
    Godkend et redacted billede til produktion.

    Efter godkendelse kan det redacted billede bruges som 'primary' billede.
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    if capture.redaction_status != "detected":
        raise HTTPException(
            status_code=400,
            detail=f"Capture must be redacted first, current status: {capture.redaction_status}"
        )

    # Marker som approved/redacted
    _update_redaction_status(db, capture, "redacted", redacted_by="manual")

    return {"capture_id": capture_id, "status": "approved"}
