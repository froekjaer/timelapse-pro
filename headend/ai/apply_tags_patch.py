#!/usr/bin/env python3
"""
TimeLapse Pro — Tags Feature Patch
====================================
Patcher:
  - headend/ai/integration.py  (ai_tags migration + søgeendpoints)
  - headend/main.py             (ai_tags i captures responses)

Kør fra timelapse-pro roden:
  python headend/ai/apply_tags_patch.py
"""
import shutil
from pathlib import Path
from datetime import datetime

ROOT         = Path(__file__).parent.parent.parent
INTEGRATION  = ROOT / "headend" / "ai" / "integration.py"
MAIN_PY      = ROOT / "headend" / "main.py"


def backup(path: Path) -> None:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, dest)
    print(f"  ✓ Backup: {dest.name}")


def patch_integration(content: str) -> str:
    marker = '"ai_tags"'
    if marker in content:
        print("  · ai_tags migration allerede tilføjet")
    else:
        old = '        ("ai_analyzed_at", "DATETIME"),\n    ]'
        new = '        ("ai_analyzed_at", "DATETIME"),\n        ("ai_tags",        "TEXT"),\n    ]'
        if old in content:
            content = content.replace(old, new)
            print("  ✓ ai_tags tilføjet til migration")
        else:
            print("  ⚠ Migration-blok ikke fundet")

    # Tilføj søgeendpoints i setup_ai_router
    if "/tags/search" in content:
        print("  · Søgeendpoints allerede tilføjet")
    else:
        search_endpoint = '''
    @ai_router.get("/tags/search")
    def search_by_tags(
        tags:      str,
        device_id: Optional[str] = None,
        limit:     int = 50,
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
                c_tags = _json.loads(c.ai_tags) if c.ai_tags else []
                if any(t in c_tags for t in tag_list):
                    results.append({
                        "id":             c.id,
                        "device_id":      c.device_id,
                        "filename":       c.filename,
                        "captured_at":    c.captured_at.isoformat() if c.captured_at else None,
                        "tags":           c_tags,
                        "blur_score":     c.blur_score,
                        "quality_passed": c.quality_passed,
                        "ai_result":      c.ai_result,
                    })
            except Exception:
                pass
            if len(results) >= limit:
                break

        return {"query": tag_list, "total": len(results), "results": results}

    @ai_router.get("/tags/all")
    def all_tags(device_id: Optional[str] = None, db: Session = Depends(get_db_fn)):
        """Returner alle kendte tags med antal. Til UI søgeforslag og tag-cloud."""
        from database import Capture
        import json as _json
        from collections import Counter

        q = db.query(Capture.ai_tags).filter(Capture.ai_tags.isnot(None))
        if device_id:
            q = q.filter(Capture.device_id == device_id)

        tag_counter: Counter = Counter()
        rows = q.all()
        for (tags_json,) in rows:
            try:
                for t in _json.loads(tags_json):
                    tag_counter[t] += 1
            except Exception:
                pass

        return {
            "total_tagged": len(rows),
            "tags": [{"tag": t, "count": c} for t, c in tag_counter.most_common(100)],
        }
'''
        # Indsæt før slutningen af setup_ai_router
        old = "\n    @ai_router.get(\"/flagged\")"
        if old in content:
            content = content.replace(old, search_endpoint + old)
            print("  ✓ Søgeendpoints tilføjet")
        else:
            print("  ⚠ Indsætningspunkt ikke fundet — tilføj endpoints manuelt")

    return content


def patch_main(content: str) -> str:
    patched = 0

    # Patch 1: Kalender-endpoint
    if '"ai_tags"' in content:
        print("  · ai_tags allerede i captures responses")
        return content

    old1 = '''                "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
                "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
            }
            for c in captures
        ]'''
    new1 = '''                "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
                "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
                "ai_tags":        json.loads(c.ai_tags) if hasattr(c, 'ai_tags') and c.ai_tags else None,
            }
            for c in captures
        ]'''
    if old1 in content:
        content = content.replace(old1, new1)
        patched += 1
        print("  ✓ ai_tags tilføjet i kalender-endpoint")

    # Patch 2: Admin captures endpoint
    old2 = '''            "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
            "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
        }
        for c in captures
    ]'''
    new2 = '''            "ai_result":      c.ai_result if hasattr(c, 'ai_result') else None,
            "ai_analyzed_at": c.ai_analyzed_at.isoformat() if hasattr(c, 'ai_analyzed_at') and c.ai_analyzed_at else None,
            "ai_tags":        json.loads(c.ai_tags) if hasattr(c, 'ai_tags') and c.ai_tags else None,
        }
        for c in captures
    ]'''
    if old2 in content:
        content = content.replace(old2, new2)
        patched += 1
        print("  ✓ ai_tags tilføjet i admin captures endpoint")

    if patched == 0:
        print("  ⚠ Ingen captures endpoints fundet — check main.py manuelt")

    return content


def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║  TimeLapse Pro — Tags Feature Patch         ║")
    print("╚══════════════════════════════════════════════╝\n")

    print("── headend/ai/integration.py ──")
    if not INTEGRATION.exists():
        print(f"  ✗ Ikke fundet: {INTEGRATION}")
    else:
        backup(INTEGRATION)
        content = INTEGRATION.read_text(encoding="utf-8")
        content = patch_integration(content)
        INTEGRATION.write_text(content, encoding="utf-8")
        print("  ✓ integration.py gemt\n")

    print("── headend/main.py ──")
    if not MAIN_PY.exists():
        print(f"  ✗ Ikke fundet: {MAIN_PY}")
    else:
        backup(MAIN_PY)
        content = MAIN_PY.read_text(encoding="utf-8")
        content = patch_main(content)
        MAIN_PY.write_text(content, encoding="utf-8")
        print("  ✓ main.py gemt\n")

    print("═" * 48)
    print("✓ Patches anvendt\n")
    print("Næste skridt:")
    print("  1. Tilføj ai_tags til PostgreSQL:")
    print("     psql timelapse_db -c \"ALTER TABLE captures ADD COLUMN IF NOT EXISTS ai_tags TEXT;\"")
    print("  2. Genstart headend:")
    print("     sudo launchctl unload && load /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist")
    print("  3. Kør tag backfill (i baggrunden, ~8 timer for 21.000 billeder):")
    print("     nohup env DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \\")
    print("       SFTP_BASE=/Volumes/data/timelapse-incoming \\")
    print("       python headend/ai/backfill_tags.py > /tmp/ai_tags.log 2>&1 &")
    print("  4. Test søgning:")
    print("     curl \"http://localhost:8000/api/ai/tags/search?tags=crane\"")
    print()


if __name__ == "__main__":
    main()
