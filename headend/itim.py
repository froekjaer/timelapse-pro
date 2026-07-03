# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — itim.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Observability / IT Infrastructure Monitoring (ITIM) — letvægt, Postgres-baseret.
#
# Selvstændigt driftslag ved siden af SIEM (sikkerhedshændelser) og CMDB (assets).
# Spørgsmålet ITIM svarer på: "Hvordan har systemet det NU og over tid?" —
# service oppe/nede, ressourcer (CPU/RAM/disk/temp/batteri), volumen-helbred,
# billedfejl (fokus/snavs/sne/dug), komponentfejl og AI-pipeline — med alarmer.
#
# Designprincipper (SABSA/ISO27001 A.12.1+A.12.4 / IEC 62443 SR6.x / CRA):
#   • Availability/kapacitet er en selvstændig disciplin → eget datalag + retention.
#   • GDPR-invariant: metrics er rene drifts-tal. INGEN personoplysninger,
#     INGEN billeder, INGEN brugerindhold, INGEN IP-adresser i metric_samples.
#   • Mindste rettighed: probes er lokale og ikke-muterende (SELECT 1, HTTP GET).
#   • Genbrug eksisterende data (diagnostics, captures.ai_tags, ai_batch_jobs)
#     frem for at duplikere — samme DB, additive itim_-tabeller, designet til
#     senere udtræk (MetricSink-seam → Elastic/OpenSearch uden at røre indsamling).
#
# Montér i main.py:
#   from itim import router as itim_router, start_itim_collector
#   app.include_router(itim_router, prefix="/api/itim")
#   start_itim_collector()
# ═══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Session

from database import Base, get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["ITIM"])

_COLLECTOR_STARTED = False
_notify_cooldown: dict[tuple, float] = {}
_notify_cooldown_lock = threading.Lock()
NOTIFY_COOLDOWN_SECONDS = int(os.getenv("TIMELAPSE_ITIM_NOTIFY_COOLDOWN_S", "300"))

# Retention (rå holdes kort, rulles op til 5m/1h og slettes derefter)
RETAIN_RAW_HOURS = int(os.getenv("TIMELAPSE_ITIM_RETAIN_RAW_HOURS", "48"))
RETAIN_5M_DAYS   = int(os.getenv("TIMELAPSE_ITIM_RETAIN_5M_DAYS", "30"))
RETAIN_1H_DAYS   = int(os.getenv("TIMELAPSE_ITIM_RETAIN_1H_DAYS", "395"))  # ~13 mdr


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Datamodel ──────────────────────────────────────────────────────────────

class ItimTarget(Base):
    __tablename__ = "itim_targets"
    id           = Column(Integer, primary_key=True)
    target_key   = Column(String(120), unique=True, nullable=False, index=True)
    kind         = Column(String(40), nullable=False)   # host|service|volume|edge|pipeline|image_qa
    device_id    = Column(String(50))                    # FK-løs kobling til CMDB/Device
    display_name = Column(String(160))
    scope        = Column(String(40), default="core")    # core|host|edge|ai
    enabled      = Column(Boolean, default=True)
    meta         = Column(Text, default="{}")
    created_at   = Column(DateTime(timezone=True), default=_now)


class ItimMetricSample(Base):
    __tablename__ = "itim_metric_samples"
    # Unik pr. (target, metric, rollup, ts) → ON CONFLICT DO NOTHING virker, så
    # rollup-kørsler ikke dublerer 5m/1h-buckets. Rå-samples kolliderer ikke (unik ts/runde).
    __table_args__ = (UniqueConstraint("target_id", "metric", "rollup", "ts", name="uq_itim_sample"),)
    id         = Column(Integer, primary_key=True)
    target_id  = Column(Integer, nullable=False, index=True)
    metric     = Column(String(60), nullable=False)
    ts         = Column(DateTime(timezone=True), nullable=False, index=True)
    value      = Column(Float)
    rollup     = Column(String(8), default="raw")        # raw|5m|1h


class ItimHealthStatus(Base):
    __tablename__ = "itim_health_status"
    target_id  = Column(Integer, primary_key=True)
    state      = Column(String(16), nullable=False, default="unknown")  # ok|warning|critical|unknown
    summary    = Column(Text)
    metrics    = Column(Text, default="{}")              # JSON snapshot af seneste nøgletal
    changed_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class ItimAlertRule(Base):
    __tablename__ = "itim_alert_rules"
    id          = Column(Integer, primary_key=True)
    name        = Column(String(160), nullable=False)
    target_kind = Column(String(40))     # matcher kind, eller NULL = alle
    target_key  = Column(String(120))    # eksakt target, eller NULL
    metric      = Column(String(60), nullable=False)
    op          = Column(String(4), default=">")
    threshold   = Column(Float, nullable=False)
    for_seconds = Column(Integer, default=60)
    severity    = Column(String(16), default="warning")
    enabled     = Column(Boolean, default=True)
    notify      = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), default=_now)


class ItimAlertEvent(Base):
    __tablename__ = "itim_alert_events"
    id          = Column(Integer, primary_key=True)
    rule_id     = Column(Integer, index=True)
    target_id   = Column(Integer, index=True)
    severity    = Column(String(16))
    state       = Column(String(16), default="firing")   # firing|resolved
    value       = Column(Float)
    message     = Column(Text)
    started_at  = Column(DateTime(timezone=True), default=_now)
    resolved_at = Column(DateTime(timezone=True))
    notified_at = Column(DateTime(timezone=True))


