"""
TimeLapse Pro — AI Strategy System
====================================
Konfigurerbar AI-strategi pr. kunde/site.

Strategier:
  technical_only   → kun OpenCV (ingen AI)
  local_only       → kun Ollama (vælg model)
  local_then_cloud → Ollama først, Gemini ved usikkerhed
  cloud_only       → direkte til Gemini Flash

Konfiguration hentes i prioriteret rækkefølge:
  1. Site-specifik config  (ai_config WHERE site_id = ...)
  2. Kunde-specifik config (ai_config WHERE customer_id = ... AND site_id IS NULL)
  3. Global default        (ai_config WHERE customer_id IS NULL)
  4. Hardcoded fallback    (GLOBAL_DEFAULTS)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import json
import logging

log = logging.getLogger(__name__)

# ── Hardcoded fallback hvis intet er konfigureret i DB ───────────────────────
GLOBAL_DEFAULTS = {
    "strategy":              "cloud_only",      # sikreste default
    "local_model":           "qwen2.5vl:7b",
    "cloud_model":           "gemini-2.5-flash",
    "escalation_threshold":  0.70,              # confidence under denne → eskalér
    "escalation_new_tags":   4,                 # >N nye tags → eskalér
    "always_escalate_tags":  ["brand", "røg", "ild", "vandskade", "ulykke", "hærværk"],
    "always_cloud_tags":     [],                # disse tags sender ALTID til cloud uanset strategi
    "max_local_retries":     1,
    "tag_vocabulary_limit":  80,                # maks tags i prompt (performance)
    "enabled":               True,
}

VALID_STRATEGIES = {"technical_only", "local_only", "local_then_cloud", "cloud_only"}


# ── Schema ────────────────────────────────────────────────────────────────────
AI_CONFIG_DDL = """
CREATE TABLE IF NOT EXISTS ai_config (
    id              SERIAL PRIMARY KEY,
    customer_id     TEXT,                    -- NULL = global default
    site_id         TEXT,                    -- NULL = gælder alle sites for kunden
    customer_name   TEXT,                    -- til visning i UI
    site_name       TEXT,

    strategy        TEXT NOT NULL DEFAULT 'cloud_only',
    local_model     TEXT DEFAULT 'qwen2.5vl:7b',
    cloud_model     TEXT DEFAULT 'gemini-2.5-flash',

    -- Eskaleringstærskler
    escalation_threshold    REAL DEFAULT 0.70,
    escalation_new_tags     INTEGER DEFAULT 4,
    always_escalate_tags    TEXT[] DEFAULT ARRAY['brand','røg','ild','vandskade','ulykke'],
    always_cloud_tags       TEXT[] DEFAULT '{}',

    -- Øvrige
    tag_vocabulary_limit    INTEGER DEFAULT 80,
    enabled                 BOOLEAN DEFAULT TRUE,
    notes                   TEXT,

    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by      TEXT,

    CONSTRAINT uq_ai_config UNIQUE (customer_id, site_id)
);

-- Global default (indsæt hvis ikke findes)
INSERT INTO ai_config (customer_id, site_id, strategy, notes)
SELECT NULL, NULL, 'cloud_only', 'Global default — cloud_only er sikreste start'
WHERE NOT EXISTS (
    SELECT 1 FROM ai_config WHERE customer_id IS NULL AND site_id IS NULL
);

COMMENT ON TABLE ai_config IS
    'AI-strategi konfiguration pr. kunde/site. NULL customer_id = global default.';
