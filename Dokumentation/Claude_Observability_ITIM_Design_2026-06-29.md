# TimeLapse Pro — Observability / ITIM — Design-notat

**Forfatter:** Claude · **Dato:** 2026-06-29 · **Status:** Implementeret og live-verificeret (v1.0 bygget 2026-06-29, live-verificeret af Codex 2026-06-30 — se HANDOVER_LOG.md)
**Beslægtet:** `SERVICES_OG_DRIFT_kilde_til_sandhed.md`, `README_CMDB.md`, `siem.py`, `cmdb.py`

> **Beslutning truffet med Peter (2026-06-29):** Underliggende lag = **letvægt i Postgres**
> (ikke fuld Elastic Stack nu) med en plugin-seam så Elastic/OpenSearch kan kobles på senere.
> Overvåg fra start: **data-fast + kerneservices, vært-metrics (Mac), edge-enheder, AI-pipeline**.
> Leverance: **design-notat → derefter kode**.

---

## 1. Hvorfor (problem og formål)

I dag har TimeLapse Pro to driftsnære systemer:

- **SIEM** — *hvad skete der* (sikkerheds-/loghændelser, event-centreret).
- **CMDB** — *hvad findes der* (assets, software, SBOM, patch-status, point-in-time).

Det der mangler er **ITIM / observability** — *hvordan har det det lige nu og over tid*:
service oppe/nede, ressource-forbrug, latens, kapacitet og **trends**, med **alarmer på
drifts­helbred**. Den konkrete, gentagne smerte er `data-fast`-volumenet: når det får I/O-fejl,
vælter det login, genstart og batch — **uden forvarsel**. Et observability-lag, der prober
volumenets helbred hvert minut og alarmerer på stigende I/O-latens *før* det fejler, er den
direkte gevinst. Det er en *availability*- og *capacity*-disciplin, ikke en sikkerheds-disciplin —
derfor et selvstændigt lag ved siden af SIEM/CMDB, ikke ovenpå dem.

### Afgrænsning mod de eksisterende lag

| | SIEM | CMDB | **ITIM (nyt)** |
|---|---|---|---|
| Spørgsmål | Hvad skete der (sikkerhed)? | Hvad findes/skal patches? | Hvordan har det det nu + over tid? |
| Datatype | Diskrete events | Tilstand (snapshot) | **Tidsserie-metrics + health** |
| Primær værdi | Detektion/forensics | Inventar/compliance | **Availability/kapacitet/alarm** |
| Skrives af | agents/syslog/collector | edge-inventory/scan | **collector (host+probe), edge-heartbeat, app-hooks** |

ITIM *læner sig op ad* CMDB (samme `device_id`-nøgle, targets refererer CMDB-enheder) og kan
*fodre* SIEM (en alarm kan også registreres som security_event hvis relevant), men har sit eget
datalag og sin egen livscyklus/retention.

---

## 2. SABSA-forankring (kort)

| SABSA-lag | For dette system |
|---|---|
| **Kontekstuelt** (forretning) | Oppetid og billedkontinuitet er produktet. Nedetid på headend/data-fast = tabte timelapse-frames = kunde-SLA-brud. |
| **Konceptuelt** (attributter) | *Available, Detectable, Recoverable, Capacity-aware, Accountable, Private-by-design*. |
| **Logisk** | Targets → metrics/health → regler → alarmer → notifikation; RBAC-styret visning; retention. |
| **Fysisk** | Postgres tidsserie-tabeller; headend-collector (launchd); edge via eksisterende heartbeat. |
| **Komponent** | `psutil`, eksisterende `notify`, FastAPI-router, React-side, `pg_cron`/intern scheduler til rollup. |
| **Drift** | Codex ejer launchd/OS-laget; Claude ejer kode/skema/UI; alarm-cooldown som i SIEM. |

**Standard-kroge:** ISO 27001 A.12.1 (kapacitets-/driftsovervågning) og A.12.4 (logning/monitorering);
IEC 62443 SR 6.1/6.2 (audit & kontinuerlig overvågning); CRA (secure-by-default + driftslogning);
GDPR (metrics er **ikke** personoplysninger — se §8, vi designer det sådan).

---

