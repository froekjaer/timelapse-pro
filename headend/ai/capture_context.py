"""
TimeLapse Pro — Capture Context Builder
=======================================
Bygger en kompakt, menneskelæsbar kontekstblok der fodres til vision-prompten
(Gemini og Ollama) FØR billedet analyseres.

Formål: give modellen den viden et menneske ville have, når det kigger på
billedet — hvilken kunde/site/kameraposition det er, hvad klokken er (dag/nat),
og hvad kameraet NORMALT viser. Det er forudsætningen for at modellen kan
vurdere AFVIGELSER ("en bil i indkørslen den ikke plejer at se", "personer i
baggården om natten") frem for bare at liste objekter.

Konteksten er ren læse-only metadata — den indeholder ALDRIG persondata
(navne, ansigter, nummerplader). Baseline/context_notes redigeres af admin pr.
kamera (Camera.baseline_description / Camera.context_notes).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# Default tidszone hvis site ikke har en sat (Danmark).
DEFAULT_TZ = "Europe/Copenhagen"


@dataclass
class CaptureContext:
    """Kontekst om ét billede — alt sammen ikke-personhenførbar metadata."""
    customer_name:        Optional[str] = None
    site_name:            Optional[str] = None
    camera_name:          Optional[str] = None
    local_timestamp:      Optional[str] = None   # ISO i site-tidszone
    part_of_day:          Optional[str] = None   # nat | dæmring | dag | aften
    season:               Optional[str] = None   # vinter | forår | sommer | efterår
    perspective:          Optional[str] = None   # fx "high_angle" / "eye_level"
    baseline_description:  Optional[str] = None   # hvad kameraet normalt viser
    context_notes:        Optional[str] = None   # ekstra driftsnoter til AI

    @property
    def is_night(self) -> bool:
        return self.part_of_day == "nat"


def _part_of_day(hour: int) -> str:
    """Grov dag/nat-bucket ud fra lokal time. Modellen ser også billedets
    lysstyrke — dette er kontekst, ikke en sandhed."""
    if 22 <= hour or hour < 5:
        return "nat"
    if 5 <= hour < 8 or 18 <= hour < 22:
        return "dæmring"
    if 8 <= hour < 18:
        return "dag"
    return "aften"


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "vinter"
    if month in (3, 4, 5):
        return "forår"
    if month in (6, 7, 8):
        return "sommer"
    return "efterår"


def _localize(captured_at: Optional[datetime], tz_name: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Returnér (iso_local, part_of_day, season). Robust over for manglende tz-data."""
    if not captured_at:
        return None, None, None
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name or DEFAULT_TZ)
        # captured_at er typisk naive UTC i denne kodebase — antag UTC hvis ingen tzinfo.
        if captured_at.tzinfo is None:
            from datetime import timezone as _tz
            captured_at = captured_at.replace(tzinfo=_tz.utc)
        local = captured_at.astimezone(tz)
    except Exception as exc:  # zoneinfo mangler tzdata e.l. — fald tilbage til rå tid
        log.debug("capture_context: kunne ikke lokalisere tid (%s) — bruger rå", exc)
        local = captured_at
    return local.isoformat(timespec="minutes"), _part_of_day(local.hour), _season(local.month)


def build_capture_context(db, capture, device) -> CaptureContext:
    """Resolvér kontekst for ét capture.

    Kilder, i prioriteret rækkefølge:
      - Aktiv logisk Camera (via DeviceAssignment) → baseline/context_notes + site-tz
      - Device-felter (customer_name/site_name/camera_name) som fallback
      - capture.captured_at → lokal tid + dag/nat + årstid
      - capture.perspective → kameravinkel

    Fejler aldrig hårdt: returnerer en så-udfyldt-som-muligt CaptureContext.
    """
    customer_name = getattr(device, "customer_name", None) if device else None
    site_name     = getattr(device, "site_name", None) if device else None
    camera_name   = getattr(device, "camera_name", None) if device else None
    tz_name       = DEFAULT_TZ
    baseline      = None
    notes         = None

    try:
        from database import Camera, DeviceAssignment, Site
        device_id = getattr(capture, "device_id", None) or (getattr(device, "device_id", None) if device else None)
        if device_id:
            assignment = (
                db.query(DeviceAssignment)
                .filter_by(device_id=device_id)
                .filter(DeviceAssignment.unassigned_at.is_(None))
                .order_by(DeviceAssignment.assigned_at.desc())
                .first()
            )
            cam = db.query(Camera).filter_by(id=assignment.camera_id).first() if assignment else None
            if cam:
                camera_name = cam.camera_name or camera_name
                # Håndskrevet baseline vinder; ellers den selvlærende auto-baseline.
                human_baseline = (getattr(cam, "baseline_description", None) or "").strip()
                auto_baseline  = (getattr(cam, "auto_baseline", None) or "").strip()
                baseline    = human_baseline or auto_baseline or None
                notes       = getattr(cam, "context_notes", None)
                site = db.query(Site).filter_by(id=cam.site_id).first() if cam.site_id else None
                if site:
                    site_name = site.name or site_name
                    tz_name   = getattr(site, "timezone", None) or DEFAULT_TZ
    except Exception as exc:
        log.debug("capture_context: kunne ikke resolve Camera/Site (%s)", exc)

    local_ts, part, season = _localize(getattr(capture, "captured_at", None), tz_name)

    return CaptureContext(
        customer_name        = customer_name,
        site_name            = site_name,
        camera_name          = camera_name,
        local_timestamp      = local_ts,
        part_of_day          = part,
        season               = season,
        perspective          = getattr(capture, "perspective", None),
        baseline_description  = (baseline or "").strip() or None,
        context_notes        = (notes or "").strip() or None,
    )


def format_context_block(ctx: Optional[CaptureContext]) -> str:
    """Render konteksten til en kompakt blok til prompten. Tom streng hvis
    ingen brugbar kontekst (så prompten falder tilbage til generel adfærd)."""
    if ctx is None:
        return ""

    lines: list[str] = []
    where = ", ".join(p for p in (ctx.customer_name, ctx.site_name, ctx.camera_name) if p)
    if where:
        lines.append(f"- Lokation: {where}")
    when_bits = [b for b in (ctx.local_timestamp, ctx.part_of_day, ctx.season) if b]
    if when_bits:
        lines.append(f"- Tidspunkt: {', '.join(when_bits)} (lokal tid)")
    if ctx.perspective:
        lines.append(f"- Kameravinkel: {ctx.perspective}")
    if ctx.baseline_description:
        lines.append(f"- Normalbillede for dette kamera: {ctx.baseline_description}")
    if ctx.context_notes:
        lines.append(f"- Driftsnoter: {ctx.context_notes}")

    if not lines:
        return ""

    night_hint = ""
    if ctx.is_night:
        night_hint = (
            "\n  Det er NAT her. Personer, køretøjer eller aktivitet er som "
            "udgangspunkt usædvanligt og bør markeres som en hændelse."
        )

    return (
        "## KONTEKST (baggrundsviden — beskriv stadig kun hvad du faktisk ser)\n"
        + "\n".join(lines)
        + night_hint
    )
