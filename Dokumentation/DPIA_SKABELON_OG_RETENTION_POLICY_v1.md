# TimeLapse Pro — DPIA-skabelon + Retention Policy (v1, udkast)

**Dato:** 2026-07-04 (nat)
**Forfatter:** Claude (på Peters anmodning, mens han sov — se `HANDOVER_LOG.md` 2026-07-04 nat)
**Status:** Udkast — lukker det tekniske/organisatoriske grundlag for R12 (GDPR-evidens
mangler) i `RISK_ASSESSMENT_v10.md`, samt GO_LIVE_CHECKLIST_v10.md §G-01/G-02.
**VIGTIGT:** Dette er ikke juridisk rådgivning. Skabelonen og policy-designet er et
teknisk/organisatorisk udkast baseret på kodegennemgang. Peter (eller en rådgiver med
juridisk kompetence) skal gennemgå og godkende indholdet, særligt retsgrundlag
(hjemmel) og opbevaringsperioder, før det anvendes over for rigtige kunder.

---

## 0. Hvorfor dette dokument

`RISK_ASSESSMENT_v10.md` R12 og `GO_LIVE_CHECKLIST_v10.md` §G markerer som blokerende
for produktion:

1. DPIA pr. kunde/site (G-01)
2. Retention policy pr. kamera (G-02)
3. Databehandleraftale (G-03) — **dækkes ikke her**, kræver en egentlig kontrakt/jurist
4. Subprocessor-liste (G-04) — dækket i §4 nedenfor
5. Download/adgangslog (G-05) — teknisk allerede delvist muligt via eksisterende
   audit-infrastruktur, men ikke skemalagt her; foreslås som opfølgning
6. Procedure for databrud (G-06) — **dækkes ikke her**
7. Oplysningspligt til registrerede (G-07) — kort udkast i §5

Dette dokument leverer #1, #2, #4 og et udkast til #5/#7. #3 og #6 kræver en jurist og
er bevidst udeladt.

---

## 1. Rolleafklaring (controller/processor)

Baseret på forretningsmodellen (kamera-udstyr + software leveret til kunder i bygge-,
anlægs- og infrastruktursektoren, jf. `RISK_ASSESSMENT_v10.md` §8):

- **TimeLapse Pro (Peter/virksomheden) er databehandler (processor).**
- **Kunden (byggeherre/entreprenør, ejer af byggepladsen) er dataansvarlig (controller)**
  for de personoplysninger, der optages på deres site (personer, køretøjer,
  nummerplader der utilsigtet fanges af kameraet).
- Konsekvens: **DPIA'en er formelt kundens/den dataansvarliges ansvar** (GDPR art. 35),
  men da kunden ikke selv har indsigt i den tekniske løsning, er det naturligt at
  TimeLapse Pro leverer en udfyldt teknisk skabelon som kunden kan godkende/underskrive.
  Skabelonen i §2 er bygget til dette: TimeLapse Pro udfylder de tekniske afsnit,
  kunden udfylder formål/kontekst-afsnittene og træffer den endelige beslutning.

---

## 2. DPIA-skabelon (pr. kunde/site)

> Kopiér denne sektion pr. site og udfyld. Felter markeret **[KUNDE]** udfyldes af
> kunden. Felter markeret **[TLP]** er allerede udfyldt af TimeLapse Pro nedenfor og
> gælder generelt for alle sites, medmindre andet er noteret pr. site.

### 2.1 Grunddata

| Felt | Værdi |
|---|---|
| Kunde | **[KUNDE]** |
| Site/adresse | **[KUNDE]** — matcher `Site.address`/`Site.gps_lat/lon` i CMDB |
| Formål med kameraovervågning | **[KUNDE]** — typisk: fremdriftsdokumentation, tidsforløbsvideo, byggepladssikkerhed |
| Dato for DPIA | **[KUNDE]** |
| Ansvarlig hos kunden | **[KUNDE]** |
| Databehandler | TimeLapse Pro / Peter Frøkjær |

### 2.2 Beskrivelse af behandlingen [TLP]

- **Hvad optages:** periodiske stillbilleder (timelapse) af byggepladsen fra fast
  monteret kamera. Billeder kan utilsigtet indeholde personer, køretøjer og
  nummerplader, der befinder sig i kameraets synsfelt.
- **Hvor ofte:** konfigurerbart pr. kamera (typisk hvert 5.-15. minut i dagtimer).
- **Hvilke afledte data genereres:**
  - GPS/lokationskoordinater for kameraet (ikke for personer) — se `location`-feltet
    i sidecar-metadata.
  - AI-genererede tags og scenebeskrivelser (dansk fritekst) af billedindholdet,
    produceret af enten en lokal model (Ollama, kører på TimeLapse Pro's egen
    server — ingen tredjepart) eller en cloud-model (Google Gemini — se §4).
  - Automatisk kvalitetskontrol (skarphed/lysstyrke) — ingen persondata.
