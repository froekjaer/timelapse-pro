# TimeLapse Pro — Capability Map v0.1

**Dato:** 2026-09-16  
**Forfatter:** ChatGPT i samarbejde med Peter Frøkjær  
**Status:** Working capability map — ikke en erstatning for GRC, kravregister eller UI usecase-katalog  
**Baseline:** `main` @ `8452c5ef264d85823dce149a3bb371142d598569`

## 1. Formål

Dette dokument etablerer et tyndt capability-lag mellem produktets intention, usecases, implementation, tests og faktisk runtime-evidens.

Det skal gøre det muligt at svare på:

1. Hvad skal TimeLapse Pro faktisk kunne?
2. Hvilke invariants må en ændring ikke bryde?
3. Hvilke usecases realiserer capability'en?
4. Hvor er den implementeret?
5. Hvilken kendt-god reference har vi?
6. Hvilken evidens viser at den virker i praksis?
7. Hvilke gaps er stadig åbne?

Dokumentet må ikke bruges som bevis for runtime-status alene. Historiske dokumenter, kode, tests og UI-status er evidenskilder, men capability-status skal afspejle det stærkeste aktuelle evidensniveau.

## 2. Kilder og forhold til eksisterende registre

Primære kilder ved oprettelsen:

- `Dokumentation/UI_USECASE_CATALOG_2026-08-26.md` — menneskelig UAT-/usecase-baseline.
- `Dokumentation/KRAVREGISTER_og_STATUS_v10.md` — historisk krav- og implementeringsstatus.
- aktuelle runtime-/auditfund dokumenteret i handover og nyere reviewspor.
- GRC-registret — fortsat autoritativt for tests, findings, risks og evidensstatus.

Dette capability map skal ikke konkurrere med disse. Den ønskede kæde er:

`Requirement / rule → Capability → Usecase → Implementation → Test/evidence → Runtime outcome`

## 3. Statusmodel

En capability kan være på forskellige evidensniveauer:

- **DEFINED** — intent/invariants beskrevet.
- **IMPLEMENTED** — implementation kan identificeres.
- **AUTOMATED VERIFIED** — relevante automatiserede tests passerer.
- **RUNTIME VERIFIED** — faktisk runtime er verificeret i relevant miljø.
- **CAPABILITY VERIFIED** — end-to-end adfærd er verificeret fra bruger-/missionsperspektiv.

Supplerende tilstande:

- **DEGRADED** — capability findes, men et vigtigt invariant eller outcome er ikke opfyldt.
- **GAP** — nødvendig del mangler.
- **UNKNOWN** — utilstrækkelig eller forældet evidens.
- **SUPERSEDED** — capability eller løsning er bevidst erstattet.

Et grønt implementation-flag er aldrig alene bevis for CAPABILITY VERIFIED.

## 4. Golden Capabilities

### CAP-01 — Autonom billedoptagelse

**Intent**  
Edge skal tage planlagte billeder på korrekt tidspunkt uden at være afhængig af Headend eller aktiv internetforbindelse.

**Invariants**
- Capture må ikke stoppe alene fordi Headend/internet er utilgængelig.
- Plan/schedule skal kunne anvendes lokalt.
- En vellykket capture skal resultere i et identificerbart billede med metadata.
- Reboot/strømsvigt må ikke permanent stoppe capture-loopet.

**Usecases / krav**
- Historisk krav: `CAP-001` automatiske timelapse-billeder.
- UI-observation via device/capture flows: `UC-DEV-001..003`.

**Implementation / kendt løsning**
- Edge capture-loop, kamera-driver/gphoto2 og lokal state/config.
- Kameraer har historisk omfattet Canon og Nikon Z30.

**Verification**
- Automatiske tests er relevante men utilstrækkelige alene.
- Fysisk Edge2 capture er observeret i nyere audit.
- Edge1/Edge2 skal indgå i fuld capability-acceptance.

**Aktuel status:** **RUNTIME VERIFIED / PARTIAL**  
**Åbne gaps:** end-to-end golden test for scheduled capture efter reboot, offline drift og senere upload bør formaliseres.

---

### CAP-02 — Kamera- og strømstyring

**Intent**  
TimeLapse Pro skal kunne kontrollere kamera og nødvendige relæer på en kontrolleret, recoverable måde.

**Invariants**
- Hardwarehandlinger skal gå gennem defineret HAL/service-operation frem for vilkårlig direkte GPIO i normal drift.
- Relay skal efterlade sikkert slut-state efter teardown/expiry.
- Forkert pin/config må ikke kunne ændres uden tydelig risikokontekst og recovery-plan.
- Kamera-detektion og PTP-status skal kunne verificeres.

