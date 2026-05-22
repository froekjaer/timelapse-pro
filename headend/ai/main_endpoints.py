"""
TimeLapse Pro — AI Endpoints til headend/main.py
==================================================
Indsæt disse imports og endpoints i main.py.

IMPORTS — tilføj til toppen af main.py:
─────────────────────────────────────────
from ai.ollama_service import get_ollama_service, OllamaService

ENDPOINTS — indsæt efter eksisterende endpoints i main.py
"""

# ══════════════════════════════════════════════════════════════════════════════
# AI / Ollama endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/ai/status")
def ai_status():
    """
    Tjek om Ollama kører og hvilke modeller der er tilgængelige.
    Bruges af UI til at vise AI-status i dashboard.
    """
    svc = get_ollama_service()
    models = svc.list_models()
    available = svc.is_available()
    return {
        "ollama_running": len(models) > 0,
        "vision_ready":   available,
        "models":         models,
        "endpoint":       "http://localhost:11434",
    }


@app.post("/api/ai/analyze/capture/{capture_id}")
def ai_analyze_capture(capture_id: int, db: Session = Depends(get_db)):
    """
    AI second-opinion på et specifikt capture (via capture_id fra DB).

    Finder billedet på disk via device_id + filename fra captures-tabellen,
    sender til Ollama, og returnerer analyse.

    Fremtidigt: gem resultat i captures-tabellen (ai_result JSON kolonne).
    """
    capture = db.query(Capture).filter_by(id=capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture ikke fundet")

    image_path = _find_image(capture.device_id, capture.filename)
    if not image_path:
        raise HTTPException(
            status_code=404,
            detail=f"Billedfil ikke fundet på disk: {capture.filename}"
        )

    svc = get_ollama_service()
    if not svc.is_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama ikke tilgængelig. Kør: brew services start ollama && ollama pull moondream"
        )

    # Kontekst fra OpenCV til modellen
    context = None
    if capture.blur_score is not None:
        context = (
            f"OpenCV blur_score={capture.blur_score:.1f} (threshold=80, lower=blurrier), "
            f"brightness={capture.brightness_mean:.1f}, "
            f"quality_flag={capture.quality_flag}, "
            f"quality_passed={capture.quality_passed}"
        )

    result = svc.analyze_image(image_path, context=context)

    log.info(
        "AI analyse: capture=%d file=%s cause=%s alarm=%s latency=%dms",
        capture_id, capture.filename,
        result.probable_cause, result.alarm, result.latency_ms,
    )

    return {
        "capture_id":  capture_id,
        "filename":    capture.filename,
        "device_id":   capture.device_id,
        "opencv": {
            "blur_score":      capture.blur_score,
            "brightness_mean": capture.brightness_mean,
            "quality_flag":    capture.quality_flag,
            "quality_passed":  capture.quality_passed,
        },
        "ai": result.as_dict(),
    }


@app.post("/api/ai/analyze/file")
def ai_analyze_file(payload: dict, db: Session = Depends(get_db)):
    """
    AI analyse af et billede via device_id + filename.

    Body: { "device_id": "TL-xxx", "filename": "Frøkjær_...jpg" }

    Bruges til manuel analyse fra UI eller test.
    """
    device_id = payload.get("device_id", "")
    filename  = payload.get("filename", "")
    context   = payload.get("context")   # Valgfri OpenCV-kontekst

    if not device_id or not filename:
        raise HTTPException(status_code=400, detail="device_id og filename er påkrævet")

    image_path = _find_image(device_id, filename)
    if not image_path:
        raise HTTPException(status_code=404, detail=f"Fil ikke fundet: {filename}")

    svc = get_ollama_service()
    if not svc.is_available():
        raise HTTPException(status_code=503, detail="Ollama ikke tilgængelig")

    result = svc.analyze_image(image_path, context=context)

    return {
        "device_id": device_id,
        "filename":  filename,
        "ai":        result.as_dict(),
    }


@app.get("/api/ai/analyze/flagged")
def ai_analyze_flagged(
    limit:     int     = 10,
    device_id: str     = None,
    db: Session = Depends(get_db),
):
    """
    Hent de seneste captures der fejlede OpenCV-tjekket og analysér dem.

    Bruges til batch-gennemgang af problematiske billeder.
    Returnerer maks `limit` resultater (default 10) for ikke at overbelaste Ollama.
    """
    svc = get_ollama_service()
    if not svc.is_available():
        raise HTTPException(status_code=503, detail="Ollama ikke tilgængelig")

    query = db.query(Capture).filter_by(quality_passed=False)
    if device_id:
        query = query.filter_by(device_id=device_id)
    captures = query.order_by(Capture.id.desc()).limit(limit).all()

    if not captures:
        return {"message": "Ingen flagged captures fundet", "results": []}

    results = []
    for cap in captures:
        image_path = _find_image(cap.device_id, cap.filename)
        if not image_path:
            results.append({
                "capture_id": cap.id,
                "filename":   cap.filename,
                "error":      "Fil ikke fundet på disk",
            })
            continue

        context = (
            f"OpenCV: blur={cap.blur_score:.1f}, "
            f"brightness={cap.brightness_mean:.1f}, "
            f"flag={cap.quality_flag}"
        ) if cap.blur_score else None

        ai_result = svc.analyze_image(image_path, context=context)
        results.append({
            "capture_id": cap.id,
            "filename":   cap.filename,
            "device_id":  cap.device_id,
            "captured_at": cap.captured_at.isoformat() if cap.captured_at else None,
            "opencv_flag": cap.quality_flag,
            "ai":         ai_result.as_dict(),
        })

    alarms = sum(1 for r in results if r.get("ai", {}).get("alarm"))
    log.info("AI batch analyse: %d captures, %d alarmer", len(results), alarms)

    return {
        "total":   len(results),
        "alarms":  alarms,
        "results": results,
    }
