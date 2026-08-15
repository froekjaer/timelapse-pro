# Claude — Gennemgang af opdateringsflowet (Edge + Headend) (2026-08-16)

**Forfatter:** Claude (Sonnet 5), på opdrag fra Peter
**Dato:** 2026-08-16
**Scope:** Hele opdateringsflowet — fra headend-orkestrering (bundle-bygning, godkendelse, distribution), over edge-agentens installationslogik, til headends egen deployment-pipeline (Mac mini) og operatør-UI'en (`UpdatesPage.tsx`).
**Metode:** Fire parallelle, uafhængige kodegennemgange (headend-orkestrering, edge-installation, headend-deployment, UI/UX), synteseret til én vurdering.

**Provenance-note (jf. TRUST.md/EVIDENCE_MODEL.md):** AI-genereret evidens, ikke en autoritativ konklusion. Skal efterprøves af et menneske før den lægges til grund for beslutninger. Bygger videre på [Claude-2026-08-15.md](Claude-2026-08-15.md) og anvender samme metode (kode-mod-påstand-verifikation).

---

## Kort svar

**Virker det?** Mekanisk ja — pipelinen (byg bundle → signér manifest → edge henter kun egne autoriserede filer → hash-verificeres to gange → installeres → rapporteres tilbage) er reelt implementeret, ikke kun dokumenteret. Men ét fund ændrer risikobilledet væsentligt: der er ingen reel kryptografisk signaturverifikation på edge.

**Er det overskueligt?** Nej, ikke helt — der er reelt to konkurrerende stier ind i OS-update-systemet med modsatrettede tillidsmodeller, og tre overlappende statusordforråd i UI'en.

**Er det brugervenligt?** Grunddesignet og tooltip-teksten er god, men den mindst friktionsfyldte handling ("Godkend") er også den med størst konsekvens ("Alle enheder"), uden ekstra advarsel.

---

## 1. Kritisk fund: signaturverifikation på edge er ikke reel

Distributionsmodellens navn (`headend_signed_offline_os_bundle_edge_pull`) og kode-kommentarer antyder signerede bundles. Men `verify_update_artifact()` (`edge/security.py:110-154`) gør reelt tre ting:

1. Genberegner SHA-256 af manifestet og sammenligner med det manifestet selv hævder — **selv-konsistens, ikke ægthed** (en angriber der leverer et manifest kan trivielt beregne sin egen hash).
2. Tjekker at `signer_fingerprint` er en streng på en tillidsliste — **strengmatch, ikke signaturverifikation.**
3. Tjekker at `signature`-feltet blot **ikke er tomt** (`security.py:142-143`) — bytes verificeres aldrig mod en offentlig nøgle noget sted i `edge/`.

Docstringen erkender det selv (`security.py:110-117`): *"It does not yet perform OpenPGP verification on the Edge."* Både artefaktet og listen over "trusted" fingerprints kommer over samme TLS-forbindelse fra samme headend — det er derfor ikke forsvar-i-dybden mod en kompromitteret headend-konto, kun en garanti for at et device ikke fodres med et artefakt hvis manifest ikke matcher sit eget indhold.

**Praktisk konsekvens:** OS-opdateringer installeres via `systemd-run` med fuld root (`ProtectSystem=false`, `ReadWritePaths=/`, `edge/agent.py:2059-2066`) — kun begrænset af en denylist-regex mod exfiltrations-mønstre (curl/wget/git clone/pip install), ikke af nogen reel sandkasse.

## 2. Governance-bypass: den tiltænkte, gennemgåede sti bliver reelt ikke brugt

To måder en OS-opdatering kan opstå på, med modsat tillidsmodel — begge indført i samme commit (`b3666709`, 2026-06-14):

| Sti | Hvordan | Lab-review før build? |
|---|---|---|
| `headend/cmdb.py:369-426` (`_sync_edge_os_updates`) | Edge'ens eget selvrapporterede apt-package-liste opretter direkte en `pending`-update | **Nej** |
| `headend/main.py` (`os_security_ignored_cmdb_catalog_required`) | Kræver manuelt admin-trigger (`os-catalog/refresh-from-builder`/`import-apt-list`), opretter `blocked`-update | Ja (tiltænkt) |

