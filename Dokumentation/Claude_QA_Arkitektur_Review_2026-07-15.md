# Claude — QA- & Arkitektur-review efter z.ai-perioden

**Dato:** 2026-07-15 · **Forfatter:** Claude (Cowork-session) · **Status:** Til fælles gennemgang (Peter + Claude + Codex)
**Omfang:** Hele repoet på main + ucommittet working tree, med fokus på (a) småfejl/QA efter z.ai-perioden, (b) teknisk gæld og retning fremad, (c) modularisering mod en generisk edge-platform, (d) frontend (DMZ)/backend-adskillelse.
**Metode:** Læsning af 00_START_HER.md, HANDOVER_LOG.md (nyeste ~2 uger), PRIORITIZED_BACKLOG.md, ISSUES.md, TEKNISK GÆLD-analysen, P2-01-planen, MILJOE_ARKITEKTUR v1 — plus statisk analyse (ruff 0.15.21, AST-baseret funktionsmåling, git-historik) og manuel kodelæsning af de berørte filer. Alle fund er verificeret direkte i koden.

---

## 1. Kritiske fund (bør handles på nu)

### 1.1 🔴 SEC: `/api/ai/vocabulary/*` og AI-review-endpoints er HELT uden authentication
`headend/ai/vocabulary_routes.py` og `headend/ai/review_api.py` har ingen `require_role`/`get_current_user` på nogen endpoints — kun `Depends(get_db)`. Routerne mountes i `main.py` (linje 16918-16920) uden `dependencies=[...]`, og nginx' generelle `location /api/` proxy'er dem ud på `timelapse.froekjaer.dk`. Konsekvens:

- Uautentificeret adgang til at **godkende/afvise/merge/omdøbe tags** (vocabulary approve/reject/merge/translation).
- Uautentificeret **`POST /api/review/escalation/approve`** trigger Gemini-kørsler som background task → cloud-behandling af kundebilleder + omkostninger uden login (GDPR/R12-relevant).

Dette er præcis samme fejlklasse som SEC-001 (redaction API), der ER blevet lukket — mønsteret blev bare aldrig efterset på AI-routerne. **Anbefaling:** Tilføj auth på router-niveau: `app.include_router(vocab_router, dependencies=[Depends(require_role("admin","super_admin"))])` (viewer-rolle til de rene læse-endpoints som `/translations` hvis kundevendt UI kræver det). Opret SEC-015-dokument efter SEC-001-skabelonen. *(Codex/Peter: kør venligst denne fix som første prioritet — den er lille og isoleret.)*

### 1.2 🔴 BUG: `get_similar_tag_suggestions` crasher altid (TypeError)
`headend/ai/repositories.py:539` — `_normalize_tag_for_similarity(tag: str)` er defineret **uden `self`** (og uden `@staticmethod`), men bruger `self._stem_tag_word(...)` i kroppen og kaldes som instansmetode på linje 355. Ethvert kald til `GET /api/ai/vocabulary/similar` → `TypeError: takes 1 positional argument but 2 were given`. Fix: tilføj `self` som første parameter. (Nabo-metoden `_clean_tag` viser det tiltænkte mønster.)

### 1.3 🟠 Ucommittet z.ai-arbejde ligger i working tree
`git status` viser ucommittet: `headend/main.py` (+113 linjer Open WebUI-runtime), untracked `headend/openwebui_runtime.py` + `deploy/launchd/dk.froekjaer.open-webui.agent.plist`, samt ændret `.github/workflows/ci.yml` og dokumentation. Kvalitetsproblemer i diffen:

- Bruger deprecated `@app.on_event("startup")` (FastAPI anbefaler lifespan) og starter en rå daemon-tråd der åbner en DB-session hvert 30. sekund — kopiér hellere det eksisterende loop-mønster fra retention/backup-loops.
- Fjerner top-import `import shutil as _shutil`, mens `_shutil` stadig bruges 8 steder. Det virker KUN fordi der ligger en duplikeret mid-fil `import shutil as _shutil` på linje 12884 — skrøbeligt; genindsæt top-importen.
- Settings-nøglen `peter-vil-gerne-lege-med-ollama` som produktions-feature-flag bør omdøbes (fx `openwebui_enabled`) før commit.
- ci.yml-ændringen (py_compile + bash -n på alle trackede filer) er derimod en reel forbedring — behold den.

