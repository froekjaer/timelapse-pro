# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — redaction_api.py (Headend API)
# ───────────────────────────────────────────────────────────────────────────
# Version : 1.1.0
# Dato    : 2026-08-15
# Ændring : Tenant-/rolle-isolation for GDPR redaction (SEC-ZAI-02)
# ═══════════════════════════════════════════════════════════════════════════
"""REST API endpoints for the GDPR redaction workflow.

Security contract:
- all endpoints require an authenticated Headend principal;
- mutating redaction operations require operator or higher;
- capture access is tenant-scoped using the immutable Capture.customer_id where
  available, with the central device-access helper only as a fail-closed legacy
  fallback for pre-tenant captures;
- tenant-scoped list/count queries never aggregate another customer's captures.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Capture, User, get_db

router = APIRouter(prefix="/api/redaction", tags=["redaction"])
log = logging.getLogger(__name__)

_ROLE_LEVEL = {
    "viewer": 10,
    "operator": 20,
    "admin": 30,
    "super_admin": 40,
}


def get_required_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Delegate session validation to Headend's central auth implementation."""
    from main import get_current_user

    user = get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ikke autentificeret",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _require_role(user: User, minimum_role: str) -> None:
    """Fail closed if the authenticated principal lacks the required RBAC level."""
    actual = _ROLE_LEVEL.get(str(getattr(user, "role", "") or ""), -1)
    required = _ROLE_LEVEL[minimum_role]
    if actual < required:
        raise HTTPException(status_code=403, detail="Utilstrækkelige rettigheder")


def _ensure_capture_access(db: Session, user: User, capture: Capture) -> None:
    """Enforce capture tenant isolation before reading or mutating GDPR data.

    Capture.customer_id is the authoritative frozen tenant tag for modern
    captures.  Legacy captures without that tag fall back to the existing
    central device-access policy instead of silently becoming globally visible.
    """
    if getattr(user, "role", None) == "super_admin":
        return

    user_customer_id = getattr(user, "customer_id", None)
    capture_customer_id = getattr(capture, "customer_id", None)

    # Existing Headend semantics allow explicitly global (customer_id=None)
    # administrative/operator principals.  Tenant-bound principals must match
    # the capture's immutable customer tag exactly.
    if capture_customer_id:
        if user_customer_id is not None and str(user_customer_id) != str(capture_customer_id):
            raise HTTPException(status_code=403, detail="Ingen adgang til denne capture")
        return

    # Historical rows may predate frozen capture.customer_id.  Reuse the
    # canonical device visibility policy rather than inventing a second join.
    from main import _ensure_capture_device_access

    _ensure_capture_device_access(db, user, capture.device_id)


def _tenant_scope_query(query, user: User):
    """Apply fail-closed tenant scope to capture collection/count queries."""
    if getattr(user, "role", None) == "super_admin":
        return query
    customer_id = getattr(user, "customer_id", None)
    if customer_id is None:
        # Preserve the existing explicit global-principal semantics.
        return query
    return query.filter(Capture.customer_id == str(customer_id))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class BoundingBox(BaseModel):
    x: int
    y: int
    w: int
    h: int
    confidence: float


