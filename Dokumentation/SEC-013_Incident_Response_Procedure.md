# SEC-013: Incident Response Procedure
**Version:** 1.0.0  
**Dato:** 2026-07-07  
**Ansvarlig:** Peter Frøkjær + sikkerhedsansvarlig

---

## 1. Formål

Denne procedure definerer processen for håndtering af sikkerhedshændelser i TimeLapse Pro systemet, i overensstemmelse med GDPR Art. 33 (notifikation til tilsyn) og Art. 34 (notifikation til registrerede).

---

## 2. Incident typer

### 2.1 Kritiske incidents (umiddelbar handling krævet)
- **Databrud:** Uautoriseret adgang til persondata (billeder, GPS, kundeinfo)
- **System kompromitteret:** Malware, root access, ransomware
- **Services ned:** Production system unavailable > 4 timer
- **Data tab:** Uopretteligt tab af produktionsdata

### 2.2 Moderate incidents (handling inden 24 timer)
- **Brud på adgangskontrol:** Mistænkt uautoriseret login forsøg
- **Konfigurationsfejl:** Exponeret secrets eller åbne porte
- **Performance degradation:** System langsomt men fungerende

### 2.3 Lavprioriterede incidents (handling inden 7 dage)
- **False positives:** Sikkerhedsalarm uden reelt brud
- **Mindre konfigurationsfejl:** Ikke-sikkerhedskritisk

---

## 3. Incident Response Process

### 3.1 Detektion og rapportering

**Hvem som helst** kan rapportere et incident via:
- Slack: `#incident-response`
- Email: `security@timelapse-pro.dk`
- Telefon: Peter Frøkjær (hvis kritisk)

**Initialt rapport skal indeholde:**
- Hvad er sket?
- Hvornår blev det opdaget?
- Hvem er berørt?
- Hvad er systemets status nu?

### 3.2 Triage (sker inden 30 minutter)

1. **Verificér incidentet:**
   - Er det et falsk positiv?
   - Er der faktisk data eksponeret?
   
2. **Klassificér severity:**
   - **P0 (Kritisk):** Produktion nede, data lækket, system kompromitteret
   - **P1 (Høj):** Mistænkt data eksponering, performance kritisk
   - **P2 (Medium):** Mindre sikkerhedshændelse
   - **P3 (Lav):** False positive

3. **Escalation:**
   - P0/P1: SMS til alle stakeholders + møde inden 1 time
   - P2/P3: Email + næste hverdag

### 3.3 Inddæmning (Containment)

**For P0/P1 incidents:**
1. Isoler berørte systemer:
   - Tag affected services offline
   - Blokerér mistænkte IP-adresser
   - Skift credentials (JWT_SECRET, API keys)

2. **Bevar evidence:**
   - Tag snapshot af VM/disk
   - Gem logs: `/var/log/`, `/Users/peter/Library/Logs/timelapse-headend.log`
   - Export database state (timelapse_db)

### 3.4 Eradikering

1. **Identificer rodårsag:**
   - Review access logs
   - Tjek for malware
   - Analyser konfigurationsændringer

2. **Fjern trussel:**
   - Patch sårbarhed
   - Skift alle credentials
   - Rebuild fra known-good backup hvis nødvendigt

### 3.5 Gendannelse (Recovery)

1. **Restore fra backup:**
   - Verificér backup integritet før restore
   - Test restore i isoleret miljø
   - Gradvis rollout (rd → staging → prod)

2. **Verifikation:**
   - Kør smoke tests
   - Bekræft ingen backdoors
   - Monitor for 7 dage

### 3.6 Post-Incident aktiviteter

1. **Dokumentation:**
   - Skriv incident rapport (hvordan, hvorfor, hvem)
   - Opdater RISK_ASSESSMENT hvis nye risici fundet

2. **Læring:**
   - Root cause analysis
   - Process forbedringer
   - Træning af team

---

## 4. GDPR Krav (Art. 33 og 34)

### 4.1 Notifikation til Datatilsynet (Art. 33)

**Hvornår:** Ved persondatabrud der udgør en risiko for registreredes rettigheder

**Frist:** Senest 72 timer efter opdagelse

**Process:**
1. Kontakt Datatilsynet: `sdv@sdv.dk` eller `+45 33 19 32 00`
2. Indberet via: https://www.datatilsynet.dk/indberetning

**Information der skal indberettes:**
- Beskrivelse af bruddets karakter
- Kategorier af berørte data
- Antal berørte personer
- Konsekvenser for registrerede
- Tiltag til at afhjælpe brudet

### 4.2 Notifikation til registrerede (Art. 34)

**Hvornår:** Når brudet udgør en **høj risiko** for registreredes rettigheder

**Frist:** Uden unødig forsinkelse

**Risikoindikatorer:**
- Identitetstyveri
- Finansielt tab
- Diskrimination
- Ophævelse af omdømme
- Andre væsentlige ulemper

**Notifikationsmetode:**
- Direkte email til berørte kunder
- Offentlig meddelelse hvis mange berørte

**Information der skal gives:**
- Hvad er sket
- Sandsynlige konsekvenser
- Tiltag til at afhjælpe
- Kontaktinfo for mere information

---

## 5. Kontaktpersoner

| Rolle | Navn | Telefon | Email |
|------|------|---------|-------|
| Produktionsejer | Peter Frøkjær | | peter@froekjaer.dk |
| Sikkerhedsansvarlig | [TBD] | | security@timelapse-pro.dk |
| Juridisk | [Jurist firma] | | |
| Databehandler | [Hver kunde] | | |

---

## 6. Kommunikation

### 6.1 Interne kommunikation

**P0/P1:** Slack `#incident-response` + SMS til alle
**P2/P3:** Email + Slack

### 6.2 Ekstern kommunikation

**Til kunder:**
- Kørselsplan godkendt af Peter
- Tekst: Klar, præcis, uden teknisk jargon

**Til pressen:**
- Kun talsperson (Peter) må udtale sig
- Standard: "Vi kan ikke kommentere på pågående sikkerhedshændelser"

---

## 7. Test af procedure

**Gennemfør mindst en gang om året:**
1. Tabletop øvelse: Hvad gør vi hvis X sker?
2. Restore test: Kan vi faktisk gendanne fra backup?
3. GDPR notifikation test: Kontakt info opdateret?

**Dato for sidste test:** [TBD]
**Dato for næste test:** [TBD]

---

## 8. Referencer

- GDPR Art. 33: Notifikation til tilsynsmyndighed
- GDPR Art. 34: Kommunikation til registrerede
- NIS2: Incident rapporteringskrav for operatører af essentielle tjenester
- `RISK_ASSESSMENT_v10.md`: Risikoer i systemet
- `GO_LIVE_CHECKLIST_v10.md`: Sikkerhedskrav før go-live

---

**Status:** 🟡 Delvist (procedure skrevet, men ikke testet i praksis endnu)
