# Guide: Den håndholdte update-proces

**Målgruppe:** Peter, som eneste driftsansvarlig uden AI til stede.
**Dato:** 2026-09-03
**Status:** Afspejler systemet som det faktisk virker efter #174/#175/#176 (verificeret live i produktion samme dag).

Denne guide beskriver hvad du selv kan og bør gøre på `/updates`-siden i dag —
og lige så vigtigt: hvad der IKKE er selvbetjent endnu, så du ikke bruger tid på
at forsøge noget systemet ikke understøtter. Se
`Dokumentation/UPDATE_GOVERNANCE_DIAGNOSIS_2026-09-01.md` for den fulde tekniske
diagnose bag dette, og punktet "Opfølgning 2026-09-03" for hvad der er lukket.

---

## 1. De tre spor i update-køen — og hvem der bør røre dem

Update-køen (`/updates`) blander tre helt forskellige ting, som ser ens ud i
UI'et men opfører sig forskelligt:

| Spor | `update_type` | Hvad det er | Kan du selv godkende og deploye via UI'et i dag? |
|---|---|---|---|
| **TimeLapse Pro-software** | `app_updates`, `app_security` | Selve TimeLapse Pro-agenten der kører på Edge-enhederne | Teknisk ja (signeret artifact-pipeline virker, git-tag-baseret) — men **gør det kun sammen med en AI**, jf. din egen beslutning om at app-deploys altid skal håndbæres |
| **OS/sikkerhed på Edge** | `os_security`, `os_updates` | apt-pakker på Orange Pi-enhederne | **Nej.** Kræver et lab-bygget, Headend-signeret offline OS-bundle — den infrastruktur findes ikke endnu |
| **Platform-apps på selve Mac mini'en** | `application_updates`, `dependency_updates`, `third_party_updates` | Homebrew-pakker (ollama, ffmpeg, postgresql, node, nginx, certbot) som Headend selv kører oven på | **Nej**, af samme grund — kræver signeret dependency-artifact |

De to sidste spor er dem, du bad om at kunne drive selv, "hver gang, uden
hjælp". Det korte svar efter denne uges gennemgang: **UI'ets "Godkend"-knap kan
ikke gøre det for dig endnu** for disse to spor — den lange, samlede
preflight→artifact→install→postflight-automatisering findes ikke, og vi har
netop besluttet ikke at bygge den nu. Men der er en praktisk, håndholdt vej
udenom, beskrevet i afsnit 3.

---

## 2. Sådan læser du et kort på `/updates`

- **Fanen "Kræver handling"** er default og viser kun det der reelt kræver en
  beslutning (pending, approved, blocked, rollback anmodet) — sorteret med de
  mest aktuelle øverst. De øvrige faner (Afventer, Godkendt, Blokeret, Deployet,
  Afvist, Erstattet, Rullet tilbage, Alle) er for at slå historik op.
- **Status-badge** på kortet: Afventer / Godkendt / Blokeret / Deployet / Afvist
  / Erstattet / Rullet tilbage.