## 3. Arkitektur (overblik)

```
                     ┌─────────────────────────────────────────────┐
   headend host ───► │ headend-collector (launchd-tråd, 30–60 s)    │
   (psutil, probes)  │  • host-metrics (cpu/ram/disk/load/temp)     │
                     │  • service-probes (headend/nginx/pg/ollama)  │
                     │  • data-fast volumen-helbredsprobe           │
                     └───────────────┬─────────────────────────────┘
   edge-enheder ────────────────────►│  (metrics i eksisterende heartbeat/inventory)
   AI-pipeline (batch/kø) ──────────►│  (app-hooks skriver metrics direkte)
                                     ▼
                     ┌─────────────────────────────────────────────┐
                     │ Postgres (letvægt tidsserie)                 │
                     │  monitored_targets · metric_samples ·        │
                     │  health_status · alert_rules · alert_events  │
                     │  + rollups (1m→5m→1t) + retention            │
                     └───────────────┬───────────────┬─────────────┘
                                     │               │
                  /api/itim/* (FastAPI, RBAC)        │ (plugin-seam)
                                     │               ▼
                     ┌───────────────▼──────┐   ┌─────────────────────┐
                     │ React "Drift"-side    │   │ Exporter (valgfri):  │
                     │ tiles · grafer · alarm│   │ Elastic/OpenSearch/  │
                     └───────────────────────┘   │ Prometheus remote-w  │
                                                  └─────────────────────┘
                          Alarm ──► eksisterende notify() (mail/webhook), cooldown som SIEM
```

**Princip:** ét skrive-API og ét datalag. Collectoren og app-hooks kalder samme interne
`record_metrics()/record_health()`. Exporteren (hvis aktiveret) er en *læser* af samme lag —
så Elastic kan tilføjes uden at røre indsamlingen.

---

## 4. Datamodel (Postgres)

Additiv, idempotent migration (samme mønster som `siem._ensure_schema` / `v3_*`-migrationerne).
Tidsserie holdes bevidst smal og indekseret; rollups holder tabellen lille.

```sql
-- 4.1 Hvad overvåger vi (refererer CMDB-device_id når relevant)
CREATE TABLE itim_targets (
    id            SERIAL PRIMARY KEY,
    target_key    VARCHAR(120) UNIQUE NOT NULL,   -- fx 'headend:host', 'svc:nginx', 'vol:data-fast', 'edge:TL-...'
    kind          VARCHAR(40)  NOT NULL,           -- host | service | volume | edge | pipeline
    device_id     VARCHAR(50),                     -- FK-løs kobling til CMDB/Device
    display_name  VARCHAR(160),
    scope         VARCHAR(40)  DEFAULT 'core',     -- core | host | edge | ai
    enabled       BOOLEAN      DEFAULT TRUE,
    meta          JSONB        DEFAULT '{}',
    created_at    TIMESTAMPTZ  DEFAULT now()
);

-- 4.2 Tidsserie (rå, kortlevet — rulles op og slettes)
CREATE TABLE itim_metric_samples (
    target_id     INTEGER      NOT NULL REFERENCES itim_targets(id) ON DELETE CASCADE,
    metric        VARCHAR(60)  NOT NULL,           -- 'cpu_pct','mem_pct','disk_used_pct','io_latency_ms','up','queue_depth'...
    ts            TIMESTAMPTZ  NOT NULL,
    value         DOUBLE PRECISION,
    rollup        VARCHAR(8)   DEFAULT 'raw',      -- raw | 5m | 1h
    PRIMARY KEY (target_id, metric, rollup, ts)
);
CREATE INDEX itim_samples_ts      ON itim_metric_samples (ts);
CREATE INDEX itim_samples_metric  ON itim_metric_samples (target_id, metric, ts DESC);

-- 4.3 Aktuel health pr. target (hurtige tiles uden at scanne tidsserien)
CREATE TABLE itim_health_status (
    target_id     INTEGER PRIMARY KEY REFERENCES itim_targets(id) ON DELETE CASCADE,
    state         VARCHAR(16)  NOT NULL DEFAULT 'unknown',  -- ok | warning | critical | unknown
    summary       TEXT,
    metrics       JSONB        DEFAULT '{}',                -- seneste nøgletal (snapshot)
    changed_at    TIMESTAMPTZ  DEFAULT now(),
    updated_at    TIMESTAMPTZ  DEFAULT now()
);

-- 4.4 Alarm-regler (tærskler) — admin-redigerbare
CREATE TABLE itim_alert_rules (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(160) NOT NULL,
    target_kind   VARCHAR(40),                     -- matcher kind, eller NULL = alle
    target_key    VARCHAR(120),                    -- eksakt target, eller NULL
    metric        VARCHAR(60)  NOT NULL,
    op            VARCHAR(4)   NOT NULL DEFAULT '>',-- > | < | >= | <= | ==
    threshold     DOUBLE PRECISION NOT NULL,
    for_seconds   INTEGER      DEFAULT 60,          -- skal holde i X sek før alarm (anti-flap)
    severity      VARCHAR(16)  DEFAULT 'warning',   -- warning | critical
    enabled       BOOLEAN      DEFAULT TRUE,
    notify        BOOLEAN      DEFAULT TRUE,
    created_at    TIMESTAMPTZ  DEFAULT now()
);

-- 4.5 Udløste alarmer (åbne/lukkede) — til UI + audit
CREATE TABLE itim_alert_events (
    id            SERIAL PRIMARY KEY,
    rule_id       INTEGER REFERENCES itim_alert_rules(id) ON DELETE SET NULL,
    target_id     INTEGER REFERENCES itim_targets(id)     ON DELETE CASCADE,
    severity      VARCHAR(16),
    state         VARCHAR(16)  DEFAULT 'firing',   -- firing | resolved
    value         DOUBLE PRECISION,
    message       TEXT,
    started_at    TIMESTAMPTZ  DEFAULT now(),
    resolved_at   TIMESTAMPTZ,
    notified_at   TIMESTAMPTZ
);
```