# ── Settings-helper (robust på tværs af settings/system_settings) ────────────

def _setting(db: Session, key: str, default: str = "") -> str:
    for tbl in ("settings", "system_settings"):
        try:
            row = db.execute(text(f"SELECT value FROM {tbl} WHERE key=:k"), {"k": key}).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
    return default


# ── MetricSink-seam (fremtidssikring: Elastic kan tilføjes uden at røre resten) ─

class MetricSink:
    """Default: ingen ekstra eksport. record_metrics skriver altid til Postgres;
    en sink kan SPEJLE samples til et eksternt system (Elastic/OpenSearch/Prometheus)."""
    def write(self, rows: list[dict]) -> None:
        return None


_SINK: MetricSink = MetricSink()


def configure_sink(db: Session) -> None:
    """Aktivér Elastic-eksport hvis itim_export_elastic_url er sat. Lazy import,
    så afhængigheden kun kræves når den faktisk bruges."""
    global _SINK
    url = _setting(db, "itim_export_elastic_url", "").strip()
    if not url:
        _SINK = MetricSink()
        return
    try:
        _SINK = _ElasticSink(url)  # noqa: F821 (defineres når/ hvis behovet opstår)
        log.info("ITIM: Elastic-eksport aktiveret → %s", url)
    except Exception as exc:
        log.warning("ITIM: kunne ikke aktivere Elastic-sink (%s) — falder tilbage til Postgres-only", exc)
        _SINK = MetricSink()


# ── Kerne: registrér targets, metrics og health ─────────────────────────────

def _get_or_create_target(db: Session, target_key: str, kind: str,
                          device_id: str | None = None, display_name: str | None = None,
                          scope: str = "core") -> ItimTarget:
    t = db.query(ItimTarget).filter_by(target_key=target_key).first()
    if t is None:
        t = ItimTarget(target_key=target_key, kind=kind, device_id=device_id,
                       display_name=display_name or target_key, scope=scope)
        db.add(t)
        db.flush()
    return t


def record_metrics(db: Session, target_key: str, kind: str, metrics: dict[str, float],
                   ts: datetime | None = None, device_id: str | None = None,
                   display_name: str | None = None, scope: str = "core") -> None:
    """Skriv et sæt metrics for ét target (rå sample). Opdaterer også health-snapshot."""
    ts = ts or _now()
    t = _get_or_create_target(db, target_key, kind, device_id, display_name, scope)
    sink_rows = []
    for metric, value in metrics.items():
        if value is None:
            continue
        try:
            fval = float(value)
        except (TypeError, ValueError):
            continue
        db.add(ItimMetricSample(target_id=t.id, metric=metric, ts=ts, value=fval, rollup="raw"))
        sink_rows.append({"target": target_key, "kind": kind, "metric": metric,
                          "ts": ts.isoformat(), "value": fval})
    try:
        _SINK.write(sink_rows)
    except Exception as exc:
        log.debug("ITIM sink write fejl (ikke kritisk): %s", exc)


def set_health(db: Session, target_key: str, kind: str, state: str, summary: str,
               metrics: dict | None = None, scope: str = "core",
               device_id: str | None = None, display_name: str | None = None) -> None:
    import json
    t = _get_or_create_target(db, target_key, kind, device_id, display_name, scope)
    hs = db.query(ItimHealthStatus).filter_by(target_id=t.id).first()
    now = _now()
    if hs is None:
        hs = ItimHealthStatus(target_id=t.id, state=state, summary=summary,
                              metrics=json.dumps(metrics or {}), changed_at=now, updated_at=now)
        db.add(hs)
    else:
        if hs.state != state:
            hs.changed_at = now
        hs.state = state
        hs.summary = summary
        hs.metrics = json.dumps(metrics or {})
        hs.updated_at = now


# ── Probes / collectors ──────────────────────────────────────────────────────

def _probe_host_metrics(db: Session) -> None:
    """Vært-metrics for Mac-headenden via psutil. Degraderer pænt hvis psutil mangler."""
    try:
        import psutil
    except Exception:
        log.debug("ITIM: psutil ikke tilgængelig — host-metrics springes over (pip install psutil)")
        return
    m: dict[str, float] = {}
    try:
        m["cpu_pct"] = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        m["mem_pct"] = vm.percent
        sm = psutil.swap_memory()
        m["swap_pct"] = sm.percent
        du = psutil.disk_usage("/")
        m["disk_used_pct"] = du.percent
        try:
            m["load1"] = os.getloadavg()[0]
        except (OSError, AttributeError):
            pass
        try:
            m["uptime_s"] = max(0.0, time.time() - psutil.boot_time())
        except Exception:
            pass
        # Temperatur hvis læsbar (typisk ikke på macOS uden sudo — derfor best-effort)
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            for _name, entries in (temps or {}).items():
                for e in entries:
                    if e.current:
                        m["temp_c"] = float(e.current)
                        break
                if "temp_c" in m:
                    break
        except Exception:
            pass
    except Exception as exc:
        log.debug("ITIM host-probe fejl: %s", exc)
        return

    record_metrics(db, "host:headend", "host", m, scope="host", display_name="Headend (Mac)")
    state, summary = "ok", "Normal"
    if m.get("disk_used_pct", 0) >= 97 or m.get("mem_pct", 0) >= 96:
        state, summary = "critical", "Disk/RAM kritisk høj"
    elif m.get("disk_used_pct", 0) >= 90 or m.get("mem_pct", 0) >= 92:
        state, summary = "warning", "Disk/RAM høj"
    set_health(db, "host:headend", "host", state, summary, m, scope="host",
               display_name="Headend (Mac)")


