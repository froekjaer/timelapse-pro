# Uafhængig 3.-parts Assessment — TimeLapse Pro (2026-07)

- **Assessor:** Claude (uafhængig session, uden binding til tidligere designvalg i repoet)
- **Dato:** 2026-07-31
- **Vurderet commit:** `eed9e3c8c67369e1924c25a11908616220c3c753` (HEAD på `main` ved assessment — identisk med REVIEW-001-baseline; ingen drift siden)
- **Formål:** Beslutningsgrundlag før (1) installation af headend på rigtig prod-server, (2) generering af ny edge til den virkelige verden, (3) 1. version af det modulære framework.

## Dokumentspor

| Dokument | Indhold |
|---|---|
| `01_Sikkerhedsfund.md` | Sikkerhedsfund TPA-01.. med evidens (fil:linje), severity og anbefaling |
| `02_Kodekvalitet_Struktur_TekniskGaeld.md` | Struktur, memory-/ressource-mønstre, teknisk gæld, moderne kodestandard |
| `03_Hardkodede_Variable_Inventar.md` | Inventar over hardkodede værdier målt mod reglen "alt konfigurerbart i UI + DB, kun opstartsparametre i .env" |
| `04_UI_UX_Gennemgang.md` | UI-menuer: struktur, ensartethed, fejl/mangler, brugervenlighed |
| `05_Compliance_Vurdering.md` | Måling mod standarderne i Compliance Cockpit → "Regler og Standarder" |
| `06_Arkitekturvej_Modulaert_Framework_v1.md` | Arkitekturvej til modulært framework v1 jf. Mission Framework-empirien |
| `07_Prioriteret_Handlingsplan.md` | Prioriteret plan frem mod staging-test, prod-headend og ny edge |

## Metode og dækning (ærlig deklaration)

Kodebasen er ~95.000 linjer Python (headend/edge/tests/tools), ~28.000 linjer TypeScript (UI) og 173 dokumentationsfiler. Ingen gennemgang kan meningsfuldt læse hver linje i én session, og en assessment der påstår det, bør afvises. Metoden her er den, en professionel ekstern audit ville bruge:

1. **Fuld automatiseret sweep af hele kodebasen** (100% af tracked filer): farlige mønstre (subprocess/eval/pickle/MD5/verify=False), SQL-opbygning, CORS/cookie/JWT-håndtering, secrets, hardkodede IP'er/domæner/stier/porte, module-level caches, tråd-/loop-mønstre, env-variabel-inventar.
2. **Kørsel af projektets egne governance-gates** (arkitektur-ratchet, route-auth-sweep) på HEAD i rent miljø, samt kontrol af CI-historik via GitHub API.
3. **Målrettede manuelle dybdegennemgange** af de sikkerhedskritiske stier: auth/JWT/cookie-flow (`main.py` §auth), edge-signering (`edge/security.py`), edge→headend upload-klient (`edge/upload/headend_client.py`), CORS-opsætning, baggrundstråde/startup, UI-navigation (`Navbar.tsx`, 31 pages).
4. **Dokumentgennemgang** af autoritative kilder (`00_START_HER.md`, ADR-001/0007, `GO_LIVE_CHECKLIST_v10`, `RISK_ASSESSMENT_v10`-struktur, CI-workflow).

**Ikke dækket i denne omgang** (kræver kørende system eller mere tid — anbefalet som opfølgning): dynamisk test/pentest mod kørende headend, fuld linje-gennemgang af alle 234 routes i `main.py`, DB-skema-review mod produktionsdata, load-/soak-test for memory-verifikation over tid, gennemgang af alle 31 UI-pages enkeltvist (adfærd), tredjepartsafhængigheds-audit (SBOM+CVE-match er planlagt men ikke udført her).

## Klassifikation

**Kritisk** = blokerer forsvarlig prod-eksponering. **Høj** = skal løses før/under staging. **Mellem** = planlægges, skal ikke blokere staging. **Lav** = hygiejne.

Alle fund er formuleret så de kan importeres i GRC-registret (id, severity, evidens, anbefaling, ejer-felt tomt til Peter).
