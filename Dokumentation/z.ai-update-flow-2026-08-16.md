# z.ai — Gennemgang af update-flowet: edge → headend → deploy (2026-08-16)

**Udført af:** z.ai (GLM-5.3), uafhængig session — opfølgning på `z.ai-2026-08-15.md`.
**Omfang:** Hele update-flowet: (1) edge-agentens hentning/installation af updates fra headend,
(2) headend som update-authority (godkendelse, artifacts, policy, rapportering, promotion), (3)
headend-egen deployment (CI). Fokus: *virker det, og er det overskueligt og brugervenligt?*
**Kodebase:** `main @ 412eddce` (alle fil:linje-verificerede fund er eftertjekket på denne commit;
ikke-genverificerede detaljer fra traces kan afvige få linjer).
**Metode:** Dokumentation (`Update_Flow_v10.md`) læst som tiltænkt design → fuld kode-trace af
edge (`agent.py`, `security.py`, `headend_client.py`, deploy-scripts) og headend (`main.py`
updates-sektion, `update_supersession.py`, `reconcile_updates.py`, CI/deploy-scripts) via to
parallelle gennemgange → **egen efterverifikation af alle topfund** → UI-gennemgang
(`UpdatesPage.tsx`). Severity: kritisk/høj/mellem/lav som i hovedreviewet.

---

## 0. Executive konklusion

**Kerneflowet virker og er E2E-verificeret** (QA 2026-06-21 på aktiv Edge `TL-C87FF9587CA0`,
dokumenteret i `Update_Flow_v10.md`; koden matcher dokumentationen for app-artifact-pathen).
Pull-modellen, pr.-fil SHA-256, path-restriktioner, OS offline-bundle-gates og promotion-disiplinen
er reelt implementeret. UI'en er velbygget og brugervenlig.