- **Fold kortet ud** for at se detaljer. Der står nu et **"Årsag:"**-felt lige
  øverst (nyt siden #174) — det er den korte, konkrete forklaring på hvorfor
  kortet har den status det har, uden at du skal læse hele
  "Beskrivelse"-prosaen. For platform-app/OS-blokerede kort vil Årsag typisk
  sige noget i stil med *"CMDB re-observed package as still outdated; requires
  signed dependency artifact"* — det betyder: systemet har set at pakken
  stadig er outdated, og det er stadig ikke sat op til at kunne installere den
  automatisk.
- **`resolution_reason` er tom (NULL) for kort oprettet før 2026-09-03** — det
  er ikke en fejl, feltet fandtes bare ikke endnu dengang.

---

## 3. Det du faktisk kan gøre selv, i dag, uden AI

For OS-opdateringer på Edge og Homebrew-pakker på Mac mini'en er den
håndholdte proces **ikke** "klik Godkend i UI'et". Den er:

### 3a. Homebrew-pakker på selve Mac mini'en (Headend)

1. Åbn Terminal på Mac mini'en.
2. Kør selv opdateringen direkte, som du plejer:
   ```bash
   brew upgrade nginx
   # eller den pakke Årsag/Beskrivelse peger på
   ```
3. Gør ikke andet. Systemets egen inventory-sync kører hvert **5. minut**
   (`inventory_interval = 300` i `/etc/timelapse/node-agent.conf`) og opdager
   selv at pakken ikke længere er outdated.
4. Inden for de næste ~5 minutter lukker systemet automatisk det tilhørende
   kort på `/updates` (status bliver `superseded`) — **du behøver ikke gøre
   noget i UI'et**. Dette er verificeret live i produktion i dag: et helt
   parallelt tilfælde (stale target-status på #228/#230/#231) blev automatisk
   rettet af præcis denne mekanisme uden manuel handling.

### 3b. OS-sikkerhedsopdateringer/apt-pakker på en Edge-enhed

Samme princip, men fra selve enheden:

1. SSH ind på Edge-enheden.
2. Kør `sudo apt update && sudo apt upgrade` (eller kun de specifikke pakker
   Beskrivelsen nævner) selv.
3. Edge-enhedens egen inventory-rapportering (typisk op til ~24 timer,
   afhængig af enhedens sync-interval) opdager det og lukker kortet
   automatisk — igen uden at du skal røre UI'et.

### 3c. Hvad "Godkend"/"Afvis"-knapperne reelt gør i dag for disse to spor

- **Godkend** flytter status til "Godkendt", men da der ikke findes et
  signeret artifact for disse typer, sidder updaten derefter fast som
  "Mangler signeret artifact" — den bliver ikke installeret af sig selv. Brug
  den ikke til Homebrew/OS-kort, medmindre du ved præcis hvad du gør (fx en AI
  har lige bundet et artifact manuelt, jf. "Bind artifact"-flowet på
  Headend-platform-app-kort).
- **Afvis** sætter status til "Afvist" og skriver nu (#176) automatisk
  "Rejected by \<dit brugernavn\>" i Årsag-feltet. Brug den hvis du aktivt
  IKKE vil have en given opdatering foreslået igen — men vær opmærksom på at
  CMDB-synkroniseringen ikke genopretter et afvist kort, så det er en mere
  permanent handling end blot at lade det stå blokeret.
- **Rollback** (kun synlig når status er "Deployet") beder Edge om at rulle
  tilbage til forrige verificerede release ved næste heartbeat. Det er kun
  relevant for `app_updates`-sporet.

---

## 4. TimeLapse Pro-softwaren selv (Edge-agent) — bliv ved med at have en AI med

Dette spor (`app_updates`/`app_security`) har faktisk en fungerende, signeret
artifact-pipeline (git-tag-baseret, automatisk) og kan derfor reelt godkendes
og deployes via UI'et alene. Det er bevidst **ikke** dét du bad om at kunne
drive selv — tværtimod bad du om at disse altid skal ske håndbåret, med en AI
til stede, netop fordi det er selve produktets kernesoftware. Den beslutning
er ikke ændret af dette arbejde, og er ikke teknisk håndhævet i systemet (du
KAN klikke Godkend alene) — det er en aftale mellem os, ikke en spærring i
koden.

---

## 5. Fejlsøgning

- **Et kort virker "forkert"** (fx status siger Blokeret, men et target under
  flow-status stadig viser "Klar til Edge pull"/queued): Dette var netop den
  konkrete fejl vi rettede 2026-09-03. Rettelsen er selv-helende — det retter
  sig selv ved enhedens næste sync, uden manuel handling. Hvis det IKKE er
  rettet efter et par sync-cyklusser (5 min for Headend selv, op til et døgn
  for Edge), er det værd at flage til en AI-session.
- **Et kort har ingen Årsag**: enten er det oprettet før 2026-09-03 (ingen
  retroaktiv udfyldning), eller det er en status hvor der ikke er nogen
  "hvorfor" at forklare (fx "Afventer" — det afventer bare din beslutning).
- **Du er i tvivl om en Homebrew/apt-opdatering er sikker at køre selv**: Årsag
  og Beskrivelse på kortet fortæller hvilken pakke og hvilken version-gap det
  drejer sig om. Hvis du er i tvivl om selve opdateringens indhold (ikke om
  update-køens mekanik), er det stadig værd at spørge en AI først — denne
  guide handler om update-køens process, ikke om at vurdere enkeltpakkers
  risiko.

---

## 6. Hvad der bevidst IKKE er bygget

Efter din tilbagemelding 2026-09-03 ("vi er ikke modne til en samlet proces")
er følgende bevidst ikke forsøgt, og bør ikke forventes at virke:

- Et fuldt automatisk preflight → artifact → install → postflight-flow for
  Homebrew-pakkerne på Mac mini'en.
- Et tilsvarende automatisk, signeret offline OS-bundle-flow for Edge apt-pakker.
- En 3-vejs UI-opdeling (drift/release/historik) — køen viser stadig alle tre
  spor blandet, blot sorteret og forklaret bedre end før.

Hvis du på et tidspunkt vil genoptage dette, ligger den fulde tekniske analyse
og et konkret forslag i `Dokumentation/UPDATE_GOVERNANCE_DIAGNOSIS_2026-09-01.md`,
punkt 4 og 5 under "Næste anbefalede tekniske lukning".
