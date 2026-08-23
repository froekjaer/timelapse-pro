# GRC — opdateret beslutningsliste: hvad venter på Peter?

**Dato:** 2026-08-23
**Forfatter:** Kimi (AI-assistent)
**Kildegrundlag:** `main` @ `90cf483c`. Opfølgning på `kimi-grc-afventer-2026-08-19.md` — hvert punkt genverificeret mod aktuel kode og HANDOVER_LOG-entries (9)–(15) fra 2026-08-21 samt PR'er #79–#102. **Denne liste erstatter 2026-08-19-versionen som den aktuelle arbejdsliste.**

---

## Ændringer siden 2026-08-19 (hvad der er rykket)

| Punkt fra 19/8 | Status 23/8 |
|---|---|
| **1. Plaintext SSH-key-kolonne** (🔴) | ✅ **Kodefix merget** (PR #96): de 4 orphaned `devices`-kolonner droppes automatisk ved headend-startup. Claude har BEVIDST ikke lukket GRC-fundet endnu — det lukkes først når næste headend-deploy har kørt, og kolonnerne er verificeret væk i produktions-DB. **Ingen beslutning længere — afventer deploy + verifikation.** |
| **2. Break-glass-designkonflikt** (🔴) | ✅ **BESLUTTET af Peter 2026-08-21** (entry 11): ét design vinder — password-baseret `BreakGlassAccount` bevares som nødadgang, og RBAC-scopede tekniker-SSH-nøgler (PR #79 + #95 + #97/98/100) er det daglige adgangsspor. Restarbejdet er udførelse, se nedenfor. |
| **5. docker-ce/apt-kilde-sporing** (🟡) | ✅ **Implementeret** (PR #80): apt-kilde-drift-detektion bygget, docker-ce registreret som forventet, styret kanal i `target.yaml`. Lukket. |
| **6b. `orangepi`-password som formelt break-glass** (🟡) | ✅ **Overflødiggjort** af beslutningen i entry (11) — det nye design bruger `BreakGlassAccount` (password-baseret) + RBAC-nøgler, ikke `orangepi`-password. |

---

## Del 1 — Beslutninger der STADIG venter på Peter (prioriteret)

### 1. 🔴 R06: device fjernet midt i en rollout

- **Uændret siden 19/8.** Ældste ubesluttede punkt (venter siden **2026-07-05**).
- **Valg:** (a) permanent blokering af decommission under rollout, (b) nuværende adfærd, (c) "delvist bekræftet"-markering. SABSA/ISO27001 A.8.32-anbefalingen peger på **(c)**.
- **Kilde:** RISK_ASSESSMENT_v10.md linje 901, 1052-1068.

### 2. 🔴 `TL-DCA63234D813` — udfas eller behold?

- **Uændret siden 19/8.** Stale-credential-runbooken er forberedt men ikke eksekveret; der findes ingen dokumenteret ufasningsbeslutning.
- **Valg:** Udfas enheden formelt (eksekver runbooken), eller behold den aktiv med roterede credentials.
- **Kilde:** STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md.

### 3. 🟠 `system-hash` fallback for artifact-signatur (F-005)

- **Genverificeret 23/8: stadig aktiv i koden** (`headend/main.py:6740, 6762, 7026-7031`). Headend accepterer hash-binding uden GPG-nøgle som signaturgrundlag.
- **Valg:** Formaliser en PO-risikoaccept, eller fjern fallback'en og kræv GPG-signering overalt.
- **Kilde:** kimi-2026-08-15.md (F-005); kode verificeret på `main` 23/8.

### 4. 🟠 C-08 og C-10 (fra MASTER_REVIEW_CLOSURE-spotcheck)

- **C-08:** BT-pairing/TOTP-firewall lifecycle — rører fysisk hardware-adfærd (BlueZ-agent, iptables på levende enheder).
- **C-10:** Ingen session-revocation/absolut levetid — rører hele auth-sessionsmodellen på tværs af alle endpoints.
- **Valg:** Begge er for store til at ændre uden Peters eksplicitte retning (blast radius). Skal de designes nu, parkeres bevidst, eller droppes?
- **Kilde:** HANDOVER_LOG entries 2026-08-20 (4) og (5).

### 5. 🟠 Ubuntu Noble på TL-C87FF9587CA0 — bevidst eller drift?

- **Sag:** Enheden kører reelt **Ubuntu 24.04 (Noble)**, ikke den dokumenterede 22.04 (Jammy)-baseline. To "identiske" produktionsenheder er på forskellige OS-major-versioner, udokumenteret. `target.yaml` er bevidst holdt på jammy, så afvigelsen vises som drift i stedet for stille at blive absorberet.
- **Valg:** Var opgraderingen bevidst/planlagt (→ opdatér baseline og dokumentation), eller utilsigtet drift (→ plan for konvergens)?
- **Kilde:** HANDOVER_LOG 2026-08-19 (nat), `FIND-TL-C87FF9587CA0-UBUNTU-NOBLE-UNDOCUMENTED-OS-UPGRADE`.

### 6. 🟠 Skal headend kunne trigge Service Operations fjernt?

- **Sag:** Headend kan i dag udstede `EdgeServiceGrant`, men har INGEN relay/dispatch-mekanisme — Service Operations er udelukkende lokal (bootstrap_cli.py på selve enheden). Bekræftet som en reel, ueksekveret arkitektur-mulighed.
- **Valg:** Byg fjern-triggering (bekvemmelighed, men udvider headends magt over enheder), eller behold det som bevidst lokal-only (sikkerhedsmæssigt renere)?
- **Kilde:** HANDOVER_LOG 2026-08-21 (9).

### 7. 🟡 Break-glass password-flow: byg det ende-til-ende?

- **Sag:** Peter har valgt at beholde password-baseret break-glass, men `BreakGlassAccount`s to TODOs er stadig åbne: (a) `emergency`-brugeren oprettes ikke ved provisionering, (b) password-rotation ved checkout propagerer aldrig til enhedens rigtige UNIX-password. **Designet er besluttet, men virker reelt ikke endnu.**
- **Valg:** Sæt dette i arbejde (det er den eneste vej til at break-glass rent faktisk fungerer i produktion), eller accepter at nødadgang pt. kun er manuel SSH via den delte headend-nøgle?
- **Kilde:** HANDOVER_LOG 2026-08-21 (11).

### 8. 🟡 Dobbelt heartbeat/sync-loop på edge — ryd op?

- **Sag:** Genverificeret 23/8: `edge/agent.py::_tick()` kører STADIG det gamle `_send_heartbeat()` + `_pull_config()` + `_check_and_apply_updates()` (linje 306-311) **parallelt** med den nye konsoliderede `_run_sync()` (linje 830) fra PR #76, der skulle erstatte dem. De to bruger uforenelige hash-rum, hvilket får "Config version ændret via heartbeat" til at fyre ved hvert eneste kald — aldrig stabiliserer.
- **Valg:** Grønt lys til at fjerne det gamle heartbeat-loop helt? (Ren teknisk gæld, men rører wire-protokollen for alle enheder — derfor ikke gjort uden at spørge.)
- **Kilde:** HANDOVER_LOG 2026-08-21 (9); kode verificeret på `main` 23/8.

### 9. 🟡 `emergency`-kontoen på de to live enheder — hvor kom den fra?

- **Sag:** En `emergency`-konto med `breakglass_shell_wrapper.sh`-shell findes reelt på begge live enheder (UID 1002), men **ingen kode i repoet har nogensinde oprettet den** (verificeret 23/8: scriptet findes kun nævnt i dokumentation, ikke i `edge/scripts/`). Nogen har provisioneret den manuelt, udenfor git.
- **Valg:** Skal kontoens oprindelse undersøges (hvem/hvornår/hvordan), og skal den ind under den nye BreakGlassAccount-model eller fjernes?
- **Kilde:** HANDOVER_LOG 2026-08-21 (13).

### 10. 🟡 Lav-prioritet, stadig åbne

- **(a) CMDB baseline-reconciliation scheduling:** stadig kun on-demand endpoint (verificeret 23/8: kun `main.py:11727`, ingen periodisk job). Beslut om automatisk cadence.
- **(b) NPU-modelvej:** installér eksisterende `.nb`-model på TL-C87FF9587CA0, eller kør trænings-pipeline først?
- **(c) Open-Meteo/geokodning:** stillingtagen til geokodning af Travbyen/"Mod baggård".
- **(d) Google Drive Photos Library:** sikkerhedskopieres den overhovedet? (+ kontrolleret Drive-genstart, memory-pressure guard).
- **(e) FIND-MEM-001:** findes stadig kun i `grc_items`-DB — slå op med `psql`, eller lad mig gøre det næste gang jeg har DB-adgang.

---

## Del 2 — Afventer PETERS HANDLING (ikke beslutning, bare udførelse)

Disse er besluttet/bygget, men kræver at Peter selv gør noget:

1. **Registrér din egen SSH-nøgle** (fra entry 11+15): Brugere-siden → din bruger → sæt `field_role = technician` → "SSH-nøgler" → generér direkte i browseren (PR #100 — ingen CLI nødvendig længere) eller indsæt din `~/.ssh/id_ed25519.pub`. **OBS: brug IKKE `timelapse_headend_ed25519` — det er stadig den delte operationelle nøgle.**
2. **Kør servicetekniker-provisionering på de 2 live enheder** (kræver din sudo; kommandoerne genbruges fra `inject_edge_image.py`s blok — se entry 11). Bemærk: UID-kollisionen på TL-043EB9E72EFD er rettet i koden (entry 13) — brug scriptet fra entry 13 til port 2204, standard til port 2201 (allerede gjort?).
3. **Visuelt tjek af UsersPage** efter badge-fixet (entry 14) — Claude kunne ikke logge ind og verificere selv.
4. **Verificér hjælpemenuen** i UI'en (PR #89 deployet 23/8 kl. ~04:30): "Hjælp" i hovedmenuen + redningskrans-ikon øverst til højre.

---

## Del 3 — Afventer udførelse af AI-teamet (ingen beslutning nødvendig, men udestående)

- **Deploy + verifikation af kolonne-drop** (PR #96), derefter lukkes `FIND-DEVICES-PLAINTEXT-SSH-KEY-COLUMN` i GRC (entry 12).
- **U-01, U-03 (delvist), U-04, U-14** fra update-flow-auditten — bekræftet åbne (interrupted install / ikke-atomisk file-copy / disk-space preflight / reject-bekræftelsesdialog).
- **GO_LIVE-blokkere:** E-02 restore-test (🔴), C-03 manuel password-bekræftelse rd/staging/prod (🔴), A-01..A-13 netværks-audits (🔴).
- **FIND-FAIL2BAN-SSHD-GAP-001** og **FIND-TEST-ISOLATION-001** — sidstnævnte vurderet til at kræve Peters gennemsyn før påbegyndelse, da den rører hele test-suiten bredt.
- **Vitest-infrastrukturen** i `/tmp/timelapse-test-continuity-plan` — STATUS UKENDT 23/8 (mappen er ikke i repoet; har to gange været årsag til at kendte fixes ikke nåede main). Bør bekræftes committet/merget eller bevidst droppet.
- **SEC-016 punkt 3:** dokumentér SSH/konsol som sanktioneret break-glass for allerede udrullede enheder — bør nu skrives mod det NYE design (BreakGlassAccount + RBAC-nøgler), ikke det gamle.

---

## Henvisninger

- `Dokumentation/kimi-grc-afventer-2026-08-19.md` (forrige version — historik)
- `Dokumentation/HANDOVER_LOG.md` — især entries 2026-08-19 (nat), 2026-08-20 (1)–(7), 2026-08-21 (9)–(15)
- `Dokumentation/RISK_ASSESSMENT_v10.md` (R06)
- `Dokumentation/STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md`
- `Dokumentation/kimi-2026-08-15.md` (F-005)
- `Dokumentation/MASTER_REVIEW_CLOSURE_2026-08-15.md` (C-08, C-10, U-serien)
