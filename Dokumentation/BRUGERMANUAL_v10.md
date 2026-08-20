# TimeLapse Pro — Brugermanual (v10, konsolideret)

**Version:** 10 (konsolideret, opdateret 2026-07-12)
**Dato:** 2026-07-02 (opdateret 2026-07-12 med F-012 Site-Wide Look Matching)
**Målgruppe:** Kunde, site manager, projektleder og almindelig bruger
**Status:** Pre-production manual. Skærmnavne kan ændre sig lidt, men arbejdsgangen er gældende.
**Se også:** `MENUGUIDE_BRUGER_v1.md` — menu-for-menu beskrivelse af hver side i UI'en (felt-for-felt). `FAQ_og_fejlsøgning.md` — spørgsmål/svar til de hyppigste problemer.
**Konsoliderer:** `BRUGERMANUAL_2026-06-23.md`, `Claude_BRUGERMANUAL_2026-06-23.md`, `Codex_BRUGERMANUAL_2026-06-23.md` (tidligere versioner arkiveret i `Gamle versioner/`).

## 1. Login

1. Åbn TimeLapse Pro i browseren.
2. Log ind med brugernavn/e-mail og adgangskode.
3. Hvis MFA er aktivt, indtast koden fra authenticator/WebAuthn.
4. Efter login vises dashboardet med de kunder, sites og kameraer, din rolle giver adgang til.

Adgang er rolle- og kundestyret. En kunde kan kun se egne sites, kameraer, billeder, tags og rapporter.

> **Domæner:** Det offentlige website `www.timelapse-pro.dk` er kun et informationssite. Selve produktet (kunde-/admin-UI og API) tilgås via `backend.timelapse-pro.dk`. Login-knapper på det offentlige site redirecter til `https://backend.timelapse-pro.dk/login`.

## 2. Dashboard

Dashboardet bruges til hurtigt overblik:

- aktive kameraer
- seneste billeder
- alarmer eller kvalitetsproblemer
- uploadstatus
- online/offline/stale status
- seneste capture-tidspunkt

Hvis et kamera står som offline/stale, betyder det typisk at Headend ikke har fået frisk heartbeat fra edge-enheden.

## 3. Se billeder

1. Gå til kundens site eller kamera.
2. Brug billedgalleriet til at se thumbnails.
3. Klik på et thumbnail for at åbne billedet i fuld størrelse.
4. Brug dato-/tag-/kvalitetsfiltre til at finde relevante billeder.

Thumbnails skal normalt være genereret af edge/headend. Hvis et thumbnail mangler, kan systemet postprocessere det i baggrunden (administrator kan starte postprocessing).

## 4. Søgning og tags

TimeLapse Pro bruger engelske canonical tags i backend og viser danske navne i UI'et via en oversættelsestabel.

Du kan søge efter:

- byggeaktiviteter
- vejr og belysning
- billedkvalitet
- dag/nat
- genskin eller modlys
- regn eller dårligt lys
- brugbarhed til timelapse-video

Eksempel:

```text
dagtimer, klart sollys, ingen direkte sol i linsen, høj skarphed
```

AI-tags er hjælpemetadata, ikke juridisk sandhed. Ved vigtige rapporter bør billeder gennemgås manuelt.

## 5. Billedkvalitet

Billeder kan markeres med:

- blur-/fokus-score
- over-/undereksponering
- kvalitetsadvarsel
- mulig kamera-/fokusdrift
- upload- eller analysefejl

Hvis et kamera gentagne gange giver dårlige billeder, skal en administrator bruge LAB-funktionen til at teste fokus, live preview og kamerakonfiguration.

## 6. Timelapse-video

Når videoeksport er aktiveret:

1. Vælg kamera.
2. Vælg datointerval.
3. Filtrér eventuelt på tags, dagtimer, belysning eller kvalitet.
4. Start eksport / generer video.
5. Download den færdige video.

Status pr. 2026-06-23: videoeksport er et kendt krav, men ikke vurderet som fuldt production-ready i kravregisteret.

## 7. Rapporter

Compliance-/GRC-rapportering er primært for administratorer, men kunder kan på sigt få adgang til rapporter pr. standard:

- SABSA
- ISO 27001
- IEC 62443
- NIS2
- CRA
- GDPR

Rapporter skal baseres på CMDB, update evidence, backup evidence, adgangslogs og kundens/siteets konfiguration.

### 7.1 Compliance- og backup-status

I Compliance- og Backup/Resilience-sektionerne kan administratorer følge den aktuelle operationelle status for systemet. Når der endnu ikke er indsamlet evidence, vil UI'et vise en tydelig "ikke tilgængelig/ikke data endnu"-tilstand i stedet for at virke som om status er uklar eller fejlet. Det gør det lettere at skelne mellem "ikke udført endnu" og "fejlet".