def _tcp_up(host: str, port: int, timeout: float = 2.0) -> tuple[bool, float]:
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, (time.monotonic() - t0) * 1000.0
    except Exception:
        return False, 0.0


def _http_up(url: str, timeout: float = 3.0) -> tuple[bool, float]:
    import urllib.request
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (lokal URL)
            ok = 200 <= resp.status < 500
            return ok, (time.monotonic() - t0) * 1000.0
    except Exception:
        return False, 0.0


def _probe_services(db: Session) -> None:
    """Oppe/nede + latens for kerneservices. Kun lokale, ikke-muterende kald."""
    # headend (self-probe)
    hport = int(os.getenv("TIMELAPSE_HEADEND_PORT", "8000"))
    up, ms = _http_up(f"http://127.0.0.1:{hport}/api/health")
    record_metrics(db, "svc:headend", "service", {"up": 1.0 if up else 0.0, "latency_ms": ms},
                   display_name="Headend API")
    set_health(db, "svc:headend", "service", "ok" if up else "critical",
               "Oppe" if up else "Svarer ikke", {"up": up, "latency_ms": round(ms, 1)},
               display_name="Headend API")

    # postgres (SELECT 1)
    t0 = time.monotonic()
    pg_up = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        pg_up = False
    pg_ms = (time.monotonic() - t0) * 1000.0
    record_metrics(db, "svc:postgres", "service", {"up": 1.0 if pg_up else 0.0, "latency_ms": pg_ms},
                   display_name="PostgreSQL")
    set_health(db, "svc:postgres", "service", "ok" if pg_up else "critical",
               "Oppe" if pg_up else "Fejler", {"up": pg_up, "latency_ms": round(pg_ms, 1)},
               display_name="PostgreSQL")

    # nginx (TCP 443 → fallback 80)
    n_up, n_ms = _tcp_up("127.0.0.1", int(os.getenv("TIMELAPSE_NGINX_PORT", "443")))
    if not n_up:
        n_up, n_ms = _tcp_up("127.0.0.1", 80)
    record_metrics(db, "svc:nginx", "service", {"up": 1.0 if n_up else 0.0, "latency_ms": n_ms},
                   display_name="nginx")
    set_health(db, "svc:nginx", "service", "ok" if n_up else "warning",
               "Oppe" if n_up else "Lytter ikke", {"up": n_up}, display_name="nginx")

    # ollama (kun hvis lokal strategi/aktiveret)
    strat = _setting(db, "ai_strategy", "cloud_only")
    if strat and strat != "cloud_only":
        o_up, o_ms = _http_up(f"http://127.0.0.1:{os.getenv('TIMELAPSE_OLLAMA_PORT','11434')}/api/tags")
        record_metrics(db, "svc:ollama", "service", {"up": 1.0 if o_up else 0.0, "latency_ms": o_ms},
                       display_name="Ollama")
        set_health(db, "svc:ollama", "service", "ok" if o_up else "warning",
                   "Oppe" if o_up else "Svarer ikke", {"up": o_up}, display_name="Ollama")


