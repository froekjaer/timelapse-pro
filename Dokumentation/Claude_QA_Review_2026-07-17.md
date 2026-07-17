# Claude — QA-opfølgning & retningsnotat

**Dato:** 2026-07-17 · **Forfatter:** Claude (Cowork-session, ny) · **Status:** Til fælles gennemgang (Peter + Claude + Codex)
**Omfang:** Opfølgning på `Claude_QA_Arkitektur_Review_2026-07-15.md` + `Codex_REVIEW_Claude_Arkitektur_Risk_Test_2026-07-15.md` mod koden pr. i dag (main @ 5987852f + working tree), plus svar på Peters to spørgsmål: (a) modularisering mod generisk edge-platform, (b) teknisk gæld — retningen fra nu af.
**Metode:** Fuld læsning af 00_START_HER, HANDOVER_LOG (nyeste entries), ADR-001, Modularisering-planen, teknisk gæld-analysen, begge 15/7-reviews m.fl. Statisk analyse (ruff 0.15.22, AST-funktionsmåling, git-historik) + manuel kodelæsning af nyeste kode (GRC-registret, route-auth-testen, backup.sh, TOTP-flows). Alle fund verificeret direkte i koden.

---

## 1. Hvad er lukket siden 15/7-reviewet (anerkendelse)

Codex' trancher 1-3 har reelt lukket hovedparten af 15/7-fundene. Verificeret i dag:

| 15/7-fund | Status i dag |
|---|---|
| R22 vocab/review uden auth | ✅ `vocab_read_router` (viewer) / `vocab_router` + `_rev_router` (super_admin) — korrekt splittet |
| R23 `_normalize_tag_for_similarity` self-bug | ✅ Rettet |
| R24 `/translations` 403-regression | ✅ Viewer-adgang genoprettet |
| R25 MFA-disable uden step-up | ✅ Step-up + SIEM-events |
| Route-auth sweep (K1) | ✅ `headend/tests/test_route_auth_coverage.py` — solid: rekursiv dependency-inspektion, eksplicit exception-liste med begrundelser, high-risk-matrix |
| Bare `except:` | ✅ 0 i egen kode (headend/edge/node-agent) |
| `main_endpoints.py` (død patch-skabelon) | ✅ Slettet |
| JWT-secret divergens main/redaction | ✅ Fail-fast i prod (<32 tegn afvises); redaction delegerer til central auth |
| CI kun 3 testfiler | ✅ Fuld `not integration`-suite + py_compile + shell-check; symlinks gjort relative |
| Brudte absolutte symlinks deploy/backup.sh | ✅ Relative nu |
| GRC-register (nyt siden) | ✅ Gennemlæst `grc_register_api.py` (380 linjer): auth på ALLE endpoints, super_admin-krav på dokumentgodkendelse, hashbar evidens, snapshot-baseret revisionsidentitet. Godt håndværk. |

Testbaseline pr. 15/7: 1.033 collected, 486 passed, 0 failed (serverløst scope). Arbejdet i denne periode er af høj kvalitet — retningen fra ADR-001/K1-K6 **virker**.

---

## 2. Nye fund (ikke tidligere dokumenteret)

### 2.1 🔴 SEC-016 (forslag): Fabriksstandard BT PAN TOTP-secret — universel default credential

`headend/main.py` (linje ~4066 og ~5262) og `edge/scripts/totp-service.py` (linje ~102) bruger den hardcodede fabriksstandard **`JBSWY3DPEHPK3PXP`** som fallback for BT PAN technician-TOTP, når intet secret er sat i hierarkiet (global/kunde/site/kamera). DB-kommentaren siger eksplicit `NULL = fabriksstandard`.

- Secret'et er **det kanoniske demo-secret fra pyotp-dokumentationen** — det første enhver angriber prøver. Enhver kan generere gyldige TOTP-koder for alle enheder, der står på fabriksstandard.
- Angrebsvektoren kræver Bluetooth-nærhed til edge-enheden (fysisk/lokal), så udnyttelsen er begrænset — men enhederne står per design ubemandede i felten (byggepladser, og fremover vandværker/møller).
- **Compliance:** CRA Annex I §1(1) forbyder udlevering med kendte udnyttelige default-credentials; IEC 62443-4-2 CR 1.5 (authenticator management) og NIS2 art. 21 rammes også. Dette skal lukkes før CE-mærkning under CRA overhovedet kan diskuteres.
- Fundet er **ikke** nævnt i RISK_ASSESSMENT v10/v11-addendum eller noget SEC-dokument.

