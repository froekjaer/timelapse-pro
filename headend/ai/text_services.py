"""
TimeLapse Pro — Tekst-model Services
======================================
SIEM-analyse og CMDB-enrichment via llama3.2:latest (tekstmodel).

SIEMAnalyser:
  - Korrelerer heartbeats, fejllog og capture-statistik
  - Returnerer strukturerede hændelser med alvorlighedsgrad
  - Dansk output

CMDBEnricher:
  - Vurderer device-helbred baseret på historiske data
  - Foreslår vedligehold og klassificerer status
  - Dansk output
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional, Any

import httpx

log = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
TEXT_MODEL      = "llama3.2:latest"
TIMEOUT_TEXT    = 60


# =============================================================================
# DATAKLASSER
# =============================================================================

@dataclass
class SIEMEvent:
    severity:         str           # info / warning / critical
    event_type:       str           # heartbeat_gap / temp_spike / capture_failure / osv.
    summary:          str           # dansk, menneskevenlig beskrivelse
    device_id:        Optional[str]
    location_id:      Optional[str]
    recommended_action: str
    affects_captures: bool
    raw_indicators:   list[str]     # de faktiske datapunkter der trigede det
    confidence:       float         # 0.0–1.0


@dataclass
class CMDBAssessment:
    device_id:                str
    health_status:            str           # healthy / degraded / critical / unknown
    issues:                   list[str]     # konkrete problemer
    recommendations:          list[str]     # hvad skal gøres
    maintenance_due:          bool
    estimated_days_to_issue:  Optional[int] # None = ukendt
    tags:                     list[str]     # cmdb-tags: outdoor / indoor / high_humidity / osv.
    summary:                  str


# =============================================================================
# BASE — fælles HTTP-klient
# =============================================================================

class _OllamaTextBase:

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = TEXT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model    = model
        self._client  = httpx.Client(timeout=TIMEOUT_TEXT)

    def _call(self, prompt: str, system: str = "") -> str:
        """Kald tekstmodel. Returnerer rå tekst fra modellen."""
        payload: dict[str, Any] = {
            "model":  self.model,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 800},
        }
        if system:
            payload["system"] = system
            payload["prompt"] = prompt
        else:
            payload["prompt"] = prompt

        try:
            resp = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=TIMEOUT_TEXT,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except httpx.TimeoutException:
            log.error("Ollama tekst-model timeout")
            raise
        except Exception as e:
            log.error("Ollama tekst-fejl: %s", e)
            raise

    def _parse_json(self, text: str) -> dict:
        """Robust JSON-parsing af model-output."""
        for pattern in [
            r"```(?:json)?\s*(\{.*?\})\s*```",
            r"(\{.*\})",
        ]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                candidate = re.sub(r",\s*([}\]])", r"\1", match.group(1))
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        return {}


# =============================================================================
# SIEM ANALYSER
# =============================================================================

SIEM_SYSTEM = """Du er et dansk SIEM-system (Security Information and Event Management)
specialiseret i IoT-kameraer og edge-enheder på byggepladser.
Du analyserer tekniske data og returnerer KUN JSON.
Vær præcis, konkret og handlingsorienteret. Dansk output."""

SIEM_PROMPT = """
Analyser disse systemhændelser og returner en SIEM-vurdering.

## DATA
{data_block}

## RETURNER PRÆCIS DETTE JSON:
{{
  "severity": "info",
  "event_type": "type_af_hændelse",
  "summary": "Dansk beskrivelse af hvad der er observeret",
  "recommended_action": "Konkret handling der skal tages",
  "affects_captures": false,
  "confidence": 0.85,
  "raw_indicators": ["indikator1", "indikator2"]
}}

Mulige severity-værdier: info, warning, critical
Mulige event_type-værdier:
  heartbeat_gap, heartbeat_storm, temperature_spike, temperature_normal,
  capture_failure_rate, upload_backlog, reboot_loop, config_drift,
  gpio_fault, disk_pressure, memory_pressure, network_instability,
  break_glass_access, unauthorized_access, service_restart, normal

