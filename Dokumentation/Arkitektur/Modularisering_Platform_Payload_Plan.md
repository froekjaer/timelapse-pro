# Fra TimeLapse Pro til modulær edge-platform — plan & GitHub-strategi

**Dato:** 2026-07-15 · **Forfatter:** Claude (Cowork) · **Status:** Oplæg til fælles beslutning (Peter + Claude + Codex)
**Bygger på:** `Claude_QA_Arkitektur_Review_2026-07-15.md` §4, `Codex_REVIEW_Claude_Arkitektur_Risk_Test_2026-07-15.md`, `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md`. Diagrammer: `TimeLapse_Arkitektur_og_Dataflow.mermaid.md` + `TimeLapse_Arkitektur.drawio`.

---

## 1. Målet i én sætning

Gør den **non-funktionelle kerne** (identitet, config, opdatering, telemetri, remote access, sikkerhed, HAL, storage) til en **genbrugelig edge-platform** der udvikles i ét spor, mens den **funktionelle del** (i dag: kamera/timelapse) bliver en **udskiftelig payload** der udvikles i et parallelt spor — så nye verticals (vandværk, vindmølle, solcelle) kan bygges oven på præcis den samme, hærdede kerne uden at røre den.

Det centrale snit: **Platform vs. Payload**, koblet gennem én kontrakt (`PayloadDriver` + capability manifest). Se diagram 5 i Mermaid-filen.

---

## 2. Hvad er kerne (genbruges) vs. payload (udskiftes)

| Platform-kerne (non-funktionel, ét spor) | Payload (funktionel, parallelt spor) |
|---|---|
| Identitet & enrollment (device-token, HMAC, mTLS) | Sensor-/aktuator-drivere (i dag gphoto2/Nikon) |
| Config- & policy-hierarki (global→customer→site→device) | Domæne-QA (i dag billed-blur/eksponering/WB) |
| Update/OTA (signerede artifacts, rollback, change tickets) | Databehandling/AI (i dag tagging, Ollama/Gemini) |
| Telemetri & observability (SIEM, CMDB, ITIM, heartbeat) | Domæne-datamodel (i dag captures/tags) |
| Remote access (tunnel + JIT/AccessTicket + session recording) | Domæne-UI-flader (i dag billed-galleri, tag-søgning) |
| Sikkerhed & RBAC (auth, MFA, GRC/compliance) | — |
| HAL (orangepi/rpi/jetson/generic) | — |
| Storage/backup | — |

Test: hvis et modul ville se **identisk** ud for et vandværk som for et kamera, er det **platform**. Ser det anderledes ud, er det **payload**.

---

## 3. Kontrakten mellem kerne og payload (Codex' skærpelse indarbejdet)

Et simpelt interface er ikke nok. `PayloadDriver` skal ledsages af et **capability manifest**, så platformen kan køre en ukendt payload sikkert:

```text
PayloadDriver (livscyklus):
  configure(policy)            # modtager signeret config fra platformens hierarki
  tick(now)                    # periodisk arbejde (capture/poll)
  collect_telemetry() -> dict  # standardiseret metrik til SIEM/CMDB
  handle_command(cmd)          # fra remote access, gennem allowlist

Capability manifest (deklareres, håndhæves af platformen):
  - påkrævede hardware-capabilities (kamera / Modbus / GPIO ...)
  - resource quota (CPU, RAM, disk, netdata)
  - fil- & netværks-allowlist (least privilege)
  - service-identitet (egen credential, ikke platformens)
  - health/rollback-kontrakt + versioneret payload-API
  - dataklassifikation (til GDPR/retention: billeder vs. procesdata)
```

Payload leveres som **signeret pakke** (samme trust-model som OTA-artifacts). Platformen loader den bag quota + allowlist — så en fejl i en payload ikke kan kompromittere kernen eller andre payloads.

---

## 4. Repo-strategi: hvordan de to spor lever side om side

Tre realistiske modeller. **Anbefaling: start som monorepo (A), design fra dag 1 så skiftet til B er billigt.**

**A) Monorepo med skarpe pakkegrænser (anbefalet nu)**
Ét repo, men klare mapper/pakker: `platform/`, `payloads/camera/`, `payloads/<ny>/`, `contracts/` (PayloadDriver + manifest-schema). Fordele: nem refaktorering mens grænserne stadig sætter sig, ét sted at teste kontrakten. Parallel udvikling styres via **CODEOWNERS pr. sti** + **path-filtrerede CI-workflows** (se §6).

**B) Platform som versioneret pakke, payloads som separate repos (mål på sigt)**
Platform-kernen publiceres som en **versioneret artefakt** (GitHub Packages / privat PyPI). Hver payload er sit eget repo der afhænger af `edge-platform>=X.Y`. Fordele: hård isolation, uafhængige release-tog, en payload-fejl kan ikke bryde kernen. Skiftet fra A→B er let hvis pakkegrænserne fra A holdes rene.

**C) Hybrid:** platform + `camera`-payload i monorepo (de modnes sammen), nye verticals som separate repos fra fødslen via et **template-repo** (§6).

**Vigtigt uanset model:** kontrakten (`contracts/`) versioneres semantisk (SemVer). Breaking changes i PayloadDriver = major bump = bevidst, koordineret på tværs af begge spor.

---

## 5. Faseinddelt roadmap (additivt — bryder intet undervejs)

**Fase 0 — Beslut & indram (ingen kode).** ADR-001 vedtager platform/payload-snittet, kontrakten og repo-modellen (A). Beslut navngivning: nye platform-tabeller/API bruger neutrale ord ("asset"/"node"), men **eksisterende camera/capture-kontrakter omdøbes IKKE** (additiv-princippet, Codex enig).