**Anbefaling:** Beslut commit/ret/kassér i fællesskab. Indtil da: lad filerne ligge (evidens).

### 1.4 🟠 CI gate'r kun 3 af 40 testfiler
`ci.yml` kører kun `test_agent_integrity.py`, `test_headend_endpoints.py` og smoke-suiten. `tests/` har 40 filer, og HANDOVER_LOG (2026-07-13) dokumenterer **36 fejlende tests** (rate limiting, nginx config, node-agent) der bare står og fejler uden at blokere noget. Fejlende tests der ikke gate'r er værre end ingen tests — de lærer alle at ignorere rød. **Anbefaling:** (1) triager de 36: fix, markér `xfail` med issue-reference, eller slet; (2) udvid CI til hele suiten med en kendt-grøn baseline; (3) indfør samme ratchet-princip som ESLint-gaten (H-02).

---

## 2. Kodekvalitet — småfejl og mønstre (ruff + manuel læsning)

| Fund | Omfang | Vurdering |
|---|---|---|
| `F821 undefined-name` | 35 | 32 stammer fra `headend/ai/main_endpoints.py` — en "indsæt i main.py"-skabelon der ligger som død, ikke-importérbar kode i pakken. Slet/arkivér. Resten: repositories.py-buggen (1.2) + 2 i main.py der er "ufarlige" pga. defensive guards (se nedenfor). |
| Defensive `"X" in globals()`-guards | 5 steder i main.py | fx linje 7226 (`_shutil`), 9456 (`STATUS_LABELS`). Det er patch-artefakter der skjuler manglende imports/definitioner i stedet for at rette dem. Fjern guards, ret årsagen. |
| Død kode efter `return` | main.py:16496 | `return {"status": "ok", "tags": tags}` er uopnåelig og refererer udefineret navn — patch-rest. |
| `E402` imports midt i filen | 70 | main.py importerer moduler på linje 12884 m.fl. — følgefejl af copy/paste-vækst. |
| Ubrugte imports (`F401`) | 135 | Støj der skjuler reelle afhængigheder. Autofixbar (`ruff --fix`). |
| Bare `except:` | 11 | Skjuler fejl inkl. `KeyboardInterrupt`. Minimum: `except Exception`. |
| `B023` loop-variabel i closure | 3 (bl.a. `gemini_service.py:726`) | Klassisk sen-binding-bug; virker måske tilfældigt nu. |
| Committede patch-scripts | `headend/ai/apply_*_patch.py` (6 stk.) + `main_endpoints.py` | Engangs-scripts der muterer main.py — de hører ikke til i pakken. Arkivér under `tools/oneoff/` eller slet (git har historikken). |
| `.bak`-filer | `PRIORITIZED_BACKLOG.md.bak` (tracked), `main.py.bak_*` ×7, `DevicePage.tsx.bak_*` ×4 (untracked) | Slet; git er backup. `.gitignore` dækker allerede `*.bak_*`. |

**Positivt, som fortjener at blive nævnt:** ISSUES.md's kritiske A-01/A-02/A-03 (CMDB uden auth, break-glass identitet, route-hack) er reelt lukket på main — CMDB-endpoints har konsekvent `_require_cmdb_role`, og `report_inventory` kaldes kun efter device-auth i main.py. z.ai-committet `464288d3` (authenticate edge update reports) er solidt håndværk: binder body-`device_id` til edge-credential og har medfølgende kontrakttest. Edge-siden (`edge/`) er væsentligt sundere modulariseret end headend (hal/, camera/, capture/, upload/, tunnel/, config/).

---

## 3. Teknisk gæld — status og retning fremad

### 3.1 Gælden VOKSER
Målt mod TEKNISK GÆLD-analysen (2026-07-06) og P2-01-planen (2026-07-07):