"""


@dataclass
class AIConfig:
    """Effektiv AI-konfiguration for én kunde/site."""
    strategy:              str        # technical_only | local_only | local_then_cloud | cloud_only
    local_model:           str
    cloud_model:           str
    escalation_threshold:  float
    escalation_new_tags:   int
    always_escalate_tags:  list[str]
    always_cloud_tags:     list[str]
    tag_vocabulary_limit:  int
    enabled:               bool
    customer_id:           Optional[str] = None
    site_id:               Optional[str] = None
    source:                str = "default"   # default | customer | site

    @property
    def use_local(self) -> bool:
        return self.strategy in ("local_only", "local_then_cloud")

    @property
    def use_cloud(self) -> bool:
        return self.strategy in ("cloud_only", "local_then_cloud")

    @property
    def local_first(self) -> bool:
        return self.strategy == "local_then_cloud"

    def should_escalate(
        self,
        confidence:      float,
        new_tags:        list[str],
        tags:            list[str],
        change_detected: bool,
        quality_ok:      bool,
    ) -> tuple[bool, list[str]]:
        """Beregn om analyse skal eskaleres til cloud. Returnerer (escalate, reasons)."""
        reasons = []

        if not self.use_cloud:
            return False, []

        if confidence < self.escalation_threshold:
            reasons.append(f"lav_confidence:{confidence:.2f}")

        if len(new_tags) > self.escalation_new_tags:
            reasons.append(f"mange_nye_tags:{len(new_tags)}")

        critical = [t for t in tags + new_tags if t in self.always_escalate_tags]
        if critical:
            reasons.append(f"kritisk_tag:{','.join(critical)}")

        if change_detected:
            reasons.append("change_detected")

        if not quality_ok:
            reasons.append("dårlig_kvalitet")

        return len(reasons) > 0, reasons

    def should_use_cloud_directly(self, tags: list[str]) -> bool:
        """Skal dette billede sende direkte til cloud (bypass lokal model)?"""
        if self.strategy == "cloud_only":
            return True
        return any(t in self.always_cloud_tags for t in tags)


class AIConfigManager:
    """
    Læser og skriver AI-strategi konfiguration fra PostgreSQL.
    """

    def __init__(self, db):
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        from sqlalchemy import text
        try:
            self.db.execute(text(AI_CONFIG_DDL))
            self.db.execute(text("""
                DELETE FROM ai_config a
                USING ai_config b
                WHERE COALESCE(a.customer_id, '__global__') = COALESCE(b.customer_id, '__global__')
                  AND COALESCE(a.site_id, '__all__') = COALESCE(b.site_id, '__all__')
                  AND a.id > b.id
            """))
            # NULL-værdier konflikter ikke i almindelige PostgreSQL UNIQUE constraints.
            # Denne indeks sikrer præcis én global, én pr. kunde og én pr. site/kamera-scope.
            self.db.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_config_scope
                ON ai_config (
                    COALESCE(customer_id, '__global__'),
                    COALESCE(site_id, '__all__')
                )
            """))
            self.db.commit()
        except Exception as e:
            log.warning("ai_config DDL: %s", e)
            self.db.rollback()

    def get_config(
        self,
        customer_id: Optional[str] = None,
        site_id:     Optional[str] = None,
    ) -> AIConfig:
        """
        Hent effektiv config med fallback-hierarki:
          site → kunde → global → hardcoded
        """
        from sqlalchemy import text

        candidates = []

        # Site-specifik
        if site_id and customer_id:
            row = self._fetch(customer_id, site_id)
            if row:
                candidates.append(("site", row))

        # Kunde-specifik
        if customer_id:
            row = self._fetch(customer_id, None)
            if row:
                candidates.append(("customer", row))

        # Global
        row = self._fetch(None, None)
        if row:
            candidates.append(("global", row))

        if candidates:
            source, row = candidates[0]
            return self._row_to_config(row, source, customer_id, site_id)

        # Hardcoded fallback
        log.warning("Ingen ai_config fundet — bruger hardcoded defaults")
        return self._hardcoded_default(customer_id, site_id)

    def _fetch(self, customer_id, site_id):
        from sqlalchemy import text
        if customer_id is None and site_id is None:
            q = "SELECT * FROM ai_config WHERE customer_id IS NULL AND site_id IS NULL LIMIT 1"
            p = {}
        elif site_id is None:
            q = "SELECT * FROM ai_config WHERE customer_id=:cid AND site_id IS NULL LIMIT 1"
            p = {"cid": customer_id}
        else:
            q = "SELECT * FROM ai_config WHERE customer_id=:cid AND site_id=:sid LIMIT 1"
            p = {"cid": customer_id, "sid": site_id}
        return self.db.execute(text(q), p).mappings().first()

    def _row_to_config(self, row, source, customer_id, site_id) -> AIConfig:
        d = GLOBAL_DEFAULTS
        return AIConfig(
            strategy             = row.get("strategy")             or d["strategy"],
            local_model          = row.get("local_model")          or d["local_model"],
            cloud_model          = row.get("cloud_model")          or d["cloud_model"],
            escalation_threshold = row.get("escalation_threshold") or d["escalation_threshold"],
            escalation_new_tags  = row.get("escalation_new_tags")  or d["escalation_new_tags"],
            always_escalate_tags = list(row.get("always_escalate_tags") or d["always_escalate_tags"]),
            always_cloud_tags    = list(row.get("always_cloud_tags")    or d["always_cloud_tags"]),
            tag_vocabulary_limit = row.get("tag_vocabulary_limit") or d["tag_vocabulary_limit"],
            enabled              = row.get("enabled", True),
            customer_id          = customer_id,
            site_id              = site_id,
            source               = source,
        )

    def _hardcoded_default(self, customer_id, site_id) -> AIConfig:
        d = GLOBAL_DEFAULTS
        return AIConfig(
            strategy=d["strategy"], local_model=d["local_model"],
            cloud_model=d["cloud_model"],
            escalation_threshold=d["escalation_threshold"],
            escalation_new_tags=d["escalation_new_tags"],
            always_escalate_tags=d["always_escalate_tags"],
            always_cloud_tags=d["always_cloud_tags"],
            tag_vocabulary_limit=d["tag_vocabulary_limit"],
            enabled=d["enabled"],
            customer_id=customer_id, site_id=site_id, source="hardcoded",
        )

    def set_config(
        self,
        strategy:             str,
        customer_id:          Optional[str] = None,
        site_id:              Optional[str] = None,
        customer_name:        Optional[str] = None,
        site_name:            Optional[str] = None,
        local_model:          str  = "qwen2.5vl:7b",
        cloud_model:          str  = "gemini-2.5-flash",
        escalation_threshold: float = 0.70,
        escalation_new_tags:  int   = 4,
        always_escalate_tags: Optional[list] = None,
        always_cloud_tags:    Optional[list] = None,
        tag_vocabulary_limit: int   = 80,
        enabled:              bool  = True,
        notes:                Optional[str] = None,
        updated_by:           str   = "admin",
    ) -> AIConfig:
        """Gem eller opdater config for kunde/site."""
        from sqlalchemy import text

        if strategy not in VALID_STRATEGIES:
            raise ValueError(f"Ugyldig strategi '{strategy}'. Gyldige: {VALID_STRATEGIES}")

        params = {
            "cid":        customer_id,
            "sid":        site_id,
            "cname":      customer_name,
            "sname":      site_name,
            "strategy":   strategy,
            "local":      local_model,
            "cloud":      cloud_model,
            "thresh":     escalation_threshold,
            "new_tags":   escalation_new_tags,
            "esc_tags":   always_escalate_tags or GLOBAL_DEFAULTS["always_escalate_tags"],
            "cloud_tags": always_cloud_tags or [],
            "vocab_limit": tag_vocabulary_limit,
            "enabled":    enabled,
            "notes":      notes,
            "by":         updated_by,
        }
        updated = self.db.execute(text("""
            UPDATE ai_config SET
                customer_name        = COALESCE(:cname, customer_name),
                site_name            = COALESCE(:sname, site_name),
                strategy             = :strategy,
                local_model          = :local,
                cloud_model          = :cloud,
                escalation_threshold = :thresh,
                escalation_new_tags  = :new_tags,
                always_escalate_tags = :esc_tags,
                always_cloud_tags    = :cloud_tags,
                tag_vocabulary_limit = :vocab_limit,
                enabled              = :enabled,
                notes                = :notes,
                updated_by           = :by,
                updated_at           = NOW()
            WHERE COALESCE(customer_id, '__global__') = COALESCE(:cid, '__global__')
              AND COALESCE(site_id, '__all__') = COALESCE(:sid, '__all__')
        """), params)
        if updated.rowcount == 0:
            self.db.execute(text("""
                INSERT INTO ai_config (
                    customer_id, site_id, customer_name, site_name,
                    strategy, local_model, cloud_model,
                    escalation_threshold, escalation_new_tags,
                    always_escalate_tags, always_cloud_tags,
                    tag_vocabulary_limit, enabled, notes, updated_by, updated_at
                ) VALUES (
                    :cid, :sid, :cname, :sname,
                    :strategy, :local, :cloud,
                    :thresh, :new_tags,
                    :esc_tags, :cloud_tags,
                    :vocab_limit, :enabled, :notes, :by, NOW()
                )
            """), params)
        self.db.commit()
        log.info("AI config sat: customer=%s site=%s strategy=%s", customer_id, site_id, strategy)
        return self.get_config(customer_id, site_id)

    def list_all(self) -> list[dict]:
        """Vis alle konfigurationer — til admin UI."""
        from sqlalchemy import text
        rows = self.db.execute(text("""
            SELECT *,
                CASE WHEN customer_id IS NULL THEN 'Global default'
                     WHEN site_id IS NULL THEN 'Kunde: ' || COALESCE(customer_name, customer_id)
                     ELSE 'Site: ' || COALESCE(site_name, site_id)
                END AS display_name
            FROM ai_config
            ORDER BY customer_id NULLS FIRST, site_id NULLS FIRST
        """)).mappings().all()
        return [dict(r) for r in rows]

    def delete_config(self, customer_id: str, site_id: Optional[str] = None):
        """Slet kunde/site-specifik config (falder tilbage til global)."""
        from sqlalchemy import text
        if customer_id is None:
            raise ValueError("Kan ikke slette global config")
        self.db.execute(text("""
            DELETE FROM ai_config
            WHERE customer_id=:cid AND (site_id=:sid OR (:sid IS NULL AND site_id IS NULL))
        """), {"cid": customer_id, "sid": site_id})
        self.db.commit()
