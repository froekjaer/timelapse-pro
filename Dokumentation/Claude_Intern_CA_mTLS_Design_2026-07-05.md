# TimeLapse Pro — Intern CA / mTLS til Device-identitet — Design-notat

**Forfatter:** Claude · **Dato:** 2026-07-05 · **Status:** Besluttet 2026-07-05 (Peter) — Model B
valgt, alle §10-spørgsmål besvaret, ingen blockers tilbage; klar til kodefase (kode følger IKKE af
sig selv — se §9's faseplan)
**Beslægtet:** `RISK_ASSESSMENT_v10.md` §13–14 (PKI-skelet, Key Management UI-krav), R05/R07/R08,
`SABSA_Architecture_v10.md`, `HANDOVER_LOG.md` (opgave "#52 intern CA/mTLS-design" — designfasen
afsluttet 2026-07-05, se entries 2026-07-04/05).

> **Dette var oprindeligt et rent design-/beslutningsoplæg.** Arkitekturvalget (§6) krævede Peters
> beslutning, fordi det berørte produktionens netværkstopologi (Cloudflare Tunnel/Access vs.
> direkte eksponering). **Peter har siden truffet valget (Model B, §6) og besvaret alle
> opfølgningsspørgsmål (§10)** — designet er derfor færdigt og blocker-frit. Ingen kode er rørt
> endnu; §9 beskriver den resterende, ikke-startede implementeringsplan.

---

## 1. Hvorfor (problem og formål)

I dag identificerer et Orange Pi-device sig over for Headend med to lag, begge **delte hemmeligheder**,
ikke certifikater:

1. **Bearer-token** (`device.api_token`, udstedt ved `/api/bootstrap` eller zero-touch batch-bootstrap)
   — sammenlignet med `hmac.compare_digest` (`headend/main.py:2071`).
2. **HMAC-SHA256 request-signatur** (`alg=hmac-sha256-v1`, device-specifik `secret` + timestamp +
   nonce) — verificeret i `headend/main.py:2098-2127`. R15-arbejdet (juli) gjorde denne enforcement
   sporbar (`api_hmac_required`/`api_hmac_missing`-tællere, `headend/main.py:2503,2585-2655`), men
   den er stadig **ikke globalt påtvunget** (§11 P0.5 "HMAC enforcement globalt" er fortsat åben).

Det der **mangler**, og som R05/R07/R08 peger på, er en **stærk, asymmetrisk device-identitet**:

- Delte hemmeligheder kan **eksfiltreres fra device'et** (fysisk adgang til Orange Pi, R05) og
  genbruges et vilkårligt sted uden at det efterlader spor på den anden legitime part.
- Der er **ingen kryptografisk binding** mellem "dette TLS-lag" og "dette device" — TLS
  termineres i dag direkte af nginx på port 8443 (staging/prod, ingen Cloudflare Tunnel, se §6/§8-
  korrektionen), device-laget er ren applikationslag-HMAC ovenpå en i øvrigt anonym TLS-forbindelse.
- Revokering i dag = markér `device.api_token`/secret som `revoked` i DB. Det virker, men er
  **reaktivt** (kun opdaget ved næste requests) og har ingen kryptografisk kæde til en CA man kan
  spærre centralt.

mTLS med en intern CA løser dette ved at gøre device-identitet til en **kryptografisk egenskab af
selve TLS-håndtrykket**, ikke noget der efterprøves i applikationskoden efter at forbindelsen er
oprettet.

---

## 2. SABSA-forankring (kort)

| SABSA-lag | For dette system |
|---|---|
| **Kontekstuelt** (forretning) | Kundens tillid til at *kun deres egne* kameraer/edges kan levere billeder ind i deres site — device-identitet er en del af multi-tenant-løftet (jf. R16-lækagesagen, som var en *autorisations*-fejl, ikke en *autentificerings*-fejl, men samme tillidskæde). |
| **Konceptuelt** (attributter) | *Authentic, Accountable, Non-repudiable, Revocable, Scalable* (O(1) pr. device ved rotation af mellemliggende CA, jf. §13.3 i RISK_ASSESSMENT). |
| **Logisk** | Root CA → (evt. Intermediate CA) → device client cert; TLS-håndtryk kræver klientcert; applikationslag læser `device_id` fra certifikatets CN/SAN i stedet for fra en payload. |
| **Fysisk** | Root CA offline/air-gapped på Mac Mini (allerede besluttet i v6, §13.1); device certs leveres via provisioneringspakke ved bootstrap. |
| **Komponent** | Python `cryptography`-biblioteket (allerede i venv, jf. Fernet-brug i `cmdb.py`); nginx `ssl_client_certificate` (Model B, besluttet 2026-07-05 — Cloudflare Tunnel indgår ikke i prod-arkitekturen, se §6). |
| **Drift** | Codex ejer launchd/OS/Cloudflare-konfiguration; Claude ejer CA-kode/DB-skema/UI; Peter ejer go/no-go på §6. |

**Standard-kroge:** ISO 27001 A.10 (kryptografi), A.9.4 (system-/applikationsadgangskontrol);
IEC 62443 SR 1.1/1.2 (identifikation, device-autentificering), FR 1 (identification & authentication
control); CRA (secure-by-default identitet, ingen delte long-lived secrets som eneste forsvar);
GDPR: styrker access control omkring billeddata (art. 32 — passende tekniske foranstaltninger),
men er ikke i sig selv en GDPR-retsgrund.

---

## 3. Nuværende tilstand (grundlag for designet — verificeret ved kodelæsning i dag)

| Komponent | Fil | Mekanisme i dag |
|---|---|---|
| Første kontakt | `headend/main.py:1640` `/api/bootstrap` | Bootstrap-token (DB, `revoked=False`) → udsteder `api_token` + HMAC-secret |
| Zero-touch batch | `headend/main.py:1765` `/api/bootstrap/batch` | Samme, men token har `max_uses` (multi-device) |
| Request-auth (bearer) | `headend/main.py:2071` | `hmac.compare_digest(provided, device.api_token)` |
| Request-auth (signatur) | `headend/main.py:2098-2127` | `hmac-sha256-v1` over `timestamp+nonce+body`, sammenlignet mod device-secret |
| Enforcement-status | `headend/main.py:2503,2585-2655` | Tælles og vises (R15), men **ikke globalt påtvunget** |
| Provisioneringspakke | `headend/main.py:9438` `_build_bootstrap_yaml` | Genererer `bootstrap.yaml` med token — **intet certifikat i dag** |
| TLS-termination | nginx direkte på port **8443** på staging/prod (rettet 2026-07-05: CrushFTP ejer 21/22/80/443 på disse maskiner, ingen Cloudflare Tunnel — jf. GO_LIVE_CHECKLIST A-01–A-04/A-13 og PORT_AUDIT_og_WEBSITE_v10.md §3/§4) | nginx-niveau, **ikke device-specifik** |

Konklusion: der findes **ingen PKI-kode overhovedet** i dag (bekræftet ved `grep` for `cryptography`/
`x509`/`generate_private_key` i `headend/` og `edge/` — eneste træffere er Fernet-symmetrisk kryptering
i `cmdb.py`, urelateret). §13 i RISK_ASSESSMENT_v10 er et **arkitektur-skelet fra v6**, ikke kode.

---

## 4. Foreslået PKI-hierarki

```
TimeLapse Root CA                       (Mac Mini/R&D, 10 års levetid — bevaret fra v6, se §4.2 om placering)
  └── TimeLapse Issuing CA              (NY: online, kortere levetid, signerer device-certs løbende)
        ├── Headend Server Cert         (relevant nu — Model B er valgt, se §6)
        └── Device Client Cert × N      (pr. Orange Pi, CN = device_id, SAN = device_id)
```

### 4.2 Root CA-placering — BESLUTTET, med forbehold (2026-07-05, Peter)

Peters svar: "Jeg vil pt. gerne have den på denne (R&D) maskinen, da den nok vil være den maskine
der er mindst eksponeret. Du må dog meget gerne bygge den fleksibel, så den senere kan flyttes."

**Vigtig nuance jeg vil fremhæve før dette implementeres (dobbelttjekker før du udfører):**
"Mindst eksponeret" holder for netværkseksponering (R&D har ingen indgående Internet-trafik ud
over admin-login), men R&D-maskinen er PRÆCIS den maskine, Claude og Codex arbejder frit på hver
dag — via almindelige fil-værktøjer (samme slags, jeg netop har brugt til at redigere
`headend/main.py` i denne session). Hvis Root CA's private nøgle lægges et sted under den
sti, mine værktøjer kan læse (dvs. under `~/projects/timelapse-pro/` — hvad enten det er i
selve Git-repoet eller blot en undermappe på samme volumen), ville jeg de-facto kunne læse den,
uanset politikbeslutningen om at agenter ikke må have adgang til prod. Det er ikke en advarsel
om ond hensigt — det er en påpegning af at "denne maskine er mindst eksponeret over Internet" og
"denne maskine er utilgængelig for Claudes fil-værktøjer" er to FORSKELLIGE egenskaber, og kun
den første er sand for R&D i dag.

**Anbefaling (implementerer den ønskede fleksibilitet):** placér Root CA's private nøgle UDENFOR
Git-repoet og udenfor `~/projects/timelapse-pro/` — fx `/etc/timelapse/ca/root/ca-key.pem` med
`600`-rettigheder ejet af `peter` (eller `root`), præcis samme mønster som `headend.env` allerede
bruger i dag for at holde secrets ude af mine værktøjers rækkevidde (jf.
`SERVICES_OG_DRIFT_kilde_til_sandhed.md`). Genereringen bør ske via et script Peter selv kører i
Terminal (jeg kan skrive scriptet, men ikke eksekvere det eller læse output-nøglen bagefter).
Dette opfylder både "ligger på R&D-maskinen nu" og "reelt utilgængelig for agenter" — og gør det
let at flytte senere (kopiér blot filen til den nye maskine, ingen kode-ændring nødvendig, da
stien er en konfigurationsværdi).

**Hvorfor en Issuing CA og ikke Root CA signerer direkte** (ændring ift. skelettet i §13.1, som
ikke skelnede): Root CA'ens private nøgle skal aldrig røre et system der er online/routinemæssigt
tilgået (device-udstedelse sker ved hvert bootstrap — potentielt ugentligt ved kunde-vækst). En
Issuing CA, signeret én gang af Root CA og opbevaret på Headend (kryptet i hvile, samme mønster
som `cmdb.py`'s Fernet-nøgle), holder Root CA'ens eksponering minimal. Kompromitteres Issuing CA,
spærres/genudstedes den fra Root CA uden at røre allerede udstedte device-certs' tillidskæde
fundamentalt (de skal dog re-udstedes — acceptabel kost, sjældent scenarie).

### 4.1 Certifikatprofil (forslag)

| Felt | Device client cert | Issuing CA cert |
|---|---|---|
| Nøglealgoritme | ECDSA P-256 (mindre CPU/strøm-fodaftryk på Orange Pi end RSA-2048) | ECDSA P-256 eller RSA-2048 |
| CN | `device_id` (fx `TL-C87FF9587CA0`, matcher eksisterende device-ID-format) | `TimeLapse Issuing CA` |
| SAN | `URI:timelapse:device:<device_id>` (undgår DNS-navne-krav for interne device-IDs) | — |
| Extended Key Usage | `clientAuth` | — |
| Levetid | **10 år, default — konfigurerbar, se §4.3** (ændret 2026-07-05, erstatter §13.2's oprindelige 6 måneder) | 2 år |
| Revokering | CRL — se §7. **Skal altid stoppe kommunikation øjeblikkeligt, uanset levetids-konfiguration (§4.3)** | — |

### 4.3 Certifikat-levetid — politik og konfiguration (BESLUTTET 2026-07-05, Peter)

Peters svar på §10 spørgsmål 2: "Jeg vil pt. gerne have default 10 års levetid, og mulighed (i
config. hierakiet - global/kunde/site/kamera) ændre, samt mulighed for at konfigurere om forældet
certifikat påvirker driften. Revoket certifikater skal selvfølgelig stoppe kommunikationen til den
fokale enhed."

Dette er tre separate beslutninger, som bør holdes adskilt i design og kode:

1. **Default levetid: 10 år** (ikke 6 måneder som i v6-skelettet, §13.2) — markant længere end den
   oprindelige antagelse, fordi devices ofte sidder fysisk svært tilgængeligt i lang tid ad gangen
   (byggepladser), og hyppig automatisk rotation tilføjer kompleksitet uden tilsvarende
   sikkerhedsgevinst for denne trusselsmodel.
2. **Konfigurerbar pr. lag i den EKSISTERENDE config-hierarki** (global → kunde → site → kamera,
   jf. `_resolve_config_hierarchy()` i `headend/main.py:12253` — samme mønster som fx
   `debug_mode`/FLEET_DEFAULTS allerede bruger). Cert-levetid bliver et nyt felt i dette hierarki,
   ikke en ny, parallel konfigurationsmekanisme — device-certifikatets faktiske udløbsdato
   beregnes ved udstedelse ud fra den effektive, nedarvede værdi for det pågældende kamera/device.
3. **Separat, konfigurerbar politik: "påvirker et UDLØBET (ikke revokeret) certifikat driften?"**
   — dvs. om Headend skal afvise forbindelser fra et device med et cert, der er teknisk udløbet men
   ikke revokeret (fx en byggeplads uden internetadgang i en periode, der forhindrede rettidig
   rotation), eller acceptere det i en "grace"-tilstand indtil rotation kan gennemføres. Dette er
   et separat felt i samme config-hierarki — ikke et alt-eller-intet-flag globalt.

**VIGTIGT — revokering er IKKE en del af denne konfigurerbarhed:** et **revokeret** certifikat
(CRL) skal ALTID stoppe kommunikation til det pågældende device øjeblikkeligt, uanset
udløbs-/grace-politikken ovenfor. Revokering og udløb er to forskellige tilstande i denne model:
udløb er en "tid er gået"-tilstand, som Peter ønsker fleksibilitet omkring; revokering er en
"dette device er ikke længere tillid" — en aktiv sikkerhedsbeslutning, der aldrig bør være
konfigurerbart bort. Dette skal håndhæves i koden som to adskilte tjek, ikke ét kombineret
"er certifikatet gyldigt?"-flag.

**Implikation for §7 (CRL-friskhed):** fordi certifikater nu lever op til 10 år (ikke 6 måneder),
bliver CRL-distributionens FRISKHED den reelle "hvor hurtigt kan vi spærre et kompromitteret
device"-kontrol — en lang cert-levetid uden hyppig CRL-opdatering ville betyde et kompromitteret,
langtidslevende certifikat forbliver gyldigt i lang tid, hvis CRL'en sjældent hentes. Anbefaling:
hold CRL-cache-TTL kort (minutter, ikke timer/dage) på nginx/Headend-siden, uafhængigt af selve
cert-levetiden — dette bliver vigtigere, ikke mindre vigtigt, med den nu besluttede lange levetid.

---

## 5. Integration med eksisterende auth (ikke et enten/eller)

**BESLUTTET 2026-07-05 (Peter, svar på §10 spørgsmål 3):** "Enig, men alt fremtidige skal på
mTLS, og jeg vil gerne have den aktuelle opsætning over på mTLS, så vi er sikker på at det
virker." Det vil sige: begge lag bevares **permanent** (ikke kun som en fase-1-mellemstation),
OG mTLS er ikke kun for nye devices — det eksisterende, allerede-bootstrappede R&D-device
(`Frøkjær`) skal RETROFITTES til mTLS som en del af denne udrulning, netop for at bevise
end-to-end at det virker, før flere devices/kunder kommer til.

Begrundelse for at bevare begge lag permanent: HMAC-request-signaturen beskytter mod
*replay/tampering på applikationslaget* og virker uafhængigt af TLS-laget. mTLS beskytter *hvem
der overhovedet får lov at åbne TLS-forbindelsen*. De to lag dækker forskellige trusler (jf. IEC
62443 defense-in-depth) — lav ekstra kompleksitet ved at beholde eksisterende, allerede-fungerende
HMAC-kode uændret, mens mTLS lægges ovenpå.

**Udrulningsrækkefølge (opdateret ift. den oprindelige "fase 1/fase 2"-formulering):**

1. **Alle NYE devices bootstrappes direkte med mTLS** fra den dag koden er klar — ingen
   overgangsperiode for nye devices, HMAC bevares som ekstra lag ovenpå, ikke som eneste
   beskyttelse.
2. **Det eksisterende R&D-device (`Frøkjær`) retrofittes til mTLS** — kræver en
   "re-bootstrap"/cert-udstedelses-vej for allerede-provisionerede devices (ikke kun
   først-gangs-bootstrap-flowet i §9 trin 3-4), da device'et allerede har et `api_token`/HMAC-
   secret og skal have et klientcertifikat tilføjt UDEN at miste eksisterende data/historik.
   Dette er den konkrete verifikation af, at hele kæden virker i praksis, før den rulles ud til
   Kirkbi A/S/Travbyen eller fremtidige kunder.
3. **HMAC-laget forbliver PERMANENT** ved siden af mTLS for alle devices, ikke kun midlertidigt —
   ingen fremtidig "nedgrader HMAC til valgfri"-beslutning er planlagt.

Dette ændrer omfanget af §9 (implementeringsplan) — se tilføjet trin 3b.

---

## 6. Arkitekturvalg — BESLUTTET 2026-07-05 (Peter): Model B

Dette er grunden til at #52 gentagne gange er blevet udskudt som "ikke afgrænseligt til én kørsel
uden Peter": mTLS's placering afhænger af hvordan Cloudflare Tunnel bruges, og det er en
netværkstopologi-beslutning, ikke en kodebeslutning.

| Model | Beskrivelse | Fordele | Ulemper |
|---|---|---|---|
| **A: Cloudflare Access mTLS / service tokens** | `cloudflared` valideres device-certs ved tunnel-indgangen (Cloudflare Access "mTLS"-policy eller service tokens), Cloudflare terminerer stadig public TLS | Ingen ændring af A-01–A-04 (GO_LIVE_CHECKLIST) — Cloudflare-arkitekturen fra go-live-planen bevares fuldt ud | Cloudflare bliver en *nødvendig* del af tillidskæden for device-identitet, ikke kun transport; kræver Cloudflare Access-plan-niveau der understøtter dette (skal bekræftes — Codex/Peter har adgang til Cloudflare-dashboardet, jeg har det ikke) |
| **B: Ende-til-ende mTLS til nginx/Headend selv** | `cloudflared` proxy'er TCP transparent (eller device'er forbinder uden om Cloudflare for API-trafik), nginx/Headend selv validerer klientcert (`ssl_client_certificate` i nginx, eller FastAPI/Starlette-mellemlag) | Fuld ende-til-ende kryptografisk kæde, uafhængig af Cloudflare | Kræver formentlig en separat indgang uden om den planlagte Cloudflare Tunnel for device-trafik (modstrider evt. A-01–A-04-designet, som netop vil lukke alt direkte porteksponering) — **skal afklares mod GO_LIVE_CHECKLIST §A før dette vælges** |
| **C: Hybrid** | Cloudflare Tunnel til brugere/UI (model som i dag), separat, snævert scoped mTLS-only endpoint kun for device-trafik | Adskiller bruger- og device-tillidskæder rent | Mest kompleksitet — to indgange at drifte/overvåge |

**Claudes anbefaling uden at kunne se Cloudflare-planen/dashboardet:** Model A, hvis Cloudflare
Access understøtter det på jeres plan — mindst arkitektur-friktion mod det allerede besluttede
Tunnel-design (A-01–A-04). Dette **kan ikke bekræftes af mig** (ingen adgang til Cloudflare-kontoen),
så det er den konkrete blocker for at gå fra design til kode.

**BESLUTTET 2026-07-05 (Peter):** **Model B — ende-til-ende mTLS til nginx/Headend selv.**
Peter har samtidig bekræftet at Cloudflare Tunnel bevidst skal undgås for prod (se
`MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §8 og det opdaterede `GO_LIVE_CHECKLIST_v10.md` §A). Det
fjerner selve forudsætningen for Model A (som kun gav mening hvis Cloudflare Tunnel/Access var i
vejen) og gør Model B til det naturlige, konfliktfrie valg.

**RETTET 2026-07-05 (2. runde, port-korrektion):** Prod-arkitekturen blev først beskrevet her som
"direkte nginx-eksponering på standard 443/80" — det viste sig at være forkert, da CrushFTP
allerede kører på både staging-iMac'en og prod-Mac Mini'en og optager 21/22/80/443 dér (bekræftet
af Peter). Den faktiske arkitektur er i stedet: nginx direkte på **port 8443**, ægte Let's
Encrypt-certifikat via **DNS-01** (`certbot-dns-cloudflare`, rører ingen port), hostname-routet
(se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4 og det opdaterede `www/index.html`, hvis login-knapper nu
peger på `https://backend.timelapse-pro.dk:8443/`). Dette ændrer IKKE selve Model B-beslutningen —
mTLS-laget sidder stadig i nginx/Headend, blot på en anden portadresse end først antaget.
A-01–A-04/A-13s Tunnel-/443-krav er allerede rettet i `GO_LIVE_CHECKLIST_v10.md`. Peter bruger
Cloudflares gratis niveau (evt. som valgfri DNS-proxy foran 8443), men ikke til Access mTLS/Tunnel
for prod-trafikken. Cloudflare-plan-spørgsmålet (§10 punkt 1) er dermed IKKE længere relevant for
denne beslutning.

---

## 7. Nøglelivscyklus

| Handling | Trigger | Mekanisme |
|---|---|---|
| **Udstedelse** | Ved bootstrap (`/api/bootstrap`, `/api/bootstrap/batch`), ELLER retrofit-flow for allerede-provisionerede devices (nyt, se §9 trin 3b) | Device genererer keypair lokalt (privatnøgle forlader ALDRIG device'et), sender CSR til Headend; Issuing CA signerer, cert leveres tilbage i samme response/provisioneringspakke som i dag bærer `bootstrap_token` |
| **Rotation** | Effektiv levetid fra config-hierarkiet (default 10 år, §4.3), eller manuel fra Key Mgmt UI | Device genererer ny CSR før udløb (analogt til JWT-refresh-mønster), Headend re-signerer — ingen nedetid hvis rotation sker med margin. Given den lange default-levetid er dette job mindre tidskritisk end oprindeligt antaget (var 6 måneder), men bør stadig bygges nu, samme stil som `_backup_auto_loop`/`_baseline_recompute_loop` |
| **Udløb (uden revokering)** | Cert-levetid overskredet | Konfigurerbar pr. §4.3: enten hård afvisning, eller "grace"-tilstand indtil rotation — IKKE det samme som revokering, se §4.3 |
| **Revokering** | Fysisk kompromitteret device (R05), device udfaset | Cert tilføjes til CRL, **eller** OCSP-responder markerer den spærret. Stopper ALTID kommunikation øjeblikkeligt — ikke konfigurerbart (§4.3). Se afvejning nedenfor. |

**CRL vs. OCSP for dette system:** Med formentlig **titalls, ikke tusindvis** af devices (edge-fleet-
størrelsesorden, jf. CMDB-omtaler i eksisterende dokumentation) er en simpel CRL, publiceret af
Headend og læst af nginx med kort cache-TTL, tilstrækkelig og markant simplere end en fuld
OCSP-responder-tjeneste. Anbefaling: **CRL**, revurdér til OCSP kun hvis fleet-størrelsen vokser
til at gøre CRL-download tungt. (Se §4.3 for hvorfor CRL-friskhed nu er ekstra vigtig med en
10-års default cert-levetid.)

---

## 8. Key Management UI — udvidelse af eksisterende §14-krav

RISK_ASSESSMENT_v10 §14 spec'er allerede en "Nøglehåndtering"-side. Denne mTLS-arkitektur kræver
følgende **tilføjelser** til det eksisterende funktionskrav (ikke en ny side):

- **Issuing CA-status:** udløbsdato, fingerprint, "generér ny Issuing CA" (kun `super_admin`,
  kræver Root CA-adgang — sandsynligvis en manuel/offline handling på Mac Mini, ikke et UI-klik).
- **Device client cert-liste:** udvidelse af den eksisterende device client cert-liste (§14 nævner
  den allerede som "list aktive device client certs m. udløb") med CN/SAN, udstedelsesdato, og en
  **"Spærr" (CRL)**-knap ud over den eksisterende "markér revokeret"-handling for SSH-nøgler.
- **Provisioneringspakke (§14):** `_build_bootstrap_yaml` (`headend/main.py:9438`) skal udvides til
  også at inkludere `headend_ca.crt` (Issuing CA — allerede nævnt i §14's pakke-indhold!) og
  device-nøglegenerering/CSR-flow — **§14 forudsatte faktisk allerede denne funktion**, den er bare
  aldrig implementeret.

---

## 9. Implementeringsplan (faser, ikke datoer — §6-beslutning truffet, ingen fase startet endnu)

1. ~~Peter/Codex træffer §6-beslutning~~ — **afsluttet:** Model B, ingen Cloudflare Access/Tunnel.
2. **Root + Issuing CA-generering** (offline-script, samme mønster som Fernet-nøglegenerering i
   `cmdb.py:416` — `python3 -c "from cryptography...` étliner til dokumentation, ikke et UI-klik for
   Root CA specifikt).
3. **Headend: CSR-signering i bootstrap-flowet** (`headend/main.py:1640/1765`) — udvid
   `BootstrapResponse`/`BatchBootstrapResponse` med signeret cert + Issuing CA-kæde. Inkluderer
   cert-levetid/udløbs-politik-opslag mod config-hierarkiet (§4.3).
4. **Edge: CSR-generering ved bootstrap** (`edge/agent.py` eller en ny `bootstrap_agent.py`-funktion,
   jf. kommentaren i `headend/main.py:1765` om `bootstrap_agent.py`).
5. **Retrofit af eksisterende R&D-device (`Frøkjær`) til mTLS** (BESLUTTET 2026-07-05, tilføjet som
   eksplicit trin) — kræver en separat "udsted cert til allerede-bootstrappet device"-vej (kan ikke
   genbruge `/api/bootstrap` uændret, da device'et allerede har `api_token`/HMAC-secret og aktiv
   historik). Dette er den konkrete ende-til-ende-verifikation Peter har bedt om, FØR kunder/flere
   devices kommer på mTLS — bør ske umiddelbart efter trin 3-4 er kodet, FØR trin 8 (Key Mgmt UI)
   og 9 (CRL) anses for "færdige", da retrofit-flowet sandsynligvis afslører kanttilfælde
   first-bootstrap-flowet ikke rammer.
6. **Transport-laget** (nginx `ssl_client_certificate` på port 8443 — Model B, ingen Cloudflare
   Access/Tunnel involveret, se §6) — Codex-ejet, kræver Mac Mini-adgang jeg ikke har.
7. **Cert-levetid + udløbs-politik i config-hierarkiet** (§4.3, BESLUTTET) — nye felter i
   `_resolve_config_hierarchy()`s eksisterende global/kunde/site/kamera-lag, adskilt fra
   revokeringslogik (som aldrig må være konfigurerbar).
8. **Key Mgmt UI-udvidelse** (§8) — ren frontend/backend-kode, kan gøres af Claude når 3–5 er på plads.
9. **CRL-generering og -distribution** — nyt periodisk job, samme stil som eksisterende
   `_backup_auto_loop`. Hold CRL-cache-TTL kort (§4.3) — vigtigere nu med 10-års cert-levetid.

**Ingen af disse faser er "en afgrænset, sikker kørsel uden opsyn"** i deres nuværende form — de
kræver enten §6-beslutningen fra Peter, eller ændringer i selve bootstrap-protokollen som bør
gennemgås før commit (auth-kode, jf. eksisterende fast konvention om ikke at røre auth-kode
uden ekstra dobbelttjek). Dette dokument er derfor leverancen for denne runde; kode afventer §6.

---

## 10. Åbne spørgsmål til Peter (opsummeret) — status 2026-07-05, ALLE BESVARET

1. ~~Understøtter jeres Cloudflare-plan Access mTLS/service tokens (Model A i §6)?~~ **Bortfaldet**
   — Model B er valgt, Cloudflare Tunnel/Access indgår ikke i prod-arkitekturen (se §6). Peter:
   "Enig - udgår."
2. **Besvaret (§4.3):** Device-cert-levetid er **10 år, default**, konfigurerbar pr.
   global/kunde/site/kamera via den eksisterende config-hierarki-mekanisme
   (`_resolve_config_hierarchy()`), IKKE de oprindelige 6 måneder fra v6/§13.2. Desuden
   konfigurerbart, separat fra revokering: om et UDLØBET (men ikke revokeret) certifikat blokerer
   drift, eller kører i en grace-tilstand. Revokerede certifikater stopper ALTID kommunikation
   øjeblikkeligt — ikke konfigurerbart. Peter: "Jeg vil pt. gerne have default 10 års levetid, og
   mulighed (i config. hierakiet - global/kunde/site/kamera) ændre, samt mulighed for at
   konfigurere om forældet certifikat påvirker driften. Revoket certifikater skal selvfølgelig
   stoppe kommunikationen til den fokale enhed."
3. **Besvaret (§5):** HMAC-laget bevares **permanent** ved siden af mTLS (ikke kun i en fase-1-
   mellemstation som oprindeligt foreslået). ALLE fremtidige devices skal på mTLS fra bootstrap.
   Det EKSISTERENDE R&D-device (`Frøkjær`) skal desuden **retrofittes til mTLS** som en konkret
   ende-til-ende-verifikation, før udrulning til flere kunder/devices — se §9 trin 5 (nyt).
   Peter: "Enig, men alt fremtidige skal på mTLS, og jeg vil gerne have den aktuelle opsætning
   over på mTLS, så vi er sikker på at det virker."
4. **Besvaret (§4.2):** Root CA-nøgle placeres pt. på R&D-maskinen, men UDENFOR mine
   værktøjers rækkevidde (uden for repoet) — se §4.2 for den konkrete anbefaling. Peter: "Enig."

**Status:** Alle fire designspørgsmål er nu besvaret af Peter (2026-07-05). Næste skridt er
STADIG IKKE at skrive selve PKI-koden i denne omgang — det er en betydelig, auth-nær kodeændring
(bootstrap-flow, DB-skema, edge-agent CSR-generering, retrofit-flow for eksisterende device), der
fortjener sin egen, fokuserede runde med ekstra dobbelttjek, ikke en hurtig tilføjelse oven på en
allerede lang session med mange andre ændringer (port-arkitektur-korrektion samme dag). Konkret
næste skridt: kode-fasen (§9, trin 2-9) kan nu påbegyndes som en ny, afgrænset opgave — design er
færdigt, ingen blockers tilbage.

---

## 11. Dokumenthistorik

| Dato | Ændring |
|---|---|
| 2026-07-05 | Claude (periodisk tjek): Første version — design-notat for #52, ingen kode rørt |
| 2026-07-05 (installationsscript-runde) | Claude: §6 opdateret — Peter har valgt Model B (ende-til-ende mTLS, ingen Cloudflare Tunnel/Access), efter at have bekræftet at Cloudflare Tunnel bevidst undgås for prod. §4.2 (ny) — Root CA-placering besluttet (R&D-maskinen, fleksibelt design), med en fremhævet nuance om at "mindst netværkseksponeret" og "utilgængelig for agenters filværktøjer" er to forskellige egenskaber — anbefaler nøglen placeres udenfor Git-repoet (`/etc/timelapse/ca/root/`), samme mønster som `headend.env`. §10 opdateret med status. Ingen PKI-kode skrevet endnu — bevidst udskudt til en separat, fokuseret runde givet auth-nærheden. |
| 2026-07-05 (port-korrektionsrunde, 2.) | Claude: §6 og tabellen i §5 rettet — "direkte nginx-eksponering på standard 443/80" (skrevet samme dag i forrige runde) var selv en fejlantagelse; CrushFTP ejer allerede 21/22/80/443 på både staging-iMac'en og prod-Mac Mini'en (bekræftet af Peter). Prod-arkitekturen er nu port **8443** + DNS-01-certifikat, ikke 443/80. Model B-beslutningen (§6) er uændret — kun portadressen mTLS/TLS termineres på er rettet. Se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4 for den fulde begrundelse. |
| 2026-07-05 (designspørgsmål besvaret) | Claude: Peter besvarede §10 spørgsmål 2-3 (spørgsmål 1+4 allerede afsluttet). Ny §4.3 tilføjet — cert-levetid 10 år default, konfigurerbar pr. global/kunde/site/kamera via eksisterende `_resolve_config_hierarchy()`, adskilt fra en separat udløbs-grace-politik, og adskilt fra revokering (som ALTID stopper kommunikation, ikke konfigurerbart). §5 opdateret — HMAC bevares permanent (ikke kun fase 1), alle fremtidige devices på mTLS, OG det eksisterende R&D-device skal retrofittes til mTLS som verifikation. §4.1, §7, §9 (nyt trin 5: retrofit) og §10 opdateret i tråd hermed. Design er nu færdigt — ingen åbne spørgsmål tilbage; kodefasen kan påbegyndes som ny, afgrænset opgave. Ingen kode rørt i denne runde. |
| 2026-07-06 (periodisk tjek #79) | Claude: §1 og §2 (SABSA-tabellen "Komponent"-rækken) rettede to interne, uopdaterede rester efter port-/Cloudflare-korrektionen — begge beskrev stadig TLS-terminering som "Cloudflare Tunnel/nginx" hhv. "afhængig af §6-valg", selvom §3 (linje 76), §6 og dokumentets eget statusfelt allerede fastslår Model B/port 8443/DNS-01/ingen Cloudflare Tunnel som besluttet og endeligt. Ren intern konsistensrettelse, ingen ny beslutning, ingen kode rørt. |
