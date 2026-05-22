#!/usr/bin/env python3
"""
TimeLapse Pro — Tag Search + QA Rename Patch
=============================================
Patcher:
  1. headend/main.py       — bulk-tags endpoint + dato-filter på tag-søgning
  2. timelapse-ui/src/pages/DevicePage.tsx  — QA rename + tags i CaptureCard
  3. timelapse-ui/src/App.tsx              — TagSearchPage route
  4. timelapse-ui/src/components/Navbar.tsx — Tag søgning link (valgfrit)

Kør fra timelapse-pro roden:
  python3 headend/ai/apply_tags_search_patch.py
"""
import shutil
from pathlib import Path
from datetime import datetime

ROOT       = Path(__file__).parent.parent.parent
MAIN_PY    = ROOT / "headend" / "main.py"
DEVICE_TSX = ROOT / "timelapse-ui" / "src" / "pages" / "DevicePage.tsx"
APP_TSX    = ROOT / "timelapse-ui" / "src" / "App.tsx"
NAVBAR_TSX = ROOT / "timelapse-ui" / "src" / "components" / "Navbar.tsx"

def backup(path: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, dest)
    print(f"  ✓ Backup: {dest.name}")


# ═══════════════════════════════════════════════════════════════════════════
# 1. main.py — bulk-tags endpoint + dato-filter
# ═══════════════════════════════════════════════════════════════════════════

def patch_main(content: str) -> str:

    # Bulk tags endpoint
    if "/captures/bulk-tags" in content:
        print("  · bulk-tags allerede tilføjet")
    else:
        old = '@app.get("/api/admin/notifications")'
        new = '''@app.post("/api/captures/bulk-tags")
def bulk_update_tags(payload: dict, db: Session = Depends(get_db)):
    """
    Bulk opdater tags på en liste af captures.
    Body: {"capture_ids": [1,2,3], "add_tags": ["tag1"], "remove_tags": ["tag2"]}
    """
    from database import Capture as _Cap
    import json as _j
    from ai.integration import update_sidecar_with_ai
    capture_ids = payload.get("capture_ids", [])
    add_tags    = [t.lower().strip() for t in payload.get("add_tags", [])]
    remove_tags = [t.lower().strip() for t in payload.get("remove_tags", [])]

    updated = 0
    for cid in capture_ids:
        cap = db.query(_Cap).filter_by(id=cid).first()
        if not cap:
            continue
        tags = _j.loads(cap.ai_tags) if cap.ai_tags else []
        tags = [t for t in tags if t not in remove_tags]
        tags = list(dict.fromkeys(tags + [t for t in add_tags if t not in tags]))
        cap.ai_tags = _j.dumps(tags, ensure_ascii=False)
        updated += 1
    db.commit()
    return {"updated": updated}

@app.put("/api/captures/{capture_id}/tags")
def update_capture_tags(capture_id: int, payload: dict, db: Session = Depends(get_db)):
    """Opdater tags på ét capture. Body: {"tags": ["tag1", "tag2"]}"""
    from database import Capture as _Cap
    import json as _j
    cap = db.query(_Cap).filter_by(id=capture_id).first()
    if not cap:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")
    tags = [t.lower().strip() for t in payload.get("tags", [])]
    cap.ai_tags = _j.dumps(tags, ensure_ascii=False)
    db.commit()
    return {"status": "ok", "tags": tags}

@app.get("/api/admin/notifications")'''
        if old in content:
            content = content.replace(old, new)
            print("  ✓ bulk-tags + single-tag endpoints tilføjet")
        else:
            print("  ⚠ Indsætningspunkt for bulk-tags ikke fundet")

    # Tilføj dato-filter til /api/ai/tags/search
    if "date_from" in content:
        print("  · Dato-filter allerede tilføjet")
    else:
        old = '''    results = []
    for c in captures:
        try:
            c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
            if any(t in c_tags for t in tag_list):
                results.append({'''
        new = '''    # Dato-filter
    if date_from := db.execute(text("SELECT 1")).fetchone() and False: pass  # placeholder

    results = []
    for c in captures:
        try:
            # Dato-filter
            if date_from and c.captured_at and str(c.captured_at.date()) < date_from:
                continue
            if date_to and c.captured_at and str(c.captured_at.date()) > date_to:
                continue
            c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
            if any(t in c_tags for t in tag_list):
                results.append({'''

        # Mere præcis tilgang — tilføj parametre til search endpoint
        old2 = '''    def search_by_tags(
        tags:      str,
        device_id: Optional[str] = None,
        limit:     int = 50,
        db: Session = Depends(get_db_fn),
    ):'''
        new2 = '''    def search_by_tags(
        tags:      str,
        device_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to:   Optional[str] = None,
        limit:     int = 200,
        db: Session = Depends(get_db_fn),
    ):'''
        if old2 in content:
            content = content.replace(old2, new2)
            print("  ✓ Dato-parametre tilføjet til tag-søgning")

        # Tilføj dato-filter i løkken
        old3 = '''            c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
                if any(t in c_tags for t in tag_list):'''
        new3 = '''            if date_from and c.captured_at and str(c.captured_at.date()) < date_from:
                continue
            if date_to and c.captured_at and str(c.captured_at.date()) > date_to:
                continue
            c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
                if any(t in c_tags for t in tag_list):'''
        if old3 in content:
            content = content.replace(old3, new3)
            print("  ✓ Dato-filter tilføjet i søge-løkken")

    return content


