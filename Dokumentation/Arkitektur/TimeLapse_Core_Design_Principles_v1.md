# TimeLapse Pro — Core Design Principles and Secure Local Service Architecture

- **Status:** Arkitektur- og designgrundlag — **Proposed**
- **Anvendelse:** TimeLapse Pro, Mission Timelapse og fremtidige Mission Framework-baserede løsninger
- **Sprog:** Dansk
- **Normativ styrke:** Forslag til bindende produkt- og udviklingsprincipper. Principperne bliver først bindende, når Peter accepterer dem eller de relevante dele som ADR'er.
- **Dato:** 2026-07-31

> **Integrationsstatus.** Dette dokument ændrer ikke kørende funktionalitet eller eksisterende retention-adfærd. Det er en samlet normativ retning, som skal bruges ved design- og reviewbeslutninger. Hvor det kolliderer med en accepteret ADR, er ADR'en gældende, indtil en ny ADR superseder den. Se især [ADR-001](../ADR/ADR-001-platform-payload-split.md), [platform/payload-planen](Modularisering_Platform_Payload_Plan.md), [SABSA-arkitekturen](../SABSA_Architecture_v10.md) og handover-loggen for integrationsreviewet.

---

## 1. Formål

Dette dokument fastlægger de centrale designprincipper for TimeLapse Pro og beskriver en sikker, modulær lokal serviceløsning baseret på Bluetooth Low Energy og en lokal serviceportal.

Det har to formål:

1. At skabe et stabilt sæt principper, som alle fremtidige ændringer i TimeLapse Pro skal vurderes imod.
2. At definere en sikker arkitektonisk retning for lokal installation, konfiguration, diagnosticering og service af edge-enheder.

TimeLapse Pro skal udvikles som et langsigtet projekt-, dokumentations- og evidenssystem — ikke blot som en kameraapplikation. Systemet anvendes blandt andet på byggeprojekter, der kan vare mere end fem år. Billeder, metadata, konfigurationer og historik kan derfor have betydelig dokumentationsmæssig, kontraktuel og bevismæssig værdi.

### 1.1 Åbne afklaringer og as-is → target

Dette er et målarkitekturdokument. Følgende forhold er bevidst registreret som åbne, så dokumentet ikke sammenblander ønsket retning med eksisterende adfærd:

| Område | Dokumenteret nuværende situation | Foreslået mål | Næste beslutning |
|---|---|---|---|
| Retention og lagerpres | V10-manualerne beskriver automatisk cleanup efter `retention_days`; SABSA beskriver en 50 GB circular buffer | Originale projektdata slettes kun gennem eksplicit disposition | Særskilt ADR om evidensretention, cache/temporære data, GDPR og lagerpres |
| Lokal Bluetooth-service | Eksisterende Bluetooth-/TOTP-løsning er ikke dokumenteret som fysisk aktiveret, capability-/rollebaseret gateway | Service normalt lukket; fysisk aktivering, kort session, platform-policy og audit | Samlet ADR om kontrolleret lokal serviceadgang og efterfølgende implementeringsplan |
| Projektmodel | Den eksisterende model er Customer → Site → Camera → Device/Capture | Explicit project lifecycle med projekt-ID og disposition | Definér om `project` er et site, et nyt aggregate eller en tværgående relation |
| HAL og capability manifest | HAL findes delvist; rå hardwarebindinger findes fortsat | Versionerede, logiske hardware- og servicecapabilities | ADR-002/kontrakt-spike under ADR-001 |

I særdeleshed skal *projektdata* afgrænses fra cache, midlertidige filer, sikkerhedslogs og afledte artefakter, før retentionprincippet kan blive bindende. Lovlig sletningsforpligtelse og GDPR's storage limitation kræver fortsat eksplicit, autoriseret og auditeret disposition — ikke stiltiende automatisk sletning af evidens.

---

# Del I — Core Design Principles

## 2. Grundlæggende produktforståelse

TimeLapse Pro er:

- et projektstyringssystem for langvarige timelapse-projekter
- et distribueret sensor- og edge-system
- et dokumentations- og evidenssystem
- en platform for kamera-, telemetri-, AI- og servicefunktioner
- en potentiel referenceimplementering af Mission Framework.

Det er ikke alene et kamera, billedlager, netværksvideorecorder, almindelig IoT-enhed eller midlertidig capture-buffer. Denne forståelse skal afspejles i storage, sikkerhed, arkitektur, brugerroller, drift og lifecycle management.

## 3. Princip 1 — Formål før teknologi

Enhver ny funktion skal kunne spores til et reelt behov, en forpligtelse, en risiko eller et ønsket resultat. Der må ikke tilføjes teknologi alene, fordi den er interessant eller tilgængelig.

