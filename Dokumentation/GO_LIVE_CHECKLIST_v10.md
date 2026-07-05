# TimeLapse Pro — Go-live checkliste (v10, konsolideret): krav før Internet-eksponering og timelapse-pro.dk

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Gælder for:** Skift fra `timelapse.froekjaer.dk` (lab) til `timelapse-pro.dk` (produktion) og egentlig Internet-eksponering af Headend
**Konsoliderer:** `GO_LIVE_CHECKLIST_2026-06-23.md`, `Claude_GO_LIVE_CHECKLIST_2026-06-23.md`, `Codex_GO_LIVE_CHECKLIST_2026-06-23.md` (arkiveret i `Gamle versioner/`).

> **Definitioner (farve = hastværk, P0/P1 = Codex-gate):**
> - **Blocker (🔴 / P0):** Systemet MÅ IKKE gå i Internet-facing produktion uden dette er opfyldt
> - **Stærkt anbefalet (🟠 / P1):** Bør løses inden første rigtige kunde-site aktiveres
> - **Anbefalet (🟡):** Løses snarest muligt efter go-live

**Samlet beslutning pr. 2026-06-23 (Claude + Codex enige): No-go for Internet-facing production.** Systemet kan fortsætte i lab/pre-production.

---

## A. Netværk og porteksponering

| # | Krav | Status | Ansvar |
|---|---|---|---|
| A-01 | nginx lytter IKKE direkte på public TCP/80 og TCP/443 | 🔴 Blocker | Konfiguration |
| A-02 | Cloudflare Tunnel konfigureret: `timelapse-pro.dk` → `127.0.0.1:18443` | 🔴 Blocker | DNS/CF |
| A-03 | `backend.timelapse-pro.dk` Cloudflare Tunnel til Headend API | 🔴 Blocker | DNS/CF |
| A-04 | nginx lytter på `127.0.0.1:18443` (ikke `*:18443`) | 🔴 Blocker | Konfiguration |
| A-05 | TCP/21 (FTP) ikke åben på Headend | 🔴 Blocker | Audit |
| A-06 | TCP/22 (SSH) ikke direkte Internet-eksponeret — enten lukket eller bag Cloudflare Access | 🟠 Anbefalet | Firewall |
| A-07 | TCP/8080 ikke eksponeret direkte | 🔴 Blocker | Audit |
| A-08 | SFTP-port ændret fra 22222 til 12222 eller bag Cloudflare Tunnel | 🟠 Anbefalet | Konfiguration |
| A-09 | Alle ukendte porte (2201, 5000, 7000) klassificeret | 🔴 Blocker | Asset-register |
| A-10 | fail2ban aktivt og konfigureret (API login + scanner) | 🟠 Anbefalet | Drift |
| A-11 | Mac firewall (pf/macOS) blokerer alt indgående undtagen Cloudflare IP-ranges + SFTP | 🟠 Anbefalet | Konfiguration |
| A-12 | OpenWebUI er lab-only eller RBAC-beskyttet intern service (ikke public) | 🟠 P1 | Konfiguration |

**Verificering A-01 til A-12:**
```bash
# Lokalt på Headend
sudo lsof -i -n -P | grep LISTEN | grep -v '127.0.0.1\|::1'
# Bør kun vise Cloudflare Tunnel daemon, evt. SFTP-port
curl -sk https://timelapse-pro.dk/api/health | jq .
```

---

## B. TLS og certifikater

