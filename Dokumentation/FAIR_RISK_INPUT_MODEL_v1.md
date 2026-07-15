# TimeLapse Pro - FAIR risk input model v1

## Formål

Modellen gør CMDB, SIEM og Drift klar til kvantitativ risiko efter FAIR-principper uden at præsentere upræcise DKK-tal som fakta. Den nuværende 0-100-værdi er en operationel prioritetsindikator. Den er ikke FAIR eller et forventet tab.

## Datakilder

### Kommercielt input

Platformadministrator registrerer kundens månedlige servicepris med valuta, ikrafttrædelsesdato, kilde og validator. Alle ændringer opretter en ny version. Månedsprisen er en proxy for TimeLapse Pros omsætningseksponering, men er ikke automatisk kundens tab.

### Kundeoplyst forretningsprofil

Kundeadministrator kan indsende:

- produktets eller projektets værdi;
- estimeret nedetidsomkostning pr. dag;
- genskabelsesomkostning;
- kontraktuelle bods- eller erstatningsbeløb;
- forretningsafhængighed fra 1 til 5;
- konsekvens for availability, integrity og confidentiality fra 1 til 5;
- recovery time objective og maksimal tolerabel nedetid;
- persondataniveau;
- antagelser og kontekst.

En indsendt profil har status `submitted`. Kun platformadministrator kan ændre den til `validated` eller `rejected`. En ny valideret version superseder den tidligere, men historikken slettes ikke.

## FAIR-beregning

En egentlig beregning aktiveres først, når følgende er valideret:

1. Threat Event Frequency som min/mest sandsynlig/max pr. år.
2. Vulnerability som min/mest sandsynlig/max sandsynlighed for at hændelsen skaber tab.
3. Primary Loss baseret på driftstab, response, genskabelse og direkte kontraktuelle tab.
4. Secondary Loss baseret på sandsynlig og estimeret regulatorisk, juridisk, omdømme- og kundepåvirkning.

Når datagrundlaget er komplet, kan systemet beregne Loss Event Frequency gange Loss Magnitude og vise årligt tab som P10/P50/P90 i DKK. Indtil da returnerer systemet `needs_input` og viser kun hvilke input der er tilgængelige.

## Governance

- Beløb og risikoprofiler er tenantafgrænsede.
- Månedspris kan kun læses og ændres af platformadministrator.
- Kundeadministrator kan kun indsende profil for egen kunde.
- Platformadministrator validerer eller afviser profilen med note.
- Version, indsender, validator og tidsstempler bevares som audit-evidens.
- SIEM- og ITIM-signaler påvirker operationel prioritet, men må ikke ændre kundens validerede økonomiske input.

## Næste trin

- Definer fælles spørgeguide og beløbsintervaller med forretning og kunder.
- Definer scenarier, eksempelvis langvarig kameranedetid, billedtab, kompromittering og GDPR-hændelse.
- Kalibrer hændelsesfrekvens fra SIEM-, incident- og driftsdata.
- Godkend Monte Carlo-antagelser og rapportformat før DKK-risiko vises som beslutningsgrundlag.
