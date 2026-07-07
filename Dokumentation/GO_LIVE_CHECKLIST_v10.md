# TimeLapse Pro — Go-live checkliste (v10, konsolideret): krav før Internet-eksponering og timelapse-pro.dk

**Version:** 10 (konsolideret)
**Dato:** 2026-07-07
**Gælder for:** Skift fra `timelapse.froekjaer.dk` (lab) til `timelapse-pro.dk` (produktion) og egentlig Internet-eksponering af Headend
**Konsoliderer:** `GO_LIVE_CHECKLIST_2026-06-23.md`, `Claude_GO_LIVE_CHECKLIST_2026-06-23.md`, `Codex_GO_LIVE_CHECKLIST_2026-06-23.md` (arkiveret i `Gamle versioner/`).

> **Definitioner (farve = hastværk, P0/P1 = Codex-gate):**
> - **Blocker (🔴 / P0):** Systemet MÅ IKKE gå i Internet-facing produktion uden dette er opfyldt
> - **Stærkt anbefalet (🟠 / P1):** Bør løses inden første rigtige kunde-site aktiveres
> - **Anbefalet (🟡):** Løses snarest muligt efter go-live

**Samlet beslutning pr. 2026-06-23 (Claude + Codex enige): No-go for Internet-facing production.** Systemet kan fortsætte i lab/pre-production.

---

## A. Netværk og porteksponering

**KORREKTION 2026-07-05 (Claude, 2. runde, efter Peters bekræftelse):** Den forrige korrektion i
dette afsnit (samme dato) antog "direkte nginx-eksponering på standard 443/80" som erstatning for
den oprindelige Cloudflare Tunnel-plan. **Det var også forkert** — Peter har efterfølgende
bekræftet at **CrushFTP allerede kører på både staging-iMac'en og prod-Mac Mini'en** og optager
21, 22, 80 og 443 på disse maskiner. TimeLapse Pro's nginx må derfor ALDRIG binde til de porte på
disse maskiner. Den endeligt aftalte arkitektur (se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4 for
fuld begrundelse) er:
- `backend.timelapse-pro.dk` eksponeres direkte på **port 8443** (ikke 443/80, ikke Cloudflare
  Tunnel) — bekræftet Cloudflare-proxy-kompatibel HTTPS-port, hvis Peter senere ønsker at lægge
  Cloudflares gratis WAF/DDoS-beskyttelse foran (valgfrit, kræver ikke Tunnel-produktet).
- Certifikat udstedes via **DNS-01** (`certbot-dns-cloudflare`), ikke HTTP-01 — rører derfor
  ingen port på maskinen under udstedelse/fornyelse.
- Marketingsitet (`www.timelapse-pro.dk`) hostes **et helt andet sted** end staging-/prod-
  maskinerne (fx Cloudflare Pages) — det er derfor slet ikke en del af denne portmodel og rammes
  ikke af CrushFTP-konflikten. `www/index.html`s login-knapper er opdateret til at pege på
  `https://backend.timelapse-pro.dk:8443/`.
A-01–A-04 er omskrevet herunder til at reflektere dette. **Dette gælder for BÅDE `staging` og
`prod`, da begge maskiner kører CrushFTP — `rd`-domænet (`timelapse.froekjaer.dk`, ingen
CrushFTP) er upåvirket, ikke kundevendt og ikke en go-live-blocker.**

