# TimeLapse Pro — Go-live checkliste: krav før Internet-eksponering og timelapse-pro.dk

**Version:** 1.0
**Dato:** 23. juni 2026
**Gælder for:** Skift fra `timelapse.froekjaer.dk` (lab) til `timelapse-pro.dk` (produktion) og egentlig Internet-eksponering af Headend

> **Definitioner:**
> - **Blocker (🔴):** Systemet MÅ IKKE gå i Internet-facing produktion uden dette er opfyldt
> - **Stærkt anbefalet (🟠):** Bør løses inden første rigtige kunde-site aktiveres
> - **Anbefalet (🟡):** Løses snarest muligt efter go-live

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

**Verificering A-01 til A-11:**
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
| C-04 | RBAC aktivt på alle `/api/admin/*` endpoints | ✅ require_role() |
| C-05 | Alle CMDB-endpoints kræver viewer-rolle (ingen anonym adgang) | ✅ Rettet 2026-06-21 |
| C-06 | Rate limiting på `/api/auth/login` (10r/m) | ✅ nginx |
| C-07 | MFA/WebAuthn til super_admin og admin operationer | 🔴 Blocker (anbefalet; se note) |
| C-08 | Session-timeout implementeret | ✅ JWT 12t |
| C-09 | BREAK_GLASS_ENC_KEY er unik og stærk | ✅ LaunchAgent |
| C-10 | HMAC enforcement aktivt for alle aktive device-tokens | 🟠 Stale credentials skal ryddes |

> **Note C-07:** MFA er anbefalede men ikke teknisk en hård blocker for lab-to-prod, da systemet ikke endnu er multi-bruger med mange admins. Bør implementeres inden anden admin oprettes.

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
| E-01 | Automatisk backup til /Volumes/Backup konfigureret og kørende | 🔴 Blocker |
| E-02 | Restore-test udført og dokumenteret (dato, scope, RTO) | 🔴 Blocker |
| E-03 | Off-site backup konfigureret (anden disk/location) | 🟠 Anbefalet |
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

---

## G. GDPR og compliance

| # | Krav | Status |
|---|---|---|
| G-01 | DPIA udfyldt for hvert aktiv kunde-site | 🔴 Blocker for kunde-aktivering |
| G-02 | Retention policy konfigureret pr. kamera | 🔴 Blocker for kunde-aktivering |
| G-03 | Databehandleraftale med kunden | 🔴 Blocker for første kunde |
| G-04 | Subprocessor-liste (Google Cloud/Gemini) offentliggjort | 🟠 Anbefalet |
| G-05 | Download/adgangslog pr. billede implementeret | 🟠 Anbefalet |
| G-06 | Procedure for databrud (Art. 33/34) dokumenteret | 🟠 Anbefalet |
| G-07 | Oplysningspligt til registrerede (Art. 13/14) | 🟠 Anbefalet |

---

## H. Code quality og CI

| # | Krav | Status |
|---|---|---|
| H-01 | GitHub Actions CI er grøn på alle builds | ✅ Efter commit 79581ac |
| H-02 | ESLint-gate i CI — ingen nye fejl | 🟠 Mangler (219 eksisterende fejl) |
| H-03 | `slowapi` tilføjet til requirements.txt | 🟠 Mangler |
| H-04 | deploy/launchd/dk.froekjaer.timelapse-headend.plist opdateret (ikke-secret version) | 🟠 Mangler |
| H-05 | Python test-suite med edge/headend contract-tests | 🟡 Ønsket |
| H-06 | README opdateret (ikke Vite-template) | 🟡 Ønsket |

---

## I. Verificeringskommandoer (endelig go-live-check)

```bash
# 1. Portaudit — ingen public 80/443/21 fra TimeLapse
sudo lsof -i -n -P | grep LISTEN

# 2. Health
curl https://timelapse-pro.dk/api/health

# 3. Auth-gate
curl https://timelapse-pro.dk/api/cmdb/           # Forventet: 401
curl https://timelapse-pro.dk/api/admin/stats      # Forventet: 401

# 4. Rate limit
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://timelapse-pro.dk/api/auth/login \
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
# Bekræft i headend-log at seneste edge-upload lykkedes med HTTP 200
grep "HTTP 200" ~/Library/Logs/timelapse-headend.log | tail -5
```

---

## J. Go/No-go vurdering

| Kategori | Blokerende | Status |
|---|---|---|
| A. Netværk/porte | 8 blokkere | 🔴 Ikke klar |
| B. TLS | 0 blokkere | ✅ Klar |
| C. Auth | 1 blokker (MFA) | 🟠 Næsten klar |
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
