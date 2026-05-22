"""
TimeLapse Pro — AI Router
==========================
Central indgang til alle AI-funktioner i systemet.

Orkestrerer:
  1. OllamaVisionService   → billed-analyse, tags, change detection
  2. TagRepository         → vokabular, krydsreference
  3. AnalysisRepository    → gem analyse-resultat
  4. GDPRManager           → gem GDPR-detektioner (isoleret)
  5. SIEMAnalyser          → log-korrelation og hændelsesanalyse
  6. CMDBEnricher          → device-helbred og vedligeholdsplanlægning

Brug:
  router = AIRouter(db_session_factory, gdpr_db_session_factory)

  # Analysér ét billede
  result = await router.analyse_capture(capture_id=123, image_path=Path(...))

  # Kør alle ventende analyser
  stats = await router.run_pending_analyses(limit=20)

  # SIEM
  event = router.siem.analyse_heartbeats(...)

  # CMDB
  assessment = router.cmdb.assess_device(...)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

from ollama_service import OllamaVisionService, ImageAnalysisResult
from text_services import SIEMAnalyser, CMDBEnricher, SIEMEvent, CMDBAssessment
from repositories import CaptureRepository, TagRepository, AnalysisRepository
from gdpr_manager import GDPRManager

log = logging.getLogger(__name__)


# =============================================================================
# RESULTAT-DATAKLASSE
# =============================================================================

@dataclass
class AnalyseResult:
    capture_id:   int
    analysis_id:  int
    success:      bool
    duration_ms:  int
    tag_count:    int
    new_tag_count: int
    change_detected: bool
    has_gdpr_data: bool
    error:        Optional[str] = None


@dataclass
class BatchStats:
    processed:    int
    succeeded:    int
    failed:       int
    total_ms:     int
    new_tags_found: int
    gdpr_flags:   int


# =============================================================================
# AI ROUTER
# =============================================================================

class AIRouter:
    """
    Eneste indgang til alle AI-operationer.

    db_factory:       callable → Session (normale DB-rettigheder)
    gdpr_db_factory:  callable → Session (timelapse_gdpr_admin rettigheder)
    image_base_path:  rod-sti til billedarkivet
    """

    def __init__(
        self,
        db_factory:      Callable,
        gdpr_db_factory: Callable,
        image_base_path: Path = Path("/data/timelapse"),
        ollama_url:      str  = "http://localhost:11434",
    ):
        self._db_factory      = db_factory
        self._gdpr_db_factory = gdpr_db_factory
        self.image_base_path  = Path(image_base_path)

        # Services
        self._vision = OllamaVisionService(base_url=ollama_url)
        self.siem    = SIEMAnalyser(base_url=ollama_url)
        self.cmdb    = CMDBEnricher(base_url=ollama_url)

    # ── Enkelt-capture analyse ────────────────────────────────────────────────

    def analyse_capture(
        self,
        capture_id:   int,
        image_path:   Path | str,
        location_id:  Optional[str] = None,
        force_reanalysis: bool = False,
    ) -> AnalyseResult:
        """
        Fuld analyse af ét capture:
          1. Hent vokabular fra DB
          2. Find referencebillede (change detection)
          3. Kald vision-model
          4. Gem analyse + tags
          5. Gem GDPR-data (isoleret)

        Springer over hvis analyse allerede eksisterer (medmindre force_reanalysis).
        """
        import time
        start = time.monotonic()
        db = next(self._db_factory())

        try:
            tag_repo      = TagRepository(db)
            analysis_repo = AnalysisRepository(db)
            capture_repo  = CaptureRepository(db)

            # Tjek om analyse allerede eksisterer
            if not force_reanalysis:
                existing = analysis_repo.get_analysis_for_capture(capture_id)
                if existing:
                    log.debug("Capture %d er allerede analyseret, springer over", capture_id)
                    return AnalyseResult(
                        capture_id=capture_id, analysis_id=existing["id"],
                        success=True, duration_ms=0, tag_count=0,
                        new_tag_count=0, change_detected=existing.get("change_detected", False),
                        has_gdpr_data=existing.get("has_gdpr_data", False),
                    )

            # Hent vokabular
            vocab_by_cat   = tag_repo.get_approved_by_category()
            approved_set   = set(tag_repo.get_approved_tags())

            # Find referencebillede
            reference_path: Optional[Path] = None
            reference_cid:  Optional[int]  = None
            if location_id:
                ref_cid = analysis_repo.get_reference_capture_id(capture_id, location_id)
                if ref_cid:
                    ref_capture = capture_repo.get_by_id(ref_cid)
                    if ref_capture:
                        ref_path = self._resolve_image_path(ref_capture.filename)
                        if ref_path and ref_path.exists():
                            reference_path = ref_path
                            reference_cid  = ref_cid

            # Kald vision-model
            image_path = Path(image_path)
            if not image_path.exists():
                image_path = self._resolve_image_path(str(image_path))
                if not image_path or not image_path.exists():
                    raise FileNotFoundError(f"Billede ikke fundet: {image_path}")

            result: ImageAnalysisResult = self._vision.analyse(
                image_path           = image_path,
                vocabulary_by_cat    = vocab_by_cat,
                approved_tag_set     = approved_set,
                reference_image_path = reference_path,
            )

            # Gem analyse
            change_tags_all = result.approved_tags + result.change_tags
            analysis_id = analysis_repo.save_analysis(
                capture_id           = capture_id,
                location_id          = location_id,
                model_vision         = result.model,
                scene_dk             = result.scene_dk,
                change_detected      = result.change_detected,
                change_summary       = result.change_summary,
                ai_quality_flag      = result.quality_flag,
                ai_quality_ok        = result.quality_ok,
                reference_capture_id = reference_cid,
                raw_response         = result.raw_response,
                has_gdpr_data        = result.has_gdpr_data,
                duration_ms          = result.duration_ms,
            )

            # Gem tags (krydsreference)
            tag_repo.upsert_capture_tags(
                capture_id    = capture_id,
                analysis_id   = analysis_id,
                approved_tags = result.approved_tags + result.change_tags,
                new_tags      = result.new_tags,
            )

            # Gem GDPR-data (isoleret session med admin-rettigheder)
            if result.has_gdpr_data and result.gdpr_detections:
                self._save_gdpr_detections(
                    capture_id  = capture_id,
                    analysis_id = analysis_id,
                    location_id = location_id,
                    detections  = result.gdpr_detections,
                )

            duration_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "Analyse færdig: capture=%d tags=%d new=%d change=%s gdpr=%s (%dms)",
                capture_id, len(result.approved_tags), len(result.new_tags),
                result.change_detected, result.has_gdpr_data, duration_ms,
            )

            return AnalyseResult(
                capture_id      = capture_id,
                analysis_id     = analysis_id,
                success         = True,
                duration_ms     = duration_ms,
                tag_count       = len(result.approved_tags),
                new_tag_count   = len(result.new_tags),
                change_detected = result.change_detected,
                has_gdpr_data   = result.has_gdpr_data,
            )

        except Exception as e:
            log.error("Analyse fejlede for capture %d: %s", capture_id, e, exc_info=True)
            return AnalyseResult(
                capture_id=capture_id, analysis_id=0, success=False,
                duration_ms=int((time.monotonic() - start) * 1000),
                tag_count=0, new_tag_count=0,
                change_detected=False, has_gdpr_data=False,
                error=str(e),
            )
        finally:
            db.close()

    # ── Batch-analyse ─────────────────────────────────────────────────────────

    def run_pending_analyses(self, limit: int = 20) -> BatchStats:
        """
        Analysér alle captures der ikke endnu er AI-analyseret.
        Køres typisk fra et scheduled job (fx hvert 5. minut).
        """
        import time
        db = next(self._db_factory())
        start_all = time.monotonic()

        try:
            pending = CaptureRepository(db).get_captures_needing_analysis(limit=limit)
        finally:
            db.close()

        if not pending:
            log.debug("Ingen captures afventer analyse")
            return BatchStats(0, 0, 0, 0, 0, 0)

        log.info("Starter batch-analyse af %d captures", len(pending))

        succeeded  = 0
        failed     = 0
        new_tags   = 0
        gdpr_count = 0

        for item in pending:
            # Find billedsti
            image_path = self._resolve_image_path(item["filename"])
            if not image_path or not image_path.exists():
                log.warning("Billede ikke fundet: %s", item.get("filename"))
                failed += 1
                continue

            result = self.analyse_capture(
                capture_id  = item["id"],
                image_path  = image_path,
                location_id = item.get("location_id"),
            )

            if result.success:
                succeeded  += 1
                new_tags   += result.new_tag_count
                if result.has_gdpr_data:
                    gdpr_count += 1
            else:
                failed += 1

        total_ms = int((time.monotonic() - start_all) * 1000)
        stats = BatchStats(
            processed     = len(pending),
            succeeded     = succeeded,
            failed        = failed,
            total_ms      = total_ms,
            new_tags_found= new_tags,
            gdpr_flags    = gdpr_count,
        )
        log.info("Batch færdig: %d/%d ok, %d fejl, %d nye tags, %d GDPR-flag (%dms total)",
                 succeeded, len(pending), failed, new_tags, gdpr_count, total_ms)
        return stats

    # ── SIEM-integration ──────────────────────────────────────────────────────

    def run_siem_check(
        self,
        device_id:   str,
        location_id: str,
        store_event: bool = True,
    ) -> SIEMEvent:
        """
        Kør SIEM-analyse for en device baseret på DB-data.
        store_event: gem SIEMEvent i siem_events tabel (TODO: tabel i sprint D).
        """
        db = next(self._db_factory())
        try:
            # Hent data til analyse
            heartbeats = self._fetch_heartbeats(db, device_id, hours=24)
            captures   = self._fetch_recent_captures(db, device_id, hours=24)
            system_info = self._fetch_system_info(db, device_id)

            event = self.siem.analyse_heartbeats(
                device_id   = device_id,
                location_id = location_id,
                heartbeats  = heartbeats,
                captures    = captures,
                system_info = system_info,
            )

            if event.severity in ("warning", "critical"):
                log.warning("[SIEM] %s — %s: %s", device_id, event.severity.upper(), event.summary)

            return event
        finally:
            db.close()

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self) -> dict:
        """Tjek status på alle AI-services."""
        vision_ok = self._vision.health_check()
        return {
            "vision_model": self._vision.vision_model,
            "text_model":   self.siem.model,
            "vision_ok":    vision_ok,
            "ollama_url":   self._vision.base_url,
            "checked_at":   datetime.now(timezone.utc).isoformat(),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_image_path(self, filename: str) -> Optional[Path]:
        """Find billedsti ud fra filnavn."""
        if not filename:
            return None
        # Prøv absolut sti
        p = Path(filename)
        if p.is_absolute() and p.exists():
            return p
        # Prøv relativ til image_base_path
        p2 = self.image_base_path / filename
        if p2.exists():
            return p2
        # Søg rekursivt (langsomt — kun fallback)
        matches = list(self.image_base_path.rglob(Path(filename).name))
        if matches:
            return matches[0]
        return None

    def _save_gdpr_detections(
        self,
        capture_id:  int,
        analysis_id: int,
        location_id: Optional[str],
        detections:  list,
    ):
        """Gem GDPR-detektioner via isoleret admin-session."""
        gdpr_db = next(self._gdpr_db_factory())
        try:
            manager = GDPRManager(gdpr_db)
            for det in detections:
                manager.record_detection(
                    capture_id     = capture_id,
                    analysis_id    = analysis_id,
                    location_id    = location_id,
                    detection_type = det.detection_type,
                    detail_json    = det.detail or {},
                    bounding_box   = det.bounding_box,
                )
        except Exception as e:
            log.error("GDPR gem fejlede for capture %d: %s", capture_id, e)
        finally:
            gdpr_db.close()

    def _fetch_heartbeats(self, db, device_id: str, hours: int) -> list[dict]:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT received_at, cpu_temp, free_disk_mb, free_mem_mb,
                   capture_count, upload_queue, service_ok
            FROM heartbeats
            WHERE device_id = :did
              AND received_at > NOW() - :hours * INTERVAL '1 hour'
            ORDER BY received_at DESC
            LIMIT 100
        """), {"did": device_id, "hours": hours}).mappings().all()
        return [dict(r) for r in rows]

    def _fetch_recent_captures(self, db, device_id: str, hours: int) -> list[dict]:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT captured_at, quality_passed, quality_flag, uploaded, filesize
            FROM captures
            WHERE device_id = :did
              AND captured_at > NOW() - :hours * INTERVAL '1 hour'
            ORDER BY captured_at DESC
            LIMIT 50
        """), {"did": device_id, "hours": hours}).mappings().all()
        return [dict(r) for r in rows]

    def _fetch_system_info(self, db, device_id: str) -> dict:
        from sqlalchemy import text
        row = db.execute(text("""
            SELECT platform, os_version, service_version,
                   environment, location_id, last_seen
            FROM devices
            WHERE device_id = :did
        """), {"did": device_id}).mappings().first()
        return dict(row) if row else {}


# =============================================================================
# FACTORY — til brug i FastAPI dependency injection
# =============================================================================

_router_instance: Optional[AIRouter] = None

def get_ai_router() -> AIRouter:
    """
    FastAPI dependency — returnerer singleton AIRouter.
    Initialiseres én gang ved opstart via init_ai_router().
    """
    if _router_instance is None:
        raise RuntimeError("AIRouter ikke initialiseret — kald init_ai_router() ved opstart")
    return _router_instance


def init_ai_router(
    db_factory:      Callable,
    gdpr_db_factory: Callable,
    image_base_path: Path = Path("/data/timelapse"),
    ollama_url:      str  = "http://localhost:11434",
) -> AIRouter:
    """Kald én gang ved applikationsopstart (i main.py lifespan)."""
    global _router_instance
    _router_instance = AIRouter(
        db_factory      = db_factory,
        gdpr_db_factory = gdpr_db_factory,
        image_base_path = image_base_path,
        ollama_url      = ollama_url,
    )
    log.info("AIRouter initialiseret — vision=%s text=%s",
             _router_instance._vision.vision_model, _router_instance.siem.model)
    return _router_instance
