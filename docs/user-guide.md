# TimeLapse Pro — Bruger Guide

**Version:** 1.0
**Dato:** 13. juli 2026
**Målgruppe:** Operatører, viewere, og admin-brugere

---

## 📋 Indhold

1. [Kom i gang](#kom-i-gang)
2. [Navigation og Menuer](#navigation-og-menuer)
3. [Dashboard og Overblik](#dashboard-og-overblik)
4. [Kameraer og Enheder](#kameraer-og-enheder)
5. [Konfiguration med Tooltips](#konfiguration-med-tooltips)
6. [Søgning og Filtrering](#søgning-og-filtrering)
7. [Timelapse og Video](#timelapse-og-video)
8. [Support og Hjælp](#support-og-hjælp)

---

## Kom i gang

### Login

1. Gå til `https://timelapse.example.com` (eller din interne URL)
2. Indtast brugernavn og password
3. Vælg "Husk mig" for at forblive logget ind (30 dage)

**Glemt password?** Kontakt din systemadministrator.

### Første gangs opsætning

Ved første login vil du blive mødt af dashboardet med en tom liste. Kontakt admin for:
- Oprettelse af kunder og sites
- Tildeling af kameraer til sites
- Konfiguration af capture schedule

---

## Navigation og Menuer

### Hovedmenu

Naviger til forskellige sektioner via top-menuen:

| Menu | Funktion | Typisk bruger |
|------|----------|---------------|
| **Dashboard** | Overblik over systemstatus | Alle |
| **Kameraer** | Liste over alle kameraer | Operatør, Admin |
| **Søg** | Avanceret tagsøgning | Alle |
| **Timelapse** | Opret video fra captures | Alle |
| **Lab** | Test og eksperimenter | Admin |
| **Admin** | Brugerstyring, konfiguration | Admin, Super Admin |

### Tooltips i Menuen

Alle menupunkter har tooltips der vises ved hover. Hold musen over et menupunkt for at se:
- **Kort beskrivelse** — hvad menupunktet gør
- **Genvej** — tastaturgenvej hvis tilgængelig
- **Tip** — praktisk tip til brug

**Eksempel:** Hold musen over "Kameraer" for at se "Vis og administrer alle kameraer i systemet."

---

## Dashboard og Overblik

### Dashboard Widgets

Dashboardet giver et hurtigt overblik over:

- **Status tiles** — Systemstatus (online/offline kameraer, disk plads, capture rate)
- **Aktive alarmer** — Løbende problemer der kræver opmærksomhed
- **Seneste captures** — De nyeste billeder fra alle kameraer
- **Grafer** — Tidsserier for capture success rate, disk usage, etc.

### Interaktion

- **Klik på en tile** for at gå til detaljeret side
- **Brug filter** for at vise specifikke kunder/sider
- **Opdater** manuelt med refresh knappen eller vent på auto-refresh (30 sekunder)

---

## Kameraer og Enheder

### Kamera Liste

Kamera-listen viser alle kameraer med:

- **Status** — online (grøn), offline (rød), unknown (grå)
- **Navn** — Kameraets navn (f.eks. "Kamera 1 mod N")
- **Site** — Hvilket site kameraet tilhører
- **Seneste capture** — Tidspunkt for sidste billede
- **Capture rate** — Procentdel af succesfulde captures

### Kamera Detaljer

Klik på et kamera for at se detaljer:

- **Live billede** — Seneste capture med timestamp
- **Tekniske data** — Kamera model, serialnummer, firmware
- **Konfiguration** — Alle indstillinger med tooltips
- **Historik** — Graf over capture success rate over tid
- **Alarmer** — Aktive alarmer for dette kamera

---

## Konfiguration med Tooltips

### Hvad er Tooltips?

Tooltips er hjælpe-tekster der vises når du holder musen over et felt eller parameter. De ser sådan ud:

**ⓘ** — Klik på dette ikon (eller hold musen over) for at se hjælpeteksten.

### Tooltip Struktur

Hver tooltip indeholder 4 linjer:

1. **Hvad parameteren gør** — praktisk forklaring
2. **Anbefalede værdier** — typiske indstillinger
3. **Konsekvenser** — hvad sker der hvis du ændrer det
4. **Tips** — best practices og gotchas

### Eksempler

#### Kamera Indstillinger

| Parameter | Tooltip Eksempel |
|-----------|------------------|
| **ISO** | Kameraets lysfølsomhed (100-6400). Lav ISO = mindre støj men kræver mere lys. Udendørs dagslys: 100-200. |
| **Lukker** | Lukkerhastighed der styrer eksponering og bevægelse. Hurtig (1/500+) fryser bevægelse. Udendørs: 1/125-1/500. |
| **Interval** | Minutter mellem captures. Lavere = tættere timelapse men mere plads. Typisk 5-60 minutter. |

#### AI Kvalitet

| Parameter | Tooltip Eksempel |
|-----------|------------------|
| **Edge AI** | Aktiverer AI-baseret kvalitetsanalyse. Sløring, mørk, lens obstruction. Anbefales altid. |
| **AI Mode** | AI adfærd: off, monitor (log kun), assist (advar), autonomous (rett). Assist anbefales. |

#### Drift Detektion

| Parameter | Tooltip Eksempel |
|-----------|------------------|
| **Fokus-drift** | Alarmer hvis skarphed systematisk falder. Detekterer manuel fokus der glider (vibration). |
| **Fokus-følsomhed** | Antal standardafvigelser før alarm (2.0-4.0). Lavere = mere følsom. Typisk 2.0-3.0. |

### Brug af Tooltips

1. **Identificer parameteren** du vil ændre
2. **Hold musen over** ⓘ ikonet ved siden af parameter-navnet
3. **Læs tooltips** for at forstå parameteren
4. **Vælg en værdi** baseret på anbefalingen i tooltip
5. **Gem ændringer** med "Gem" knappen

---

## Søgning og Filtrering

### Tagsøgning

Søgning giver mulighed for at finde billeder baseret på tags:

- **Kvalitet tags** — `blurry`, `overexposed`, `underexposed`, `unusable`
- **AI tags** — `dirty_lens`, `motion_blur`, `low_contrast`
- **Kilde tags** — `manual_capture`, `scheduled_capture`, `test_capture`

### Søge Tips

- **Kombiner tags** — Brug `AND`/`OR` til at kombinere søgninger
- **Tidsinterval** — Begræns søgningen til en periode
- **Kamera filter** — Søg kun på specifikke kameraer
- **Eksport** — Eksporter resultater til CSV eller download billeder

---

## Timelapse og Video

### Opret Timelapse Video

1. Gå til **Timelapse** menuen
2. Vælg **Kamera** og **tidsinterval**
3. Konfigurer **indstillinger**:
   - **FPS** — Billeder per sekund (typisk 15-30)
   - **Resolution** — Output resolution (typisk 1080p eller 4K)
   - **Kvalitet** — Video quality (high, medium, low)
4. Klik **"Generer video"**
5. Vent på at videoen bliver genereret (kan tage flere minutter)
6. **Download** eller **stream** videoen

### Video Indstillinger Tooltips

| Parameter | Tooltip |
|-----------|---------|
| **FPS** | Billeder per sekund i output. Højere FPS = jævnere video men kortere varighed. Typisk 15-30. |
| **Resolution** | Output resolution i pixels. Højere = bedre kvalitet men større fil. 1080p anbefales. |
| **Kvalitet** | Video compression kvalitet. Høj = mindre compression men større fil. Medium anbefales. |

---

## Support og Hjælp

### Ofte Stillede Spørgsmål (FAQ)

**Q: Jeg kan ikke se mit kamera i listen**
- A: Kontakt admin for at få kameraet tildelt til dit site/kunde.

**Q: Capture success rate er lav**
- A: Tjek kameraets tekniske data for fejl. Prøv at genstarte kameraet eller kontakt support.

**Q: Hvordan ændrer jeg kamera indstillinger?**
- A: Gå til Kameraer → vælg kamera → Klik på rediger → Brug tooltips til at forstå parametre.

**Q: Video generering fejler**
- A: Sørg for at der er nok captures i det valgte interval. Prøv et større interval.

### Kontakt Support

| Problem | Kontakt |
|---------|---------|
| Akutte driftsproblemer | +45 XX XX XX XX |
| Teknisk support | support@timelapse.example.com |
| Feature requests | product@timelapse.example.com |

---

**Guide version:** 1.0
**Sidst opdateret:** 13. juli 2026

---

## Changelog

### v1.0 (2026-07-13)
- Første version af bruger guiden
- Dokumentation af tooltip funktionalitet
- Eksempler på alle vigtige parametre
- FAQ sektion