| Metrik | 2026-07-06 | 2026-07-07 | I dag (2026-07-15) |
|---|---|---|---|
| main.py linjer | 16.692 | 17.045 | **18.412** |
| Funktioner | 461 | 490 | **520** |
| API-routes i main.py | — | 219 | **235** |
| `get_config` | 366 linjer | — | **373** |
| `startup` | 306 linjer | — | **318** |

Dertil er `edge/agent.py:_lab_tick` vokset til **456 linjer** i z.ai-perioden — en ny monolit-funktion med ad-hoc tilstand via `getattr(self, "_lab_...", ...)`-attributter og kald til privat API (`self._api._post`). Analysen fra 07-06 var rigtig; den er bare ikke blevet fulgt, fordi hver session har optimeret for "feature færdig i dag".

### 3.2 Retningsregler fra nu af (forslag til fælles vedtagelse)
Det rigtige tidspunkt at sætte retningen er nu — foreslås som bindende arbejdsregler i CLAUDE.md/AGENTS-instruktioner, så både Claude, Codex og fremtidige AI-sessioner er underlagt dem:

1. **Stop tilvæksten:** Ingen nye endpoints i `headend/main.py`. Nye endpoints skrives som `APIRouter` i domænemodul (mønster: `headend/api/site_look_config_api.py` + `headend/services/site_look_config_service.py` — det mønster findes allerede og virker).
2. **Boy scout-reglen, afgrænset:** Rør du en funktion >125 linjer, skal den deles op i validation → execution → response (jf. gæld-analysens §2) i samme PR — men refaktorér aldrig utestet kode uden først at skrive en kontrakttest (H-05-mønsteret).
3. **Ratchet-gates i CI:** Udvid H-02-princippet fra ESLint til Python: `ruff check` med baseline-fil; antal violations må aldrig stige. Samme for main.py-linjetal (fail hvis > nuværende).
4. **Alle router-includes har eksplicit auth:** `include_router(..., dependencies=[...])` eller dokumenteret begrundelse for public. Tilføj en automatisk test der itererer `app.routes` og fejler på endpoints uden auth-dependency, med en godkendt allowlist (`/api/health`, login, enrollment). Det havde fanget både SEC-001 og fund 1.1.
5. **Ingen patch-scripts mod kodefiler:** ændringer sker som rigtige commits; engangs-migreringer ligger i `tools/oneoff/` med dato.
6. **TODO-markører med ID** (`# TODO(P2-01): ...`) som gæld-analysen foreslog — plus et ugentligt greb: `grep -rn "TODO(" | wc -l` rapporteres i SYSTEM_HEALTH_REGISTER.
7. **ADR'er (Architecture Decision Records):** Én side pr. strukturbeslutning i `Dokumentation/ADR/`, så AI-sessioner ikke gen-diskuterer eller stille omgør tidligere beslutninger.

### 3.3 P2-01 eksekvering (konkretisering af eksisterende plan)
P2-01-planens moduler er rigtige, men "flyt 5.000 linjer til `update_flow.py`" bytter bare én monolit for en anden. Justeret snit pr. modul: `router.py` (HTTP, tyndt) / `service.py` (forretningslogik, testbar uden FastAPI) / `models.py` (Pydantic). Rækkefølge efter risiko-reduktion: **(1) auth/RBAC** (mest sikkerhedskritisk at kunne teste isoleret), **(2) config-resolution** (`get_config` — mest brugte kodesti), **(3) updates/artifacts**, **(4) AI/batch**, **(5) resten**. Én modul-udtrækning pr. sprint, med kontrakttests før flytning og uændrede URL'er.

---

## 4. Arkitektur: fra Timelapse-produkt til generisk edge-platform

### 4.1 Det strategiske snit: Platform vs. Payload
Ambitionen (vandværker, vindmøller, solceller, sikker remote access til bagvedliggende systemer) kræver ét principsnit, som med fordel kan indføres gradvist under P2-01-refaktoreringen:

