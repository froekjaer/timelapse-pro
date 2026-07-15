"""
TimeLapse Pro — Repository Layer (Abstraktionslag)
====================================================
Alle data-forespørgsler går gennem repositories — ALDRIG direkte SQL i endpoints.

Returnerer altid DTOs (Pydantic), aldrig rå ORM-objekter til API-laget.
GDPR-felter er aldrig i normale DTO'er — kun boolske flag.

Repositories:
  CaptureRepository   — captures + AI analyse
  TagRepository       — vokabular, krydsreference, statistik
  AnalysisRepository  — AI-analyser, change events
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, date, timezone
from difflib import SequenceMatcher
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import text, func, and_, or_, desc
from sqlalchemy.orm import Session

from ai.tag_vocabulary import canonical_metadata

log = logging.getLogger(__name__)


# =============================================================================
# DTOs — hvad API'et eksponerer (aldrig rå ORM)
# =============================================================================

class TagDTO(BaseModel):
    tag:        str
    category:   str
    count:      int
    approved:   bool
    predefined: bool

    class Config:
        from_attributes = True


class CaptureTagsDTO(BaseModel):
    capture_id:   int
    filename:     str
    captured_at:  datetime
    device_id:    str
    location_id:  Optional[str]
    tags:         list[str]
    pending_tags: list[str]         # model-opfundne, afventer review
    tag_count:    int
    has_gdpr_data: bool             # flag kun — ingen GDPR-data her


class CapturePublicDTO(BaseModel):
    id:              int
    device_id:       str
    filename:        str
    captured_at:     datetime
    filesize:        Optional[int]
    camera_model:    Optional[str]
    quality_flag:    Optional[str]
    quality_passed:  Optional[bool]
    blur_score:      Optional[float]
    brightness_mean: Optional[float]
    uploaded:        Optional[bool]
    # AI-felter
    scene_dk:        Optional[str]
    change_detected: Optional[bool]
    change_summary:  Optional[str]
    ai_quality_flag: Optional[str]
    ai_quality_ok:   Optional[bool]
    model_vision:    Optional[str]
    analysed_at:     Optional[datetime]
    has_gdpr_data:   bool
    # Tags
    tags:            list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ChangeEventDTO(BaseModel):
    analysis_id:  int
    capture_id:   int
    filename:     str
    captured_at:  datetime
    device_id:    str
    location_id:  Optional[str]
    change_summary: Optional[str]
    change_tags:  list[str]
    analysed_at:  datetime


class TagTimelineDTO(BaseModel):
    location_id:  str
    tag:          str
    category:     str
    capture_date: date
    occurrences:  int


class TagStatDTO(BaseModel):
    tag:             str
    category:        str
    total_count:     int
    location_count:  int
    latest_occurrence: Optional[datetime]
    approved:        bool
    predefined:      bool


class PendingTagDTO(BaseModel):
    id:         int
    tag:        str
    count:      int
    first_seen: datetime
    last_seen:  datetime
    canonical_tag: Optional[str] = None
    display_name_da: Optional[str] = None
    display_name_en: Optional[str] = None
    translation_status: Optional[str] = None


# =============================================================================
# CAPTURE REPOSITORY
# =============================================================================

class CaptureRepository:
    """
    Læseadgang til captures med AI-data.
    Bruger v_capture_public view — ingen GDPR-data.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, capture_id: int) -> Optional[CapturePublicDTO]:
        row = self.db.execute(
            text("SELECT * FROM v_capture_public WHERE id = :id"),
            {"id": capture_id}
        ).mappings().first()
        if not row:
            return None
        tags = self._get_tags_for_capture(capture_id)
        return CapturePublicDTO(**dict(row), tags=tags)

    def list_by_location(
        self,
        location_id: str,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        quality_passed: Optional[bool] = None,
        tags: Optional[list[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CapturePublicDTO]:
        """
        Hent captures for en lokation med filtrering.
        tags-filter: returnér kun captures der har ALLE de angivne tags.
        """
        query = "SELECT cp.* FROM v_capture_public cp"
        params: dict = {"loc": location_id, "limit": limit, "offset": offset}
        where = ["cp.device_id IN (SELECT device_id FROM devices WHERE location_id = :loc)"]

        if from_dt:
            where.append("cp.captured_at >= :from_dt")
            params["from_dt"] = from_dt
        if to_dt:
            where.append("cp.captured_at <= :to_dt")
            params["to_dt"] = to_dt
        if quality_passed is not None:
            where.append("cp.quality_passed = :qp")
            params["qp"] = quality_passed

        if tags:
            # Subquery: kun captures der har alle ønskede tags
            tag_placeholders = ", ".join(f":tag_{i}" for i in range(len(tags)))
            for i, t in enumerate(tags):
                params[f"tag_{i}"] = t
            query += f"""
                JOIN (
                    SELECT ct.capture_id
                    FROM capture_tags ct
                    JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id
                    WHERE tv.tag IN ({tag_placeholders}) AND tv.approved = TRUE
                    GROUP BY ct.capture_id
                    HAVING COUNT(DISTINCT tv.tag) = :tag_count
                ) tagged ON tagged.capture_id = cp.id
            """
            params["tag_count"] = len(tags)

        query += " WHERE " + " AND ".join(where)
        query += " ORDER BY cp.captured_at DESC LIMIT :limit OFFSET :offset"

        rows = self.db.execute(text(query), params).mappings().all()
        result = []
        for row in rows:
            tags_for = self._get_tags_for_capture(row["id"])
            result.append(CapturePublicDTO(**dict(row), tags=tags_for))
        return result

    def _get_tags_for_capture(self, capture_id: int) -> list[str]:
        rows = self.db.execute(
            text("""
                SELECT tv.tag FROM capture_tags ct
                JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id
                WHERE ct.capture_id = :cid AND tv.approved = TRUE AND tv.rejected = FALSE
                ORDER BY ct.confidence DESC
            """),
            {"cid": capture_id}
        ).fetchall()
        return [r[0] for r in rows]

    def count_by_location(self, location_id: str) -> int:
        row = self.db.execute(
            text("""
                SELECT COUNT(*) FROM v_capture_public cp
                WHERE cp.device_id IN (SELECT device_id FROM devices WHERE location_id = :loc)
            """),
            {"loc": location_id}
        ).scalar()
        return row or 0

    def get_captures_needing_analysis(self, limit: int = 20) -> list[dict]:
        """Captures der endnu ikke er AI-analyseret."""
        rows = self.db.execute(text("""
            SELECT c.id, c.filename, c.device_id
            FROM captures c
            LEFT JOIN ai_analyses a ON a.capture_id = c.id
            WHERE a.id IS NULL
              AND c.quality_passed = TRUE
            ORDER BY c.captured_at DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]


# =============================================================================
# TAG REPOSITORY
# =============================================================================

class TagRepository:
    """
    Læse- og skrive-adgang til tag-vokabular og krydsreference.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Vokabular ─────────────────────────────────────────────────────────────

    def get_approved_tags(self) -> list[str]:
        rows = self.db.execute(text("""
            SELECT COALESCE(canonical_tag, tag) FROM ai_tag_vocabulary
            WHERE approved = TRUE AND rejected = FALSE
            ORDER BY count DESC
        """)).fetchall()
        return [r[0] for r in rows]

    def get_approved_by_category(self) -> dict[str, list[str]]:
        rows = self.db.execute(text("""
            SELECT COALESCE(canonical_tag, tag), category FROM ai_tag_vocabulary
            WHERE approved = TRUE AND rejected = FALSE
            ORDER BY category, count DESC
        """)).fetchall()
        result: dict[str, list[str]] = {}
        for tag, cat in rows:
            result.setdefault(cat or "øvrige", []).append(tag)
        return result

    def get_statistics(self, limit: int = 200) -> list[TagStatDTO]:
        rows = self.db.execute(text("""
            SELECT tag, category, total_count, location_count,
                   latest_occurrence, approved, predefined
            FROM v_tag_statistics
            ORDER BY total_count DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [TagStatDTO(**dict(r)) for r in rows]

    def get_tag_translations(self) -> dict[str, str]:
        """Tag → dansk visningsnavn, til kundevendt UI (thumbnails, capture-visning osv.).
        Inkluderer ALLE rækker med et sat display_name_da — ikke kun 'approved' —
        så ÆLDRE captures (tagget før engelsk-omlægningen, eller med siden-afviste
        tags) stadig viser et fornuftigt dansk navn i stedet for rå nøgle.
        """
        rows = self.db.execute(text("""
            SELECT tag, display_name_da FROM ai_tag_vocabulary
            WHERE display_name_da IS NOT NULL AND display_name_da != ''
        """)).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_pending_review(self) -> list[PendingTagDTO]:
        rows = self.db.execute(text("""
            SELECT id, tag, count, first_seen, last_seen,
                   canonical_tag, display_name_da, display_name_en, translation_status
            FROM ai_tag_vocabulary
            WHERE approved = FALSE AND rejected = FALSE
            ORDER BY count DESC, first_seen ASC
        """)).mappings().all()
        return [PendingTagDTO(**dict(r)) for r in rows]

    def update_translation(self, tag_id: int, display_name_da: Optional[str] = None,
                            display_name_en: Optional[str] = None) -> None:
        """Admin retter et AI-foreslået (eller manglende) dansk/engelsk visningsnavn.
        Sætter translation_status='approved' — markerer at et menneske har bekræftet det.
        """
        self.db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET display_name_da = COALESCE(:da, display_name_da),
                display_name_en = COALESCE(:en, display_name_en),
                translation_status = 'approved',
                translation_source = 'human',
                translation_updated_at = NOW()
            WHERE id = :id
        """), {"id": tag_id, "da": display_name_da, "en": display_name_en})
        self.db.commit()
        log.info("Tag %d oversættelse opdateret af admin", tag_id)

    def approve_tag(self, tag_id: int, category: Optional[str] = None):
        self.db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET approved = TRUE, rejected = FALSE,
                category = COALESCE(:cat, category)
            WHERE id = :id
        """), {"id": tag_id, "cat": category})
        self.db.commit()
        log.info("Tag %d approved", tag_id)

    def reject_tag(self, tag_id: int):
        self.db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET rejected = TRUE, approved = FALSE
            WHERE id = :id
        """), {"id": tag_id})
        self.db.commit()
        log.info("Tag %d rejected", tag_id)

    def get_similar_tag_suggestions(self, limit: int = 50, threshold: float = 0.72) -> list[dict]:
        rows = self.db.execute(text("""
            SELECT id, tag, category, count, approved, rejected
            FROM ai_tag_vocabulary
            WHERE rejected = FALSE
            ORDER BY count DESC, tag
            LIMIT 1000
        """)).mappings().all()

        tags = [dict(r) for r in rows]
        normalized = {t["id"]: self._normalize_tag_for_similarity(t["tag"]) for t in tags}
        groups: list[dict] = []
        used: set[int] = set()

        for tag in tags:
            if tag["id"] in used:
                continue

            left = normalized[tag["id"]]
            scored = []
            for other in tags:
                if other["id"] == tag["id"] or other["id"] in used:
                    continue
                score = self._tag_similarity(left, normalized[other["id"]])
                if score >= threshold:
                    scored.append((score, other))

            if not scored:
                continue

            candidates = [tag] + [item for _, item in sorted(scored, key=lambda x: x[0], reverse=True)[:8]]
            canonical = max(
                candidates,
                key=lambda item: (bool(item["approved"]), int(item["count"] or 0), -len(item["tag"])),
            )
            groups.append({
                "canonical_tag": canonical["tag"],
                "score": round(max(score for score, _ in scored), 3),
                "reason": self._similarity_reason([item["tag"] for item in candidates]),
                "tags": candidates,
                "total_count": sum(int(item["count"] or 0) for item in candidates),
            })
            used.update(item["id"] for item in candidates)

            if len(groups) >= limit:
                break

        return groups

    def merge_tags(self, source_tag_ids: list[int], canonical_tag: str, category: Optional[str] = None) -> dict:
        canonical_clean = self._clean_tag(canonical_tag)
        if not canonical_clean:
            raise ValueError("canonical_tag mangler")

        now = datetime.now(timezone.utc)
        canonical_id = self._get_or_create_tag_id(canonical_clean, approved=True, now=now)
        if not canonical_id:
            raise ValueError("Kunne ikke oprette canonical tag")

        source_ids = sorted({int(tag_id) for tag_id in source_tag_ids if int(tag_id) != canonical_id})
        if not source_ids:
            self.approve_tag(canonical_id, category)
            return {"canonical_tag_id": canonical_id, "merged_tags": 0, "updated_links": 0}

        self.db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET approved = TRUE,
                rejected = FALSE,
                category = COALESCE(:category, category)
            WHERE id = :id
        """), {"id": canonical_id, "category": category, "now": now})

        updated = self.db.execute(text("""
            UPDATE capture_tags ct
            SET tag_id = :canonical_id, is_new_tag = FALSE
            WHERE ct.tag_id = ANY(:source_ids)
              AND NOT EXISTS (
                  SELECT 1
                  FROM capture_tags existing
                  WHERE existing.capture_id = ct.capture_id
                    AND existing.tag_id = :canonical_id
              )
        """), {"canonical_id": canonical_id, "source_ids": source_ids}).rowcount

        self.db.execute(text("""
            DELETE FROM capture_tags
            WHERE tag_id = ANY(:source_ids)
        """), {"source_ids": source_ids})

        self.db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET approved = FALSE,
                rejected = TRUE,
                notes = CONCAT(COALESCE(notes || E'\n', ''), 'Merged into ', :canonical_tag, ' ', NOW()::text)
            WHERE id = ANY(:source_ids)
        """), {"source_ids": source_ids, "canonical_tag": canonical_clean})

        self.db.execute(text("""
            UPDATE ai_tag_vocabulary
            SET count = (
                SELECT COUNT(*) FROM capture_tags WHERE tag_id = :canonical_id
            ),
                last_seen = :now
            WHERE id = :canonical_id
        """), {"canonical_id": canonical_id, "now": now})

        self.db.commit()
        return {
            "canonical_tag_id": canonical_id,
            "canonical_tag": canonical_clean,
            "merged_tags": len(source_ids),
            "updated_links": updated or 0,
        }

    # ── Krydsreference ────────────────────────────────────────────────────────

    def upsert_capture_tags(
        self,
        capture_id: int,
        analysis_id: int,
        approved_tags: list[str],
        new_tags: list[str],
        new_tags_da: dict[str, str] | None = None,
    ):
        """
        Gem tags for en capture.
        approved_tags: kendte, godkendte tags
        new_tags:      model-opfundne (ENGELSK), gemmes med approved=False
        new_tags_da:   AI-foreslået dansk oversættelse pr. nyt tag (fra backfill.py)
        """
        now = datetime.now(timezone.utc)
        new_tags_da = new_tags_da or {}

        for tag in approved_tags:
            tag_id = self._get_or_create_tag_id(tag, approved=True, now=now)
            if tag_id:
                self._upsert_capture_tag(capture_id, tag_id, analysis_id, is_new=False)

        for tag in new_tags:
            tag_clean = tag.lower().strip().replace(" ", "_").replace("-", "_")
            if 2 < len(tag_clean) <= 60:
                da_hint = new_tags_da.get(tag) or new_tags_da.get(tag_clean) or ""
                tag_id = self._get_or_create_tag_id(tag_clean, approved=False, now=now, da_hint=da_hint)
                if tag_id:
                    self._upsert_capture_tag(capture_id, tag_id, analysis_id, is_new=True)

        self.db.commit()

    def _get_or_create_tag_id(self, tag: str, approved: bool, now: datetime, da_hint: str = "") -> Optional[int]:
        canonical, label_da, label_en = canonical_metadata(tag, da_hint=da_hint)
        row = self.db.execute(
            text("""
                SELECT id FROM ai_tag_vocabulary
                WHERE tag = :tag OR canonical_tag = :canonical
                ORDER BY approved DESC, predefined DESC
                LIMIT 1
            """),
            {"tag": tag, "canonical": canonical}
        ).fetchone()
        if row:
            return row[0]
        status = "ai_suggested" if da_hint else "pending"
        result = self.db.execute(text("""
            INSERT INTO ai_tag_vocabulary (
                tag, canonical_tag, display_name_da, display_name_en,
                translation_status, translation_source, translation_updated_at,
                category, approved, first_seen, last_seen
            )
            VALUES (
                :tag, :canonical, :label_da, :label_en,
                :status, 'gemini', :now,
                'model_invented', :approved, :now, :now
            )
            ON CONFLICT (tag) DO UPDATE SET
                last_seen = :now,
                canonical_tag = COALESCE(ai_tag_vocabulary.canonical_tag, EXCLUDED.canonical_tag),
                display_name_da = COALESCE(ai_tag_vocabulary.display_name_da, EXCLUDED.display_name_da),
                display_name_en = COALESCE(ai_tag_vocabulary.display_name_en, EXCLUDED.display_name_en)
            RETURNING id
        """), {
            "tag": tag,
            "canonical": canonical,
            "label_da": label_da,
            "label_en": label_en,
            "status": status,
            "approved": approved,
            "now": now,
        }).fetchone()
        return result[0] if result else None

    @staticmethod
    def _clean_tag(tag: str) -> str:
        return re.sub(r"_+", "_", tag.lower().strip().replace(" ", "_").replace("-", "_")).strip("_")

    def _normalize_tag_for_similarity(self, tag: str) -> str:
        normalized = unicodedata.normalize("NFKD", tag.lower())
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
        words = [
            self._stem_tag_word(word) for word in normalized.split("_")
            if word and word not in {"og", "i", "det", "den", "de", "paa", "på"}
        ]
        return "_".join(words)

    @staticmethod
    def _stem_tag_word(word: str) -> str:
        if word.startswith("over") and len(word) > 7:
            word = word[4:]
        for suffix in ("ende", "et", "ede", "e"):
            if len(word) > len(suffix) + 4 and word.endswith(suffix):
                return word[:-len(suffix)]
        return word

    @staticmethod
    def _tag_similarity(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        ratio = SequenceMatcher(None, left, right).ratio()
        left_words = set(left.split("_"))
        right_words = set(right.split("_"))
        overlap = len(left_words & right_words) / max(1, len(left_words | right_words))
        prefix_bonus = 0.12 if left.split("_")[0] == right.split("_")[0] else 0.0
        suffix_bonus = 0.18 if left.split("_")[-1] == right.split("_")[-1] else 0.0
        containment_bonus = 0.20 if left in right or right in left else 0.0
        return min(1.0, (ratio * 0.55) + (overlap * 0.45) + prefix_bonus + suffix_bonus + containment_bonus)

    @staticmethod
    def _similarity_reason(tags: list[str]) -> str:
        word_sets = [set(tag.split("_")) for tag in tags]
        common = set.intersection(*word_sets) if word_sets else set()
        if common:
            return "Deler ordene: " + ", ".join(sorted(common))
        return "Hoj tekstlig lighed"

    def _upsert_capture_tag(self, capture_id: int, tag_id: int, analysis_id: int, is_new: bool):
        self.db.execute(text("""
            INSERT INTO capture_tags (capture_id, tag_id, analysis_id, is_new_tag)
            VALUES (:cid, :tid, :aid, :new)
            ON CONFLICT (capture_id, tag_id) DO NOTHING
        """), {"cid": capture_id, "tid": tag_id, "aid": analysis_id, "new": is_new})

    # ── Søgning og statistik ──────────────────────────────────────────────────

    def get_captures_by_tags(
        self,
        tags: list[str],
        require_all: bool = True,
        limit: int = 50,
    ) -> list[CaptureTagsDTO]:
        """
        Søg billeder efter tags.
        require_all=True  → AND-logik (alle tags skal være til stede)
        require_all=False → OR-logik (mindst ét tag)
        """
        rows = self.db.execute(text("""
            SELECT * FROM v_capture_tags_flat
            WHERE capture_id IN (
                SELECT ct.capture_id
                FROM capture_tags ct
                JOIN ai_tag_vocabulary tv ON tv.id = ct.tag_id
                WHERE (tv.tag = ANY(:tags) OR tv.canonical_tag = ANY(:tags)) AND tv.approved = TRUE
                GROUP BY ct.capture_id
                HAVING COUNT(DISTINCT COALESCE(tv.canonical_tag, tv.tag)) >= :min_count
            )
            ORDER BY captured_at DESC
            LIMIT :limit
        """), {
            "tags": tags,
            "min_count": len(tags) if require_all else 1,
            "limit": limit,
        }).mappings().all()
        return [CaptureTagsDTO(**dict(r)) for r in rows]

    def get_timeline(
        self,
        location_id: str,
        tags: Optional[list[str]] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[TagTimelineDTO]:
        """Tag-frekvens over tid for en lokation."""
        query = """
            SELECT location_id, tag, category, capture_date, occurrences
            FROM v_location_tag_timeline
            WHERE location_id = :loc
        """
        params: dict = {"loc": location_id}

        if tags:
            query += " AND tag = ANY(:tags)"
            params["tags"] = tags
        if from_date:
            query += " AND capture_date >= :from_date"
            params["from_date"] = from_date
        if to_date:
            query += " AND capture_date <= :to_date"
            params["to_date"] = to_date

        query += " ORDER BY capture_date, occurrences DESC"
        rows = self.db.execute(text(query), params).mappings().all()
        return [TagTimelineDTO(**dict(r)) for r in rows]

    def co_occurring_tags(self, tag: str, limit: int = 20) -> list[dict]:
        """Hvilke andre tags optræder oftest sammen med dette tag?"""
        rows = self.db.execute(text("""
            SELECT COALESCE(tv2.canonical_tag, tv2.tag), COUNT(*) AS co_count
            FROM capture_tags ct1
            JOIN ai_tag_vocabulary tv1 ON tv1.id = ct1.tag_id AND (tv1.tag = :tag OR tv1.canonical_tag = :tag)
            JOIN capture_tags ct2      ON ct2.capture_id = ct1.capture_id
            JOIN ai_tag_vocabulary tv2 ON tv2.id = ct2.tag_id AND COALESCE(tv2.canonical_tag, tv2.tag) != COALESCE(tv1.canonical_tag, tv1.tag) AND tv2.approved = TRUE
            GROUP BY COALESCE(tv2.canonical_tag, tv2.tag)
            ORDER BY co_count DESC
            LIMIT :limit
        """), {"tag": tag, "limit": limit}).fetchall()
        return [{"tag": r[0], "count": r[1]} for r in rows]


# =============================================================================
# ANALYSIS REPOSITORY
# =============================================================================

class AnalysisRepository:
    """Adgang til AI-analyser og change events."""

    def __init__(self, db: Session):
        self.db = db

    def get_change_events(
        self,
        location_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[ChangeEventDTO]:
        query = "SELECT * FROM v_change_events WHERE TRUE"
        params: dict = {"limit": limit}
        if location_id:
            query += " AND location_id = :loc"
            params["loc"] = location_id
        if from_dt:
            query += " AND captured_at >= :from_dt"
            params["from_dt"] = from_dt
        query += " ORDER BY captured_at DESC LIMIT :limit"
        rows = self.db.execute(text(query), params).mappings().all()
        return [ChangeEventDTO(**dict(r)) for r in rows]

    def get_analysis_for_capture(self, capture_id: int) -> Optional[dict]:
        row = self.db.execute(
            text("SELECT * FROM ai_analyses WHERE capture_id = :cid"),
            {"cid": capture_id}
        ).mappings().first()
        return dict(row) if row else None

    def save_analysis(
        self,
        capture_id: int,
        location_id: Optional[str],
        model_vision: str,
        scene_dk: str,
        change_detected: bool,
        change_summary: Optional[str],
        ai_quality_flag: str,
        ai_quality_ok: bool,
        reference_capture_id: Optional[int],
        raw_response: dict,
        has_gdpr_data: bool,
        duration_ms: int,
    ) -> int:
        """Gem eller opdater AI-analyse. Returnerer analysis_id."""
        result = self.db.execute(text("""
            INSERT INTO ai_analyses (
                capture_id, location_id, model_vision, scene_dk,
                change_detected, change_summary, ai_quality_flag, ai_quality_ok,
                reference_capture_id, raw_response, has_gdpr_data, duration_ms
            ) VALUES (
                :cid, :loc, :model, :scene,
                :change, :change_sum, :qflag, :qok,
                :ref_cid, CAST(:raw AS jsonb), :gdpr, :dur
            )
            ON CONFLICT (capture_id) DO UPDATE SET
                scene_dk             = EXCLUDED.scene_dk,
                change_detected      = EXCLUDED.change_detected,
                change_summary       = EXCLUDED.change_summary,
                ai_quality_flag      = EXCLUDED.ai_quality_flag,
                ai_quality_ok        = EXCLUDED.ai_quality_ok,
                has_gdpr_data        = EXCLUDED.has_gdpr_data,
                raw_response         = EXCLUDED.raw_response,
                analysed_at          = NOW()
            RETURNING id
        """), {
            "cid":        capture_id,
            "loc":        location_id,
            "model":      model_vision,
            "scene":      scene_dk,
            "change":     change_detected,
            "change_sum": change_summary,
            "qflag":      ai_quality_flag,
            "qok":        ai_quality_ok,
            "ref_cid":    reference_capture_id,
            "raw":        __import__('json').dumps(raw_response),
            "gdpr":       has_gdpr_data,
            "dur":        duration_ms,
        }).fetchone()
        self.db.commit()
        return result[0]

    def get_reference_capture_id(self, capture_id: int, location_id: str) -> Optional[int]:
        """
        Find referencebillede til change detection.
        Strategi: samme lokation, samme tidspunkt ±1 time, dagen før.
        """
        row = self.db.execute(text("""
            SELECT c.id FROM captures c
            JOIN devices d ON d.device_id = c.device_id
            WHERE d.location_id = :loc
              AND c.quality_passed = TRUE
              AND c.captured_at < (
                  SELECT captured_at FROM captures WHERE id = :cid
              )
              AND c.captured_at > (
                  SELECT captured_at - INTERVAL '25 hours' FROM captures WHERE id = :cid
              )
            ORDER BY ABS(EXTRACT(EPOCH FROM (
                c.captured_at - (SELECT captured_at FROM captures WHERE id = :cid) + INTERVAL '24 hours'
            ))) ASC
            LIMIT 1
        """), {"loc": location_id, "cid": capture_id}).fetchone()
        return row[0] if row else None
