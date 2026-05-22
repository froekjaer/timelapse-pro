#!/usr/bin/env python3
"""
TimeLapse Pro — Timeline + Multi-select + Backend fix patch
===========================================================
Kør fra timelapse-pro roden:
  python3 headend/ai/apply_multiselect_patch.py
"""
import shutil
from pathlib import Path
from datetime import datetime

ROOT           = Path(__file__).parent.parent.parent
MAIN_PY        = ROOT / "headend" / "main.py"
TIMELINE_TSX   = ROOT / "timelapse-ui" / "src" / "components" / "TimelineNavigator.tsx"
DEVICE_TSX     = ROOT / "timelapse-ui" / "src" / "pages" / "DevicePage.tsx"

def backup(path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, path.with_suffix(path.suffix + f".bak_{ts}"))
    print(f"  ✓ Backup: {path.name}.bak_{ts}")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Eksportér CaptureCard fra DevicePage.tsx
# ═══════════════════════════════════════════════════════════════════════════
def patch_export_capturecard(content: str) -> str:
    if "export function CaptureCard" in content:
        print("  · CaptureCard allerede eksporteret")
        return content
    old = "function CaptureCard({ capture, onClick }"
    new = "export function CaptureCard({ capture, onClick }"
    if old in content:
        content = content.replace(old, new, 1)
        print("  ✓ CaptureCard eksporteret")
    else:
        print("  ⚠ CaptureCard ikke fundet")
    return content


# ═══════════════════════════════════════════════════════════════════════════
# 2. TimelineNavigator — brug CaptureCard-grid til dag-billeder
# ═══════════════════════════════════════════════════════════════════════════
def patch_timeline_grid(content: str) -> str:
    if "CaptureCard" in content:
        print("  · TimelineNavigator allerede bruger CaptureCard")
        return content

    # Tilføj import
    old_import = "import { getThumbnailUrl, getApiUrl } from '../api/client'"
    new_import = "import { getThumbnailUrl, getApiUrl } from '../api/client'\nimport { CaptureCard } from '../pages/DevicePage'"
    content = content.replace(old_import, new_import)

    # Tilføj onSelect og lightbox state øverst i komponenten
    old_state = "  const [selFilename, setSelFilename] = useState<string | null>(null)"
    new_state = """  const [selFilename, setSelFilename] = useState<string | null>(null)
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null)
  const [lightboxCaptures, setLightboxCaptures] = useState<Capture[]>([])"""
    content = content.replace(old_state, new_state)

    # Tilføj Lightbox import
    old_import2 = "import { CaptureCard } from '../pages/DevicePage'"
    new_import2 = "import { CaptureCard, Lightbox } from '../pages/DevicePage'"
    content = content.replace(old_import2, new_import2)

    # Erstat dag-grid med CaptureCard-grid
    old_grid = '''              <p className="text-xs text-gray-400 mb-3">{dayCaptures.length} billeder</p>
              <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-1.5">
                {dayCaptures.map(c => {
                  const d   = c.captured_at ? toLocal(c.captured_at) : null
                  const lbl = d ? `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}` : ''
                  return (
                    <button key={c.id} onClick={() => openCapture(c)}
                      className={`relative rounded-lg overflow-hidden border-2 transition-all hover:scale-105 ${selFilename===c.filename ? 'border-sky-400' : 'border-transparent'} ${!c.quality_passed ? 'ring-1 ring-red-400' : ''}`}>
                      <img src={getThumbnailUrl(c.device_id, c.filename)} alt="" className="w-full aspect-video object-cover" />
                      <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-center py-0.5" style={{fontSize:9}}>{lbl}</div>
                    </button>
                  )
                })}
              </div>'''

    new_grid = '''              <p className="text-xs text-gray-400 mb-3">{dayCaptures.length} billeder</p>
              {lightboxIdx !== null && (
                <Lightbox captures={lightboxCaptures} index={lightboxIdx} onClose={() => setLightboxIdx(null)} />
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {dayCaptures.map((c, i) => (
                  <CaptureCard key={c.id} capture={c} onClick={() => {
                    setLightboxCaptures(dayCaptures)
                    setLightboxIdx(i)
                  }} />
                ))}
              </div>'''

    if old_grid in content:
        content = content.replace(old_grid, new_grid)
        print("  ✓ TimelineNavigator dag-grid opdateret til CaptureCard format")
    else:
        print("  ⚠ Dag-grid ikke fundet i TimelineNavigator")
    return content


