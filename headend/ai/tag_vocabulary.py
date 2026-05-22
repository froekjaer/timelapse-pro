"""
TimeLapse Pro — AI Tag Vocabulary Manager
==========================================
Selvudvidende tag-vokabular til billed-analyse.

Princip:
  - Starter med ~300 foruddefinerede tags organiseret i kategorier
  - Vision-modellen bruger listen som udgangspunkt
  - Nye tags modellen finder gemmes automatisk med approved=False
  - Admin kan godkende/afvise nye tags i UI
  - Godkendte tags indgår i næste prompt → vokabularet vokser

DB-tabel: ai_tag_vocabulary (PostgreSQL)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ── Foruddefineret startvokabular ─────────────────────────────────────────────
# Organiseret i kategorier. Alle tags på dansk, lowercase, underscore.

PREDEFINED_TAGS: dict[str, list[str]] = {

    "strukturer": [
        "fundament", "kælder", "stueetage", "etage_1", "etage_2", "etage_3",
        "tagetage", "tag", "fladt_tag", "skråt_tag", "facade", "gavl",
        "betonvæg", "murstensvæg", "trævæg", "glasfacade", "søjle", "bjælke",
        "dæk", "trappe", "elevator_skakt", "skorsten", "balkon", "terrasse",
        "carport", "garage", "kælder_nedgang", "lyskasse", "tagkvist",
        "vinduesparti", "dør", "port", "havelåge", "hegn", "mur",
    ],

    "bygningstyper": [
        "enfamiliehus", "rækkehus", "etagebyggeri", "villa", "sommerhus",
        "erhvervsbygning", "kontorhus", "lager", "fabrik", "hal",
        "parkeringshus", "skur", "pavillon", "container_bolig",
        "historisk_bygning", "kirke", "skole", "institution",
    ],

    "byggefremskridt": [
        "tom_grund", "udgravning", "jordarbejde", "pilotering",
        "fundamentstøbning", "kælder_støbt", "betondæk_støbt",
        "råhus_opførelse", "råhus_færdigt", "murerarbejde",
        "tagkonstruktion", "tagdækning", "tagpap", "tagsten",
        "facade_beklædning", "puds", "isolering_ydervæg",
        "vinduesmontage", "dørmontage", "indvendig_aptering",
        "el_installation", "vvs_installation", "gulvlægning",
        "maling_indvendig", "maling_udvendig", "flisearbejde",
        "badeværelse_montage", "køkken_montage", "færdigbygget",
        "renovering", "nedrivning", "tilbygning", "ombygning",
    ],

    "tunge_maskiner": [
        "tårnkran", "mobilkran", "minikran", "gravemaskine",
        "minigraver", "bulldozer", "læssemaskine", "hjullæsser",
        "betonbil", "betonpumpe", "vibrator_bil", "asfaltmaskine",
        "vejhøvl", "tromle", "komprimator", "borepæle_maskine",
        "pæleramme", "spunsvægs_maskine",
    ],

    "udstyr_og_redskaber": [
        "stillads", "rullestillads", "arbejdslift", "sakselift",
        "teleskoplift", "gaffeltruck", "håndtruck", "trillebør",
        "betonblander", "kompressor", "generator", "svejseudstyr",
        "borehammer", "vinkelsliber", "travis", "elevator_bygge",
        "betonform", "forskalling", "spændebånd", "kran_krog",
        "løftegrej", "stige", "palle", "container_opbevaring",
        "affalds_container", "skip", "vandbeholder", "dieseltank",
    ],

    "køretøjer": [
        "personbil", "varevogn", "stor_varevogn", "pickup",
        "lastbil", "lastbil_med_kran", "tipvogn", "sættevogn",
        "tankvogn", "betontransport", "stiklevogn", "trailer",
        "ambulance", "brandvogn", "politibil", "bus", "minibus",
        "motorcykel", "knallert", "cykel", "elcykel", "elscooter",
        "truck", "palleløfter",
    ],

    "materialer_på_plads": [
        "armering", "armeringsjern", "betonblokke", "letklinker_blokke",
        "mursten", "porebeton", "beton_elementer", "præfab_elementer",
        "stålbjælker", "stålplader", "stålrør", "træ_planker",
        "krydsfiner", "tagsten", "tagpap_ruller", "isoleringsplader",
        "rockwool", "gipsplader", "vinduer_på_palle", "døre_på_palle",
        "rør_vvs", "kabler", "kabelrør", "sand", "grus", "sten",
        "jord", "fyldsand", "betonblanding", "mørtel", "lim_sække",
        "malingsspande", "affalds_sække", "paller", "stablede_materialer",
    ],

    "arbejdere_og_aktivitet": [
        "arbejder", "flere_arbejdere", "gruppe_arbejdere",
        "arbejder_aktiv", "arbejder_pause", "arbejder_klatrer",
        "hjelm", "orange_vest", "gul_vest", "sikkerhedsudstyr",
        "sikkerhedssko", "sikkerhedsbriller", "høreværn",
        "svejser", "murer", "tømrer", "elektriker", "vvs_mand",
        "kranfører", "maskinfører", "arbejdsleder", "tilsynsførende",
        "ingen_aktivitet", "aktiv_byggeplads", "stille_byggeplads",
    ],

    "vejr": [
        "solskin", "delvis_skyet", "overskyet", "grå_himmel",
        "tåge", "let_tåge", "tyk_tåge", "dis", "regn", "let_regn",
        "kraftig_regn", "styrtregn", "hagl", "sne", "let_sne",
        "kraftigt_snefald", "sne_på_jord", "is", "frost",
        "rimfrost", "blæsende", "storm", "torden", "regnbue",
        "skydække", "blå_himmel", "hvide_skyer",
    ],

    "lys_og_tid": [
        "dagslys", "solrig_dag", "mørk_dag", "tusmørke_morgen",
        "tusmørke_aften", "nat", "kunstig_belysning", "arbejdslys",
        "modlys", "direkte_sollys", "diffust_lys", "skygge",
        "lang_skygge", "kort_skygge", "gyldent_lys", "blåt_lys",
    ],

    "sikkerhed_og_afspærring": [
        "byggeplads_hegn", "byggepladshegn_grønt", "byggeplads_port",
        "adgang_forbudt_skilt", "advarselsskilt", "vejskilt",
        "sikkerhedsnet", "kantbeskyttelse", "afspærring",
        "advarselsbånd", "kegler", "vejomlægning", "brandslukker",
        "førstehjælpsskab", "nødudgang_skilt",
    ],

    "pladstilstand": [
        "ryddig_plads", "rodet_plads", "meget_rodet",
        "mudret_underlag", "tørt_underlag", "vådt_underlag",
        "sne_dækket", "is_dækket", "støvende", "mudder",
        "vandpytter", "oversvømmelse", "erosion",
    ],

    "omgivelser": [
        "vej", "fortov", "asfalt", "fliser", "græs", "have",
        "træ", "træer", "busk", "hæk", "natur", "mark",
        "skov", "sø", "å", "kanal", "havn",
        "nabobygning", "nabo_renovering", "parkering",
        "lygtepæl", "elskab", "brønddæksel", "grøft",
    ],

    "gdpr_safe": [
        "nummerplade_synlig", "person_synlig", "ansigt_synlig",
        "gruppe_mennesker", "fodgænger", "cyklist",
    ],

    "anomalier_og_hændelser": [
        "brand", "røg", "ild", "brandfare",
        "vandskade", "oversvømmelse_risiko", "skybrud",
        "konstruktionsskade", "revne", "kollaps_risiko",
        "nyt_objekt", "manglende_objekt", "ukendt_objekt",
        "efterladt_udstyr", "tyveri_risiko", "hærværk",
        "uvedkommende", "dyr_på_pladsen",
        "kran_alarm", "ulykke", "sikkerhedshændelse",
    ],

    "dyr": [
        "hund", "kat", "fugl", "flok_fugle", "måge",
        "rotte", "ræv", "hare",
    ],

    "kamera_kvalitet": [
        "klart_billede", "tåget_billede", "beskidt_linse",
        "kondens_på_linse", "forhindring_foran_kamera",
        "overeksponeret", "undereksponeret", "korrekt_eksponering",
        "bevægelsesslør", "forkert_fokus", "natbillede_ok",
        "natbillede_for_mørkt", "kamera_bevæget",
    ],

    "change_detection": [
        "ny_konstruktion_siden_sidst", "fremskridt_siden_sidst",
        "nyt_køretøj", "ny_maskine", "ny_container",
        "materialer_fjernet", "konstruktion_fjernet",
        "kran_position_ændret", "ny_etage_synlig",
        "tag_påbegyndt", "facade_ændret",
        "ingen_ændring", "lille_ændring", "stor_ændring",
    ],
}


def get_all_predefined() -> list[str]:
    """Returnér alle foruddefinerede tags som flad liste."""
    tags = []
    for cat_tags in PREDEFINED_TAGS.values():
        tags.extend(cat_tags)
    return sorted(set(tags))


def get_by_category(category: str) -> list[str]:
    return PREDEFINED_TAGS.get(category, [])


def get_categories() -> list[str]:
    return list(PREDEFINED_TAGS.keys())


# ── Database-integration ──────────────────────────────────────────────────────

VOCABULARY_DDL = """
CREATE TABLE IF NOT EXISTS ai_tag_vocabulary (
    id          SERIAL PRIMARY KEY,
    tag         TEXT UNIQUE NOT NULL,
    category    TEXT,
    count       INTEGER DEFAULT 1,
    first_seen  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    predefined  BOOLEAN DEFAULT FALSE,
    approved    BOOLEAN DEFAULT TRUE,
    rejected    BOOLEAN DEFAULT FALSE,
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_vocab_tag ON ai_tag_vocabulary(tag);
CREATE INDEX IF NOT EXISTS idx_vocab_approved ON ai_tag_vocabulary(approved, rejected);
"""


class TagVocabulary:
    """
    Dynamisk tag-vokabular der vokser med systemet.

    Bruges af OllamaService til at bygge prompts og gemme nye tags.
    """

    def __init__(self, db_session_factory):
        """
        db_session_factory: callable der returnerer en SQLAlchemy Session
        (samme factory som headend/main.py bruger)
        """
        self._get_db = db_session_factory
        self._ensure_table()
        self._seed_predefined()

    def _ensure_table(self):
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            db.execute(text(VOCABULARY_DDL))
            db.commit()
        except Exception as e:
            log.warning("Vocabulary DDL: %s", e)
            db.rollback()
        finally:
            db.close()

    def _seed_predefined(self):
        """Indsæt foruddefinerede tags hvis tabellen er tom."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            result = db.execute(
                text("SELECT COUNT(*) FROM ai_tag_vocabulary WHERE predefined=TRUE")
            ).scalar()
            if result == 0:
                log.info("Seeding %d predefined tags...", len(get_all_predefined()))
                for category, tags in PREDEFINED_TAGS.items():
                    for tag in tags:
                        db.execute(text("""
                            INSERT INTO ai_tag_vocabulary (tag, category, predefined, approved)
                            VALUES (:tag, :cat, TRUE, TRUE)
                            ON CONFLICT (tag) DO NOTHING
                        """), {"tag": tag, "cat": category})
                db.commit()
                log.info("Tag vocabulary seeded.")
        except Exception as e:
            log.error("Seed error: %s", e)
            db.rollback()
        finally:
            db.close()

    def get_approved_tags(self) -> list[str]:
        """Returnér alle godkendte tags (bruges i prompt)."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            rows = db.execute(text(
                "SELECT tag FROM ai_tag_vocabulary WHERE approved=TRUE AND rejected=FALSE ORDER BY count DESC"
            )).fetchall()
            return [r[0] for r in rows]
        finally:
            db.close()

    def get_approved_by_category(self) -> dict[str, list[str]]:
        """Returnér godkendte tags grupperet på kategori."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            rows = db.execute(text(
                "SELECT tag, category FROM ai_tag_vocabulary WHERE approved=TRUE AND rejected=FALSE ORDER BY category, tag"
            )).fetchall()
            result: dict[str, list[str]] = {}
            for tag, cat in rows:
                cat = cat or "øvrige"
                result.setdefault(cat, []).append(tag)
            return result
        finally:
            db.close()

    def record_usage(self, tags: list[str], new_tags: list[str] | None = None):
        """
        Registrér at tags blev brugt.
        new_tags: tags modellen opfandt selv — gemmes med approved=False til review.
        """
        from sqlalchemy import text
        now = datetime.now(timezone.utc)
        db = next(self._get_db())
        try:
            for tag in tags:
                db.execute(text("""
                    UPDATE ai_tag_vocabulary
                    SET count = count + 1, last_seen = :now
                    WHERE tag = :tag
                """), {"tag": tag, "now": now})

            if new_tags:
                for tag in new_tags:
                    tag_clean = tag.lower().strip().replace(" ", "_").replace("-", "_")
                    if len(tag_clean) < 3 or len(tag_clean) > 60:
                        continue
                    db.execute(text("""
                        INSERT INTO ai_tag_vocabulary (tag, category, predefined, approved, first_seen, last_seen)
                        VALUES (:tag, 'model_opfundet', FALSE, FALSE, :now, :now)
                        ON CONFLICT (tag) DO UPDATE SET
                            count = ai_tag_vocabulary.count + 1,
                            last_seen = :now
                    """), {"tag": tag_clean, "now": now})
                log.info("Stored %d new model-invented tags for review", len(new_tags))

            db.commit()
        except Exception as e:
            log.error("record_usage error: %s", e)
            db.rollback()
        finally:
            db.close()

    def get_pending_review(self) -> list[dict]:
        """Tags opfundet af modellen der afventer godkendelse."""
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            rows = db.execute(text("""
                SELECT id, tag, count, first_seen, last_seen
                FROM ai_tag_vocabulary
                WHERE approved=FALSE AND rejected=FALSE
                ORDER BY count DESC, first_seen ASC
            """)).fetchall()
            return [{"id": r[0], "tag": r[1], "count": r[2],
                     "first_seen": str(r[3]), "last_seen": str(r[4])} for r in rows]
        finally:
            db.close()

    def approve(self, tag_id: int, category: str | None = None):
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            db.execute(text(
                "UPDATE ai_tag_vocabulary SET approved=TRUE, rejected=FALSE, category=COALESCE(:cat, category) WHERE id=:id"
            ), {"id": tag_id, "cat": category})
            db.commit()
        finally:
            db.close()

    def reject(self, tag_id: int):
        from sqlalchemy import text
        db = next(self._get_db())
        try:
            db.execute(text(
                "UPDATE ai_tag_vocabulary SET rejected=TRUE, approved=FALSE WHERE id=:id"
            ), {"id": tag_id})
            db.commit()
        finally:
            db.close()