**Men:** der er fire fund, der kan slå igennem i drift (H-1, H-2, H-3, E-3/E-4), én kendt
arkitekturgæld der nu er præcist afgrænset (E-1 signatur), og headend-egen deploy mangler den
robusthed (migrering, rollback, health-gate), som systemets øvrige flows faktisk har.
Dokumentationen overdriver sikkerhedsniveauet to steder ("signeret artifact", "backup af
eksisterende Edge").

**Kort svar på "virker det?":** Ja for den testede path (`app_updates`, scope=device, lab).
Nej, ikke for alle dokumenterede update-typer og scopes — se E-2 og H-2/H-3, som betyder at
hhv. flere update-typer installeres uden verifikation, og customer/site-rollouts aldrig
når frem til enhederne.

---

## 1. Det faktiske flow (som implementeret)

### 1.1 Edge-app-update (primær mekanisme — virker)

```
PendingUpdate opstår (4 veje, se 1.3) → artifact registreres+signeres → change ticket →
admin/compliance godkender i UI →
Edge poller GET /api/updates/policy/{device_id} (hvert 5. min, agent.py:1220) →
  trust-gate (verify_update_artifact, security.py:110) →
  pre-update backup (config/DB/units) + upload til headend →
  download pr. fil fra /api/updates/artifacts/{id}/files/{path} →
  SHA-256 pr. fil (agent.py:1778-1780) →
  lokal backup af eksisterende filer til /opt/timelapse/prev (agent.py:1786-1798) →
  installér kun paths der starter med edge/ (agent.py:1725-1728) →
  release-receipt atomisk + readback-gate (agent.py:1890-1905) →
  rapport 'deployed' → systemctl restart timelapse-edge
```

Fejlgrene: exception → unit-rollback + filer genskabt fra `prev` + rapport `rolled_back`
(agent.py:1914-1939). Manglende/utroværdig artifact → `blocked` (ikke `rolled_back`) — matcher doc.

### 1.2 Headend-egen deployment

CI (`.github/workflows/ci.yml:94-157`): GPG-verificér nyeste tag → `git checkout --detach` +
`reset --hard` → `launchctl kickstart -k` (hård genstart af headend) → `npm install && npm run
build` **efter** restart. Brew-platformskomponenter (nginx/postgres/ollama/…) har et separat,
governance-ordnet flow (`_run_headend_platform_update`, main.py:6016-6170) med preflight, backup,
postflight og rollback. Førstegangsinstallation: `deploy/install/install_headend.sh`.

### 1.3 Sådan opstår en PendingUpdate — fire veje (dokumenteret som én)

1. **Manuel CLI-reconcile** (`headend/tools/reconcile_updates.py:73-195`): kræver `DATABASE_URL`
   mod drift-DB + lab-katalog-JSON; `--create` opretter pending OS-updates.
2. **Edge "available"-hints** (main.py:10562-10649): app-kandidater pr. device (environment
   default "production").
3. **Git-tag-poller** (main.py:8643-8708, timesplan): GPG-signerede tags → app-kandidater
   (environment "test") for lab/test/rd-enheder + supersession.
4. **Auto-OS-bundle-poller** (main.py:8713-8769, hvert 10. min): bygger OS-bundle automatisk til
   pending OS-updates uden artifact (signeres med første super_admin som bruger).

`Update_Flow_v10.md` beskriver kun vej 1. Det er den væsentligste overskuelighedsafvigelse
mellem dokumentation og kode — ikke en fejl i sig selv, men operatøren møder updates i UI'en,
der er opstået ad stier, manualen ikke nævner.

---

## 2. Hvad der er verificeret som virkende

- **Pull-modellen**: Edge henter selv, én update ad gangen (`agent.py:1642-1660` returnerer efter
  første håndterede update). Ingen push til edge i den aktive sti (legacy signalering er
  env-deaktiveret: `headend/deploy/signal_edge_update.py:4-10`).
- **Pr.-fil SHA-256** verificeret på edge (agent.py:1778-1780) **og** ved hver download på headend
  (main.py:8364-8366) — dobbelt tjek.
- **Artifact-file-serving med solidt forsvar**: device-auth, binding til approved update for
  netop dette device (`_update_applies_to_device`, main.py:8330-8344 — forhindrer
  cross-customer-download), path-traversal-forsvar (manifest-medlemskab + resolve/parents-tjek,
  main.py:8346-8366).
- **OS-gates**: offline-only `.deb`-bundle kræves (`agent.py:1673-1674`), `--no-download`-krav
  gennemtvunget (agent.py:2015-2047), forbidden-kommando-scanning af bundle (main.py:7098-7133).
- **Promotion lab→staging→prod**: production kræver `deployed` kilde-evidens; prod-kandidat
  oprettes som `pending` (installerer ikke noget) med idempotent genbrug (main.py:10285-10357) —
  UI-knappen gør præcis, hvad manualen lover.
- **Multi-target rollup (HLTH-008)**: global status flippes først, når alle targets har
  rapporteret terminal status; blandet udfald → `rolled_back` (main.py:10509-10551). Har tests
  (`test_report_update_rollup.py`).
- **Dokumentationens restpunkt 5 er rettet**: `deployed_count` inkrementeres nu for single-scope
  og recounts for multi-scope (main.py:10472-10477, 10543-10544); test dokumenterer selv
  "var tidligere fastfrosset på 0 (bug, nu rettet)". `Update_Flow_v10.md` bør opdateres.
- **Auth-struktur**: alle operatør-endpoints bag `require_role("super_admin","admin")`;
  policy/report/artifact-files bag device-token (også body-binding mod credential-manipulation,
  main.py:10450-10451). Route-auth-sweep-test fail-closed-tvinger dækning.

---

## 3. Fund — edge-siden

| ID | Fund | Sted | Alvor |
|---|---|---|---|
| **E-1** | **Signatur verificeres ikke kryptografisk.** `verify_update_artifact` tjekker kun at `signature`-feltet er ikke-tomt (security.py:142). `signed_by=system-hash` er en SHA-256-binding af manifestets canonical JSON **uden hemmelighed** (`_sign_payload`, main.py:6638-6669 — docstring selv: "nyttig i LAB men ikke en kryptografisk signatur"), og headend tildeler system-hash-artifacts sit eget fingerprint i policy (main.py:6935-6938). Reelt trust-anker er config-kanalen (TLS + Bearer/HMAC), ikke en uafhængig signatur — dvs. en kompromitteret headend kan levere vilkårlig kode til alle edges. Manifest-SHA (`hmac.compare_digest`, security.py:132), pr.-fil-hash og tom trusted-liste fejler lukket (security.py:139-140) afbøder transport-fejl, men ikke headend-kompromis. Blev påpeget i `z.ai-2026-08-15.md` (SEC-ZAI-10) — **bekræftet uændret på main@412eddce**. | security.py:110-145 | **Kritisk** (misbrugskræver headend-kompromis; eskalerer ved Internet-eksponering) |
| **E-2** | **Trust-gate dækker ikke alle update-typer.** Gate-mængden i security.py:119 er `{app_security, app_updates, app_update, timelapse_update, timelapse_pro_update, os_security, os_updates}` — de kanoniske `timelapse_updates`, `timelapse_security`, `application_security`, `application_updates`, `timelapse_pro_security`, `dependency_*`, `third_party_*` falder igennem som `"non-code update"` uden manifest-/signer-/signaturtjek, mens filerne stadig installeres som kode af `_run_artifact_app_update`. Headend kræver artifact for langt flere typer (main.py:7031-7050). QA-pathen (`app_updates`) er dækket; UI-promotion-typerne er det ikke. **Selv verificeret på main.** | security.py:119-120 | **Høj** |
| **E-3** | **Rollback-kilden ødelægges ved genkørsel.** Hvis en installation afbrydes (strømudfald midt i copy-løkken), står update'en stadig `approved` (progress-rapporter flipper ikke status), og agenten genkører hele flowet efter reboot — men sletter først `prev` og tager derefter backup af den **delvist opdaterede** tilstand (agent.py:1786-1787). Den originale rollback-kilde går tabt netop i det scenarie, hvor den behøves. **Selv verificeret på main (linje 1787).** | agent.py:1786-1787 | **Høj** |
| **E-4** | **Ingen postflight health-tjek efter genstart.** Efter `deployed` + `systemctl restart` (agent.py ~1910) tjekkes ikke om agenten kommer op. Krascher ny kode ved opstart: systemd giver op efter 5 genstarts­forsøg (timelapse-edge.service:27-29) → død edge; `watchdog.sh` genstarter ikke kode. Ironisk nok har **legacy**-scriptet `deploy/edge_update.sh:70-84` netop denne beskyttelse (30 s health-check + `git checkout`-rollback) — mønstret findes, det er bare ikke portet til artifact-flowet. | agent.py:~1908-1910 | **Høj** |
| E-5 | Installation er ikke-atomisk pr. fil (copy-løkke, agent.py:1801-1806; kun receipt-skrivning er atomisk). OS-update har ingen pakke-rollback — fejl under `dpkg -i` efterlader delvist installerede pakker og rapporteres `blocked` (agent.py:2084-2086; matcher doc appendiks D, men "rollback" eksisterer ikke for OS). | agent.py:1801-1806, 2084 | Mellem |
| E-6 | **systemd-run-sandbox reelt deaktiveret**: `ProtectSystem=false`, `NoNewPrivileges=false`, `PrivateTmp=false`, `ReadWritePaths=/` (agent.py:2060 ff.). Dokumentation/navn antyder isolation; koden åbner alt. OS-runner-kommandoen er desuden vilkårlig shell fra manifestet (`bash -lc "dpkg -i … || apt-get --no-download -f install"`), hvor edge kun validerer tokens, ikke shell-semantik. | agent.py:2058-2066 | Mellem |
| E-7 | **Backup-upload uden retry**: `upload_edge_backup` bruger plain session uden retry-adapter (headend_client.py:503-515). Transient netværksfejl → `pre_update_backup_upload_failed` → hele update'en terminalt `rolled_back` (agent.py:1761-1762) uden auto-retry, selvom intet var installeret. | headend_client.py:503-515 | Mellem |
| E-8 | Forbidden-kommando-scanning kan omgås: linje-ankeret regex (agent.py:1998-2001) fanger ikke `cd x && curl`, variabler, base64; scanner kun udvalgte filtyper (2004). `--no-download`-kravet er derimod solidt. | agent.py:1995-2017 | Mellem |
| E-9 | `_run_rollback` (force-rollback) genstarter ikke servicen og fjerner ikke filer, der ikke fandtes i `prev` (agent.py:2093-2107) — kører videre på gammel in-memory kode til næste naturlige genstart. | agent.py:2093-2107 | Mellem |
| E-10 | Legacy git-update (to stier: `_check_update` agent.py:1563-1624 + `deploy/edge_update.sh` via agent.py:1690-1696) beskyttes **kun** af env-flags — `_check_update` tjekker ikke `TIMELAPSE_ENV` (i modsætning til `_run_update`-stien, agent.py:1680-1684). Prod beskyttes alene af flag-defaults. | agent.py:1563-1624, 1680-1684 | Lav-mellem |
| E-11 | Update-poll er nøglet ind under config-pull-blokken (agent.py:795-800): hæves config-intervallet, throttles update-polllingen ulogisk. Heartbeat-stien (2141-2142) omgår intervallet — to forskellige poll-triggere. | agent.py:795-800, 2141-2142 | Lav |
| E-12 | `queued`-status emitieres aldrig af edge (headend opretter target som pending/queued selv); doc-statuslisten gør den til edge-progress. Download i hukommelsen, 30 s timeout, ingen resume for store bundles (headend_client.py:608-629). | headend_client.py:608-629 | Lav |

---

## 4. Fund — headend som update-authority

| ID | Fund | Sted | Alvor |
|---|---|---|---|
| **H-1** | **`report` verificerer ikke at enheden er target for update'en.** `report_update` (main.py:10439) binder device_id til dets credential og slår update op — men tjekker **ikke** at deviceet indgår i `_resolve_update_targets`/`target_device_ids`. Enhver autentificeret edge kan rapportere `deployed`/`rolled_back` for en vilkårlig update: for scope=device flipper det hele update'ens status (main.py:10468-10477), og der oprettes falske `UpdateTarget`-rækker. "Edge rapporterer falsk deployed" er ikke dækket af tests. **Selv verificeret på main (10439 ff., intet target-tjek før single_target_scope-grenerne).** | main.py:10439-10496 | **Høj** |
| **H-2** | **Customer/site-scoped updates leveres aldrig til edge.** Policy-filteret er `or_(scope=="global", scope_id==device_id)` (main.py:10404) — for scope=customer/site er scope_id et kunde-/site-ID og matcher aldrig et device_id. Approve, target-oprettelse og artifact-download-auth understøtter alle disse scopes (main.py:9940-9944, 9540-9543, 6240-6243) — dvs. et godkendt site-rollout står permanent i "Afventer Edge policy-pull" (flow-status:9601) **uden nogen fejlmeddelelse**. **Selv verificeret på main (linje 10404).** | main.py:10402-10405 | **Høj** |
| **H-3** | **Intet environment-filter i policy** (main.py:10402-10412): en godkendt lab/test-update leveres til alle scope-matchende devices, også produktion. Approve default'er desuden environment til "production", hvis payload udelader det (main.py:9939) — en lab-update kan blive markeret production ved et uheld. **Selv verificeret på main.** | main.py:10402-10412, 9939 | **Høj** |
| H-4 | **GET /policy har skrivevirkninger**: edge-poll auto-approver matchende pending kandidater (opretter system change tickets, main.py:10390-10397) og flipper permanent approved→blocked + muterer description for updates uden artifact (10419-10424, med `db.commit()` i GET-pathen). Governance-beslutninger som side-effekt af enhedstrafik — ikke-atomær og svær at auditere korrekt. | main.py:10390-10424 | Mellem |
| H-5 | `target_device_ids` kan overstyre scope med N devices (main.py:9535-9537), men `single_target_scope` tester kun scope=="device" (10467) — første devices terminalrapport flipper hele multi-device-rolloutet. Præcis den risiko, HLTH-008-rollupen ellers beskytter mod. | main.py:10467 vs 9535-9537 | Mellem |
| H-6 | Supersession dækker kun pending `app_updates`, scope=device, environment=test fra tag-poller-flowet (update_supersession.py:7-13; kaldes kun fra main.py:8493). Edge-hint-kandidater (default production, main.py:10635-10645) supersederes aldrig → stabel af forældede "N commits bagud"-updates i Afventer-køen. | update_supersession.py | Lav |
| H-7 | CI deploy-verificerer det **nyeste** GPG-tag, ikke om den deployede SHA er tag-covered (ci.yml:122-127) — et signeret gammelt tag + usigneret ny push deployer stadig. | ci.yml:122-127 | Lav-mellem |
| H-8 | Test-dækning: rollup/scopes/SBOM/re-signering er dækket; `tests/test_update_supersession.py:8-16` stubber Query.filter (filterlogik uverificeret); `headend/tools/test_update_flow.sh` er en køreplan, ikke en test — og dokumenterer **manuel SQL INSERT mod pending_updates som officiel metode** (trin 6) udenfor al governance. Mangler: E2E policy→download→report, negative tests (fremmed device-rapport, traversal-forsøg), OS-bundle E2E. | tests/, tools/ | Lav-mellem |

---

## 5. Fund — headend EGEN deploy

| ID | Fund | Alvor |
|---|---|---|
| **D-1** | **CI-deploy uden rollback, uden migreringer, med nedetid**: `launchctl kickstart -k` = hård genstart (kort nedetid); UI-build køres **efter** restart, så ny backend serverer gammel UI-dist i et vindue (index.html↔assets-hash-mismatch-risiko, jf. den kendte "internal redirection cycle"-fejl i 00_START_HER); ingen health-verifikation efter deploy; ingen rollback-vej ud over manuel `git reset` + kickstart. `headend/migrations/*.sql` (30 filer) køres **ingen steder automatisk** (hverken CI, install-script eller app-start — app-start kører `create_tables()` + inline additive ALTERs med try/except, main.py:358-582). Den eneste automatiserede headend-rollback i repoet ligger i det **deaktiverede** `deploy/headend_poller.sh:46-51`. | **Mellem-høj** |
| D-2 | To divergerende launchd-plists: `deploy/launchd/dk.froekjaer.timelapse-headend.plist` (uvicorn direkte, WorkingDirectory `~/projects/...`) vs `deploy/launchd/macos/...` (start-script med port-guard, WorkingDirectory `/Volumes/data-fast/...`). CI deployer til `~/projects` (ci.yml:102) — hvis macos-varianten er den installerede, deployer CI til et andet katalog end det kørende. | Mellem |
| D-3 | Kontrast-observation: **brew-platformsflowet er et mønstereksempel** (`_run_headend_platform_update`, main.py:6016-6170): allowlist, environment-gate (test installerer, production kræver deployed test-evidens), preflight, pre-update backup, postflight, launch-agent-rollback ved fejl. App-kode-deployet bør arve netop denne disciplin — byggeblokkene findes allerede i kodebasen. | Observation |

---

## 6. Overskuelighed og brugervenlighed

### UI (`timelapse-ui/src/pages/UpdatesPage.tsx`, 1.867 linjer) — overraskende stærk

- ✅ Dansk statussprog overalt (`Afventer`, `Godkendt`, `Blokeret`, `Erstattet`…), filtre der
  matcher statusmodellen (7 + Alle, default `Afventer`).
- ✅ Udfoldelige rækker med **flow-tidslinje** pr. update (Godkendt → Afventer Edge poll →
  Download/Verify/Install → Deployet) og per-target-status med `attempt_count`/`last_error`.
- ✅ **Tooltips på alle handlinger** der forklarer konsekvens ("Afvis opdateringen. Den
  distribueres ikke…", "Opret en staging-promotion. Installeres først efter
  staging-godkendelse.") — sjældent set så gjort ordentligt.
- ✅ `DeviceUpdateMatrix`: enheder × update-kategorier med risiko-score og versionsgab — giver
  operatøren ét overblik.
- ✅ "Afventer Edge"-diagnostik (`waiting_for`: edge_policy_pull, lab_os_bundle,
  artifact_or_lab_evidens, cmdb_device_record) matcher fejlsøgningslisten i manualen.
- ⚠️ Mindre: OS-bundle-registrering exponerer rå kommando-JSON (`[{"name":"offline dpkg
  install","argv":[…]}]`) som editérbart felt — fint til lab, for teknisk til normal drift;
  artifact-bind kræver manuelt artifact-ID (dropdown over kataloget ville være lettere).

### Dokumentation og kompleksitet — blandet

- ➖ **Fire måder en update opstår på** (CLI, edge-hint, tag-poller, auto-OS-poller) mod ét
  dokumenteret — operatøren kan ikke altid forklare, hvor en "Afventer"-række kommer fra.
- ➖ **Fire kode-distributionsmekanismer på edge** (artifact-app, artifact-OS, legacy git-pull i
  agenten, legacy shell-script) + **tre headend-deploy-mekanismer** (CI-git, brew-governance,
  deaktiveret systemd-poller). Legacy-stierne er env-flagget af — men de lever, dobbelt-dækker
  hinanden (to git-stier alene i agent.py) og forvirrer vedligeholdelse. Konvergensplanens
  feature-freeze-princip er det rigtige værktøj her: slet/arkivér legacy-stierne.
- ➖ OS-update-operatørbyrde: CLI med direkte `DATABASE_URL` mod drift-DB + evt. Docker-byg —
  tungt sammenlignet med app-flowets 3-4 klik.
- ➕ `Update_Flow_v10.md` er ellers velskrevet: status-tabel, fejlsøgning med konkrete SQL/ssh/
  journalctl-kommandoer, promotion-forklaring der matcher koden.

**Brugervenlighedskonklusion:** For den normale app-update er flowet **overskueligt og
brugervenligt** — 3-4 UI-handlinger når artifact først findes, og UI'en guider godt. OS-flowet og
forklaringen på *hvor updates kommer fra* er de to svage punkter.

---

## 7. Anbefalinger (rækkefølge efter risiko/indsats)

1. **H-1** — verificér device ∈ targets i `report_update` (få linier, genbrug
   `_update_applies_to_device`). Lukker forfalsket status-rapportering.
2. **H-2 + H-3** — udvid policy-filteret til at løse customer/site-scope (device → site →
   customer) og filtrér på environment (device-env fra CMDB). Ellers virker site-rollout *aldrig*
   — og lab-updates kan nå prod.
3. **E-3 + E-4** — beskyt `prev` (versionér pr. update-id: `prev/{update_id}/` i stedet for
   rmtree) + postflight health-check efter genstart med automatisk rollback fra `prev` (port
   mønstret fra `edge_update.sh:70-84`).
4. **E-2** — harmonisér update-type-mængden mellem `security.py:119` og headends
   artifact-krav-mængde (én delt konstant/kilde).
5. **E-1** — kryptografisk signaturverifikation på edge (allerede top-anbefaling i
   `z.ai-2026-08-15.md` SEC-ZAI-10; GPG-nøglen findes allerede i deploy-setuppet —
   `TIMELAPSE_GPG_KEY` i launchd-plisten). Efter H-1..E-2 er dette den største tilbageværende
   trust-lift.
6. **D-1** — CI-deploy: kør pending `migrations/*.sql` som eksplicit trin (fail-closed), byg UI
   *før* restart, health-gate efter restart (`/api/health`), dokumentér rollback. Genovervej
   D-2 (to plists) i samme omgang.
7. **H-4/H-5/E-7** — flyt auto-approve/blocked-flip ud af GET-policy-pathen (eksplicit job eller
   approve-tid), brug `_resolve_update_targets`-antal i single_target_scope, retry-adapter på
   backup-upload.
8. **Oprydning** — fjern/arkivér `deploy/edge_update.sh`-kald fra agenten, `headend_poller.sh`,
   `signal_edge_update.py`, `timelapse-deploy.service/.timer` (Linux-only på Mac-drift) og den
   anden git-sti; opdatér `Update_Flow_v10.md` (deployed_count rettet; fire opståelsesveje;
   `superseded`/`blocked` i statusmodellen; signatur-niveauet af `system-hash` ærligt beskrevet).

---

## 8. Samlet vurdering

| Spørgsmål | Svar |
|---|---|
| Virker app-artifact-update E2E? | **Ja** — verificeret i QA og koden matcher for denne path. |
| Virker det for alle dokumenterede typer/scopes? | **Nej** — E-2 (typer uden verifikation), H-2 (site/customer når aldrig frem), H-3 (environment-læk). |
| Kan man stole på status i UI? | **Næsten** — H-1 tillader falske rapporter; H-4 gør governance-hændelser svære at følge. |
| Er rollback sikret? | **Delvist** — `prev`-rollback virker ved *håndteret* fejl, men E-3 (genkørsel) og E-4 (ingen postflight) efterlader de værste scenarier uden sikkerhedsnet. |
| Er headend-egen deploy robust? | **Nej** — D-1 (nedetid, ingen migrering, ingen rollback). Brew-flowet viser, hvordan det bør se ud. |
| Er det overskueligt/brugervenligt? | **Ja for normal app-update** (UI'en er velbygget). **Nej** i periferien: fire opståelsesveje, fire edge-mekanismer, tre headend-mekanismer, to plists. |

Flowet er tættere på "driftssikkert" end hovedreviewet fra 2026-08-15 antog — men de fire
hurtige rettelser (H-1, H-2, H-3, E-3/E-4) bør lande, før updates stole på i andet end lab.

---

## Bilag — Metode og begrænsninger

- **Kilder:** `Update_Flow_v10.md` (design), fuld trace af `edge/agent.py` (update-sektionen
  ~1563-2107), `edge/security.py`, `edge/upload/headend_client.py`, `deploy/edge_update.sh`,
  `edge/scripts/*`; `headend/main.py` updates-sektion (~5500-10650: policy/report/approve/
  promote/artifacts/tickets/pollers), `services/update_supersession.py`,
  `tools/reconcile_updates.py`, `tools/test_update_flow.sh`; `.github/workflows/ci.yml`,
  `deploy/launchd/`, `deploy/install/install_headend.sh`; `timelapse-ui/src/pages/UpdatesPage.tsx`;
  tests (`test_update_lifecycle.py`, `test_report_update_rollup.py`,
  `test_update_supersession.py`, `test_change_ticket_sbom.py`, `test_route_auth_coverage.py`).
- **Verificering:** E-1, E-2, E-3, H-1, H-2, H-3 + deployed_count-fix er efterverificeret direkte
  på `main @ 412eddce` af hovedsessionen. Øvrige fund er trace-verificerede med angivne
  kildehenvisninger (Medium-high confidence).
- **Ikke omfattet:** dynamisk kørsel (ingen kode eksekveret), OS-bundle E2E på fysisk enhed,
  brew-flowets reelle kørsel på Mac-mini, CI-runner-konfiguration, git-historik.
- **Krydsreferencer:** `z.ai-2026-08-15.md` (hovedreview; SEC-ZAI-10 = E-1 her),
  `TIMELAPSE_PRO_RELEASE_CONVERGENCE_PLAN_2026-08.md` (WP-1/WP-4 berøres af E-1, D-1),
  `Update_Flow_v10.md` (dokumentation der bør opdateres — se anbefaling 8).
