# TimeLapse Pro — Intern CA / mTLS til Device-identitet — Design-notat

**Forfatter:** Claude · **Dato:** 2026-07-05 · **Status:** Til godkendelse (kode følger IKKE af sig selv — se §9)
**Beslægtet:** `RISK_ASSESSMENT_v10.md` §13–14 (PKI-skelet, Key Management UI-krav), R05/R07/R08,
`SABSA_Architecture_v10.md`, `HANDOVER_LOG.md` (opgave "#52 intern CA/mTLS-design", udskudt
flere runder — se entries 2026-07-04/05).

> **Dette er et design-/beslutningsoplæg, ikke en implementering.** Opgaven kræver et
> arkitekturvalg (§6) som kun Peter kan træffe (det ændrer produktionens netværkstopologi via
> Cloudflare Tunnel). Ingen kode er rørt i denne omgang.

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
  termineres i dag af Cloudflare Tunnel/nginx (se §6), device-laget er ren applikationslag-HMAC
  ovenpå en i øvrigt anonym TLS-forbindelse.
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
| **Komponent** | Python `cryptography`-biblioteket (allerede i venv, jf. Fernet-brug i `cmdb.py`); Cloudflare Tunnel/`cloudflared` eller nginx `ssl_client_certificate` afhængig af §6-valg. |
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
| TLS-termination | Cloudflare Tunnel → nginx `127.0.0.1:18443` (jf. GO_LIVE_CHECKLIST A-02/A-04) | Cloudflare/nginx-niveau, **ikke device-specifik** |

Konklusion: der findes **ingen PKI-kode overhovedet** i dag (bekræftet ved `grep` for `cryptography`/
`x509`/`generate_private_key` i `headend/` og `edge/` — eneste træffere er Fernet-symmetrisk kryptering
i `cmdb.py`, urelateret). §13 i RISK_ASSESSMENT_v10 er et **arkitektur-skelet fra v6**, ikke kode.

---

## 4. Foreslået PKI-hierarki

```
TimeLapse Root CA                       (offline, Mac Mini, 10 års levetid — bevaret fra v6)
  └── TimeLapse Issuing CA              (NY: online, kortere levetid, signerer device-certs løbende)
        ├── Headend Server Cert         (evt. — kun relevant hvis §6 vælger "direkte" model)
        └── Device Client Cert × N      (pr. Orange Pi, CN = device_id, SAN = device_id)
```

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
| Levetid | 6 måneder (bevaret fra §13.2) | 2 år |
| Revokering | CRL eller OCSP — se §7 | — |

---

## 5. Integration med eksisterende auth (ikke et enten/eller)

**Anbefaling: mTLS lægges *ved siden af* HMAC, ikke i stedet for — i første omgang.**

Begrundelse: HMAC-request-signaturen beskytter mod *replay/tampering på applikationslaget* og virker
allerede uafhængigt af TLS-laget (nyttigt hvis Cloudflare Tunnel nogensinde termineres af noget der
ikke er fuldt tillid til, eller ved fremtidig debugging via proxy). mTLS beskytter *hvem der overhovedet
får lov at åbne TLS-forbindelsen*. De to lag dækker forskellige trusler (jf. IEC 62443 defense-in-depth)
og bør ikke erstatte hinanden i første version:

1. **Fase 1 (dette forslag):** mTLS kræves for at nå Headend API overhovedet. `device_id` udledes
   fra certifikatets CN i stedet for at blive taget fra en request-header/JWT-claim — fjerner en
   klasse af "device hævder at være X"-fejl. HMAC-laget bevares uændret ovenpå.
2. **Fase 2 (senere, separat beslutning):** når mTLS har kørt stabilt i produktion i en periode,
   revurdér om HMAC-signaturen kan nedgraderes til valgfri/diagnostisk, eller om begge lag bevares
   permanent (defense-in-depth er ofte det rigtige svar for et system med både fysisk edge-eksponering
   R05 og internet-eksponering).

Dette holder **blast radius lille**: mTLS-udrulning kan fejle/rulles tilbage uden at ændre den
eksisterende HMAC-kode i `headend/main.py:2098-2127` overhovedet.

---

## 6. Åbent arkitekturvalg — KRÆVER Peters beslutning før kode skrives

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

---

## 7. Nøglelivscyklus

