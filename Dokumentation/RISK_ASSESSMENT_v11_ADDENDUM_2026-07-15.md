# TimeLapse Pro — Risikovurdering & Virtuel Penetrationstest — Addendum til v10 (2026-07-15)

**Version:** v11-addendum (additivt supplement til `RISK_ASSESSMENT_v10.md` — promoveres til v11 når Peter godkender)
**Dato:** 2026-07-15
**Forfatter:** Claude (Cowork-session), SABSA/IEC 62443/ISO 27001/CRA/NIS2/GDPR
**Metode:** Ikke-destruktiv. Statisk kodeanalyse (ruff 0.15.21, AST), konfigurations- og routergennemgang, git-historik, testsuite-kortlægning. Ingen aggressiv scanning, brute force eller exploit-forsøg mod live-miljø. Alle fund verificeret direkte i kildekoden på `main` @ `806c58fb` + ucommittet working tree pr. 2026-07-15.
**Relation:** Bygger på QA-/arkitektur-reviewet `Claude_QA_Arkitektur_Review_2026-07-15.md` (samme dag). Dette dokument formaliserer de sikkerhedsrelevante fund i risikoregister-/pentest-form, så de kan spores på linje med R01–R21 og VPEN-2026-001…009.

> **Vigtigt — samtidig session:** Mens dette review blev lavet, arbejdede en anden Claude/Codex-session aktivt i samme repo (`.git/index.lock` observeret, `headend/main.py` blev ændret live). To af mine kritiske fund (R22, R23 nedenfor) blev **rettet af den samtidige session under selve reviewet** — statusfelterne afspejler det. Linjenumre kan derfor være skredet siden skrivning; verificér mod aktuel kode.

---

## 1. Sammenfatning

Reviewet efter z.ai-perioden (13.–15. juli) bekræfter Peters mistanke: kernen er moden og de tidligere lukkede fund (CMDB-auth, SIEM-auth, kryds-kunde-lækage, MFA-gab) holder stadig på `main`. Men perioden introducerede **to nye reelle sikkerhedshuller af samme fejlklasse som det allerede lukkede SEC-001** (routere monteret uden auth-dependency), samt en voksende mængde teknisk gæld der i sig selv er en integritets-/vedligeholdelsesrisiko (CRA "secure by design"/ISO 27001 A.8.25–A.8.28). De to auth-huller er lukket live under reviewet; den korrekte lukning afslørede til gengæld ét nyt regressionspunkt (R24).

**Samlet posture: uændret LAB/pre-production — ikke Internet-facing production-klar.** Ingen af de nye fund ændrer go/no-go-billedet fra v10, men R22/R23 ville have været go-live-blockere hvis de ikke var fanget nu.

---

## 2. Nye risici (additive til v10-registeret)

### R22 — AI-vokabular- og review-API'er eksponeret uden authentication (NY, fundet + rettet 2026-07-15)
- **Kategori:** Broken Access Control (OWASP A01) · IEC 62443 SR 1.1/1.2 · GDPR art. 32
- **Status:** ✅ **Rettet live 2026-07-15 af samtidig session** (verificér efter merge)
- **Beskrivelse:** `headend/ai/vocabulary_routes.py` (10 endpoints) og `headend/ai/review_api.py` (12 endpoints) definerede samtlige ruter med kun `Depends(get_db)` — ingen `require_role`/`get_current_user`. Routerne blev monteret i `main.py` uden `dependencies=[...]`, og nginx' generelle `location /api/`-proxy eksponerer dem på `timelapse.froekjaer.dk`. Konsekvens i den sårbare tilstand:
  - Uautentificeret godkendelse/afvisning/**merge**/omdøbning af AI-tags (`POST /api/ai/vocabulary/{id}/approve|reject|merge`, `PUT .../translation`) — integritetsbrud på det kundevendte tag-vokabular.
  - Uautentificeret **`POST /api/review/escalation/approve`** → starter Gemini-analyse som background task = cloud-behandling af kundebilleder hos underdatabehandler + omkostninger, uden login. Direkte GDPR-/R12-eksponering.
