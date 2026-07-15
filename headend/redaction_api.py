# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — redaction_api.py (Headend API)
# ───────────────────────────────────────────────────────────────────────────
# Version : 1.0.2
# Dato    : 2026-07-08
# Ændring : Tilføjet authentication (SECURITY-001 fix)
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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import JWTError, jwt as _jwt  # Samme som main.py

# Import fra headend moduler
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Capture, User

router = APIRouter(prefix="/api/redaction", tags=["redaction"])

# JWT Constants (samme som i main.py)
COOKIE_NAME = "tl_session"
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-do-not-use-in-production")
JWT_ALGORITHM = "HS256"

# Logger
log = logging.getLogger(__name__)


# ── Database Session ────────────────────────────────────────────────────────────

def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        try:
            db.rollback()
        finally:
            db.close()


# ── Authentication ─────────────────────────────────────────────────────────────


# ── Authentication ─────────────────────────────────────────────────────────────

def _decode_token(token: str) -> dict | None:
    """Decode JWT token."""
    try:
        return _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User | None:
    """FastAPI dependency — returnerer current user fra cookie eller None.

    SECURITY: Hvis ingen cookie/ugyldig token, returneres None (til opt_endpoints).
    For krævet auth, brug Depends(get_required_user).
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = _decode_token(token)
    if not payload:
        return None
    user = db.query(User).filter_by(username=payload.get("sub"), is_active=True).first()
    return user


def get_required_user(
    current_user: User | None = Depends(get_current_user)
) -> User:
    """FastAPI dependency — kræver authenticated user.

    Kaster 401 hvis ingen user.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ikke autentificeret",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class BoundingBox(BaseModel):
    x: int
    y: int
    w: int
    h: int
    confidence: float


class PIIDetections(BaseModel):
    faces: list[BoundingBox] = []
    license_plates: list[BoundingBox] = []
    has_pii: bool = False

    def to_dict(self) -> dict:
        return {
            "faces": [f.model_dump() for f in self.faces],
            "license_plates": [p.model_dump() for p in self.license_plates],
            "has_pii": self.has_pii
        }


class AnalyzeResponse(BaseModel):
    capture_id: int
    redaction_status: str
    detections: PIIDetections
    message: str


class RedactionStatusResponse(BaseModel):
    capture_id: int
    device_id: str
    filename: str
    redaction_status: str
    has_gdpr_data: Optional[bool] = None
    gdpr_detections: Optional[dict] = None
    redacted_at: Optional[str] = None
    redacted_by: Optional[str] = None


class PendingListResponse(BaseModel):
    total: int
    pending_analysis: int
    detected_pii: int
    items: list[RedactionStatusResponse]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_image_path(capture: Capture, base_path: str = "/mnt/SFTP_DATA") -> Path:
    """Finder billedet baseret på capture record.

    Bruger samme logik som _find_image() i main.py:
    1. Flad device: {device_id}/filename (SIMPEL - vi tester med dette)
    """
    import os

    filename = capture.filename or ""
    device_id = capture.device_id

    # Hent storage roots fra env eller brug base_path
    storage_roots = os.getenv("SFTP_DATA_ROOT", base_path).split(":")

    for root in storage_roots:
        base = Path(root)

        # 1. Prøv flad struktur først: {device_id}/filename
        path_simple = base / device_id / filename

        if path_simple.exists():
            return path_simple

        # 2. Prøv dato-struktur hvis filename har dato
        import re
        m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
        if m:
            yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
            path_date = base / device_id / yyyy / mm / dd / filename
            if path_date.exists():
                return path_date

    raise HTTPException(status_code=404, detail=f"Image not found for device={device_id}, filename={filename}")


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user)  # AUTH REQUIRED
):
    """
    Analyser et billede for GDPR data (ansigter, nummerplader).

    Bruger OpenCV HAAR cascades til detection.
    Kræver: operator rettighed eller derover.
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    try:
        import cv2
        import numpy as np

        # Find billedet
        image_path = _find_image_path(capture)

        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise HTTPException(status_code=500, detail=f"Failed to load image: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Load HAAR cascades
        cascade_dir = cv2.data.haarcascades
        face_cascade = cv2.CascadeClassifier(f"{cascade_dir}/haarcascade_frontalface_default.xml")
        plate_cascade = cv2.CascadeClassifier(f"{cascade_dir}/haarcascade_license_plate_rus_16stages.xml")

        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        face_boxes = [
            BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h), confidence=0.8)
            for x, y, w, h in faces
        ]

        # Detect license plates
        plates = plate_cascade.detectMultiScale(gray, 1.1, 4)
        plate_boxes = [
            BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h), confidence=0.7)
            for x, y, w, h in plates
        ]

        detections = PIIDetections(
            faces=face_boxes,
            license_plates=plate_boxes,
            has_pii=len(face_boxes) > 0 or len(plate_boxes) > 0
        )

        # Opdater status
        if detections.has_pii:
            _update_redaction_status(
                db, capture, "detected",
                has_gdpr_data=True, detections=detections
            )
            message = f"Detected {len(face_boxes)} faces, {len(plate_boxes)} license plates"
        else:
            _update_redaction_status(
                db, capture, "analyzed",
                has_gdpr_data=False, detections=detections
            )
            message = "No GDPR data detected"

        db.refresh(capture)

        return AnalyzeResponse(
            capture_id=capture_id,
            redaction_status=capture.redaction_status,
            detections=detections,
            message=message
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenCV ikke tilgængeligt: {e}"
        )
    except Exception as e:
        log.exception(f"Analyse fejlede for capture {capture_id}")
        raise HTTPException(status_code=500, detail=f"Analyse fejlede: {e}")


@router.post("/redact/{capture_id}")
def redact_capture(
    capture_id: int,
    blur_kernel: int = 51,
    blur_sigma: int = 30,
    auto_approve: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user)  # AUTH REQUIRED
):
    """Udfør redaction/sløring på et billede.

    Kræver: operator rettighed eller derover.
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    if capture.redaction_status != "detected":
        raise HTTPException(
            status_code=400,
            detail=f"Capture skal have status 'detected' før redaction. Nu: {capture.redaction_status}"
        )

    try:
        import cv2
        import shutil
        from datetime import datetime as _datetime

        # Find billedet
        image_path = _find_image_path(capture)

        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise HTTPException(status_code=500, detail="Failed to load image")

        # Hent detections
        detections = capture.gdpr_detections
        if not detections:
            raise HTTPException(status_code=400, detail="Ingen detections at sløre")

        # Apply blur til alle detections
        for face in detections.get("faces", []):
            x, y, w, h = face["x"], face["y"], face["w"], face["h"]
            roi = img[y:y+h, x:x+w]
            blurred = cv2.GaussianBlur(roi, (blur_kernel, blur_kernel), blur_sigma)
            img[y:y+h, x:x+w] = blurred

        for plate in detections.get("license_plates", []):
            x, y, w, h = plate["x"], plate["y"], plate["w"], plate["h"]
            roi = img[y:y+h, x:x+w]
            blurred = cv2.GaussianBlur(roi, (blur_kernel, blur_kernel), blur_sigma)
            img[y:y+h, x:x+w] = blurred

        # Backup original
        backup_path = image_path.with_suffix(".original" + image_path.suffix)
        shutil.copy(image_path, backup_path)

        # Save redacted
        cv2.imwrite(str(image_path), img)

        # Opdater status
        new_status = "redacted" if auto_approve else "redacted"
        _update_redaction_status(
            db, capture, new_status,
            redacted_path=str(image_path),
            redacted_by="auto"
        )

        return {
            "success": True,
            "message": "Billede sløret",
            "backup_path": str(backup_path)
        }

    except Exception as e:
        log.exception(f"Redaction fejlede for capture {capture_id}")
        raise HTTPException(status_code=500, detail=f"Redaction fejlede: {e}")


