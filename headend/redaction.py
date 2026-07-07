# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — redaction.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Version : 1.0.0
# Dato    : 2026-07-07
# ═══════════════════════════════════════════════════════════════════════════
"""
GDPR redaction workflow for ansigter og nummerplader.

Funktioner:
  - detect_pii(): Detekter ansigter og nummerplader med OpenCV
  - redact_image(): Slører detekterede områder med Gaussian blur
  - redaction_pipeline(): Komplett workflow fra detection → redaction → gem

Krav: UI-010 (GDPR redaction workflow)
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from typing import Optional, List, Tuple, Any
from pathlib import Path

log = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class BoundingBox:
    """Bounding box for detected object."""
    x: int      # Top-left X
    y: int      # Top-left Y
    w: int      # Width
    h: int      # Height
    confidence: float  # Detection confidence (0-1)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "confidence": self.confidence}


@dataclass
class PIIDetections:
    """Detected Personally Identifiable Information."""
    faces: List[BoundingBox]
    license_plates: List[BoundingBox]

    def has_pii(self) -> bool:
        return len(self.faces) > 0 or len(self.license_plates) > 0

    def to_dict(self) -> dict:
        return {
            "faces": [f.to_dict() for f in self.faces],
            "license_plates": [p.to_dict() for p in self.license_plates],
            "has_pii": self.has_pii()
        }


# ── Detection ────────────────────────────────────────────────────────────────

def detect_pii(image_path: Path, cascade_dir: Optional[Path] = None) -> PIIDetections:
    """
    Detekter ansigter og nummerplader i billedet.

    Args:
        image_path: Sti til billedet
        cascade_dir: Sti til OpenCV cascade XML filer (brug /usr/share/opencv4/haarcascades/ som default)

    Returns:
        PIIDetections med fundne objekter
    """
    import cv2
    import numpy as np

    # Default cascade sti for Ubuntu/Debian med opencv-python
    if cascade_dir is None:
        cascade_dir = Path("/usr/share/opencv4/haarcascades/")
        if not cascade_dir.exists():
            # Fallback: try common locations
            for alt in ["/usr/local/share/opencv4/haarcascades/", "/usr/share/opencv/haarcascades/"]:
                if Path(alt).exists():
                    cascade_dir = Path(alt)
                    break

    faces: List[BoundingBox] = []
    plates: List[BoundingBox] = []

    try:
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            log.warning("Kunne ikke læse billede: %s", image_path)
            return PIIDetections(faces=[], license_plates=[])

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Load cascade classifiers
        face_cascade_path = cascade_dir / "haarcascade_frontalface_default.xml"
        plate_cascade_path = cascade_dir / "haarcascade_russian_plate_number.xml"

        # Detect faces
        if face_cascade_path.exists():
            face_cascade = cv2.CascadeClassifier(str(face_cascade_path))
            face_rects = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                maxSize=(400, 400)
            )
            for (x, y, w, h) in face_rects:
                faces.append(BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h), confidence=0.8))

        # Detect license plates
        if plate_cascade_path.exists():
            plate_cascade = cv2.CascadeClassifier(str(plate_cascade_path))
            plate_rects = plate_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 15),
                maxSize=(300, 100)
            )
            for (x, y, w, h) in plate_rects:
                plates.append(BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h), confidence=0.7))

        log.debug("PII detection: %d ansigter, %d nummerplader i %s",
                  len(faces), len(plates), image_path.name)

    except ImportError:
        log.warning("OpenCV ikke tilgængelig - PII detection sprunget")
    except Exception as e:
        log.error("PII detection fejlede for %s: %s", image_path, e)

    return PIIDetections(faces=faces, license_plates=plates)


# ── Redaction ─────────────────────────────────────────────────────────────────

def redact_image(
    image_path: Path,
    detections: PIIDetections,
    output_path: Optional[Path] = None,
    blur_kernel: int = 51,
    blur_sigma: int = 30
) -> Tuple[Path, dict]:
    """
    Slører detekterede ansigter og nummerplader med Gaussian blur.

    Args:
        image_path: Sti til originalbillede
        detections: PIIDetections med objekter der skal sløres
        output_path: Sti til output (hvis None, overskriver original med .redacted suffix)
        blur_kernel: Kernel size for Gaussian blur (skal være ulige, default 51)
        blur_sigma: Sigma for Gaussian blur (default 30)

    Returns:
        (output_path, metadata_dict) hvor metadata indeholder redaction info
    """
    import cv2
    import numpy as np

    if output_path is None:
        output_path = image_path.with_suffix(image_path.suffix + ".redacted" + image_path.suffix)

    try:
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Kunne ikke læse billede: {image_path}")

        redacted_count = 0
        redacted_regions: List[dict] = []

        # Slør hver detektion
        all_detections = [("face", detections.faces), ("plate", detections.license_plates)]

        for label, items in all_detections:
            for bbox in items:
                # Udvid bounding box lidt for at sikre fuld dækning
                padding = int(min(bbox.w, bbox.h) * 0.1)
                x1 = max(0, bbox.x - padding)
                y1 = max(0, bbox.y - padding)
                x2 = min(img.shape[1], bbox.x + bbox.w + padding)
                y2 = min(img.shape[0], bbox.y + bbox.h + padding)

                # Extract region
                region = img[y1:y2, x1:x2]

                # Apply Gaussian blur
                blurred = cv2.GaussianBlur(region, (blur_kernel, blur_kernel), blur_sigma)

                # Replace region
                img[y1:y2, x1:x2] = blurred

                redacted_count += 1
                redacted_regions.append({
                    "type": label,
                    "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    "original_bbox": bbox.to_dict()
                })

        # Gem redacted billede
        cv2.imwrite(str(output_path), img,
                    [cv2.IMWRITE_JPEG_QUALITY, 95, cv2.IMWRITE_PNG_COMPRESSION, 9])

        log.info("Redacted %d regions in %s → %s",
                 redacted_count, image_path.name, output_path.name)

        metadata = {
            "original_path": str(image_path),
            "redacted_path": str(output_path),
            "redaction_method": "opencv_gaussian_blur",
            "blur_kernel": blur_kernel,
            "blur_sigma": blur_sigma,
            "redacted_count": redacted_count,
            "redacted_regions": redacted_regions,
            "detections": detections.to_dict()
        }

        return output_path, metadata

    except Exception as e:
        log.error("Redaction fejlede for %s: %s", image_path, e)
        raise


# ── Pipeline ─────────────────────────────────────────────────────────────────

def redaction_pipeline(
    image_path: Path,
    output_dir: Optional[Path] = None,
    auto_redact: bool = True
) -> dict:
    """
    Komplett redaction pipeline: detection → (valgfri) redaction → metadata.

    Args:
        image_path: Sti til billede
        output_dir: Mappe til redacted billeder (hvis None, samme som original)
        auto_redact: Hvis True, kør automatisk redaction ved detection

    Returns:
        Dict med pipeline resultat: {
            "has_pii": bool,
            "detections": {...},
            "redacted_path": str | None,
            "metadata": {...}
        }
    """
    try:
        # Step 1: Detect PII
        detections = detect_pii(image_path)
        has_pii = detections.has_pii()

        result = {
            "has_pii": has_pii,
            "detections": detections.to_dict(),
            "redacted_path": None,
            "metadata": {
                "original_path": str(image_path),
                "redaction_method": None
            }
        }

        # Step 2: Redact hvis fundet og auto_redact=True
        if has_pii and auto_redact:
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / image_path.name
            else:
                output_path = None

            redacted_path, metadata = redact_image(image_path, detections, output_path)
            result["redacted_path"] = str(redacted_path)
            result["metadata"] = metadata

        return result

    except Exception as e:
        log.error("Redaction pipeline fejlede for %s: %s", image_path, e)
        return {
            "has_pii": None,
            "error": str(e),
            "detections": {"faces": [], "license_plates": [], "has_pii": False}
        }


# ── CLI / Direct execution ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python redaction.py <image_path> [--dry-run]")
        sys.exit(1)

    img_path = Path(sys.argv[1])
    if not img_path.exists():
        print(f"File not found: {img_path}")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv

    result = redaction_pipeline(img_path, auto_redact=not dry_run)

    print(json.dumps(result, indent=2))