For enhver væsentlig funktion skal man kunne svare på:

- Hvilket problem løser den?
- For hvem skaber den værdi?
- Hvilken risiko introducerer den?
- Hvordan kan dens effekt observeres og verificeres?
- Hvem er ansvarlig for dens anvendelse?

Bluetooth, AI, fjernstyring og automatisering er midler — ikke formål.

## 4. Princip 2 — Projektdata slettes aldrig automatisk

TimeLapse Pro må aldrig automatisk slette projektbilleder eller tilhørende projektdata som reaktion på lagergrænser, diskpres, alder, manglende uploadstatus, databasefejl, timeout, forbindelsesproblemer, softwareopdateringer eller ukendt systemtilstand.

Projektdata må kun slettes gennem en eksplicit, autoriseret og auditeret disposition. Ved usikkerhed skal systemet altid vælge at bevare data.

**Bindende regel ved accept:** Ukendt tilstand fortolkes som *bevar*, aldrig som *slet*. Det gælder blandt andet ved ukendt upload-, arkiv-, checksum-, databasekonsistens-, ejerskabs-, projektrelations- eller retentionstatus.

## 5. Princip 3 — Retain until explicit disposition

Projektdata bevares, indtil en autoriseret bruger aktivt vælger en disposition:

1. Behold på aktiv storage.
2. Eksportér.
3. Arkivér.
4. Slet eksplicit.

Eksport eller arkivering må ikke automatisk udløse sletning af originaldata. Frigivelse af aktiv lagerplads skal være en separat handling efter gennemført og verificeret eksport eller arkivering.

## 6. Princip 4 — Projektlivscyklus er en kernefunktion

Alle projekter skal have en eksplicit lifecycle-state. Anbefalede tilstande er:

`planned` · `commissioning` · `active` · `paused` · `completed` · `archived` · `deletion_pending` · `deleted`.

Tilstandsændringer skal være autoriserede, auditerede, tidsstemplede, reversible hvor muligt og bundet til en ansvarlig bruger eller systemidentitet. `completed` betyder ikke slettet eller arkiveret; kun at aktiv indsamling er afsluttet.

## 7. Princip 5 — Afslutning af et projekt er en styret proces

Funktionen **Afslut projekt** skal:

1. Stoppe eller deaktivere fremtidige planlagte captures.
2. Afslutte åbne capture-jobs kontrolleret.
3. Kontrollere manglende eller inkonsistente data.
4. Registrere tidspunkt og ansvarlig bruger.
5. Gøre projektet read-only som standard.
6. Præsentere dispositionerne Behold, Eksportér, Arkivér og Slet.

Behold markerer projektet afsluttet uden at flytte data. Eksport opretter en komplet transportabel pakke. Arkivér kopierer og verificerer projektet til en defineret arkivplacering. Slet er en særskilt destruktiv arbejdsgang med skærpet autorisation.

## 8. Princip 6 — Destruktive handlinger kræver særlig kontrol

Sletning er en højrisikohandling. Sletning af et projekt skal mindst kræve afsluttet projektstatus, privilegeret rolle, reautentifikation, MFA hvor aktiveret, visning af den præcise konsekvens, indtastning af projektnavn eller -ID, obligatorisk begrundelse og permanent auditregistrering.

Det skal være muligt at indføre four-eyes-godkendelse for særligt regulerede kunder eller projekter. Auditregistreringen af sletningen må ikke slettes sammen med projektet.

## 9. Princip 7 — Originalen er autoritativ

Originale captures bevares uændret. Thumbnails, previews, beskæringer, farvekorrektioner, AI-analyser, tags, rapporter, videoer, timelapse-film og komprimerede eksportkopier er separate eller afledte data og må aldrig overskrive originalen.

Alle transformationer skal kunne spores til kildefil, tidspunkt, værktøj eller model, softwareversion, konfiguration og ansvarlig aktør.

## 10. Princip 8 — Integritet skal kunne dokumenteres

Kritiske filer og eksportpakker skal kunne integritetsverificeres. Som minimum bør systemet understøtte SHA-256 for originale captures, manifest over forventede filer, filstørrelse, capture-tidspunkt, projekt-ID, device-ID, kamerareference og arkiv-/eksportstatus.

En eksport eller arkivering er først verificeret, når alle forventede filer er kopieret, checksums matcher, manifestet er komplet, destinationen kan læses og processen er dokumenteret i auditloggen.

## 11. Princip 9 — Evidens og fortolkning skal adskilles

Originale observationer holdes adskilt fra efterfølgende fortolkning. Et billede er en observation; AI-tags, beskrivelser, afvigelsesvurderinger og anbefalinger er fortolkninger. Systemet må ikke præsentere en AI-vurdering som observeret kendsgerning.