- **Automatiske afgørelser:** Nej. AI-tags bruges til søgning/filtrering og
  fremdriftsvurdering, ikke til automatiserede afgørelser om enkeltpersoner.
- **Særlige kategorier af data (GDPR art. 9):** Forventes normalt IKKE at forekomme
  (billeder af en byggeplads, ikke målrettet optagelse af personer). Der findes en
  isoleret datamodel til at registrere evt. ansigt/nummerplade-fund
  (`GDPRDetection`, se §3), men **den tekniske komponent, der reelt skal udføre
  denne detektion og gemme fund isoleret (`gdpr_manager.py`), er endnu ikke
  implementeret** (se `RISK_ASSESSMENT_v10.md` R12 og R18). Indtil dette er på
  plads, skal det antages, at billeder KAN indeholde identificerbare personer uden
  systematisk detektion/sløring.

### 2.3 Nødvendighed og proportionalitet [KUNDE + TLP]

| Spørgsmål | Svar |
|---|---|
| Er formålet legitimt og klart defineret? | **[KUNDE]** |
| Kan formålet opnås med mindre indgribende midler (fx sjældnere optagelse, snævrere synsfelt)? | **[KUNDE]** — TLP kan rådgive teknisk om FOV/vinkel |
| Er kameraets synsfelt afgrænset til byggepladsen (undgår offentlig vej/naboarealer)? | **[KUNDE]** — bør bekræftes ved opsætning; TLP kan levere `fov_horizontal_deg`/`azimuth_deg`-data fra kamerakonfigurationen som dokumentation |
| Er der skiltet om kameraovervågning på pladsen (jf. TV-overvågningsloven)? | **[KUNDE]** |

### 2.4 Risikovurdering [TLP + KUNDE]

| Risiko | Sandsynlighed | Konsekvens | Vurdering |
|---|---|---|---|
| Utilsigtet optagelse af forbipasserende/naboarealer | Middel (afhænger af opsætning) | Lav-middel | Afhjælpes ved korrekt FOV/vinkel — **[KUNDE]** bekræfter ved opsætning |
| Uautoriseret adgang til billeder | Lav — RBAC + tenant-isolation implementeret, MFA påkrævet for admin | Middel-høj | Se `RISK_ASSESSMENT_v10.md` R02/R16 (begge lukkede) |
| Lokationsdata (kamera-GPS) afslører adresse | Lav — adressen er allerede kendt (byggepladsens egen adresse) | Lav | Ingen særskilt risiko udover selve stedets kendte adresse |
| AI-scenebeskrivelse identificerer/omtaler personer i fritekst | Middel | Lav-middel | Gennemgås manuelt ved eskalering (review-workflow); ingen automatiseret beslutning baseret på dette |
| Data sendt til cloud-AI (Gemini) uden for EU | Lav, men **skal bekræftes teknisk** | Middel-høj hvis bekræftet | Se §4 — regionsindstilling er IKKE verificeret i denne gennemgang, kun at koden STØTTER EU-region |
| Overskridelse af rimelig opbevaringsperiode | Høj (ingen automatisk sletning findes i dag) | Middel | Se §3 (retention policy) — teknisk ikke implementeret endnu |

### 2.5 Foranstaltninger og konklusion [KUNDE]

- Foreslåede foranstaltninger: **[KUNDE + TLP i fællesskab]**
- Er den resterende risiko acceptabel? **[KUNDE, med rådgivning fra TLP hvor teknisk relevant]**
- Skal Datatilsynet høres forud for behandlingen (GDPR art. 36)? **[KUNDE, vurderes typisk ikke nødvendigt for denne type behandling, men er en juridisk vurdering]**

---

## 3. Retention policy — design (teknisk, endnu IKKE implementeret)

Databasen har allerede en isoleret datamodel klar til formålet
(`headend/ai/ai_models.py`, `GDPRDetection.retain_until`/`is_expired()`/
`soft_delete()`, samt en `gdpr_deletion_queue`-tabel i `schema_v2.sql`) — men **ingen
scheduler eller baggrundsjob kalder den i dag**. Det følgende er et forslag til,
hvordan det lukkes:

### 3.1 Foreslået model

1. **Ny config-nøgle pr. kamera:** `retention.days` (default fx 365 dage, konfigurerbart
   pr. kunde/site/kamera via samme hierarki som øvrig kamera-config —
   `get_config()` i `headend/main.py` understøtter allerede dette mønster for andre
   nøgler som `location`/`quality`).