class PIIDetections(BaseModel):
    faces: list[BoundingBox] = Field(default_factory=list)
    license_plates: list[BoundingBox] = Field(default_factory=list)
    has_pii: bool = False

    def to_dict(self) -> dict:
        return {
            "faces": [f.model_dump() for f in self.faces],
            "license_plates": [p.model_dump() for p in self.license_plates],
            "has_pii": self.has_pii,
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


def _find_image_path(capture: Capture, base_path: str = "/mnt/SFTP_DATA") -> Path:
    """Find a capture image within configured storage roots."""
    import re

    filename = capture.filename or ""
    device_id = capture.device_id
    storage_roots = os.getenv("SFTP_DATA_ROOT", base_path).split(":")

    for root in storage_roots:
        base = Path(root)
        path_simple = base / device_id / filename
        if path_simple.exists():
            return path_simple

        match = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
        if match:
            yyyy, mm, dd = match.group(1), match.group(2), match.group(3)
            path_date = base / device_id / yyyy / mm / dd / filename
            if path_date.exists():
                return path_date

    raise HTTPException(
        status_code=404,
        detail=f"Image not found for device={device_id}, filename={filename}",
    )


def _update_redaction_status(
    db: Session,
    capture: Capture,
    redaction_status: str,
    has_gdpr_data: Optional[bool] = None,
    detections: Optional[PIIDetections] = None,
    redacted_path: Optional[str] = None,
    redacted_by: str = "auto",
) -> None:
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


@router.post("/analyze/{capture_id}", response_model=AnalyzeResponse)
def analyze_capture(
    capture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Analyse a capture for faces/license plates. Requires operator+."""
    _require_role(current_user, "operator")
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    _ensure_capture_access(db, current_user, capture)

    try:
        import cv2

        image_path = _find_image_path(capture)
        img = cv2.imread(str(image_path))
        if img is None:
            raise HTTPException(status_code=500, detail=f"Failed to load image: {image_path}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        cascade_dir = cv2.data.haarcascades
        face_cascade = cv2.CascadeClassifier(f"{cascade_dir}/haarcascade_frontalface_default.xml")
        plate_cascade = cv2.CascadeClassifier(f"{cascade_dir}/haarcascade_license_plate_rus_16stages.xml")

        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        face_boxes = [
            BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h), confidence=0.8)
            for x, y, w, h in faces
        ]
        plates = plate_cascade.detectMultiScale(gray, 1.1, 4)
        plate_boxes = [
            BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h), confidence=0.7)
            for x, y, w, h in plates
        ]
        detections = PIIDetections(
            faces=face_boxes,
            license_plates=plate_boxes,
            has_pii=bool(face_boxes or plate_boxes),
        )

        if detections.has_pii:
            _update_redaction_status(
                db,
                capture,
                "detected",
                has_gdpr_data=True,
                detections=detections,
            )
            message = f"Detected {len(face_boxes)} faces, {len(plate_boxes)} license plates"
        else:
            _update_redaction_status(
                db,
                capture,
                "analyzed",
                has_gdpr_data=False,
                detections=detections,
            )
            message = "No GDPR data detected"

        db.refresh(capture)
        return AnalyzeResponse(
            capture_id=capture_id,
            redaction_status=capture.redaction_status,
            detections=detections,
            message=message,
        )
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"OpenCV ikke tilgængeligt: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Analyse fejlede for capture %s", capture_id)
        raise HTTPException(status_code=500, detail=f"Analyse fejlede: {exc}")


@router.post("/redact/{capture_id}")
def redact_capture(
    capture_id: int,
    blur_kernel: int = 51,
    blur_sigma: int = 30,
    auto_approve: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Apply redaction to a capture. Requires operator+."""
    _require_role(current_user, "operator")
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    _ensure_capture_access(db, current_user, capture)

    if capture.redaction_status != "detected":
        raise HTTPException(
            status_code=400,
            detail=f"Capture skal have status 'detected' før redaction. Nu: {capture.redaction_status}",
        )

    try:
        import cv2
        import shutil

        image_path = _find_image_path(capture)
        img = cv2.imread(str(image_path))
        if img is None:
            raise HTTPException(status_code=500, detail="Failed to load image")

        detections = capture.gdpr_detections
        if not detections:
            raise HTTPException(status_code=400, detail="Ingen detections at sløre")

        for detected in list(detections.get("faces", [])) + list(detections.get("license_plates", [])):
            x, y, w, h = detected["x"], detected["y"], detected["w"], detected["h"]
            roi = img[y : y + h, x : x + w]
            blurred = cv2.GaussianBlur(roi, (blur_kernel, blur_kernel), blur_sigma)
            img[y : y + h, x : x + w] = blurred

        backup_path = image_path.with_suffix(".original" + image_path.suffix)
        shutil.copy(image_path, backup_path)
        if not cv2.imwrite(str(image_path), img):
            raise HTTPException(status_code=500, detail="Failed to write redacted image")

        # Do not manufacture approval evidence here. auto_approve remains accepted
        # for API compatibility but approval is a separate, authenticated operation.
        _update_redaction_status(
            db,
            capture,
            "redacted",
            redacted_path=str(image_path),
            redacted_by=current_user.username,
        )
        if auto_approve:
            log.warning(
                "Ignoring legacy auto_approve for capture %s; explicit approval is required",
                capture_id,
            )

        return {
            "success": True,
            "message": "Billede sløret; eksplicit godkendelse kræves",
            "redaction_status": "redacted",
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Redaction fejlede for capture %s", capture_id)
        raise HTTPException(status_code=500, detail=f"Redaction fejlede: {exc}")


@router.post("/approve/{capture_id}")
def approve_capture(
    capture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Validate access for explicit approval; no false approval state is emitted."""
    _require_role(current_user, "operator")
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    _ensure_capture_access(db, current_user, capture)

    if capture.redaction_status != "redacted":
        raise HTTPException(
            status_code=400,
            detail=f"Capture skal have status 'redacted'. Nu: {capture.redaction_status}",
        )

    # The current schema has no durable approved_at/approved_by fields. Returning
    # success here would create false security/GDPR evidence. Fail explicitly
    # until the approval-evidence schema is implemented in a dedicated migration.
    raise HTTPException(
        status_code=501,
        detail="Redaction approval kræver durable approved_at/approved_by auditfelter; ikke implementeret endnu",
    )


@router.get("/status/{capture_id}", response_model=RedactionStatusResponse)
def get_redaction_status(
    capture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    _require_role(current_user, "viewer")
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    _ensure_capture_access(db, current_user, capture)

    return RedactionStatusResponse(
        capture_id=capture.id,
        device_id=capture.device_id,
        filename=capture.filename or "",
        redaction_status=capture.redaction_status or "pending",
        has_gdpr_data=capture.has_gdpr_data,
        gdpr_detections=capture.gdpr_detections,
        redacted_at=capture.redacted_at.isoformat() if capture.redacted_at else None,
        redacted_by=capture.redacted_by,
    )


@router.get("/pending", response_model=PendingListResponse)
def get_pending_captures(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    _require_role(current_user, "viewer")

    base_query = _tenant_scope_query(
        db.query(Capture).filter(
            Capture.redaction_status.in_(["pending", "analyzed", "detected"])
        ),
        current_user,
    )
    if status_filter and status_filter != "all":
        base_query = base_query.filter(Capture.redaction_status == status_filter)

    captures = base_query.order_by(Capture.captured_at.desc()).limit(100).all()
    total = base_query.count()

    pending_analysis = _tenant_scope_query(
        db.query(Capture).filter(Capture.redaction_status == "pending"),
        current_user,
    ).count()
    detected_pii = _tenant_scope_query(
        db.query(Capture).filter(
            Capture.redaction_status == "detected",
            Capture.has_gdpr_data.is_(True),
        ),
        current_user,
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
            redacted_by=c.redacted_by,
        )
        for c in captures
    ]
    return PendingListResponse(
        total=total,
        pending_analysis=pending_analysis,
        detected_pii=detected_pii,
        items=items,
    )