def _probe_data_fast(db: Session) -> None:
    """Volumen-helbred for data-fast — den tilbagevendende smerte.
    Måler mounted/writable/io_latens SEPARAT, så vi kan skelne 'nede' fra 'langsom'.

    HÆRDET (efter Codex' live-fund): (1) probe-stien defaulter til en SKRIVBAR
    undermappe (afledt af sftp_base), ikke volumen-roden der er root-ejet → ingen
    falsk critical out-of-the-box. (2) En RETTIGHEDSFEJL (EACCES) er en konfig-/
    sti-fejl, IKKE et volumen-svigt: den giver `warning` og rører ikke `writable`
    (så `writable==0`-alarmen ikke fyrer falsk). Kun ægte I/O-fejl/umonteret →
    `critical`. Probe-stien kan stadig sættes eksplicit via `itim_data_fast_path`."""
    import shutil
    # Smartere default: eksplicit setting → env → sftp_base (kendt skrivbar) → fallback.
    vol = (_setting(db, "itim_data_fast_path")
           or os.getenv("TIMELAPSE_DATA_FAST_PATH")
           or _setting(db, "sftp_base")
           or "/Volumes/data-fast/timelapse-incoming")
    m: dict[str, float] = {}
    mounted = os.path.ismount(vol) or os.path.isdir(vol)
    m["mounted"] = 1.0 if mounted else 0.0

    writable: float | None = None   # None = ikke målt (fx rettighedsfejl)
    io_ms: float | None = None
    perm_issue = False
    if mounted:
        probe_dir = os.path.join(vol, ".itim-probe")
        try:
            os.makedirs(probe_dir, exist_ok=True)
            p = os.path.join(probe_dir, "probe.tmp")
            payload = b"itim" * 256  # ~1KB
            t0 = time.monotonic()
            with open(p, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            io_ms = (time.monotonic() - t0) * 1000.0
            try:
                os.unlink(p)
            except OSError:
                pass
            writable = 1.0
        except PermissionError as exc:
            # Rettigheds-/konfigproblem på probe-stien — IKKE et volumen-svigt.
            log.debug("ITIM data-fast probe-sti ikke skrivbar (rettigheder): %s", exc)
            perm_issue = True
        except OSError as exc:
            # Ægte I/O-fejl / volumen forsvundet under skrivning.
            log.debug("ITIM data-fast skrivetest fejlede (I/O): %s", exc)
            writable = 0.0

    if writable is not None:
        m["writable"] = writable
    if io_ms is not None:
        m["io_latency_ms"] = io_ms
    m["probe_config_ok"] = 0.0 if perm_issue else 1.0
    try:
        if mounted:
            du = shutil.disk_usage(vol)
            m["disk_used_pct"] = (du.used / du.total) * 100.0 if du.total else 0.0
    except Exception:
        pass

    record_metrics(db, "vol:data-fast", "volume", m, display_name="data-fast volumen")
    if not mounted:
        state, summary = "critical", "Ikke monteret — vælter login/batch"
    elif writable == 0.0:
        state, summary = "critical", "Ikke skrivbar (I/O-fejl) — vælter login/batch"
    elif perm_issue:
        state, summary = "warning", ("Probe-sti ikke skrivbar (rettigheder) — sæt "
                                     "itim_data_fast_path til en skrivbar undermappe")
    elif io_ms is not None and io_ms > 250:
        state, summary = "critical", f"Høj I/O-latens ({io_ms:.0f} ms)"
    elif io_ms is not None and io_ms > 100:
        state, summary = "warning", f"Forhøjet I/O-latens ({io_ms:.0f} ms)"
    elif m.get("disk_used_pct", 0) >= 95:
        state, summary = "warning", "Næsten fuld"
    else:
        state, summary = "ok", "Sund"
    set_health(db, "vol:data-fast", "volume", state, summary,
               {k: (round(v, 1) if isinstance(v, float) else v) for k, v in m.items()},
               display_name="data-fast volumen")


def _probe_edge_from_diagnostics(db: Session) -> None:
    """Edge-helbred udledt af EKSISTERENDE diagnostics-telemetri (ingen ny edge-kode).
    Dækker batteri-/solspænding, CPU-temp, disk, kamera-batteri, upload-kø, oppetid."""
    import json
    # Seneste diagnostik pr. enhed (sidste 24t)
    rows = db.execute(text("""
        SELECT DISTINCT ON (device_id)
            device_id, recorded_at, cpu_temp_c, cpu_load_pct, ram_used_mb, disk_used_gb,
            battery_v, solar_v, connectivity, uptime_s, ssd_used_pct, upload_queue,
            cam_battery_pct, cam_shutter_pct, cam_shutter_alarm, cam_available_shots
        FROM diagnostics
        WHERE recorded_at >= :since
        ORDER BY device_id, recorded_at DESC
    """), {"since": _now() - timedelta(hours=24)}).mappings().all()

    low_batt = float(_setting(db, "itim_edge_battery_low_v", "11.8") or 11.8)
    for r in rows:
        did = r["device_id"]
        m: dict[str, float] = {}
        for col in ("cpu_temp_c", "cpu_load_pct", "ram_used_mb", "disk_used_gb",
                    "battery_v", "solar_v", "uptime_s", "ssd_used_pct", "upload_queue",
                    "cam_battery_pct", "cam_shutter_pct", "cam_available_shots"):
            if r[col] is not None:
                m[col] = float(r[col])
        rec = r["recorded_at"]
        if rec is not None:
            if rec.tzinfo is None:
                rec = rec.replace(tzinfo=timezone.utc)
            age = (_now() - rec).total_seconds()
            m["last_seen_age_s"] = age
            m["up"] = 1.0 if age < 1800 else 0.0
        record_metrics(db, f"edge:{did}", "edge", m, device_id=did, scope="edge",
                       display_name=did)

        # Health-vurdering
        state, reasons = "ok", []
        if m.get("up", 1.0) == 0.0:
            state, reasons = "critical", ["ingen heartbeat >30 min"]
        if m.get("battery_v") is not None and m["battery_v"] < low_batt:
            state = "critical"; reasons.append(f"lav batterispænding {m['battery_v']:.1f} V")
        if m.get("cpu_temp_c") is not None and m["cpu_temp_c"] >= 80:
            state = "warning" if state == "ok" else state; reasons.append(f"høj CPU-temp {m['cpu_temp_c']:.0f}°C")
        if r["cam_shutter_alarm"]:
            state = "warning" if state == "ok" else state; reasons.append("shutter-alarm")
        if m.get("ssd_used_pct", 0) >= 92:
            state = "warning" if state == "ok" else state; reasons.append("disk næsten fuld")
        set_health(db, f"edge:{did}", "edge", state, ", ".join(reasons) or "Normal",
                   {k: round(v, 1) for k, v in m.items()}, scope="edge",
                   device_id=did, display_name=did)


# Billedfejl-metrics. Metric-navnene følger Codex' edge_qa-kontrakt
# (probable_cause/quality_dimension), så det INTERIM cloud-ai_tags-feed og det
# senere PRIMÆRE edge_qa_signal deler samme namespace (ingen rework).
# AFTALE (HANDOVER_Claude_Codex_arbejdsdeling §8): headend AGGREGERER Edge QA —
# genklassificerer ikke fra pixels. Indtil Codex lander edge_qa_signal-feltet
# bruges cloud-ai_tags som fallback (engine=cloud_tags), manglende → unknown.
_IMAGE_DEFECTS = {
    "unusable_rate":         ["unusable_image"],                       # quality_flag=error
    "blurry_rate":           ["blurry", "blur", "out_of_focus", "unsharp"],  # focus_or_lens_issue
    "overexposed_rate":      ["overexposed", "overexposure", "glare", "lens_flare"],
    "underexposed_rate":     ["underexposed", "underexposure", "too_dark"],
    "lens_obstruction_rate": ["dirty_lens", "dirt_on_lens", "snow_on_lens", "raindrop",
                              "water_droplet", "rain_on_lens", "condensation", "dew", "fog_on_lens"],
}


def _probe_image_qa(db: Session) -> None:
    """Billedfejl-rater. INTERIM-kilde: cloud captures.ai_tags (engine=cloud_tags).
    Skifter til Codex' edge_qa_signal som primær kilde når feltet lander (samme
    metric-namespace). Pr. analyseret billede i vinduet: andel med hvert defekt-mønster."""
    window_h = int(os.getenv("TIMELAPSE_ITIM_IMAGE_WINDOW_HOURS", "24"))
    since = _now() - timedelta(hours=window_h)
    total = db.execute(text("""
        SELECT COUNT(*) FROM captures
        WHERE ai_analyzed_at >= :since AND ai_tags IS NOT NULL
    """), {"since": since}).scalar() or 0
    if not total:
        set_health(db, "image_qa:all", "image_qa", "unknown", "Ingen analyserede billeder i vinduet",
                   {"analyzed": 0}, scope="ai", display_name="Billedkvalitet")
        return
    m: dict[str, float] = {"analyzed": float(total)}
    for metric, needles in _IMAGE_DEFECTS.items():
        like = " OR ".join(["ai_tags ILIKE :n%d" % i for i in range(len(needles))])
        params = {"since": since}
        for i, n in enumerate(needles):
            params["n%d" % i] = f"%{n}%"
        cnt = db.execute(text(f"""
            SELECT COUNT(*) FROM captures
            WHERE ai_analyzed_at >= :since AND ai_tags IS NOT NULL AND ({like})
        """), params).scalar() or 0
        m[metric] = (cnt / total) * 100.0
    record_metrics(db, "image_qa:all", "image_qa", m, scope="ai", display_name="Billedkvalitet")
    worst = max((m.get(k, 0) for k in _IMAGE_DEFECTS), default=0)
    state = "critical" if worst >= 25 else "warning" if worst >= 10 else "ok"
    snap = {k: round(v, 1) for k, v in m.items()}
    snap["engine"] = "cloud_tags"   # interim; skifter til edge_qa_signal når Codex lander det
    set_health(db, "image_qa:all", "image_qa", state,
               f"{int(total)} analyseret, værste defekt-rate {worst:.0f}% (kilde: cloud-tags, interim)",
               snap, scope="ai", display_name="Billedkvalitet")


def _probe_ai_pipeline(db: Session) -> None:
    """AI-pipeline-helbred: batch-jobs + fejl. Knytter sig til det vi lige byggede."""
    try:
        running = db.execute(text("""
            SELECT COUNT(*) FROM ai_batch_jobs WHERE status IN ('submitting','submitted','running')
        """)).scalar() or 0
        failed_24h = db.execute(text("""
            SELECT COUNT(*) FROM ai_batch_jobs
            WHERE status IN ('failed','expired','cancelled')
              AND COALESCE(completed_at, submitted_at) >= :since
        """), {"since": _now() - timedelta(hours=24)}).scalar() or 0
    except Exception as exc:
        log.debug("ITIM ai-pipeline probe fejl: %s", exc)
        return
    m = {"batch_jobs_running": float(running), "batch_jobs_failed_24h": float(failed_24h)}
    record_metrics(db, "pipeline:ai", "pipeline", m, scope="ai", display_name="AI batch-pipeline")
    state = "warning" if failed_24h > 0 else "ok"
    set_health(db, "pipeline:ai", "pipeline", state,
               f"{int(running)} kører, {int(failed_24h)} fejlet (24t)", m, scope="ai",
               display_name="AI batch-pipeline")


# ── Alarm-evaluering ─────────────────────────────────────────────────────────

_OPS = {
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
}


def _latest_value(db: Session, target_id: int, metric: str) -> Optional[float]:
    row = db.execute(text("""
        SELECT value FROM itim_metric_samples
        WHERE target_id=:t AND metric=:m AND rollup='raw'
        ORDER BY ts DESC LIMIT 1
    """), {"t": target_id, "m": metric}).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _breach_sustained(db: Session, target_id: int, metric: str, op, threshold: float,
                      for_seconds: int) -> bool:
    """True hvis ALLE rå-samples i de seneste for_seconds bryder tærsklen (anti-flap)."""
    since = _now() - timedelta(seconds=max(for_seconds, 1))
    rows = db.execute(text("""
        SELECT value FROM itim_metric_samples
        WHERE target_id=:t AND metric=:m AND rollup='raw' AND ts >= :since
        ORDER BY ts DESC
    """), {"t": target_id, "m": metric, "since": since}).fetchall()
    vals = [float(r[0]) for r in rows if r[0] is not None]
    if not vals:
        return False
    return all(op(v, threshold) for v in vals)


def evaluate_alerts(db: Session) -> None:
    rules = db.query(ItimAlertRule).filter_by(enabled=True).all()
    for rule in rules:
        op = _OPS.get(rule.op or ">")
        if op is None:
            continue
        q = db.query(ItimTarget).filter_by(enabled=True)
        if rule.target_key:
            q = q.filter(ItimTarget.target_key == rule.target_key)
        elif rule.target_kind:
            q = q.filter(ItimTarget.kind == rule.target_kind)
        for t in q.all():
            latest = _latest_value(db, t.id, rule.metric)
            if latest is None:
                continue
            firing = op(latest, rule.threshold) and _breach_sustained(
                db, t.id, rule.metric, op, rule.threshold, rule.for_seconds or 60)
            open_ev = db.query(ItimAlertEvent).filter_by(
                rule_id=rule.id, target_id=t.id, state="firing").first()
            if firing and not open_ev:
                ev = ItimAlertEvent(
                    rule_id=rule.id, target_id=t.id, severity=rule.severity,
                    state="firing", value=latest,
                    message=f"{t.display_name or t.target_key}: {rule.metric}={latest:.2f} {rule.op} {rule.threshold:g} ({rule.name})",
                )
                db.add(ev)
                db.flush()
                if rule.notify:
                    _notify_alert(db, rule, t, ev)
            elif not firing and open_ev:
                open_ev.state = "resolved"
                open_ev.resolved_at = _now()
    db.commit()


def _notify_alert(db: Session, rule: ItimAlertRule, target: ItimTarget, ev: ItimAlertEvent) -> None:
    key = (target.target_key, rule.metric)
    now_ts = time.time()
    with _notify_cooldown_lock:
        if now_ts - _notify_cooldown.get(key, 0) < NOTIFY_COOLDOWN_SECONDS:
            return
        _notify_cooldown[key] = now_ts
    try:
        from ai.notify import notify, get_notification_config
        if not get_notification_config(db):
            return
        notify({
            "rule_name":    f"ITIM: {rule.name}",
            "rule_id":      "itim",
            "severity":     "critical" if rule.severity == "critical" else "warning",
            "device_id":    target.device_id or target.target_key,
            "description":  ev.message,
            "matched_on":   [f"{rule.metric}{rule.op}{rule.threshold:g}"],
            "confidence":   1.0,
            "triggered_at": _now().isoformat(),
            "capture_id":   None,
        }, db)
        ev.notified_at = _now()
    except Exception as exc:
        log.debug("ITIM notify fejl (ikke kritisk): %s", exc)


# ── Rollup + retention (holder Postgres slank) ───────────────────────────────

def rollup_and_retain(db: Session) -> None:
    try:
        # 5-min rollup fra rå (gns) for buckets der ikke allerede findes
        db.execute(text("""
            INSERT INTO itim_metric_samples (target_id, metric, ts, value, rollup)
            SELECT target_id, metric, date_trunc('hour', ts)
                   + floor(extract(minute FROM ts)::int/5)*interval '5 min' AS bucket,
                   AVG(value), '5m'
            FROM itim_metric_samples
            WHERE rollup='raw' AND ts >= :since
            GROUP BY target_id, metric, bucket
            ON CONFLICT DO NOTHING
        """), {"since": _now() - timedelta(hours=RETAIN_RAW_HOURS)})
        # 1-time rollup fra 5m
        db.execute(text("""
            INSERT INTO itim_metric_samples (target_id, metric, ts, value, rollup)
            SELECT target_id, metric, date_trunc('hour', ts), AVG(value), '1h'
            FROM itim_metric_samples
            WHERE rollup='5m' AND ts >= :since
            GROUP BY target_id, metric, date_trunc('hour', ts)
            ON CONFLICT DO NOTHING
        """), {"since": _now() - timedelta(days=2)})
        # Retention
        db.execute(text("DELETE FROM itim_metric_samples WHERE rollup='raw' AND ts < :c"),
                   {"c": _now() - timedelta(hours=RETAIN_RAW_HOURS)})
        db.execute(text("DELETE FROM itim_metric_samples WHERE rollup='5m' AND ts < :c"),
                   {"c": _now() - timedelta(days=RETAIN_5M_DAYS)})
        db.execute(text("DELETE FROM itim_metric_samples WHERE rollup='1h' AND ts < :c"),
                   {"c": _now() - timedelta(days=RETAIN_1H_DAYS)})
        # Luk gamle resolved alarmer (>90 dage)
        db.execute(text("DELETE FROM itim_alert_events WHERE state='resolved' AND resolved_at < :c"),
                   {"c": _now() - timedelta(days=90)})
        db.commit()
    except Exception as exc:
        db.rollback()
        log.warning("ITIM rollup/retention fejl: %s", exc)


# ── Seed: default targets og alarm-regler (idempotent) ───────────────────────

_DEFAULT_RULES = [
    # name, kind, key, metric, op, threshold, for_s, severity
    ("data-fast ikke skrivbar",       "volume", "vol:data-fast", "writable",       "==", 0, 60,  "critical"),
    ("data-fast ikke monteret",       "volume", "vol:data-fast", "mounted",        "==", 0, 0,   "critical"),
    ("data-fast høj I/O-latens",      "volume", "vol:data-fast", "io_latency_ms",  ">",  250, 60, "critical"),
    ("Service nede",                  "service", None,           "up",             "==", 0, 60,  "critical"),
    ("Host disk næsten fuld",         "host",   "host:headend",  "disk_used_pct",  ">",  90, 0,   "warning"),
    ("Host disk fuld",                "host",   "host:headend",  "disk_used_pct",  ">",  97, 0,   "critical"),
    ("Host RAM høj",                  "host",   "host:headend",  "mem_pct",        ">",  92, 60,  "warning"),
    ("Edge offline",                  "edge",   None,            "up",             "==", 0, 0,   "warning"),
    ("Edge lav batterispænding",      "edge",   None,            "battery_v",      "<",  11.8, 0, "critical"),
    ("Edge høj CPU-temp",             "edge",   None,            "cpu_temp_c",     ">",  80, 0,   "warning"),
    ("Billedfejl-rate høj",           "image_qa", "image_qa:all","unusable_rate",  ">",  20, 0,   "warning"),
    ("AI batch-jobs fejlet",          "pipeline","pipeline:ai",  "batch_jobs_failed_24h", ">", 0, 0, "warning"),
]


def seed_defaults(db: Session) -> None:
    if db.query(ItimAlertRule).count() == 0:
        for name, kind, key, metric, op, thr, fs, sev in _DEFAULT_RULES:
            db.add(ItimAlertRule(name=name, target_kind=kind, target_key=key, metric=metric,
                                 op=op, threshold=thr, for_seconds=fs, severity=sev))
        db.commit()
        log.info("ITIM: %d default alarm-regler seedet", len(_DEFAULT_RULES))


def run_collection_cycle(db: Session) -> None:
    """Én indsamlingsrunde — hvert probe er isoleret så én fejl ikke vælter resten."""
    for probe in (_probe_host_metrics, _probe_services, _probe_data_fast,
                  _probe_edge_from_diagnostics, _probe_image_qa, _probe_ai_pipeline):
        try:
            probe(db)
        except Exception as exc:
            log.debug("ITIM probe %s fejl: %s", getattr(probe, "__name__", "?"), exc)
    db.commit()
    try:
        evaluate_alerts(db)
    except Exception as exc:
        log.warning("ITIM alarm-evaluering fejl: %s", exc)


# ── Collector-tråd ───────────────────────────────────────────────────────────

def start_itim_collector() -> None:
    global _COLLECTOR_STARTED
    if _COLLECTOR_STARTED:
        return
    if os.getenv("TIMELAPSE_ITIM_ENABLED", "true").lower() not in ("1", "true", "yes", "on"):
        log.info("ITIM collector deaktiveret via TIMELAPSE_ITIM_ENABLED")
        return
    _COLLECTOR_STARTED = True
    interval_s = int(os.getenv("TIMELAPSE_ITIM_INTERVAL_S", "60"))
    rollup_every = max(1, int(os.getenv("TIMELAPSE_ITIM_ROLLUP_EVERY_CYCLES", "5")))

    def loop() -> None:
        from database import SessionLocal
        # Seed + sink-konfig én gang
        try:
            db = SessionLocal()
            try:
                seed_defaults(db)
                configure_sink(db)
            finally:
                db.close()
        except Exception as exc:
            log.warning("ITIM seed/sink-init fejl: %s", exc)
        log.info("ITIM collector startet (interval=%ds)", interval_s)
        cycle = 0
        while True:
            try:
                db = SessionLocal()
                try:
                    run_collection_cycle(db)
                    cycle += 1
                    if cycle % rollup_every == 0:
                        rollup_and_retain(db)
                finally:
                    db.close()
            except Exception as exc:
                log.debug("ITIM collector-runde fejl: %s", exc)
            time.sleep(interval_s)

    threading.Thread(target=loop, name="itim-collector", daemon=True).start()


# ── RBAC-bro (uden at importere main ved modulindlæsning) ────────────────────

def _require_role(*roles: str):
    def _check(request: Request, db: Session = Depends(get_db)):
        from main import _ROLE_HIERARCHY, get_current_user
        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        return user
    return _check


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/health")
def get_health(_user=Depends(_require_role("viewer")), db: Session = Depends(get_db)):
    """Alle targets + aktuel state — til drifts-tiles."""
    import json
    rows = (db.query(ItimTarget, ItimHealthStatus)
            .outerjoin(ItimHealthStatus, ItimHealthStatus.target_id == ItimTarget.id)
            .filter(ItimTarget.enabled == True)  # noqa: E712
            .all())
    out = []
    for t, hs in rows:
        try:
            metrics = json.loads(hs.metrics) if hs and hs.metrics else {}
        except Exception:
            metrics = {}
        out.append({
            "target_key":   t.target_key,
            "kind":         t.kind,
            "scope":        t.scope,
            "device_id":    t.device_id,
            "display_name": t.display_name,
            "state":        hs.state if hs else "unknown",
            "summary":      hs.summary if hs else None,
            "metrics":      metrics,
            "updated_at":   hs.updated_at.isoformat() if hs and hs.updated_at else None,
        })
    order = {"critical": 0, "warning": 1, "unknown": 2, "ok": 3}
    out.sort(key=lambda r: (order.get(r["state"], 9), r["scope"], r["target_key"]))
    return out


@router.get("/metrics")
def get_metrics(
    target: str = Query(..., description="target_key"),
    metric: str = Query(...),
    hours:  int = Query(24, ge=1, le=8760),
    rollup: str = Query("raw", pattern="^(raw|5m|1h)$"),
    _user=Depends(_require_role("viewer")),
    db: Session = Depends(get_db),
):
    """Tidsserie til grafer."""
    t = db.query(ItimTarget).filter_by(target_key=target).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ukendt target")
    since = _now() - timedelta(hours=hours)
    rows = db.execute(text("""
        SELECT ts, value FROM itim_metric_samples
        WHERE target_id=:t AND metric=:m AND rollup=:r AND ts >= :since
        ORDER BY ts ASC
    """), {"t": t.id, "m": metric, "r": rollup, "since": since}).fetchall()
    return {"target": target, "metric": metric, "rollup": rollup,
            "points": [{"ts": r[0].isoformat(), "value": float(r[1]) if r[1] is not None else None} for r in rows]}


@router.get("/alerts")
def get_alerts(
    state: Optional[str] = Query(None, pattern="^(firing|resolved)$"),
    hours: int = Query(168, ge=1, le=8760),
    _user=Depends(_require_role("viewer")),
    db: Session = Depends(get_db),
):
    since = _now() - timedelta(hours=hours)
    q = db.query(ItimAlertEvent, ItimTarget).outerjoin(
        ItimTarget, ItimTarget.id == ItimAlertEvent.target_id).filter(
        ItimAlertEvent.started_at >= since)
    if state:
        q = q.filter(ItimAlertEvent.state == state)
    rows = q.order_by(ItimAlertEvent.started_at.desc()).limit(500).all()
    return [{
        "id":          ev.id,
        "severity":    ev.severity,
        "state":       ev.state,
        "value":       ev.value,
        "message":     ev.message,
        "target_key":  t.target_key if t else None,
        "started_at":  ev.started_at.isoformat() if ev.started_at else None,
        "resolved_at": ev.resolved_at.isoformat() if ev.resolved_at else None,
    } for ev, t in rows]


@router.get("/alert-rules")
def list_alert_rules(_user=Depends(_require_role("viewer")), db: Session = Depends(get_db)):
    rules = db.query(ItimAlertRule).order_by(ItimAlertRule.id).all()
    return [{
        "id": r.id, "name": r.name, "target_kind": r.target_kind, "target_key": r.target_key,
        "metric": r.metric, "op": r.op, "threshold": r.threshold, "for_seconds": r.for_seconds,
        "severity": r.severity, "enabled": r.enabled, "notify": r.notify,
    } for r in rules]


@router.post("/alert-rules")
def create_alert_rule(payload: dict, _user=Depends(_require_role("admin")), db: Session = Depends(get_db)):
    if not payload.get("name") or not payload.get("metric") or payload.get("threshold") is None:
        raise HTTPException(status_code=400, detail="name, metric og threshold er påkrævet")
    r = ItimAlertRule(
        name=payload["name"], target_kind=payload.get("target_kind"),
        target_key=payload.get("target_key"), metric=payload["metric"],
        op=payload.get("op", ">"), threshold=float(payload["threshold"]),
        for_seconds=int(payload.get("for_seconds", 60)), severity=payload.get("severity", "warning"),
        enabled=bool(payload.get("enabled", True)), notify=bool(payload.get("notify", True)),
    )
    db.add(r); db.commit(); db.refresh(r)
    return {"status": "ok", "id": r.id}


@router.put("/alert-rules/{rule_id}")
def update_alert_rule(rule_id: int, payload: dict, _user=Depends(_require_role("admin")), db: Session = Depends(get_db)):
    r = db.query(ItimAlertRule).filter_by(id=rule_id).first()
    if not r:
        raise HTTPException(status_code=404)
    for f in ("name", "target_kind", "target_key", "metric", "op", "severity"):
        if f in payload:
            setattr(r, f, payload[f])
    for f in ("threshold", "for_seconds"):
        if f in payload and payload[f] is not None:
            setattr(r, f, float(payload[f]) if f == "threshold" else int(payload[f]))
    for f in ("enabled", "notify"):
        if f in payload:
            setattr(r, f, bool(payload[f]))
    db.commit()
    return {"status": "ok"}


@router.delete("/alert-rules/{rule_id}")
def delete_alert_rule(rule_id: int, _user=Depends(_require_role("admin")), db: Session = Depends(get_db)):
    r = db.query(ItimAlertRule).filter_by(id=rule_id).first()
    if not r:
        raise HTTPException(status_code=404)
    db.delete(r); db.commit()
    return {"status": "ok"}