**Anbefaling (fail-closed, additiv):**
1. Provisionering/enrollment genererer et kryptografisk tilfældigt per-device `bt_totp_secret` (basen findes allerede — kolonnen + hierarkiet er der).
2. Fjern fabriksstandard-fallback: intet secret ⇒ BT PAN-management **deaktiveret** (fail-closed), ikke "åben med kendt nøgle".
3. Migration: generér secrets for eksisterende enheder ved næste config-pull; SIEM-event når en enhed stadig kører factory-default.
4. Opret `SEC-016`-dokument efter SEC-001-skabelonen + nyt R-nummer i GRC-registret (nu i PostgreSQL).

### 2.2 🟠 GOV-01: Ratchet-baseline blev HÆVET — governance-mekanismen holdt ikke ved første tryk

`tests/architecture_baseline.json` blev i commit `fc3e58b8` (2026-07-16) hævet fra `18483` → `18549` (+66 linjer), samtidig med at main.py voksede tilsvarende. Ratchet-reglen (K3: "baseline må kun sænkes efter udtrækning") blev altså omgået ved at flytte loftet — netop det, ratchets skal forhindre. Ingen undtagelse er dokumenteret i commit eller handover.

Det er ikke en katastrofe (+66 linjer), men det er **den første test af, om K1-K6 er bindende i praksis — og den fejlede**. Hvis baseline kan hæves uden ceremoni, er ratchet'en dekorativ.

**Anbefaling:** (1) Vedtag eksplicit: baseline-ændringer opad kræver ADR-reference eller en "RATCHET-EXCEPTION"-linje i commit + handover-entry med begrundelse og tilbagebetalingsplan. (2) Betal de 66 linjer tilbage som del af første P2-01-udtræk og sænk baseline under 18.483. (3) Overvej at CI-jobbet nægter ændringer af `architecture_baseline.json` i samme commit som vækst i main.py, medmindre commit-beskeden indeholder nøgleordet.

### 2.3 🟠 R09: Backup-default stadig i stykker (gentagelse — nu 2. påmindelse)

`deploy/scripts/backup.sh` linje 26 har fortsat `BACKUP_BASE="${BACKUP_BASE:-/Volumes/data-fast}"` — volumen-roden er ikke skrivbar for `peter`, så backup fejler med default-indstillinger (manifesteret 2026-07-16, jf. handover). Scriptet er korrekt fail-closed (`set -euo pipefail`), men **default-konfigurationen producerer ingen backups**. Handover 07-16 bad Codex fikse det; det er endnu ikke sket. R09/P0-03 er fortsat go-live-blocker uden grøn restore-evidens.

### 2.4 🟡 Oprydningsrestancer fra 15/7-handlingslisten (punkt 5 og 7 — ikke udført)

- **6 × `headend/ai/apply_*_patch.py`** ligger stadig i pakken (engangs-scripts der muterer main.py). Flyt til `tools/oneoff/` eller slet.
- **`.bak`-filer:** `main.py.bak_*` ×7, `integration.py.bak_*` ×3, `DevicePage.tsx.bak_*` ×4 m.fl. (untracked) + **`PRIORITIZED_BACKLOG.md.bak` er tracked**. Slet; git er backup.
- **`docs/` vs `Dokumentation/`:** de 20 z.ai-dokumenter i `docs/` er stadig ukendte for 00_START_HER (beslutning udestår).
- **`ISSUES.md`** er stadig dateret 2026-06-14 og lister A-01..03 som åbne, selvom de er lukket. Bør have en forældelses-banner eller flyttes til `Gamle versioner/` — nu hvor GRC-registret i PostgreSQL er autoritativt, er dokumentet dobbelt farligt.
- **`HANDOVER_LOG.md` er nu 779 KB** og rotation er stadig ikke sket. Derudover er strukturen skredet: de to nyeste entries (07-16 GRC v1, 07-17 GRC migration) ligger **over** "Medarbejdere"/"Skabelon"/"## Log"-sektionerne, mens resten ligger under — loggen har nu to indsættelsespunkter. Forslag: rotér til `HANDOVER_LOG_ARKIV_2026-H1.md` (alt før 2026-07-01) og saml alle entries under ét "## Log" igen.
- **134 ubrugte imports (F401)** og 75 × E402 (imports midt i filen) består i ruff-sweepet — autofixbart, lav risiko, tag det med i første udtræks-PR.

### 2.5 🟡 Cirkulær import-workaround spreder sig som mønster

De nye API-moduler (`grc_register_api.py`, `storage_api.py`, m.fl.) bruger alle `from main import get_current_user` **inde i funktionskroppen** for at undgå cirkulær import. Det virker, men cementerer main.py som nav: hvert nyt modul binder sig runtime til monolitten. Det er det stærkeste tekniske argument for at **P2-01 sprint 1 = udtræk af auth/RBAC-modulet** (`headend/platform/auth.py` e.l.): derefter kan alle routere importere auth rent, og mønsteret forsvinder af sig selv. Bemærk også at de nye moduler bruger rå `payload: dict` frem for Pydantic-modeller — acceptabelt for interne admin-API'er, men Pydantic bør være husstandarden ved udtræk.