Eksempel på den sporbare kæde:

1. Observation: billedets skarphedsscore er faldet over syv dage.
2. AI-forslag: linsen kan være snavset.
3. Menneskelig vurdering: en servicetekniker bekræfter snavs på frontglasset.
4. Handling: linsen rengøres.
5. Resultat: skarphedsscoren normaliseres.

## 12. Princip 10 — AI er rådgiver, ikke autoritet

AI kan anvendes til klassifikation, anomalidetektion, sammenligning, opsummering, fejlsøgningsforslag, eksponeringsanbefalinger og sandsynlige fejlårsager.

AI må ikke uden eksplicit, afgrænset delegation slette data, ændre kritiske kameraindstillinger, aktivere/deaktivere sikkerhedskontroller, udsende firmware, give permanente rettigheder, lukke et projekt eller godkende en destruktiv disposition. Konsekvensfulde handlinger skal have menneskelig ansvarlighed og audit.

## 13. Princip 11 — Fail-safe frem for fail-open

Ved fejl bevarer systemet den sikreste kendte tilstand:

- Hvis brugerens rolle ikke kan valideres, afvises handlingen.
- Hvis arkivstatus er ukendt, bevares originaldata.
- Hvis fysisk serviceaktivering udløber, lukkes servicekanalen.
- Hvis en Bluetooth-session mister autorisation, afbrydes privilegeret adgang.
- Hvis hardwareinterfacet ikke kan identificeres sikkert, aktiveres GPIO ikke.
- Hvis en opdateringssignatur ikke kan verificeres, installeres opdateringen ikke.

## 14. Princip 12 — Least privilege og explicit authority

Alle brugere, tjenester, moduler og hardwarefunktioner skal have mindst mulige rettigheder. En servicetekniker behøver ikke automatisk adgang til alle kunder, projekter, billeder, brugeradministration, permanent konfiguration, cloud credentials eller rå databaseskemaer.

Rettigheder gives til bestemt device, projekt og formål, i et bestemt tidsrum og med en bestemt rolle, og de skal kunne tilbagekaldes øjeblikkeligt.

## 15. Princip 13 — Fysisk nærhed er ikke autentifikation

Bluetooth-rækkevidde eller fysisk nærhed er kun én sikkerhedsfaktor. En Bluetooth-forbindelse må ikke i sig selv give administrativ adgang.

Sikker lokal service kombinerer fysisk aktivering, krypteret parring, identificeret device, brugerautentifikation, rollebaseret autorisation, sessionsudløb, audit og begrænsning af handlinger.

## 16. Princip 14 — Alle betydelige handlinger skal være auditerbare

Systemet registrerer hvad der skete, hvornår, hvilket device/projekt handlingen vedrørte, hvem eller hvad der udførte den, anvendt autorisation og begrundelse, resultat samt systemtilstand før og efter.

Auditloggen skal være manipulationsresistent og ikke redigerbar for almindelige brugere.

## 17. Princip 15 — Konfiguration er en styret og versioneret ressource

Konfiguration behandles som data med lifecycle og provenance. Konfigurationsændringer skal have versionsnummer, timestamp, actor, tidligere og ny værdi, scope, valideringsstatus, rollbackmulighed og kilde (lokal, headend, default eller payload).

Systemet bør undgå spredte konfigurationsfiler uden fælles ejerskab og validering.

## 18. Princip 16 — Platform og payload skal holdes adskilt

Dette princip er konsistent med den accepterede ADR-001. Platformen ejer device identity, provisioning, autentifikation, RBAC, audit, konfiguration, OTA/update, telemetri, health, lokal serviceadgang, remote access, storage services, HAL, secrets og policy enforcement.

Timelapse-payloaden ejer kameraopdagelse, capture, eksponering, fokus, capture-planer, billedmetadata, timelapse-specifik billedbehandling/generering, kameradiagnostics og payload-specifik AI-analyse.

Bluetooth-serviceløsningen er derfor en platformservice; eksempelvis *tag testbillede* og *vis fokusstatus* er payload-capabilities.

## 19. Princip 17 — Hardware skal tilgås gennem en HAL

Applikationskode må ikke være direkte afhængig af Orange Pi SYSFS-numre, Raspberry Pi BCM-numre, fysiske pin-numre, bestemte relæboards, modemtyper eller kameramodeller. Hardwareadgang går gennem et versioneret Hardware Abstraction Layer (HAL).

Et hardwaremanifest kan beskrive logiske capabilities frem for rå pins:

```json
{
  "board": "orange-pi-4-pro",
  "capabilities": {
    "camera_power": {
      "driver": "gpio-relay",
      "logical_name": "camera_power",
      "gpio_backend": "sysfs",
      "gpio_number": 356,
      "active_low": false
    }
  }
}
```

