# TimeLapse Pro — Menuguide: Bruger (v1)

**Dato:** 2026-08-20
**Formål:** Menu-for-menu beskrivelse af alle sider der er tilgængelige for almindelige brugere (viewer/operator) samt de dele af admin-siderne en bruger kan støde på. Supplerer `BRUGERMANUAL_v10.md`, som er opgaveorienteret; denne guide er struktureret efter selve menuen.
**Kilde:** Indholdet er udledt direkte af koden (`timelapse-ui/src/`), så det matcher den faktiske UI. Rollekrav er angivet pr. side.

> **Roller i korthed:** `viewer` kan se captures og status. `operator` kan desuden trigge handlinger på enheder. `admin`/`super_admin` har adgang til alle sider (se `MENUGUIDE_ADMIN_v1.md`). Sider markeret 🔒 kræver admin eller højere.

> **Hover-hjælp i UI'en:** Alle ikke-selvforklarende felter har et ⓘ-ikon ved siden af feltnavnet. Hold musen over (eller fokusér med tastaturet) for at få en kort forklaring. Tooltip-teksterne bruger samme terminologi som denne guide.

---

## Topmenuen

### Enheder (`/`) — Dashboard

- **Formål:** Samlet overblik over alle kameraenheder og kunde-/site-hierarkiet.
- **Hvem ser den:** Alle roller.
- **Indhold:** Kundelisten med sites og kameraer; status pr. enhed (online/offline, seneste capture); links videre til enheds-, site- og kundesider. Admins ser desuden knapper til oprettelse (fx "Ny kunde" — kun super_admin).
- **Typiske opgaver:**
  1. Find et kamera: klik dig ned via kunde → site → kamera, eller brug Tag søgning (se nedenfor).
  2. Tjek om en enhed er i live: se statusmarkeringen på enhedskortet.
- **Fejlfinding:** Hvis en enhed ser offline ud, men du ved den kører: edge-enheden rapporterer via den konsoliderede sync-poll (standard hvert 5. minut) — vent en cyklus før du konkluderer nedbrud.
- **Relateret:** `BRUGERMANUAL_v10.md` §2.

### Enhedssiden (`/devices/:id`)

- **Formål:** Detaljer for én edge-enhed: identitet, optagelsesplan, kameraparametre, GPS/lokation og helbredstrend.
- **Hvem ser den:** Alle roller kan se; redigering kræver admin.
- **Indhold (sektioner):**
  - *Enhedsidentitet* — navn og tilknytning til kunde/site/kamera (dropdowns med "ny…"-mulighed for admin).
  - *Optagelsesplan* — interval, tidsvinduer og om optagelse er aktiv.
  - *Kamera-parametre* — blænde, lukketid, ISO, fokus m.m. (arv fra Global Config medmindre der er sat override).
  - *GPS og lokation* — koordinater og GPS-kilde (fx gpsd).
  - *Helbred* — grafer for CPU-temperatur, SSD-forbrug og kamera-shutter-tæller over de seneste 7 dage.
- **Fejlfinding:** GPS viser kun data hvis enheden har et fungerende GPS-modul og gpsd installeret — se FAQ'en ("Data-fast"/GPS-afsnit) og handover-noterne om gpsd.

### Kundesiden (`/customers/:customerId`)

- **Formål:** Kundestamdata, kommerciel risikoprofil og kundens sites.
- **Hvem ser den:** Alle med adgang til kunden; redigering kræver admin. Risikoprofilen valideres af platformadministrator før den slår igennem.
- **Indhold:** *Kundeoplysninger* · *Kommercielt risikoinput* og *Kundens forretningsmæssige risikoprofil* (produktværdi, nedetidsomkostninger, CIA-impact 1–5, RTO/MTD, persondataniveau) · *BT PAN TOTP kunde-override* 🔒 · *Edge QA AI kunde-override* 🔒 · *Drift-detektion kunde-override* 🔒 · *Sites*-listen.
- **Typiske opgaver:** udfyld risikoprofilen ved onboarding af en ny kunde — den bruges i FAIR-baseret risikoberegning (se `FAIR_RISK_INPUT_MODEL_v1.md`).

### Sitesiden (`/sites/:siteId`)

- **Formål:** Én fysisk lokation under en kunde.
- **Indhold:** *Site-oplysninger* · *SFTP-adgang* (upload-endpoint for sitets enheder) · *BT PAN TOTP site-override* 🔒 · *Edge QA AI site-override* 🔒 · *Drift-detektion site-override* 🔒 · *GPS og lokation* · *Kameraer* på sitet.
- **Bemærk:** Overrides på site-niveau arves ned til kameraerne, medmindre kameraet har sit eget override (Global → Kunde → Site → Kamera).

