# TimeLapse Pro - Update Governance Diagnosis

Dato: 2026-09-01
Forfatter: Codex

## Executive summary

Update-flowet er ikke "bare" en liste over pakker. Det dækker tre forskellige arbejdsgange:

1. TimeLapse Pro software-release til Headend/Edge.
2. OS- og sikkerhedspakker på Edge.
3. Standard platform-apps på Headend, f.eks. nginx, certbot, node, ollama, ffmpeg og postgresql.

De tre arbejdsgange har forskellige risici og bør ikke føles som samme brugerrejse. TimeLapse Pro software-release må fortsat være håndbåret af Codex/Claude/Kimi eller anden betroet teknisk assistent, fordi det omfatter source commit, CI, signerede artifacts, migrations, deploy og rollback-evidence. Driftspakker og sikkerhedsopdateringer bør derimod være et selvbetjeningsflow med tydelig status, preflight, én-knaps handling, postflight og automatisk oprydning af gamle kandidater.

Den aktuelle database viser ikke et stort antal aktive almindelige "pending" updates. Den viser primært seks aktuelle blokerede Headend platform-app-kandidater og en del historiske rejected/rolled_back/superseded rækker fra tidligere lærings- og recovery-forløb.

Denne diagnose supplerer eksisterende åbne GRC-/kravspor, bl.a. `GRC #215` om adskilt OS security/functional updates, `#217` om komplet update audit trail, `#208` om verificerede update-artifacts, `#213` om rollback, `#219` om drift under update og `#313` om Ubuntu 24.04/22.04 mismatch mellem Edge-profiler.

## Aktuel status i databasen

Udtræk fra `pending_updates` 2026-09-01:

| Status | Miljø | Type | Antal | IDs |
|---|---:|---|---:|---|
| blocked | test | application_updates | 6 | 268, 267, 233, 231, 230, 228 |
| rolled_back | lab | app_updates | 2 | 9, 8 |
| rolled_back | test | app_updates | 4 | 171, 88, 85, 78 |
| rejected | lab | os_security | 1 | 5 |
| rejected | production | os_security | 2 | 172, 152 |
| rejected | production | os_updates | 2 | 173, 153 |
| rejected | test | application_updates | 6 | 176, 131, 116, 115, 114, 113 |
| rejected | test | os_security | 1 | 12 |
| rejected | test | os_updates | 1 | 11 |

Der findes også mange `deployed` og `superseded` rækker. De er audit-/historikrækker og må ikke blandes sammen med "du skal gøre noget nu".

## Hvorfor ligger der blokerede updates?

### Aktuelle blokerede Headend platform-apps

IDs `268`, `267`, `233`, `231`, `230`, `228` er alle `application_updates` for `TL-MACMINI-HEADEND-TEST-1` i `test`.

De handler om:

- `ollama 0.32.14 -> 0.33.0`
- `ffmpeg 9.0.1 -> 9.0.1_1`
- `postgresql@17 17.10 -> 17.11`
- `node 26.0.0 -> 26.7.0`
- `nginx 1.31.1 -> 1.31.4`
- `certbot 5.6.0_1 -> 5.7.0`

Årsag: CMDB/Homebrew-inventory rapporterer, at der er nyere versioner. Backend opretter dem bevidst som `blocked`, fordi standard-app-opdateringer ikke må installeres direkte uden signeret dependency-artifact, rollback-plan og postflight.

Det er sikkerhedsmæssigt korrekt, men UX'en skal gøre næste trin tydeligere.

### Stale target-status på nogle blokerede rækker

Nogle rækker har `update_targets.status = queued`, selv om hovedrækken er `blocked`. Det er historisk støj fra tidligere flow-versioner. Eksempler: `228`, `230`, `231`.

Forventet fremadrettet: når en update er `blocked`, må target-status ikke se deploy-klar ud. Den bør være `blocked`/`waiting_for_artifact` eller slet ikke oprettes før artifact/godkendelse.

## Hvorfor ligger der afviste updates?

### OS updates på Edge 2

IDs `152`, `153`, `172`, `173` er afviste OS/security updates for `TL-043EB9E72EFD`.

Årsagerne i evidence:

- Tidlige store update-kandidater viste 184 security- og 503 funktionelle pakker.
- Installforsøg fejlede med lavniveau OS-kompatibilitet, bl.a. `GLIBC_2.38 not found`.
- Senere mindre kandidater viste 8 security- og 27 funktionelle pakker.
- Handover-loggen beskriver, at tilsvarende pakker senere blev håndteret uden om det oprindelige governed flow og derfor blev lukket som stale, så gamle kandidater ikke kunne godkendes ved en fejl.

