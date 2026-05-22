"""
TimeLapse Pro — Alarm Engine
==============================
Evaluerer alarm-regler mod AI-analyseresultater efter hierarkiet:

  Global (config_defaults.alarm_rules)
    └── Kunde (customer.config_overrides → alarm_rules)
          └── Site (site.config_overrides → alarm_rules)
                └── Device (device.device_config → alarm_rules)

Merge-strategi: regler merges per ID — lavere lag kan:
  - Tilsidesætte en specifik regel (enabled, thresholds osv.)
  - Tilføje nye regler
  - Deaktivere en regel med enabled=false

Regel-struktur:
  {
    "id":          "fire_smoke",          # unik ID
    "name":        "Brand eller røg",     # visningsnavn
    "enabled":     true,
    "severity":    "critical",            # critical | warning | maintenance | info
    "triggers": {
      "tags":      ["fire", "smoke"],     # match på AI-tags (OR-logik som default)
      "causes":    ["condensation_on_lens"], # match på AI probable_cause
      "logic":     "OR"                  # OR | AND
    },
    "time_filter": null,                  # eller {"start": "22:00", "end": "06:00"}
    "min_confidence": 0.5,
    "cooldown_minutes": 60,               # minimum minutter mellem alarmer for samme regel
    "description": "Alarm ved tegn på brand eller røg"
  }

SABSA: Integrity — alarm-engine er read-only ift. captures; skriver kun til alarm_events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("headend.alarm")


# ── Globale standardregler ────────────────────────────────────────────────────

DEFAULT_ALARM_RULES = [
    {
        "id":          "fire_smoke",
        "name":        "Brand eller røg",
        "enabled":     True,
        "severity":    "critical",
        "triggers":    {"tags": ["fire", "smoke", "flames"], "causes": [], "logic": "OR"},
        "time_filter": None,
        "min_confidence": 0.5,
        "cooldown_minutes": 30,
        "description": "Tegn på brand eller røg i billedet",
    },
    {
        "id":          "night_intrusion",
        "name":        "Person/køretøj om natten",
        "enabled":     True,
        "severity":    "warning",
        "triggers":    {"tags": ["person", "worker", "car", "truck", "van", "motorcycle"], "causes": [], "logic": "OR"},
        "time_filter": {"start": "22:00", "end": "06:00"},
        "min_confidence": 0.6,
        "cooldown_minutes": 120,
        "description": "Person eller køretøj observeret i nattetimerne (22-06)",
    },
    {
        "id":          "condensation",
        "name":        "Kondens på linse",
        "enabled":     True,
        "severity":    "maintenance",
        "triggers":    {"tags": [], "causes": ["condensation_on_lens"], "logic": "OR"},
        "time_filter": None,
        "min_confidence": 0.65,
        "cooldown_minutes": 240,
        "description": "Kondens detekteret på kameralinsen — tjek kamerahus",
    },
    {
        "id":          "dirty_lens",
        "name":        "Snavset linse",
        "enabled":     True,
        "severity":    "maintenance",
        "triggers":    {"tags": [], "causes": ["dirty_lens"], "logic": "OR"},
        "time_filter": None,
        "min_confidence": 0.6,
        "cooldown_minutes": 480,
        "description": "Snavs eller belægning på linsen — rengøring nødvendig",
    },
    {
        "id":          "camera_moved",
        "name":        "Kamera flyttet",
        "enabled":     True,
        "severity":    "warning",
        "triggers":    {"tags": [], "causes": ["camera_moved"], "logic": "OR"},
        "time_filter": None,
        "min_confidence": 0.6,
        "cooldown_minutes": 60,
        "description": "Kameraets vinkel ser ud til at have ændret sig",
    },
    {
        "id":          "hardware_failure",
        "name":        "Hardwarefejl",
        "enabled":     True,
        "severity":    "critical",
        "triggers":    {"tags": [], "causes": ["hardware_failure"], "logic": "OR"},
        "time_filter": None,
        "min_confidence": 0.5,
        "cooldown_minutes": 60,
        "description": "Mulig hardwarefejl på kamera eller linse",
    },
    {
        "id":          "flood_water",
        "name":        "Vand eller oversvømmelse",
        "enabled":     True,
        "severity":    "critical",
        "triggers":    {"tags": ["flood", "water", "river", "lake"], "causes": [], "logic": "AND"},
        "time_filter": None,
        "min_confidence": 0.6,
        "cooldown_minutes": 60,
        "description": "Tegn på vand eller oversvømmelse på byggepladsen",
    },
    {
        "id":          "accident_person",
        "name":        "Personskade eller uheld",
        "enabled":     False,  # Deaktiveret som default — kræver manuel aktivering
        "severity":    "critical",
        "triggers":    {"tags": ["person", "worker"], "causes": [], "logic": "OR"},
        "time_filter": None,
        "min_confidence": 0.7,
        "cooldown_minutes": 30,
        "description": "Person observeret i potentielt farlig situation",
    },
]


# ── Hjælpefunktioner ──────────────────────────────────────────────────────────

def _merge_rules(base: list, override: list) -> list:
    """
    Merge alarm-regler per ID.
    Override kan tilsidesætte felter i eksisterende regler eller tilføje nye.
    """
    result = {r["id"]: dict(r) for r in base}
    for rule in override:
        rule_id = rule.get("id")
        if not rule_id:
            continue
        if rule_id in result:
            result[rule_id].update(rule)
        else:
            result[rule_id] = dict(rule)
    return list(result.values())


def _is_in_time_window(time_filter: Optional[dict], timezone_str: str = "Europe/Copenhagen") -> bool:
    """Tjek om nuværende tidspunkt er inden for det angivne tidsvindue."""
    if not time_filter:
        return True

    try:
        from zoneinfo import ZoneInfo
        now   = datetime.now(ZoneInfo(timezone_str))
        start = datetime.strptime(time_filter["start"], "%H:%M").time()
        end   = datetime.strptime(time_filter["end"],   "%H:%M").time()
        t     = now.time()

        if start <= end:
            return start <= t <= end
        else:
            # Natvinduer der krydser midnat: 22:00–06:00
            return t >= start or t <= end
    except Exception:
        return True


def _get_device_timezone(db, device_id: str) -> str:
    """Hent tidszone for device via site-konfiguration."""
    try:
        from database import Device, Site
        device = db.query(Device).filter_by(device_id=device_id).first()
        if device and hasattr(device, "site_id") and device.site_id:
            site = db.query(Site).filter_by(id=device.site_id).first()
            if site and site.timezone:
                return site.timezone
    except Exception:
        pass
    return "Europe/Copenhagen"


# ── Alarm Engine ──────────────────────────────────────────────────────────────

class AlarmEngine:
    """
    Evaluerer alarm-regler mod AI-analyseresultater.

    Bruges fra integration.py's AI-worker efter hvert capture.
    """

    def __init__(self, db):
        self._db = db

    def get_rules_for_device(self, device_id: str) -> list[dict]:
        """
        Hent merged alarm-regler for en enhed.
        Følger hierarkiet: Global → Kunde → Site → Device.
        """
        from database import ConfigDefaults, Customer, Device, Site

        rules = list(DEFAULT_ALARM_RULES)  # Lag 0: hardcodede defaults

        try:
            # Lag 1: Global config_defaults
            defaults = self._db.query(ConfigDefaults).first()
            if defaults and hasattr(defaults, "alarm_rules") and defaults.alarm_rules:
                global_rules = json.loads(defaults.alarm_rules)
                rules = _merge_rules(rules, global_rules)

            device = self._db.query(Device).filter_by(device_id=device_id).first()
            if not device:
                return [r for r in rules if r.get("enabled", True)]

            site     = self._db.query(Site).filter_by(id=device.site_id).first() if hasattr(device, "site_id") and device.site_id else None
            customer = self._db.query(Customer).filter_by(id=site.customer_id).first() if site else None

            # Lag 2: Kunde
            if customer and hasattr(customer, "config_overrides") and customer.config_overrides:
                cfg = json.loads(customer.config_overrides)
                if "alarm_rules" in cfg:
                    rules = _merge_rules(rules, cfg["alarm_rules"])

            # Lag 3: Site
            if site and hasattr(site, "config_overrides") and site.config_overrides:
                cfg = json.loads(site.config_overrides)
                if "alarm_rules" in cfg:
                    rules = _merge_rules(rules, cfg["alarm_rules"])

            # Lag 4: Device
            device_cfg_str = getattr(device, "device_config", None) or getattr(device, "config_overrides", None)
            if device_cfg_str:
                cfg = json.loads(device_cfg_str)
                if "alarm_rules" in cfg:
                    rules = _merge_rules(rules, cfg["alarm_rules"])

        except Exception as e:
            log.warning("Fejl ved merge af alarm-regler for %s: %s", device_id, e)

        return [r for r in rules if r.get("enabled", True)]

    def evaluate(
        self,
        capture_id:   int,
        device_id:    str,
        ai_result:    Optional[dict],
        tags:         Optional[list[str]],
        captured_at:  Optional[datetime] = None,
    ) -> list[dict]:
        """
        Evaluér alle aktive regler mod et captures AI-data.
        Returnerer liste af udløste alarmer (kan være tom).
        """
        if not ai_result and not tags:
            return []

        rules    = self.get_rules_for_device(device_id)
        tz       = _get_device_timezone(self._db, device_id)
        fired    = []
        now_utc  = datetime.now(timezone.utc)

        for rule in rules:
            try:
                result = self._check_rule(rule, capture_id, device_id, ai_result, tags or [], tz, now_utc)
                if result:
                    fired.append(result)
                    self._save_alarm_event(result)
            except Exception as e:
                log.warning("Fejl ved evaluering af regel %s: %s", rule.get("id"), e)

        if fired:
            log.info("Alarm: %d regler udløst for capture %d (%s)",
                     len(fired), capture_id, device_id)

        return fired

    def _check_rule(
        self,
        rule:        dict,
        capture_id:  int,
        device_id:   str,
        ai_result:   Optional[dict],
        tags:        list[str],
        timezone_str: str,
        now_utc:     datetime,
    ) -> Optional[dict]:
        """Tjek én regel — returnerer alarm-dict eller None."""

        # Tidsvindue
        if not _is_in_time_window(rule.get("time_filter"), timezone_str):
            return None

        # Konfidencetærskel
        min_conf   = float(rule.get("min_confidence", 0.5))
        confidence = float(ai_result.get("confidence", 0)) if ai_result else 0

        if ai_result and confidence < min_conf:
            return None

        # Cooldown — spring over hvis vi allerede har alarmeret for denne regel for nylig
        if self._in_cooldown(rule["id"], device_id, rule.get("cooldown_minutes", 60), now_utc):
            return None

        # Tjek triggers
        triggers = rule.get("triggers", {})
        logic    = triggers.get("logic", "OR").upper()

        tag_matches   = [t for t in triggers.get("tags",   []) if t in tags]
        cause_matches = []
        if ai_result:
            cause = ai_result.get("probable_cause", "")
            cause_matches = [c for c in triggers.get("causes", []) if c == cause]

        matched = bool(tag_matches or cause_matches)

        if logic == "AND":
            # Alle triggers skal matche
            tag_required   = triggers.get("tags", [])
            cause_required = triggers.get("causes", [])
            matched = (
                (not tag_required   or all(t in tags for t in tag_required)) and
                (not cause_required or (ai_result and ai_result.get("probable_cause") in cause_required))
            )

        if not matched:
            return None

        # Alarm udløst
        matched_on = []
        if tag_matches:
            matched_on.extend([f"#tag:{t}" for t in tag_matches])
        if cause_matches:
            matched_on.extend([f"cause:{c}" for c in cause_matches])

        return {
            "rule_id":     rule["id"],
            "rule_name":   rule["name"],
            "severity":    rule.get("severity", "warning"),
            "capture_id":  capture_id,
            "device_id":   device_id,
            "description": rule.get("description", ""),
            "matched_on":  matched_on,
            "confidence":  confidence,
            "triggered_at": now_utc.isoformat(),
        }

    def _in_cooldown(self, rule_id: str, device_id: str, cooldown_minutes: int, now_utc: datetime) -> bool:
        """Tjek om denne regel er i cooldown for denne enhed."""
        try:
            from sqlalchemy import text
            cutoff = now_utc - timedelta(minutes=cooldown_minutes)
            row = self._db.execute(text("""
                SELECT id FROM alarm_events
                WHERE rule_id = :rule_id
                AND device_id = :device_id
                AND triggered_at > :cutoff
                ORDER BY triggered_at DESC LIMIT 1
            """), {"rule_id": rule_id, "device_id": device_id, "cutoff": cutoff.isoformat()}).fetchone()
            return row is not None
        except Exception:
            return False

    def _save_alarm_event(self, alarm: dict) -> None:
        """Gem alarm i alarm_events-tabellen."""
        try:
            from sqlalchemy import text
            self._db.execute(text("""
                INSERT INTO alarm_events
                  (rule_id, rule_name, severity, capture_id, device_id,
                   description, matched_on, confidence, triggered_at)
                VALUES
                  (:rule_id, :rule_name, :severity, :capture_id, :device_id,
                   :description, :matched_on, :confidence, :triggered_at)
            """), {
                "rule_id":      alarm["rule_id"],
                "rule_name":    alarm["rule_name"],
                "severity":     alarm["severity"],
                "capture_id":   alarm["capture_id"],
                "device_id":    alarm["device_id"],
                "description":  alarm["description"],
                "matched_on":   json.dumps(alarm["matched_on"]),
                "confidence":   alarm["confidence"],
                "triggered_at": alarm["triggered_at"],
            })
            self._db.commit()
            log.warning(
                "ALARM [%s] %s — capture %d (%s) — match: %s",
                alarm["severity"].upper(),
                alarm["rule_name"],
                alarm["capture_id"],
                alarm["device_id"],
                ", ".join(alarm["matched_on"]),
            )
        except Exception as e:
            log.error("Kunne ikke gemme alarm: %s", e)
            return

        # Send notifikationer
        try:
            from ai.notify import notify
            notify(alarm, self._db)
        except Exception as ne:
            log.debug("Notifikations-fejl (ikke kritisk): %s", ne)


# ── DB Migration ──────────────────────────────────────────────────────────────

def run_alarm_migration(engine) -> None:
    """
    Opret alarm_events-tabel og tilføj alarm_rules-kolonne til config_defaults.
    Idempotent — kør ved headend-startup.
    """
    from sqlalchemy import text
    with engine.connect() as conn:
        # alarm_events tabel
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alarm_events (
                    id            SERIAL PRIMARY KEY,
                    rule_id       TEXT NOT NULL,
                    rule_name     TEXT,
                    severity      TEXT NOT NULL,
                    capture_id    INTEGER,
                    device_id     TEXT,
                    description   TEXT,
                    matched_on    TEXT,
                    confidence    REAL,
                    triggered_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    acknowledged_at  TIMESTAMP,
                    acknowledged_by  TEXT,
                    notes         TEXT
                )
            """))
            conn.commit()
            log.info("alarm_events tabel klar")
        except Exception as e:
            log.debug("alarm_events: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass

        # alarm_rules kolonne på config_defaults
        try:
            conn.execute(text("ALTER TABLE config_defaults ADD COLUMN alarm_rules TEXT"))
            conn.commit()
            log.info("config_defaults.alarm_rules kolonne tilføjet")
        except Exception:
            pass