**Usecases / krav**
- `CAP-010` relay-styring.
- `UC-CONF-006` GPIO/relay parameter.
- `UC-TECH-002` camera power lease.
- `UC-TECH-003` revoke/expiry cleanup.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Åbne gaps:** fysisk golden-test på de aktuelle Edge-hardwareprofiler.

---

### CAP-03 — Korrekt og sporbar tid

**Intent**  
Capture-tid, systemtid og den tid der vises centralt skal være konsistent, korrekt og sporbar.

**Invariants**
- Capture timestamp må ikke ændre betydning gennem Edge → Headend → UI.
- Tidszone og UTC/local-konvertering skal være entydig.
- Tidssynkronisering må have kendt health-state.
- Forkert tidspunkt må ikke skjules som et almindeligt UI-formatproblem.

**Known evidence**
- GPS/chrony Stratum-1 blev verificeret på begge Edge-enheder i nyere fysisk audit.
- Historisk åbent spor #159 om capture timestamp-felter viser, at capability'en ikke bør anses fuldt lukket.

**Aktuel status:** **RUNTIME VERIFIED / DEGRADED**  
**Gap:** semantisk end-to-end capture-time verification mangler.

---

### CAP-04 — Billedintegritet og provenance

**Intent**  
Et capture skal kunne følges fra kamera til lagring/visning uden uopdaget identitets- eller integritetstab.

**Invariants**
- Capture-id/device/filename/timestamp skal fortsat referere til samme logiske billede.
- Sidecar/metadata må ikke silently kobles til forkert capture.
- Original og eventuelle derivater/redaction/thumbnails skal kunne skelnes.
- Destruktive flows skal være auditerede.

**Usecases / krav**
- `CAP-008` capture access log.
- `CAP-009` sidecar JSON/XMP.
- `UC-DEV-007..009`.
- `UC-RED-001..003`.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** samlet provenance-test gennem capture → upload → storage → UI → derivative mangler.

---

### CAP-05 — Lokal dataoverlevelse

**Intent**  
Captures, nødvendig config og lokal driftsstate skal overleve relevante netværksudfald og reboots.

**Invariants**
- Netværksudfald må ikke i sig selv medføre datatab.
- Buffered captures må ikke overskrives uden defineret retention/backpressure-adfærd.
- Lokal config/cache skal være tilstrækkelig til sikker degraded drift.

**Usecases / krav**
- Historisk `CAP-002` store-and-forward / circular buffer.
- Backup/restore-relaterede `UC-BKP-004..005`.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** dokumenteret failure-test for buffer-full + reboot + offline recovery bør tilføjes.

---

### CAP-06 — Store-and-forward og senere levering

**Intent**  
Manglende forbindelse må ikke stoppe capture; manglende uploads skal senere kunne leveres uden tab eller ukontrolleret duplikering.

**Invariants**
- Capture fortsætter offline.
- Backlog er synlig.
- Genforbindelse skal resultere i kontrolleret drain.
- Upload-status må ikke påstå succes før faktisk levering er verificeret.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** golden end-to-end test offline → reconnect → backlog drained.

---

### CAP-07 — Edge ↔ Headend kommunikation

**Intent**  
Headend og Edge skal udveksle config, heartbeat, telemetry, events, update-state og relevante artifacts kontrolleret.

**Invariants**
- Manglende kommunikation skal kunne skelnes fra sund runtime.
- Edge må kunne fortsætte relevante lokale funktioner under Headend-udfald.
- Sync må ikke være eneste recovery-vej.
- Security/audit-events må ikke silently forsvinde ved midlertidig central utilgængelighed.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** kontraktmæssig end-to-end health for alle centrale sync payloads bør samles.

---

### CAP-08 — Central konfiguration med arv og sikker anvendelse

**Intent**  
Operatøren skal kunne konfigurere systemet centralt og forstå effektiv værdi, arv og hvornår ændringen er aktiv.

**Invariants**
- Global → kunde → site → kamera arv skal være deterministisk.
- Effektiv config skal være synlig.
- Ændringer skal versions-/audit-spores.
- En config markeret som gemt er ikke nødvendigvis bevis for at Edge faktisk anvender den.

**Usecases**
- `UC-CONF-001..006`.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** runtime-applied-state skal bindes tydeligere til central status.

---

### CAP-09 — Lokal Edge management og recovery

