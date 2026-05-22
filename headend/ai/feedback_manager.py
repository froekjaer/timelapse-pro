"""
TimeLapse Pro — Feedback Manager
==================================
Human-in-the-loop feedback loop til AI-analyse.

To workflows:

1. ESKALERING (should_escalate)
   - Lokal model markerer usikre billeder
   - Admin godkender batch i UI
   - Gemini analyserer godkendte billeder
   - Resultater merges ind i analyse

2. MANUEL KORREKTION
   - Admin gennemgår en dags billeder
   - Retter tags, kvalitet og scene-beskrivelse
   - Korrektioner gemmes som ground truth
   - PromptOptimizer genererer few-shot eksempler
   - Næste analyse inkluderer eksemplerne
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


# =============================================================================
# ESKALERINGS-KRITERIER
# Justér thresholds her — ét sted, ingen kode-ændringer
# =============================================================================

ESCALATION_RULES = {
    "low_confidence":      0.70,   # escalate hvis confidence < denne
    "many_new_tags":       4,      # escalate hvis > N nye/ukendte tags
    "critical_tags": [             # escalate altid hvis disse tags ses
        "brand", "røg", "ild", "vandskade", "oversvømmelse",
        "konstruktionsskade", "kollaps_risiko", "ulykke",
        "hærværk", "uvedkommende",
    ],
    "always_escalate_change": True,  # change_detected = True → altid eskalér
    "poor_quality_flags": [
        "beskidt_linse", "kondens_på_linse", "forhindring_foran_kamera",
        "overeksponeret", "undereksponeret", "kamera_bevæget",
    ],
}


def should_escalate(
    confidence:      float,
    tags:            list[str],
    new_tags:        list[str],
    change_detected: bool,
    quality_flag:    str,
    quality_ok:      bool,
) -> tuple[bool, float, list[str]]:
    """
    Beregn om et billede skal eskaleres til Gemini.

    Returnerer: (should_escalate, score, reasons)
      score: 0.0–1.0 — jo højere, jo mere usikker
      reasons: hvilke regler der triggede
    """
    reasons = []
    score_components = []

    # Lav confidence
    if confidence < ESCALATION_RULES["low_confidence"]:
        reasons.append(f"lav_confidence:{confidence:.2f}")
        score_components.append(1.0 - confidence)

    # Mange nye tags (modellen ser noget ukendt)
    if len(new_tags) > ESCALATION_RULES["many_new_tags"]:
        reasons.append(f"mange_nye_tags:{len(new_tags)}")
        score_components.append(min(len(new_tags) / 10.0, 1.0))

    # Kritiske tags
    critical_found = [t for t in tags if t in ESCALATION_RULES["critical_tags"]]
    if critical_found:
        reasons.append(f"kritiske_tags:{','.join(critical_found)}")
        score_components.append(0.9)

    # Change detection
    if change_detected and ESCALATION_RULES["always_escalate_change"]:
        reasons.append("change_detected")
        score_components.append(0.6)

    # Dårlig billedkvalitet
    if quality_flag in ESCALATION_RULES["poor_quality_flags"] or not quality_ok:
        reasons.append(f"dårlig_kvalitet:{quality_flag}")
        score_components.append(0.5)

    escalate = len(reasons) > 0
    score = max(score_components) if score_components else 0.0

    return escalate, score, reasons


# =============================================================================
# ESCALATION MANAGER
# =============================================================================

@dataclass
class EscalationItem:
    analysis_id:    int
    capture_id:     int
    filename:       str
    captured_at:    datetime
    location_id:    Optional[str]
    scene_dk:       str
    escalation_score: float
    escalation_reasons: list[str]
    current_tags:   list[str]
    quality_flag:   str
    change_detected: bool


@dataclass
class EscalationBatchResult:
    approved_count: int
    gemini_called:  int
    tags_updated:   int
    errors:         int


class EscalationManager:
    """
    Håndterer eskalerings-workflow:
      mark_for_escalation() → kaldes af ai_router efter analyse
      get_pending()         → UI henter billeder til review
      approve_batch()       → admin godkender udvalgte
      run_approved()        → Gemini analyserer godkendte
    """

    def __init__(self, db: Session):
        self.db = db

    def mark_for_escalation(
        self,
        analysis_id: int,
        score:       float,
        reasons:     list[str],
    ):
        """Markér en analyse til eskalering (pending_review)."""
        self.db.execute(text("""
            UPDATE ai_analyses SET
                should_escalate    = TRUE,
                escalation_score   = :score,
                escalation_reasons = :reasons,
                escalation_status  = 'pending_review'
            WHERE id = :aid
        """), {"aid": analysis_id, "score": score, "reasons": reasons})
        self.db.commit()
        log.info("Marked analysis %d for escalation (score=%.2f, reasons=%s)",
                 analysis_id, score, reasons)

    def get_pending(
        self,
        location_id: Optional[str] = None,
        date_filter: Optional[date] = None,
        limit:       int = 100,
    ) -> list[EscalationItem]:
        """Hent billeder der afventer admin-review."""
        query = "SELECT * FROM v_escalation_queue WHERE TRUE"
        params: dict = {"limit": limit}

        if location_id:
            query += " AND location_id = :loc"
            params["loc"] = location_id
        if date_filter:
            query += " AND DATE(captured_at) = :dt"
            params["dt"] = date_filter

        query += " ORDER BY escalation_score DESC LIMIT :limit"
        rows = self.db.execute(text(query), params).mappings().all()

        return [EscalationItem(
            analysis_id        = r["analysis_id"],
            capture_id         = r["capture_id"],
            filename           = r["filename"],
            captured_at        = r["captured_at"],
            location_id        = r["location_id"],
            scene_dk           = r["scene_dk"] or "",
            escalation_score   = r["escalation_score"] or 0.0,
            escalation_reasons = list(r["escalation_reasons"] or []),
            current_tags       = list(r["current_tags"] or []),
            quality_flag       = r["ai_quality_flag"] or "",
            change_detected    = bool(r["change_detected"]),
        ) for r in rows]

    def approve_batch(self, analysis_ids: list[int], approved_by: str):
        """Admin godkender en liste af analyser til Gemini-eskalering."""
        now = datetime.now(timezone.utc)
        self.db.execute(text("""
            UPDATE ai_analyses SET
                escalation_status      = 'approved',
                escalation_approved_by = :by,
                escalation_approved_at = :now
            WHERE id = ANY(:ids)
              AND escalation_status = 'pending_review'
        """), {"ids": analysis_ids, "by": approved_by, "now": now})
        self.db.commit()
        log.info("Admin %s approved %d analyses for escalation", approved_by, len(analysis_ids))

    def reject_batch(self, analysis_ids: list[int], rejected_by: str):
        """Admin afviser eskalering — billederne behøver ikke Gemini."""
        self.db.execute(text("""
            UPDATE ai_analyses SET escalation_status = 'rejected'
            WHERE id = ANY(:ids)
        """), {"ids": analysis_ids})
        self.db.commit()

    def get_approved_for_gemini(self, limit: int = 50) -> list[dict]:
        """Hent analyser godkendt til Gemini, endnu ikke kørt."""
        rows = self.db.execute(text("""
            SELECT a.id AS analysis_id, c.id AS capture_id,
                   c.filename, a.location_id, a.escalation_reasons
            FROM ai_analyses a
            JOIN captures c ON c.id = a.capture_id
            WHERE a.escalation_status = 'approved'
              AND a.gemini_analysed_at IS NULL
            ORDER BY a.escalation_score DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    def save_gemini_result(
        self,
        analysis_id:  int,
        gemini_model: str,
        tags:         list[str],
        scene_dk:     str,
        raw_result:   dict,
    ):
        """Gem Gemini-svar og mergé tags ind i capture_tags."""
        now = datetime.now(timezone.utc)
        self.db.execute(text("""
            UPDATE ai_analyses SET
                gemini_result       = :raw::jsonb,
                gemini_model        = :model,
                gemini_analysed_at  = :now,
                gemini_tags         = :tags,
                gemini_scene_dk     = :scene,
                escalation_status   = 'completed'
            WHERE id = :aid
        """), {
            "aid":   analysis_id,
            "raw":   str(raw_result).replace("'", '"'),
            "model": gemini_model,
            "now":   now,
            "tags":  tags,
            "scene": scene_dk,
        })
        self.db.commit()
        log.info("Gemini result saved for analysis %d: %d tags", analysis_id, len(tags))

    def get_stats(self, days: int = 7) -> dict:
        """Eskalerings-statistik til dashboard."""
        row = self.db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE should_escalate)                 AS total_flagged,
                COUNT(*) FILTER (WHERE escalation_status = 'pending_review') AS pending,
                COUNT(*) FILTER (WHERE escalation_status = 'approved')  AS approved,
                COUNT(*) FILTER (WHERE escalation_status = 'rejected')  AS rejected,
                COUNT(*) FILTER (WHERE escalation_status = 'completed') AS completed,
                AVG(escalation_score) FILTER (WHERE should_escalate)    AS avg_score
            FROM ai_analyses
            WHERE analysed_at > NOW() - :days * INTERVAL '1 day'
        """), {"days": days}).mappings().first()
        return dict(row) if row else {}


# =============================================================================
# CORRECTIONS MANAGER
# =============================================================================

@dataclass
class CaptureForReview:
    capture_id:     int
    filename:       str
    captured_at:    datetime
    location_id:    Optional[str]
    scene_dk:       str
    current_tags:   list[str]
    quality_flag:   str
    quality_ok:     bool
    change_detected: bool
    should_escalate: bool
    gemini_tags:    Optional[list[str]]
    corrected_tags: Optional[list[str]]   # None = ikke korrigeret endnu
    correction_id:  Optional[int]


class CorrectionsManager:
    """
    Håndterer manuel korrektions-workflow.

    Typisk flow:
      1. Admin åbner "Gennemgå dag" i UI
      2. start_session() → opretter feedback-session
      3. get_day_captures() → henter dagens billeder med nuværende analyse
      4. save_correction() × N → admin retter tags/kvalitet
      5. complete_session() → afslutter session
      6. PromptOptimizer.generate_examples() → opdaterer prompts
    """

    def __init__(self, db: Session):
        self.db = db

    def start_session(
        self,
        session_date: date,
        admin_id:     str,
        location_id:  Optional[str] = None,
        notes:        Optional[str] = None,
    ) -> int:
        """Opret ny feedback-session. Returnerer session_id."""
        result = self.db.execute(text("""
            INSERT INTO ai_feedback_sessions
                (session_date, admin_id, location_id, notes)
            VALUES (:dt, :admin, :loc, :notes)
            RETURNING id
        """), {
            "dt":    session_date,
            "admin": admin_id,
            "loc":   location_id,
            "notes": notes,
        }).fetchone()
        self.db.commit()
        log.info("Feedback session %d started by %s for %s", result[0], admin_id, session_date)
        return result[0]

    def get_day_captures(
        self,
        review_date: date,
        location_id: Optional[str] = None,
        only_escalated: bool = False,
        limit: int = 200,
    ) -> list[CaptureForReview]:
        """Hent alle analyserede captures for en dag til gennemgang."""
        query = """
            SELECT * FROM v_daily_review
            WHERE DATE(captured_at) = :dt
        """
        params: dict = {"dt": review_date, "limit": limit}

        if location_id:
            query += " AND location_id = :loc"
            params["loc"] = location_id
        if only_escalated:
            query += " AND should_escalate = TRUE"

        query += " ORDER BY captured_at ASC LIMIT :limit"
        rows = self.db.execute(text(query), params).mappings().all()

        return [CaptureForReview(
            capture_id      = r["capture_id"],
            filename        = r["filename"],
            captured_at     = r["captured_at"],
            location_id     = r["location_id"],
            scene_dk        = r["scene_dk"] or "",
            current_tags    = list(r["current_tags"] or []),
            quality_flag    = r["ai_quality_flag"] or "",
            quality_ok      = bool(r["ai_quality_ok"]),
            change_detected = bool(r["change_detected"]),
            should_escalate = bool(r["should_escalate"]),
            gemini_tags     = list(r["gemini_tags"]) if r["gemini_tags"] else None,
            corrected_tags  = list(r["corrected_tags"]) if r["corrected_tags"] else None,
            correction_id   = r["correction_id"],
        ) for r in rows]

    def save_correction(
        self,
        capture_id:           int,
        session_id:           int,
        admin_id:             str,
        corrected_tags:       list[str],
        corrected_quality_flag: str,
        corrected_quality_ok: bool,
        corrected_scene:      Optional[str] = None,
        corrected_change:     Optional[bool] = None,
        notes:                Optional[str] = None,
    ) -> int:
        """
        Gem manuel korrektion for ét capture.
        Beregner automatisk diff (tilføjede/fjernede tags).
        Returnerer correction_id.
        """
        # Hent original analyse
        original = self.db.execute(text("""
            SELECT a.id AS analysis_id,
                   a.ai_quality_flag, a.ai_quality_ok,
                   a.scene_dk, a.change_detected,
                   array_agg(tv.tag) AS original_tags
            FROM ai_analyses a
            LEFT JOIN capture_tags ct ON ct.capture_id = a.capture_id
            LEFT JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id AND tv.approved = TRUE
            WHERE a.capture_id = :cid
            GROUP BY a.id, a.ai_quality_flag, a.ai_quality_ok, a.scene_dk, a.change_detected
        """), {"cid": capture_id}).mappings().first()

        if not original:
            log.warning("Ingen analyse fundet for capture %d", capture_id)
            return -1

        orig_tags = set(original["original_tags"] or [])
        corr_tags = set(corrected_tags)

        tags_added   = sorted(corr_tags - orig_tags)
        tags_removed = sorted(orig_tags - corr_tags)

        quality_changed = (
            corrected_quality_flag != original["ai_quality_flag"] or
            corrected_quality_ok   != original["ai_quality_ok"]
        )
        scene_changed = bool(
            corrected_scene and corrected_scene != original["scene_dk"]
        )

        result = self.db.execute(text("""
            INSERT INTO ai_corrections (
                capture_id, analysis_id, session_id,
                original_tags, original_scene, original_quality_flag,
                original_quality_ok, original_change_detected,
                corrected_tags, corrected_scene, corrected_quality_flag,
                corrected_quality_ok, corrected_change_detected,
                tags_added, tags_removed,
                quality_changed, scene_changed,
                notes, corrected_by
            ) VALUES (
                :cid, :aid, :sid,
                :orig_tags, :orig_scene, :orig_qflag,
                :orig_qok, :orig_change,
                :corr_tags, :corr_scene, :corr_qflag,
                :corr_qok, :corr_change,
                :added, :removed,
                :qchg, :schg,
                :notes, :admin
            )
            ON CONFLICT (capture_id, session_id) DO UPDATE SET
                corrected_tags        = EXCLUDED.corrected_tags,
                corrected_quality_flag= EXCLUDED.corrected_quality_flag,
                corrected_quality_ok  = EXCLUDED.corrected_quality_ok,
                tags_added            = EXCLUDED.tags_added,
                tags_removed          = EXCLUDED.tags_removed,
                quality_changed       = EXCLUDED.quality_changed,
                notes                 = EXCLUDED.notes
            RETURNING id
        """), {
            "cid":         capture_id,
            "aid":         original["analysis_id"],
            "sid":         session_id,
            "orig_tags":   sorted(orig_tags),
            "orig_scene":  original["scene_dk"],
            "orig_qflag":  original["ai_quality_flag"],
            "orig_qok":    original["ai_quality_ok"],
            "orig_change": original["change_detected"],
            "corr_tags":   corrected_tags,
            "corr_scene":  corrected_scene,
            "corr_qflag":  corrected_quality_flag,
            "corr_qok":    corrected_quality_ok,
            "corr_change": corrected_change,
            "added":       tags_added,
            "removed":     tags_removed,
            "qchg":        quality_changed,
            "schg":        scene_changed,
            "notes":       notes,
            "admin":       admin_id,
        }).fetchone()

        self.db.commit()

        # Opdatér session-tæller
        self.db.execute(text("""
            UPDATE ai_feedback_sessions
            SET corrections_made = corrections_made + 1
            WHERE id = :sid
        """), {"sid": session_id})
        self.db.commit()

        log.info("Correction saved: capture=%d +%d -%d tags",
                 capture_id, len(tags_added), len(tags_removed))
        return result[0]

    def complete_session(self, session_id: int) -> dict:
        """Afslut session og returnér statistik."""
        self.db.execute(text("""
            UPDATE ai_feedback_sessions
            SET completed_at = NOW(),
                captures_reviewed = (
                    SELECT COUNT(*) FROM ai_corrections WHERE session_id = :sid
                )
            WHERE id = :sid
        """), {"sid": session_id})
        self.db.commit()

        row = self.db.execute(text("""
            SELECT session_date, admin_id, captures_reviewed,
                   corrections_made, started_at, completed_at
            FROM ai_feedback_sessions WHERE id = :sid
        """), {"sid": session_id}).mappings().first()

        return dict(row) if row else {}

    def get_correction_stats(self, days: int = 30) -> list[dict]:
        """Korrektions-statistik til at vurdere model-fremgang over tid."""
        rows = self.db.execute(text("""
            SELECT * FROM v_correction_stats
            WHERE correction_date > NOW() - :days * INTERVAL '1 day'
            ORDER BY correction_date DESC
        """), {"days": days}).mappings().all()
        return [dict(r) for r in rows]


# =============================================================================
# PROMPT OPTIMIZER
# Genererer few-shot eksempler fra korrektioner
# =============================================================================

class PromptOptimizer:
    """
    Analyserer korrektioner og genererer forbedrede prompt-eksempler.

    Logik:
      1. Find tags der konsekvent tilføjes (model glemmer dem)
      2. Find tags der konsekvent fjernes (model fejltagger)
      3. Generer "når du ser X, husk at tagge Y"-eksempler
      4. Gem i ai_prompt_examples
      5. OllamaVisionService inkluderer disse i næste prompt
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_examples(
        self,
        min_occurrences: int = 3,   # tag skal være glemt/fejltagget mindst N gange
        location_id:     Optional[str] = None,
    ) -> int:
        """
        Generer few-shot eksempler fra ubrugte korrektioner.
        Returnerer antal nye eksempler genereret.
        """
        # Tags der oftest tilføjes af admin (model glemmer dem)
        forgotten_tags = self._get_frequently_added(min_occurrences, location_id)

        # Tags der oftest fjernes af admin (model ser dem der ikke er der)
        false_tags = self._get_frequently_removed(min_occurrences, location_id)

        examples_created = 0

        for tag, count in forgotten_tags:
            context = self._get_tag_context(tag, added=True)
            example_text = (
                f"Husk at tilføje '{tag}' når: {context}. "
                f"(Korrigeret {count} gange — du glemmer dette tag)"
            )
            self._save_example(
                example_text = example_text,
                example_type = "tags",
                based_on_tag = tag,
                priority     = max(1, 10 - count),
                location_id  = location_id,
            )
            examples_created += 1

        for tag, count in false_tags:
            context = self._get_tag_context(tag, added=False)
            example_text = (
                f"Brug IKKE '{tag}' medmindre: {context}. "
                f"(Fjernet {count} gange — du bruger dette tag forkert)"
            )
            self._save_example(
                example_text = example_text,
                example_type = "tags",
                based_on_tag = tag,
                priority     = max(1, 10 - count),
                location_id  = location_id,
            )
            examples_created += 1

        # Markér korrektioner som brugt
        self.db.execute(text("""
            UPDATE ai_corrections
            SET used_in_prompt = TRUE, used_in_prompt_at = NOW()
            WHERE used_in_prompt = FALSE
        """))
        self.db.commit()

        log.info("Generated %d prompt examples from corrections", examples_created)
        return examples_created

    def get_active_examples(
        self,
        location_id: Optional[str] = None,
        limit:       int = 20,
    ) -> list[str]:
        """
        Hent aktive few-shot eksempler til inkludering i prompt.
        Returnerer liste af eksempel-tekster, sorteret efter prioritet.
        """
        rows = self.db.execute(text("""
            SELECT example_text FROM ai_prompt_examples
            WHERE active = TRUE
              AND (location_id IS NULL OR location_id = :loc)
            ORDER BY priority ASC, times_used ASC
            LIMIT :limit
        """), {"loc": location_id, "limit": limit}).fetchall()

        # Tæl brug
        self.db.execute(text("""
            UPDATE ai_prompt_examples SET times_used = times_used + 1
            WHERE active = TRUE
              AND (location_id IS NULL OR location_id = :loc)
        """), {"loc": location_id})
        self.db.commit()

        return [r[0] for r in rows]

    def get_accuracy_trend(self, days: int = 30) -> list[dict]:
        """
        Beregn model-nøjagtighed over tid baseret på korrektioner.
        Metric: (tags der IKKE blev ændret) / (total tags i periode)
        """
        rows = self.db.execute(text("""
            SELECT
                DATE(corrected_at) AS dt,
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE array_length(tags_added, 1) = 0
                      AND array_length(tags_removed, 1) = 0
                      AND NOT quality_changed
                ) AS no_changes_needed,
                ROUND(
                    100.0 * COUNT(*) FILTER (
                        WHERE array_length(tags_added, 1) = 0
                          AND array_length(tags_removed, 1) = 0
                          AND NOT quality_changed
                    ) / NULLIF(COUNT(*), 0), 1
                ) AS accuracy_pct
            FROM ai_corrections
            WHERE corrected_at > NOW() - :days * INTERVAL '1 day'
            GROUP BY DATE(corrected_at)
            ORDER BY dt ASC
        """), {"days": days}).mappings().all()
        return [dict(r) for r in rows]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_frequently_added(
        self, min_count: int, location_id: Optional[str]
    ) -> list[tuple[str, int]]:
        rows = self.db.execute(text("""
            SELECT unnest(tags_added) AS tag, COUNT(*) AS cnt
            FROM ai_corrections
            WHERE used_in_prompt = FALSE
            GROUP BY tag
            HAVING COUNT(*) >= :min
            ORDER BY cnt DESC
            LIMIT 15
        """), {"min": min_count}).fetchall()
        return [(r[0], r[1]) for r in rows]

    def _get_frequently_removed(
        self, min_count: int, location_id: Optional[str]
    ) -> list[tuple[str, int]]:
        rows = self.db.execute(text("""
            SELECT unnest(tags_removed) AS tag, COUNT(*) AS cnt
            FROM ai_corrections
            WHERE used_in_prompt = FALSE
            GROUP BY tag
            HAVING COUNT(*) >= :min
            ORDER BY cnt DESC
            LIMIT 15
        """), {"min": min_count}).fetchall()
        return [(r[0], r[1]) for r in rows]

    def _get_tag_context(self, tag: str, added: bool) -> str:
        """Byg kontekst-beskrivelse for et tag baseret på co-occurring tags."""
        rows = self.db.execute(text("""
            SELECT unnest(corrected_tags) AS co_tag, COUNT(*) AS cnt
            FROM ai_corrections
            WHERE :tag = ANY(CASE WHEN :added THEN tags_added ELSE tags_removed END)
            GROUP BY co_tag
            HAVING COUNT(*) >= 2
            ORDER BY cnt DESC
            LIMIT 5
        """), {"tag": tag, "added": added}).fetchall()
        co_tags = [r[0] for r in rows if r[0] != tag]
        if co_tags:
            return f"billedet indeholder {', '.join(co_tags[:3])}"
        return "relevante byggeplacads-situationer"

    def _save_example(
        self,
        example_text: str,
        example_type: str,
        based_on_tag: str,
        priority:     int,
        location_id:  Optional[str],
    ):
        self.db.execute(text("""
            INSERT INTO ai_prompt_examples
                (example_text, example_type, priority, location_id, active)
            VALUES (:text, :type, :pri, :loc, TRUE)
            ON CONFLICT DO NOTHING
        """), {
            "text": example_text,
            "type": example_type,
            "pri":  priority,
            "loc":  location_id,
        })
        self.db.commit()