**Fase 1 — Indfør kontrakten uden at flytte noget.** Definér `PayloadDriver` + manifest-schema i `contracts/`. Skriv en **adapter** så den nuværende kamera-logik implementerer interfacet *bagom* uden at ændre adfærd. Kontrakttest + `test_lab_tick_state_machine.py` som sikkerhedsnet. (Anledning: oprydningen af `_lab_tick`, jf. R26.)

**Fase 2 — Træk platform ud af monolitten.** Kør P2-01 med snittet router/service/models pr. domæne, men gruppér i `platform/`-moduler: auth/RBAC først (mest sikkerhedskritisk), så config, update, telemetri. Én modul-udtrækning pr. sprint, kontrakttest før flytning, uændrede URL'er.

**Fase 3 — Isolér camera-payloaden.** Flyt kamera/capture/QA/tagging til `payloads/camera/` bag kontrakten. Nu er kernen fri for domæneviden.

**Fase 4 — Bevis modulariteten med én ny vertical.** Byg en minimal `payloads/waterworks/` (fx Modbus-poll af én pumpe) *kun* mod platform-API'et — uden at røre kernen. Det er den egentlige validering af hele øvelsen. Her indløses også "sikker remote access via edgen til backendsystemer": fjernadgang til OT-nettet sker gennem platformens tunnel + JIT/AccessTicket, aldrig ved at åbne porte.

**Fase 5 — Federation (når der er >1 prod-headend/kunde).** Trust root, release-promotion på tværs af headends, tenant ownership, central vs. lokal CMDB, revocation, SBOM/VEX-distribution (Codex' punkt).

---

## 6. Kan GitHub hjælpe? Ja — konkret mapping

GitHub understøtter præcis den parallelle to-spors-model:

| Behov | GitHub-feature |
|---|---|
| **Parallelt ejerskab** (kerne-team vs. payload-team, menneske+AI) | `CODEOWNERS` pr. sti → automatiske review-krav; separate PR-godkendere for `platform/` vs. `payloads/` |
| **Uafhængige pipelines** (spor kører ikke i vejen for hinanden) | **Path-filtered workflows** (`on: push: paths:`) → kerne-CI og payload-CI trigges kun af relevante ændringer |
| **Genbrugelig CI/release på tværs af payloads** | **Reusable workflows** (`workflow_call`) — platformen definerer én kanonisk CI/release-workflow som hver payload kalder |
| **Versioneret kerne som afhængighed** (repo-model B) | **GitHub Packages** (privat registry) — publicér `edge-platform` som versioneret pakke; payloads pinner `>=X.Y` |
| **Ny vertical hurtigt & ensartet** | **Template repository** — et `payload-template` med kontrakt-stub, CI, manifest-skabelon; "Use this template" → nyt vertical-repo |
| **Miljøer (rd/staging/prod) + agent-lockout** | **GitHub Environments** med protection rules + required reviewers → maps til jeres 3-maskiners topologi; hemmeligheder pr. miljø; prod bag manuel godkendelse |
| **Uafhængige release-tog** | **Release Please / semantic-release** pr. modul → separate versioner for platform og hver payload |
| **CRA/sikkerheds-posture pr. modul** | **Dependabot** (afhængigheder), **CodeQL** (SAST), **SBOM-eksport** (Actions), branch protection + required checks (jeres unit-gate + arch-ratchet) |
| **De to spor synligt styret** | **Projects** (board pr. spor) + **milestones** + issue-labels `area:platform` / `area:payload` |
| **Signerede payload-pakker (§3)** | **Actions OIDC + cosign/GPG** → signér artefakter i release-workflow, verificér ved OTA (samme trust-model som i dag) |

**Konkret første GitHub-skridt (lavt niveau, høj værdi):**
1. Tilføj `CODEOWNERS` med `platform/` og `payloads/` (selv i nuværende struktur — sæt stierne op nu).
2. Split CI i path-filtrerede jobs (I har allerede unit-gate + arch-ratchet at bygge på).
3. Opret et `ADR/`-katalog og en PR-skabelon der kræver ADR-reference ved arkitekturændringer.

---

## 7. Risici & vagtskel (så modularisering ikke bliver et sidespor)

- **Scope-disciplin (Codex' punkt 4):** den generiske platform må ikke forsinke TimeLapse Pro production-readiness. Fase 1-3 er *også* teknisk gæld-nedbrydning (P2-01) — de betaler sig selv hjem uanset verticals. Fase 4-5 er først relevante når en konkret ny kunde/vertical er på bordet.
- **Ingen big-bang rewrite.** Alt additivt, kontrakttest før hver flytning, uændrede URL'er, additiv DB.
- **Kontrakten er det dyre at ændre.** Invester i `contracts/` + manifest-schema tidligt; SemVer-disciplin.
- **Sikkerhed følger med, ikke bagefter.** Capability manifest = least privilege fra dag 1; remote access til nye OT-verticals SKAL gå gennem platformens JIT-model (R19/break-glass), aldrig direkte portåbning.

---

## 8. Anbefalede næste 3 handlinger

1. **ADR-001** (Peter + Claude + Codex): vedtag platform/payload-snit, `PayloadDriver`+manifest, repo-model A. Én side.
2. **CODEOWNERS + path-filtered CI** i nuværende repo (GitHub-skridt 1-2 ovenfor) — koster timer, sætter sporene op.
3. **Fase 1 spike:** definér `contracts/PayloadDriver` og wrap den nuværende kamera-logik bag den, dækket af eksisterende LAB-tick-test. Bevis at kontrakten passer på det vi har, før vi flytter noget.