Returner KUN JSON."""


class SIEMAnalyser(_OllamaTextBase):
    """
    Analyserer systemhændelser og returnerer strukturerede SIEM-events.

    Input: dict med relevante datapunkter (heartbeats, temperatur, capture-statistik)
    Output: SIEMEvent
    """

    def analyse_heartbeats(
        self,
        device_id:   str,
        location_id: str,
        heartbeats:  list[dict],
        captures:    list[dict],
        system_info: dict,
    ) -> SIEMEvent:
        """
        Analysér heartbeat-historik for en device.

        heartbeats: liste af heartbeat-records (captured_at, cpu_temp, free_disk, ...)
        captures:   seneste capture-resultater (quality_passed, uploaded, ...)
        system_info: dict med os, platform, service_version, uptime, ...
        """
        data_block = json.dumps({
            "device_id":    device_id,
            "location_id":  location_id,
            "heartbeats":   heartbeats[-48:],   # maks 48 (seneste 24t ved 30-min interval)
            "captures_24h": captures[-50:],
            "system_info":  system_info,
        }, ensure_ascii=False, indent=2)

        prompt = SIEM_PROMPT.format(data_block=data_block)

        try:
            raw = self._call(prompt=prompt, system=SIEM_SYSTEM)
            parsed = self._parse_json(raw)
            return SIEMEvent(
                severity          = parsed.get("severity", "info"),
                event_type        = parsed.get("event_type", "unknown"),
                summary           = parsed.get("summary", "Ingen analyse tilgængelig"),
                device_id         = device_id,
                location_id       = location_id,
                recommended_action= parsed.get("recommended_action", "Ingen handling nødvendig"),
                affects_captures  = bool(parsed.get("affects_captures", False)),
                raw_indicators    = list(parsed.get("raw_indicators", [])),
                confidence        = float(parsed.get("confidence", 0.5)),
            )
        except Exception as e:
            log.error("SIEM analyse fejlede for %s: %s", device_id, e)
            return SIEMEvent(
                severity="warning", event_type="analysis_error",
                summary=f"SIEM-analyse fejlede: {e}",
                device_id=device_id, location_id=location_id,
                recommended_action="Tjek Ollama-service",
                affects_captures=False, raw_indicators=[], confidence=0.0,
            )

    def analyse_break_glass(
        self,
        device_id:  str,
        admin_id:   str,
        session_log: list[str],
        duration_s:  int,
    ) -> SIEMEvent:
        """Analysér en break-glass SSH-session."""
        data_block = json.dumps({
            "event":       "break_glass_access",
            "device_id":   device_id,
            "admin_id":    admin_id,
            "duration_s":  duration_s,
            "session_log": session_log[:100],   # maks 100 linjer
        }, ensure_ascii=False, indent=2)

        prompt = SIEM_PROMPT.format(data_block=data_block)
        raw    = self._call(prompt=prompt, system=SIEM_SYSTEM)
        parsed = self._parse_json(raw)

        return SIEMEvent(
            severity          = parsed.get("severity", "warning"),
            event_type        = "break_glass_access",
            summary           = parsed.get("summary", f"Break-glass adgang til {device_id} af {admin_id}"),
            device_id         = device_id,
            location_id       = None,
            recommended_action= parsed.get("recommended_action", "Verificer handlinger i session-log"),
            affects_captures  = bool(parsed.get("affects_captures", False)),
            raw_indicators    = [f"admin:{admin_id}", f"duration:{duration_s}s"],
            confidence        = 0.95,
        )

    def correlate_events(self, events: list[SIEMEvent]) -> Optional[SIEMEvent]:
        """
        Korrelér flere SIEM-events til én overordnet vurdering.
        Relevant når samme device har gentagne warnings.
        """
        if not events:
            return None
        if len(events) == 1:
            return events[0]

        summary_data = [
            {"severity": e.severity, "event_type": e.event_type, "summary": e.summary}
            for e in events
        ]
        data_block = json.dumps({
            "task":   "correlate",
            "device": events[0].device_id,
            "events": summary_data,
        }, ensure_ascii=False, indent=2)

        prompt = SIEM_PROMPT.format(data_block=data_block)
        raw    = self._call(prompt=prompt, system=SIEM_SYSTEM)
        parsed = self._parse_json(raw)

        return SIEMEvent(
            severity          = parsed.get("severity", "warning"),
            event_type        = "correlated_" + events[0].event_type,
            summary           = parsed.get("summary", "Korreleret hændelse"),
            device_id         = events[0].device_id,
            location_id       = events[0].location_id,
            recommended_action= parsed.get("recommended_action", ""),
            affects_captures  = any(e.affects_captures for e in events),
            raw_indicators    = [e.event_type for e in events],
            confidence        = float(parsed.get("confidence", 0.6)),
        )


# =============================================================================
# CMDB ENRICHER
# =============================================================================

CMDB_SYSTEM = """Du er en CMDB-specialist (Configuration Management Database)
specialiseret i IoT-kameraer og edge-enheder (Orange Pi, Raspberry Pi) på udendørs byggepladser.
Du analyserer enhedsdata og returnerer KUN JSON med driftsvurderinger.
Dansk output, konkrete og handlingsorienterede anbefalinger."""

CMDB_PROMPT = """
Vurdér denne edge-enhed baseret på de tilgængelige data.