### 2.6 Målinger (gælden pr. i dag)

| Metrik | 07-06 | 07-15 | **07-17** |
|---|---|---|---|
| main.py linjer | 16.692 | 18.412 | **18.549** (= ratchet-loft, jf. 2.2) |
| Funktioner i main.py | 461 | 520 | **525** |
| Direkte routes i main.py | — | 235 | **235** (ratchet holder ✅) |
| Funktioner >125 linjer | 20 | — | **14** (get_config 372, startup 322, resilience 232 …) |
| `_lab_tick` (edge/agent.py) | — | 456 | **457** |
| UI-sider >1.200 linjer | — | 4 | **7** (BackupPage 2.016 er størst) |

Konklusion: **route-ratchet'en virker** (235 fastholdt), linje-ratchet'en blev omgået én gang, og selve udtrækket (P2-01/Fase 2) er endnu ikke begyndt. Gælden er stabiliseret, ikke reduceret.

---

## 3. Teknisk gæld — retningen fra nu af (svar på Peters spørgsmål 2)

Retningen ER sat — ADR-001 + K1-K6 er de rigtige regler, og §1 viser at de efterleves af agenterne. Det der mangler er ikke flere regler, men **eksekvering og to justeringer**:

1. **Gør ratchet-undtagelser dyre** (GOV-01, jf. 2.2). En ratchet, der kan hæves stiltiende, er ingen ratchet.
2. **Start udtrækket nu — auth/RBAC først.** Alt peger samme vej: sikkerhedskritikalitet (15/7-reviewet), cirkulær-import-mønsteret (2.5), og at hvert nyt API-modul gør behovet større. Én modul-udtrækning pr. sprint med kontrakttest før flytning (mønsteret `api/`+`services/` findes allerede og virker — site_look, GRC, storage beviser det). Efter hvert udtræk: **sænk baseline**.
3. **Gældsbudget frem for gældsstop:** enhver session, der rører main.py, skal efterlade den mindre end den fandt den (netto-linjer). Det er boy scout-reglen gjort målbar — og den håndhæves allerede af ratchet'en, hvis baseline sænkes løbende.
4. **Synliggør gælden i SYSTEM_HEALTH_REGISTER:** main.py-linjer, funktioner >125 linjer, ruff-total, ESLint-total, testtal — én tabel, opdateret ved handover. Så kan alle tre se om kurven knækker.
5. **TODO(ID)-markører:** kun 9 findes i dag. Ved hvert fund der udskydes: markér i koden med GRC-ID, så gælden er synlig hvor den bor (og nu sporbar i PostgreSQL-registret).

Det rigtige tidspunkt at sætte retningen var 15/7 — og det skete. Det rigtige tidspunkt at bevise den er nu: **første P2-01-udtræk er den eneste handling, der flytter kurven.**

---

## 4. Modularisering mod generisk edge-platform (svar på Peters spørgsmål 1)

**Kort svar: Ja — og beslutningen er allerede truffet og bindende (ADR-001, accepteret 2026-07-16).** Platform/payload-snittet med `PayloadDriver` + capability manifest, proces-isolation, control/data-plane-adskillelse, fail-closed privilegier og JIT-conduits dækker præcis ambitionen om vandværker/vindmøller/solceller med sikker remote access. Jeg har efterprøvet snittet mod SABSA/IEC 62443/CRA-kravene og finder det rigtigt — inkl. Codex' seks amendments, som var nødvendige skærpelser. Der er ingen grund til at gen-designe; der er grund til at **eksekvere**.

Gap-analyse — hvad der konkret mangler mellem beslutning og virkelighed:

