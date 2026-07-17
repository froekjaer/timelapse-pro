# TimeLapse Pro — Installationsguide: Headend på Staging/Prod (v1)

**Dato:** 2026-07-05 · **Forfatter:** Claude · **Status:** Klar til brug, IKKE afprøvet på
rigtig hardware endnu (jeg har ingen adgang til staging/prod, jf. politikken nedenfor)

**Hvorfor dette dokument findes:** Peter har besluttet at Claude og Codex ALDRIG får adgang til
staging eller prod — kun R&D (se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §5). Det betyder Peter
skal kunne installere og drifte headend på nye maskiner helt uden agent-hjælp i selve
udførelsen. Denne guide + `deploy/install/install_headend.sh` er designet til at gøre det
muligt — udførligt nok til at stå alene, med alle kendte faldgruber allerede fanget på forhånd.

**Gælder for:** `staging` (iMac) og `prod` (`timelapse-pro.dk`, og eventuelle fremtidige
yderligere prod-servere). Gælder IKKE for `rd` (nuværende Mac Mini) — det system er allerede
kørende og driftes via de eksisterende dokumenter (`SERVICES_OG_DRIFT_kilde_til_sandhed.md`).

---

## 0. Overblik over hele forløbet

1. Forbered maskinen (§1-2)
2. Klon repoet + kør scriptet FØRSTE gang (§3-4) — bringer headend op på plain HTTP:8443, ingen TLS endnu
3. Sæt DNS (§5) og kør certbot DNS-01 (§6, rører ingen port), kør SÅ scriptet IGEN — nu med TLS
4. Første login + tvungen MFA-opsætning (§7) — kan IKKE scriptes
5. Opret yderligere brugere/roller via UI'en (§8)
6. Kend grænserne: hvad denne guide bevidst IKKE dækker endnu (§9)

**VIGTIGT — portvalg (rettet 2026-07-05, se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4):** Både
staging-iMac'en og prod-Mac Mini'en kører allerede **CrushFTP**, som optager port 21, 22, 80 og
443. TimeLapse Pro's nginx må ALDRIG binde til disse porte på disse maskiner. Backend kører derfor
på **port 8443** i stedet, og certifikatet udstedes via **DNS-01** (ikke den almindelige HTTP-01),
som slet ikke kræver at nginx besvarer noget på port 80. Marketingsitet
(`www.timelapse-pro.dk`) hostes desuden **et helt andet sted** end disse maskiner — se §5b.

---

## 1. Forudsætninger på den nye maskine