# ═══════════════════════════════════════════════════════════════════════════
# 2. DevicePage.tsx — QA rename + tags i CaptureCard
# ═══════════════════════════════════════════════════════════════════════════

def patch_device_tsx(content: str) -> str:

    # QA rename: AI Analyse → QA
    qa_renames = [
        ('🤖 AI Analyse',        '🔬 QA'),
        ('"AI: OK"',             '"QA: OK"'),
        ('"AI✓"',               '"QA✓"'),
        ('AI✓',                  'QA✓'),
        ('"Ikke analyseret endnu"', '"Ikke QA-analyseret endnu"'),
        ('AI badge',              'QA badge'),
        ('AI BADGE',              'QA BADGE'),
        ('{/* AI-BADGE */}',      '{/* QA-BADGE */}'),
        ('{/* AI ANALYSE */}',    '{/* QA ANALYSE */}'),
    ]
    renamed = 0
    for old, new in qa_renames:
        if old in content:
            content = content.replace(old, new)
            renamed += 1
    if renamed:
        print(f"  ✓ {renamed} QA-omdøbninger i DevicePage.tsx")
    else:
        print("  · QA-omdøbninger allerede anvendt")

    # Tilføj tags i CaptureCard — under tid/blur-linjen
    if "ai_tags" in content and "tags.slice" in content:
        print("  · Tags allerede i CaptureCard")
    else:
        old = '''        <div className="border-t border-gray-100 pt-1 mt-1">
              <p className="text-xs font-bold text-gray-900 leading-tight truncate">{customer}</p>'''
        new = '''        {capture.ai_tags && capture.ai_tags.length > 0 && (
              <div className="flex flex-wrap gap-0.5 mb-1">
                {(capture.ai_tags as string[]).slice(0, 3).map((t: string) => (
                  <span key={t} className="text-[9px] bg-gray-100 text-gray-500 px-1 py-0.5 rounded-full">#{t}</span>
                ))}
                {capture.ai_tags.length > 3 && (
                  <span className="text-[9px] text-gray-400">+{capture.ai_tags.length - 3}</span>
                )}
              </div>
            )}
            <div className="border-t border-gray-100 pt-1 mt-1">
              <p className="text-xs font-bold text-gray-900 leading-tight truncate">{customer}</p>'''
        if old in content:
            content = content.replace(old, new)
            print("  ✓ Tags tilføjet i CaptureCard")
        else:
            print("  ⚠ CaptureCard tags indsætningspunkt ikke fundet")

    # Tags i Timeline (TimelineNavigator dagsbilleder)
    # Timeline bruger en anden komponent — skippes her, håndteres i TimelineNavigator patch

    return content


