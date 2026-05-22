#!/usr/bin/env python3
"""
TimeLapse Pro — Lightbox export + QA søgning patch
====================================================
Kør fra timelapse-pro roden:
  python3 headend/ai/apply_lightbox_qa_patch.py
"""
import shutil, re
from pathlib import Path
from datetime import datetime

ROOT       = Path(__file__).parent.parent.parent
DEVICE_TSX = ROOT / "timelapse-ui" / "src" / "pages" / "DevicePage.tsx"
MAIN_PY    = ROOT / "headend" / "main.py"

def backup(path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, path.with_suffix(path.suffix + f".bak_{ts}"))
    print(f"  ✓ Backup: {path.name}.bak_{ts}")

# ── 1. Eksportér Lightbox fra DevicePage.tsx ──────────────────────────────────
def patch_lightbox_export(content: str) -> str:
    if "export function Lightbox" in content:
        print("  · Lightbox allerede eksporteret")
        return content

    old = "function Lightbox({ captures, index, onClose }"
    new = "export function Lightbox({ captures, index, onClose }"
    if old in content:
        content = content.replace(old, new, 1)
        print("  ✓ Lightbox eksporteret fra DevicePage.tsx")
    else:
        print("  ⚠ Lightbox funktion ikke fundet")
    return content

# ── 2. QA-søgning endpoint i main.py ─────────────────────────────────────────
def patch_qa_search(content: str) -> str:
    if "/api/ai/qa/search" in content:
        print("  · QA search endpoint allerede tilføjet")
        return content

    old = "@app.get(\"/api/admin/notifications\")"
    new = '''@app.get("/api/ai/qa/search")
def qa_search(
    cause:          Optional[str] = None,
    is_anomaly:     Optional[bool] = None,
    alarm:          Optional[bool] = None,
    min_confidence: Optional[float] = None,
    device_id:      Optional[str] = None,
    date_from:      Optional[str] = None,
    date_to:        Optional[str] = None,
    limit:          int = 200,
    db: Session = Depends(get_db),
):
    """
    Søg captures baseret på QA/AI-analyse resultater.
    ?cause=condensation_on_lens&is_anomaly=true&min_confidence=0.5
    """
    from database import Capture as _Cap
    import json as _j

    q = db.query(_Cap).filter(_Cap.ai_result.isnot(None))
    if device_id:
        q = q.filter_by(device_id=device_id)
    q = q.order_by(_Cap.captured_at.desc())

    results = []
    for c in q.all():
        try:
            if date_from and c.captured_at and str(c.captured_at.date()) < date_from:
                continue
            if date_to and c.captured_at and str(c.captured_at.date()) > date_to:
                continue
            ai = _j.loads(c.ai_result)
            if cause and ai.get("probable_cause") != cause:
                continue
            if is_anomaly is not None and bool(ai.get("is_anomaly")) != is_anomaly:
                continue
            if alarm is not None and bool(ai.get("alarm")) != alarm:
                continue
            if min_confidence is not None and float(ai.get("confidence", 0)) < min_confidence:
                continue
            results.append({
                "id":             c.id,
                "device_id":      c.device_id,
                "filename":       c.filename,
                "captured_at":    c.captured_at.isoformat() if c.captured_at else None,
                "quality_passed": c.quality_passed,
                "blur_score":     c.blur_score,
                "brightness":     c.brightness_mean,
                "filesize_mb":    round(c.filesize / 1e6, 1) if c.filesize else None,
                "uploaded":       c.uploaded,
                "ai_result":      c.ai_result,
                "ai_tags":        _j.loads(c.ai_tags) if c.ai_tags else None,
            })
        except Exception:
            pass
        if len(results) >= limit:
            break

    return {"total": len(results), "results": results}

@app.get("/api/admin/notifications")'''

    if old in content:
        content = content.replace(old, new)
        print("  ✓ QA search endpoint tilføjet")
    else:
        print("  ⚠ QA search indsætningspunkt ikke fundet")
    return content


def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║  TimeLapse Pro — Lightbox + QA Search Patch ║")
    print("╚══════════════════════════════════════════════╝\n")

    print("── DevicePage.tsx ──")
    backup(DEVICE_TSX)
    content = DEVICE_TSX.read_text(encoding="utf-8")
    content = patch_lightbox_export(content)
    DEVICE_TSX.write_text(content, encoding="utf-8")
    print()

    print("── headend/main.py ──")
    backup(MAIN_PY)
    content = MAIN_PY.read_text(encoding="utf-8")
    content = patch_qa_search(content)
    MAIN_PY.write_text(content, encoding="utf-8")
    print()

    print("═" * 48)
    print("✓ Patches anvendt")
    print("\nNæste skridt:")
    print("  1. Kopier ny TagSearchPage.tsx")
    print("  2. Genstart headend")
    print("  3. Byg UI")


if __name__ == "__main__":
    main()
