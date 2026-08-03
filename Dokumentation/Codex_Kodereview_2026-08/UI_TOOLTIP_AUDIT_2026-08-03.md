# UI- og hjælpetekstaudit 2026-08-03

## Princip

Alle navigationspunkter, ikonknapper og konfigurationsfelter skal have en
kort dansk forklaring ved hover/fokus. Hjælp beskriver effekt, risiko og
forventet resultat, ikke kun labelen. Native `title` er minimum; komplekse
felter skal have et synligt `HelpCircle`-ikon med samme indhold.

## Fælles navigation

`timelapse-ui/src/components/Navbar.tsx` er opdateret:

- Admin-menuen og logout har hjælpetekst og tilgængeligt navn.
- Desktop- og mobilnavigation bruger samme beskrivelser.
- Mobilnavigationen bevarer mindst 44 px betjeningsflader.

## Prioriteret matrix

| Område | Status | Næste handling |
|---|---|---|
| Navigation | Delvis afsluttet | Visuel kontrol i autentificeret browser. |
| Kamera, site og kunde | God feltdækning | Ensret sprog og handlingstekster. |
| LAB | God parameterdækning | Dæk ikonknapper og destructive tests. |
| AI | Delvis | Gennemgå model-, pause- og prompt-handlinger. |
| Opdateringer | Delvis afsluttet | Flow, promotion, artifact-bind, rollback og katalogfelter har nu hjælpetekst; visuel E2E mangler. |
| Backup | Mangelfuld | Forklar scope, restore, retention og konsekvenser. |
| CMDB/SBOM | Mangelfuld | Forklar versionfarver, source-of-truth og download. |
| SIEM/Drift | Delvis | Forklar filtre, kildevalg og notifikationer. |
| GRC/Compliance | Delvis | Forklar mapping, rapportgenerering og godkendelse. |
| Brugere/Nøgler | Delvis | Forklar MFA, rotation, tilbagekaldelse. |
| Timelapse video | Delvis | Forklar QA, frame-ekskludering og render. |
| Import/Post-processing/Retention/Redaction | Mangelfuld | Tilføj felt- og knaphjælp. |

## Verifikationsplan

For hver route i `App.tsx` testes i dedikeret testkonto og isoleret miljø:

1. Side åbner på desktop og mobilbredde uden overlap eller klippet tekst.
2. Primære knapper og ikonknapper har hover-/fokushjælp.
3. Formularfelter har label, hjælp og fejltilstand.
4. Handlinger har klar succes-, ventende- eller fejlstatus.
5. Destruktive handlinger har præcis bekræftelse.

Matrixen markeres først PASS efter browser-E2E mod isoleret testmiljø.