UI og serviceportal refererer til logiske capabilities; rå backendoplysninger hører alene hjemme i avanceret diagnose.

## 20. Princip 18 — Moduler skal have eksplicitte kontrakter

Alle moduler skal have stabil identitet, semantisk version, capability manifest, input-/outputkontrakter, deklarerede rettigheder, health-status, dependency-liste, audit-hooks, lifecycle hooks og failure behaviour.

Et modul må ikke få bred platformadgang blot ved at være installeret.

## 21. Princip 19 — Teknologi skal kunne erstattes

Projektdata, sikkerhedsmodel og kerneviden må ikke afhænge af én cloudleverandør, AI-model, kameraleverandør, SBC-type, databaseklient eller transportprotokol. Udskiftning skal ske gennem versionerede interfaces og migrerbare dataformater.

## 22. Princip 20 — Engineering continuity

Kritisk systemviden må ikke kun eksistere i en udviklers hukommelse, en chatsession, ucommittet kode, ét device, én database eller én AI-models kontekst. Beslutninger, kontrakter, testresultater og operationelle procedurer skal leve i kontrollerede, reviewbare og genoprettelige artefakter.

## 23. Princip 21 — Sikkerhed er integreret, ikke tilføjet

Sikkerhed indgår i arkitektur, UI, hardwaredesign, provisioning, service, opdatering, projektlivscyklus, datahåndtering, fejlhåndtering, AI-brug og leverandørstyring. Den reduceres ikke til firewall, kryptering eller login.

## 24. Princip 22 — Standarder anvendes risikobaseret

SABSA, ISO/IEC 27001, IEC 62443, CRA, GDPR, NIS2 og AI Act bruges som design- og kontrolrammer. De må ikke være afkrydsningslister uden forbindelse til aktiver, trusler, konsekvenser, ansvar, systemgrænser, trust boundaries, lifecycle og evidens.

## 25. Princip 23 — Observability skal understøtte beslutninger

Observability skal ud over CPU, RAM og disk vise capture-kontinuitet, forventet næste capture, kameraets faktiske tilstand, konfigurationsdrift, dataintegritet, storage-vækst og kapacitetshorisont, upload backlog, modemstabilitet, servicehistorik, software-/firmwarestatus, sikkerhedstilstand og billedkvalitetstendenser.

Målet er at understøtte den beslutning, en operatør eller tekniker skal træffe.

## 26. Princip 24 — Alarmer repræsenterer tilstande

En vedvarende fejl skal ikke skabe en ny alarm hvert tiende minut. Alarmer har lifecycle:

`normal` → `firing` → `acknowledged` → `suppressed` → `resolved`.

Notifikationer sendes ved overgang til `firing`, konfigureret reminder, eskalation og resolution. Alarmtilstand skal være persistent på tværs af restart og workers.

## 27. Princip 25 — Testbarhed er en arkitekturegenskab

Væsentlige funktioner skal kunne testes uden hele det fysiske miljø. HAL, kamera-driver, modem-driver, storage og Bluetooth-service skal tilbyde mock drivers, simulatorer, deterministiske fejltilstande, contract tests, security tests og recovery tests.

En funktion, som ikke kan testes sikkert og reproducerbart, er ikke færdigdesignet.

---

# Del II — Secure Local Service Architecture

## 28. Formål med lokal serviceløsning

Den lokale serviceløsning gør det muligt for en autoriseret tekniker at installere, konfigurere, diagnosticere og vedligeholde en edge-enhed på stedet — også uden internet/modem, før fuld provisionering og uden en permanent åben lokal administrationskanal.

Bluetooth og Wi-Fi er transport for discovery, bootstrap og lokal adgang; de er ikke i sig selv applikations- eller autorisationsmodellen.

## 29. Arkitekturplacering

Lokal service implementeres som en platformservice med arbejdstitlen **Local Service Gateway**, uafhængig af payload.

| Platformansvar | Payloadansvar |
|---|---|
| Bluetooth-advertising, fysisk aktivering, pairing, session management, device identity, autentifikation, RBAC, audit, rate limiting, transportkryptering, service-tokenvalidering, lokal portal og policy enforcement | Kamerastatus, testcapture, preview, fokus, eksponeringsdata, payload-logs, payloaddiagnostics og payload-servicehandlinger |

Payloaden registrerer service-capabilities gennem et versioneret manifest.

## 30. Foreslået komponentmodel

```text
Technician PC / Mobile
        │ Bluetooth LE / Wi-Fi
        ▼
Bluetooth Transport Adapter / Wi-Fi
        ▼
Local Service Gateway
  ├── Physical Presence Controller
  ├── Device Identity / Session Manager
  ├── Authentication Provider / RBAC / Policy Engine
  ├── Audit Service / Diagnostic Orchestrator
  ├── Update Service Adapter / HAL Service Adapter
  └── Payload Service Adapter
             ▼
     TimeLapse Payload Driver
       ├── Camera / Capture / Preview
       └── Focus / Image Quality
```

