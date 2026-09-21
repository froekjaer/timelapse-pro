# TimeLapse Pro — Risikovurdering & Virtuel Penetrationstest — Addendum v12 (2026-09-19)

**Version:** v12-addendum (additivt supplement til `RISK_ASSESSMENT_v10.md` + `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md`, som stadig ikke er promoveret til en samlet v11/v12 — afventer Peters godkendelse, jf. samme konvention)
**Dato:** 2026-09-19
**Forfatter:** Claude (Sonnet 5), på Peters mandat ("vi har lavet mange ændringer siden sidste sikkerhedsanalyse — lav en ny, inkl. login på begge Edge for at tjekke unødvendig software")
**Metode:** Praktisk, evidensbaseret review — IKKE en klausul-komplet certificeringsaudit (IEC 62443/ISO 27001-fuldtekst er licenseret og ikke importeret i dette repo, jf. Dokumentation/REGULATORISK_OG_STANDARD_REFERENCE_v1.md §fuld-audit-katalogberedskab). Ikke-destruktiv: statisk kodegennemgang (delta-diff `806c58fb..928134be`, 220 filer, +32391/-4857), GRC-registeret (Postgres `grc_items`, direkte forespørgsel), samt **live, read-only SSH ind på begge fysiske Edge-enheder** via de allerede eksisterende reverse-tunnels (port 2201/2204, forhåndsgodkendt i `.claude/settings.local.json`). Ingen kommandoer skrev til enhederne, ingen tjenester blev stoppet/ændret, ingen hemmeligheder blev læst i klartekst (redigeret ved kilden med `sed`, se §2).
**Relation:** Bygger på `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md` (R22–R27, VPEN-2026-010…013, K1–K6) og på PR #242 (`zai/edge-physical-audit-2026-09-16`, 3 dage gammel — genbruges, ikke gentaget, jf. §14-reglen om ikke at duplikere nylig auditering). Regulatorisk rammeværk genbruger `Dokumentation/REGULATORISK_OG_STANDARD_REFERENCE_v1.md` (2026-07-16, stadig "living reference") uændret, med to opdateringer noteret i §5.

---

## 1. Executive summary