**Edge-platform (genbrugelig kerne)** — findes i dag spredt i `edge/`:
- Enrollment/identitet (zero-touch, HMAC/device-token, fremtidig mTLS jf. Intern CA-design 2026-07-05)
- Config-hierarki + signeret policy-pull (global→customer→site→device er ALLEREDE domæne-agnostisk)
- Update-flow (signerede artifacts, rollback, change tickets)
- Telemetri/heartbeat/SIEM-forwarding, CMDB/inventory-rapportering
- Tunnel/remote access (`edge/tunnel/`), HAL (`edge/hal/` — orangepi/rpi/jetson/generic er allerede abstraheret)
- Drift mode/strømstyring, teknikerinterface

**Payload/vertikal (udskiftelig)** — i dag: kamera + capture + billed-QA + AI-tagging. I morgen: Modbus/OPC UA-poll af pumper, vibrations-telemetri fra møller, inverter-data.

**Anbefaling:** Definér et payload-interface i edge-agenten (fx `PayloadDriver`: `configure(cfg)`, `tick(now)`, `collect_telemetry()`, `handle_command(cmd)`), og flyt gphoto2/capture-logikken ind bag det som første implementation. `_lab_tick`-oprydningen (3.1) er den naturlige anledning. På headend-siden svarer det til at holde capture/AI-domænet ude af platform-modulerne under P2-01. **Navngivningen** i DB/API bør samtidig gøres payload-neutral hvor det er gratis (fx "asset" frem for "camera" i nye platform-tabeller — men omdøb ikke eksisterende, jf. additiv-princippet).

### 4.2 Zoner og DMZ (IEC 62443-terminologi: zones & conduits)
Nuværende lab-setup har alt (nginx, FastAPI, Postgres, Ollama, billeder, UI) i én zone på én maskine. Mod prod bør målbilledet være:

| Zone | Indhold | Eksponering |
|---|---|---|
| **Z1 DMZ / præsentation** | nginx (TLS-terminering, 8443, DNS-01), statisk UI-build, rate limiting, fail2ban, WAF-regler | Internet |
| **Z2 Applikation** | FastAPI (platform-API + payload-API adskilt som routere), Ollama | Kun fra Z1 via conduit |
| **Z3 Data** | PostgreSQL, billedlager, backup-target | Kun fra Z2 |
| **Z4 Edge-adgang** | SSH-reverse-tunnel-endpoint / fremtidig broker + Support-CA (break-glass, AccessTickets) | Udgående fra edge; JIT-adgang fra Z2 |
| **Z5 Management** | CMDB, SIEM, node-agent, GRC | Admin-roller, MFA |

Konkret og realistisk på nuværende hardware: zonerne behøver ikke separate maskiner fra dag 1 — start med **logisk** adskillelse (separate nginx-vhosts/porte, separate DB-roller med least privilege pr. modul, UI serveret som ren statisk DMZ-artefakt uden API-nøgler) og dokumentér conduits i SABSA_Architecture_v10. Det gør den fysiske udskilning (staging/prod jf. MILJOE_ARKITEKTUR v1) til et deployment-valg, ikke en omskrivning. Vigtigt eksisterende princip der SKAL bevares i platformen: **edge initierer alle forbindelser** (ingen indgående forbindelser til edge) — det er netop det mønster, der gør "sikker remote access via edgen til backendsystemer" muligt for de nye verticals: fjernadgang sker via edge'ens udgående tunnel + AccessTicket/break-glass-modellen (design 2026-07-06), aldrig ved at åbne porte på OT-nettet.

### 4.3 Frontend/backend
UI'et er allerede en separat SPA (godt), men med 35 sider hvor de største er 1.200-2.000 linjer og med `.bak`-filer i `src/pages/`. Anbefalinger: (1) samme ratchet-tilgang som backend; (2) udskil en typet API-klient (genereret fra OpenAPI-skemaet, som FastAPI gratis leverer) i stedet for håndskrevne fetches — det gør DMZ-snittet og fremtidige payload-UI'er billigere; (3) split de fire største sider i komponenter når de alligevel røres.

---