## 31. Fase 1 — Bluetooth og Wi-Fi Service Framework

### 31.1 Bluetooth LE Service

Administrationsservicen annonceres kun, når lokal service er aktiveret. I normal drift er der ingen åben pairing, generisk administrationsadvertising eller permanent discoverable mode. I service-mode er advertising tidsbegrænset, profilen begrænset, device-ID unikt, challenge sessionsspecifik og udløbet automatisk.

### 31.2 Unikt device-ID

Device-ID er stabilt, unikt og bundet til provisioneret identitet. Bluetooth-navnet må ikke indeholde kundenavn, projektadresse, e-mail, interne relationsafslørende serienumre eller hemmeligheder. Et navn som `TLP-C87FF9587CA0` kan kobles til CMDB og fysisk label/QR-kode.

### 31.3 Fysisk serviceaktivering

Pairing og privilegeret service starter kun efter fysisk handling: serviceknap, langt tryk på eksisterende knap, nøglekontakt, NFC-tag eller autoriseret lokal konsolhandling.

Anbefalet standard: hold serviceknappen inde i tre sekunder; LED viser servicevindue; advertising åbnes i fem minutter; eksisterende sessioner kan fortsætte i begrænset tid; ny pairing afvises efter udløb.

### 31.4 Automatisk timeout

Der skelnes mellem pairing window, idle timeout, maksimum sessionslængde og privilegeret operation timeout. Forslag: pairing 5 minutter, idle 10 minutter, session 30 minutter, ny godkendelse af privilegeret operation efter 5 minutter og konfigurerbar offline service-tokenlevetid (fx 8 timer).

### 31.5 Pairing

Prioriteret parring: LE Secure Connections med numeric comparison, sessions-/device-specifik passkey, out-of-band QR/NFC, og kun i snævert bootstrap-scenarie Just Works med fysisk aktivering og efterfølgende applikationsautentifikation. Fast universel PIN er forbudt. Pairing giver aldrig alene administrativ autorisation.

### 31.6 Audit

Audit dækker åbnet servicevindue og aktiveringsmetode, pairing-forsøg/resultat, klientidentitet, bruger og rolle, sessionsstart/-slut, handlinger/ændringer samt timeout/tvungen afbrydelse. Bluetooth MAC-adresser behandles forsigtigt, fordi klienter kan randomisere dem.

## 32. Fase 2 — Lokal Service Portal

Bluetooth bør etablere sikker lokal kanal til en serviceportal eller et struktureret service-API. Muligheder er BLE GATT-baseret bootstrap til HTTPS via Bluetooth PAN/Wi-Fi Direct, kompakt BLE RPC, eller BLE til discovery/tokenudveksling efterfulgt af lokal HTTPS.

For preview, logs og opdateringspakker anbefales BLE primært til discovery, proof of physical presence, bootstrap og credential exchange. Selve portalen anvender derefter midlertidig, krypteret IP-kanal. BLE alene er uegnet til store logfiler, billeder og pakker.

## 33. Serviceportalens funktioner

### 33.1 Status

Vis device-ID, hostname, boardtype, uptime, CPU/systemtemperatur, RAM, storage, servicestatus, seneste Headend-kontakt, klokkeslæt/tidsdrift, softwareversion, provisioning-status og security posture.

### 33.2 Kamera

Vis detekteret model, serienummer hvor tilladt, USB, strømstatus, fokus-/eksponeringsmode, opløsning, seneste/næste capture og seneste fejl. Rolleafhængige handlinger: genopdag kamera, tag testbillede, hent live preview, genstart forbindelse og test power-relæ.

### 33.3 Modem

Vis model, signal, netværksregistrering, operatør, IP-status, uptime, genstarter, fejl og databrug. Tillad connectivity/DNS-test, ping til forhåndsdefinerede endpoints, modemgenstart og power-relætest. Relægenstart kræver cooldown og beskyttelse mod cyklusser.

### 33.4 GPIO-test

UI viser logiske funktioner som Kamera-strøm, Modem-strøm, Service-LED og Serviceknap — ikke primært rå GPIO-numre. Hver test kontrollerer capability manifest, boardprofil og rolle; advarer om konsekvens; kræver bekræftelse; begrænser aktiveringstid; logger før-/eftertilstand; og vender automatisk tilbage til safe state.

### 33.5 Live preview