**Samlet posture: uændret LAB/pre-production.** Ingen af fundene her ændrer go/no-go-billedet fra v10/v11, men ét fund er kritisk og har ligget åbent i 19 dage uden at være registreret nogetsteds i GRC. Den nye trust-/mTLS-arkitektur (WP-2/WP-4, `headend/trust/*`, se §4) er solidt designet på nøglehåndtering (CA-nøgle nu Keychain-beskyttet) men har to reelle huller, ingen af dem eksponeret endnu fordi koden ligger på en umerged draft-PR (#246). K1-kontrollen fra juli (route-auth-sweep) er implementeret og kører i CI — det systemiske R22-mønster er nu strukturelt lukket. R24/R25 er bekræftet rettet i koden.

| # | Fund | Alvor | Status |
|---|---|---|---|
| F-1 | Levende GitHub-credential i `.git/config` på Edge1 (TL-C87FF9587CA0) | 🔴 Kritisk | Åben 19 dage, **aldrig i GRC** |
| F-2 | `iperf3` lytter på 0.0.0.0:5201 (Edge1) | 🟠 Høj | Ny, ikke i GRC |
| F-3 | `rpcbind`/portmapper lytter på 0.0.0.0:111 (Edge2) | 🟠 Høj | Ny, ikke i GRC |
| F-4 | `fail2ban` inaktiv på begge Edges, SSH lytter 0.0.0.0:22 | 🟡 Medium | Allerede tracked: `FIND-FAIL2BAN-SSHD-GAP-001` |
| F-5 | Dev-rig-pakker på Edge1 vokset 29→~40 siden 2026-09-16 | 🟡 Lav-medium | Re-baseline anbefalet |
| F-6 | `trust/grants.py` replay-beskyttelse er single-værdi, ikke nonce-sæt | 🟠 Høj (design, ikke live) | Ny, kun på draft-PR #246 |
| F-7 | `trust/policy.py` MFA-gate er tautologisk (fail-open-risiko for fremtidige kaldere) | 🟡 Medium (latent) | Ny, kun på draft-PR #246 |
| F-8 | `provisioning.py::issue_tls_certificate_from_csr` uden Keychain-beskyttelse af CA-nøgle-param | 🟡 Lav (uwired) | Ny, flag før den kobles på |
| F-9 | CRA-rapporteringspligt trådte i kraft 2026-09-11 (8 dage siden) — SEC-013 dækker den ikke | 🟠 Høj (compliance) | Ny |
| R22/R24/R25 | Route-auth-sweep, translations-split, disable-mfa step-up | ✅ Verificeret rettet i kode | GRC opdateret denne runde |

---

## 2. Kritisk fund — F-1: Levende GitHub-credential på Edge1, aldrig registreret

**Historik:** En Claude-session fandt 2026-08-31 (`HANDOVER_LOG.md` linje 828-839) at `/opt/timelapse/edge/.git/config` på TL-C87FF9587CA0 indeholdt en levende GitHub Personal Access Token i klartekst i `origin`-URL'en, med anbefaling "roter/tilbagekald denne token snarest." Ingen senere handover-entry bekræfter rotation. Den efterfølgende fysiske audit (PR #242, 2026-09-16) tjekkede ikke for dette og klassificerede Edge1's dev-rig-rester som "harmløse."

**Verificeret nu (2026-09-19, read-only, token ALDRIG læst i klartekst):**
```
ssh -p 2201 orangepi@127.0.0.1 "cat /opt/timelapse/.git/config | sed -E 's#https://[^@/]+@#https://[REDACTED]@#g'"
→ url = https://[REDACTED]@github.com/froekjaer/timelapse-pro.git
```
Stien har flyttet sig fra `/opt/timelapse/edge/.git` (rapporteret 08-31) til `/opt/timelapse/.git` (samme checkout-rod, `edge/` er en underkatalog) — men det er **samme lækage, stadig til stede**, blot en anelse forskudt sti. Edge2 (TL-043EB9E72EFD) har fortsat intet git-checkout — bekræftet rent.

**Konsekvens:** Enhver med filsystem- eller backup-adgang til Edge1 har haft de-facto push-adgang til hele repoet i 19 dage. Dette er en direkte krænkelse af allerede registrerede krav: `REQ-...-SEC-002 "Secrets ikke i Git"` og `REQ-...-UPD-001 "Edge må ikke bruge direkte Internet/GitHub/apt"`.

**Hvorfor det er sket igen:** Dette er nøjagtig det mønster CLAUDE.md advarer om — et kritisk fund blev korrekt identificeret og korrekt eskaleret i HANDOVER_LOG, men **aldrig fulgt op i GRC-registeret**, så ingen efterfølgende session (inkl. en fuld fysisk audit 16 dage senere) genopdagede det systematisk. Handover-log alene er ikke nok til at forhindre at et fund forsvinder — det skal i GRC for at overleve session-skift.

**Anbefaling:** (1) Roter/tilbagekald tokenen på GitHub (kun du kan gøre dette). (2) Fjern `/opt/timelapse/.git`-checkoutet på Edge1 — bekræftet ikke-destruktivt (ikke deploy-mekanismen). Begge dele afventer din beslutning (spurgt og noteret: du roterer først). (3) Tilføj en periodisk automatiseret check (fx del af den eksisterende `governed update`-pipeline eller en cron/systemd-timer på hver Edge) der scanner for `.git/config`-filer med embedded credentials — forhindrer fjerde gentagelse.

---

## 3. Uønsket/unødvendig software og tjenester — live verifikation

Bygger på PR #242's kapacitetsmatrix (2026-09-16) uden at gentage den; fokus her er på netværkslyttende tjenester, som den audit ikke tjekkede eksplicit.

| Device | Tjeneste | Binding | Vurdering |
|---|---|---|---|
| Edge1 | `iperf3` | **0.0.0.0:5201 + [::]** | **F-2 — unødvendigt**: netværks-benchmark-værktøj, ingen auth, LAN-tilgængeligt. Ingen legitim produktionsbrug identificeret. IEC 62443-4-2 "least functionality"-brud. |
| Edge1 | CUPS (`ipp`) | 127.0.0.1:631 | Unødvendigt, men loopback-only → lav risiko. Rester fra dev-rig (samme klasse som xfce/pihole, jf. PR #242 §7-D13). |
| Edge2 | `rpcbind`/portmapper | **0.0.0.0:111 + [::]** | **F-3 — unødvendigt**: legacy RPC/NFS-portmapper, kendt enumerations-/amplifikationsvektor, ingen NFS-brug i arkitekturen. Højere prioritet end Edge1's CUPS fordi bundet til alle interfaces og bekræftet **PRODUKTIONS-enhed** (live capture). |
| Begge | `fail2ban` | inaktiv | Allerede tracked (`FIND-FAIL2BAN-SSHD-GAP-001`, medium, ejer ikke sat) — **ikke duplikeret her**, men skærpet: begge Edges' SSH lytter på `0.0.0.0:22`/`[::]:22`, så manglende brute-force-beskyttelse er reel eksponering, ikke kun en LAN-antagelse. |
| Edge1 | dev-rig-pakker (xfce/xorg/lightdm/pihole-mønster) | — | `dpkg -l` case-insensitive match = **~40 linjer** i dag vs. **29** rapporteret 2026-09-16 (3 dage siden). Måling ikke identisk metode (denne kørsel talte linjer, ikke unikke pakker), så tallet er indikativt, ikke en bekræftet stigning — men bør re-baselines med samme metode som PR #242 for at afgøre om Edge1's dev-rig-footprint reelt vokser. |
| Begge | `unattended-upgrades` | enabled | ✅ Positiv kontrol, ingen ændring. |

Ingen af disse blev stoppet eller ændret live (aftalt med Peter: dokumentation only, remediation via normal governed change-path).

---

## 4. Trust-/mTLS-arkitektur (`headend/trust/*`, draft PR #246) — pre-merge review

**Vigtigt kontekst:** Dette er **ikke deployeret**. `main` står på `928134be` (2026-09-16); mTLS/trust-arbejdet ligger på den umergede draft-PR #246 (`chatgpt/api-mtls-20260917`, senest `3375f78c`). Ingen Edge kører denne kode endnu. Fundene her er pre-merge review-feedback, ikke aktive produktionshuller.

**Positivt — CA-nøglehåndtering (commit `a4bbc09f`):** Headend CA-privatnøglen er nu PKCS8+`BestAvailableEncryption`, passphrase hentes udelukkende via en snæver, root-ejet C-helper der læser macOS System Keychain (`deploy/macos/timelapse-ca-keychain.c`, `caller_is_allowed()` begrænser til uid 0/kendt runtime-bruger). Passphrase går aldrig gennem argv/env (kun stdout-pipe, stderr discardet), fejl giver kun generiske fejlbeskeder (ingen nøgle-/passphrase-lækage i exceptions), nøglefil håndhæver `0o600` + `O_EXCL`-oprettelse. **Ingen fund her** — adresserer den tidligere key-at-rest-svaghed korrekt.

**F-6 — `trust/grants.py` replay-beskyttelse (høj, design):** Replay-tjek sammenligner kun mod en enkelt `last_challenge_id` (linje ~194-196), ikke et brugt-nonce-sæt. Et opsnappet challenge C1 kan genafspilles efter en efterfølgende legitim C2-request er behandlet, fordi kun "seneste" tjekkes, ikke "brugt før." Scope: `EdgeServiceGrant`-validering for tekniker-til-Edge-adgang. **Anbefaling:** brug et tidsvindues-begrænset brugt-nonce-sæt (eller monotont sekvensnummer + afvis ≤ seneste), ikke kun sidste værdi.

**F-7 — `trust/policy.py` MFA-tautologi (medium, latent):** PDP'ens MFA-gate udleder `mfa_required` af selve `mfa_verified`-parameteren (linje ~103), så den håndhæver ikke uafhængigt "denne handling kræver MFA" — den stoler på at kalderen allerede har tjekket det. De to nuværende kaldere (`service_access_api.py:43`, `ssh_tunnel_terminal_api.py:174`) gør faktisk det korrekte tjek før kald, så **ikke udnytteligt i dag** — men PDP'en giver ingen reel garanti, og en fremtidig kalder der glemmer pre-tjekket vil fejle stille (fail-open, ikke fail-closed). **Anbefaling:** flyt selve MFA-verifikationen ind i PDP'en, ikke kun dens flag.

**F-8 — `provisioning.py::issue_tls_certificate_from_csr` (lav, uwired):** Tager `ca_key_pem` som rå string-parameter uden indbygget Keychain-beskyttelse — modsat mønsteret i `headend_api_mtls.py`. Ingen kaldere fundet i produktionskode endnu (kun tests). **Flag før denne kobles til en rute**: skal følge samme passphrase-beskyttede-at-rest-mønster.

**Bekræftet lukket (mindre fund, ikke sikkerhedskritisk):** `trust/grants.py` bruger et hardkodet test-secret-fallback når `"pytest" in sys.modules`, uden et eksplicit env-only-gate. Lav sandsynlighed for produktionseksponering, men bør lukkes med et eksplicit `TIMELAPSE_ENV`-tjek i stedet for at stole på modul-introspektion.

---

## 5. Verificerede lukninger siden juli (R22/R24/R25 + K1 + VPEN-2026-013)

Disse stod som `candidate_review` i GRC (bulk-importeret fra addendummet, aldrig ejer-valideret — `attributes.method = "document_migration_requires_owner_validation"`). Nu verificeret direkte i kildekoden på `main@928134be`:

- **K1 (route-auth-sweep):** Implementeret som `headend/tests/test_route_auth_coverage.py` — itererer `app.routes`, kræver auth-dependency fra en vedligeholdt allowlist eller en eksplicit begrundet undtagelse. **Kører i CI** (`.github/workflows/ci.yml`, ingen `integration`-marker på filen). Det systemiske R22/SEC-001/R15-mønster er nu strukturelt forhindret, ikke kun punktrettet.
- **R25 (disable-mfa step-up):** `headend/main.py:1108-1154` kræver nu frisk password-reverifikation + TOTP (hvis MFA aktiv) for enhver disable-mfa-handling, og kun `super_admin` kan målrette andres `user_id` (linje 1118-1120) — en `admin` kan ikke længere deaktivere en anden brugers (herunder `super_admin`'s) MFA. **Bekræftet rettet.**
- **R24 (translations over-restricted):** `headend/ai/vocabulary_routes.py` har nu to routere — `vocab_read_router` (GET pending/translations, `require_role("viewer")`) og `vocab_router` (alle mutationer, `require_role("super_admin")`). Kundevendt UI kan læse labels uden admin-adgang; skrive-ruterne er strammere end oprindeligt foreslået (super_admin, ikke admin+MFA) — værd at bekræfte det er bevidst. **Bekræftet rettet.**
- **VPEN-2026-013 (CI-dækning):** 211 testfiler i `tests/`+`headend/tests/`+`edge/ai/tests/` i dag, kun 21 med `integration`-marker; CI kører `pytest ... -m "not integration"`, dvs. reelt alle 211 filers ikke-integrationstests. Markant forbedring fra "~3 af 49."
- **Nye routere stikprøve** (capture_access, edge_disk_image, ai_batch, admin_settings, cameras): ingen umuterende-uden-auth endpoints fundet; alle state-changing (POST/PUT/DELETE) har eksplicit per-endpoint `require_role(...)`.

**GRC-registeret er opdateret denne runde** (se `headend/tools/import_grc_security_review_20260919.py`) til at afspejle disse som ejer/session-validerede lukninger i stedet for uvaliderede kandidater.

---

## 6. GDPR / AI Act / cloud-subprocessor — status uændret siden DPIA-dokumentet

`Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` §4 dokumenterer allerede Google Gemini/Vertex AI som subprocessor for cloud-eskaleret billedanalyse, med en **stadig åben, selv-flagget verifikationsopgave**: den faktisk konfigurerede GCP-region er ikke bekræftet som EU, kun at koden (`headend/ai/gemini_service.py:194-217`) *understøtter* et EU-region-tjek. Denne runde tilføjer intet nyt her — genbekræfter blot at det stadig er åbent og bør prioriteres, da det er den letteste GDPR Art. 44-eksponering at lukke (en miljøvariabel-verifikation, ikke et kodeprojekt).

---

## 7. F-9 — CRA-rapporteringspligt trådte i kraft, ikke dækket af SEC-013

`Dokumentation/REGULATORISK_OG_STANDARD_REFERENCE_v1.md` (linje 45) noterer at CRA's rapporteringspligt ("Reporting starter 2026-09-11") nu er trådt i kraft — **for 8 dage siden**. `Dokumentation/SEC-013_Incident_Response_Procedure.md` definerer interne 24t/72t-frister (72t matcher GDPR Art. 33 til Datatilsynet) men nævner intet om CRA/ENISA-rapporteringskanalen for aktivt udnyttede sårbarheder eller alvorlige hændelser i "products with digital elements." Hvis TimeLapse Pro er i scope som fabrikant (afhænger af endelig produktklassifikation, jf. samme dokument), er dette et reelt, tidssensitivt hul — særligt relevant fordi F-1 (den lækkede credential) i sig selv er præcis den slags hændelse en opdateret procedure bør kunne rute korrekt.

**Anbefaling:** Udvid SEC-013 med en eksplicit CRA/NIS2-rapporteringsgren (hvem, hvornår, hvilken myndighed/CSIRT), betinget af den produktklassifikations-afklaring dokumentet allerede efterlyser. Ikke eksekveret her — kræver Peters beslutning om fabrikant-rolle først.

---

## 8. Ikke gentaget / eksplicit ude af scope denne runde

- Fuld kapacitetsmatrix-genkørsel (PR #242 er 3 dage gammel og dækker det grundigt — genbrugt, ikke duplikeret, jf. §14-reglen).
- Klausul-komplet IEC 62443-4-2/3-3/2-4 eller ISO 27001-mapping (kræver licenseret katalogtekst, ikke til stede i repoet).
- Fjern-eksekvering: `iperf3`/`rpcbind` er dokumenteret, ikke stoppet (Peters beslutning: governed change-path). `.git`-checkoutet på Edge1 er ikke rørt (Peters beslutning: roter token først).
- China CSL/DSL/PIPL, NERC CIP, SOCI Act, DORA og lignende sektor-/marked-betingede rammer — ingen ændring i produktets marked/kunde-scope siden juli-vurderingen; `REGULATORISK_OG_STANDARD_REFERENCE_v1.md`'s klassifikation (B/C/H, betinget) står uændret.
- R23 (tag-similarity-crash) — ikke re-verificeret denne runde, lav prioritet, ingen indikation af regression.

---

## 9. Prioriteret handlingsliste

| # | Handling | Ejer | Prioritet |
|---|---|---|---|
| 1 | Roter/tilbagekald GitHub-tokenen (F-1) | Peter | **P0** |
| 2 | Efter rotation: fjern `/opt/timelapse/.git` på Edge1 (bekræftet ikke-destruktivt) | Peter/næste session | P0 |
| 3 | Fjern/deaktiver `iperf3` (Edge1) og `rpcbind` (Edge2) via governed update, ikke ad-hoc SSH | Codex/næste session | P1 |
| 4 | Nonce-sæt i stedet for single-value replay-tjek i `trust/grants.py` (F-6) — før PR #246 merges | ChatGPT/ejer af #246 | P1 (pre-merge) |
| 5 | Flyt MFA-håndhævelse ind i `trust/policy.py` PDP, ikke kun flag (F-7) — før PR #246 merges | ChatGPT/ejer af #246 | P2 (pre-merge) |
| 6 | Keychain-beskyt `ca_key_pem`-parameteren i `provisioning.py` før den kobles til en rute (F-8) | ejer af trust-modulet | P2 |
| 7 | Bekræft faktisk konfigureret Gemini/Vertex-region er EU (§6) | Peter/Codex | P1 |
| 8 | SEC-013: tilføj CRA/NIS2-rapporteringsgren, betinget af fabrikant-rolle-afklaring (§7) | Peter (beslutning) | P2 |
| 9 | Re-baseline Edge1 dev-rig-pakketal med samme metode som PR #242 (F-5) | næste audit-session | P3 |
| 10 | Automatiseret periodisk scan for `.git/config`-lækager på Edges (forhindrer 4. gentagelse) | Codex | P2 |

---

## 10. Dokumenthistorik

| Version | Dato | Ændringer |
|---|---|---|
| v12-addendum | 2026-09-19 | Claude (Sonnet 5): F-1…F-9 tilføjet. R22/K1/R24/R25/VPEN-2026-013 verificeret rettet i kode og GRC opdateret fra `candidate_review` til valideret status. Live SSH-verifikation af begge fysiske Edges (læs-kun). Pre-merge review af draft-PR #246 (trust/mTLS). |

*Alle linjenumre pr. `main@928134be` medmindre andet angivet. mTLS/trust-fund (§4) refererer draft-PR #246 (`chatgpt/api-mtls-20260917@3375f78c`), ikke `main`.*
