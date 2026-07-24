# TimeLapse Pro — Installationsmanual: Ny Headend (staging/prod) oven på kørende Mac

**Version:** v1.1 · 2026-07-24 · **Forfattere:** Claude/Codex · **Status:** Headend-generator, release trust, least-privilege installation og dry-run er QA-testet. SFTP-listener/per-site RBAC i fase 2b er fortsat en eksplicit go-live-blokering.
**Målgruppe:** Peter alene — ingen agent (Claude/Codex) må have adgang til staging/prod (`MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §5).
**Princip:** Headenden installeres **oven på et kørende macOS-miljø** og skal **sameksistere med CrushFTP**, som ejer 21/22/80/443. TimeLapse rører ALDRIG disse porte. Alt TimeLapse kører på 8443 (UI/API), 22222 (SFTP-ingress), 8000/8080 (loopback), 5514 (valgfri syslog).
**Relaterede dokumenter:** `HEADEND_GENERATOR_v1.md` (design), `INSTALLATION_GUIDE_HEADEND_v1.md` (detaljer pr. trin), `deploy/PORTS.md` (portpolitik), `STAGING_TIL_PROD_PROMOTION_v1.md` (promotion).

---

## 0. Oversigt — de fire faser + manuelle go-live-gates

```
 Fase 0  PREFLIGHT   læs-only: er værten klar? er 8443 fri? (evidens-JSON)
 Fase 1  STAGE       vælg SIGNERET release/SHA i UI, hent, GPG-verify, dry-run
 Fase 2  APPLY       installér (venv, DB, UI, nginx:8443, launchd) + DNS-01-cert
 Fase 2b SFTP        ⚠️ MANUELT trin i dag: dedikeret sshd på 22222 + sftp-settings
 Fase 3  ENROLL      node-agent → self-register i CMDB, fail-closed
 Efterspil           første login (MFA), verifikation, backup
```

Forventet tid: 1-2 timer ekskl. DNS-propagering. Alt er idempotent — hvert script kan køres igen.

---

## 1. Forudsætninger på den kørende Mac

Installér via Homebrew (rører ikke CrushFTP):

```bash
brew install python@3.12 postgresql@17 nginx node certbot git gnupg
pip3 install certbot-dns-cloudflare
brew services start postgresql@17
```

Derudover:

- **GPG:** importér den offentlige release-signeringsnøgle, ellers fejler Fase 1's `git verify-tag`:
  `gpg --import <release-nøgle.asc>` (nøgle-ID: se `CHANGE_TICKET_GPG_KEY`/release-dokumentationen).
- **Cloudflare API-token** med `Zone:DNS:Edit` for zonen (til DNS-01) — gemmes i `/etc/timelapse/certbot/cloudflare.ini`, chmod 600.
- **Konfigurationsfil:** kopiér `deploy/install/example-staging.conf` (eller `-prod`) og tilpas. Sæt `TL_REPO_DIR` til den **staged release-mappe** fra Fase 1 (fx `/Users/Shared/TimeLapsePro/releases/staging`) — IKKE en almindelig arbejdskopi. Ellers installeres der udenom GPG-verifikationen.
- **Servicekonto:** installeren opretter som standard den skjulte, ikke-administrative
  konto `_timelapse`. Den forventer ikke, at brugeren `peter` findes på målmaskinen.
- **Standardstier:** brug `/Users/Shared/TimeLapsePro/releases/<miljø>` og
  `/Users/Shared/TimeLapsePro/data/canonical-images`, medmindre storage-registeret
  foreskriver andet.
- **Beslut device-ID:** `TL-HEADEND-STAGING-1` / `TL-HEADEND-PROD-1` (afventer formel bekræftelse, HEADEND_GENERATOR §8.5).
- **Docker Desktop:** KUN hvis denne headend selv skal bygge edge-images (uafklaret for prod — GEN-11). Staging/prod behøver det ikke for normal drift.

**CrushFTP-tjek før du starter:** notér hvilke porte CrushFTP faktisk lytter på (`sudo lsof -nP -iTCP -sTCP:LISTEN`). Preflight-rapporten gemmer det som evidens. Hvis CrushFTP mod forventning også bruger 8443 (det er en almindelig alternativ-HTTPS-port!), fejler preflight med exit 3 — vælg da en anden `TL_BACKEND_PORT` i conf-filen (aldrig 21/22/80/443).

---

## 2. Fase 0 — Preflight (læs-only)

```bash
deploy/install/bootstrap_headend_macos.sh --mode preflight --config ~/timelapse-staging.conf
```

- Skriver evidens-JSON (`dk.froekjaer.timelapse.headend-preflight.v1`) til `$TMPDIR/timelapse-headend-preflight.json` (eller `--report <sti>`).
- Fejler hvis 8443 er optaget. Ændrer INTET på maskinen.
- **Gem rapporten** — den er go-live-evidens (GO_LIVE_CHECKLIST) og dokumenterer CrushFTP-sameksistensen på installationstidspunktet.

## 3. Fase 1 — Stage (signeret release)

I R&D-Headend: **Drift & Resilience → Headend generator**. Vælg et tag i
**Release-tag**. UI'et viser kun lokalt GPG-verificerede annotated tags og binder
automatisk den eneste gyldige fulde commit-SHA til valget. Manuelle/frie tag- og
SHA-værdier accepteres ikke.

```bash
deploy/install/bootstrap_headend_macos.sh --mode stage --config ~/timelapse-staging.conf \
  --repo-url git@github.com:froekjaer/timelapse-pro.git \
  --release-tag v<X.Y.Z> --expected-commit <fuld-40-tegns-SHA> \
  --destination ~/tl-staging-release
```

- Henter KUN det signerede tag (depth=1), kører `git verify-tag` (GPG), matcher commit-SHA, tjekker clean tree, og kører `install_headend.sh --dry-run`.
- Tag + SHA tages fra release-dokumentationen/change ticket — aldrig fra hukommelsen.
- Fejler ét af trinnene: STOP. Installér aldrig fra en uverificeret kilde.

## 4. Fase 2 — Apply (installation)

```bash
sudo ~/tl-staging-release/deploy/install/install_headend.sh --config ~/timelapse-staging.conf
```

Hvad scriptet gør (idempotent): opretter/verificerer `_timelapse`, bygger venv
under servicekontoens home, opretter PostgreSQL-rolle/DB, bygger UI, installerer
LaunchDaemon og en **isoleret** nginx-instans med egen config, pid, logs og
temp-kataloger. Global Homebrew-nginx, CrushFTP og andre apps genstartes eller
ændres ikke.

På en ny installation genererer `/etc/timelapse/headend.env` en frisk
`JWT_SECRET` og en unik `TIMELAPSE_INITIAL_ADMIN_PASSWORD`. En eksisterende
env-fil overskrives aldrig.

**Første kørsel uden certifikat** giver et plain-HTTP-bootstrap-block på 8443 med statusbesked. Det er forventet. Fortsæt til §5.

## 5. Certifikat (DNS-01 — rører ingen port, CrushFTP-sikkert)

```bash
sudo mkdir -p /etc/timelapse/certbot
# cloudflare.ini: dns_cloudflare_api_token = <token>   (chmod 600)
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/timelapse/certbot/cloudflare.ini \
  -d staging.timelapse-pro.dk \
  --agree-tos --no-eff-email -m <din-email>

# Link/kopiér til stien nginx-configen forventer:
sudo mkdir -p /opt/homebrew/etc/nginx/ssl/staging.timelapse-pro.dk
sudo ln -sfn /etc/letsencrypt/live/staging.timelapse-pro.dk/fullchain.pem /opt/homebrew/etc/nginx/ssl/staging.timelapse-pro.dk/fullchain.pem
sudo ln -sfn /etc/letsencrypt/live/staging.timelapse-pro.dk/privkey.pem  /opt/homebrew/etc/nginx/ssl/staging.timelapse-pro.dk/privkey.pem

# Kør Fase 2 IGEN — scriptet opdager certifikatet og aktiverer fuldt SSL-block:
sudo ~/tl-staging-release/deploy/install/install_headend.sh --config ~/timelapse-staging.conf
```

Husk certbot-renewal (launchd-plist findes i `Dokumentation/Konfig artefakter/certbot-renewal.plist` som skabelon) + genkørsel af nginx-reload efter renewal.

## 6. Første login — GØR DETTE FØR OFFENTLIG EKSPONERING

`admin/changeme` er forbudt i staging/prod. Installeren genererer i stedet en
unik initial adgangskode. **Rækkefølgen er sikkerhedskritisk:** gennemfør første
login og password-skift FØR offentlig DNS/firewall åbnes. Test lokalt via
`/etc/hosts` eller LAN:

1. Læs initial adgangskode lokalt:
   `sudo grep '^TIMELAPSE_INITIAL_ADMIN_PASSWORD=' /etc/timelapse/headend.env`
2. Åbn `https://<domæne>:8443/` og log ind som `admin`
3. Gennemfør TOTP-opsætning (super_admin kræver MFA ved første login)
4. Skift adgangskoden STRAKS
5. Fjern `TIMELAPSE_INITIAL_ADMIN_PASSWORD` fra env-filen og genstart Headend
6. Opret evt. øvrige brugere/roller via UI'en

## 7. Fase 2b — SFTP-ingress på 22222 (⚠️ MANUELT trin i dag — GEN-01/GEN-02)

Uden dette trin kan headenden ikke modtage SFTP-uploads fra edges.
Kode-, generator- og installer-defaulten er nu **22222**, aldrig 22, men en
default åbner ikke en listener eller opretter per-site RBAC. Gør følgende:

**a) Dedikeret sshd-socket på 22222** (launchd; rører IKKE system-SSH/CrushFTP på 22):
Opret `/Library/LaunchDaemons/ssh-2222.plist` med `Sockets → Listeners → SockServiceName = 22222` der starter `/usr/sbin/sshd -i` (samme mønster som R&D — filnavnet er historisk, porten er 22222). `sudo launchctl bootstrap system /Library/LaunchDaemons/ssh-2222.plist`.