**Intent**  
En servicetekniker skal kunne diagnosticere og recovere Edge lokalt, også hvis Headend eller internet er nede.

**Invariants**
- Må ikke afhænge af Headend.
- Må ikke afhænge af én bestemt management-transport.
- BT-PAN, LAN og routed/customer network kan anvendes hvor deployment-policy tillader det.
- Authentication/authorization er uafhængig af netværksvejen.
- Under development/stabilization bevares praktisk fuld recovery/root shell.
- En terminal skal være praktisk anvendelig som terminal — ikke blot kunne sende tekst til en shell.

**Usecases**
- `UC-LOCAL-001..002`.
- Technician-usecases `UC-TECH-001..003`.
- Direct-Edge portal er ikke dækket fuldt af den historiske UI usecase-catalog og skal have eksplicit usecase.

**Known-good reference**
- Headend "Åbn terminal" rich terminal experience.
- Historisk Direct-Edge xterm-linje er relevant capability-provenance, ikke automatisk merge-authority.

**Aktuel status:** **IMPLEMENTED / DEGRADED**  
**Evidence/gaps**
- Backend recovery/session robustness fra PR #238 er på main.
- Direct-Edge terminal UX havde fysisk regression.
- #239 er kandidat til renderer-fix, men fysisk acceptance mangler.

---

### CAP-10 — Remote management og recovery

**Intent**  
Når netværksforbindelse findes, skal teknikeren kunne administrere/recovere Edge centralt via Headend/reverse tunnel uden at gøre lokal recovery afhængig af denne vej.

**Invariants**
- Host identity/trust må verificeres.
- MFA/capability/audit skal gælde for browserterminal.
- Central vej må ikke erstatte lokal recovery som eneste mulighed.

**Usecases**
- `UC-SSH-001..004`.
- `UC-CMDB-006..007` break-glass-relaterede flows.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** browserterminal/usecase fysisk og security acceptance bør holdes adskilt fra Direct-Edge acceptance.

---

### CAP-11 — Software-, OS- og dependency-update med faktisk health-verifikation

**Intent**  
Systemet skal kunne opdateres kontrolleret og efterfølgende bevise, at den nye runtime faktisk fungerer.

**Invariants**
- Artifact/scope/version skal være identificerbar.
- Approval/deployment-state er ikke det samme som working runtime.
- Relevant health gate skal verificeres efter restart/install.
- Rollback skal kunne udføres ved relevant failure.
- Edge OS-dependencies må følge den governede offline-bundle-model, hvor den gælder.

**Usecases**
- `UC-UPD-001..006`.
- `UC-CHG-001..004`.

**Aktuel status:** **DEGRADED**  
**Evidence**
- Edge1 havde dependency-update registreret som deployed, mens TOTP-service crash-loopede i ca. 19 timer.
- App-update post-restart health gate findes for relevante app-update flows.
- Dependency lifecycle har fortsat gaps.

---

### CAP-12 — Health, monitoring og alarmering på faktisk outcome

**Intent**  
Operatøren skal kunne se forskel på registreret/deployed/alive og en Edge der faktisk udfører sine kritiske funktioner.

**Invariants**
- Health skal knyttes til relevante runtime outcomes.
- Monitoring skal være proportional med konsekvens, ikke kun fejlens varighed.
- En service i restart-loop må ikke fremstå sund alene fordi processen genstarter.
- Telemetry der indsamles uden consumer/alarm er ikke en fuld monitoring capability.

**Usecases**
- `UC-DRIFT-001..004`.
- `UC-SIEM-001..004`.
- `UC-CMDB-001..004`.

**Aktuel status:** **DEGRADED**  
**Evidence**
- NRestarts indsamles forskellige steder, men nyere audit fandt ingen relevant Headend consumer/alarm.
- Edge1's langvarige crash-loop blev ikke operationalt fanget.

---

### CAP-13 — Boot/restart recovery

**Intent**  
Efter reboot, strømudfald eller relevant servicefejl skal Edge vende tilbage til fungerende missionstilstand eller tydeligt eskalere at den ikke gør.

**Invariants**
- Boot skal starte kritiske services.
- Capture og management skal kunne komme tilbage.
- Watchdog/self-heal må ikke skjule vedvarende fejl.
- Recovery-status skal måles på outcome, ikke blot at systemd genstarter processen.

**Aktuel status:** **RUNTIME VERIFIED / PARTIAL**  
**Evidence**
- Edge1 reboot persistence er observeret fysisk.
- Watchdog/restart-loop design og Builder-provenance er stadig åbne gaps.

---

