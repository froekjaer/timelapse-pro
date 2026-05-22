#!/usr/bin/env python3
"""
TimeLapse Pro — AI Integration Patch Script
============================================
Patcher automatisk:
  - headend/main.py         (trin 2 + 3)
  - timelapse-ui/src/pages/DevicePage.tsx  (trin 4)

Kør fra timelapse-pro roden:
  python headend/ai/apply_patch.py

Scriptet er idempotent — kør det trygt flere gange.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

ROOT       = Path(__file__).parent.parent.parent
MAIN_PY    = ROOT / "headend" / "main.py"
DEVICE_TSX = ROOT / "timelapse-ui" / "src" / "pages" / "DevicePage.tsx"


def backup(path: Path) -> Path:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, dest)
    print(f"  ✓ Backup: {dest.name}")
    return dest


def already_patched(content: str, marker: str) -> bool:
    return marker in content


# ═══════════════════════════════════════════════════════════════════════════
# MAIN.PY PATCHES
# ═══════════════════════════════════════════════════════════════════════════

def patch_main_imports(content: str) -> str:
    """Tilføj AI imports efter eksisterende imports."""
    marker = "# ── AI INTEGRATION ──"
    if already_patched(content, marker):
        print("  · AI imports allerede tilføjet")
        return content

    ai_imports = """
# ── AI INTEGRATION ──────────────────────────────────────────────────────────
from ai.integration import (
    run_ai_migration,
    setup_ai,
    setup_ai_router,
    queue_capture_for_analysis,
    ai_router,
)
"""
    # Indsæt efter sidste import-blok — find første ikke-import linje efter imports
    lines  = content.split("\n")
    insert = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert = i + 1

    lines.insert(insert, ai_imports)
    print("  ✓ AI imports tilføjet")
    return "\n".join(lines)


def patch_startup(content: str) -> str:
    """Tilføj AI migration og setup i startup()."""
    marker = "# ── AI SETUP ──"
    if already_patched(content, marker):
        print("  · AI startup allerede tilføjet")
        return content

    ai_startup = """
    # ── AI SETUP ──────────────────────────────────────────────────────────
    try:
        run_ai_migration(engine)
        setup_ai(get_db, _find_image)
        setup_ai_router(get_db, _find_image)
        app.include_router(ai_router)
        log.info("AI integration klar — Ollama: http://localhost:11434")
    except Exception as _ai_err:
        log.warning("AI integration ikke tilgængelig: %s", _ai_err)
"""
    # Indsæt før slutningen af startup() — find log.info("TimeLapse Pro Headend started
    target = 'log.info("TimeLapse Pro Headend started'
    if target not in content:
        print("  ⚠ Kunne ikke finde startup()-markør — tilføj AI setup manuelt")
        return content

    content = content.replace(target, ai_startup + "    " + target)
    print("  ✓ AI startup tilføjet")
    return content


def patch_receive_capture(content: str) -> str:
    """Tilføj queue_capture_for_analysis efter db.commit() i receive_capture."""
    marker = "# ── AI KØDNING ──"
    if already_patched(content, marker):
        print("  · AI kødning allerede tilføjet")
        return content

    # Find den specifikke db.commit() i receive_capture — efterfulgt af quality log
    old = '''    db.commit()

    quality = "PASS" if req.quality_passed else "FAIL"'''

    new = '''    db.commit()

    # ── AI KØDNING ────────────────────────────────────────────────────────
    try:
        queue_capture_for_analysis(capture.id)
    except Exception:
        pass  # AI er valgfri — aldrig blokér capture-flow

    quality = "PASS" if req.quality_passed else "FAIL"'''

    if old not in content:
        print("  ⚠ Kunne ikke finde receive_capture db.commit() — tilføj kødning manuelt")
        return content

    content = content.replace(old, new)
    print("  ✓ AI kødning tilføjet i receive_capture()")
    return content


def patch_list_captures(content: str) -> str:
    """Tilføj ai_result og ai_analyzed_at i list_captures return-dict."""
    marker = '"ai_result":'
    if already_patched(content, marker):
        print("  · ai_result allerede i captures response")
        return content

    # Find slutningen af capture-dict i list_captures
    old = '            "xmp_written":   c.xmp_written if hasattr(c, \'xmp_written\') else None,'
    new = '''            "xmp_written":   c.xmp_written if hasattr(c, 'xmp_written') else None,
            "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
            "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,'''

    if old not in content:
        # Prøv alternativ markør
        old2 = '"uploaded":      c.uploaded,'
        new2 = '''"uploaded":      c.uploaded,
            "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
            "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,'''
        if old2 in content and old2 not in content.replace(old2, "", 1):
            # Kun første forekomst
            content = content.replace(old2, new2, 1)
            print("  ✓ ai_result tilføjet i list_captures (alternativ markør)")
            return content
        print("  ⚠ Kunne ikke finde list_captures return-dict — tilføj ai_result manuelt")
        return content

    content = content.replace(old, new)
    print("  ✓ ai_result + ai_analyzed_at tilføjet i list_captures()")
    return content


# ═══════════════════════════════════════════════════════════════════════════
# DEVICEPAGE.TSX PATCHES
# ═══════════════════════════════════════════════════════════════════════════

def patch_capture_type(content: str) -> str:
    """Tilføj ai_result og ai_analyzed_at til Capture-type."""
    marker = "ai_result?:"
    if already_patched(content, marker):
        print("  · Capture type allerede udvidet")
        return content

    # Find blur_score i type definition
    old = "  blur_score?:"
    new = "  blur_score?:\n  ai_result?:      string | null\n  ai_analyzed_at?: string | null"
    if old not in content:
        print("  ⚠ Kunne ikke finde Capture type — tilføj ai-felter manuelt")
        return content
    content = content.replace(old, new, 1)
    print("  ✓ Capture type udvidet med ai_result")
    return content


def patch_parse_ai_helper(content: str) -> str:
    """Tilføj parseAI() hjælpefunktion."""
    marker = "function parseAI("
    if already_patched(content, marker):
        print("  · parseAI() allerede tilføjet")
        return content

    helper = """