| Handling | Trigger | Mekanisme |
|---|---|---|
| **Udstedelse** | Ved bootstrap (`/api/bootstrap`, `/api/bootstrap/batch`) | Device genererer keypair lokalt (privatnøgle forlader ALDRIG device'et), sender CSR til Headend; Issuing CA signerer, cert leveres tilbage i samme response/provisioneringspakke som i dag bærer `bootstrap_token` |
| **Rotation** | 6 måneder (§4.1), eller manuel fra Key Mgmt UI | Device genererer ny CSR før udløb (analogt til JWT-refresh-mønster), Headend re-signerer — ingen nedetid hvis rotation sker med margin (fx 30 dage før udløb, planlagt job i samme stil som `_backup_auto_loop`/`_baseline_recompute_loop`) |
| **Revokering** | Fysisk kompromitteret device (R05), device udfaset | Cert tilføjes til CRL, **eller** OCSP-responder markerer den spærret. Se afvejning nedenfor. |

**CRL vs. OCSP for dette system:** Med formentlig **titalls, ikke tusindvis** af devices (edge-fleet-
størrelsesorden, jf. CMDB-omtaler i eksisterende dokumentation) er en simpel CRL, publiceret af
Headend og læst af nginx/`cloudflared` med kort cache-TTL, tilstrækkelig og markant simplere end en
fuld OCSP-responder-tjeneste. Anbefaling: **CRL**, revurdér til OCSP kun hvis fleet-størrelsen vokser
til at gøre CRL-download tungt.

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

## 9. Implementeringsplan (faser, ikke datoer — afhænger af §6-beslutning)

1. **Peter/Codex træffer §6-beslutning** (Cloudflare Access-model vs. ende-til-ende) — blocker for
   alt kode. Kræver et kig i Cloudflare-dashboardet (Access-planniveau) som jeg ikke har adgang til.
2. **Root + Issuing CA-generering** (offline-script, samme mønster som Fernet-nøglegenerering i
   `cmdb.py:416` — `python3 -c "from cryptography...` étliner til dokumentation, ikke et UI-klik for
   Root CA specifikt).
3. **Headend: CSR-signering i bootstrap-flowet** (`headend/main.py:1640/1765`) — udvid
   `BootstrapResponse`/`BatchBootstrapResponse` med signeret cert + Issuing CA-kæde.
4. **Edge: CSR-generering ved bootstrap** (`edge/agent.py` eller en ny `bootstrap_agent.py`-funktion,
   jf. kommentaren i `headend/main.py:1765` om `bootstrap_agent.py`).
5. **Transport-laget** (nginx `ssl_client_certificate` ELLER Cloudflare Access-policy, afhængig af
   §6) — Codex-ejet, kræver Mac Mini/Cloudflare-adgang jeg ikke har.
6. **Key Mgmt UI-udvidelse** (§8) — ren frontend/backend-kode, kan gøres af Claude når 3–5 er på plads.
7. **CRL-generering og -distribution** — nyt periodisk job, samme stil som eksisterende
   `_backup_auto_loop`.

**Ingen af disse faser er "en afgrænset, sikker kørsel uden opsyn"** i deres nuværende form — de
kræver enten §6-beslutningen fra Peter, eller ændringer i selve bootstrap-protokollen som bør
gennemgås før commit (auth-kode, jf. eksisterende fast konvention om ikke at røre auth-kode
uden ekstra dobbelttjek). Dette dokument er derfor leverancen for denne runde; kode afventer §6.

---

## 10. Åbne spørgsmål til Peter (opsummeret)

1. Understøtter jeres Cloudflare-plan Access mTLS/service tokens (Model A i §6)? Afgør hele
   implementeringsretningen.
2. Er 6-måneders device-cert-levetid (bevaret fra v6, §13.2) stadig ønsket, eller skal den
   revurderes samtidig med denne udrulning?
3. Skal HMAC-laget (§5) bevares permanent ved siden af mTLS, eller er hensigten på sigt at erstatte
   det? (Anbefaling: bevar begge — defense-in-depth, lav ekstra kompleksitet ved at beholde
   eksisterende, allerede-fungerende kode.)

---

## 11. Dokumenthistorik

| Dato | Ændring |
|---|---|
| 2026-07-05 | Claude (periodisk tjek): Første version — design-notat for #52, ingen kode rørt |