### CAP-14 — Tenant-, kunde-, site- og device-isolation

**Intent**  
Data, administration og handlinger skal være korrekt scoped til kunde/site/device og rolle.

**Invariants**
- Viewer/operator/admin/super-admin må kun se/ændre autoriseret scope.
- Backend skal håndhæve isolation, ikke kun frontend.
- Cross-tenant data leakage er en capability-failure, ikke kun en UI-bug.

**Usecases**
- `UC-AUTH-001..005`.
- Tenant-scope gennem device, image, tag og admin-usecases.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** fuld multi-role/multi-tenant acceptance-matrix bør være eksplicit.

---

### CAP-15 — Audit, accountability og forensic evidence

**Intent**  
Konsekventielle handlinger og sikkerhedshændelser skal kunne rekonstrueres med tilstrækkelig provenance og uden at gøre lokal recovery afhængig af central connectivity.

**Invariants**
- Hvem/hvad/hvornår/resultat skal registreres proportionalt med handlingens konsekvens.
- Local-first audit skal anvendes hvor central connectivity ikke kan antages.
- Manglende forwarding må ikke slette lokal evidence.
- Audit-log må ikke selv lække secrets.

**Usecases**
- `UC-SIEM-001..004`.
- update/change/credential/terminal/retention/destructive flows.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Evidence**
- Shell session start/end local-first audit er på main via #238.
- Fuld transcript logging er ikke et generelt krav.

---

### CAP-16 — Headend operation, UI og human-operable system

**Intent**  
Operatøren skal gennem den faktiske UI kunne forstå status, udføre relevante handlinger og opdage når systemets statusmodel ikke svarer til virkeligheden.

**Invariants**
- Samme statusord skal have samme betydning eller forklares.
- Farlige handlinger skal adskilles tydeligt fra read-only handlinger.
- UI skal vise relevante gaps/UNKNOWN frem for falsk grøn status.
- UI-usecase-kataloget er den menneskelige "kan vi faktisk bruge systemet?" baseline og skal kobles til capabilities.

**Usecases**
- Dashboard, device, CMDB, Drift, SIEM, Updates, Backup, Retention, AI, Import m.fl. i `UI_USECASE_CATALOG_2026-08-26.md`.
- Katalogets `OBS-UI-001` er et konkret eksempel på divergerende statussemantik mellem Dashboard og Drift.

**Aktuel status:** **IMPLEMENTED / PARTIAL**  
**Gap:** samlet UAT/acceptance med capability-sporbarhed mangler.

## 5. Foreløbig capability × kendte åbne spor

| Capability | Kendt åbent spor / evidens |
|---|---|
| CAP-03 Korrekt tid | #159 capture timestamp relocation/retest |
| CAP-09 Lokal recovery | #239 fysisk Direct-Edge terminal acceptance |
| CAP-11 Updates | Edge1 dependency incident; #163 post-restart handshake-rest |
| CAP-12 Monitoring | Edge1 19h crash-loop; NRestarts uden relevant consumer/alarm |
| CAP-13 Boot/recovery | Builder/watchdog/reproducibility fra #242 |
| CAP-16 Human-operable UI | UI usecase-katalog; OBS-UI-001..005 |

## 6. Capability preservation rule

Ved en consequential ændring skal følgende spørgsmål besvares før disposition:

1. Hvilke capabilities berøres?
2. Hvilke invariants er relevante?
3. Hvad er known-good reference?
4. Hvilken implementation ændres?
5. Hvilke automatiserede tests beskytter implementationen?
6. Hvilken runtime/physical verification kræves?
7. Er capability outcome efter ændringen VERIFIED, DEGRADED, GAP eller UNKNOWN?

En branch må ikke klassificeres som absorberet/superseded alene fordi filer/funktioner/tests ser dækket ud, hvis den indeholder en consequential capability med særskilt intention eller runtime-adfærd.

## 7. Næste iteration

Før dette map kan blive et stabilt baseline-dokument skal følgende verificeres mod aktuel source og runtime:

- præcis implementation-reference for hver capability;
- komplette usecase-links;
- GRC test/finding/evidence-referencer;
- actual runtime-status pr. Edge1/Edge2/Headend;
- acceptance-test for Golden Capabilities;
- relation til Builder/image reproducibility;
- eksplicit Direct-Edge terminal usecase;
- samlet `Capability → Usecase → Implementation → Test/evidence → Runtime` gap-map.

Ingen af ovenstående bør rekonstrueres fra hukommelse hvis authoritative state kan hentes direkte.