function parseAI(capture: any): Record<string, any> | null {
  if (!capture.ai_result) return null
  try { return JSON.parse(capture.ai_result) } catch { return null }
}

"""
    # Indsæt før første komponent-funktion
    target = "function CaptureCard("
    if target not in content:
        target = "function Lightbox("
    if target not in content:
        print("  ⚠ Kunne ikke finde indsætningspunkt for parseAI() — tilføj manuelt")
        return content

    content = content.replace(target, helper + target)
    print("  ✓ parseAI() hjælpefunktion tilføjet")
    return content


def patch_capture_card_badge(content: str) -> str:
    """Tilføj AI-badge i CaptureCard ved siden af blur-badge."""
    marker = "// AI-BADGE"
    if already_patched(content, marker):
        print("  · AI badge allerede tilføjet i CaptureCard")
        return content

    # Find blur-badge blokken i CaptureCard
    old = """          <p className={`text-xs font-medium flex-shrink-0 ${capture.blur_score < 80 ? 'text-amber-500' : 'text-gray-400'}`}>
              ⬡ {Math.round(capture.blur_score)}
            </p>"""

    new = """          <p className={`text-xs font-medium flex-shrink-0 ${capture.blur_score < 80 ? 'text-amber-500' : 'text-gray-400'}`}>
              ⬡ {Math.round(capture.blur_score)}
            </p>"""  + """
          {/* AI-BADGE */}
          {(() => {
            const ai = parseAI(capture)
            if (!ai) return null
            if (ai.alarm)      return <span title={ai.description} className="text-xs flex-shrink-0 cursor-help">🚨</span>
            if (ai.is_anomaly) return <span title={ai.description} className="text-xs flex-shrink-0 cursor-help">⚠️</span>
            if (ai.probable_cause === 'ok') return <span title="AI: OK" className="text-[9px] flex-shrink-0 text-emerald-400 font-bold cursor-help">AI✓</span>
            return null
          })()}"""

    if old not in content:
        print("  ⚠ Kunne ikke finde blur-badge i CaptureCard — tilføj AI badge manuelt")
        return content

    content = content.replace(old, new)
    print("  ✓ AI badge tilføjet i CaptureCard")
    return content


def patch_lightbox_metadata(content: str) -> str:
    """Tilføj AI-sektion i Lightbox metadata-panel."""
    marker = "{/* AI ANALYSE */}"
    if already_patched(content, marker):
        print("  · AI metadata sektion allerede tilføjet")
        return content

    ai_section = """
                {/* AI ANALYSE */}
                {(() => {
                  const ai = parseAI(c)
                  const causeLabels: Record<string, string> = {
                    ok: 'OK', condensation_on_lens: 'Kondens på linse',
                    dirty_lens: 'Snavset linse', focus_drift: 'Fokusdrift',
                    camera_moved: 'Kamera flyttet', obstruction: 'Afskærmning',
                    rain_on_lens: 'Regn på linse', sun_flare: 'Solreflektion',
                    night_capture: 'Natkamera', hardware_failure: 'Hardwarefejl',
                    unknown: 'Ukendt',
                  }
                  const actionLabels: Record<string, string> = {
                    none: '—', inspect_camera_housing: 'Tjek kamerahus',
                    clean_lens: 'Rengør linse', check_focus: 'Tjek fokus',
                    reposition_camera: 'Juster kamera',
                    wait_for_conditions: 'Afvent vejr', replace_camera: 'Udskift kamera',
                  }
                  return (
                    <div className="mt-2">
                      <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mb-1.5">🤖 AI Analyse</p>
                      {!ai ? (
                        <p className="text-white/30 text-xs italic">Ikke analyseret endnu</p>
                      ) : (
                        <>
                          <MR l="Status" v={
                            <span className={`font-medium ${ai.alarm ? 'text-red-400' : ai.is_anomaly ? 'text-amber-400' : 'text-emerald-400'}`}>
                              {ai.alarm ? '🚨 ' : ai.is_anomaly ? '⚠️ ' : '✓ '}
                              {causeLabels[ai.probable_cause] ?? ai.probable_cause}
                            </span>
                          } />
                          <MR l="Konfidence" v={`${Math.round((ai.confidence ?? 0) * 100)}%`} />
                          <MR l="Beskrivelse" v={<span className="text-white/60 text-[10px] leading-tight">{ai.description}</span>} />
                          {ai.action && ai.action !== 'none' && (
                            <MR l="Handling" v={<span className="text-amber-300">{actionLabels[ai.action] ?? ai.action}</span>} />
                          )}
                          <MR l="Model" v={<span className="text-white/40 text-[10px]">{ai.model}{ai.used_thumbnail ? ' · thumbnail' : ''}</span>} />
                          {c.ai_analyzed_at && (
                            <MR l="Analyseret" v={
                              <span className="text-white/30 text-[10px]">
                                {new Date(c.ai_analyzed_at).toLocaleString('da-DK', {timeZone: getTz(), day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'})}
                              </span>
                            } />
                          )}
                        </>
                      )}
                    </div>
                  )
                })()}
"""

    # Indsæt efter <MR l="Størrelse" blokken
    old = "                <MR l=\"Størrelse\" v={c.filesize_mb"
    if old not in content:
        # Prøv alternativ
        old = '<MR l="Størrelse"'

    if old not in content:
        print("  ⚠ Kunne ikke finde Størrelse-række i Lightbox — tilføj AI sektion manuelt")
        return content

    # Find linjen og indsæt efter den
    lines  = content.split("\n")
    insert = -1
    for i, line in enumerate(lines):
        if '<MR l="Størrelse"' in line or "l=\"Størrelse\"" in line:
            insert = i + 1
            break

    if insert == -1:
        print("  ⚠ Kunne ikke finde indsætningspunkt — tilføj AI sektion manuelt")
        return content

    lines.insert(insert, ai_section)
    print("  ✓ AI metadata sektion tilføjet i Lightbox")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║  TimeLapse Pro — AI Integration Patch       ║")
    print("╚══════════════════════════════════════════════╝\n")

    errors = []

    # ── main.py ──────────────────────────────────────────────────────────────
    print("── headend/main.py ──")
    if not MAIN_PY.exists():
        print(f"  ✗ Ikke fundet: {MAIN_PY}")
        errors.append("main.py ikke fundet")
    else:
        backup(MAIN_PY)
        content = MAIN_PY.read_text(encoding="utf-8")
        content = patch_main_imports(content)
        content = patch_startup(content)
        content = patch_receive_capture(content)
        content = patch_list_captures(content)
        MAIN_PY.write_text(content, encoding="utf-8")
        print("  ✓ main.py gemt\n")

    # ── DevicePage.tsx ────────────────────────────────────────────────────────
    print("── timelapse-ui/src/pages/DevicePage.tsx ──")
    if not DEVICE_TSX.exists():
        print(f"  ✗ Ikke fundet: {DEVICE_TSX}")
        errors.append("DevicePage.tsx ikke fundet")
    else:
        backup(DEVICE_TSX)
        content = DEVICE_TSX.read_text(encoding="utf-8")
        content = patch_capture_type(content)
        content = patch_parse_ai_helper(content)
        content = patch_capture_card_badge(content)
        content = patch_lightbox_metadata(content)
        DEVICE_TSX.write_text(content, encoding="utf-8")
        print("  ✓ DevicePage.tsx gemt\n")

    # ── Resultat ──────────────────────────────────────────────────────────────
    print("═" * 48)
    if errors:
        print(f"⚠  Færdig med {len(errors)} advarsel(er):")
        for e in errors:
            print(f"   - {e}")
    else:
        print("✓  Alle patches anvendt")
        print("\nNæste skridt:")
        print("  1. Genstart headend:  sudo launchctl unload && sudo launchctl load \\")
        print("       /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist")
        print("  2. Byg UI:            cd timelapse-ui && npm run build")
        print("  3. Tjek AI status:    curl http://localhost:8000/api/ai/status")
    print()


if __name__ == "__main__":
    main()
