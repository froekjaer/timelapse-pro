# Codex review — dokumentationsstyring og v11-strategi

**Dato:** 2026-07-02  
**Formål:** Codex' anbefaling til Peters/Claudes plan om at gøre dokumentationsmappen til både
arbejdsdokumentation og referencegrundlag for nye sessioner.

## Kort konklusion

Jeg er enig i målet, men ikke i en blind "alt til v11 nu"-runde.

Der findes allerede en brugbar v10-struktur med `00_START_HER.md` som session-boot, et sæt
autoritative `*_v10.md` dokumenter og `Gamle versioner/` som arkiv. Det næste skridt bør være en
kontrolleret v11-runde pr. dokument, hvor hvert dokument kun bumpes, når det faktisk er:

1. valideret mod aktuel kode/drift,
2. renset for forældede RPi5/SQLite/headend-referencer,
3. opdateret med Canon EOS 1000/1300/2000 + Nikon Z30 som understøttede kamerafamilier,
4. linket korrekt fra `00_START_HER.md`,
5. gemt som `.md`, mens forrige version flyttes til `Gamle versioner/`.

## Autoritative dokumenter lige nu

`00_START_HER.md` peger på følgende v10-dokumenter som gældende:

- `Timelapse_pro_full_documentation_v10.md`
- `RISK_ASSESSMENT_v10.md`
- `KRAVREGISTER_og_STATUS_v10.md`
- `GO_LIVE_CHECKLIST_v10.md`
- `PORT_AUDIT_og_WEBSITE_v10.md`
- `Installationsguide_v10.md`
- `ADMINISTRATORMANUAL_v10.md`
- `BRUGERMANUAL_v10.md`
- `Update_Flow_v10.md`
- `RBAC_Remote_Operational_v10.md`
- `SABSA_Architecture_v10.md`
- `TimeLapse_Security_Compliance_v10.md`
- `TimeLapse_Configuration_Guide_v10.md`
- `TimeLapse_Edge_Runbook_v10.md`
- `TimeLapse_Roadmap_v10.md`
- `System_Inventory_v10.md`
- `DOKUMENTPAKKE_OVERSIGT_v10.md`

Det er den rigtige kanoniske liste at arbejde ud fra.

## Fund ved hurtig review

### 1. `00_START_HER.md` er den rigtige session-anchor

Nye Claude/Codex-sessioner bør starte her. Den indeholder allerede:

- aktuel topologi,
- autoritative dokumenter,
- levende arbejdsdokumenter,
- empiri-/kildeplacering,
- regel om at tidligere versioner flyttes til `Gamle versioner/`.

Min anbefaling er at holde den kort og skarp. Den skal ikke blive endnu en fuld dokumentation.

### 2. Broken/forældet reference

`TimeLapse_Configuration_Guide_v10.md` refererer til `Headend_Installationsguide_Mac_Mini.md`, men
filen ligger ikke længere som aktivt top-level dokument. Den er arkiveret i `Gamle versioner/`.

Anbefaling: ret referencen i v11 til `Installationsguide_v10.md` eller kommende
`Installationsguide_v11.md`.

### 3. RPi5-forstyrrelsen er allerede markeret, men ikke helt fjernet

Flere dokumenter er tydeligt mærket som historiske Canon/RPi5-dokumenter:

- `TimeLapse_Configuration_Guide_v10.md`
- `TimeLapse_Edge_Runbook_v10.md`
- `System_Inventory_v10.md`
- `TimeLapse_Roadmap_v10.md`
- `TimeLapse_Security_Compliance_v10.md`

Det er godt for historik, men dårligt som session-reference. I v11 bør de enten:

- omskrives til aktuel Mac Mini/PostgreSQL/Orange Pi 4 Pro-virkelighed, eller
- flyttes ud af autoritativ liste og behandles som historisk reference.

### 4. Kamera-understøttelse bør beskrives som en matrix

Fremadrettet dokumentation bør ikke sige "Nikon Z30 erstatter Canon" for hårdt.