## ENHEDSDATA
{device_block}

## RETURNER PRÆCIS DETTE JSON:
{{
  "health_status": "healthy",
  "issues": [],
  "recommendations": [],
  "maintenance_due": false,
  "estimated_days_to_issue": null,
  "tags": ["outdoor", "production"],
  "summary": "Dansk overordnet vurdering af enheden"
}}

Mulige health_status: healthy, degraded, critical, unknown
Mulige issues (eksempler):
  disk_nearing_full, high_temperature_trend, frequent_reboots,
  capture_failure_rate_high, upload_backlog_growing, outdated_software,
  gpio_instability, network_packet_loss, battery_low, camera_degradation

Mulige tags:
  outdoor, indoor, high_humidity, dusty_environment, vibration_risk,
  production, staging, lab, primary, secondary, critical_location,
  needs_inspection, scheduled_maintenance, recently_serviced

Returner KUN JSON."""


class CMDBEnricher(_OllamaTextBase):
    """
    Beriger CMDB-data med AI-vurdering af device-helbred.
    """

    def assess_device(
        self,
        device_id:      str,
        platform:       str,
        location_id:    Optional[str],
        environment:    str,
        uptime_days:    Optional[float],
        cpu_temp_history: list[float],
        disk_usage_pct: Optional[float],
        capture_success_rate_7d: Optional[float],
        upload_success_rate_7d:  Optional[float],
        reboot_count_7d: int,
        software_version: Optional[str],
        last_inspection: Optional[str],
        notes:          Optional[str] = None,
    ) -> CMDBAssessment:
        """
        Fuld device-vurdering til CMDB.
        """
        device_block = json.dumps({
            "device_id":         device_id,
            "platform":          platform,
            "location_id":       location_id,
            "environment":       environment,
            "uptime_days":       uptime_days,
            "cpu_temp_history":  cpu_temp_history[-48:] if cpu_temp_history else [],
            "cpu_temp_avg":      round(sum(cpu_temp_history) / len(cpu_temp_history), 1) if cpu_temp_history else None,
            "cpu_temp_max":      max(cpu_temp_history) if cpu_temp_history else None,
            "disk_usage_pct":    disk_usage_pct,
            "capture_success_7d": capture_success_rate_7d,
            "upload_success_7d":  upload_success_rate_7d,
            "reboot_count_7d":   reboot_count_7d,
            "software_version":  software_version,
            "last_inspection":   last_inspection,
            "notes":             notes,
        }, ensure_ascii=False, indent=2)

        try:
            raw    = self._call(prompt=CMDB_PROMPT.format(device_block=device_block), system=CMDB_SYSTEM)
            parsed = self._parse_json(raw)
            return CMDBAssessment(
                device_id                = device_id,
                health_status            = parsed.get("health_status", "unknown"),
                issues                   = list(parsed.get("issues", [])),
                recommendations          = list(parsed.get("recommendations", [])),
                maintenance_due          = bool(parsed.get("maintenance_due", False)),
                estimated_days_to_issue  = parsed.get("estimated_days_to_issue"),
                tags                     = list(parsed.get("tags", [])),
                summary                  = parsed.get("summary", "Ingen vurdering tilgængelig"),
            )
        except Exception as e:
            log.error("CMDB assessment fejlede for %s: %s", device_id, e)
            return CMDBAssessment(
                device_id=device_id, health_status="unknown",
                issues=["assessment_failed"], recommendations=["Tjek Ollama-service"],
                maintenance_due=False, estimated_days_to_issue=None,
                tags=[], summary=f"Vurdering fejlede: {e}",
            )

    def batch_assess(
        self,
        devices: list[dict],
    ) -> list[CMDBAssessment]:
        """Vurdér flere devices — bruges til daglig CMDB-opdatering."""
        results = []
        for d in devices:
            try:
                assessment = self.assess_device(**d)
                results.append(assessment)
            except Exception as e:
                log.error("Batch assess fejl for %s: %s", d.get("device_id"), e)
        return results
