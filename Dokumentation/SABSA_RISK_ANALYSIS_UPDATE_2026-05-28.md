# TimeLapse Pro - SABSA Risk Analysis Update

**Version:** 2026-05-28  
**Status:** Arbejdsversion, supplerer `RISK_ASSESSMENT_v6.md`  
**Fokus:** Forretningsstrategi, GRC, COBIT/SABSA governance, finansiel impact, AI/cost-aware drift og opdateret risikobillede baseret på live evidence.

## 1. Strategisk Retning

TimeLapse Pro bevæger sig fra et teknisk timelapse-system til en GRC-understøttet platform for dokumentation, drift, compliance og forretningsrisiko. Systemet skal kunne forklare ikke bare *hvad* der skete, men *hvorfor* en teknisk beslutning blev taget, hvad den kostede, hvilken risiko den reducerede, og hvilken kundeværdi den skabte.

Det er en naturlig SABSA/COBIT-retning:

- SABSA forbinder business attributes med kontroller og evidens.
- COBIT forbinder beslutningsrettigheder, målepunkter, procesmodenhed og governance.
- ISO 27000, IEC 62443, NIS2 og CRA bliver compliance-lag over samme evidence model.

## 2. Opdaterede Business Attributes

| Attribute | Forretningsbetydning | Ny 2026-05-28 fortolkning |
|---|---|---|
| Availability | Billeder, UI, AI og updates skal fungere uden uacceptabel driftspåvirkning | AI/Ollama er nu en delt kapacitetsressource, som skal styres pr. kamera/kunde/SLA |
| Integrity | Billeder, metadata, updates og change tickets må ikke kunne manipuleres | Code-signing trust root findes; Edge artifact verification og signal attestation mangler |
| Confidentiality | Kundedata og secrets må ikke lække | Git hygiene er bedre, men anonymiseret eksport og legacy token cleanup mangler |
| Accountability | Beslutninger og handlinger skal kunne spores | Change-ticket model findes, men 0 tickets er registreret |
| Authenticity | Edge, Headend, bruger og artifact skal kunne bevise identitet | 7 devices mangler API/signing credentials; 2 legacy tokens findes |
| Manageability | Drift skal styres centralt og sikkert | Update matrix og compliance cockpit findes; enforcement mangler stadig |
| Continuity | Headend/Edge skal kunne gendannes | Backup/failover er ikke klar; ISO/bare-metal pipeline er planlagt |
| Auditability | Compliance status skal kunne dokumenteres near-real-time | Cockpit findes med live evidence, men controls viser 11 warnings og 1 fail |
| Economic Efficiency | Risiko- og driftsbeslutninger skal være økonomisk forsvarlige | Ny attribute: AI local/cloud/batch og service tiers skal prissættes ud fra impact vs. cost |
| Customer Value | Sikkerhed og AI skal understøtte kundens forretningsmål | Ny attribute: premium/compliance/critical tiers kan differentieres med SLA, evidence og risk appetite |

## 3. GRC Evidence Status

| Evidence source | Status | Risikobetydning |
|---|---|---|
| CMDB inventory | Delvist | Devices findes, men installed-state og firmware coverage er ufuldstændig |
| SIEM | Delvist positiv | 14 info events sidste 24 timer, ingen critical; coverage skal stadig udvides |
| Key lifecycle | Delvist | Trust root findes, men device credentials mangler |
| Signed artifacts | Delvist | 1 signed artifact registered |
| Signed change tickets | Mangler | 0 registered, derfor svag audit chain |
| Backup/restore evidence | Mangler | Headend backup/off-host/warm standby ikke klar |
| AI Ops/SAST | Delvist | 73 signaler kræver triage |
| Update device matrix | Delvist | OS security og OS updates synlige med risk score; workflow mangler accept/enforcement |

## 4. Opdateret Risikoregister

| Risk | v6 status | 2026-05-28 opdatering | Ny vurdering |
|---|---|---|---|
| R01 SFTP data-adskillelse | Residual lav | Ikke genverificeret som produktionskontrol i denne runde | Uændret indtil chroot evidence indgår i cockpit |
| R02 UI adgangskontrol | MFA åbent punkt | 4 brugere, 1 med MFA; WebAuthn/TOTP findes, men ikke bredt enforced | Medium: MFA policy skal gøres rolle-/risk-baseret |
| R03 Hardware-historik | Lav efter Camera/Pi-kobling | Camera/device model findes; CMDB coverage mangler for alle devices | Lav/medium afhængigt af restore evidence |
| R04 Remote adgang | Lav efter SSH tunnel | Tunnel bør fortsat være manuel debug-only; no headend push afhængighed | Lav hvis policy enforced |
| R05 Kompromitteret edge | Medium | Device API/signing credentials mangler; legacy tokens findes | Højere end v6: identity lifecycle er ikke lukket |
| R06 Fejlet update til alle sites | Lav efter staged rollout | UpdateTarget, artifact og cockpit findes; change tickets og enforcement mangler | Medium/høj for production |
| R07 Nøglekompromittering | Lav efter key mgmt | Trust root findes, men devices mangler credentials | Medium indtil rollout |
| R08 MITM/API | Lav efter mTLS/pinning plan | mTLS/request signing ikke færdig | Medium |
| R09 Backup | Medium | Headend backup/off-host/warm standby ikke klar | Høj for production |
| R10 SSH tunnel misbrug | Lav | Stadig acceptabel hvis debug-only og audited | Lav/medium afhængigt af audit coverage |
| R11 AI resource/cost overload | Ny | Flere kameraer/backfill/Open WebUI deler Ollama; cloud/batch beslutning ikke cost-aware | Medium nu, høj ved skalering |
| R12 Compliance evidence gap | Ny | Cockpit findes, men 11 warnings, 1 fail, 0 tickets | Medium/høj for kunde-/audit-ready |
| R13 Business impact underestimeres | Ny | Risk score begynder at bruge business impact, men finansiel impact er ikke modelleret pr. kunde/site/kamera | Medium |