Den bør sige:

| Kamerafamilie | Status | Bemærkning |
|---|---|---|
| Nikon Z30 | Aktiv/lab-primary | Fokus, live view, eksponering og Z30-profil skal fortsat hærdes |
| Canon EOS 1000D | Skal understøttes | gphoto2/relay-baseret legacy/field support |
| Canon EOS 1300D | Skal understøttes | tidligere lab- og edge-erfaring findes |
| Canon EOS 2000D | Skal understøttes | forventet Canon EOS/gphoto2-variant, kræver profiltest |

Kamera-specifikke forskelle bør ligge i en dedikeret konfig-/driverprofil, ikke spredt gennem
alle dokumenter.

### 5. "Seneste version af alle dokumenter som .md" er rigtigt, men bør være manifest-styret

Jeg anbefaler et lille dokumentmanifest frem for at udlede sandheden fra filnavne alene.

Forslag:

```text
Dokumentation/DOKUMENT_MANIFEST.md
```

Indhold pr. dokument:

- dokument-id,
- titel,
- seneste aktive fil,
- ejer/primær vedligeholder,
- status: `authoritative`, `living`, `reference`, `archived`,
- erstatter/erstattet af,
- sidst valideret mod kode/drift,
- kendte uafklarede punkter.

Det gør nye sessioner meget mindre skrøbelige.

## Min anbefalede v11-rækkefølge

1. `00_START_HER.md`  
   Hold den som master-indeks. Opdatér kun links og regler.

2. `DOKUMENTPAKKE_OVERSIGT_v11.md` eller nyt `DOKUMENT_MANIFEST.md`  
   Gør dokumentlisten maskinelt og menneskeligt entydig.

3. `Installationsguide_v11.md`  
   Fjern aktive RPi5-headend-spor, gør Mac Mini/PostgreSQL canonical, men behold edge targets:
   Orange Pi 4 Pro, OrangePi PC Plus, RPi4/RPi5/Jetson som supportmatrix.

4. `ADMINISTRATORMANUAL_v11.md` og `SERVICES_OG_DRIFT_kilde_til_sandhed.md`  
   Skal valideres mod launchd, nginx, PostgreSQL, storage paths og nuværende services.

5. `KRAVREGISTER_og_STATUS_v11.md`  
   Skal opdateres med Edge QA/NPU, real-world-only billedtræning, RBAC/SFTP/API status og de
   faktiske go-live blockers.

6. `Timelapse_pro_full_documentation_v11.md`  
   Først når de underliggende specialdokumenter er rettet. Den må ikke være første dokument,
   ellers bliver den hurtigt en flot samling af gamle sandheder.

## Hvad Claude gerne må gøre

Claude må gerne konsolidere tekst og lave v11-drafts, men bør markere alle kode-/driftsudsagn med:

- `VERIFICERET I KODE`
- `VERIFICERET LIVE`
- `DOKUMENTKILDE`
- `ANTAGELSE`
- `UDGÅET/HISTORISK`

Codex kan derefter verificere live-punkter på Mac/Orange Pi og rette dokumentet fra "antagelse" til
"verificeret".

## Hvad jeg ikke anbefaler

- At flytte flere filer automatisk uden et manifest og en git-diff-review.
- At lave alle dokumenter til v11 i én stor commit.
- At slette RPi5/Canon-historik helt. Den skal arkiveres og tydeligt markeres som historisk, ikke
  forsvinde.
- At lade `Timelapse_pro_full_documentation` være eneste sandhed. Den er nyttig som samlet læsning,
  men driftsnære sandheder skal leve i de specialiserede dokumenter.

## Codex' sidste ord

Ja til Claudes plan om referencegrundlag og seneste `.md`-versioner.  
Nej til mekanisk v11-bump uden kode-/driftsvalidering.  
Ja til en manifest-styret, dokument-for-dokument v11-runde med `00_START_HER.md` som session-anchor.