**b) Hardening-profil:**

```bash
sudo bash ~/tl-staging-release/deploy/ssh/apply_timelapse_sftp_hardening.sh
```

Den indsætter `deploy/ssh/timelapse-sshd-sftp.conf`-blokken: `sftp_*`-brugere afvises hårdt på 22 og 2222 og er default-deny på 22222 indtil per-site-allowregler genereres.

**c) Per-site RBAC-regler** (efter kunder/sites er oprettet i DB):

```bash
python headend/tools/render_sftp_rbac_config.py --output /private/tmp/timelapse-sftp-rbac-sites.conf
# Indsæt den genererede blok FØR default-deny-blokken i sshd_config, test og genindlæs:
sudo /usr/sbin/sshd -t && sudo launchctl kickstart -k system/ssh-2222  # (label jf. plist)
```

**d) Verificér settings i headend-DB'en:** `sftp_host=<backend-domæne>`,
**`sftp_port=22222`**, `sftp_remote_base=<TL_DATA_DIR>`. Installeren sætter
miljø-defaulten, men config-preview på en rigtig Edge er acceptkriteriet.

**e) Opret ingen SFTP-brugere efter v10-guidens §12-opskrift** — den beskriver den udfasede chroot/port-22-model (GEN-05).

## 8. Fase 3 — Enrollment i CMDB + config-control