- **Verificeret (AST):** 22 endpoints, 0 med auth-parameter, routere oprindeligt monteret uden `dependencies`.
- **Rettelse (samtidig session, verificeret i kode):** `app.include_router(vocab_router, dependencies=[require_role("super_admin","admin")])` og tilsvarende for `_rev_router`. `require_role` håndhæver både rolle OG MFA-verificeret session — så fixet lukker også et implicit MFA-gab. **Korrekt lukning.**
- **Residualrisiko:** 🟢 4 efter merge/deploy (var reelt 🔴 15 i den eksponerede tilstand). Se R24 for bivirkning.
- **Læring (systemisk):** Dette er tredje forekomst af samme fejlklasse (SEC-001 redaction, R15 SIEM, nu R22). Punktrettelser stopper ikke mønsteret — se §4 "Kontrol K1" (automatisk route-auth-sweep-test).

### R23 — `get_similar_tag_suggestions` crashede altid (NY, fundet + rettet 2026-07-15)
- **Kategori:** Korrektheds-/tilgængelighedsfejl (ikke sikkerhed) · CRA kvalitet
- **Status:** ✅ **Rettet live 2026-07-15 af samtidig session**
- **Beskrivelse:** `headend/ai/repositories.py` `_normalize_tag_for_similarity()` var defineret uden `self`, men kaldte `self._stem_tag_word()` og blev kaldt som instansmetode. Ethvert kald til `GET /api/ai/vocabulary/similar` → `TypeError`. Funktionen (tag-oprydningsforslag) var dermed 100% ikke-funktionel.
- **Rettelse (verificeret):** `def _normalize_tag_for_similarity(self, tag: str)`. **Korrekt.**
- **Residualrisiko:** 🟢 2. Anbefaling: tilføj unit test (se testdokument §manglende tests) så regressionen ikke kan gentages ubemærket.

### R24 — Kundevendt tag-oversættelses-endpoint over-restringeret af R22-fixet (NY, 2026-07-15)
- **Kategori:** Tilgængelighed/regression (afledt af korrekt sikkerhedsfix) · UX
- **Status:** 🟠 Åben — kræver beslutning
- **Beskrivelse:** R22-rettelsen lægger **hele** `vocab_router` bag `require_role("super_admin","admin")` + MFA. Men `GET /api/ai/vocabulary/translations` kaldes af det kundevendte UI via `timelapse-ui/src/hooks/useTagLabels.ts` (`credentials: 'include'`) for at vise danske tag-labels. Efter fixet vil viewer/operator/kunde-sessioner få **403** på dette read-only endpoint → danske labels falder tilbage til rå engelske kanoniske nøgler i kunde-UI'et (jf. den kendte `tag-translation-ui`-opgave). Sikkerhedsmæssigt korrekt, funktionelt en regression.
- **Anbefaling:** Adskil læse- og skrive-adgang: behold admin+MFA på de muterende endpoints (approve/reject/merge/PUT translation), men eksponér `GET /translations` (og evt. `/statistics`) på `viewer`-niveau — enten via en separat sub-router med lettere dependency, eller ved at flytte de to read-only ruter ud af den admin-gatede router. Cache-venligt, ingen følsomme data. **Flag til samtidig session — dette er direkte konsekvens af deres fix.**
- **Residualrisiko:** 🟡 5 (funktionel, ikke sikkerhed).

### R25 — `POST /api/auth/disable-mfa` mangler step-up/MFA-verificeret session (NY, bekræfter ISSUES.md A-04)
- **Kategori:** Broken Authentication / manglende re-authentication på følsom operation · IEC 62443 SR 1.5 · ISO 27001 A.8.5
- **Status:** 🟠 Åben (bekræftet i kode 2026-07-15)
- **Beskrivelse:** `disable_mfa()` (`headend/main.py:1408`) beskyttes kun af `Depends(get_current_user)` — **ikke** `require_role`. Det betyder:
  1. Handlingen kræver ikke en **MFA-verificeret** session (i modsætning til alle `require_role`-gatede endpoints). En sikkerhedskritisk handling — at fjerne MFA — er dermed svagere beskyttet end at læse en enhedsliste.
  2. En `admin` kan deaktivere MFA for **andre** brugere via `user_id` (koden tillader `role in ("super_admin","admin")`), inkl. potentielt en `super_admin`. Ingen selv-eskalerings-spærre, ingen SIEM-alarm ud over en `log.info`.
  3. En bruger kan selv-deaktivere sin egen MFA uden step-up (re-auth), hvilket underminerer MFA-enforcement-politikken (R02): en kapret, men MFA-"grandfathered" session kan slå MFA fra.