**Retention/rollup (holder Postgres slank):** rå samples beholdes fx 48 t, `5m`-rollup 30 dage,
`1h`-rollup 13 måneder. En intern scheduler-tråd (samme stil som AI-batch-polleren) kører
rollup+prune hvert 5./60. minut. Ingen ekstern afhængighed; kan senere flyttes til `pg_cron`.

---

## 5. Metrik-katalog (de fire scopes)

**A. data-fast + kerneservices** (den vigtigste)
- `vol:data-fast`: `mounted` (0/1), `writable` (0/1), `io_latency_ms` (lille test-write+fsync),
  `disk_used_pct`, `smart_ok` (hvis tilgængelig via `diskutil`/`smartctl`).
- `svc:headend`: `up` (HTTP `…/api/health` 200), `latency_ms`.
- `svc:nginx`: `up` (port 443/80), `svc:postgres`: `up` (`SELECT 1`), `svc:ollama`: `up`
  (`/api/tags`, kun hvis strategi bruger lokal).

**B. Vært-metrics (Mac)** via `psutil`
- `host:headend`: `cpu_pct`, `mem_pct`, `load1`, `disk_used_pct` (boot), `swap_pct`,
  `temp_c` (hvis læsbar), `uptime_s`.

**C. Edge-enheder** (genbrug eksisterende heartbeat/inventory — ingen ny edge-kode krævet i v1)
- `edge:<device_id>`: `up`/`last_seen_age_s`, `cpu_pct`, `mem_pct`, `disk_used_pct`,
  `camera_ok` (afledt af device-status/heartbeat). Henter fra `DeviceInventory` + `Device.last_seen`.

**D. AI-pipeline** (app-hooks på det vi lige har bygget)
- `pipeline:ai`: `batch_jobs_running`, `batch_jobs_failed_24h`, `ai_queue_depth`,
  `tag_error_rate`, `gemini_ok`. Skrives fra batch-polleren / AI-worker.

---

## 6. API-kontrakt (`/api/itim/*`, RBAC som CMDB/SIEM)