2. **Nyt baggrundsjob** (samme mønster som eksisterende pollere, fx
   `AI batch-job poller startet (interval=5m)` set i opstartsloggen): kører dagligt,
   finder `Capture`-rækker ældre end `retention.days` for det pågældende kamera, og:
   - Flytter filen til en "papirkurv"-mappe i **[X] dage** før permanent sletning
     (sikkerhedsnet mod fejlkonfiguration), ELLER
   - Sletter direkte, hvis kunden har fravalgt papirkurv-perioden.
   - Logger hver sletning til en ny `deletion_log`-tabel (adskilt fra selve
     billedet, så der er revisionsspor for HVAD der blev slettet HVORNÅR, uden at
     gemme selve billedet).
3. **Undtagelse:** billeder der indgår i en aktiv GDPR-sag (`GDPRDetection` med
   `retain_until` sat af en igangværende undersøgelse) ekskluderes fra automatisk
   sletning, indtil `retain_until` er passeret.
4. **UI:** ny indstilling under kamera-konfiguration ("Opbevaringsperiode"), samt en
   statusvisning der viser hvor mange billeder der forventes slettet ved næste kørsel
   (undgår overraskelser).

### 3.2 Ikke inkluderet i dette udkast

- Selve implementeringen (baggrundsjob, UI, migration) — dette er et designforslag,
  ikke kode. Foreslås som næste konkrete opgave, hvis Peter godkender modellen.
- Beslutning om default-værdi for `retention.days` — dette er en forretningsmæssig/
  juridisk beslutning, ikke en teknisk. Datatilsynets vejledning peger typisk på "så
  kort tid som muligt af hensyn til formålet" — for byggepladsdokumentation er dette
  ofte "indtil byggeriets afslutning + en kort efterfølgende periode", hvilket taler
  for en pr.-site-konfigurerbar værdi frem for én fast global værdi.

---

## 4. Subprocessor-liste [TLP]

| Underleverandør | Rolle | Databehandlet | Bemærkning |
|---|---|---|---|
| Ingen (Ollama) | Lokal AI-model, kører på TimeLapse Pro's egen headend-server | Billeder til AI-tagging | Ingen tredjepart involveret — data forlader ikke serveren |
| Google Cloud / Gemini (Vertex AI eller AI Studio) | Cloud AI-billedanalyse ved eskalering | Billeder sendt til analyse, evt. inkl. personer i baggrunden | **Skal bekræftes:** `headend/ai/gemini_service.py` understøtter en EU-region-indstilling til Vertex AI-batch-processering (kodekommentar fremhæver eksplicit at bucket'en SKAL ligge i samme EU-region), men den faktisk KONFIGUREREDE region er ikke verificeret i denne gennemgang — kræver opslag i det faktiske deployment (miljøvariabler/GCP-projektindstillinger) |
| GitHub | Kodedistribution/opdateringer til edge-enheder | Ingen kundedata — kun software/konfiguration | Ingen GDPR-relevans |
| Cloudflare | Netværksrouting (Tunnel) til den offentlige webadresse | Transporterer trafik, herunder billeddata i transit | Bør bekræftes om Cloudflare har adgang til at inspicere/cache indhold, eller udelukkende router trafik (TLS-terminering-detaljer bør tjekkes) |

**Anbefaling:** Bekræft Gemini/Vertex AI's faktiske region-indstilling som allerførste
skridt — hvis den IKKE er sat til en EU-region, er dette et selvstændigt, akut punkt
der skal rettes (potentiel tredjelandsoverførsel uden gyldigt overførselsgrundlag).

---

## 5. Udkast til oplysningspligt (GDPR art. 13/14) [KUNDE, skabelon-tekst]

> Forslag til skilte-/informationstekst kunden kan bruge på byggepladsen. Kræver
> juridisk godkendelse før brug — dette er kun et sprogligt udkast.

"Denne byggeplads er under kameraovervågning til brug for fremdriftsdokumentation.
Billeder opbevares i [X] og behandles af [KUNDENS NAVN] som dataansvarlig. TimeLapse
Pro fungerer som databehandler. Spørgsmål om databehandlingen rettes til [KUNDENS
KONTAKT]."

---

## 6. Sammenhæng til øvrige dokumenter

- `RISK_ASSESSMENT_v10.md` R12 (GDPR-evidens) — dette dokument adresserer DPIA-skabelon,
  retention-design og subprocessor-liste. Databehandleraftale (G-03) og
  brudprocedure (G-06) mangler stadig og kræver en jurist.
- `RISK_ASSESSMENT_v10.md` R18 (nyt, 2026-07-04) — fundet under research til dette
  dokument: `gdpr_manager.py` mangler helt i kodebasen, hvilket betyder GDPR-
  detektioner (§2.2) ikke kan gemmes isoleret selv hvis de blev fundet. Selve
  integritetsbugget (stille-crashende Gemini-eskalering) er rettet; det underliggende
  manglende modul er ikke.
- `GO_LIVE_CHECKLIST_v10.md` §G — opdateres til at pege på dette dokument.