| Gap | Status | Næste skridt |
|---|---|---|
| `contracts/` (PayloadDriver + manifest-schema) | Findes ikke endnu | **Fase 1-spike:** definér kontrakten og wrap nuværende kameralogik bagom — anledningen er `_lab_tick`-oprydningen (457 linjer, R26). Beviser kontrakten passer, før noget flyttes. |
| ADR-002 (payload-pakkeformat, signering, proces-sandbox, control/data-plane) | Ikke skrevet | Skriv parallelt med Fase 1-spiket — spiket informerer ADR'en. |
| Zone/conduit-register med SL-T og enforcement points (Codex' skærpelse 1) | Ikke skrevet | Ét dokument/GRC-datasæt: pr. conduit: enforcement point, tilladte flows, identitet, protokol, kryptering, logging, target security level. |
| P2-01 Fase 2 (platform ud af monolitten) | Ikke begyndt | Auth/RBAC først (jf. §3.2). |
| CODEOWNERS + path-filtreret CI | Ikke sat op | Timer-opgave, sætter to-spors-modellen op i GitHub. |

**Om sikker remote access til OT-backends** (vandværkets SRO/PLC, møllens styring): mønsteret findes allerede i produktet — edge initierer alle forbindelser, reverse tunnel + AccessTicket/break-glass (R19, Support Access Model 2026-07-06, Intern CA/mTLS-design 2026-07-05). Det, der gør det OT-klart, er allerede normativt i ADR-001 §6/amendment 5: JIT-tickets, destinations-/port-allowlist, kortlivede certifikater, session recording, kill switch, kundegodkendelse. Min tilføjelse: når første OT-vertical bygges (Fase 4), skal conduit'en ind i zone/conduit-registret med **SL-T pr. zone** og en eksplicit dataklassifikation (procesdata ≠ billeddata — andre retention- og integritetskrav; for et vandværk er integritet/availability vigtigere end confidentiality, omvendt af timelapse-billeder). Det er dokumentarbejde oven på eksisterende mekanik — ikke ny kode.

**Skalérbarhedsbekymring at holde øje med:** headend-monolitten er i dag også *platformens* headend. Når payloads bliver flere, må headend-siden følge samme snit (platform-API vs. payload-API som separate routere/moduler) — det er allerede planens Fase 2/3, blot værd at fastholde ved hvert udtræk: **spørg "platform eller payload?" ved hver eneste modul-udtrækning** (afgrænsningstesten i ADR-001: ville modulet se identisk ud for et vandværk?).

---

## 5. Dokumentation — er 00_START_HER + HANDOVER_LOG dækkende?

00_START_HER.md bootede denne session korrekt — kernefakta, ADR-binding og GRC-banneret er præcis det en ny session skal bruge. Jeg har lavet følgende **additive** rettelser i dag: opdateret "Sidst opdateret", tilføjet manglende pointere (PRIORITIZED_BACKLOG, MASTER_TEST_CHECKLIST, teknisk gæld-analysen, P2-01-planen, 15/7-reviewene + dette dokument, STAGING_TIL_PROD_PROMOTION, HEADEND_GENERATOR), markeret ISSUES.md som forældet, og tilføjet en note om `docs/`-mappen og om governance-gates' placering i koden.

Udestående dokumentbeslutninger (Peters bord):
1. **HANDOVER_LOG-rotation** (779 KB + dobbelt indsættelsespunkt, jf. 2.4) — jeg foreslår at gøre det, men rører ikke strukturen uden ok.
2. **`docs/`-mappens skæbne** (flyt varige dokumenter til `Dokumentation/`, resten forbliver kode-nære noter?).
3. **ISSUES.md → `Gamle versioner/`** nu hvor GRC-registret i PostgreSQL er autoritativt.

---

## 6. Prioriteret handlingsliste

| # | Handling | Ejer (forslag) | Prioritet |
|---|---|---|---|
| 1 | SEC-016: per-device BT TOTP-secret, fjern factory-default fail-open (2.1) + GRC-entry | Codex (kode) + Claude (SEC-doc) | 🔴 P0 (CRA-blocker) |
| 2 | R09: ret `BACKUP_BASE`-default + grøn restore-evidens (2.3) | Codex | 🔴 P0 (go-live-blocker, 2. påmindelse) |
| 3 | GOV-01: vedtag ratchet-undtagelsesregel + betal 66 linjer tilbage (2.2) | Peter (regel) + første udtræk | 🟠 P1 |
| 4 | P2-01 sprint 1: udtræk auth/RBAC-modul med kontrakttests (§3.2 + 2.5) | Claude + Codex review | 🟠 P1 |
| 5 | Fase 1-spike: `contracts/PayloadDriver` + wrap kameralogik (§4) | Claude design + Codex impl. | 🟠 P1 |
| 6 | ADR-002 (pakkeformat/signering/sandbox) + zone/conduit-register | Claude, review af alle | 🟡 P2 |
| 7 | Oprydning: apply_*_patch.py, .bak-filer, F401/E402, tracked .bak (2.4) | Hvem der først har ledig time | 🟡 P2 |
| 8 | Dokumentbeslutninger: HANDOVER-rotation, docs/, ISSUES.md (§5) | Peter | 🟡 P2 |
| 9 | Gældsmetrikker i SYSTEM_HEALTH_REGISTER (§3.4) | Claude | 🟡 P2 |

---

*Linjenumre refererer til working tree pr. 2026-07-17 (main @ 5987852f). Ingen kode er ændret i denne session — kun dokumentation, jf. samarbejdsmodellen og Codex' igangværende testarbejde.*