Preview er rollebeskyttet, kortvarigt, viser timestamp/device-ID, lagres ikke som standard, auditeres, rate-/opløsningsbegrænses og stopper ved session timeout. Privacy- og kundepolitik håndhæves hvor personer kan være synlige.

### 33.6 Logfiler og diagnostic bundles

Portalen tilbyder filtreret logvisning, redigeret diagnostic bundle, tidsinterval, projekt/device-scope og checksums. Logs slettes ikke automatisk; ældre logs kan komprimeres og flyttes til konfigureret backupplacering kun gennem defineret, auditeret proces.

### 33.7 Softwareversion og opdateringer

Vis installeret payload-/platform-/firmwareversion, seneste opdatering, signaturstatus, rollout channel og rollbackmulighed. Offline-opdateringer er signeret, verificeret, kompatibilitetskontrolleret, har rollbackplan, auditeres og kræver passende rolle.

### 33.8 Netværksdiagnostik

Tilbyd kun sikre, forhåndsdefinerede tests: interface/IP/gateway, DNS, TLS til Headend, certifikat, clock skew, modem, routing og latenstid. Der eksponeres ikke vilkårlig shell i normal service-mode.

## 34. Rollemodel for lokal service

| Rolle | Må | Må ikke |
|---|---|---|
| **Observer** | status, versionsoplysninger, health, begrænset diagnostic bundle | konfigurere, aktivere relæ, genstarte service eller installere software |
| **Technician** | godkendte diagnostiske tests, testcapture, preview, interface-genstart, ikke-kritiske lokale indstillinger | højrisiko-konfiguration og update |
| **Senior Technician** | hardwarebinding, provisioning, signerede offline-opdateringer, kontrolleret rollback | policy- og sikkerhedsadministration uden særskilt rolle |
| **Security Administrator** | servicepolitikker, token-revocation, security audit, lokal serviceidentitet, særlige undtagelser | payload-/projektstyring uden relevant scope |
| **Platform Administrator** | platformomfattende ansvar | undtagelse fra audit, MFA eller separation of duties |

## 35. Fase 3 — AI Service Assistant

AI-assistenten arbejder på observationer og telemetri og leverer forslag med evidens. Et fokusforslag viser fx skarphedsfald, tidsperiode, sammenligningsgrundlag, berørte billeder, alternative årsager, usikkerhed og anbefalet menneskelig test — ikke blot en kategorisk fejltekst.

Et eksponeringsforslag viser forventet effekt og rollbackværdi, kræver menneskelig godkendelse, logges og kan afprøves som testcapture.

## 36. AI-governance

Materielle AI-forslag registrerer model og version, execution environment, inputreferencer, analysetidspunkt, prompt/opgavedefinition, confidence, alternative forklaringer, menneskelig disposition, efterfølgende handling og observeret resultat. AI-output blandes aldrig med originale observationer.

## 37. Fase 4 — Enterprise Service Management

### 37.1 TimeLapse-brugeridentitet

Når Headend er tilgængelig, autentificerer teknikeren med normal TimeLapse-identitet. Headend udsteder kortlivet device-specifikt service-token med bruger-ID, rolle, device-ID, tilladte capabilities, udløb, token-ID, issuer, audience, offline-tilladelse og policyversion.

### 37.2 Midlertidige service-tokens

Tokens er kortlivede, device- og purpose-bound, revocable, auditerede, digitalt signerede og replaybeskyttede. Et token til kameratest giver ikke update- eller netværkskonfigurationsadgang.

### 37.3 Offline service-mode

Offline service kan bygge på forudstedt token, engangskode fra Headend, fysisk servicekort med hardware-backed nøgle eller autoriseret companion-app med secure storage. Tokenet er tids-/scopebegrænset, device-bound, underlagt revocation ved næste synkronisering, lokal audit og fysisk serviceaktivering.

### 37.4 Synkronisering af servicehistorik

Ved gendannet forbindelse synkroniseres sessioner, tests, ændringer, før-/efterværdier, opdateringer, AI-forslag, teknikerdispositioner, diagnostic bundles og offline-policyafvigelser. Headend bør opdage manglende sekvensnumre/tidshuller, manipuleret audit, ukendt tekniker og uautoriseret serviceaktivitet.

## 38. Lokal service og IEC 62443

Local Service Gateway behandles som en kontrolleret maintenance access path. Den understøtter identification/authentication control, use control, integrity, confidentiality, restricted data flow, timely event response og resource availability. Kanalen er normalt deaktiveret og åbnes efter fysisk handling; den må ikke skabe permanent conduit fra ukendt teknikernetværk til kontrolsystemet.

## 39. Lokal service og ISO/IEC 27001

Løsningen understøtter risikobaserede kontroller inden for asset management, identity/access control, authentication information, logging, monitoring, configuration/change management, information deletion, backup, secure maintenance og supplier/service access.