### 7.2 Retention Policy (GDPR G-02)

TimeLapse Pro har automatiseret retention policy for at overholde GDPR krav om begrænset opbevaring af persondata.

**Adgang (administrator):**
1. Gå til **Retention** i menuen (kræver admin/super_admin rolle).
2. Du ser tre tabs:
   - **Status**: Viser om cleanup kører, progress log og antal slettede captures.
   - **Indstillinger**: Konfigurer hvor ofte automatisk cleanup skal køre (manuel/dagligt/ugentligt/månedligt).
   - **Sletningslog**: Revisionslog over alle slettede captures med detaljer.

**Per-kamera retention:**
- Hvert kamera har sin egen `retention_days` værdi (default: 365 dage).
- Ændr dette via kamera-konfigurationssiden under "Kamera identitet" → "Retention (dage)".
- Billeder ældre end det konfigurerede antal dage slettes automatisk ved næste cleanup.

**Manuelt trigger:**
- Klik "Start retention cleanup nu" i Status-tab for at køre cleanup med det samme.
- Sletning er permanent — en log gemmes til compliance-formål.

**Sikkerhedsnoter:**
- Sletning er permanent. Billeder kan ikke gendannes efter sletning.
- Alle sletninger logges med capture_id, kamera, device, filename, sletningstidspunkt, årsag og hvem der udførte slettet.
- Retention kan sættes til `NULL` for at deaktivere automatisk sletning for et specifikt kamera.

### 7.3 Site-Wide Look Matching (F-012)

Site-Wide Look Matching sikrer at alle kameraer på et site producerer timelapse-videoer med ensartede farver og eksponering. Det betyder at du frit kan klippe mellem forskellige kameravinkler uden synlige farveforskelle.

**Hvordan virker det?**
1. **Golden Reference** — En enkelt capture bruges som farvestandard for hele sitet
2. **Per-Camera LUTs** — Hvert kamera får sin egen farvetransformation (LUT)
3. **Capture Hints** — Kameraet får anbefalinger til optimal indstilling

**I praksis:**
1. Gå til **Devices** → vælg kamera
2. Kig i **Site-Wide Look Matching** kolonnen (kolonne 5)
3. Hvis du ser "Mangler Site Reference":
   - Tag et nyt billede med god belysning
   - Klik "Opret Site Reference" når billedet har quality >= 75%
4. Når reference findes:
   - Klik "Regenerer Kamera LUT"
   - Følg anbefalingerne i "Capture Hints" sektionen

**Capture Hints viser:**
- Anbefalet Picture Control (Nikon) eller Picture Style (Canon)
- White Balance temperatur (Kelvin)
- Eksponering kompensering (EV)
- Forventet match kvalitet (0-100%)

**Kamera-specifikke anbefalinger:**

*Nikon Z30 (Flat for timelapse):*
- Picture Control: Flat
- Skarphed: 3, Kontrast: 0, Mætning: 0

*Canon EOS 1300D/2000D (Neutral for timelapse):*
- Picture Style: Neutral
- Skarphed: 2, Kontrast: 1, Mætning: 1

**Match quality skala:**

| Score | Kvalitet | Beskrivelse |
|-------|----------|-------------|
| 90-100% | 🟢 Fremragende | Ingen synlig forskel |
| 75-89% | 🔵 God | Minimal forskel, acceptabel |
| 60-74% | 🟡 Acceptabel | Synlig forskel, post-processing hjælper |
| < 60% | 🔴 Dårlig | Betydelig forskel, manuel korrektion nødvendig |

**Tips til bedste resultat:**
- Undgå harsh middagssol (for meget kontrast)
- Brug manuelt white balance (ikke auto)
- Sikre at alle kameraer har lignende belysning
- Hold Picture Control/Style konsekvent (Flat/Neutral)

## 8. Kendte begrænsninger

- AI-tags kan være ufuldstændige på historiske billeder, indtil postprocessering er kørt færdig.
- GDPR-adgangslog er delvist implementeret (se Retention Policy for sletningslog).
- MFA/WebAuthn er planlagt som krav før moden flerbrugerdrift.
- Nikon Z30 LAB/fokusfunktioner er delvist implementeret, men ikke endeligt production-hærdet.

## 9. Hvad gør jeg ved fejl?

Kontakt administrator hvis:

- kameraet står offline/stale
- der mangler billeder
- thumbnails ikke vises efter længere tid
- billedkvaliteten falder
- tags virker åbenlyst forkerte
- du ikke kan logge ind
- du ser data fra en forkert kunde eller et forkert site

Ved mulig datalækage eller forkert adgang skal det behandles som sikkerhedshændelse.
