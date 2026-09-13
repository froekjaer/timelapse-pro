# Codex-review — eksplicit selvreview, ikke tredje uafhængige stemme

Reviewer: Codex, denne integrationssession, 2026-09-13. Baseline: `13a0d3b3af67a36adf9115d0911aaf2a687bca15`.

Jeg skrev §14/§15 og syntesen i #231. Jeg har også læst Claude/Kimi-reviewene før dette separate review; det er derfor **informeret selvreview**, ikke et blindt eller uafhængigt review. Faktisk grundlag: baseline-ADR, samarbejdsmodel, register, agentloadere, reviewpakke, begge fulde modtagne reviews, faste Framework/Platform-kilder læst i denne sessionkæde samt en begrænset kodekontrol af release-kvitteringen. Ingen fuld semantisk branchtriage eller live-installationsverifikation.

Samlet vurdering: tiltræder efter rettelser og synlig disposition af udskudt teknik. Claude og Kimis væsentlige fund er begrundede; mine oprindelige formuleringer var for uklare om status, ejerskab og sikker recovery. Deres forslag er ikke alle sikre at kopiere ordret.

## Beslutninger

| ID | Vurdering | Begrundelse |
|---|---|---|
| D01 | Rettelse kræves | Statusheader og dobbelt procedurespecifikation skal rettes, KIMI-01/02 |
| D02 | Rettelse kræves | Screening af #159/#163 skal mærkes som foreløbig, CLAUDE-04 |
| D03 | Rettelse kræves | Synlig intentionsregistrering og proportionalitet; draft-PR alene løser ikke race |
| D04 | Rettelse kræves | Navngiv mandat uden automatisk tildeling til sidste forfatter; CODEX-02 |
| D05 | Mere evidens | Proces kan anvendes nu, men scheduler/aktivitet over tid er ikke afprøvet |
| D06 | Rettelse kræves | Konkret restore-kontrol; PR-nummer er ikke generel retentiongaranti |
| D07 | Tiltræder med afgrænsning | Eksisterende delkontrol må ikke fremstilles som fuld sikkerhedsdækning, CODEX-03 |
| D08 | Tiltræder | Genbrug Framework-principper og Platform-kontrakter; ingen upstream-vedtagelse |
| D09 | Rettelse kræves | Selvrapporteret identitet og selvreview er ikke uafhængig attestering |
| D10 | Tiltræder med åbne rester | Lille procedure nu; teknisk håndhævelse og oprydning forbliver separate leverancer |

## Yderligere fund

**CODEX-01 — skal rettes:** En ny historisk optælling bliver ikke reproducerbar alene ved at totalsummen går op. KIMI-03's råpopulation er oplyst som lokal, ikke vedlagt. Bevar den påstand som reviewerens observation; tilføj separat frosset datasæt med alle ref/head/base-SHA'er og rå output. Sammenbland ikke forskellige måletidspunkter. Evidens: vedlagte BRANCH_REFS_FROSSET.tsv/BRANCH_SCREENING.json; Kimis originale datasæt afventes.

**CODEX-02 — skal rettes:** CLAUDE-07's foreslåede default "sidst rørte integration" kan genindføre implicit autoritet, og KIMI-07's automatisk degradering efter syv dage må ikke fortolkes som frigivelse af ejerskab. Registrér konkret udpegning/overdragelse; markér uverificeret aktivitet ved aftalt frist, uden overtagelse. Test/afprøv senere med to aktive sessioner; dokumentet er ikke en teknisk lås.

**CODEX-03 — skal rettes:** Funktionen `release_receipt_matches_artifact` kontrollerer artifact-id/commit/version i en kvittering. Den funktion alene beviser ikke kryptografisk signaturverifikation, mål-autorisation eller immutabilitet af hele artifactlageret. Ved henvisning til eksisterende teknik skal påstanden være præcis og begrænset; deploy kræver særskilt verificering af de øvrige kontroller.

## Scenarier

| ID | Vurdering ved baseline | Nødvendig kontrol/evidens |
|---|---|---|
| S01 | Proces delvist; teknisk hul | Intention + efterkontrol + sekventiel integration; ingen atomar lås påstået |
| S02 | Teknisk hul | Platform-generationskontrol er udskudt med opgave, ikke implementeret |
| S03 | Proces dækket | Recovery skal også omfatte materiale uden commits |
| S04 | Proces dækket | Første reelle semantiske restanalyse udestår |
| S05 | Proces og delkontrol | Faktisk preflight/autorisation/verifikation kræves ved deployment |
| S06 | Operativt teksthul | Flyt data≠instruktioner til §14 og loaderne; teknik udestår |
| S07 | Uafprøvet | Aktivitet/frister skal følges op; ingen eksisterende scheduler påstået |
| S08 | Dækket i dokumentdesign | Frisk deltager-onboarding endnu ikke afprøvet |
| S09 | Baseline for abstrakt | Tilføj konkret ref/backup + isoleret restore-pilot |
| S10 | Princip dækket, ikke attestering | Originaler, metode og begrænsninger bevares; tre navne er ikke tre uafhængige reviews |

Nødvendigt før endelig beslutning: status/deduplikering, datatillid, recovery, ejerskab, rådata og screeningforbehold. Minimumsændringer er indarbejdet i slutkandidaten, men forfatteren kan ikke selv erklære reviewerne enige i ny tekst. Platformkontrol, scheduler og branchtriage har synligt åbne næste leverancer. Ingen nye kanoniske FF-id'er eller driftsændringer foretages i denne reviewrunde.
