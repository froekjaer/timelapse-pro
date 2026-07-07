# Teknisk Gældsanalyse — headend/main.py

**Dato:** 2026-07-06
**Analysat af:** Claude (AI-assistant)
**Omfang:** headend/main.py (16.692 linjer, 461 funktioner)

---

## 1. Executive Summary

`headend/main.py` er en stor "monolitisk" fil med 16.692 linjer og 461 funktioner. Filen indeholder meget af TimeLapse Pro's core forretningslogik, men størrelsen gør den svær at vedligeholde. Analysen identificerer:

- **20 funktioner > 125 linjer** (gentegnelig for stor kompleksitet)
- **Flerere hardcoded værdier** der bør flyttes til config
- **Ingen TODO/FIXME markers** (dokumenteret gæld er usynlig i koden)
- **Blanding af concerns** (business logik, API-routing, background loops, system ops)

**Anbefaling:** Gradvis refaktorering over flere sprints, ikke "big bang" rewrite.

---

## 2. Største Funktioner (>125 linjer)

| Funktion | Linjer | Problem | Anbefaling |
|----------|--------|---------|-------------|
| `get_config` | 366 | Ekstremt stor, blander config-resolution, validation, og rendering | Opdel i: `_resolve_config()`, `_validate_config()`, `_render_config_response()` |
| `startup` | 306 | Gør for meget: migration, logging-check, admin-setup, loop-start | Træk ud: `_run_startup_migrations()`, `_initialize_background_loops()` |
| `resilience_assessment` | 236 | Kompleks tilstands-logik | Ekstrahér hjælpe-funktioner per kategori (backup, update, edge) |
| `_run_edge_disk_image_build` | 184 | Lang build-sekvens | Opdel i trin: `_prepare_build()`, `_execute_build()`, `_finalize_build()` |
| `prepare_edge_provisioning` | 180 | provisioning-logik | Træk ud: `_validate_provisioning_request()`, `_prepare_provisioning_artifacts()` |
| `enroll_device` | 176 | device enrolment med mange checks | Opdel i: `_verify_device_bootstrap()`, `_finalize_enrollment()` |
| `_run_headend_platform_update` | 158 | update-logik | Simpilere ved at trække fælles patterns ud |
| `_auto_build_and_bind_os_bundle` | 152 | OS bundle build | Opdel i faser |
| `start_ai_batch_job` | 152 | AI batch logik | Ekstrahér: `_validate_batch_request()`, `_submit_gemini_batch()` |
| `grc_dashboard` | 150 | compliance aggregation | Træk ud: `_aggregate_compliance_metrics()` |

**Observation:** De største funktioner har ofte et fælles mønster — de blander validation, eksekvering, og response-rendering. Et generisk refaktorerings-mønster ville være:

1. **Validation-fase** — tjek indput, hent data, valider constraints
2. **Eksekverings-fase** — udfør den faktiske operation (skriv til DB, kald ekstern API)
3. **Response-fase** — render respons til API-klienten

---

## 3. Hardcoded Værdier der Bør Flyttes til Config

### 3.1 URLs og Endpoints

```python
# Disse bør være env-vars eller config-værdier:
"http://127.0.0.1:8000"          # HEADEND_URL / TIMELAPSE_HEADEND_URL
"http://127.0.0.1:11434"         # OLLAMA_URL / TIMELAPSE_OLLAMA_URL
"http://127.0.0.1:5173"          # UI_DEV_URL (kun relevant for udvikling)
"http://ports.ubuntu.com/..."    # APT_MIRROR (relevant for OS bundle)
```

**Anbefaling:** Centraliser disse i:
- Miljøvariable (`TIMELAPSE_OLLAMA_URL`, `TIMELAPSE_APT_MIRROR`)
- eller `settings`-tabellen i databasen (for runtime-konfigurerbare værdier)

### 3.2 Stier

```python
# Disse bør være config-stier:
"/Volumes/data-fast/backup/timelapse-artifacts/edge-images"   # TIMELAPSE_ARTIFACT_PATH
"/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images"  # (alternativ)
"/Volumes/data-fast"                                          # TIMELAPSE_STORAGE_BASE
```

**Bemærk:** Dokumentationen nævner at `/Volumes/data-fast` er rettet fra `/Volumes/data` i DB, men koden kan stadig have gamle hardcoded paths.

---