| Metode | Sti | Rolle | Formål |
|---|---|---|---|
| GET | `/api/itim/health` | viewer | Alle targets + aktuel state (til tiles). |
| GET | `/api/itim/targets` | viewer | Liste/registrér targets. |
| GET | `/api/itim/metrics?target=&metric=&since=&rollup=` | viewer | Tidsserie til grafer. |
| GET | `/api/itim/alerts?state=firing` | viewer | Åbne/lukkede alarmer. |
| GET/POST/PUT/DELETE | `/api/itim/alert-rules` | admin | Tærskler. |
| POST | `/api/itim/ingest/{target_key}` | device/intern | Edge/app skubber metrics (rate-limited som SIEM). |

Intern (ikke HTTP): `record_metrics(db, target_key, {metric: value}, ts)` og
`evaluate_alerts(db)` kaldt af collector-tråden.

---

## 7. Alarmering

Genbrug **`ai.notify`** (allerede brugt af SIEM) → mail + ticket-webhook. Anti-flap via
`for_seconds` på reglen; **cooldown pr. (target, metric)** som SIEM's `_notify_cooldown`
(maks 1 mail/5 min). En firing-alarm åbner en `itim_alert_events`-række; når metrikken er under
tærsklen igen, sættes `resolved`. Kritiske drifts-alarmer kan *valgfrit* også spejles til
`security_events` (kategori `availability`) hvis I vil se dem i SIEM — slået fra by default.

**Startsæt af regler** (seedede, redigerbare): `vol:data-fast io_latency_ms > 250 (for 60s, critical)`,
`vol:data-fast writable == 0 (critical)`, `svc:* up == 0 (for 60s, critical)`,
`host disk_used_pct > 90 (warning)/ > 97 (critical)`, `host mem_pct > 92 (warning)`,
`edge last_seen_age_s > 1800 (warning)`, `pipeline batch_jobs_failed_24h > 0 (warning)`.

---

## 8. Sikkerhed & compliance (designvalg)

- **Ingen personoplysninger:** metrics er numeriske drifts-tal (CPU/disk/latens/op-status).
  Ingen billeder, ingen brugerindhold, ingen IP-adresser i metric_samples. → ITIM-laget er
  **uden for GDPR-scope**; det holder vi som invariant (kodegennemgang sikrer det).
- **RBAC:** læsning kræver `viewer`, regel-ændring `admin` (samme bro som `cmdb._require_cmdb_role`).
- **Ingen hemmeligheder i metrics/summary:** genbrug SIEM's redaction-mønster på fri tekst i
  `message`/`summary`.
- **Mindste rettighed på probes:** service-probes laver kun lokale, ikke-muterende kald
  (`SELECT 1`, HTTP GET health). Volumen-skrivetesten skriver én lille fil i et dedikeret
  probe-dir og rydder op.
- **Audit:** alarm-events er selv en audit-række; regel-ændringer logges (admin-handling).
- **CRA/IEC 62443:** kontinuerlig drifts-overvågning + alarm er direkte evidens for
  "secure-by-default"/"continuous monitoring"-kravene; tilføjes til risk-/krav-registeret.

---

## 9. Plugin-seam til Elastic (fremtidssikring)

Indsamling og lagring kobles bag et lille interface `MetricSink`:

```python
class MetricSink:           # default-implementering skriver til Postgres
    def write(self, samples: list[Sample]) -> None: ...
class ElasticSink(MetricSink):   # valgfri, aktiveres via setting itim_export_elastic_url
    def write(self, samples): ...    # bulk-index til ES/OpenSearch
```

Collectoren kalder `sink.write(...)`; default er Postgres. Vil I senere have Kibana-dashboards,
sættes `itim_export_elastic_url`, og samme samples spejles til Elastic — **uden** at flytte
selve indsamlingen eller UI'et. Dermed respekteres jeres Elastic-ønske, men vi tager ikke
JVM-/disk-byrden før der er et konkret behov.

---

## 10. UI — ny "Drift"-side (Admin-menu)

- **Health-tiles** øverst: data-fast, headend, nginx, postgres, ollama, hver Mac/edge — farve
  efter `state` (grøn/gul/rød), nøgletal + "sidst opdateret".
- **Tidsserie-grafer** (sparklines/linjer) for valgt target/metric, med rollup-skift (1t/24t/7d).
  Genbrug grafkomponenten/mønstret fra eksisterende sider; ingen tung charting-afhængighed nødvendig.