# ═══════════════════════════════════════════════════════════════════════════
# 3. Backend — fix tag search og QA search med SQL-filtre + højere limit
# ═══════════════════════════════════════════════════════════════════════════
def patch_backend_filters(content: str) -> str:
    # Fix tag search — anvend dato-filter i SQL
    if "TIMELINE_DATE_FILTER_FIXED" in content:
        print("  · Backend dato-filter allerede fixet")
    else:
        # Erstat tag search med SQL-baseret dato-filter
        old = '''    def search_by_tags(
        tags:      str,
        device_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to:   Optional[str] = None,
        limit:     int = 200,
        db: Session = Depends(get_db_fn),
    ):
        """Søg billeder efter AI-tags. ?tags=crane,car"""
        from database import Capture
        import json as _json

        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if not tag_list:
            raise HTTPException(status_code=400, detail="Angiv mindst ét tag")

        q = db.query(Capture).filter(Capture.ai_tags.isnot(None))
        if device_id:
            q = q.filter_by(device_id=device_id)
        captures = q.order_by(Capture.captured_at.desc()).all()

        results = []
        for c in captures:
            try:
                if date_from and c.captured_at and str(c.captured_at.date()) < date_from:
                    continue
                if date_to and c.captured_at and str(c.captured_at.date()) > date_to:
                    continue
                c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
                if any(t in c_tags for t in tag_list):
                    results.append({'''

        new = '''    def search_by_tags(
        tags:         str,
        device_ids:   Optional[str] = None,
        device_id:    Optional[str] = None,
        date_from:    Optional[str] = None,
        date_to:      Optional[str] = None,
        limit:        int = 500,
        db: Session = Depends(get_db_fn),
    ):
        # TIMELINE_DATE_FILTER_FIXED
        """Søg billeder efter AI-tags. ?tags=crane,car&device_ids=TL-xxx,TL-yyy"""
        from database import Capture
        from sqlalchemy import text as _t
        import json as _json
        from datetime import datetime as _dt

        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if not tag_list:
            raise HTTPException(status_code=400, detail="Angiv mindst ét tag")

        q = db.query(Capture).filter(Capture.ai_tags.isnot(None))

        # Device filter — støtter både enkelt og kommaseparerede
        all_device_ids = []
        if device_ids:
            all_device_ids = [d.strip() for d in device_ids.split(",") if d.strip()]
        elif device_id:
            all_device_ids = [device_id]
        if all_device_ids:
            q = q.filter(Capture.device_id.in_(all_device_ids))

        # Dato filter i SQL
        if date_from:
            try:
                q = q.filter(Capture.captured_at >= _dt.fromisoformat(date_from))
            except Exception:
                pass
        if date_to:
            try:
                from datetime import timedelta as _td
                dt_to = _dt.fromisoformat(date_to) + _td(days=1)
                q = q.filter(Capture.captured_at < dt_to)
            except Exception:
                pass

        captures = q.order_by(Capture.captured_at.desc()).limit(limit * 5).all()

        results = []
        for c in captures:
            try:
                c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
                if any(t in c_tags for t in tag_list):
                    results.append({'''

        if old in content:
            content = content.replace(old, new)
            print("  ✓ Tag search filter fixet (SQL-baseret)")
        else:
            print("  ⚠ Tag search endpoint ikke fundet — søgefiltre ikke fixet")

    # Fix QA search — samme SQL-tilgang + multi-device + multi-cause
    if "QA_MULTI_FILTER_FIXED" in content:
        print("  · QA search allerede fixet")
    else:
        old = '''@app.get("/api/ai/qa/search")
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
):'''
        new = '''@app.get("/api/ai/qa/search")
def qa_search(
    # QA_MULTI_FILTER_FIXED
    causes:         Optional[str] = None,
    cause:          Optional[str] = None,
    is_anomaly:     Optional[str] = None,
    alarm:          Optional[str] = None,
    min_confidence: Optional[float] = None,
    device_ids:     Optional[str] = None,
    device_id:      Optional[str] = None,
    date_from:      Optional[str] = None,
    date_to:        Optional[str] = None,
    limit:          int = 500,
    db: Session = Depends(get_db),
):'''
        if old in content:
            content = content.replace(old, new)

        # Fix QA search body to handle multi-cause and multi-device
        old_body = '''    q = db.query(_Cap).filter(_Cap.ai_result.isnot(None))
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
                continue'''
        new_body = '''    from datetime import datetime as _dt2, timedelta as _td2
    q = db.query(_Cap).filter(_Cap.ai_result.isnot(None))

    # Multi-device filter
    all_dev = []
    if device_ids:
        all_dev = [d.strip() for d in device_ids.split(",") if d.strip()]
    elif device_id:
        all_dev = [device_id]
    if all_dev:
        q = q.filter(_Cap.device_id.in_(all_dev))

    # Dato filter i SQL
    if date_from:
        try: q = q.filter(_Cap.captured_at >= _dt2.fromisoformat(date_from))
        except Exception: pass
    if date_to:
        try: q = q.filter(_Cap.captured_at < _dt2.fromisoformat(date_to) + _td2(days=1))
        except Exception: pass

    q = q.order_by(_Cap.captured_at.desc())

    # Multi-cause filter
    all_causes = []
    if causes:
        all_causes = [c.strip() for c in causes.split(",") if c.strip()]
    elif cause:
        all_causes = [cause]

    results = []
    for c in q.limit(limit * 3).all():
        try:
            ai = _j.loads(c.ai_result)
            if all_causes and ai.get("probable_cause") not in all_causes:
                continue
            if is_anomaly == "true" and not ai.get("is_anomaly"):
                continue
            if is_anomaly == "false" and ai.get("is_anomaly"):
                continue
            if alarm == "true" and not ai.get("alarm"):
                continue
            if alarm == "false" and ai.get("alarm"):
                continue'''
        if old_body in content:
            content = content.replace(old_body, new_body)
            print("  ✓ QA search fixet (multi-cause, multi-device, SQL dato-filter)")
        else:
            print("  ⚠ QA search body ikke fundet")
    return content


def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║  TimeLapse Pro — Multi-select + Fix Patch   ║")
    print("╚══════════════════════════════════════════════╝\n")

    print("── DevicePage.tsx — eksportér CaptureCard ──")
    backup(DEVICE_TSX)
    content = DEVICE_TSX.read_text(encoding="utf-8")
    content = patch_export_capturecard(content)
    DEVICE_TSX.write_text(content, encoding="utf-8")
    print()

    print("── TimelineNavigator.tsx ──")
    backup(TIMELINE_TSX)
    content = TIMELINE_TSX.read_text(encoding="utf-8")
    content = patch_timeline_grid(content)
    TIMELINE_TSX.write_text(content, encoding="utf-8")
    print()

    print("── headend/main.py — backend fixes ──")
    backup(MAIN_PY)
    content = MAIN_PY.read_text(encoding="utf-8")
    content = patch_backend_filters(content)
    MAIN_PY.write_text(content, encoding="utf-8")
    print()

    print("═" * 48)
    print("✓ Patches anvendt\n")
    print("Næste skridt:")
    print("  1. Kopier ny TagSearchPage.tsx")
    print("  2. Genstart headend")
    print("  3. Byg UI")


if __name__ == "__main__":
    main()