- **Anbefaling:** (a) Kræv MFA-verificeret session + frisk password/TOTP-reauth (step-up) for at deaktivere MFA — også for egen konto. (b) Forbyd at `admin` deaktiverer MFA for `super_admin`. (c) Løft hændelsen fra `log.info` til en SIEM-security-event (`mfa_disabled`, aktør + mål). (d) Overvej at kræve `super_admin` for at røre andres MFA.
- **Residualrisiko:** 🟡 6 (kræver gyldig session for at udnytte; ingen præ-auth-vej fundet).

### R26 — Teknisk gæld i `headend/main.py` som integritets-/vedligeholdelsesrisiko (NY, kvantificeret 2026-07-15)
- **Kategori:** CRA "secure by design"/vedligeholdbarhed · ISO 27001 A.8.25–A.8.28 · SABSA Integrity/Manageability
- **Status:** 🟠 Åben — voksende trend
- **Beskrivelse:** Monolitten voksede i z.ai-perioden på trods af gæld-analysen 2026-07-06 og P2-01-planen 2026-07-07:

  | Metrik | 07-06 | 07-07 | 2026-07-15 |
  |---|---|---|---|
  | `main.py` linjer | 16.692 | 17.045 | **18.412** |
  | Funktioner | 461 | 490 | **520** |
  | Endpoints i main.py | — | 219 | **235** |
  | `get_config` / `startup` | 366/306 | — | **373/318** |

  Dertil `edge/agent.py::_lab_tick` = **456 linjer** med ad-hoc tilstand via `getattr(self, "_lab_*", …)` og kald til privat API (`self._api._post`). Statisk analyse: 135 ubrugte imports, 70 imports midt i filen, 11 bare `except:`, 5 `"X" in globals()`-guards der maskerer manglende definitioner, samt en ikke-importérbar skabelonfil `headend/ai/main_endpoints.py` (32 undefined-name) og 6 committede `apply_*_patch.py`-scripts der muterer produktionskode. Hver enkelt er lille; samlet sænker de signal-til-støj og øger sandsynligheden for at næste auth-hul af R22-typen glider igennem ubemærket.
- **Anbefaling:** Se §4 (retningsregler + ratchet-gates) og QA-reviewets §3.
- **Residualrisiko:** 🟠 8 (ikke direkte udnyttelig, men forøger sandsynligheden for fremtidige fund; primær driver bag at holde posture på "ikke production-klar").

### R27 — Ucommitteret produktionskode (Open WebUI runtime) i working tree uden review-spor (NY, 2026-07-15)
- **Kategori:** Change management / SBOM-integritet · CRA · ISO 27001 A.8.32
- **Status:** 🟠 Åben — afventer Peters beslutning
- **Beskrivelse:** `headend/main.py` (+113 linjer Open WebUI-runtimekontrol), untracked `headend/openwebui_runtime.py` + `deploy/launchd/dk.froekjaer.open-webui.agent.plist`, og ændret `.github/workflows/ci.yml` ligger ucommitteret. Kvalitetsproblemer: deprecated `@app.on_event("startup")`, rå daemon-tråd der åbner DB-session hvert 30. sek., fjernet top-import `import shutil as _shutil` (virker kun pga. en duplikeret mid-fil-import — skrøbeligt), og et produktions-feature-flag ved navn `peter-vil-gerne-lege-med-ollama`. Uden commit er ændringen uden for change-ticket-/SBOM-sporet.
- **Anbefaling:** Ret de fire punkter, omdøb flaget (fx `openwebui_enabled`), commit via normal change-ticket-vej. `ci.yml`-ændringen (py_compile + `bash -n` på alle trackede filer) er en reel forbedring og bør beholdes.
- **Residualrisiko:** 🟡 5.

---

## 3. Virtuel penetrationstest — opdatering 2026-07-15

**Metode:** Som §5 i v10 — ikke-destruktiv, code review + konfigurations-/routeranalyse. Ingen live-exploit.

### 3.1 Angrebsflade-delta siden juni-kørslen
Uændret flade-billede (nginx/TLS/HSTS, `/api/health` bevidst åben, `/api/cmdb` 401, login rate-limited `10/minute` verificeret på `main.py:1539`, SFTP 22222 chroot, Ollama/OpenWebUI kun interne). Nye observationer:

