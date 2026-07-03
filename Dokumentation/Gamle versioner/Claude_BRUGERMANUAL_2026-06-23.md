# TimeLapse Pro - Brugermanual

**Dato:** 2026-06-23  
**Målgruppe:** Kunde, site manager, projektleder og almindelig bruger  
**Status:** Pre-production manual. Skærmnavne kan ændre sig lidt, men arbejdsgangen er gældende.

## 1. Login

1. Åbn TimeLapse Pro i browseren.
2. Log ind med brugernavn/e-mail og adgangskode.
3. Hvis MFA er aktivt, indtast koden fra authenticator/WebAuthn.
4. Efter login vises dashboardet med de kameraer og sites, du har adgang til.

Adgang er rolle- og kundestyret. En kunde kan kun se egne sites, kameraer, billeder, tags og rapporter.

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

Thumbnails skal normalt være genereret af edge/headend. Hvis et thumbnail mangler, kan systemet postprocessere det i baggrunden.

## 4. Søgning og tags

TimeLapse Pro bruger engelske canonical tags i backend og viser danske navne i UI'et via en oversættelsestabel.

Du kan søge efter:

- byggeaktiviteter
- vejr og belysning
- billedkvalitet
- dag/nat
- genskin eller modlys
- brugbarhed til timelapse-video

Eksempel:

```text
dagtimer, klart sollys, ingen direkte sol i linsen, høj skarphed
```

AI-tags er hjælpemetadata, ikke juridisk sandhed. Ved vigtige rapporter bør billeder gennemgås manuelt.

## 5. Billedkvalitet

Billeder kan markeres med:

- blur-score
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
4. Start eksport.
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

## 8. Kendte begrænsninger

- AI-tags kan være ufuldstændige på historiske billeder, indtil postprocessering er kørt færdig.
- Retention og GDPR-adgangslog er ikke fuldt implementeret endnu.
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