Konklusion: disse bør blive i historikken, men må ikke føles som aktuelle opgaver.

### Headend platform-apps

IDs `176`, `131`, `116`, `115`, `114`, `113` er gamle Headend test-kandidater.

Årsag: queue hygiene 2026-08-23 lukkede dem som stale testkandidater. Nye kandidater blev senere oprettet med nyere evidence.

## Hvorfor ligger der rolled back?

Rolled-back rækkerne er primært gamle lab/test-app artifacts til `TL-C87FF9587CA0`.

Eksempler:

- `88` og `85`: rollback fordi artifact-installationen forsøgte at skrive systemd unit-filer på et read-only filesystem.
- `78`: rollback efter download-/artifact-fejl.
- `8`, `9`, `171`: gamle lab/test rollback-events fra signerede artifact-pull/apply forsøg.

Konklusion: de er nyttige som lærings- og audit-historik, men ikke aktuelle opgaver.

## Grundproblemer

### 1. Én kø viser tre driftsmodeller

TimeLapse Pro release, Edge OS-pakker og Headend platform-apps kræver forskellig beslutning, men vises næsten ens.

### 2. "Afventer" og "blokeret" blandes i dashboardet

Dashboardet tæller både pending og blocked som ventende. `/updates` åbnede tidligere på fanen `Afventer`, som kunne være tom. Det gav indtryk af, at systemet skjulte opdateringerne.

### 3. "Alle" var ikke alle

UI'en sendte ingen statusparameter for `Alle`, og backend returnerede derfor kun default `pending/approved`. Det gjorde historik- og diagnosevisningen misvisende.

### 4. Aktuelle update-kort lå for langt nede

Opdateringslisten lå efter device-matrix, lab-import og artifact-katalog. Reelle `#xxx`-kort kunne derfor ende langt nede på siden.

### 5. Blokerede updates mangler et bedre teknisk state

`blocked` bruges både som sikkerhedsgate, historisk fejl og "afventer artifact". Fremadrettet bør der være en mere præcis understatus, f.eks. `waiting_for_signed_artifact`, `failed_preflight`, `stale_superseded`, `manual_decision_required`.

## Anbefalet målmodel

### TimeLapse Pro software-release

Skal være et håndbåret release-flow:

1. PR/branch klar.
2. CI grøn.
3. Migration rehearsal.
4. Signeret release artifact.
5. Headend deploy.
6. Canary Edge.
7. Edge 2 efter canary.
8. Postflight.
9. Cleanup af gamle pending/superseded candidates.
10. Handover-entry.

Dette er ikke et "Peter klikker alene"-flow.

### OS og standard driftspakker

Skal være selvbetjeningsvenligt:

1. CMDB viser installeret version og tilgængelig version.
2. Systemet bygger eller finder signeret offline artifact.
3. UI viser enkel anbefaling: "Kan installeres", "Kræver forarbejde", "Blokeret fordi ...".
4. Peter kan godkende én enhed ad gangen.
5. Systemet kører preflight, backup, install, postflight og rollback automatisk.
6. Hvis en nyere inventory viser at pakken ikke længere mangler, lukkes den gamle kandidat automatisk som `superseded`.

## Ændring i denne PR

Denne PR retter kun synlighed og sortering:

- `/api/updates/pending?status=actionable` returnerer updates der kræver handling.
- `/api/updates/pending?status=all` returnerer faktisk alle updates.
- Backend sorterer action-first: pending, approved, rollback requested, blocked, failed, rolled back, deployed, rejected, superseded.
- `/updates` starter på `Kræver handling`.
- Selve update-kortlisten vises før CMDB-matrix, lab-import og artifact-katalog.
- UI sorterer også lokalt med status, severity, oprettelsesdato og ID.

## Næste anbefalede tekniske lukning

1. Indfør en eksplicit `resolution_reason` eller `blocked_reason` i databasen i stedet for at gemme forklaringen i `description`/`last_error`.
2. Harmoniser `pending_updates.status` og `update_targets.status`, så `blocked` ikke kan have target `queued`.
3. Tilføj en daglig hygiene-job:
   - Luk gamle pending/blocked updates hvis CMDB ikke længere rapporterer dem.
   - Luk gamle app release-kandidater når nyere signed release findes.
   - Bevar historik, men flyt den ud af default handling-visning.
4. Del UI op i tre spor:
   - Driftspakker.
   - TimeLapse release.
   - Historik/evidence.
5. Gør Headend platform-app updates til et egentligt "preflight -> artifact -> install -> postflight" flow for hver understøttet komponent.