- **Aktive alarmer** med firing/resolved og kvittér.
- **Alarm-regler** (admin) — simpel CRUD-tabel.
- Menupunkt i `Navbar.tsx` under Admin: `{ to:'/observability', label:'Drift', icon: Activity }`.

---

## 11. Optimerings-fund i eksisterende SIEM/CMDB (foldes ind)

1. **Død sqlite-kode** i `siem._ensure_schema` (I bruger ikke sqlite) — fjernes/renses.
2. **`/threats` event_type-mismatch:** queryen filtrerer `event_type='ssh_failure'`, men
   normaliseringen udsender `ssh_tunnel_*` og syslog `network_auth_failed`. Brute-force-detektoren
   rammer derfor sandsynligvis ikke reelle SSH-fejl — udvides til at matche de faktiske typer.
3. **Retention på `security_events`:** ingen prune i dag → vokser ubegrænset. Tilføj samme
   retention-mekanik som ITIM får.
4. **Break-glass checkout** har stadig MFA/IP-whitelist/rate-limit som TODO i koden
   (`cmdb.checkout_break_glass`) — reelt SABSA-/compliance-hul; bør lukkes (egen lille opgave).

Disse er additive og uafhængige af ITIM; kan tages som en separat lille PR.

---

## 12. Rollout-plan og arbejdsdeling

1. **(Claude)** DB-migration (additiv) + `/api/itim/*` + collector-modul + seed-regler.
2. **(Claude)** "Drift"-side + menupunkt; `npm run build`.
3. **(Codex)** Wire collector-tråden ind i headend-opstart (eller egen launchd-agent), bekræft
   `psutil` i venv, og at volumen-probe har skriverettighed i probe-dir. Genstart + verificér.
4. **(Claude)** Verificér: migration kørt, tiles grønne, en bevidst tærskel-test giver alarm-mail,
   retention/rollup kører.
5. Opdatér `SERVICES_OG_DRIFT_kilde_til_sandhed.md` (+ HANDOVER_LOG) med det nye lag.

**Afhængigheder/risici:** `psutil` skal i venv (let); volumen-skrivetest må ikke selv ligge på
data-fast (vælg probe-dir på boot-drevet, ellers fejler den når volumenet er nede — hvilket
omvendt netop *er* signalet, så vi måler "mounted/writable" separat fra latens). Collectoren skal
være billig (få hundrede ms hvert 30.-60. s) for ikke at konkurrere med headend.

---

## 13. Åbne spørgsmål til Peter — AFGJORT af implementeringen (opdateret 2026-07-05, periodisk tjek #45)

**Note (Claude, tjek #45):** Begge spørgsmål blev reelt afgjort af den faktiske v1.0-implementering
(se `HANDOVER_LOG.md`, entries 2026-06-29 og 2026-06-30 09:40) og er ikke længere åbne: (1) tråd-i-
headend blev valgt (ikke egen launchd-agent) — "dør med headend; edge-ping dækker hullet senere";
(2) `psutil`-only blev valgt for v1 — Codex' live-verifikations-entry nævner ingen installation af
`smartmontools`/`powermetrics`, så Mac-temperatur/SMART er stadig ikke en del af v1. Spørgsmålene er
efterladt herunder som historisk kontekst (samme docs-lag-drift-mønster som tidligere fundet i
`RISK_ASSESSMENT_v10.md` §13.3 og `Claude_Intern_CA_mTLS_Design_2026-07-05.md`, tjek #41/#44).

1. **Collector-placering:** egen launchd-agent (isoleret, overlever headend-genstart) **eller**
   tråd inde i headend (enklere, men dør med headend)? *Forslag: tråd i headend nu, egen agent
   senere hvis vi vil overvåge headend selv når den er nede (edge-pinger kan dække det hul).*
   → **Valgt: tråd i headend.**
2. **Temperatur/SMART på Mac:** må Codex installere `smartmontools`/bruge `powermetrics` (kræver
   sudo) for temp/SMART, eller holder vi os til `psutil`-only i v1?
   → **Valgt: `psutil`-only i v1** (temp/SMART ikke aktiveret).
3. **Retention-vinduer:** er 48t rå / 30d 5m / 13mdr 1t passende for jeres lagring?