| # | Krav | Status | Ansvar |
|---|---|---|---|
| A-01 | nginx eksponerer `backend.timelapse-pro.dk` (UI+API) direkte på **port 8443** — ikke 80/443 (CrushFTP), ikke Cloudflare Tunnel. Marketingsitet hostes separat, indgår ikke i denne nginx-instans. | 🔴 Blocker (ikke bygget endnu på staging/prod) | Konfiguration |
| A-02 | Gyldigt, offentligt tillid-certifikat (Let's Encrypt via certbot **DNS-01**, `certbot-dns-cloudflare`) for `backend.timelapse-pro.dk`, auto-fornyelse konfigureret | 🔴 Blocker | Konfiguration |
| A-03 | `backend.timelapse-pro.dk:8443` proxy'er korrekt til `127.0.0.1:8000` (Headend) med samme rate-limiting/sikkerhedsheaders som nuværende `rd`-config | 🔴 Blocker | Konfiguration |
| A-04 | Bekræftet: TimeLapse Pro's nginx binder ALDRIG til 21/22/80/443 på staging/prod (CrushFTP-ejerskab verificeret med `lsof` pr. maskine før go-live) | 🔴 Blocker | Audit |
| A-05 | TCP/21 (FTP) ikke åben fra TimeLapse Pro — ejes af CrushFTP på staging/prod | 🔴 Blocker | Audit |
| A-06 | TCP/22 (SSH) ikke direkte Internet-eksponeret for admin-brug — enten lukket eller stærkt begrænset (IP-allowlist/VPN, evt. ikke-standard admin-SSH-port); kan også være CrushFTP-ejet på staging/prod, bekræft pr. maskine | 🟠 Anbefalet | Firewall |
| A-07 | TCP/8080 ikke eksponeret direkte | 🔴 Blocker | Audit |
| A-08 | SFTP-port (device-upload, 22222) forbliver adskilt fra kunde-webtrafikken på 8443 — og fra CrushFTP's egen FTP/SFTP på 21/22 | 🟠 Anbefalet | Konfiguration |
| A-09 | Alle ukendte porte (2201, 5000, 7000) klassificeret | ✅ Klassificeret 2026-07-05 | Asset-register |
| A-10 | fail2ban aktivt og konfigureret (API login + scanner) — vigtigt uanset Cloudflare-valg, da 8443 er direkte offentligt eksponeret | 🟠 Anbefalet | Drift |
| A-11 | Mac firewall (pf/macOS): hvis Cloudflare bruges som DNS-proxy (orange cloud, IKKE Tunnel) foran port 8443 for ekstra WAF/DDoS-beskyttelse, begræns 8443 til Cloudflares IP-ranges; hvis fuldt direkte eksponering uden Cloudflare-proxy, tillad 8443 bredt og læn dig på fail2ban+rate-limiting i stedet. Peter skal vælge hvilken af de to undervarianter | 🟠 Anbefalet — undervariant ikke valgt endnu | Konfiguration |
| A-12 | OpenWebUI er lab-only eller RBAC-beskyttet intern service (ikke public) | 🟠 P1 | Konfiguration |
| A-13 | CrushFTP-portejerskab (21/22/80/443) verificeret med `lsof` på DEN KONKRETE staging-/prod-maskine før TimeLapse-installation, ikke kun antaget | 🔴 Blocker (ny, 2026-07-05) | Audit |

**Verificering A-01 til A-13:**
```bash
# Lokalt på staging/prod-maskinen, FØR TimeLapse-installation:
sudo lsof -i -n -P | grep LISTEN | grep -v '127.0.0.1\|::1'
# Bekræft at 21/22/80/443 tilhører CrushFTP (ikke TimeLapse) og at 8443 er ledig

# Efter installation:
curl -sk https://backend.timelapse-pro.dk:8443/api/health | jq .
```

**A-09 klassifikation (verificeret 2026-07-05 af Codex på Mac Headend):**

| Port | Proces/ejer | Klassifikation | Produktionsbeslutning |
|---:|---|---|---|
| 2201 | `sshd-session` | TimeLapse reverse SSH lab/support-forward til edge (`ssh -p 2201 ...`) | Tilladt kun som eksplicit support-/lab-tunnel; må ikke være generel Internet-facing port uden Cloudflare Access/firewall-regel. |
| 5000 | macOS `ControlCenter` | Host/platform, Apple AirPlay/Control Center-familie — ikke TimeLapse | Skal enten disable's på headend eller blokeres af Mac/pf firewall før Internet-facing produktion. |
| 7000 | macOS `ControlCenter` | Host/platform, Apple AirPlay/Control Center-familie — ikke TimeLapse | Skal enten disable's på headend eller blokeres af Mac/pf firewall før Internet-facing produktion. |

A-09 er dermed lukket som "ukendt port"-blocker. Eksponeringsrisikoen for 5000/7000 håndteres fortsat under A-11 (Mac firewall) og den generelle nginx-port-migration A-01 til A-04 (direkte eksponering, ikke Cloudflare Tunnel).

---

## B. TLS og certifikater

| # | Krav | Status |
|---|---|---|
| B-01 | TLS 1.2 minimum, TLS 1.3 foretrukket | ✅ nginx-config OK |
| B-02 | **RETTET 2026-07-05 (periodisk tjek #36):** Gyldigt TLS-certifikat — Let's Encrypt via DNS-01 (`certbot-dns-cloudflare`, rører ingen port); "Cloudflare managed"-certifikat er kun relevant hvis den valgfrie Cloudflare DNS-proxy-undervariant (se A-11) senere aktiveres | Bekræft ved go-live |
| B-03 | HSTS aktiveret (max-age≥31536000, includeSubDomains) | ✅ nginx-config OK |
| B-04 | Security headers: X-Content-Type-Options, X-Frame-Options, CSP | ✅ nginx-config OK |
| B-05 | Certifikat-ekspirerings-monitoring | 🟠 Mangler |
| B-06 | **RETTET 2026-07-05 (periodisk tjek #36):** Origin-certifikat valideret af Cloudflare — kun relevant HVIS den valgfrie Cloudflare DNS-proxy-undervariant (A-11) aktiveres; ved den nuværende plan (ren direkte 8443-eksponering, ingen Cloudflare-proxy) er B-02's Let's Encrypt-certifikat det faktiske og eneste krav, ikke et separat Cloudflare origin-certifikat | Bekræft ved go-live (betinget af A-11-valg) |

---

## C. Autentificering og adgangskontrol

| # | Krav | Status |
|---|---|---|
| C-01 | JWT_SECRET er stabilt og kryptografisk stærkt (≥256 bit) | ✅ LaunchAgent |
| C-02 | JWT_SECRET ikke i Git | ✅ |
| C-03 | Standard super_admin-password er ændret fra default | 🔴 Bekræft manuelt — **Delvist fremskridt, nu LIVE 2026-07-06:** `_warn_if_default_admin_password_active()` (headend/main.py) kører ved HVERT opstart (ikke kun ved oprettelse) og logger `log.critical(...)` (fanges af SIEM via den generiske log-pipeline) hvis en aktiv admin/super_admin-konto stadig autentificerer mod "changeme". Testet af Peter (6/6 bestået), merget til `main` via PR #1 og deployet til rd-headend via `deploy-macmini`-CI-jobbet (grønt). Giver nu vedvarende, automatisk SIEM-synlighed af risikoen — men erstatter IKKE selve den manuelle bekræftelse på rd/staging/prod-maskinerne, som stadig udestår som selve go-live-blokkeren |
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
| E-02 | Restore-test udført og dokumenteret (dato, scope, RTO) | 🟡 Procedure dokumenteret (2026-07-07) — se ADMINISTRATORMANUAL v10 §8.3. Kør `./deploy/scripts/verify_backup.sh --test-restore` for automatisk test. Kræver manuelt verifikation på reelt produktionsbackup før go-live. |
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
| G-02 | Retention policy konfigureret pr. kamera | ✅ Implementeret (2026-07-07) — migration v15, database model (Camera.retention_days, CaptureDeletionLog), cleanup loop, API endpoints (/api/admin/retention/*), UI (RetentionPage + per-kamera felt i CameraPage), test suite (8/8 unit tests). Se ADMINISTRATORMANUAL v10 §1.5.5, BRUGERMANUAL v10 §7.2. |
| G-03 | Databehandleraftale med kunden | 🟠 Delvist — Kirkbi A/S (kunden bag Site Travbyen) har allerede en aftale, OG (2026-07-05, Peter) har givet eksplicit tilladelse til at billederne bruges til udvikling af TimeLapse Pro (dækker agenters R&D-adgang). Fortsat ubekræftet: dækker aftalen også AI/Gemini cloud-eskalering og GPS-metadata? Fortsat blocker for NYE kunder — kræver jurist OG en tilsvarende udviklings-tilladelse, ikke startet for dem. Se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §4 |
| G-04 | Subprocessor-liste (Google Cloud/Gemini) offentliggjort | 🟠 Udkast klar (2026-07-04). 2026-07-05 (Claude): kode håndhæver nu at GCS-bucket-region matcher Vertex-region i BEGGE indgange (UI-API + CLI-bulk-script, se `RISK_ASSESSMENT_v10.md` R12) — men den faktiske PRODUKTIONS-værdi af `GOOGLE_CLOUD_LOCATION`/`gemini_gcs_bucket_region` er stadig ikke bekræftet at være EU (kræver live-adgang, ikke gjort af Claude) |
| G-05 | Download/adgangslog pr. billede implementeret | ✅ Implementeret og testverificeret 2026-07-05 — ny `CaptureAccessLog`-tabel + `_log_capture_access()`, kaldt fra `GET /api/images/{device_id}/{filename}` (kun fuldopløsningsbilledet, ikke thumbnails). Codex kørte `python3 -m py_compile headend/main.py headend/database.py headend/tests/test_capture_access_log.py`, `pytest tests/test_capture_access_log.py -v` (**4/4 passed**) og hele `headend/tests/` (**41/41 passed**). |
| G-06 | Procedure for databrud (Art. 33/34, 72t) dokumenteret | 🟠 Anbefalet |
| G-07 | Oplysningspligt til registrerede (Art. 13/14) | 🟠 Skitse-tekst klar (2026-07-04) — kræver juridisk godkendelse |
| G-08 | Vulnerability handling og CVE-proces (SEC-014) | 🟡 Procedure oprettet (2026-07-07) — se `SEC-014_Vulnerability_Handling_CVE_Process.md`. CVE overvågning, triage, patch process og rollback plan dokumenteret. Ikke testet i praksis endnu. |

> **Note G (2026-07-04→07, Claude/Claude-2):** GPS/lokationsmetadata er nu implementeret og verificeret i produktion (kilde/tillid vises i UI). DPIA-template (G-01) og retention policy (G-02) skal eksplicit dække dette felt, ikke kun selve billedet — se `RISK_ASSESSMENT_v10.md` R12. **Opdateret 2026-07-07 (Claude-2):** Retention policy (G-02/CAP-007) er nu fuldt implementeret — backend, UI (RetentionPage + per-kamera felt), test suite (8/8 unit tests bestået), og dokumentation opdateret. G-01 (DPIA) og G-03 (DPA) forbliver juridiske opgaver. **Opdateret 2026-07-07 (Claude-3):** SEC-013 (Incident Response) og SEC-014 (Vulnerability Handling) procedurer oprettet — se G-06 og G-08.

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
| Change ticket med artifact/SBOM/rollback | Delvist — se TILFØJELSE 2026-07-05 nedenfor | P1 |
| Per-target update status | 🟡 Flush-regression (fundet 2026-07-05, Claude, periodisk tjek — den 2026-07-05-deployede rettelse `61802951` manglede `db.flush()` før rollup-forespørgslen, så SIDSTE device i en multi-target rollout aldrig blev synligt for egen forespørgsel og global status sad fast på "approved") er nu RETTET, committet af Codex (`1e3c3321`, samme commit som H-05-testene) og deployet — headend genstartet, `/api/health` 200 OK, 13/13 tests bestået i Codex' venv 2026-07-05 nat. Resterer: live multi-device-rollout-test (2+ enheder, `scope=site`) for at bekræfte reel flip til "Deployet"/"Rullet tilbage" i produktion — ikke kørt fra periodisk heartbeat, da det ændrer state for rigtige enheder. Data+UI (`update_targets`, `/api/updates/{id}/flow-status`, `UpdatesPage.tsx`) har eksisteret siden juni 2026. **Separat gap, formaliseret 2026-07-05 (periodisk tjek):** hvis et device slettes fra CMDB (decommissioned) mens det har en ikke-terminal rollout-status, tæller `_resolve_update_targets()` det ikke længere med i `total` — rollup'en kan derfor flippe til "Deployet" selvom det fjernede device reelt aldrig afsluttede. Dokumenteret i kontrakttest (`test_update_lifecycle.py::test_device_removed_from_cmdb_mid_rollout_does_not_prematurely_flip`, committet), IKKE rettet — se `RISK_ASSESSMENT_v10.md` R06 for de tre løsningsmuligheder og en rådgivende anbefaling (periodisk tjek #54, mulighed (c)), kræver Peters produktbeslutning før kode. | P1 |

**TILFØJELSE 2026-07-05 (Claude, periodisk tjek) — change ticket-dokument kunne komme ud af trit med SBOM/artifact-felter:** `ChangeTicket.sbom_ref`/`.test_evidence_ref` blev gemt i DB og eksponeret via ticket-API'et, men optrådte ALDRIG i det faktiske signerede dokument (`machine_json`/`human_readable_md`) — hverken ved oprettelse, eller (værre) når et artifact blev bundet til en allerede-oprettet ticket via `bind_artifact_to_update`: der blev `ticket.sbom_ref`/`.artifact_id` opdateret direkte på DB-rækken UDEN at gensignere dokumentet, så `content_sha256`/`signature` reelt kunne pege på et forældet indhold — et integritetshul i et dokument hvis formål er at være en troværdig, signeret audit-post. Rettet: logikken der bygger `machine_json`/`human_readable_md`/`content_sha256`/`signature` er samlet i en delt funktion (`_render_change_ticket_document`), brugt både ved oprettelse og ved sen artifact-binding, så dokumentet altid gensignes når SBOM/artifact-felter ændres — ticket_id/oprindelig oprettelse/oprettet-af bevares uændret. 4 nye kontrakt-tests i `headend/tests/test_change_ticket_sbom.py`, hele suiten (23/23, inkl. de 19 eksisterende) bestået i midlertidig venv. **Stadig åbent (derfor fortsat "Delvist"):** ingen kode/politik for at KRÆVE et SBOM/test-evidens før en ticket kan godkendes (feltet kan stadig være tomt), og selve SBOM-indholdets dækning/kvalitet er ikke vurderet her — kun at det, der rent faktisk er registreret, nu vises korrekt og signeret.

---

## L. Domæner (website-arkitektur)

| Domæne | Formål | Krav |
|---|---|---|
| `www.timelapse-pro.dk` | Public informationssite | Statisk hosting, **på en anden maskine/tjeneste end staging/prod** (CrushFTP-konflikt) — ikke Headend-origin |
| `timelapse-pro.dk` | Redirect eller public site | Ikke direkte Headend |
| `backend.timelapse-pro.dk` | Kunde/admin UI og API | Direkte nginx-eksponering på **port 8443** (ikke 443/80 — CrushFTP-ejet på staging/prod) + fail2ban/rate limiting, certifikat via DNS-01 — ikke Cloudflare Tunnel, se §A |

Login-knapper på public website skal redirecte til `https://backend.timelapse-pro.dk:8443/`
(portnummeret er obligatorisk).

---

## M. Miljøadskillelse og agent-adgang (R&D/Staging/Prod)

**Baggrund (2026-07-05):** Peter har afklaret topologien i `HANDOVER_LOG.md` som svar på Codex'
agent/service-principal-forslag — se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` for fuld
beskrivelse. Nuværende system = R&D/Test (`rd`, `timelapse.froekjaer.dk`); planlagt 3. server
(iMac) = Staging; fremtidig `timelapsepro.dk` på et helt andet fysisk system = Prod, som allerede
i dag kører CrushFTP med live kundedata + det legacy-system TimeLapse Pro skal erstatte.

| # | Krav | Status |
|---|---|---|
| M-01 | Miljøterminologi fastlagt (`rd`/`staging`/`prod`) uden kollision med eksisterende "lab mode" (kamera-debug, R17) | ✅ Besluttet 2026-07-05 (Peter) |
| M-02 | Standard: default-deny — Claude/Codex har INGEN stående adgang til staging/prod, kun R&D | ✅ Besluttet 2026-07-05 (Peter, ordret bekræftet), **uddybet 2026-07-06:** en kontrolleret, tidsbegrænset, logget undtagelsesvej ("break-glass") til installation/fejlsøgning er nu godkendt ved siden af standardtilstanden — se M-08. Teknisk håndhævelse af selve default-deny (M-05) mangler stadig som defense-in-depth, men politikken gælder fra nu, ikke fra en fremtidig kode-deadline |
| M-03 | Staging-server (iMac) verificeret kapabel til fuld softwarestack | 🟡 Ikke testet — ældre hardware, kapacitet ukendt |
| M-04 | Staging etableret som software-parity-gate før prod-deploy | 🟡 Planlagt, ikke bygget |
| M-05 | Agent/service-principal-model (Codex-forslag) med hård prod-afvisning implementeret | 🟡 **"Layer 2" kodet OG testet 2026-07-06 (Claude, via `claude_proxy.py` med audit-log) — 24/24 tests bestået, `py_compile` OK, committet + PR #2 åbnet (`claude/m05-agent-lockdown-2026-07-06` → `main`, https://github.com/froekjaer/timelapse-pro/pull/2), afventer Peters review/merge + CI/deploy.** — se `headend/main.py`: ny reserveret rolle `role="agent"` (database.py), `_agent_role_blocked_in_this_environment()` (hård, IKKE DB-konfigurerbar kodespærre — kun TIMELAPSE_ENV afgør det), håndhævet to steder: (1) `/api/auth/login` afviser FØR password-tjek med samme generiske 401-besked som forkert password (ingen rolle-lækage), (2) `get_current_user()` — det centrale håndhævelsespunkt for ALLE cookie/JWT-autoriserede endpoints — afviser også allerede udstedte sessions. `_log_agent_lockdown_status()` logger status ved hvert opstart (samme SIEM-mønster som C-03). 15 nye tests i `headend/tests/test_agent_principal_lockdown.py`, reelt kørt og bestået (se ovenfor) — periodisk tjek #89 lavede desuden en uafhængig, statisk code review af koden mod testene, ingen fejl fundet. **Dette er stadig kun trin 2 af 5** (env-flag + hård afvisning) — det fulde `AgentPrincipal`/`AgentToken`/`AgentElevationGrant`-skema (trin 3), audit-udvidelse (trin 4) og CLI (trin 5) er IKKE bygget. Forudsætning fra forrige runde (`TIMELAPSE_ENV="rd"` i `edge/agent.py`/`headend/siem.py`) var allerede rettet/deployet 2026-07-06 |
| M-06 | Kirkbi A/S-databehandleraftale + udviklingstilladelse verificeret til at dække faktisk nuværende behandling | 🟢 Aftale + eksplicit udviklingstilladelse (2026-07-05) bekræftet af Peter — kun AI/Gemini-eskalering + GPS-dækning fortsat ubekræftet, se G-03 |
| M-07 | Udførlig, selvstændig installationsguide/-script til headend på staging/prod (Peter kan installere alene, uden agent-adgang) | 🟠 Under udarbejdelse 2026-07-05 — se `INSTALLATION_GUIDE_HEADEND_v1.md`/`deploy/install/install_headend.sh` |
| M-08 | Kontrolleret, logget break-glass support-adgang (installation/fejlsøgning) — design | 🟠 Design-notat klar (`Claude_Support_Access_Model_2026-07-06.md`). **Skema-forberedelse bygget 2026-07-06:** ny, separat `AccessTicket`-tabel (`headend/database.py`) — testdækket, committet/pushet til PR #2 (se M-05). Fortsat INGEN Support-CA, `grant_support_access.sh`-script eller udstedelses-endpoint bygget — det er bevidst Peters eget, senere skridt (nøglegenerering). Nøgleelementer: separat Support-CA (ikke device-CA'en fra #52), korttidslevende SSH-certifikater med indbygget kryptografisk udløb, kunde-samtykke-tjek pr. aktivering, signeret ticket + audit-log. Peter er eneste, der kan aktivere adgangen |

---

## I. Verificeringskommandoer (endelig go-live-check)

**Rettet 2026-07-05:** port 443/80 er fjernet fra disse kommandoer — CrushFTP ejer dem på
staging/prod. TimeLapse Pro's backend verificeres på port **8443** i stedet (se §A).

```bash
# 1. Portaudit — ingen TimeLapse-proces på public 21/22/80/443 (CrushFTP-ejet); 8443 er TimeLapse
sudo lsof -i -n -P | grep LISTEN
lsof -nP -iTCP -sTCP:LISTEN

# 2. Health
curl https://backend.timelapse-pro.dk:8443/api/health          # Forventet: 200

# 3. Auth-gate
curl -i https://backend.timelapse-pro.dk:8443/api/cmdb/         # Forventet: 401
curl -i https://backend.timelapse-pro.dk:8443/api/admin/stats   # Forventet: 401

# 4. Rate limit
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://backend.timelapse-pro.dk:8443/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"x","password":"y"}'
done
# Forventet: 429 efter 10 forsøg/min

# 5. TLS
echo | openssl s_client -connect backend.timelapse-pro.dk:8443 2>/dev/null \
  | openssl x509 -noout -dates -subject

# 6. Backup
ls -la /Volumes/Backup/timelapse/

# 7. Edge upload
grep "HTTP 200" ~/Library/Logs/timelapse-headend.log | tail -5
```

Forventet ved go-live: ingen TimeLapse-origin på 21/22/80/443 (kun CrushFTP der); backend svarer
på 8443; health 200; CMDB/admin 401 uden login; seneste backup kan restores; aktiv Edge kan
heartbeat, capture, upload og update-policy-poll.

---

## J. Go/No-go vurdering

| Kategori | Blokerende | Status |
|---|---|---|
| A. Netværk/porte | 7 blokkere (A-01,02,03,04,05,07,13) | 🔴 Ikke klar |
| B. TLS | 0 blokkere | ✅ Klar |
| C. Auth | 1 blokker uafklaret (C-03: bekræft super_admin-password er ændret fra default — nu med automatisk SIEM-varsling ved opstart, se C-03-note, men selve den manuelle bekræftelse på rd/staging/prod udestår stadig) + P0 #5 (HMAC-enforcement/stale credentials, C-10) stadig åben — MFA (C-07) er løst 2026-07-02, men det er ikke det samme som "ingen blokkere" | 🔴 Ikke klar |
| D. Secrets | 0 blokkere | ✅ Klar |
| E. Backup | 1 blokker (E-02 restore-test) | 🔴 Ikke klar |
| F. CMDB | 0 blokkere | ✅ Klar |
| G. GDPR | 1 blokker (per-kunde) (G-03 databehanderaftale — G-02 retention-kode er implementeret 2026-07-07, G-05 download-log er lukket 2026-07-05) — kun juridiske opgaver tilbage (DPIA, DPA) | 🔴 Ikke klar |
| H. Code quality | 0 blokkere | ✅ Klar |
| M. Miljøadskillelse/agent-adgang | 1 blokker (M-05: "layer 2"-kode skrevet OG testet 2026-07-06 — 24/24 bestået, committet, PR #2 åbnet, afventer Peters review/merge + CI/deploy — se M-05-rækken ovenfor) — M-02 (selve politikken) er ✅ besluttet/bekræftet af Peter 2026-07-05 | 🔴 Ikke klar |

**Konklusion:** Systemet er IKKE klar til Internet-eksponering og domæneskift til timelapse-pro.dk. Estimeret tid til go-live gate: **4–6 uger** med fokusindsats.

**De tre vigtigste opgaver:**
1. Direkte nginx-eksponering på **port 8443** (ikke 443/80 — CrushFTP-ejet på staging/prod;
   ikke Cloudflare Tunnel), certifikat via DNS-01, konfigureret på staging/prod (se
   §A-korrektionen ovenfor og `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4)
2. Backup + restore dokumenteret
3. DPIA-template + retention policy (før første rigtige kunde-site)

**TILFØJELSE 2026-07-04 (nat, Claude) — svar på "go-live i morgen":** God fremgang i nat (R18-krasch rettet, billed-backup-hul lukket i kode, auto-backup-loop tilføjet, DPIA/retention-udkast, migrationsrunbooks for nginx/Cloudflare og node-agent klar til eksekvering), men konklusionen ovenfor står ved magt — **fuld Internet-eksponering på timelapse-pro.dk kan ikke forsvarligt nås i morgen.** Det skyldes ikke manglende indsats, men at flere blokkere kræver ting kode alene ikke kan levere på under et døgn: en reel restore-test (kræver faktisk gendannelse til et testmiljø og observation af tidsforbrug), databehandleraftale (kræver jurist), ~~DNS-propagering ved Cloudflare Tunnel-cutover~~ (**RETTET, periodisk tjek #46:** Tunnel er ikke prod-målarkitekturen, jf. §A-korrektionen 2026-07-05 — det reelle DNS-trin er nu udstedelse/propagering af DNS-01-certifikatet for `backend.timelapse-pro.dk:8443`, `certbot-dns-cloudflare`, ikke et Tunnel-cutover), og en per-kunde DPIA-godkendelse (skabelonen er klar, men skal udfyldes og godkendes pr. kunde). At forcere disse ville bryde med "dobbelttjekker før du udfører".

**Realistisk "i morgen"-tjekpunkt i stedet:** (a) bekræft at automatisk backup + billed-mirror rent faktisk kører korrekt på Mac Mini'en (kør en manuel backup, tjek `timelapse-images-mirror/`-mappen og loggen), (b) gennemgå og evt. eksekvér node-agent- og nginx-port-migrationsrunbooks i et kontrolleret vindue (ikke under produktionstrafik) — **(rettet, periodisk tjek #46: "nginx/Cloudflare-runbooks" betyder her port-8443/DNS-01-migrationen, ikke et Cloudflare Tunnel-runbook, jf. §A)**, (c) Peter beslutter og bekræfter status på `TL-DCA63234D813` (stale credential-runbook afventer hans svar), (d) hvis "go-live" i stedet betyder en lukket lab/pilot-fase for få kendte enheder (ikke offentlig internet-eksponering), er det væsentligt tættere på klar end den fulde liste ovenfor antyder — kategori B/C/D/F/H er alle ✅.