| Flade | Fund 2026-07-15 |
|---|---|
| `/api/ai/vocabulary/*` | Var uautentificeret (**VPEN-2026-010**) → lukket live |
| `/api/review/*` | Var uautentificeret (**VPEN-2026-010**) → lukket live |
| `/api/auth/disable-mfa` | Kun `get_current_user`, ingen step-up (**VPEN-2026-011** = R25) |
| CORS | `allow_origins=[ALLOWED_ORIGIN]` (enkelt origin), `allow_credentials=True`, `allow_methods/headers=["*"]`. OK **så længe** `ALLOWED_ORIGIN` er sat eksplicit i prod (default falder tilbage til `http://127.0.0.1:5173` — bekræft env i prod). (**VPEN-2026-012**, lav) |

### 3.2 Nye pentest-fund

#### VPEN-2026-010 — Uautentificerede AI-router-flader (= R22)
**Prioritet:** P0 (ville have været go-live-blocker). **Status:** ✅ lukket live 2026-07-15. Se R22. Verifikationskrav før nedlukning: (1) confirm merge+deploy, (2) automatiseret route-auth-sweep-test (K1) tilføjet så regressionen ikke kan ske igen, (3) R24-regressionen håndteret.

#### VPEN-2026-011 — `disable-mfa` uden step-up (= R25)
**Prioritet:** P1. **Status:** 🟠 åben. Se R25. Ikke præ-auth-udnytteligt, men underminerer MFA-politikken og tillader admin→andres-MFA-nedtagning uden alarm.

#### VPEN-2026-012 — CORS-default falder tilbage til dev-origin
**Prioritet:** P3 (hygiejne). **Beskrivelse:** `ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", os.getenv("BASE_URL", "http://127.0.0.1:5173"))`. Hvis hverken `ALLOWED_ORIGIN` eller `BASE_URL` er sat i prod-miljøet, tillades credentialed CORS kun fra `127.0.0.1:5173` (harmløst, bryder blot UI) — men en forkert sat `BASE_URL` kunne åbne en uønsket origin. **Anbefaling:** fail-fast ved opstart hvis `ALLOWED_ORIGIN` ikke er eksplicit sat i `prod`/`staging` (miljø kendes allerede via `TIMELAPSE_ENV`).

#### VPEN-2026-013 — CI-testgate dækker kun 3 af ~49 backend-testfiler
**Prioritet:** P1 (assurance-hul, ikke direkte sårbarhed). **Beskrivelse:** `ci.yml` kører kun `test_agent_integrity.py`, `test_headend_endpoints.py` + smoke. Af `tests/` (38 filer) kræver **~20 en kørende headend på `127.0.0.1:8000`** med seedede testbrugere (se `conftest.py` `TEST_CREDENTIALS`) — de kan strukturelt ikke passere i CI/sandbox uden provisioneret server+DB. Det er hovedårsagen til de "36 fejlende tests" i HANDOVER_LOG (07-13): de er **live-integrationstests, ikke knækket kode**. Konsekvensen er at en reel regression i unit-/kontacttestbar kode (fx et fremtidigt R22) ikke fanges automatisk. **Anbefaling:** se testdokumentet — split unit vs. integration med markør + skip-if-server-unreachable, kør unit-subset i CI med grøn baseline, kør integration mod `rd` i et separat, ikke-blokerende job.

### 3.3 Stadig åbne fra v10-pentesten (uændret status, ikke re-verificeret her)
VPEN-2026-001 (port 8443-migration), -002 (admin-SSH-flade), -003 (secrets i LaunchAgent), -006 (GCP SA-nøgle-rotation), -007 (retention — nu delvist lukket via P0-05). Ingen ny evidens ændrer disse; se v10 §5.

---

## 4. Retningsregler & kontroller fremad (SABSA/CRA/ISO)

Reviewet peger på ét systemisk mønster: **punktrettelser lukker enkeltfund, men ikke fejlklassen.** Anbefalede bindende kontroller (bør ind i `CLAUDE.md`/AGENTS-instruktioner så alle sessioner er underlagt dem):