| # | Krav | Status |
|---|---|---|
| B-01 | TLS 1.2 minimum, TLS 1.3 foretrukket | ✅ nginx-config OK |
| B-02 | Gyldigt TLS-certifikat (Cloudflare managed eller Let's Encrypt) | Bekræft ved go-live |
| B-03 | HSTS aktiveret (max-age≥31536000, includeSubDomains) | ✅ nginx-config OK |
| B-04 | Security headers: X-Content-Type-Options, X-Frame-Options, CSP | ✅ nginx-config OK |
| B-05 | Certifikat-ekspirerings-monitoring | 🟠 Mangler |
| B-06 | Origin-certifikat valideret af Cloudflare (ikke self-signed i prod) | Bekræft ved go-live |

---

## C. Autentificering og adgangskontrol

| # | Krav | Status |
|---|---|---|
| C-01 | JWT_SECRET er stabilt og kryptografisk stærkt (≥256 bit) | ✅ LaunchAgent |
| C-02 | JWT_SECRET ikke i Git | ✅ |
| C-03 | Standard super_admin-password er ændret fra default | 🔴 Bekræft manuelt |
| C-04 | RBAC aktivt på alle `/api/admin/*` endpoints | ✅ require_role() — **NB 2026-07-03:** `/api/siem/*` (uden for `/api/admin/*`) havde slet ingen auth; rettet i kode, committet+pushet (`b0e224c`), pip-install i live-venv og headend genstartet af Peter, **live-verificeret**: health `200`, `GET /api/siem/events` uden auth → `401` |
| C-05 | Alle CMDB-endpoints kræver viewer-rolle (ingen anonym adgang) | ✅ Rettet 2026-06-21 |
| C-06 | Rate limiting på `/api/auth/login` (10r/m) | ✅ nginx |
| C-07 | MFA/WebAuthn til super_admin og admin operationer | ✅ Løst 2026-07-02 — policy-drevet MFA (TOTP) enforced for admin/super_admin (WebAuthn separat/off) |
| C-08 | Session-timeout implementeret | ✅ JWT 12t |
| C-09 | BREAK_GLASS_ENC_KEY er unik og stærk | ✅ LaunchAgent |
| C-10 | HMAC enforcement aktivt for alle aktive device-tokens | 🟠 Stale credentials skal ryddes |

> **Note C-07 (opdateret 2026-07-02):** MFA er nu implementeret og policy-drevet (Codex) — TOTP enforced som default for `super_admin` + `admin` via `mfa_required_by_role`; global override + `mfa_exempt_usernames` (Claude/Codex-testkonti fritaget under udvikling). Requests uden MFA-verificeret session → `403`. WebAuthn er et separat flag (default off). Se `RBAC_Remote_Operational_v10.md` §3.
>
> **KORREKTION 2026-07-03 (Claude):** MFA-tjekket var reelt kun håndhævet i `main.py`'s egen RBAC-funktion — CMDB- og ITIM-routerens separate, lokale RBAC-broer manglede MFA-kaldet helt, så disse to routere (inkl. break-glass password-checkout) omgik MFA-kravet i praksis. Rettet i kode, **committet+pushet (`b0e224c`) og live-verificeret** (Peter, 2026-07-03: pip-install i live-venv, headend genstartet, health `200`). Lokal testklient bekræftede forinden: viewer 200 / admin-uden-MFA 403 / admin-med-MFA 200 på både CMDB og ITIM. Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.2/§2.3.

---

## D. Secrets og nøglehåndtering

| # | Krav | Status |
|---|---|---|
| D-01 | Ingen secrets i Git-historikken | ✅ git log --all verifikation OK |
| D-02 | `secrets/gcp-service-account.json` ikke tilgængelig via webserver | ✅ Outside webroot |
| D-03 | GCP service account-nøgle roteret inden for 90 dage | 🟠 Check dato |
| D-04 | GPG-nøgle F75C248F694C097F er i peter's keyring (ikke root) | ✅ Bekræftet 2026-06-22 |
| D-05 | GPG-nøgle har stærk passphrase | 🟠 Bekræft |
| D-06 | Stale edge-credentials (TL-DCA63234D813) revokeret eller migreret | 🟠 Mangler |
| D-07 | Backup af GPG-nøgle offline (krypteret) | 🟠 Mangler |

---

## E. Backup og driftsresiliens

| # | Krav | Status |
|---|---|---|
| E-01 | Automatisk backup til /Volumes/Backup konfigureret og kørende | 🟠 Kode klar (2026-07-04 nat), IKKE bekræftet kørt i produktion — se R09 i RISK_ASSESSMENT_v10.md. Kritisk fund: billeder blev ALDRIG backet op før i nat (indstilling fandtes i UI men blev ikke læst); nu wired ind + auto-interval-loop tilføjet. Peter/Codex bør trigge en manuel backup og bekræfte billed-mirror + log-output ser rigtigt ud, før dette regnes for grønt. |
| E-02 | Restore-test udført og dokumenteret (dato, scope, RTO) | 🔴 Blocker — IKKE realistisk at nå til "go-live i morgen"; kræver reel gendannelse til et testmiljø |
| E-03 | Off-site backup konfigureret (anden disk/location) | 🟠 Anbefalet — billed-mirror ligger stadig kun lokalt/NAS, ingen ekstern kopi endnu |
| E-04 | Backup-change ticket genereres ved backup | 🟡 Ønsket |
| E-05 | Headend startup-preflight: verificer /Volumes/data-fast mount + skriveadgang | 🟠 Mangler |
| E-06 | Node-agent kørende og rapporterer frisk CMDB-inventory | 🟠 Mangler (stoppet 2026-06-22) |
| E-07 | RTO og RPO dokumenteret | 🟠 Mangler |

---

## F. CMDB og monitoring

| # | Krav | Status |
|---|---|---|
| F-01 | Alle device-statusser er freshness-baserede i ALLE UI-flader | 🟠 Delvist |
| F-02 | Stale device vises som offline (ikke online) | 🟠 Delvist |
| F-03 | Node-agent kørende og opdaterer Mac Mini inventory | 🟠 Mangler |
| F-04 | Headend-health monitoreret automatisk (fx cron/launchd watchdog) | 🟡 Ønsket |
| F-05 | Alert ved Headend-nedbrud (email/notification) | 🟡 Ønsket |
| F-06 | Dashboard/alarm for enheder i debug/lab mode (`debug_mode.enabled`) | 🟢 Deployet 2026-07-05 (badge i SystemAdminPage/LabPage, auto-timeout, SIEM-audit-log, commit `44b78fb7`) — kun manuel smoketest på live device udestår, se `RISK_ASSESSMENT_v10.md` R17 |

---

## G. GDPR og compliance

| # | Krav | Status |
|---|---|---|
| G-01 | DPIA udfyldt for hvert aktiv kunde-site | 🟠 Skabelon klar (2026-07-04) — mangler udfyldelse pr. site + juridisk godkendelse |
| G-02 | Retention policy konfigureret pr. kamera | 🔴 Design klar (2026-07-04) — IKKE implementeret i kode endnu |
| G-03 | Databehandleraftale med kunden | 🔴 Blocker for første kunde — kræver jurist, ikke startet |
| G-04 | Subprocessor-liste (Google Cloud/Gemini) offentliggjort | 🟠 Udkast klar (2026-07-04). 2026-07-05 (Claude): kode håndhæver nu at GCS-bucket-region matcher Vertex-region i BEGGE indgange (UI-API + CLI-bulk-script, se `RISK_ASSESSMENT_v10.md` R12) — men den faktiske PRODUKTIONS-værdi af `GOOGLE_CLOUD_LOCATION`/`gemini_gcs_bucket_region` er stadig ikke bekræftet at være EU (kræver live-adgang, ikke gjort af Claude) |
| G-05 | Download/adgangslog pr. billede implementeret | 🟠 Anbefalet |
| G-06 | Procedure for databrud (Art. 33/34, 72t) dokumenteret | 🟠 Anbefalet |
| G-07 | Oplysningspligt til registrerede (Art. 13/14) | 🟠 Skitse-tekst klar (2026-07-04) — kræver juridisk godkendelse |

> **Note G (2026-07-04, Claude):** GPS/lokationsmetadata er nu implementeret og verificeret i produktion (kilde/tillid vises i UI). DPIA-template (G-01) og retention policy (G-02) skal eksplicit dække dette felt, ikke kun selve billedet — se `RISK_ASSESSMENT_v10.md` R12.
>
> **Note G (2026-07-04 nat, Claude):** Se `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` — DPIA-skabelon, retention-policy-design, subprocessor-liste og oplysningspligt-udkast er nu skrevet. Dette er tekniske/organisatoriske UDKAST, ikke juridisk godkendte dokumenter, og retention er kun et design — ingen kode er skrevet endnu. G-03 og G-06 er bevidst IKKE dækket (kræver jurist). Fandt undervejs et separat, urelateret produktionsbug (R18 i RISK_ASSESSMENT_v10.md) — rettet.

---

## H. Code quality og CI

| # | Krav | Status |
|---|---|---|
| H-01 | GitHub Actions CI er grøn på alle builds | ✅ Efter commit 79581ac |
| H-02 | ESLint-gate i CI — ingen nye fejl | 🟢 Kode klar og pushet (2026-07-05, Claude → Codex commit `68805577`): ratchet-gate (`timelapse-ui/scripts/eslint-gate.mjs` + `.eslint-baseline.json`, baseline 222) tilføjet som CI-step i `ui-check` — fejler kun hvis antal ESLint-problemer STIGER over baseline, kræver ikke at de 222 eksisterende rettes først. Baseline sænkes manuelt i takt med oprydning. Resterer: bekræfte grønt "ESLint gate"-step i en faktisk GitHub Actions-kørsel. |
| H-03 | `slowapi` tilføjet til requirements.txt | ✅ Rettet 2026-07-03 (Claude) — hele `requirements.txt` er samtidig pinnet til konkrete versioner (var 100% upinnet); se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §3.1. Committet (`b0e224c`) og installeret i live-venv af Peter |
| H-04 | deploy/launchd/dk.froekjaer.timelapse-headend.plist opdateret (ikke-secret version) | 🟢 Løst 2026-07-03 (Codex, `d7a952db`) — fundet 2026-07-05 (Claude, periodisk tjek) at dette allerede var udført men ikke markeret: den kanoniske, live plist er nu `deploy/launchd/macos/dk.froekjaer.timelapse-headend.plist` (system-LaunchDaemon), som ikke rummer `DATABASE_URL`/`TIMELAPSE_GPG_KEY` inline — den peger via `TIMELAPSE_HEADEND_ENV_FILE` på `/etc/timelapse/headend.env` (uden for Git, læst af `deploy/macos/timelapse-headend-start.sh`). Den ældre rod-plist `deploy/launchd/dk.froekjaer.timelapse-headend.plist` (med inline secrets) er en efterladt, ikke-brugt bruger-LaunchAgent-artefakt fra før 2026-07-03-migrationen til system-LaunchDaemons — se `SERVICES_OG_DRIFT_kilde_til_sandhed.md`. Adskilt fra VPEN-2026-003 (P2, RISK_ASSESSMENT §5.2), som gælder plaintext-secrets i selve `/etc/timelapse/headend.env` på disk (Keychain-migration), ikke det Git-tjekkede plist-indhold. |
| H-05 | Python test-suite med edge/headend contract-tests | 🟢 `headend/tests/test_report_update_rollup.py` (4 tests) + `test_update_lifecycle.py` (9 tests) skrevet 2026-07-05 (Claude). Committet/pushet af Codex som `1e3c3321` og bekræftet i eget venv (`/tmp/tlp-hvenv`): 13/13 bestået. Resterer: bekræfte grøn kørsel i faktisk GitHub Actions CI (ikke kun lokalt/venv). |
| H-06 | README opdateret (ikke Vite-template) | ✅ Rettet 2026-07-05 (Claude, periodisk tjek) — repo-rod `README.md` var uændret `create-vite`-boilerplate (ingen omtale af headend/edge/UI/tests); erstattet med reelt projekt-README (formål, mappestruktur, lokal opsætning for headend/UI/edge, test-kommandoer, pointer til `Dokumentation/00_START_HER.md`). Committet/pushet af Codex som `9dda9923`. |

---

## K. Device identity og updates (Codex-gate)

| Krav | Status | Gate |
|---|---|---|
| Aktiv Edge HMAC-signering | Delvist | P0 |
| Stale/legacy credentials migreret eller revokeret | Åben | P0 |
| Edge må ikke bruge direkte GitHub/Internet/apt i prod | Princip implementeret | P0 |
| App-artifact update E2E på aktiv Edge | Løst i lab | P0 |
| OS offline-artifact update E2E på aktiv Edge (`apt-get --no-download`, manifest/signatur/hash) | Åben | P1 |
| Change ticket med artifact/SBOM/rollback | Delvist | P1 |
| Per-target update status | 🟡 Flush-regression (fundet 2026-07-05, Claude, periodisk tjek — den 2026-07-05-deployede rettelse `61802951` manglede `db.flush()` før rollup-forespørgslen, så SIDSTE device i en multi-target rollout aldrig blev synligt for egen forespørgsel og global status sad fast på "approved") er nu RETTET, committet af Codex (`1e3c3321`, samme commit som H-05-testene) og deployet — headend genstartet, `/api/health` 200 OK, 13/13 tests bestået i Codex' venv 2026-07-05 nat. Resterer kun: live multi-device-rollout-test (2+ enheder, `scope=site`) for at bekræfte reel flip til "Deployet"/"Rullet tilbage" i produktion — ikke kørt fra periodisk heartbeat, da det ændrer state for rigtige enheder. Data+UI (`update_targets`, `/api/updates/{id}/flow-status`, `UpdatesPage.tsx`) har eksisteret siden juni 2026. | P1 |

---

## L. Domæner (website-arkitektur)

| Domæne | Formål | Krav |
|---|---|---|
| `www.timelapse-pro.dk` | Public informationssite | Statisk hosting, ikke Headend-origin |
| `timelapse-pro.dk` | Redirect eller public site | Ikke direkte Headend |
| `backend.timelapse-pro.dk` | Kunde/admin UI og API | Cloudflare Tunnel/WAF/rate limiting |

Login-knapper på public website skal redirecte til `https://backend.timelapse-pro.dk/login`.

---

## I. Verificeringskommandoer (endelig go-live-check)

```bash
# 1. Portaudit — ingen public 80/443/21/22/8080 fra TimeLapse
sudo lsof -i -n -P | grep LISTEN
lsof -nP -iTCP -sTCP:LISTEN

# 2. Health
curl https://backend.timelapse-pro.dk/api/health          # Forventet: 200

# 3. Auth-gate
curl -i https://backend.timelapse-pro.dk/api/cmdb/         # Forventet: 401
curl -i https://backend.timelapse-pro.dk/api/admin/stats   # Forventet: 401

# 4. Rate limit
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://backend.timelapse-pro.dk/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"x","password":"y"}'
done
# Forventet: 429 efter 10 forsøg/min

# 5. TLS
echo | openssl s_client -connect timelapse-pro.dk:443 2>/dev/null \
  | openssl x509 -noout -dates -subject

# 6. Backup
ls -la /Volumes/Backup/timelapse/

# 7. Edge upload
grep "HTTP 200" ~/Library/Logs/timelapse-headend.log | tail -5
```

Forventet ved go-live: ingen TimeLapse-origin på public `*:80/443/21/22/8080`; health 200; CMDB/admin 401 uden login; seneste backup kan restores; aktiv Edge kan heartbeat, capture, upload og update-policy-poll.

---

## J. Go/No-go vurdering

| Kategori | Blokerende | Status |
|---|---|---|
| A. Netværk/porte | 8 blokkere | 🔴 Ikke klar |
| B. TLS | 0 blokkere | ✅ Klar |
| C. Auth | 0 blokkere (MFA løst 2026-07-02) | ✅ Klar |
| D. Secrets | 0 blokkere | ✅ Klar |
| E. Backup | 2 blokkere | 🔴 Ikke klar |
| F. CMDB | 0 blokkere | ✅ Klar |
| G. GDPR | 3 blokkere (per-kunde) | 🔴 Ikke klar |
| H. Code quality | 0 blokkere | ✅ Klar |

**Konklusion:** Systemet er IKKE klar til Internet-eksponering og domæneskift til timelapse-pro.dk. Estimeret tid til go-live gate: **4–6 uger** med fokusindsats.

**De tre vigtigste opgaver:**
1. Cloudflare Tunnel konfigureret + nginx port-migration
2. Backup + restore dokumenteret
3. DPIA-template + retention policy (før første rigtige kunde-site)

**TILFØJELSE 2026-07-04 (nat, Claude) — svar på "go-live i morgen":** God fremgang i nat (R18-krasch rettet, billed-backup-hul lukket i kode, auto-backup-loop tilføjet, DPIA/retention-udkast, migrationsrunbooks for nginx/Cloudflare og node-agent klar til eksekvering), men konklusionen ovenfor står ved magt — **fuld Internet-eksponering på timelapse-pro.dk kan ikke forsvarligt nås i morgen.** Det skyldes ikke manglende indsats, men at flere blokkere kræver ting kode alene ikke kan levere på under et døgn: en reel restore-test (kræver faktisk gendannelse til et testmiljø og observation af tidsforbrug), databehandleraftale (kræver jurist), DNS-propagering ved Cloudflare Tunnel-cutover, og en per-kunde DPIA-godkendelse (skabelonen er klar, men skal udfyldes og godkendes pr. kunde). At forcere disse ville bryde med "dobbelttjekker før du udfører".

**Realistisk "i morgen"-tjekpunkt i stedet:** (a) bekræft at automatisk backup + billed-mirror rent faktisk kører korrekt på Mac Mini'en (kør en manuel backup, tjek `timelapse-images-mirror/`-mappen og loggen), (b) gennemgå og evt. eksekvér node-agent- og nginx/Cloudflare-runbooks i et kontrolleret vindue (ikke under produktionstrafik), (c) Peter beslutter og bekræfter status på `TL-DCA63234D813` (stale credential-runbook afventer hans svar), (d) hvis "go-live" i stedet betyder en lukket lab/pilot-fase for få kendte enheder (ikke offentlig internet-eksponering), er det væsentligt tættere på klar end den fulde liste ovenfor antyder — kategori B/C/D/F/H er alle ✅.