## 4. Manglende TODO/FIXIE Markører

Analysen fandt **INGEN** TODO, FIXME, XXX, HACK eller TEMPORARY markers i `headend/main.py`.

**Problemet:** Teknisk gæld er ikke synlig i koden, hvilket gør det svært at:
1. Prioritere refaktorering
2. Vide hvad der er "temporary" hacks vs. permanent løsninger
3. Undgå at ændre kode der er markeret som "skal ikke røres"

**Anbefaling:** Tilføj TODO-markører for kendt gæld, f.eks.:
- `# TODO (P2-01): Refactor: denne funktion er for stor og bør opdeles`
- `# FIXME (P0-03): Hardcoded path bør flyttes til config`
- `# HACK (P1-07): Dette er en midlertidig løsning indtil X er implementeret`

---

## 5. Refaktorerings-prioritering

Baseret på SABSA/ISO 27001-principper om "defense-in-depth" og "fail-safe", samt vedligeholdelses-hensyn:

### P1 — Kritisk (bør gøres snart)

1. **Opdater `get_config` (366 linjer)** — Fjerneste fra "single responsibility", brugt overalt i systemet
2. **Opdater `startup` (306 linjer)** — Fejl i startup kan dræbe hele systemet; mindre funktioner er lettere at debugge
3. **Flyt hardcoded paths til config** — Risiko for at koden break ved miljøskift

### P2 — Vigtig (bør gøres inden 6 måneder)

4. **Opdater de 8 øvrige store funktioner (>150 linjer)** — Gradvis nedbrydning
5. **Tilføj TODO-markører** — Gør gæld synlig i koden
6. **Ekstrahér fælles patterns** — Mange funktioner har samme struktur (validation → eksekvering → response)

### P3 — Nice-to-have (kan vente)

7. **Opdater mellemstore funktioner (100-125 linjer)** — Mindre kritisk
8. **Overvej at splitte main.py op** — F.eks. `config.py`, `update.py`, `provisioning.py`, `compliance.py`

---

## 6. Forslag til Modul-opdeling

Hvis `main.py` skal opdeles, foreslås følgende modul-struktur:

```
headend/
├── main.py                    # Kun FastAPI app-definition + routing (efter: ~500 linjer)
├── config/
│   ├── __init__.py
│   ├── resolution.py          # get_config() relateret
│   └── validation.py          # config validering
├── update/
│   ├── __init__.py
│   ├── artifacts.py           # OS bundle, update logic
│   └── rollout.py             # update rollout, status
├── provisioning/
│   ├── __init__.py
│   ├── enrollment.py           # enroll_device
│   └── imaging.py              # edge disk image build
├── compliance/
│   ├── __init__.py
│   ├── dashboard.py            # grc_dashboard, compliance endpoints
│   └── reports.py              # rapporter per standard
├── ai/
│   ├── __init__.py
│   └── batch.py                # AI batch job logic
└── backup/
    ├── __init__.py
    └── archive.py              # backup, restore logic
```

**Bemærk:** Dette er en langsigtet vision, ikke en opgave for én sprint. Gradvis migration anbefales.

---

## 7. Risiko-vurdering

| Risiko | Nuværende | Efter Refaktorering |
|--------|-----------|---------------------|
| Breaking changes ved refaktorering | Medium | Lav (hvis testes gradvist) |
| Introduktion af bugs ved refaktorering | Lav → Medium | Lav (med gode tests) |
| Kode-brede søger/greps bliver sværere | Lav | Medium (flere filer) |
| Forståelse af kodebase for nye udviklere | Lav (alt ét sted) | Lav (modulær struktur er mere intuitiv) |

---

## 8. Næste Skridt

1. **Diskuter med Peter/Codex:** Er denne prioritering rigtig?
2. **Vælg én stor funktion** at starte med (`get_config` eller `startup`)
3. **Skriv tests** før refaktorering (test-coverage er vigtig for sikkerhed)
4. **Opdater PRIORITIZED_BACKLOG.md** med konkrete refaktorerings-opgaver
5. **Tilføj TODO-markører** i koden for kendt gæld

---

## 9. Referencer

- `PRIORITIZED_BACKLOG.md` — P2-01 (refaktorering af main.py)
- `RISK_ASSESSMENT_v10.md` — teknisk gæld og kvalitets-risici
- `SABSA_Architecture_v10.md` — arkitektur-principper