## 5. Dokumentation — er 00_START_HER/HANDOVER_LOG dækkende?

1. **To dokumentationstræer:** z.ai-perioden har skabt ~20 dokumenter i `docs/` (drift-mode, poll-analyser, site-look, edge-arkitektur, LAB-testguide m.m.), men `00_START_HER.md` nævner kun `Dokumentation/`. En ny session finder dem ikke. **Anbefaling:** Beslut ét hjem (forslag: flyt varige dokumenter til `Dokumentation/`, lad `docs/` være til kode-nære udviklernoter) og tilføj en linje om det i 00_START_HER §6.
2. **Manglende pointere i 00_START_HER:** `PRIORITIZED_BACKLOG.md`, `ISSUES.md`, `TESTLISTE_WEEKEND.md` og `MASTER_TEST_CHECKLIST_v1.md` er ikke nævnt, selvom sessions-opstart i praksis bruger backloggen (jf. Claude-4's handover 07-10). Tilføjes til §3-tabellen.
3. **ISSUES.md er forældet** (opdateret 2026-06-14) og lister A-01/A-02/A-03 som 🔴 åbne, selvom de er lukket på main. Farligt for nye sessioner, der kan bruge dokumentet som arbejdsliste. Opdatér status-kolonnen eller flyt til `Gamle versioner/` med henvisning til RISK_ASSESSMENT_v10.
4. **HANDOVER_LOG.md er 704 KB** — for stor til at "læses først" og tæt på ulæselig for AI-sessioner med kontekstgrænser. **Anbefaling:** Rotér: behold seneste ~30 dage + "Medarbejdere"-sektionen, flyt resten til `HANDOVER_LOG_ARKIV_2026-H1.md`.
5. **Handover-kvalitet fra z.ai-perioden:** Entries er formkorrekte, men statusudsagn skal læses kritisk — fx "Status: Klar til produktion!" (07-13) om ændringer, der aldrig var kørt på device, og "36 tests failed — ikke vores kode" uden triage. Faktuelt korrekte hvad-blev-ændret-lister, overoptimistiske konklusioner. Det bekræfter Peters mistanke: gennemgå z.ai-periodens commits med kontrakttests frem for at stole på log-konklusionerne.
6. **Kernefakta-sektionen i 00_START_HER er god** og var præcis nok til at boote denne session. Efter rettelserne ovenfor vurderer jeg 00_START_HER + HANDOVER_LOG som dækkende.

---

## 6. Prioriteret handlingsliste

| # | Handling | Ejer (forslag) | Størrelse |
|---|---|---|---|
| 1 | SEC-015: Auth på vocab-/review-routere + automatisk route-auth-test | Codex el. Claude | Timer |
| 2 | Fix `repositories.py` `self`-bug + unit test | Codex el. Claude | Minutter |
| 3 | Beslut skæbne for ucommittet Open WebUI-arbejde (ret 1.3-punkterne før commit) | Peter + én agent | Timer |
| 4 | Triage af 36 fejlende tests + fuld testsuite i CI med baseline | Codex | 1-2 dage |
| 5 | Oprydning: main_endpoints.py, apply_*_patch.py, .bak-filer, død kode, `in globals()`-guards | Claude | Timer |
| 6 | Vedtag retningsregler §3.2 (skriv ind i CLAUDE.md/AGENTS) | Peter | Møde |
| 7 | Dokumentation: docs/-beslutning, ISSUES.md-status, HANDOVER_LOG-rotation, 00_START_HER-pointere | Claude | Timer |
| 8 | P2-01 sprint 1: auth/RBAC-modul udtrækkes med kontrakttests | Claude + Codex review | 1 sprint |
| 9 | ADR-001: Platform/Payload-snit + PayloadDriver-interface (design først, ingen kode) | Claude, review af alle | 1-2 dage |
| 10 | SABSA_Architecture_v10: tilføj zone/conduit-målbillede (§4.2) | Claude | Timer |

---

*Alle linjenumre refererer til working tree pr. 2026-07-15 (main @ 806c58fb + ucommittede ændringer).*