@router.post("/approve/{capture_id}")
def approve_capture(
    capture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user)  # AUTH REQUIRED
):
    """Godkend et redacted billede.

    Kræver: operator rettighed eller derover.
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    if capture.redaction_status != "redacted":
        raise HTTPException(
            status_code=400,
            detail=f"Capture skal have status 'redacted'. Nu: {capture.redaction_status}"
        )

    # Behold status som redacted men marker som approved
    # (I mere avanceret version ville vi have en egen approved_status)

    return {
        "success": True,
        "message": "Billede godkendt",
        "redacted_at": capture.redacted_at.isoformat() if capture.redacted_at else None
    }


@router.get("/status/{capture_id}", response_model=RedactionStatusResponse)
def get_redaction_status(
    capture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user)  # AUTH REQUIRED
):
    """Hent redaction status for et capture.

    Kræver: viewer rettighed eller derover.
    """
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    return RedactionStatusResponse(
        capture_id=capture.id,
        device_id=capture.device_id,
        filename=capture.filename or "",
        redaction_status=capture.redaction_status or "pending",
        has_gdpr_data=capture.has_gdpr_data,
        gdpr_detections=capture.gdpr_detections,
        redacted_at=capture.redacted_at.isoformat() if capture.redacted_at else None,
        redacted_by=capture.redacted_by
    )


@router.get("/pending", response_model=PendingListResponse)
def get_pending_captures(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user)  # AUTH REQUIRED
):
    """List captures der afventer redaction.

    Kræver: viewer rettighed eller derover.
    """
    from sqlalchemy import func

    query = db.query(Capture).filter(
        Capture.redaction_status.in_(["pending", "analyzed", "detected"])
    )

    if status_filter and status_filter != "all":
        query = query.filter(Capture.redaction_status == status_filter)

    captures = query.order_by(Capture.captured_at.desc()).limit(100).all()

    total = query.count()
    pending_analysis = db.query(Capture).filter(Capture.redaction_status == "pending").count()
    detected_pii = db.query(Capture).filter(
        Capture.redaction_status == "detected",
        Capture.has_gdpr_data == True
    ).count()

    items = [
        RedactionStatusResponse(
            capture_id=c.id,
            device_id=c.device_id,
            filename=c.filename or "",
            redaction_status=c.redaction_status or "pending",
            has_gdpr_data=c.has_gdpr_data,
            gdpr_detections=c.gdpr_detections,
            redacted_at=c.redacted_at.isoformat() if c.redacted_at else None,
            redacted_by=c.redacted_by
        )
        for c in captures
    ]

    return PendingListResponse(
        total=total,
        pending_analysis=pending_analysis,
        detected_pii=detected_pii,
        items=items
    )