- macOS (staging: den eksisterende iMac; prod: efter Peters valg — se
  `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §7 for hvorfor macOS og ikke Linux, for nu).
- Homebrew installeret (`https://brew.sh`).
- Følgende Homebrew-pakker: `brew install python@3.12 postgresql@17 nginx node certbot`
- `pip3 install certbot-dns-cloudflare` (DNS-01-plugin — se §6; nødvendigt fordi CrushFTP ejer
  port 80 på denne maskine, så den almindelige HTTP-01-udfordring ikke er en mulighed).
- En Cloudflare API-token med KUN "Zone:DNS:Edit"-rettighed for jeres zone (Cloudflare
  dashboard → My Profile → API Tokens → Create Token) — brug IKKE din globale API-nøgle.
- PostgreSQL kørende lokalt (`brew services start postgresql@17`), med din bruger som normal
  psql-adgang (`psql -d postgres` skal virke uden fejl).
- Nok diskplads til billeddata på den valgte `TL_DATA_DIR` — dette er IKKE R&D-maskinens
  `/Volumes/data-fast`, det skal være et sted på DENNE maskine.
- Git-adgang til at klone `timelapse-pro`-repoet (samme repo som R&D, men en frisk kopi HER —
  ikke en netværksdeling til R&D-maskinen).

```bash
git clone <jeres-repo-url> /Users/peter/projects/timelapse-pro
```

## 2. Kapacitetstjek (kun relevant for `staging`, den ældre iMac)

Peters iMac er ikke kapacitetstestet endnu (se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §6.1).
Før du investerer tid i en fuld installation, tjek som minimum:

```bash
sysctl -n hw.memsize                 # RAM i bytes — headend+Postgres+nginx bør have min. 8 GB
df -h /                              # diskplads
sw_vers                              # macOS-version — skal kunne køre en nogenlunde ny Homebrew
```

Hvis RAM/disk er meget begrænset, overvej at køre `staging` UDEN Ollama/lokal AI (kun
headend+Postgres+nginx) — det er en gyldig, reduceret staging-profil.

## 3. Konfigurér din installation

Kopiér én af eksempelfilerne i `deploy/install/`:

```bash
cp deploy/install/example-staging.conf ~/timelapse-staging.conf   # ELLER:
cp deploy/install/example-prod.conf ~/timelapse-prod.conf
```

Åbn kopien og udfyld domæne, repo-sti og data-sti for DENNE maskine — se kommentarerne i filen.
Har I flere fremtidige prod-servere, laver I bare en ny kopi pr. maskine med sit eget
domæne/DB-navn.

## 4. Kør installationsscriptet — FØRSTE gang (før certifikat)

```bash
cd timelapse-pro/deploy/install
sudo ./install_headend.sh --config ~/timelapse-staging.conf --dry-run   # se hvad der VILLE ske
sudo ./install_headend.sh --config ~/timelapse-staging.conf             # kør for rigtigt
```

Dette gør (se scriptets kommentarer for detaljer):
- Opretter `/etc/timelapse/` og genererer `/etc/timelapse/headend.env` med et NYT, unikt
  `JWT_SECRET` (aldrig genbrugt fra R&D eller et andet miljø) og `TIMELAPSE_ENV=<staging|prod>`.
- Opsætter Python-venv + installerer `headend/requirements.txt`.
- Opretter PostgreSQL-database/-bruger (idempotent — gør intet hvis de allerede findes).
- Bygger UI'en (`npm run build`).
- Installerer og starter headend som launchd-service.
- Skriver en nginx-config og starter/genindlæser nginx — men KUN med et plain-HTTP-block på
  `TL_BACKEND_PORT` (default **8443**, IKKE port 80 — den ejes af CrushFTP på denne maskine) med
  en midlertidig "vent på certifikat"-side, fordi der endnu ikke findes noget TLS-certifikat.

Efter dette trin bør `curl http://127.0.0.1:8000/api/health` svare `{"status":"ok",...}` lokalt
på maskinen.

## 5. DNS

Peg det valgte backend-domænenavn (fx `backend.timelapse-pro.dk`) mod denne maskines OFFENTLIGE
IP-adresse hos jeres DNS-udbyder (almindeligt A-opslag, evt. med Cloudflares "orange sky"-proxy
aktiveret — det er valgfrit og understøtter port 8443, se `PORT_AUDIT_og_WEBSITE_v10.md` §4).
Fordi certifikatet udstedes via DNS-01 (§6), behøver DNS'en ikke at være propageret FØR du kører
certbot — DNS-01 tjekker et TXT-opslag i selve zonen, ikke et opslag mod denne maskine.

**§5b — Marketingsitet (`www.timelapse-pro.dk`) er IKKE en del af denne guide:** det hostes
bevidst på en helt anden maskine/tjeneste end staging/prod (fx Cloudflare Pages eller anden
statisk hosting), netop for at undgå enhver CrushFTP-portkonflikt. Se
`PORT_AUDIT_og_WEBSITE_v10.md` §5.3 — udgangspunktet er den allerede byggede `www/index.html`,
hvis login-knapper skal pege på `https://backend.timelapse-pro.dk:8443/` (med portnummer).

## 6. Certifikat (Let's Encrypt via certbot, DNS-01 — rører INGEN port)

CrushFTP ejer port 80 på denne maskine, så den almindelige HTTP-01-udfordring (webroot) er ikke
en mulighed. Vi bruger i stedet DNS-01 med Cloudflares plugin, som beviser domæneejerskab via et
TXT-opslag i DNS-zonen — helt uafhængigt af om nginx kører eller hvad den lytter på.

```bash
# Token fra forudsætningerne (§1), gemmes UDENFOR Git-repoet:
sudo mkdir -p /etc/timelapse/certbot
sudo tee /etc/timelapse/certbot/cloudflare.ini > /dev/null <<'EOF'
dns_cloudflare_api_token = <indsæt jeres Cloudflare API-token her>
EOF
sudo chmod 600 /etc/timelapse/certbot/cloudflare.ini

sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/timelapse/certbot/cloudflare.ini \
  -d backend.timelapse-pro.dk \
  --agree-tos --no-eff-email -m <din-email@domæne>
```

Certbot gemmer certifikatet under `/etc/letsencrypt/live/backend.timelapse-pro.dk/`. Scriptet
forventer det i stedet under `/opt/homebrew/etc/nginx/ssl/<domæne>/fullchain.pem` og
`.../privkey.pem` (samme mønster som den eksisterende R&D-config) — link eller kopiér det dertil:

```bash
sudo mkdir -p /opt/homebrew/etc/nginx/ssl/backend.timelapse-pro.dk
sudo ln -sf /etc/letsencrypt/live/backend.timelapse-pro.dk/fullchain.pem /opt/homebrew/etc/nginx/ssl/backend.timelapse-pro.dk/fullchain.pem
sudo ln -sf /etc/letsencrypt/live/backend.timelapse-pro.dk/privkey.pem  /opt/homebrew/etc/nginx/ssl/backend.timelapse-pro.dk/privkey.pem
```

**Auto-fornyelse:** certbot installerer typisk selv en periodisk fornyelses-timer/cron-job ved
installation via Homebrew — bekræft med `sudo certbot renew --dry-run` (den bruger automatisk
samme `--dns-cloudflare`-plugin igen, da det er gemt i certifikatets renewal-konfiguration). Tilføj
evt. et `--deploy-hook "nginx -s reload"`, så nginx automatisk genindlæser efter en fornyelse.

**Kør nu installationsscriptet IGEN** (samme kommando som i §4) — det opdager automatisk at
certifikatet nu findes, og skriver det fulde SSL-block på `:8443` (ingen redirect fra port 80,
da TimeLapse Pro ikke ejer den porten på denne maskine).

Verificér: `curl -I https://backend.timelapse-pro.dk:8443/` bør give `200`, ikke en TLS-fejl.

## 7. FØRSTE LOGIN og RBAC-opsætning — kan IKKE og bør IKKE scriptes

**Vigtigt, verificeret direkte i koden (`headend/main.py`):** en frisk installation opretter
automatisk en standard `super_admin`-bruger (`admin` / `changeme`), MEN systemets
sikkerhedspolitik kræver MFA (TOTP) for `super_admin`-rollen ved allerførste login
(`mfa_required_by_role["super_admin"] = True`, kodedefault, ikke kun en R&D-indstilling). Det
betyder login-flowet stopper ved en MFA-enrollment-skærm (QR-kode), FØR en fuld session gives.
Dette kan ikke gøres via `curl`/script på en meningsfuld, sikker måde — det SKAL gøres i en
rigtig browser af et menneske:

1. Åbn `https://<dit-domæne>:8443/` i en browser (husk portnummeret — se §0).
2. Log ind med `admin` / `changeme`.
3. Scan QR-koden med en autenticator-app (samme slags I allerede bruger til R&D-login) og
   bekræft med en 6-cifret kode.
4. Gå STRAKS til Indstillinger → Skift adgangskode, og sæt en stærk, unik adgangskode. Brug
   ALDRIG samme adgangskode som på R&D eller andre miljøer.
5. Overvej at ændre brugernavnet fra `admin` til noget mindre forudsigeligt (via Brugere-siden,
   kræver en anden konto eller direkte databaseændring — ikke kritisk, men en pæn ekstra
   hærdning).

## 8. Yderligere brugere og roller

Når du er logget ind som den nye, sikre `super_admin`, opret resten af brugerne (dig selv med et
personligt login, evt. kolleger, kunde-visninger) via **Brugere**-siden i UI'en — ikke via dette
script. Roller: `super_admin`, `admin`, `operator`, `viewer` (se `RISK_ASSESSMENT_v10.md` §14 for
den fulde RBAC-model).

## 9. Hvad denne guide bevidst IKKE dækker endnu

- **CA/mTLS til edge-enheder** — koden findes ikke endnu (se opgave #52,
  `Claude_Intern_CA_mTLS_Design_2026-07-05.md`). Tilføjes som et separat kapitel her, når den
  kode er skrevet og godkendt.
- **Automatiseret RBAC-seeding ud over første admin** — bevidst manuelt, se §8.
- **Backup-opsætning på den nye maskine** — se `BACKUP_RESTORE_TEST_PROCEDURE_v1.md` for
  proceduren; den skal sættes op separat pr. maskine (peger i dag på et NAS-mønster fra R&D, som
  formentlig skal tilpasses for `staging`/`prod`).
- **AI/Gemini-nøgler** — kun nødvendigt hvis I vil køre AI-analyse på denne maskine. Se de
  udkommenterede linjer i den genererede `/etc/timelapse/headend.env` og
  `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` for GDPR-implikationer FØR I aktiverer det på en
  maskine med rigtige kunders billeder.
- **Multi-prod-server-orkestrering** (hvis I får flere prod-servere) — scriptet understøtter det
  ved at køres flere gange med forskellige config-filer, men der er ingen central
  styring/dashboard på tværs af flere prod-instanser i denne version.
- **Node-agent (CMDB-inventory)** — dækkes nu af §11 nedenfor (Fase 3) og
  `HEADEND_GENERATOR_v1.md`. Enroll-scriptet (`enroll_headend_cmdb.sh`) og den
  parametriserede node-agent-installer er implementeret og kontrakttestet; fysisk
  end-to-end accept på en ny Mac mangler fortsat.

## 10. Fejlsøgning

| Symptom | Sandsynlig årsag |
|---|---|
| `nginx -t` fejler med "cannot load certificate" | Certifikat-symlinks i §6 mangler eller peger forkert — tjek `ls -la /opt/homebrew/etc/nginx/ssl/<domæne>/` |
| Health-check timer ud i scriptets §9 | Tjek `~/Library/Logs/timelapse-headend.log` — ofte forkert `DATABASE_URL` eller manglende Python-pakke |
| Certbot fejler med "Challenge failed" (DNS-01) | Cloudflare API-tokenet mangler `Zone:DNS:Edit`-rettighed for jeres zone, eller zonen ikke administreres via Cloudflare — tjek `/etc/timelapse/certbot/cloudflare.ini` og token-scopet |
| `install_headend.sh` afviser med "TL_BACKEND_PORT er forbudt" | Config-filen sætter `TL_BACKEND_PORT` til 21/22/80/443 — disse ejes af CrushFTP på staging/prod, brug 8443 (default) eller en anden ledig ikke-standard port |
| Browser kan ikke nå `https://backend.timelapse-pro.dk/` (uden port) | Forventet — backend kører på en ikke-standard port, brug `:8443` i URL'en (se §0/§7) |
| Login-side viser aldrig MFA-QR-koden | Browser-cache/cookie-problem — prøv incognito-vindue |
| `createuser`/`createdb` fejler med "already exists" | Harmløst — scriptet er idempotent, brug de eksisterende |

---

## 11. Headend-generator: kontrolleret provisioning + CMDB-enrollment (tilføjet 2026-07-16)

Siden v1 blev skrevet, er der kommet en **generator-forfase** (`deploy/install/bootstrap_headend_macos.sh`), der gør §3–§4 mere kontrollerede, plus et **Fase 3-enrollment-trin**, der bringer maskinen i CMDB + under konfigurationskontrol. Fuldt design: `HEADEND_GENERATOR_v1.md`. Kort:

**Fase 0 — Preflight (læs-only, kør FØR §4).** Beviser at værten er klar og at vi ikke rører CrushFTP:

```bash
deploy/install/bootstrap_headend_macos.sh --mode preflight --config ~/timelapse-staging.conf
# skriver evidens-JSON; fejler hvis 8443 er optaget; bekræfter 21/22/80/443 urørt
```

**Fase 1 — Stage (hent SIGNERET GitHub-release i stedet for `git clone` i §1).** Henter et GPG-signeret tag, verificerer signatur + commit-SHA, og kører installer-dry-run:

```bash
deploy/install/bootstrap_headend_macos.sh --mode stage --config ~/timelapse-staging.conf \
  --repo-url <github-url> --release-tag v<X.Y.Z> \
  --expected-commit <40-char-sha> --destination ~/tl-release
```

Dette erstatter et løst `git clone` med en verificeret, immutabel release — brug den udcheckede `~/tl-release` som repo-sti i §3-§4.

**Fase 2 — Apply.** Som §4–§6 (install → DNS-01-cert → install igen).

**Fase 3 — Enroll i CMDB + config-control.** Efter §7 (første login). Installerer node-agent så maskinen løbende rapporterer inventory/security → CMDB og bliver synlig på linje med edge-flåden:

```bash
sudo deploy/install/enroll_headend_cmdb.sh --device-id TL-HEADEND-STAGING-1 \
  --headend-url https://staging.timelapse-pro.dk:8443 \
  --bootstrap-token-file /secure/bootstrap-token --repo-dir ~/tl-staging-release
# verificér:
curl -sk https://127.0.0.1:8443/api/cmdb/ | grep TL-HEADEND-STAGING-1
```

**Sikkerhedsmodel:** bootstrap-tokenet leveres via en rettighedsbeskyttet fil og
kommer ikke i proceslisten. Agent-tokenet skrives atomisk til
`/etc/timelapse/node-agent.conf` med mode `0640`. Inventory kræver Bearer-token,
HMAC-signatur og replaybeskyttelse. Brug et backend-domæne med gyldigt certifikat;
scriptet bruger ikke `curl -k` eller anden TLS-omgåelse.

**Løbende konfigurationskontrol:** efter Fase 3 må software på en prod-headend KUN ændres via den signerede update-flow — aldrig `git pull`/manuel kopi. Node-agent + CMDB gør afvigelser synlige.

---

Se også: `HEADEND_GENERATOR_v1.md` (fuldt generator-design),
`MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` (topologi/politik),
`GO_LIVE_CHECKLIST_v10.md` §A/§M (krav før kundevendt drift),
`Claude_Intern_CA_mTLS_Design_2026-07-05.md` (fremtidig CA/mTLS),
`deploy/install/install_headend.sh` (selve scriptet).