- **K1 — Automatisk route-auth-sweep (lukker R22/SEC-001/R15-klassen permanent):** en pytest der itererer `app.routes` og fejler hvis et endpoint mangler en auth-dependency, med en eksplicit allowlist (`/api/health`, login, enrollment, `/translations` efter R24-beslutning). Havde fanget alle tre historiske forekomster.
- **K2 — Ingen nye endpoints i `main.py`:** nye ruter som `APIRouter` i domænemodul (mønster: `headend/api/site_look_config_api.py`), altid monteret med eksplicit `dependencies=[...]` eller dokumenteret public-begrundelse.
- **K3 — Ratchet-gates i CI (som ESLint H-02):** `ruff`-violations og `main.py`-linjetal må aldrig stige. Fejl bygget hvis > baseline.
- **K4 — Step-up på sikkerhedskritiske selvbetjeningshandlinger:** disable-mfa, password-skift, token-udstedelse, break-glass → kræv MFA-verificeret + frisk re-auth (R25).
- **K5 — Change-ticket/commit før deploy:** ingen ucommitteret produktionskode i drift (R27); engangs-migreringer i `tools/oneoff/`, ikke `apply_*_patch.py` i pakken.
- **K6 — ADR-proces:** strukturbeslutninger (platform/payload-snit, zone-model) som korte ADR'er i `Dokumentation/ADR/`, så AI-sessioner ikke stiltiende omgør hinandens arkitektur.

---

## 5. Opdateret samlet risikooversigt (delta)

| Risk | Score | Trend |
|---|---|---|
| R22 AI-router uden auth | 🟢 4 (efter deploy) | 🆕 fundet + rettet live 2026-07-15 (var 🔴 15) |
| R23 tag-similarity crash | 🟢 2 | 🆕 fundet + rettet live 2026-07-15 |
| R24 translations over-restringeret | 🟡 5 | 🆕 regression af R22-fix — åben |
| R25 disable-mfa uden step-up | 🟡 6 | 🆕 bekræfter ISSUES A-04 — åben |
| R26 teknisk gæld main.py | 🟠 8 | 🆕 voksende (16.692→18.412 linjer) |
| R27 ucommitteret OpenWebUI-kode | 🟡 5 | 🆕 afventer beslutning |

**Blokkere for go-live (Internet) — uændret fra v10:** R05 (edge-kryptering/mTLS), R09 (backup/restore-evidens), R12 (GDPR/DPIA), VPEN-2026-001 (port 8443). **R22 ville have været blocker** men er lukket. Nye P1-punkter før første kunde: R24 (kunde-UI), R25 (MFA step-up), VPEN-2026-013 (CI-assurance).

---

## 6. Prioriteret behandling af de nye fund

| # | Handling | Ejer | Prioritet |
|---|---|---|---|
| 1 | Verificér R22-merge/deploy + tilføj K1 route-auth-sweep-test | Samtidig session / Codex | P0 |
| 2 | R24: giv `GET /translations` (+`/statistics`) viewer-adgang uden at åbne skrive-ruterne | Samtidig session | P1 |
| 3 | R23: tilføj regressions-unit-test for `get_similar_tag_suggestions` | Claude/Codex | P1 |
| 4 | R25: step-up + super_admin-spærre + SIEM-event på disable-mfa | Claude/Codex | P1 |
| 5 | VPEN-013: split unit/integration-tests, unit-subset i CI (se testdokument) | Codex | P1 |
| 6 | R27: ret 4 punkter + commit Open WebUI-arbejde via change ticket | Peter + 1 agent | P1 |
| 7 | R26/K2/K3: vedtag retningsregler + ratchet-gates | Peter (beslutning) | P1 |
| 8 | VPEN-012: fail-fast på manglende `ALLOWED_ORIGIN` i prod/staging | Codex | P3 |

---

## 7. Dokumenthistorik (addendum)

| Version | Dato | Ændringer |
|---|---|---|
| v11-addendum | 2026-07-15 | Claude (Cowork): R22–R27 + VPEN-2026-010…013 tilføjet efter QA-review. R22/R23 rettet live af samtidig session under reviewet; R24 identificeret som regression af R22-fixet. Kontroller K1–K6 foreslået. Promoveres til `RISK_ASSESSMENT_v11.md` (og v10 → `Gamle versioner/`) når Peter godkender. |

*Alle linjenumre pr. working tree 2026-07-15. Verificér mod aktuel kode — filen redigeres muligvis samtidig af en anden session.*