## 40. Lokal service og CRA

Arkitekturen understøtter secure-by-design/default, begrænset attack surface, autentificerede opdateringer, sårbarhedshåndtering, audit/hændelsesdetektion, beskyttelse mod uautoriseret adgang og sikker lifecycle management. Permanent åben Bluetooth-administration er i modstrid med denne retning.

## 41. Lokal service og SABSA

Sentrale business attributes er Availability, Accountability, Auditability, Authenticity, Integrity, Confidentiality, Reliability, Maintainability, Recoverability, Traceability, Safety, Privacy og Longevity.

Trust boundaries omfatter tekniker ↔ companion-app ↔ Bluetooth transport ↔ Local Service Gateway ↔ platformservice ↔ HAL/payload samt edge ↔ Headend og offline-token ↔ lokal policy/audit. Hver overgang skal have eksplicit identitet, autorisation og audit.

## 42. Capability manifest

Payload og platformservices beskriver servicefunktioner maskinlæsbart:

```json
{
  "module_id": "timelapse-camera",
  "version": "1.0.0",
  "service_capabilities": [
    {
      "id": "camera.status.read",
      "risk": "low",
      "roles": ["observer", "technician"]
    },
    {
      "id": "camera.preview.start",
      "risk": "medium",
      "roles": ["technician", "senior_technician"],
      "max_duration_seconds": 120
    },
    {
      "id": "camera.power.cycle",
      "risk": "high",
      "roles": ["technician", "senior_technician"],
      "requires_physical_presence": true,
      "cooldown_seconds": 300
    }
  ]
}
```

Gatewayen eksponerer kun capabilities, der findes i manifestet, matcher installeret version, tillades af lokal policy/rolle og understøttes af hardwareprofilen.

> **Terminologisk afgrænsning for Mission Timelapse:** Et *runtime capability manifest* er her en teknisk kontrakt for autorisation, isolation og hardware-/serviceadgang. Det må ikke forveksles med Mission Frameworks kanoniske begreb *Capability* (evnen til at skabe en effekt). Runtime-manifestet er en TimeLapse-/platformmekanisme, ikke en ny Mission Core-definition.

## 43. API-principper

Service-API’et er versioneret, typed, deny-by-default, idempotent hvor muligt, rate-limited, auditeret og dokumenteret — uden vilkårlig command execution.

Eksempler:

```text
GET  /service/v1/device/status
GET  /service/v1/capabilities
GET  /service/v1/camera/status
POST /service/v1/camera/test-capture
POST /service/v1/hardware/camera-power/test
GET  /service/v1/network/diagnostics
POST /service/v1/update/validate
POST /service/v1/update/install
GET  /service/v1/audit/session
```

Et `POST /run-command`-endpoint findes ikke i almindelig service-mode.

## 44. Diagnostic bundles

En servicepakke kan struktureres sådan:

```text
diagnostic-bundle/
├── manifest.json
├── device.json
├── hardware.json
├── software.json
├── health.json
├── network.json
├── camera.json
├── modem.json
├── configuration-redacted.json
├── logs/
├── audit/
└── checksums.sha256
```

Pakken redigerer secrets, begrænser persondata, har scope/tidsinterval/checksum/eksportøridentitet, er auditeret og kan importeres i Headend til supportanalyse.

## 45. Trusselsmodel

| Trussel | Centrale kontroller |
|---|---|
| Uautoriseret pairing | Ikke normalt discoverable, fysisk aktivering, kort window, secure pairing, applikationsauth, audit, rate limit |
| Stjålet teknikerenhed | Kortlivede device-bound tokens, secure storage, reauth, revocation, ingen universelle credentials |
| Replay | Nonce, challenge-response, korte tokenlevetider, token-ID, sequence numbers og session binding |
| Rogue payload-modul | Signerede moduler, manifest, procesisolation, least privilege og ingen platformsecrets |
| Misbrug af GPIO-test | Logiske capabilities, rolle/fysisk tilstedeværelse, max varighed, cooldown, safe state og audit |
| Uautoriseret preview | Rolle, timeout, privacy policy, watermark/device-ID, ingen standardlagring og audit |
| Manipuleret offline-update | Signatur, trusted root, versionspolicy, anti-rollback hvor relevant, kompatibilitet, rollback og audit |

## 46. Anbefalet implementeringsrækkefølge

### Trin 0 — Forudsætninger

Før Bluetooth-kode: færdiggør platform/payload-kontrakt, identificér HAL, dokumentér hardwareprofiler, fastlæg service-roller, auditformat, capability manifest og Local Service Gateway trust boundary.

### Trin 1 — Service-mode uden Bluetooth