Auto-byg-poller'en (`_os_bundle_auto_poller_loop`, hver 10. min, `main.py:622-634,8713-8794`) — som reelt løser den gamle "bundle bliver aldrig bygget"-fejl (E-01) — filtrerer strengt på `status="pending"`, og finder derfor **kun** arbejde fra den uverificerede sti. Den lab-gatede, dokumenterede sti er reelt dødt kode i praksis, medmindre nogen manuelt trigger den.

Med standardpolitikken `os_security=auto` (`main.py:6954-6965`) betyder det: edge rapporterer en pakke → headend bygger en bundle direkte fra et live Ubuntu-mirror via `fetch_os_bundle.py` (med `strict_versions=False`, så en anden mirror-version end den rapporterede accepteres stille, `fetch_os_bundle.py:469-476`) → godkendes automatisk ved næste edge-poll (`_auto_approve_update_for_target`, `main.py:7156-7204`) → installeres — **uden nogen menneskelig gennemgang**, på trods af at resten af kodebasen insisterer på ("Edge må ikke installere via direkte internet/GitHub/apt") at OS-opdateringer kræver lab-verificering.

## 3. Status på kendte issues (ISSUES.md E-01/E-02, juni 2026)

| ID | Status | Bevis |
|---|---|---|
| E-01 "build_os_bundle.py køres aldrig" | 🟡 Delvist løst | Auto-poller virker reelt — men kun for den uverificerede sti (§2), ikke den tiltænkte lab-gatede sti |
| E-02 "hele flowet er ikke testet ende-til-ende" | 🔴 Stadig åbent | `tests/test_os_offline_update.py` tjekker kun at scripts *findes* og indeholder bestemte strenge (fx `"gpg" in content.lower()`) — ingen test kører den faktiske kæde byg → signér → download → verificér → installér → rapportér |

## 4. Rollback er asymmetrisk og delvist ufuldstændig

- **App-opdatering** (`_run_artifact_app_update`, `agent.py:1715`): rollback (`_run_rollback`, `agent.py:2093-2107`) gendanner filer på disk, men **genstarter aldrig servicen** — den kørende proces bliver ved med at eksekvere den dårlige kode i hukommelsen indtil næste crash/reboot.
- **OS-opdatering** (`_run_artifact_os_update`, `agent.py:1946`): hvis installationen fejler, tages der en backup, men den bruges **aldrig** til at gendanne — kun log + status `blocked` (except-blok `agent.py:2084-2086`).
- Systemd-unit-backups slettes i en `finally`-blok uanset udfald (`agent.py:1940-1944`) — en rollback bedt om *efter* opdateringen er "færdig" har intet at gendanne fra.
- Lille, ikke-testdækket race condition i multi-target rollout-status (`main.py:10522-10551`, ingen row lock): to devices der rapporterer terminal status næsten samtidigt kan i sjældne tilfælde begge se en forældet snapshot og aldrig trigge status-flippet — en mindre variant af den allerede fixede HLTH-008-fejlklasse.

## 5. Headends egen deployment