### Tag søgning (`/tags`)

- **Formål:** Søg og filtrér captures på tværs af enheder vha. tags, kvalitet og fritekst.
- **Hvem ser den:** Alle roller.
- **Indhold:** Tag-felt (skriv tag + Enter), naturligt-sprogs-søgning (fx *"find skarpe billeder med kran uden regn fra i dag"*), kvalitets-score-filter (0–1) og resultatgrid med billeder. Marker flere billeder og vælg *Rediger tags* for at tilføje/fjerne tags i bulk.
- **Typiske opgaver:**
  1. Find alle billeder med et bestemt fænomen: skriv tagget (fx `tåge`) og tryk Enter.
  2. Ryd op i dårlige tags: søg → markér → *Rediger tags* → fjern.
- **Relateret:** `BRUGERMANUAL_v10.md` §4; FAQ'en "Tags på billederne ser dårlige ud" og "Hvordan re-tagger jeg billeder?".

### Indstillinger (`/settings`)

- **Formål:** Personlige og tekniske indstillinger.
- **Hvem ser den:** Alle roller; enkelte sektioner kun for admin.
- **Indhold:** *Headend API* (API-endpoint og forbindelsestest) · *Tidszone* (påvirker visning af tider i UI) · *System Administration* (genvej, 🔒) · *Alarm Notifikationer* (genvej til `/notifications`, 🔒) · *Brugerstyring (RBAC)* (genvej, 🔒).
- **Fejlfinding:** Ændrer du API-endpoint og mister forbindelsen, skal du logge ind igen mod det korrekte endpoint.

### Alarm Notifikationer (`/notifications`)

- **Formål:** Opsætning af alarmer ud af systemet når der sker noget kritisk.
- **Hvem ser den:** Admin 🔒 (men beskrevet her fordi siden nås via Indstillinger).
- **Indhold:**
  - *Minimum alvorlighedsniveau* — kun hændelser på/over dette niveau sender alarm.
  - *Email* — SMTP host/bruger/app-adgangskode/afsender og modtagerliste (kommasepareret). Knap: **Send test**.
  - *SMS via GatewayAPI* — API-token, afsendernavn (maks 11 tegn), modtagernumre. Knap: **Send test**.
  - *Microsoft Teams* — webhook-URL. Knap: **Send test**.
  - **Gem** nederst.
- **Typiske opgaver:** sæt altid en *test*-alarm af efter ændring — en grøn test er den eneste sikkerhed for at kanalen virker, før den rigtige alarm kommer.
- **Bemærk:** Hemmeligheder (SMTP-kode, GatewayAPI-token) gemmes server-side; brug app-specifikke adgangskoder, aldrig din primære kode.

### Compliance (`/compliance`)

- **Formål:** SABSA compliance-cockpit med audit-overblik, GRC-register og rapportgenerering.
- **Hvem ser den:** Alle roller (redigering/statusændringer kræver admin).
- **Indhold (sektioner):**
  - *Autoritativt GRC-register* — søg i ID/titel/kategori; klik en post for detaljer, status og noter. Dette er den samme PostgreSQL-database der er single source of truth for fund/risici/handlinger.
  - *Generér fra autoritativ GRC-database* — danner compliance-rapporter direkte fra registeret.
  - *Kontrollerede dokumenter* — versionsstyrede politikker og procedurer.
  - *Regulatorisk reference* — søgbar liste over relevante regler/standarder (fx AI, energi, cyber).
  - *Fuld audit — katalogberedskab* — gennemgang af kontroller pr. standard.
  - *Evidenskilder* — hvilke systemdele der leverer evidens.
- **Relateret:** `BRUGERMANUAL_v10.md` §7.1; `TimeLapse_Security_Compliance_v10.md`.

---

## Relaterede sider uden eget menupunkt

- **Timelapse-video** (`/devices/:id/timelapse`) 🔒 — saml en billedsekvens til video; se `BRUGERMANUAL_v10.md` §6 og `Post-processing` i adminguiden for render-options (inkl. exposure/WB-ramping).
- **Kamera-siden** (`/cameras/:deviceId`) 🔒 — se `MENUGUIDE_ADMIN_v1.md`.
- **Kamera-laboratoriet** (`/lab/:deviceId`) 🔒 — se `docs/LAB_MODE_TEST_GUIDE.md` og adminguiden.

## Se også

- `FAQ_og_fejlsøgning.md` — spørgsmål/svar til de hyppigste problemer (login, genstart, tags, LAB mode, hukommelse/Ollama, Mac Mini efter strømsvigt).
- `MENUGUIDE_ADMIN_v1.md` — alle Admin-dropdownens menupunkter.