Implementér gateway og service-API lokalt på loopback eller Unix socket. Test RBAC, policies, audit, capabilities, HAL, payload-adapter, timeout og diagnostic bundle. Dette adskiller sikkerheds-/applikationslogik fra Bluetooth-transporten.

### Trin 2 — Bluetooth bootstrap

Tilføj fysisk aktivering, advertising, pairing, session bootstrap, device identity og timeout.

### Trin 3 — Lokal portal

Tilføj status, kamera, modem, GPIO-test, logs, netværksdiagnostik og softwareversion.

### Trin 4 — Offline identity og tokens

Tilføj service-/offline-token, device binding, revocation og synkronisering.

### Trin 5 — AI-assistent

Tilføj først AI efter etableret datakvalitet, provenance, observation/fortolkningsadskillelse, human approval og audit.

### Trin 6 — Mission Framework-integration

Modellér TimeLapse som en mission med purpose, accountable roles, objectives, observations, evidence, decisions, actions, outcomes, lifecycle og policies. Returnér generelle erfaringer som Framework Findings; behold TimeLapse-specifikke detaljer i implementeringen.

## 47. Første konkrete repository-analyse før implementering

Før fremtidig implementering kortlægges:

- **Edge:** startup/lifecycle, HAL/GPIO, camera/modem-drivere, lokal config, device identity, token storage, auditbuffer, update, health/telemetry.
- **Headend:** device auth, user RBAC/MFA, token issuance, audit ingestion, CMDB, capability-model, update-signering, servicehistorik og policyconfig.
- **UI:** roller, device pages, diagnostics, config editing, servicehistorik, security events, preview og update-flow.
- **Dokumentation:** ADR-001, platform/payload-plan, RBAC/remote operations, config-hierarki, SABSA, risk assessment, edge runbook, update flow og CRA/IEC 62443-mapping.

## 48. Definition of Done for fase 1

Bluetooth Service Framework er ikke færdigt, før følgende er dokumenteret og testet:

- Service er deaktiveret som standard og kræver fysisk aktivering.
- Pairing window, idle timeout og session timeout håndhæves.
- Device identity vises/verificeres; ingen fast universel PIN anvendes.
- Pairing giver ikke automatisk autorisation; RBAC håndhæves server-side.
- Alle handlinger auditeres; replay- og brute-force-rate-limit-tests er grønne.
- Tabt forbindelse og restart efterlader hardware/sessions i safe state.
- Multi-client-adfærd og recovery/factory-service-procedure er defineret.
- Secrets vises ikke i logs; Bluetooth kan deaktiveres centralt.
- Security review er gennemført og relevante tests kører i CI.

## 49. Kandidater til Architecture Decision Records

Følgende er **ikke** accepterede ADR'er endnu. De bør oprettes som korte, afgrænsede `Proposed` ADR'er efter owner-review, fordi de ændrer flere spor eller har væsentlige sikkerheds-/lifecycle-konsekvenser:

| Foreslået ADR | Beslutningens afgrænsning | Forhold til eksisterende retning |
|---|---|---|
| Local Service Gateway | Lokal service leveres af fælles platformgateway, ikke payload-specifik Bluetooth-service | Udvider ADR-001 uden at ændre snittet |
| Physical Presence Requirement | Pairing og privilegeret lokal service kræver fysisk aktivering | Ny maintenance-access-kontrol |
| Bluetooth as Bootstrap Transport | BLE bruges til discovery/bootstrap; dataintensiv portal bruger lokal krypteret IP | Ny transport-/attack-surface-beslutning |
| Capability-based Service Authorization | Versionerede capabilities, roller og policies styrer serviceadgang | Konkretiserer ADR-001 capability manifest |
| No General-purpose Shell | Normal serviceportal eksponerer aldrig vilkårlig shell/command execution | Ny service-API-afgrænsning |
| Retain until Explicit Disposition | Projektdata slettes ikke automatisk, men kun efter lifecycle-disposition | Kræver eksplicit afstemning med eksisterende retention/circular-buffer-adfærd |

## 50. Afsluttende retning

Den lokale serviceløsning bør beskrives som en **sikker, fysisk aktiveret og auditeret lokal serviceløsning** til installation, diagnosticering og vedligeholdelse af distribuerede TimeLapse-enheder — også uden netværk; ikke blot som Bluetooth-administration.

Den afgørende adskillelse er:

- Bluetooth som transport
- lokal service som platformfunktion
- kamera/timelapse som payload
- AI som rådgivende evidens
- mennesket som ansvarlig beslutningstager.

### Normativ kernesætning

> TimeLapse Pro skal bevare projektets observationer, evidens, konfiguration, beslutninger og historik gennem hele projektets levetid. Systemet må aldrig udføre irreversible handlinger uden eksplicit, autoriseret og auditeret menneskelig beslutning.