- CI, build og produktion kører på **samme Mac mini** (self-hosted GitHub Actions runner er selve produktionsmaskinen) — ingen redundans.
- `deploy-macmini`-jobbet (`.github/workflows/ci.yml:141-146`) tjekker restart-status med et grep på `launchctl print`-output, men **fejler ikke synligt** hvis genstarten reelt går galt — intet automatisk health-check, intet automatisk rollback.
- UI'en genbygges *efter* backend-genstart (`ci.yml:147-152`) — kort vindue med version-mismatch mellem frontend og backend.
- GPG-tag-verifikation (`ci.yml:118-128`) er en blød gate: springes helt over hvis intet tag findes, og verificerer tagget, ikke den deployede commit direkte.
- `deploy/scripts/restore.sh` peger på forældede stier (`/opt/timelapse/...`) og er ifølge `PRIORITIZED_BACKLOG.md` P0-03 ikke produktionsverificeret.
- En separat, langt mere omhyggelig rollback-mekanisme findes (`/api/updates/{id}/headend-deploy*`-ruterne i `main.py:6016-6202`, med preflight-snapshot, backup, postflight-validering og automatisk plist-rollback), men den dækker kun Homebrew-afhængigheder (nginx, postgres, ffmpeg, ollama) på maskinen — **ikke selve applikationskoden.**
- Dødt/forvirrende artefakt: `deploy/launchd/dk.froekjaer.timelapse-headend.plist` (top-level, uden for `macos/`) indeholder plaintext-secrets og er bekræftet ubrugt, men stadig sporet i git.

## 6. UI/UX for operatøren (`UpdatesPage.tsx`)

Grunddesignet er solidt og pull-modellen er korrekt afspejlet; tooltip-teksten er genuint god og på almindeligt, konkret dansk (`UpdatesPage.tsx:767,772,793,1512-1514`). Den gode operatør-guide (`Update_Flow_v10.md`) er velskrevet, men UI'en linker aldrig til den.

Svagheder:
- **"Godkend"** kræver samme ene modal og samme knapstyling uanset scope — at vælge "Alle enheder" (`:1771`) giver ingen ekstra advarsel eller preview af hvor mange devices der rammes (`:1809-1815`).
- **"Afvis"** har ingen bekræftelse overhovedet (`:740-745`).
- Fejlbeskeder viser ofte rå backend-koder (`missing_headend_signed_artifact`, `sha256 mismatch`) eller rå `stderr_tail`/`stdout_tail` (`:863-868`), selvom gode danske forklaringer allerede findes i `Update_Flow_v10.md` — de er ikke koblet ind i UI'en.
- Tre overlappende statusordforråd (overordnet update-status, per-device target-status, CMDB-matrix-state) som ligner hinanden men ikke er identiske.
- `DeviceUpdateMatrix` linker ikke til den specifikke update-række — operatøren skal matche ID'er visuelt (`:960-965`).
- `/api/updates/auto-deploy/evaluate` (auto-godkendelsespolitikken) har ingen synlig kontrolflade i UI'en overhovedet.
- Et par timeout/dead-end-tilstande: `headendDeploy()` poller i op til 6 minutter og stopper så bare uden besked om udfald (`:1521-1526`); `pollUpdateJob()` timer ud efter 12 minutter med en generisk "Job timeout"-fejl selvom jobbet kan køre videre server-side (`:1461-1477`).

## Anbefalinger, prioriteret

1. **Vigtigst:** beslut bevidst om edge-signaturverifikation skal være reel (faktisk OpenPGP/signaturtjek), eller om den nuværende model ("stol på den autenticerede headend-session") er en accepteret, dokumenteret risiko. Lige nu er det en udokumenteret afvigelse fra det designet selv hævder.
2. Luk governance-bypass'en (§2): enten lad auto-polleren respektere den tiltænkte lab-review-sti, eller fjern/dokumentér `cmdb.py`'s direkte auto-opret bevidst som den faktiske politik.
3. Tilføj service-genstart til app-update-rollback, og reel gendannelseslogik til OS-update-fejl.
4. Skriv en reel integrationstest for hele kæden (E-02), ikke kun fil-eksistens-tjek.
5. Tilføj et automatisk health-check + rollback-trin i headend-CI-deployet.
6. UI: skalér bekræftelses-friktion til blast radius (advarsel/preview ved "alle enheder"), og oversæt fejlkoder til de forklaringer der allerede findes i dokumentationen.

---

*Denne rapport er genereret af Claude (Sonnet 5) ved AI-assisteret kodegennemgang. Materiel AI-involvering er hermed synliggjort jf. framework'ets Provenance-krav. Konklusioner bør efterprøves af et menneske før de lægges til grund for beslutninger.*