## 5. AI, Cost og Risk Model

AI-strategien bør udvides fra “hvilken model giver bedst kvalitet?” til en beslutningsmotor:

```text
Decision = f(quality_need, risk_score, business_impact, SLA, local_capacity, cloud_cost, batch_window, customer_policy)
```

### Beslutningsmuligheder

| Mode | Bruges når | Økonomisk profil |
|---|---|---|
| Local realtime | Normal QA/tagging, lav/medium impact, kapacitet ledig | Lav marginal cloud-cost, men bruger Mac Mini ressourcer |
| Local queued | Ikke-kritisk analyse, flere kameraer, kort forsinkelse acceptabel | Lav cost, men kræver køstyring |
| Cloud realtime | Høj impact, lav local confidence, kritiske events, SLA | Højere direkte cost, lavere risiko for missed event |
| Backup headend batch | Historisk re-tagging, compliance review, store mængder | God til natlige jobs og isoleret resourcebelastning |
| Manual review | Høj risiko, lav model confidence eller regulatorisk krav | Høj support-cost, høj assurance |

### Nye GRC-parametre pr. kunde/site/kamera

- Business criticality
- Accepted delay
- Max monthly AI cost
- Required evidence level
- Compliance tier
- Cloud allowed / local only / hybrid
- Batch window
- Manual approval threshold
- Consequence of missed detection
- Consequence of false positive

## 6. COBIT-orienterede Governance Controls

| COBIT-lignende område | Kontrolmål | Timelapse Pro implementering |
|---|---|---|
| Evaluate/Direct/Monitor | Ledelsen skal kunne se risiko, cost og compliance | Compliance cockpit + kommende business risk/value model |
| Build/Acquire/Implement | Ændringer skal være signerede, testede og rollbackbare | Change ticket + artifact + UpdateTarget |
| Deliver/Service/Support | Drift skal være stabil og målt | CMDB, SIEM, AI resource governor, backup evidence |
| Monitor/Evaluate/Assess | Kontroller skal måles løbende | Near-realtime cockpit, AI Ops, SAST triage |

## 7. Prioriteret SABSA/COBIT Roadmap

### Sprint GRC-1: Evidence chain

- Gør change ticket obligatorisk for updates, backup, restore, ISO og high-risk AI decisions.
- Bind approvals til bruger, rolle, MFA/session context og signature.
- Vis ticket/evidence i Compliance Cockpit.

### Sprint GRC-2: Identity and attestation

- Udsted API credentials og signing credentials pr. Edge/Headend.
- Implementer request-signatures eller mTLS.
- Fjern legacy device tokens.
- Edge skal verificere Headend-signeret policy/artifact før install.

### Sprint GRC-3: Backup and resilience

- Headend backup-job, off-host target, restore-test evidence.
- Kold/varm backup headend blueprint.
- Edge bare-metal ISO pipeline med call-home bootstrap og hardening evidence.

### Sprint GRC-4: Business risk/value model

- Kundens business impact, SLA og risk appetite ind i CMDB.
- AI local/cloud/batch beslutninger baseres på risk/cost.
- Service tiers kan prissættes med dokumenteret cost, impact og assurance.

### Sprint GRC-5: Continuous assurance

- SAST/DAST signaler triageres i GRC workflow.
- Compliance status viser control owner, evidence freshness og residual risk.
- Near-realtime “compliant / non-compliant / evidence stale” per standard.

## 8. Konklusion

Timelapse Pro har nu fundamentet til en SABSA/COBIT-orienteret GRC-overbygning: CMDB, SIEM, update matrix, key management, compliance cockpit, AI Ops og signed artifact model. Næste modenhedsspring er at binde tekniske hændelser og beslutninger til forretningsrisiko og finansiel impact.

For produktionsklarhed er de vigtigste gaps fortsat: device identity/signing, signed change workflow, backup/failover evidence og AI resource/cost governance.