# ═══════════════════════════════════════════════════════════════════════════
# 3. App.tsx — tilføj TagSearchPage route
# ═══════════════════════════════════════════════════════════════════════════

def patch_app_tsx(content: str) -> str:
    if "TagSearchPage" in content:
        print("  · TagSearchPage allerede i App.tsx")
        return content

    old_import = "import { SystemAdminPage } from './pages/SystemAdminPage'"
    new_import = "import { SystemAdminPage } from './pages/SystemAdminPage'\nimport { TagSearchPage } from './pages/TagSearchPage'"
    old_route  = '<Route path="/system-admin" element={<SystemAdminPage />} />'
    new_route  = '<Route path="/system-admin" element={<SystemAdminPage />} />\n            <Route path="/tags" element={<TagSearchPage />} />'

    if old_import in content:
        content = content.replace(old_import, new_import).replace(old_route, new_route)
        print("  ✓ TagSearchPage route tilføjet i App.tsx")
    else:
        print("  ⚠ App.tsx import ikke fundet")
    return content


# ═══════════════════════════════════════════════════════════════════════════
# 4. Navbar — tilføj Tag søgning link
# ═══════════════════════════════════════════════════════════════════════════

def patch_navbar(content: str) -> str:
    if "/tags" in content:
        print("  · Tag-link allerede i Navbar")
        return content

    # Find Tag import og tilføj Tag icon
    if "Tag" not in content:
        content = content.replace("import {", "import { Tag,", 1)

    # Tilføj link ved siden af andre nav-links
    old = 'to="/settings"'
    # Find settings-linket og tilføj tags-link før det
    idx = content.find('to="/settings"')
    if idx == -1:
        print("  ⚠ Settings-link ikke fundet i Navbar")
        return content

    # Find starten af den omgivende <Link> eller <NavLink>
    link_start = content.rfind('<', 0, idx)
    before = content[:link_start]
    after  = content[link_start:]

    tag_link = '''<Link to="/tags" className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors">
              <Tag className="w-4 h-4" />
              Tags
            </Link>
            '''
    content = before + tag_link + after
    print("  ✓ Tags-link tilføjet i Navbar")
    return content


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║  TimeLapse Pro — Tag Search + QA Patch      ║")
    print("╚══════════════════════════════════════════════╝\n")

    # main.py
    print("── headend/main.py ──")
    backup(MAIN_PY)
    content = MAIN_PY.read_text(encoding="utf-8")
    content = patch_main(content)
    MAIN_PY.write_text(content, encoding="utf-8")
    print("  ✓ main.py gemt\n")

    # DevicePage.tsx
    print("── DevicePage.tsx ──")
    backup(DEVICE_TSX)
    content = DEVICE_TSX.read_text(encoding="utf-8")
    content = patch_device_tsx(content)
    DEVICE_TSX.write_text(content, encoding="utf-8")
    print("  ✓ DevicePage.tsx gemt\n")

    # App.tsx
    print("── App.tsx ──")
    backup(APP_TSX)
    content = APP_TSX.read_text(encoding="utf-8")
    content = patch_app_tsx(content)
    APP_TSX.write_text(content, encoding="utf-8")
    print("  ✓ App.tsx gemt\n")

    # Navbar.tsx
    if NAVBAR_TSX.exists():
        print("── Navbar.tsx ──")
        backup(NAVBAR_TSX)
        content = NAVBAR_TSX.read_text(encoding="utf-8")
        content = patch_navbar(content)
        NAVBAR_TSX.write_text(content, encoding="utf-8")
        print("  ✓ Navbar.tsx gemt\n")

    print("═" * 48)
    print("✓ Patches anvendt\n")
    print("Næste skridt:")
    print("  1. Kopier TagSearchPage.tsx til timelapse-ui/src/pages/")
    print("  2. Genstart headend")
    print("  3. Byg UI: cd timelapse-ui && /opt/homebrew/Cellar/node/25.9.0_2/bin/npm run build")
    print("  4. Find siden via navigationsmenuen → Tags\n")


if __name__ == "__main__":
    main()