Forudsætning: bootstrap-token genereret på DENNE headend (UI: Klargør ny Edge/node — eller API) og gemt i en fil.

```bash
sudo deploy/install/enroll_headend_cmdb.sh \
  --device-id TL-HEADEND-STAGING-1 \
  --headend-url https://staging.timelapse-pro.dk:8443 \
  --bootstrap-token-file /secure/bootstrap-token \
  --repo-dir ~/tl-staging-release
```

- ⚠️ GEN-08: brug **domænet**, ikke `https://127.0.0.1:8443` — certifikatet dækker kun domænet.
- Scriptet enroller med `node_type=headend`, installerer node-agenten parametriseret og **fejler hvis der ikke kommer en autentificeret inventory-kvittering inden 60 sek.** (fail-closed — en fejl her er en rigtig fejl, ignorér den ikke).
- Slut-accept: kontrollér i UI'en at headenden står i CMDB med software-inventar + SBOM.

## 9. Verifikationstjekliste (gem output som evidens)

```bash
curl -sk https://<domæne>:8443/api/health                          # 200 + ok
curl -skI https://<domæne>:8443/                                   # UI, HSTS-header
sudo lsof -nP -iTCP -sTCP:LISTEN | grep -E "(:21|:22|:80|:443)\b"  # KUN CrushFTP/system — intet TimeLapse
sudo lsof -nP -iTCP -sTCP:LISTEN | grep -E ":8443|:22222|:8000"    # nginx, sshd-socket, uvicorn(loopback)
sftp -P 22222 sftp_<site>@<domæne>                                 # efter §7c: virker KUN på 22222
sftp -P 22 sftp_<site>@<domæne>                                    # SKAL afvises (hardening §7b)
curl -sk https://127.0.0.1:8443/api/cmdb/ | grep TL-HEADEND        # enrolled
```

Plus: launchd-services kørende (`sudo launchctl print system/dk.froekjaer.timelapse-headend | grep state`), backup konfigureret med **skrivbar** `BACKUP_BASE` (⚠️ R09: default er i skrivende stund forkert — sæt eksplicit, fx `/Volumes/Backup`), og en gennemført restore-test før go-live (GO_LIVE_CHECKLIST).

## 10. Efter installation — config-control

Al software på maskinen ændres herefter KUN via det signerede update-flow (change tickets, GPG-artifacts, rollback) — aldrig `git pull` eller manuel kopiering. Node-agenten rapporterer løbende inventory/security til CMDB. Afvigelser fra dette er i sig selv et fund.

---

## 11. QA-evidens 2026-07-24

- 68 fokuserede generator/installations/Edge/arkitektur-kontrakttests: bestået.
- 689 samlede non-integration-tests: bestået; 4 miljøafhængige smoke-tests
  krævede autentificering og blev markeret som skipped.
- TypeScript + Vite production build: bestået.
- `install_headend.sh --dry-run` på macOS: bestået efter rettelse af
  domænevalidering og servicekonto-home-opslag.
- Browser: betroet tag/SHA-dropdown, tunnel/servicefelter, reserveret
  port-afvisning og gyldig prepare: bestået.

*Resterende blokeringer: fase 2b skal automatiseres og testes på den nye iMac;
DNS-01, MFA, CA/mTLS-status og restore-test kræver miljøspecifik evidens.*
