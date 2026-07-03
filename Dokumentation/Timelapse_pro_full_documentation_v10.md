# TimeLapse Pro — Samlet dokumentation (v10, konsolideret)

**Version:** 10 (konsolideret)  
**Dato:** 2026-07-02  
**Udarbejdet af:** Claude (konsolidering af Claude-sæt + Codex-sæt)  
**Status:** Pre-production / LAB  
**Kildedokumenter:** 14 dokumenter (7 × Claude, 7 × Codex) + underliggende assessments og kodebase  
**Konsoliderer:** `Claude_Timelapse_pro_full_documentation_v1.md` (superset-backbone) + `Codex_Timelapse_pro_full_documentation_v1.md` (begge var selv merged dokumenter — arkiveret i `Gamle versioner/`).

> **Læsevejledning:** Dette dokument er en autoritativ konsolidering. Del 1–8 udgør drifts- og risikoviden. Del 9 indeholder standard-specifikke indekser med kontrol-mapping. Del 10–11 indeholder leverandør/partner- og kundedokumenter, der er klar til tilpasning. Appendiks dokumenterer uoverensstemmelser og handover-status.

---

## Indholdsfortegnelse

- [DEL 1 — Executive Summary](#del-1--executive-summary)
- [DEL 2 — Systemarkitektur](#del-2--systemarkitektur)
- [DEL 3 — Konsolideret risikovurdering og penetrationstest](#del-3--konsolideret-risikovurdering-og-penetrationstest)
- [DEL 4 — Konsolideret kravregister og implementeringsstatus](#del-4--konsolideret-kravregister-og-implementeringsstatus)
- [DEL 5 — Go-live checkliste (konsolideret)](#del-5--go-live-checkliste-konsolideret)
- [DEL 6 — Brugermanual](#del-6--brugermanual)
- [DEL 7 — Administratormanual](#del-7--administratormanual)
- [DEL 8 — Port-audit og website-arkitektur](#del-8--port-audit-og-website-arkitektur)
- [DEL 9 — Standard-specifikke indekser og kontrol-mapping](#del-9--standard-specifikke-indekser-og-kontrol-mapping)
  - [9.1 SABSA](#91-sabsa--sherwood-applied-business-security-architecture)
  - [9.2 COBIT 2019](#92-cobit-2019)
  - [9.3 ISO 27001:2022](#93-iso-270012022)
  - [9.4 IEC 62443](#94-iec-62443)
  - [9.5 NIS2](#95-nis2-direktiv-eufodningslovgivning)
  - [9.6 CRA](#96-cra--cyber-resilience-act)
  - [9.7 GDPR](#97-gdpr)
- [DEL 10 — Leverandør- og partnerdokumenter](#del-10--leverandør--og-partnerdokumenter)
- [DEL 11 — Kundedokumenter](#del-11--kundedokumenter)
- [APPENDIKS A — Konvergensanalyse og uoverensstemmelser](#appendiks-a--konvergensanalyse-og-uoverensstemmelser)
- [APPENDIKS B — Handover og aktuel systemstatus](#appendiks-b--handover-og-aktuel-systemstatus)

---

# DEL 1 — Executive Summary

## 1.1 Produkt og formål

TimeLapse Pro er en multi-tenant edge/headend-platform til professionel, kontinuerlig og GDPR-compliant dokumentation af byggepladser. Systemet kombinerer:

- **Edge-enheder** (OrangePi 4 Pro med Nikon Z30) der tager automatiske billeder, bufrer lokalt og uploader krypteret
- **Headend** (Mac Mini, FastAPI, PostgreSQL, nginx, Ollama, React UI) der modtager, analyserer og præsenterer billeder
- **AI-analyse** (Gemini cloud + lokal Ollama) der genererer søgbare tags per billede
- **GRC/CMDB** til compliance-dokumentation, update governance og sikkerhedsstyring

## 1.2 Aktuel status (2026-06-23)

**Begge uafhængige assessments (Claude og Codex) konkluderer samstemmende:**

| Miljø | Status |
|---|---|
| LAB / R&D | ✅ GO — systemet virker og testes aktivt |
| Første kontrollerede testsite | 🟡 Næsten go — afventer backup/restore, node-agent, Nikon Z30 LAB |
| Internet-facing produktion | 🔴 NO-GO — 3 kritiske blokkere ikke lukket |
| `timelapse-pro.dk` domæneskift | 🔴 NO-GO — samme 3 blokkere + portmigration |

**De 3 kritiske blokkere (P0 — begge assessments enige):**

1. **Porte:** nginx lytter på public `*:80` og `*:443` — skal migreres til Cloudflare Tunnel + `127.0.0.1:18443`
2. **Backup/restore:** Automatisk backup kører, men restore-test er ikke dokumenteret
3. **GDPR:** DPIA-template, retention policy og databehandleraftale mangler pr. kunde/site

## 1.3 Estimeret tid til go-live gate

| Kilde | Estimat |
|---|---|
| Claude | 4–6 uger med fokusindsats |
| Codex | 2–4 uger (pre-Internet gate) + 2–3 uger (site readiness) + 3–5 uger (customer readiness) |
| **Konsolideret** | **4–6 uger til første Internet-eksponering; 8–12 uger til første rigtige kundeplads** |

---

# DEL 2 — Systemarkitektur

## 2.1 Overordnet arkitektur

```
[Nikon Z30]
    │
    ▼
[OrangePi 4 Pro — Edge]          [GitHub CI / Lab]
  timelapse-edge service              │
  gphoto2 / GPIO relay                │ artifacts (signed)
  SQLite WAL / store-and-forward      │
  HAL abstraction layer               ▼
    │                          [Mac Mini — Headend]
    ├── SFTP upload (22222) ──►    FastAPI/uvicorn :8000
    └── HTTPS upload ──────────►  PostgreSQL :5432
                                   nginx (lab: *:443 / prod: 127.0.0.1:18443)
                                   Ollama :11434
                                   SIEM/syslog :5514
                                   /Volumes/data-fast (storage)
                                   /Volumes/Backup (backup)
                                       │
                                       ▼
                                [Browser — React UI]
                              Kundevisning / Admin / CMDB / GRC / LAB
```

## 2.2 Komponenter

### Edge (OrangePi 4 Pro)
- **Hardware:** OrangePi 4 Pro (RK3588S, 4GB RAM), Nikon Z30 via USB/gphoto2
- **Software:** Debian/Armbian, timelapse-edge systemd service, SQLite WAL
- **Sikkerhed:** SFTP-only upload, HMAC device auth, GPG-signerede updates, store-and-forward ved netværksudfald
- **Aktiv enhed:** `TL-C87FF9587CA0` (192.168.86.134)

### Headend (Mac Mini)
- **Runtime:** Python 3.x, FastAPI/uvicorn, PostgreSQL, nginx
- **AI:** Ollama (lokal) + Google Gemini (cloud batch API)
- **Storage:** `/Volumes/data-fast` (captures), `/Volumes/Backup` (backup)
- **Secrets:** LaunchAgent plist — JWT_SECRET, BREAK_GLASS_ENC_KEY, DATABASE_URL, TIMELAPSE_GPG_KEY
- **LaunchAgent:** `dk.froekjaer.timelapse-headend` (gui/<uid>, ikke root)

### Update-flow (autoritativt)
```
GitHub CI ──► Headend artifact-builder ──► GPG-signering
  ──► Change ticket ──► Admin-godkendelse
    ──► Edge poller ──► Download fra Headend (HTTPS)
      ──► Manifest/hash/sig verification ──► Pre-update backup
        ──► Offline installation ──► Status-rapport til CMDB
```

**Edge må ikke bruge direkte GitHub/apt/Internet i produktion.**

## 2.3 Konfigurationshierarki

```
Global default
  └── Kunde-override
        └── Site-override
              └── Kamera-override (vinder)
```

Effektiv konfiguration beregnes dynamisk. UI viser arvet vs. direkte override vs. vindende lag.

## 2.4 Datamodel (nøgleobjekter)

| Tabel | Formål |
|---|---|
| `customers` | Multi-tenant kundeisolation |
| `sites` | Byggeplads per kunde |
| `cameras` | Logisk kamera-lokation |
| `devices` | Fysisk edge-enhed |
| `device_assignments` | Binding kamera ↔ device (historisk) |
| `captures` | Hvert enkelt billede med metadata |
| `capture_tags` | AI-genererede tags (engelske canonical) |
| `pending_updates` | Update governance |
| `change_tickets` | Audit trail for ændringer |
| `users` | RBAC med roller og customer_id scope |

---

# DEL 3 — Konsolideret risikovurdering og penetrationstest

## 3.1 Metode og scope

Begge assessments (Claude v7 og Codex v7) er gennemført som:
- Dokumentreview (alle dokumenter i `Dokumentation/`)
- Kode- og konfigurationsreview
- Non-destruktiv virtuel penetrationstest
- Ingen aggressiv scanning, brute force eller aktiv exploitation

**Begge assessments har gennemgået og forholdt sig til alle tidligere assessments:** v6, QA_Pentest_2026-06-21, QA_SABSA_Reassessment_2026-06-22, VIRTUAL_PENTEST_STATUS_2026-05-28.

## 3.2 SABSA Business Attributes — konsolideret vurdering

| Attribut | Claude | Codex | Konsolideret | Begrundelse |
|---|---|---|---|---|
| **Availability** | 🟡 | 🟡 | 🟡 Gul | Headend/Edge virker i lab; node-agent nede; startup-preflight mangler |
| **Integrity** | 🟡 | 🟡 | 🟡 Gul | GPG-signerede app artifacts virker; OS update E2E på aktiv edge mangler |
| **Confidentiality** | 🟡 | 🟡 | 🟡 Gul | RBAC og CMDB-auth virker; MFA/WebAuthn ikke enforced; secrets OK |
| **Accountability** | 🟡 | 🟡 | 🟡 Gul | Change tickets og audit-felter findes; fuld evidens-kæde mangler |
| **Authenticity** | 🟡 | 🟡 | 🟡 Gul | HMAC findes; mTLS/intern CA og stale credential cleanup mangler |
| **Manageability** | 🟢 | 🟢 | 🟢 Grøn | Global Config, CMDB, LAB og update UI giver god driftsevne |
| **Continuity** | 🟡 | 🟡 | 🟡 Gul | Edge buffer og rollback findes; restore-test mangler |
| **Extensibility** | 🟢 | — | 🟢 Grøn | HAL, multi-target build, DeviceAssignment model er skalerbar |
| **Auditability** | 🟡 | 🟡 | 🟡 Gul | GRC-dashboard findes; evidens-friskhed er ujævn |
| **Privacy** | 🔴 | 🟡/🔴 | 🔴 Rød | DPIA, retention policy og DPA mangler — blocker for kundeproduktion |
| **Resilience** | 🟡 | — | 🟡 Gul | Rollback implementeret; off-site backup og RTO/RPO mangler |

## 3.3 Konsolideret risikoregister

| ID | Risiko | Score | Status | Claude | Codex | Behandling |
|---|---|---:|---|---|---|---|
| **R01** | SFTP data-lækage / lateral movement | 4 | 🟡 Lav/delvist | Lav | Lav | Gem aktuel chroot-evidens i GRC |
| **R02** | Uautoriseret admin UI-adgang | 8 | 🟡 Medium | Medium | Medium | MFA/WebAuthn for admin og high-risk ops |
| **R03** | Hardwaretab bryder kamera-historik | 3 | 🟢 Lav | Lav | Lav | Camera/DeviceAssignment model løser dette |
| **R04** | Remote SSH tunnel misbrug | 4 | 🟡 Lav | Lav | Lav | Debug-only, auditeret, deny-policy |
| **R05** | Kompromitteret fysisk edge-enhed | 12 | 🔴 Høj | Høj | Høj | mTLS/intern CA, diskkryptering, credential rotation |
| **R06** | Fejlet update i stor skala | 8 | 🟡 Medium | Medium | Medium | Per-target status, staged rollout, OS E2E |
| **R07** | Nøglekompromittering | 8 | 🟡 Medium | Medium | Medium | Stale cleanup, GPG lifecycle, revokering |
| **R08** | MITM / API-manipulation | 8 | 🟡 Medium | Medium | Medium | CA-pinning/mTLS, HMAC globalt |
| **R09** | Backup/restore fejler | 12 | 🔴 Høj | Høj | Høj | Restore-test, RTO/RPO, offsite backup |
| **R10** | SSH tunnel always-on | 4 | 🟡 Lav | Lav | Lav | Restrict + audit, no permanent tunnel |
| **R11** | AI-tags hallucinerer | 9 | 🟡 Medium | Medium | Medium | Cloud/Gemini fast ontologi, confidence score |
| **R12** | GDPR non-compliance | 16 | 🔴 Kritisk | Kritisk | Kritisk | DPIA, retention, DPA, adgangslog |
| **R13** | Headend på public 80/443 | 12 | 🔴 Høj | Høj | Høj | Cloudflare Tunnel + loopback origin |
| **R14** | CMDB inventory stale | 9 | 🟡 Medium | Medium | Medium | Node-agent genstart, freshness-gating |
| **R15** | Nikon Z30 fokus/config drift | 9 | 🟡 Medium | — | Medium | Profilmapping, LAB-tests, accepted equivalents |
| **R16** | localStorage token posture | 6 | 🟡 Medium | — | Medium | Risikovurder + auth-cookie som primær |
| **R17** | JWT HS256 vs RS256 diskrepans | 4 | 🟡 Lav | — | Lav | Dokumenter eller migrer til asymmetrisk JWT |

**Risikoscore = Sandsynlighed (1–4) × Konsekvens (1–4)**

## 3.4 Konsoliderede pentest-fund

### Fund fra Claude-assessment (VPEN-2026-serie)

| ID | Prioritet | Finding | Status |
|---|---|---|---|
| VPEN-2026-001 | P0 | nginx på public `*:80`/`*:443` | Åben — portmigration mangler |
| VPEN-2026-002 | P0 | Backup uden restore-test | Åben |
| VPEN-2026-003 | P0 | GDPR-grundlag mangler | Åben |
| VPEN-2026-004 | P1 | MFA/WebAuthn ikke enforced | Åben |
| VPEN-2026-005 | P1 | Stale edge credentials | Åben |
| VPEN-2026-006 | P1 | OS update E2E ikke testet på aktiv edge | Åben |
| VPEN-2026-007 | P2 | OpenWebUI rolle uklar | Åben |

### Fund fra Codex-assessment (VPEN-CX-serie)

| ID | Prioritet | Finding | Unik Codex-vinkel |
|---|---|---|---|
| VPEN-CX-001 | P0 | Mac Headend lab-nginx ejer 80/443 | Samme som VPEN-2026-001 |
| VPEN-CX-002 | P0 | Backup/restore ikke bevist | Samme som VPEN-2026-002 |
| VPEN-CX-003 | P0 | GDPR-grundlag mangler | Samme som VPEN-2026-003 |
| VPEN-CX-004 | P1 | MFA/WebAuthn ikke enforced | Samme som VPEN-2026-004 |
| VPEN-CX-005 | P1 | Stale credentials | Samme som VPEN-2026-005 |
| VPEN-CX-006 | P1 | OS update E2E mangler | Samme som VPEN-2026-006 |
| VPEN-CX-007 | P2 | OpenWebUI rolle uklar | Samme som VPEN-2026-007 |
| **VPEN-CX-008** | **P2** | **localStorage/token posture** | **Unik Codex — skal adresseres** |
| **VPEN-CX-009** | **P2** | **Frontend lint-gæld (219 fejl)** | **Unik Codex — lint gate mangler** |

### Status på tidligere pentest-fund (fra VIRTUAL_PENTEST_STATUS_2026-05-28)

| Fund | Status |
|---|---|
| CMDB anonym adgang | ✅ Løst (2026-06-21) |
| OS bundle cross-release | ✅ Løst |
| Edge stale vist online i CMDB list/detail | 🟡 Delvist — alle UI-flader skal bruge freshness |
| Nikon Z30 config drift | 🔴 Åben |
| JWT_SECRET fallback | ✅ Løst — production fail-fast |
| SFTP AutoAddPolicy | ✅ Løst — explicit trust required |
| WiFi password via lab_command | ✅ Blokeret som default |
| Lokal edge provisioning CLI | ✅ Implementeret |

---

# DEL 4 — Konsolideret kravregister og implementeringsstatus

## 4.1 Capture og billedbehandling

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| CAP-001 | Automatisk capture på edge | ✅ Implementeret | Nikon Z30 tuning |
| CAP-002 | Store-and-forward ved netværksudfald | ✅ Implementeret | Driftstest over længere periode |
| CAP-003 | Thumbnail ved upload | 🟡 Delvist | Robust postprocessing af manglende thumbnails |
| CAP-004 | Billedkvalitet: blur / lys / eksponering | 🟡 Delvist | Edge CV-quality pipeline modnes |
| CAP-005 | AI-tags og søgning | 🟡 Delvist | Cloud/Gemini ontologi, confidence score, review |
| CAP-006 | Timelapse-video eksport | 🔴 Mangler/delvist | UI/FFmpeg workflow og quality filters |
| CAP-007 | Retention pr. kamera | 🔴 Mangler | GDPR-kritisk blocker |
| CAP-008 | Download/adgangslog pr. billede | 🔴 Mangler | GDPR Art. 5 (accountability) |

## 4.2 Kunde-UI

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| UI-001 | Kundegalleri og lightbox | ✅ Implementeret | Performance/backfill QA |
| UI-002 | Dansk visning af engelske canonical tags | ✅ Implementeret | Kunde-redigerbar oversættelsestabel |
| UI-003 | Kundelogin og RBAC | 🟡 Delvist | MFA/WebAuthn og token posture |
| UI-004 | Compliance-rapporter pr. standard | 🟡 Delvist | Evidence links og rapportgenerator |
| UI-005 | Timelapse-video generering og download | 🔴 Mangler | Krav kendt; ikke production-klar |

## 4.3 Admin-UI og CMDB

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| ADM-001 | CMDB device/software inventory | 🟡 Delvist | Node-agent friskhed, installed/latest version komplet |
| ADM-002 | GRC dashboard | 🟡 Delvist | Click-through, kvantitativ risiko, evidens-friskhed |
| ADM-003 | Backup UI | 🟡 Delvist | Edge backup og restore-test evidens |
| ADM-004 | Edge image build/download | ✅ Implementeret | UI QA og image signing/evidens |
| ADM-005 | Global Config 4 lag | ✅ Implementeret | Flere parametre og inherited/current UX polish |

## 4.4 Update og Edge

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| UPD-001 | Edge må ikke bruge direkte Internet/GitHub/apt | ✅ Princip implementeret | Legacy paths skal forblive lab-only |
| UPD-002 | App artifacts signeres og deployes fra Headend | 🟡 Delvist | Production signing og per-target evidens |
| UPD-003 | OS security/functional offline bundles | 🟡 Delvist | OS E2E på aktiv edge |
| UPD-004 | Lab → staging → prod promotion | 🟡 Delvist | Gates og customer/site/camera scopes |
| UPD-005 | Change tickets | 🟡 Delvist | Signeret approval, MFA-context, kundeaccept |
| UPD-006 | SBOM | 🟡 Delvist | Auto-generering og binding til artifacts |

## 4.5 Provisioning

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| PRO-001 | Bootstrap token med tidsbegrænsning | ✅ Implementeret | Multi-use/batch tokens tilføjet |
| PRO-002 | Edge image build med target-hardware | ✅ Implementeret | OrangePi 4 Pro, PC Plus, RPi 4/5, Jetson |
| PRO-003 | Kamera-lokation adskilt fra fysisk edge | ✅ Implementeret | DeviceAssignment model |
| PRO-004 | WiFi-konfiguration i image | ✅ Implementeret | Inject via build eller post-process |
| PRO-005 | SSH keypair per kamera | ✅ Implementeret | Ed25519, authorized_keys injected |
| PRO-006 | TOTP for Bluetooth/lokal management | ✅ Implementeret | bt-config.yaml, QR-kode i CMDB |
| PRO-007 | Nikon Z30 profil og LAB | 🟡 Delvist | Focus slice, video stream, accepted labels |

## 4.6 Sikkerhed

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| SEC-001 | RBAC (4 roller) | ✅ Implementeret | MFA enforcement mangler |
| SEC-002 | HMAC device auth | 🟡 Delvist | Global rollout og stale cleanup |
| SEC-003 | Intern CA / mTLS | 🔴 Mangler | IEC 62443/CRA-hardening |
| SEC-004 | Backup/restore | 🔴 Mangler/delvist | Restore-test, RTO/RPO, offsite |
| SEC-005 | GDPR DPIA/retention/DPA | 🔴 Mangler | Blocker for kundeproduktion |
| SEC-006 | Incident response procedure | 🔴 Mangler | GDPR 72t procedure |
| SEC-007 | Diskkryptering på edge | 🔴 Mangler | IEC 62443 zone hardening |
| SEC-008 | VDP / security.txt | 🔴 Mangler | CRA-krav |

## 4.7 Konfiguration og network

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| CFG-001 | 4-lags konfigurationshierarki | ✅ Implementeret | UI polish mangler |
| CFG-002 | Nikon Z30 profil med alle parametre | 🟡 Delvist | Focus, ISO, WB, accepted labels |
| NET-001 | Ingen 80/443/21/22/8080 på Headend-origin | 🔴 Mangler | Cloudflare Tunnel + port 18443 |
| NET-002 | Cloudflare Tunnel konfigureret | 🔴 Mangler | Blocker for go-live |
| NET-003 | fail2ban aktivt | 🟡 Delvist | Konfigureret; skal verificeres |

## 4.8 Website og domæne

| ID | Krav | Status | Mangler / Note |
|---|---|---|---|
| WEB-001 | `www.timelapse-pro.dk` statisk site | ✅ Implementeret | `www/index.html` klar til Cloudflare Pages |
| WEB-002 | Login redirect til backend | ✅ Implementeret | Begge login-knapper → `backend.timelapse-pro.dk` |
| WEB-003 | `backend.timelapse-pro.dk` DNS/Tunnel | 🔴 Mangler | Kræver Cloudflare Tunnel |
| WEB-004 | Privacy-side (GDPR oplysningspligt) | 🟡 Delvist | Struktur klar; GDPR-tekst mangler |

## 4.9 Samlet implementeringsstatus

| Kategori | Implementeret | Delvist | Mangler |
|---|---:|---:|---:|
| Capture/billeder | 2 | 4 | 2 |
| Kunde-UI | 2 | 2 | 1 |
| Admin/CMDB | 2 | 3 | 0 |
| Update/Edge | 1 | 5 | 0 |
| Provisioning | 5 | 2 | 0 |
| Sikkerhed | 1 | 2 | 5 |
| Config/Network | 1 | 2 | 2 |
| Website/domæne | 2 | 1 | 1 |
| **Total** | **16** | **21** | **11** |
| **Procent** | **33 %** | **44 %** | **23 %** |

## 4.10 Tidslinje

| Periode | Leverance |
|---|---|
| Apr 2026 | Grund-MVP: capture, SFTP, UI, database, edge |
| Maj 2026 | SABSA/RBAC/reverse SSH/CMDB/update governance |
| Start juni 2026 | Mac Headend, update-flow, HAL, multi-target build |
| Midt juni 2026 | Offline artifact, OS bundle, HMAC, GRC, backup UI |
| 21 juni 2026 | App update E2E på aktiv edge bekræftet |
| 22 juni 2026 | Global Config, kamera-binding, Nikon Z30 LAB profil |
| 23 juni 2026 | Dual assessment + dokumentpakke + statisk website |
| **Estimeret** | **Sprint H (2–4 uger): Porte + backup + GDPR minimum** |
| **Estimeret** | **Sprint I (2–3 uger): Node-agent + MFA + Nikon Z30** |
| **Estimeret** | **Sprint J (3–5 uger): DPA + retention + GRC rapporter** |

---

# DEL 5 — Go-live checkliste (konsolideret)

> **Blocker (🔴):** Systemet MÅ IKKE gå i Internet-facing produktion  
> **Stærkt anbefalet (🟠):** Bør løses inden første rigtige kundeplads  
> **Anbefalet (🟡):** Løses snarest muligt efter go-live

## A. Netværk og porteksponering

| # | Krav | Status | Kilde |
|---|---|---|---|
| A-01 | nginx lytter IKKE på public `*:80` og `*:443` | 🔴 Åben | Begge |
| A-02 | Cloudflare Tunnel: `timelapse-pro.dk` → `127.0.0.1:18443` | 🔴 Åben | Begge |
| A-03 | `backend.timelapse-pro.dk` via Cloudflare Tunnel | 🔴 Åben | Begge |
| A-04 | nginx lytter på `127.0.0.1:18443` (ikke `*:18443`) | 🔴 Åben | Claude |
| A-05 | TCP/21 (FTP) ikke aktiv | 🔴 Verificer | Begge |
| A-06 | TCP/22 ikke direkte Internet-eksponeret | 🟠 | Begge |
| A-07 | TCP/8080 ikke eksponeret public | 🔴 Verificer | Begge |
| A-08 | SFTP-port ændret 22222 → 12222 | 🟠 | Begge |
| A-09 | Ukendte porte (2201, 5000, 7000) klassificeret | 🔴 Åben | Claude |
| A-10 | fail2ban aktivt og konfigureret | 🟠 | Claude |
| A-11 | macOS firewall blokerer alt indgående undtagen CF + SFTP | 🟠 | Claude |
| A-12 | OpenWebUI er lab-only eller RBAC-beskyttet intern service | 🟠 | Begge |

## B. TLS og certifikater

| # | Krav | Status | Kilde |
|---|---|---|---|
| B-01 | TLS 1.2 minimum, TLS 1.3 foretrukket | ✅ OK | Begge |
| B-02 | Gyldigt TLS-certifikat (CF managed / Let's Encrypt) | Bekræft | Begge |
| B-03 | HSTS (max-age≥31536000, includeSubDomains) | ✅ OK | Claude |
| B-04 | Security headers (X-Content-Type-Options, X-Frame-Options, CSP) | ✅ OK | Claude |
| B-05 | Certifikat-ekspirerings-monitoring | 🟠 Mangler | Claude |

## C. Autentificering og adgangskontrol

| # | Krav | Status | Kilde |
|---|---|---|---|
| C-01 | JWT_SECRET stabilt og stærkt (≥256 bit) | ✅ OK | Begge |
| C-02 | JWT_SECRET ikke i Git | ✅ OK | Begge |
| C-03 | Standard super_admin-password ændret | 🔴 Bekræft | Claude |
| C-04 | RBAC på alle `/api/admin/*` endpoints | ✅ OK | Begge |
| C-05 | Alle CMDB-endpoints kræver auth | ✅ Løst 2026-06-21 | Begge |
| C-06 | Rate limiting på `/api/auth/login` | ✅ nginx | Claude |
| C-07 | MFA/WebAuthn til super_admin og admin | 🟠 Anbefalet | Begge |
| C-08 | Session-timeout | ✅ JWT 12t | Claude |
| C-09 | HMAC enforcement på alle aktive device-tokens | 🟠 Delvist | Begge |
| C-10 | Stale/legacy credentials revokeret | 🟠 Åben | Begge |
| C-11 | localStorage token posture risikovurderet | 🟠 Åben | Codex |

## D. Secrets og nøglehåndtering

| # | Krav | Status | Kilde |
|---|---|---|---|
| D-01 | Ingen secrets i Git-historikken | ✅ OK | Begge |
| D-02 | `secrets/gcp-service-account.json` ikke via webserver | ✅ OK | Claude |
| D-03 | GCP service account roteret inden for 90 dage | 🟠 Check | Claude |
| D-04 | GPG-nøgle F75C248F694C097F er i peter's keyring | ✅ OK | Claude |
| D-05 | GPG-nøgle passphrase verificeret stærk | 🟠 Bekræft | Claude |
| D-06 | Stale edge-credentials (TL-DCA63234D813) revokeret | 🟠 Åben | Begge |
| D-07 | Offline backup af GPG-nøgle | 🟠 Mangler | Claude |

## E. Backup og driftsresiliens

| # | Krav | Status | Kilde |
|---|---|---|---|
| E-01 | Automatisk backup til `/Volumes/Backup` konfigureret | 🔴 Åben | Begge |
| E-02 | Restore-test udført og dokumenteret (dato, scope, RTO) | 🔴 Åben | Begge |
| E-03 | Off-site backup konfigureret | 🟠 Anbefalet | Begge |
| E-04 | Startup-preflight: verificer `/Volumes/data-fast` mount | 🟠 Mangler | Begge |
| E-05 | Node-agent kørende og rapporterer frisk CMDB-inventory | 🟠 Åben (stoppet) | Begge |
| E-06 | RTO og RPO dokumenteret | 🟠 Mangler | Begge |

## F. CMDB og monitoring

| # | Krav | Status | Kilde |
|---|---|---|---|
| F-01 | Alle device-statusser freshness-baserede i alle UI-flader | 🟠 Delvist | Begge |
| F-02 | Stale device vises som offline | 🟠 Delvist | Begge |
| F-03 | Node-agent kørende | 🟠 Stoppet | Begge |
| F-04 | Headend-health monitoreret automatisk | 🟡 Ønsket | Claude |

## G. GDPR og compliance

| # | Krav | Status | Kilde |
|---|---|---|---|
| G-01 | DPIA-template pr. kunde/site | 🔴 Blocker | Begge |
| G-02 | Retention policy pr. kamera | 🔴 Blocker | Begge |
| G-03 | Databehandleraftale-template klar | 🔴 Blocker | Begge |
| G-04 | Subprocessor-liste (Google Cloud/Gemini) offentliggjort | 🟠 Anbefalet | Begge |
| G-05 | Download/adgangslog pr. billede implementeret | 🟠 Mangler | Begge |
| G-06 | Procedure for databrud (Art. 33/34) | 🟠 Mangler | Begge |
| G-07 | Oplysningspligt til registrerede (Art. 13/14) | 🟠 Mangler | Codex |

## H. Code quality og CI

| # | Krav | Status | Kilde |
|---|---|---|---|
| H-01 | GitHub Actions CI grøn | ✅ OK (efter 79581ac) | Begge |
| H-02 | ESLint-gate i CI — ingen nye fejl | 🟠 Mangler (219 eksist.) | Begge |
| H-03 | `slowapi` i requirements.txt | 🟠 Mangler | Claude |
| H-04 | deploy/launchd plist opdateret (non-secret version) | 🟠 Mangler | Claude |
| H-05 | Frontend lint gate | 🟠 Mangler | Codex |
| H-06 | SBOM auto-generering | 🟡 Ønsket | Begge |

## I. Konsolideret Go/No-go

| Kategori | Status |
|---|---|
| A. Netværk/porte | 🔴 Ikke klar |
| B. TLS | ✅ Klar |
| C. Auth | 🟠 Næsten klar |
| D. Secrets | ✅ Klar |
| E. Backup | 🔴 Ikke klar |
| F. CMDB | 🟠 Næsten klar |
| G. GDPR | 🔴 Ikke klar (per-kunde) |
| H. CI/Quality | 🟠 Næsten klar |

**Samlet konklusion (Claude + Codex enige): NO-GO for Internet-facing produktion pr. 2026-06-23.**

---

# DEL 6 — Brugermanual

**Målgruppe:** Kunde, site manager, projektleder og almindelig bruger

## 6.1 Login og adgang

1. Gå til `https://backend.timelapse-pro.dk/` (eller via knap på `www.timelapse-pro.dk`)
2. Indtast brugernavn/e-mail og adgangskode
3. Brug MFA/WebAuthn hvis aktiveret
4. Efter login vises de kunder, sites og kameraer, din rolle giver adgang til

> En kunde kan kun se egne sites, kameraer, billeder, tags og rapporter. Adgang er isoleret per kunde.

## 6.2 Dashboard

Dashboardet giver hurtigt overblik over:
- Aktive kameraer og seneste billeder
- Online / offline / stale status (stale = ingen frisk heartbeat fra edge-enhed)
- Uploadstatus og billedkvalitet
- Alarmer og kvalitetsadvarsler
- Seneste hændelser og tags

## 6.3 Se billeder og galleri

1. Vælg kunde/site/kamera
2. Se thumbnails i galleriet
3. Klik på et billede for fuld visning
4. Filtrer på dato, tags, billedkvalitet eller lysforhold

Thumbnails er normalt forudgenereret. Hvis thumbnails mangler, kontakt administrator — systemet kan postprocessere dem i baggrunden.

## 6.4 Tags og søgning

Backend gemmer canonical tags på engelsk. UI viser danske navne via oversættelsestabel.

Eksempler på søgning:
- `dagtimer, klart sollys, ingen direkte sol i linsen, høj skarphed`
- `regn, dårligt lys`
- `brugbare billeder til timelapse-video`

> AI-tags er hjælpemetadata — ikke juridisk sandhed. Gennemgå billeder manuelt ved vigtige rapporter.

## 6.5 Billedkvalitet

Hvert billede kan vise:
- Blur/fokus-score
- Lys/eksponering
- Mulige kamera-afvigelser
- Upload- og analysestatus

Gentagne kvalitetsproblemer skal sendes til administrator.

## 6.6 Timelapse-video

1. Vælg kamera og datointerval
2. Filtrer på tags, kvalitet og lysforhold
3. Start eksport
4. Download færdig video

> Status pr. 2026-06-23: videoeksport er et dokumenteret krav, men er ikke fuldt production-klar endnu.

## 6.7 Rapporter

Kunder kan på sigt få rapporter pr. standard:
- SABSA, ISO 27001, IEC 62443, NIS2, CRA, GDPR

Rapporter kræver frisk evidens fra CMDB, updates, backup, adgangslog og site-konfiguration.

## 6.8 Kendte begrænsninger (pr. 2026-06-23)

- AI-tags kan være ufuldstændige på historiske billeder, indtil postprocessering er kørt færdig
- Retention og GDPR-adgangslog er ikke fuldt implementeret endnu
- MFA/WebAuthn er planlagt krav — aktiveres inden flerbrugerdrift
- Nikon Z30 LAB/fokusfunktioner er delvist implementeret

## 6.9 Kontakt og fejlhåndtering

Kontakt administrator hvis:
- Du ikke kan logge ind
- Du ser data fra forkert kunde eller site
- Et kamera er offline/stale
- Der mangler billeder eller thumbnails
- Tags virker åbenlyst forkerte
- Billedkvaliteten falder markant

**Forkert adgang til kundedata behandles som sikkerhedshændelse — eskalér straks.**

---

# DEL 7 — Administratormanual

**Målgruppe:** Peter Frøkjær og systemadministratorer

## 7.1 Systemarkitektur (overblik)

```
Edge TL-C87FF9587CA0 (192.168.86.134)
  Nikon Z30 · OrangePi 4 Pro
    ↓ SFTP :22222 / HTTPS
Mac Mini Headend (127.0.0.1:8000 FastAPI)
  PostgreSQL :5432 · nginx (lab: *:443 / prod: 127.0.0.1:18443)
  Ollama :11434 · /Volumes/data-fast · /Volumes/Backup
    ↓ nginx → Browser
React UI (Admin / Kunde / CMDB / GRC / LAB)
```

## 7.2 Daglig driftskontrol

```bash
# Headend health
curl http://127.0.0.1:8000/api/health

# LaunchAgent status
launchctl print gui/$(id -u)/dk.froekjaer.timelapse-headend | grep -E "state =|pid ="

# Seneste log
tail -200 ~/Library/Logs/timelapse-headend.log

# PostgreSQL
pg_isready -U timelapse

# Storage
df -h /Volumes/data-fast /Volumes/Backup

# Captures i dag
psql -U timelapse timelapse_db -c \
  "SELECT COUNT(*) FROM captures WHERE captured_at > NOW()-INTERVAL '24h'"
```

**Kontrollér dagligt:** health, edge heartbeat, seneste capture/upload, CMDB friskhed, backupstatus, diskplads.

## 7.3 Genstart Headend

```bash
# Normal genstart
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend

# Genindlæs plist (efter konfigurationsændring)
launchctl bootout gui/$(id -u)/dk.froekjaer.timelapse-headend
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```

## 7.4 Miljøvariable (LaunchAgent)

| Variabel | Formål |
|---|---|
| `JWT_SECRET` | Signering af JWT-tokens (≥256 bit, stabilt) |
| `BREAK_GLASS_ENC_KEY` | Krypteringsnøgle til break-glass funktion |
| `DATABASE_URL` | PostgreSQL-forbindelsesstring |
| `TIMELAPSE_GPG_KEY` | GPG-nøgle-ID til artifact-signering |

> **VIGTIGT:** Disse secrets MÅ IKKE committes til Git.

## 7.5 Edge-management

```bash
# SSH til edge (direkte — lokalt netværk)
ssh pi@192.168.86.134

# SSH via reverse tunnel (fra headend UI: Admin → CMDB → [device] → SSH Tunnel)
ssh -p <tunnel-port> pi@127.0.0.1

# Edge-logs
sudo journalctl -u timelapse-edge -f
sudo journalctl -u timelapse-edge --since "1 hour ago"

# Manuelt billede (til test)
sudo systemctl stop timelapse-edge
sudo /opt/timelapse/venv/bin/python /opt/timelapse/edge/agent.py --capture-once
sudo systemctl start timelapse-edge
```

## 7.6 Provisioning af ny edge-enhed

1. Gå til **Admin UI → Backup → Edge disk image**
2. Vælg target hardware, kunde og kamera-lokation
3. Angiv WiFi SSID og password (injected i image)
4. Klik "Byg image" (15–30 min)
5. Download `.img.gz` fra listen

```bash
# Flash til SD-kort
gunzip -c timelapse-edge-orangepi4pro-*.img.gz | sudo dd of=/dev/diskN bs=4m status=progress
```

6. Boot — enheden finder automatisk WiFi og registrerer sig
7. Bekræft i **Admin UI → CMDB** at enhed dukker op
8. Tildel kamera-lokation i **Admin UI → Kameraer**

## 7.7 Update-flow

1. CI bygger ny version og opretter change ticket
2. Gå til **Admin UI → Updates**
3. Review change ticket (type, scope, version, teststatus, SBOM)
4. Klik "Godkend" — edge henter og installerer ved næste maintenance window
5. Bekræft i CMDB at edge rapporterer ny version

**Edge må ikke hente updates direkte fra Internet, GitHub eller apt.**

## 7.8 Nikon Z30 og LAB

LAB-procedure:
1. Start LAB mode (Admin UI → LAB)
2. Verificer relay og kamera-tilgængelighed
3. Kør preview
4. Kør full capture
5. Test autofocus / focus slice / focus quality
6. Justér parametre og gem på korrekt konfigurationslag
7. Stop LAB mode

**Kendte åbne punkter:** video stream via reverse SSH, focus step/slice QA, accepted labels (`AWB White` vs `Automatic`).

## 7.9 Global Config

Konfiguration arves: `global → kunde → site → kamera`. Kamera-laget vinder.

- Gå til **Admin UI → Global Config**
- Vælg lag og parameter
- UI viser: arvet værdi / direkte override / effektiv værdi / vindende lag

## 7.10 Backup og restore

```bash
# Verificer seneste backup
ls -la /Volumes/Backup/timelapse/

# Manuel restore
launchctl bootout gui/$(id -u)/dk.froekjaer.timelapse-headend
pg_restore -U timelapse -d timelapse_db /Volumes/Backup/timelapse/db/latest.dump
rsync -avz /Volumes/Backup/timelapse/captures/ /Volumes/data-fast/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```

> **Restore-test SKAL dokumenteres inden go-live.**

## 7.11 GPG og artifact-signering

```bash
gpg --list-secret-keys F75C248F694C097F
gpg --verify TL-EDGE-IMG-*.manifest.json.sig
```

> Nøglen er i `~/.gnupg` (peter's keyring). Backup nøglen offline, krypteret.

## 7.12 nginx og TLS

```bash
# Konfigurationstest
sudo nginx -t

# Genindlæs
sudo nginx -s reload
# eller
brew services restart nginx

# TLS-fornyelse
sudo certbot renew --webroot -w /private/tmp/timelapse-acme-webroot
sudo nginx -s reload
```

## 7.13 Brugerstyring

| Rolle | Adgang |
|---|---|
| `viewer` | Læs billeder, CMDB (read-only) |
| `operator` | Viewer + kamera-status, SSH tunnel (read) |
| `admin` | Operator + updates, config, konfiguration (per customer) |
| `super_admin` | Fuld adgang til alt |

Opret bruger: **Admin UI → Brugere → Opret bruger** (angiv rolle og customer_id scope).

## 7.14 Sikkerhedsprocedurer

### Kompromitteret edge-enhed
1. Revokér credentials i **Admin UI → Key Management → [device] → Revokér**
2. Sæt deny-flag: **Admin UI → CMDB → [device] → Forbyd tunnel**
3. Notér hændelse i incident-log
4. Udsted ny enhed med nyt keypair

### Mistanke om uautoriseret adgang
1. Invalider alle sessioner (roter JWT_SECRET + genstart)
2. Tjek `SELECT * FROM login_events ORDER BY created_at DESC LIMIT 50`
3. Deaktiver kompromitteret konto
4. Kontakt eventuel kunde
5. Vurdér GDPR Art. 33/34 anmeldelse inden 72 timer

### JWT_SECRET-rotation
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# Opdatér LaunchAgent plist og genindlæs
```

## 7.15 Vigtige stier

| Ressource | Sti |
|---|---|
| Repo | `~/projects/timelapse-pro` |
| LaunchAgent | `~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist` |
| Log | `~/Library/Logs/timelapse-headend.log` |
| Venv | `~/.venvs/timelapse-headend/` |
| Captures | `/Volumes/data-fast/` |
| Artifacts | `/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images/` |
| Backup | `/Volumes/Backup/` |
| nginx config | `deploy/nginx/timelapse.froekjaer.dk.conf` |
| GPG keyring | `~/.gnupg/` (nøgle: F75C248F694C097F) |
| Dokumentation | `~/projects/timelapse-pro/Dokumentation/` |

---

# DEL 8 — Port-audit og website-arkitektur

## 8.1 Aktuel portanvendelse (verificeret 2026-06-23)

### TimeLapse Pro-ejede porte

| Port | Binding | Service | Forbudt? | Handling |
|---:|---|---|---|---|
| **80** | `*` | nginx HTTP redirect | ⚠️ JA | Cloudflare Tunnel → fjernes |
| **443** | `*` | nginx HTTPS public | ⚠️ JA | Cloudflare Tunnel → fjernes |
| **8000** | `127.0.0.1` | FastAPI/uvicorn | ✅ OK | Intern |
| **22222** | `*` | SFTP ingress | 🟡 Non-standard | Flyttes til 12222 |

### Platform- og systemporte

| Port | Binding | Service | Handling |
|---:|---|---|---|
| **22** | `*` | macOS SSH (TimeLapse sftp_* blokeret via sshd Match) | Cloudflare Access SSH |
| **5432** | `127.0.0.1` | PostgreSQL | OK |
| **11434** | `127.0.0.1` | Ollama | OK |
| **8080** | `127.0.0.1` | OpenWebUI (nede) | Lab-only |
| **5514** | `127.0.0.1` | SIEM/syslog | OK |
| **21** | ikke aktiv | — | Verificer `lsof -i :21` |

### Uklassificerede porte (begge assessments)

| Port | Codex-observation | Handling |
|---:|---|---|
| 2201/2202 | Reverse SSH/lab sessions | Klassificer inden go-live |
| 5000/7000 | macOS ControlCenter (AirPlay?) | Bekræft — ikke TimeLapse |
| 3283 | Apple Remote Desktop? | Bekræft og beslut |

## 8.2 Produktionsregler for forbudte porte

| Port | Regel (begge assessments enige) |
|---:|---|
| 80 | SKAL ejes af Cloudflare/proxy — ikke Mac Headend-origin |
| 443 | SKAL ejes af Cloudflare/proxy — ikke Mac Headend-origin |
| 21 | MÅ IKKE bruges |
| 22 | MÅ IKKE bruges til TimeLapse SFTP eller normal drift |
| 8080 | MÅ IKKE eksponeres public |

## 8.3 Target portmodel

| Funktion | Port | Binding |
|---|---:|---|
| nginx TLS origin (bag Cloudflare Tunnel) | 18443 | `127.0.0.1` |
| Headend API | 8000 | `127.0.0.1` |
| OpenWebUI (lab-only) | 18081 | `127.0.0.1` |
| SFTP ingress | 12222 | LAN-IP (ikke public) |
| SIEM/syslog | 5514/15514 | `127.0.0.1` |
| Ollama | 11434 | `127.0.0.1` |
| PostgreSQL | 5432 | `127.0.0.1` |

## 8.4 Migrationsplan — Cloudflare Tunnel

```
Internet
  ↓
Cloudflare (edge) — TLS, DDoS, WAF, rate limiting
  ↓ Cloudflare Tunnel (outbound fra Mac, ingen inbound firewall-åbning)
cloudflared daemon på Mac Mini
  ↓
nginx 127.0.0.1:18443
  ↓
uvicorn 127.0.0.1:8000
```

### Migrationstrin (konsolideret)

```bash
# 1. Installer cloudflared
brew install cloudflare/cloudflare/cloudflared

# 2. Log ind og opret tunnel
cloudflared tunnel login
cloudflared tunnel create timelapse-headend

# 3. Konfigurer ~/.cloudflared/config.yml
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <tunnel-id>
credentials-file: /Users/peter/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: timelapse-pro.dk
    service: https://127.0.0.1:18443
    originRequest:
      noTLSVerify: true
  - hostname: www.timelapse-pro.dk
    service: https://127.0.0.1:18443
    originRequest:
      noTLSVerify: true
  - hostname: backend.timelapse-pro.dk
    service: https://127.0.0.1:18443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF

# 4. Tilføj nginx listener på 127.0.0.1:18443
# 5. Test lokalt: curl -sk https://127.0.0.1:18443/api/health
# 6. Start tunnel og test udefra: cloudflared tunnel run timelapse-headend
# 7. Installer som LaunchAgent: cloudflared service install
# 8. Fjern TimeLapse nginx fra *:80 og *:443
# 9. Opdater Headend base_url og Edge bootstrap/config policy
# 10. Gem portaudit som GRC-evidens
```

### Cloudflare DNS

```
CNAME  timelapse-pro.dk         <tunnel-id>.cfargotunnel.com  ✅ proxy
CNAME  www.timelapse-pro.dk     <tunnel-id>.cfargotunnel.com  ✅ proxy
CNAME  backend.timelapse-pro.dk <tunnel-id>.cfargotunnel.com  ✅ proxy
```

## 8.5 Website-arkitektur

```
www.timelapse-pro.dk (statisk — Cloudflare Pages)
  ├── /                  → Forside (hero, features, compliance, login-CTA)
  ├── /features          → Funktioner
  ├── /privacy.html      → GDPR/privatlivspolitik
  └── /login             → Redirect til backend

backend.timelapse-pro.dk (React SPA + FastAPI — via Cloudflare Tunnel)
  ├── /                  → React login
  ├── /gallery           → Billedgalleri (viewer/operator)
  ├── /admin/*           → Admin UI
  └── /api/*             → FastAPI endpoints
```

### Login-flow

```
www.timelapse-pro.dk → klik "Kundelogin" / "Administratorlogin"
  → redirect: https://backend.timelapse-pro.dk/
    → POST /api/auth/login → JWT-cookie
      → RBAC: /gallery (viewer) eller /admin (admin/super_admin)
```

### Go-live verifikation

```bash
# Portaudit — ingen public 80/443 fra TimeLapse
sudo lsof -i -n -P | grep LISTEN | grep -v '127.0.0.1\|::1'

# Funktionel test
curl https://timelapse-pro.dk/api/health          # 200 OK
curl -i https://backend.timelapse-pro.dk/api/cmdb/ # 401
curl -i https://backend.timelapse-pro.dk/api/admin/stats # 401
```

---

# DEL 9 — Standard-specifikke indekser og kontrol-mapping

## 9.1 SABSA — Sherwood Applied Business Security Architecture

### Framework-introduktion
SABSA er et risikobaseret enterprise security arkitektur framework. TimeLapse Pro anvender SABSA's **11 business attributes** som styringsmodel — alle sikkerhedskontroller relateres til disse attributter.

### Business Attribute Mapping

| Attribut | SABSA-definition | TimeLapse Pro-implementering | Status | Åbne gaps |
|---|---|---|---|---|
| **Availability** | Systemet er tilgængeligt når det kræves | Edge store-and-forward; headend LaunchAgent; nginx | 🟡 | Node-agent nede; startup-preflight mangler |
| **Integrity** | Data er korrekt og umanipuleret | GPG-signerede artifacts; HMAC device auth; PostgreSQL transactions | 🟡 | OS update E2E; mTLS mangler |
| **Confidentiality** | Data tilgås kun af autoriserede | RBAC; SFTP chroot; TLS 1.2+; HTTPS-only | 🟡 | MFA mangler; localStorage posture |
| **Accountability** | Handlinger kan spores til individ | Change tickets; login events; capture timestamps | 🟡 | Download-log mangler; GRC evidens ujævn |
| **Authenticity** | Identiteter verificeres | JWT; HMAC; Ed25519 SSH keypairs | 🟡 | Stale credentials; mTLS mangler |
| **Manageability** | Systemer kan administreres effektivt | Global Config 4 lag; CMDB; LAB; Admin UI | 🟢 | Per-target update status |
| **Continuity** | Drift videreføres ved forstyrrelser | Edge buffer; rollback; store-and-forward | 🟡 | Restore-test mangler; RTO/RPO udefineret |
| **Extensibility** | Systemet kan udvides | HAL; multi-target build; DeviceAssignment model | 🟢 | |
| **Privacy** | Persondata beskyttes | RBAC kunde-isolation; TLS | 🔴 | DPIA/retention/DPA mangler |
| **Auditability** | Handlinger kan revideres | GRC dashboard; change tickets | 🟡 | Evidens-friskhed ujævn |
| **Resilience** | Systemet genoprettes ved angreb | GPG-revokering; JWT-rotation; credential-revokering | 🟡 | Offsite backup; tested recovery mangler |

### Leverandør-/partnerdokumenter (SABSA)
- **Security Service Level Agreement (SSLA):** Definerer security-attribut SLA'er for leverandører og cloud-tjenester (se Del 10.1)
- **SABSA Architecture Statement:** Formel binding af business attributter til kontroller

### Kundedokumenter (SABSA)
- **Business Attribute SLA:** Opsummering til kunden af hvilke security-attributter systemet leverer (se Del 11.1)

---

## 9.2 COBIT 2019

### Framework-introduktion
COBIT 2019 er et IT governance- og management-framework. Relevante domæner for TimeLapse Pro:

| Domæne | Relevante processer |
|---|---|
| **EDM** (Evaluate, Direct, Monitor) | EDM03 Ensure Risk Optimization |
| **APO** (Align, Plan, Organise) | APO12 Manage Risk; APO13 Manage Security |
| **BAI** (Build, Acquire, Implement) | BAI03 Manage Solutions; BAI06 Manage IT Changes; BAI10 Manage Configuration |
| **DSS** (Deliver, Service, Support) | DSS04 Manage Continuity; DSS05 Manage Security Services |
| **MEA** (Monitor, Evaluate, Assess) | MEA01 Manage Performance and Conformance Monitoring; MEA02 Manage System of Internal Control |

### Kontrol-mapping

| COBIT 2019 Proces | TimeLapse Pro-kontrol | Status |
|---|---|---|
| EDM03 — Risk Optimization | Risk Assessment v7 (dette dokument Del 3) | 🟡 Delvist |
| APO12 — Risk Management | Risikoregister R01–R17; GRC dashboard | 🟡 Delvist |
| APO13 — Security Management | RBAC; HMAC; GPG; Change tickets | 🟡 Delvist |
| BAI06 — Change Management | Change ticket workflow; update governance; godkendelsesflow | 🟡 Delvist |
| BAI10 — Configuration Management | CMDB; Global Config 4 lag; DeviceAssignment | 🟡 Delvist |
| DSS04 — Continuity | Edge store-and-forward; backup UI; rollback | 🔴 Restore-test mangler |
| DSS05 — Security Services | SFTP chroot; TLS; nginx security headers; fail2ban | 🟡 Delvist |
| MEA01 — Monitoring | GRC dashboard; health endpoint; CMDB freshness | 🟡 Delvist |
| MEA02 — Internal Control | Audit log; change tickets; GPG signature chain | 🟡 Delvist |

### Gaps mod COBIT 2019
- Formelt **IT governance charter** og bestyrelsesgodkendelse mangler (EDM03)
- **KPI/KRI-måling** i GRC dashboard er ikke kvantitativ (MEA01)
- **Service catalog** til kunder ikke formaliseret (DSS01)
- **Supplier management** (APO10) for Google/Gemini ikke formelt dokumenteret

### Leverandør-/partnerdokumenter (COBIT)
- **IT Governance Charter:** Definerer ansvar, roller og eskaleringsveje (se Del 10.2)
- **Change Management Policy:** Formalisering af change ticket workflow

### Kundedokumenter (COBIT)
- **Service Catalog:** Beskrivelse af hvad TimeLapse Pro leverer som managed service (se Del 11.2)
- **Change Notification Policy:** Procedure for at informere kunder om ændringer

---

## 9.3 ISO 27001:2022

### Framework-introduktion
ISO/IEC 27001:2022 specificerer krav til etablering, implementering, vedligeholdelse og løbende forbedring af et informationssikkerhedsstyringssystem (ISMS).

### Kontrol-mapping (Annex A)

| ISO 27001:2022 Kontrol | TimeLapse Pro-implementering | Status |
|---|---|---|
| **5.1** Information security policies | Implicit; ingen formel policy-dokument | 🔴 Mangler |
| **5.10** Acceptable use of information and other assets | RBAC; roller defineret | 🟡 |
| **5.16** Identity management | RBAC; JWT; MFA planlagt | 🟡 |
| **5.17** Authentication information | JWT_SECRET; GPG passphrase; stærke credentials | 🟡 |
| **5.18** Access rights | RBAC kunde-isolation; viewer/operator/admin/super_admin | 🟢 |
| **5.23** Information security for cloud services | Google/Gemini brugt til AI; subprocessor mangler | 🟡 |
| **5.26** Response to information security incidents | Incident response procedure defineret (Del 7.14); 72t mangler | 🟡 |
| **5.29** Information security during disruption | Edge store-and-forward; rollback | 🟡 |
| **6.1** Actions to address risks and opportunities | Risikoregister Del 3 | 🟡 |
| **8.7** Protection against malware | GPG-signerede artifacts; restrict apt på edge | 🟡 |
| **8.8** Management of technical vulnerabilities | SBOM planlagt; VDP mangler | 🔴 |
| **8.9** Configuration management | Global Config 4 lag; CMDB | 🟡 |
| **8.12** Data leakage prevention | SFTP chroot; RBAC isolation | 🟡 |
| **8.16** Monitoring activities | GRC dashboard; health endpoint; syslog SIEM | 🟡 |
| **8.24** Use of cryptography | TLS 1.2+; HMAC; GPG; JWT | 🟡 |
| **8.28** Secure coding | SAST via CI; 73 signals (v5.28-pentest) | 🟡 |
| **8.31** Separation of development and production | Lab → staging → prod gate planlagt | 🟡 |

### Gaps mod ISO 27001:2022
- Ingen **formel ISMS-politik** (5.1)
- Ingen **Statement of Applicability (SoA)**
- Ingen **formelt risiko-treatment-plan**
- **Supplier agreements** for Google/Gemini (5.22)
- **Asset inventory** ikke komplet i CMDB

### Leverandør-/partnerdokumenter (ISO 27001)
- **Leverandør-sikkerhedsaftale:** Krav til underleverandørers informationssikkerhed (se Del 10.3)
- **Audit-klausul:** Ret til sikkerhedsaudit hos underleverandør

### Kundedokumenter (ISO 27001)
- **Sikkerhedsspørgeskema:** Kundens mulighed for at evaluere TimeLapse Pro's sikkerhedsniveau (se Del 11.3)
- **Hændelsesrapporteringsprocedure:** Vejledning til kunden om rapportering af sikkerhedshændelser

---

## 9.4 IEC 62443

### Framework-introduktion
IEC 62443 er en serie standarder for industrielle automations- og kontrolsystemer (IACS) sikkerhed. TimeLapse Pro modelleres som et edge-til-cloud system med definerede zones og conduits.

### Zone- og conduit-model

```
┌─────────────────────────────────────────────────────────┐
│ ZONE 1: Cloud/Internet (SL-0 untrusted)                 │
│   www.timelapse-pro.dk · Cloudflare WAF                 │
└────────────────────┬────────────────────────────────────┘
                     │ CONDUIT 1: Cloudflare Tunnel (TLS)
┌────────────────────▼────────────────────────────────────┐
│ ZONE 2: Headend DMZ (SL-2 target)                       │
│   nginx 127.0.0.1:18443 · FastAPI 127.0.0.1:8000        │
│   PostgreSQL · Ollama · CMDB · GRC                      │
└────────────────────┬────────────────────────────────────┘
                     │ CONDUIT 2: SFTP :22222 / HTTPS (HMAC+JWT)
┌────────────────────▼────────────────────────────────────┐
│ ZONE 3: Edge/Field (SL-2 target)                        │
│   OrangePi 4 Pro TL-C87FF9587CA0                        │
│   Nikon Z30 · timelapse-edge service                    │
│   Lokal buffer · GPG-verificerede updates               │
└─────────────────────────────────────────────────────────┘
```

### Security Level (SL) vurdering

| Zone | SL-target | Nuværende SL | Gap |
|---|---|---|---|
| Zone 1 (Cloud/Internet) | SL-1 | SL-1 | ✅ OK |
| Zone 2 (Headend) | SL-2 | SL-1.5 | 🟡 MFA, port-migration |
| Zone 3 (Edge/Field) | SL-2 | SL-1 | 🔴 mTLS, disk encryption mangler |

### Kontrol-mapping (IEC 62443-3-3 System Requirements)

| SR | Krav | TimeLapse Pro | Status |
|---|---|---|---|
| SR 1.1 | Human user identification and authentication | JWT; RBAC; MFA planlagt | 🟡 |
| SR 1.2 | Software process and device identification | HMAC; Ed25519; bootstrap token | 🟡 |
| SR 1.3 | Account management | Admin UI brugerstyring | 🟡 |
| SR 2.1 | Authorization enforcement | RBAC require_role(); customer isolation | 🟢 |
| SR 3.1 | Communication integrity | TLS 1.2+; HMAC; JWT signature | 🟡 |
| SR 3.2 | Malicious code protection | GPG-signerede artifacts; restrict apt | 🟡 |
| SR 3.3 | Security functionality verification | CI/SAST; virtual pentest | 🟡 |
| SR 3.8 | Session integrity | JWT 12t timeout; session invalidation | 🟢 |
| SR 4.1 | Information confidentiality | SFTP; TLS; RBAC isolation | 🟡 |
| SR 4.2 | Use of cryptography | TLS; HMAC; GPG; JWT | 🟡 |
| SR 5.2 | Zone boundary protection | nginx; Cloudflare WAF planlagt | 🟡 |
| SR 6.1 | Audit log accessibility | GRC; change tickets; login events | 🟡 |
| SR 7.1 | Denial of service protection | rate limiting nginx; fail2ban | 🟡 |
| SR 7.6 | Network and security configuration settings | Global Config; CMDB | 🟡 |

### Gaps mod IEC 62443
- **Intern CA og mTLS** mellem Edge og Headend (SR 3.1, SR 4.1)
- **Diskkryptering** på Edge (SR 4.1)
- **Secure boot** på Edge
- **Formelt zone-dokument** og risiko-per-zone

### Leverandør-/partnerdokumenter (IEC 62443)
- **Security Level Agreement:** Aftalt SL per zone med leverandør (se Del 10.4)
- **Secure Development Agreement:** Krav til leverandørens SDLC

### Kundedokumenter (IEC 62443)
- **System Security Plan (SSP):** Dokumentation af zone-model og sikkerhedsniveau til kunde (se Del 11.4)

---

## 9.5 NIS2-direktiv (EU/Følgelovgivning)

### Framework-introduktion
NIS2 (Network and Information Security Directive 2) gælder for udbydere af essentielle og vigtige tjenester i EU. TimeLapse Pro er relevant som **leverandør til kunder** der kan være NIS2-pligtige (bygherrer, entreprenører).

### Relevans og klassifikation

| Spørgsmål | Vurdering |
|---|---|
| Er TimeLapse Pro selv NIS2-pligtig? | Sandsynligvis nej (SMV-undtagelse) — verificer ved scale-up |
| Kan TimeLapse Pro være en kritisk leverandør for NIS2-kunder? | Ja — supply chain-krav (Art. 21) |
| Forpligtelse som underleverandør? | Kunder kan stille NIS2-inspirerede krav i kontrakten |

### Kontrol-mapping (NIS2 Art. 21 krav)

| NIS2 Art. 21 | Krav | TimeLapse Pro | Status |
|---|---|---|---|
| 21(2)(a) | Politikker for risikostyring | Risikoregister Del 3; GRC dashboard | 🟡 |
| 21(2)(b) | Incident handling | Incident response procedure Del 7.14 | 🟡 |
| 21(2)(c) | Forretningskontinuitet og backup | Backup UI; edge store-and-forward | 🔴 Restore-test mangler |
| 21(2)(d) | Supply chain security | Vurdering af Google/Gemini som underleverandør | 🟡 |
| 21(2)(e) | Sikkerhed i systemudvikling | CI; SAST; GPG-signerede artifacts; change tickets | 🟡 |
| 21(2)(f) | Politikker og procedurer (kryptografi) | TLS; HMAC; GPG; JWT | 🟡 |
| 21(2)(g) | Personalesikkerhed | Kun Peter som admin pt.; RBAC | 🟡 |
| 21(2)(h) | Adgangskontrol og asset management | RBAC; CMDB; Global Config | 🟡 |
| 21(2)(i) | MFA / krypterede kommunikation | MFA planlagt; TLS implementeret | 🟡 |

### Incident-notifikation (Art. 23)

| Trin | Tidsfrist | Handling |
|---|---|---|
| Tidlig varsling | 24 timer | Notificer CSIRT/myndighed om mulig hændelse |
| Hændelsesbeskrivelse | 72 timer | Preliminary rapport til myndighed |
| Endelig rapport | 1 måned | Teknisk analyse, årsag, remediation |

> **Gælder for kunder der er NIS2-pligtige.** TimeLapse Pro skal understøtte kundens notifikationsflow med log-udtræk og hændelsesdokumentation.

### Gaps mod NIS2
- **Formel incident response procedure** med 24t/72t flow (Del 7.14 giver struktur, men ikke NIS2-specifik timing)
- **Supply chain security assessment** af Google/Gemini
- **Business continuity plan (BCP)** ikke formelt dokumenteret
- **Kontraktuelle NIS2-klausuler** til kunder

### Leverandør-/partnerdokumenter (NIS2)
- **Incident Notification Procedure:** Hvad TimeLapse Pro gør ved sikkerhedshændelse og hvad kunden kan forvente (se Del 10.5)
- **Supply Chain Security Requirements:** Krav til underleverandører (Google/Gemini)

### Kundedokumenter (NIS2)
- **Service Continuity Commitment:** TimeLapse Pro's forpligtelse til kontinuitet og tilgængelighed (se Del 11.5)
- **Incident Support Agreement:** Hvordan TimeLapse Pro understøtter kundens NIS2-rapporteringspligt

---

## 9.6 CRA — Cyber Resilience Act

### Framework-introduktion
CRA (EU 2024/2847) stiller krav til cybersikkerhed for produkter med digitale elementer, der sælges på EU-markedet. TimeLapse Pro's edge-enheder (OrangePi + software) er potentielt CRA-pligtige.

### CRA-klassifikation

| Aspekt | Vurdering |
|---|---|
| Er TimeLapse Pro CRA-pligtigt? | Sandsynligvis **Klasse I** (connected devices med default credentials og remote update) |
| CE-mærkning kræves? | Ja — ved kommercielt salg i EU |
| Ansvarlig part | Peter Frøkjær / TimeLapse Pro som producent |

### Kontrol-mapping (CRA Essential Requirements)

| CRA Krav | TimeLapse Pro | Status |
|---|---|---|
| Art. 10(1) — No known exploitable vulnerabilities | SAST i CI; virtual pentest | 🟡 |
| Art. 10(2) — Secure by default | JWT production fail-fast; AutoAddPolicy blokeret | 🟢 |
| Art. 10(3) — Protect confidentiality | TLS; HMAC; RBAC | 🟡 |
| Art. 10(4) — Protect integrity | GPG-signerede artifacts; HMAC | 🟡 |
| Art. 10(5) — Minimal attack surface | Cloudflare Tunnel (planlagt); loopback binding | 🟡 |
| Art. 10(6) — Limited external interfaces | SFTP + HTTPS; ingen direkte GitHub/apt | 🟡 |
| Art. 10(7) — Update mechanism | Signed app artifacts; OS bundle; rollback | 🟡 |
| Art. 10(8) — Security patches | Node-agent poller OS; change tickets | 🟡 |
| Art. 10(10) — Logging | Capture timestamps; login events; change tickets | 🟡 |
| Art. 11 — Vulnerability handling | VDP/security.txt mangler | 🔴 |
| Art. 13 — Technical documentation | SBOM delvist; dette dokument | 🟡 |
| Art. 14 — Vulnerability disclosure | VDP mangler | 🔴 |

### Gaps mod CRA
- **SBOM** (Software Bill of Materials) mangler som formelt artefakt
- **VDP (Vulnerability Disclosure Policy)** og `security.txt` mangler
- **Declared lifetime support** mangler
- **CE-deklaration** og teknisk dokumentation til notified body

### Leverandør-/partnerdokumenter (CRA)
- **SBOM-template:** Struktur for Software Bill of Materials (se Del 10.6)
- **Vulnerability Disclosure Policy (VDP):** Procedure for ansvarlig afsløring (se Del 10.6)

### Kundedokumenter (CRA)
- **Produktsikkerhedserklæring:** Oversigt over CRA-compliance status (se Del 11.6)
- **Opdateringspolitik:** Hvad kunden kan forvente af softwareopdateringer og support-livstid

---

## 9.7 GDPR

### Framework-introduktion
GDPR (Forordning 2016/679) er EU's databeskyttelsesforordning. TimeLapse Pro behandler personoplysninger (billeder af byggepladser kan indeholde personbilleder) og fungerer som **databehandler** for kunder (der er dataansvarlige).

### Lovligt grundlag og dataflows

| Datatype | Behandlingsformål | Lovligt grundlag | Ansvarlig |
|---|---|---|---|
| Billedoptagelser (byggeplads) | Dokumentation | Berettiget interesse / aftale | Kunde (dataansvarlig) |
| Personbilleder i optagelser | Dokumentation | Berettiget interesse | Kunde (dataansvarlig) |
| Brugerkonti og logindata | Adgangsstyring | Aftale | TimeLapse Pro |
| CMDB/systemdata | Drift og sikkerhed | Berettiget interesse | TimeLapse Pro |
| AI-analyse (Gemini) | Tag-generering | Berettiget interesse + kontrakt | Subprocessor-kæde |

### GDPR-kontrol mapping

| Art. | Krav | TimeLapse Pro | Status |
|---|---|---|---|
| Art. 5 | Principper (lovlighed, formålsbegrænsning, dataminimering, nøjagtighed, lagringsbegreening, integritet) | RBAC; retention mangler; adgangslog mangler | 🔴 |
| Art. 13/14 | Oplysningspligt til registrerede | Privacy-side `/privacy.html` (struktur klar; tekst mangler) | 🟡 |
| Art. 25 | Privacy by design og by default | RBAC kunde-isolation; TLS | 🟡 |
| Art. 28 | Databehandleraftale | DPA-template mangler | 🔴 |
| Art. 32 | Tekniske og organisatoriske sikkerhedsforanstaltninger | TLS; HMAC; RBAC; GPG | 🟡 |
| Art. 33 | Anmeldelse af databrud (72 timer) | Procedure delvist (Del 7.14) | 🟡 |
| Art. 34 | Underretning af berørte | Procedure mangler | 🔴 |
| Art. 35 | DPIA for risikable behandlinger | DPIA-template mangler | 🔴 |
| Art. 44 | Overførsler til tredjelande | Google/Gemini (USA) — Adequacy Decision/SCCs | 🟡 |

### Subprocessorer

| Subprocessor | Formål | Datatype | Land | Grundlag |
|---|---|---|---|---|
| Google Cloud / Gemini | AI-billedanalyse | Billeder, tags | USA / EU | EU-US Data Privacy Framework + SCCs |
| OrangePi (hardware) | Edge-hardware | Ingen persondata | Kina | Hardwareleverandør |

### Gaps mod GDPR
- **DPIA** (Art. 35) pr. kunde/site **er en hård blocker**
- **Retention policy** pr. kamera **er en hård blocker**
- **Databehandleraftale** med kunder **er en hård blocker**
- **Adgangslog** pr. billede/download (Art. 5 accountability)
- **Oplysningspligtestekst** til registrerede (bygningsarbejdere på pladsen)

### Leverandør-/partnerdokumenter (GDPR)
- **Databehandleraftale (DPA):** Aftale med kunder om behandling af persondata (se Del 10.7)
- **Subprocessor-liste:** Liste over underbehandlere og grundlag (se Del 10.7)

### Kundedokumenter (GDPR)
- **Privatlivspolitik / GDPR-oplysninger:** Til website og kunder (se Del 11.7)
- **DPIA-template:** Ramme for impact assessment pr. byggeplads (se Del 11.7)
- **Procedure for registreredes rettigheder:** Indsigt, sletning, portabilitet

---

# DEL 10 — Leverandør- og partnerdokumenter

> Disse dokumenter er **templates** til tilpasning. Juridisk bindende udgaver skal gennemgås af advokat.

## 10.1 Security Service Level Agreement (SABSA)

**Formål:** Definerer security-attribut SLA'er for kritiske leverandører og cloud-tjenester.

```
SECURITY SERVICE LEVEL AGREEMENT
Mellem: TimeLapse Pro (Peter Frøkjær)
Og: [Leverandørnavn]
Version: 1.0 — Dato: [DATO]

1. SABSA BUSINESS ATTRIBUTE FORPLIGTELSER
   Leverandøren forpligter sig til at understøtte følgende attributter:
   
   - Availability: [SLA % uptime]
   - Integrity: [Checksums/audit trail]
   - Confidentiality: [Kryptering in-transit og at-rest]
   - Accountability: [Audit logs tilgængelige X måneder]
   - Authenticity: [MFA på admin-adgang]
   - Continuity: [RTO: X timer, RPO: X timer]

2. RAPPORTERING
   Leverandøren leverer månedlig security-rapport.

3. HÆNDELSESHÅNDTERING
   Leverandøren notificerer inden 4 timer ved sikkerhedshændelse.
```

## 10.2 IT Governance Charter (COBIT)

**Formål:** Definerer IT governance-ansvar, roller og eskaleringsveje.

```
IT GOVERNANCE CHARTER — TIMELAPSE PRO
Version: 1.0 — Dato: [DATO]

ROLLER OG ANSVAR:
- Ejer/CEO: Peter Frøkjær — overordnet IT governance
- System Administrator: Peter Frøkjær — daglig drift og sikkerhed
- Kunde-repræsentant: [Kunde] — krav og feedback

GOVERNANCE-PRINCIPPER (COBIT 2019):
1. EDM03: Risikostyring gennemgås minimum kvartalsvist
2. APO12: Risikoregister vedligeholdes og behandles
3. BAI06: Change management via godkendte change tickets
4. BAI10: CMDB vedligeholdes og opdateres automatisk
5. DSS04: Business continuity testes minimum halvårligt
6. MEA01: KPI-rapportering leveres månedligt til ledelse

ESKALERING:
- Operationelle issues: System Administrator
- Sikkerhedshændelser: Ejer inden 2 timer
- GDPR-databrud: Ejer inden 1 time → Datatilsynet inden 72 timer
```

## 10.3 Leverandør-sikkerhedsaftale (ISO 27001)

**Formål:** Sikkerhedskrav til alle underleverandører der behandler TimeLapse Pro-data.

```
LEVERANDØR-SIKKERHEDSAFTALE
Mellem: TimeLapse Pro (Peter Frøkjær)
Og: [Leverandørnavn]
Version: 1.0 — Dato: [DATO]

1. INFORMATIONSSIKKERHEDSKRAV (ISO 27001 Annex A)
   Leverandøren skal:
   a) Implementere og vedligeholde et ISMS eller tilsvarende
   b) Kryptere data i transit (TLS 1.2+) og at rest (AES-256)
   c) Anvende MFA for privilegeret adgang
   d) Notificere TimeLapse Pro om sikkerhedshændelser inden 24 timer
   e) Tillade audit af sikkerhedsforanstaltninger ved anmodning

2. UNDERLEVERANDØRER
   Leverandøren må ikke engagere underleverandører med adgang til
   TimeLapse Pro-data uden forudgående skriftlig godkendelse.

3. DATABEHANDLING
   Se separat Databehandleraftale (Del 10.7).

4. AFTALENS OPHØR
   Ved ophør: sikker sletning af alle TimeLapse Pro-data inden 30 dage.
```

## 10.4 Security Level Agreement (IEC 62443)

**Formål:** Aftalt Security Level per zone med leverandører og integratorer.

```
IEC 62443 SECURITY LEVEL AGREEMENT
TimeLapse Pro — Version: 1.0 — Dato: [DATO]

ZONE-DEFINITIONER OG SECURITY LEVELS:
Zone 1 (Internet/Cloud): SL-1
  - Cloudflare WAF og DDoS-beskyttelse
  - TLS-terminering

Zone 2 (Headend): SL-2 (target)
  - Autentificering krævet for alle endpoints
  - Audit log for alle administrative handlinger
  - Sikkerhedsopdateringer inden 30 dage efter release

Zone 3 (Edge/Field): SL-2 (target)
  - Krypteret kommunikation
  - Signerede software-artifacts
  - Lokal buffer ved netværksudfald

CONDUIT-KRAV:
C1 (Internet → Headend): Cloudflare Tunnel, TLS 1.2+
C2 (Headend → Edge): HTTPS + HMAC + JWT, SFTP/chroot
```

## 10.5 Incident Notification Procedure (NIS2)

**Formål:** Intern og ekstern procedure ved sikkerhedshændelse.

```
INCIDENT NOTIFICATION PROCEDURE
TimeLapse Pro — Version: 1.0 — Dato: [DATO]

INTERN PROCEDURE:
T+0:    Hændelse opdages
T+1h:   Ejer (Peter Frøkjær) notificeres
T+4h:   Indledende vurdering: scope, berørte kunder, datatyper
T+24h:  Tidlig varsling til berørte kunder og relevante myndigheder
T+72h:  Preliminary incident rapport
T+30d:  Endelig rapport med root cause og remediation

KLASSIFIKATION:
- P0: Datatab eller -lækage → Imiddelbar eskalering, GDPR Art. 33
- P1: Uautoriseret adgang → 24 timer eskalering
- P2: Serviceudfald > 4 timer → 72 timer notifikation
- P3: Potentiel sårbarhed → Intern tracking, ingen kundekommunikation

KOMMUNIKATION TIL KUNDER:
Skabelon: "TimeLapse Pro informerer om [hændelsestype] der fandt sted 
[dato/tid]. [Berørte data/services]. [Foranstaltninger truffet]. 
[Kundens anbefalede handling]."
```

## 10.6 VDP og SBOM-template (CRA)

### Vulnerability Disclosure Policy (security.txt)

```
# TimeLapse Pro — Vulnerability Disclosure Policy
# Version: 1.0 — Dato: [DATO]
# Placering: https://www.timelapse-pro.dk/.well-known/security.txt

Contact: security@timelapse-pro.dk
Preferred-Languages: da, en
Encryption: [PGP-nøgle URL]
Acknowledgments: https://www.timelapse-pro.dk/security/hall-of-fame
Policy: https://www.timelapse-pro.dk/security/policy
Expires: [DATO + 1 år]

POLITIK:
Vi tager sikkerhedsrapporter alvorligt. Vi forpligter os til:
- Kvittering inden 48 timer
- Foreløbig vurdering inden 7 dage
- Rettelse eller mitigering inden 90 dage
- Ingen juridiske skridt mod velmente, ansvarlige rapporter
```

### SBOM-template (CycloneDX / SPDX)

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "version": 1,
  "metadata": {
    "timestamp": "[DATO]",
    "component": {
      "name": "timelapse-pro-edge",
      "version": "[VERSION]",
      "type": "firmware"
    }
  },
  "components": [
    {
      "name": "python3", "version": "[VERSION]", "type": "library"
    },
    {
      "name": "fastapi", "version": "[VERSION]", "type": "library"
    }
    // ... genereres automatisk fra requirements.txt og apt-pakkeliste
  ]
}
```

## 10.7 Databehandleraftale (GDPR Art. 28)

**Formål:** Lovpligtig aftale mellem TimeLapse Pro (databehandler) og kunden (dataansvarlig).

```
DATABEHANDLERAFTALE
Dataansvarlig: [Kundenavn], [CVR]
Databehandler: Peter Frøkjær / TimeLapse Pro, [CVR]
Version: 1.0 — Dato: [DATO]

1. FORMÅL OG OMFANG
   Databehandleren behandler personoplysninger på vegne af den dataansvarlige
   i forbindelse med levering af TimeLapse Pro byggepladsdokumentationsservice.

2. BEHANDLINGENS ART OG FORMÅL
   - Billedoptagelser af byggeplads (kan indeholde personbilleder)
   - Lagringssted: Danmark / EU (Mac Mini Headend)
   - AI-analyse: Google Gemini (EU-US Data Privacy Framework)
   - Formål: Tidslapsedokumentation og byggepladskontrol

3. TEKNISKE OG ORGANISATORISKE SIKKERHEDSFORANSTALTNINGER (Art. 32)
   - Kryptering i transit (TLS 1.3) og opbevaring
   - Adgangskontrol (RBAC) med kunde-isolation
   - Audit log for alle adgange
   - Backup med verifikeret restore-kapacitet
   - Sikkerhedsvurdering minimum én gang årligt

4. INSTRUKTIONSPRINCIP
   Databehandleren behandler kun data efter den dataansvarliges dokumenterede
   instruks, herunder ved overførsler til tredjelande.

5. UNDERBEHANDLERE
   Godkendte underbehandlere pr. [DATO]:
   - Google LLC (Gemini AI) — EU-US DPF — USA
   [Kunden godkender listen og notificeres ved ændringer med 30 dages varsel]

6. DEN REGISTREREDES RETTIGHEDER
   Databehandleren bistår den dataansvarlige med:
   - Indsigtsanmodninger (Art. 15)
   - Sletning (Art. 17)
   - Portabilitet (Art. 20)
   - Begrænsning (Art. 18)

7. SLETNING VED AFTALENS OPHØR
   Alle personoplysninger slettes eller returneres inden 30 dage efter
   aftalens ophør, medmindre lovgivning kræver fortsat opbevaring.

8. AUDIT
   Den dataansvarlige kan anmode om audit-rapport eller gennemføre audit
   med 30 dages varsel.

Underskrift Dataansvarlig: __________________ Dato: __________
Underskrift Databehandler: __________________ Dato: __________
```

### Subprocessor-liste

| Subprocessor | Formål | Datatyper | Land | Grundlag |
|---|---|---|---|---|
| Google LLC (Cloud / Gemini) | AI-billedanalyse og tag-generering | Billeder, metadata | USA | EU-US Data Privacy Framework + SCCs |
| [Evt. backup-cloud-leverandør] | Off-site backup | Krypterede backups | [Land] | [Grundlag] |

---

# DEL 11 — Kundedokumenter

> Disse dokumenter leveres til eller bruges i relation til kunder.

## 11.1 Business Attribute SLA (SABSA — til kunde)

```
TIMELAPSE PRO — SIKKERHEDSGARANTIER
Version: 1.0 — Dato: [DATO]

Vi leverer disse security-garantier til din byggeplads:

AVAILABILITY    Vi tilstræber 99% tilgængelighed i driftstid.
                Edge-enheden gemmer billeder lokalt ved nedbrud.

INTEGRITY       Alle billeder gemmes med timestamp og er
                manipulationssikrede via kryptering.

CONFIDENTIALITY Kun autoriserede brugere kan se jeres billeder.
                Ingen andre kunder har adgang til jeres data.

ACCOUNTABILITY  Alle adgange til billeder logges.

CONTINUITY      Backup tages regelmæssigt.
                [RTO: X timer, RPO: X timer — udfyldes ved go-live]

PRIVACY         Vi behandler persondata i overensstemmelse med GDPR.
                Se vores databehandleraftale og privatlivspolitik.
```

## 11.2 Service Catalog (COBIT — til kunde)

```
TIMELAPSE PRO — SERVICE CATALOG
Version: 1.0 — Dato: [DATO]

SERVICE 1: Automatisk byggepladsdokumentation
  - Automatisk billedtagning (interval konfigureres)
  - Sikker upload til cloud-platform
  - Tilgængelighed via browser: pc, tablet, telefon

SERVICE 2: AI-analyse og søgning
  - Automatisk tagging: vejr, aktivitet, kvalitet
  - Søgning og filtrering på alle parametre
  - Dansk brugergrænseflade

SERVICE 3: Timelapse-video
  - Eksport af timelapse-video for valgt periode [PLANLAGT]
  - Filtrering på kvalitet og lysforhold

SERVICE 4: Compliance-dokumentation
  - Audit trail for alle billeder og adgange
  - Compliance-rapporter pr. standard [UNDER UDVIKLING]
  - GDPR-compliant opbevaring

SUPPORT:
  - Kontakt: support@timelapse-pro.dk
  - Responstid: [X timer i arbejdstid]
```

## 11.3 Sikkerhedsspørgeskema (ISO 27001 — til potentielle kunder)

```
TIMELAPSE PRO — SVAR PÅ SIKKERHEDSSPØRGESKEMA
Version: 1.0 — Dato: [DATO]

1. Anvender TimeLapse Pro kryptering?
   JA — TLS 1.3 for al datatransport, krypteret opbevaring.

2. Hvem kan se vores billeder?
   KUN jeres autoriserede brugere. Strikt adgangsonisolation per kunde.

3. Er der gennemført sikkerhedstest?
   JA — Løbende kode-review, SAST i CI og virtuel penetrationstest.

4. Hvad sker der ved sikkerhedshændelse?
   Notifikation inden 24 timer. Se Incident Notification Procedure.

5. Er TimeLapse Pro GDPR-compliant?
   JA — Databehandleraftale udstedes. Subprocessorer: Google/Gemini.

6. Har TimeLapse Pro sikkerhedscertificering?
   Under arbejde — vi arbejder mod ISO 27001 og IEC 62443 alignment.

7. Hvad er backup-strategien?
   Daglig backup, verifikation og restore-test [gennemføres pr. go-live].

8. Kan vi foretage sikkerhedsaudit?
   JA — Med 30 dages varsel, jf. databehandleraftalen.
```

## 11.4 System Security Plan (IEC 62443 — til teknisk kunde)

```
TIMELAPSE PRO — SYSTEM SECURITY PLAN (SSP)
Version: 1.0 — Dato: [DATO]

SYSTEMGRÆNSE:
  Edge-enhed (OrangePi 4 Pro + Nikon Z30) på [kundens byggeplads]
  Headend (Mac Mini) hos TimeLapse Pro
  Kundernes browseradgang via https://backend.timelapse-pro.dk

ZONE-MODEL:
  Zone 3 (Edge/Field): Edge-enhed, SL-2 target
  Zone 2 (Headend): Backend/cloud, SL-2 target
  Zone 1 (Internet): Cloudflare CDN/WAF, SL-1

KONTROLLER PER ZONE:
  Edge:    GPG-signerede updates, HMAC auth, offline-capable
  Headend: RBAC, HTTPS/TLS, audit log, backup
  Transit: TLS 1.3, HMAC, Cloudflare Tunnel

RISICI OG BEHANDLING:
  Se Risikoregister (Del 3 af dette dokument).

ANSVARSFORDELING:
  TimeLapse Pro: Headend, update governance, sikkerhed
  Kunde:         Fysisk sikring af edge-enhed på byggeplads
                 Dataansvar for billeder (GDPR)
```

## 11.5 Service Continuity Commitment (NIS2 — til kunder)

```
TIMELAPSE PRO — SERVICE CONTINUITY COMMITMENT
Version: 1.0 — Dato: [DATO]

TIMELAPSE PRO FORPLIGTER SIG TIL:

1. TILGÆNGELIGHED
   Vi tilstræber [99]% tilgængelighed (excl. planlagt vedligehold).
   Edge-enheden fortsætter med at optage billeder selv ved netværksudfald
   og uploader automatisk ved næste forbindelsesmulighed.

2. PLANLAGTE VEDLIGEHOLDSVINDUER
   Software-opdateringer sker inden for konfigurerede maintenance windows
   (normalt uden for arbejdstid). Kunden notificeres [X dage] i forvejen.

3. SIKKERHEDSHÆNDELSER
   Ved sikkerhedshændelse notificeres kunden inden [24 timer].
   Vi bistår med log-udtræk og dokumentation til myndighedsanmeldelse.

4. BACKUP OG GENDANNELSE
   Data backes op dagligt. RTO: [X timer]. RPO: [X timer].

5. KOMMUNIKATION
   Driftstatus: [status-side URL]
   Kontakt ved hændelse: kontakt@timelapse-pro.dk
```

## 11.6 Produktsikkerhedserklæring (CRA — til kunder)

```
TIMELAPSE PRO — PRODUKTSIKKERHEDSERKLÆRING
Version: 1.0 — Dato: [DATO]

TIMELAPSE PRO EDGE-ENHED OG SOFTWARE

SIKKERHEDSFUNKTIONER:
✅ Signerede software-opdateringer (GPG)
✅ Krypteret kommunikation (TLS 1.3 + HMAC)
✅ Adgangskontrol (RBAC, JWT)
✅ Automatiske sikkerhedsopdateringer via Headend
✅ Offline-kapabel ved netværksudfald

OPDATERINGSPOLITIK:
  Kritiske sikkerhedsopdateringer: inden for 30 dage
  Funktionsopdateringer: kvartalvist
  Supportperiode: [X år fra leveringsdato]

SÅRBARHEDSRAPPORTERING:
  security@timelapse-pro.dk
  Responstid: 48 timer

KENDTE BEGRÆNSNINGER (pr. 2026-06-23):
- Diskkryptering på edge-enhed er under implementering
- mTLS er planlagt — under implementation
- Fuld CRA CE-deklaration forventes Q[X] [ÅR]
```

## 11.7 GDPR-kundedokumenter

### Privatlivspolitik (til www.timelapse-pro.dk/privacy.html)

```
PRIVATLIVSPOLITIK — TIMELAPSE PRO
Sidst opdateret: [DATO]

1. DATAANSVARLIG (for brugerkontodata)
   Peter Frøkjær / TimeLapse Pro
   kontakt@timelapse-pro.dk

2. HVILKE DATA INDSAMLER VI?
   - Billeder fra byggepladsen (kan indeholde personbilleder)
   - Brugerkontooplysninger (navn, e-mail, rolle)
   - Adgangslog (IP-adresse, tidspunkt, handlinger)
   - Tekniske metadata (kamera-ID, timestamp, GPS hvis aktiveret)

3. FORMÅL OG RETSGRUNDLAG
   - Byggepladsdokumentation: Aftale / berettiget interesse
   - Adgangsstyring: Aftale
   - Sikkerhed og audit: Berettiget interesse

4. OPBEVARING OG SLETNING
   Billeder opbevares i [X måneder/år] pr. aftale med dataansvarlig.
   Brugerkonti slettes ved aftaleophør.

5. DELING AF DATA
   Vi deler ikke data med tredjeparter undtagen:
   - Google LLC (Gemini AI-analyse) — EU-US Data Privacy Framework
   Se fuld subprocessor-liste: [URL]

6. DINE RETTIGHEDER
   Du har ret til indsigt, berigtigelse, sletning, begrænsning og
   dataportabilitet. Kontakt: kontakt@timelapse-pro.dk

7. KLAGE
   Du kan klage til Datatilsynet: dt.dk

8. COOKIES
   Vi anvender kun teknisk nødvendige cookies (session).
```

### DPIA-template (GDPR Art. 35 — pr. byggeplads)

```
DPIA — DATA PROTECTION IMPACT ASSESSMENT
TimeLapse Pro — [Kunde] — [Projekt/byggeplads]
Version: 1.0 — Dato: [DATO]

1. BEHANDLINGENS BESKRIVELSE
   Formål: Automatisk billedtagning og dokumentation af byggeplads
   Datatyper: Billeder (kan indeholde personbilleder af medarbejdere)
   Dataansvarlig: [Kunde]
   Databehandler: TimeLapse Pro (Peter Frøkjær)
   Underbehandler: Google LLC (Gemini AI-analyse)

2. NØDVENDIGHED OG PROPORTIONALITET
   Er behandlingen nødvendig? [JA/BEGRUND]
   Er den proportional med formålet? [JA/BEGRUND]
   Kan formålet opnås med mindre indgribende midler? [VURDERING]

3. RISICI FOR DE REGISTREREDE
   Risiko A: Uautoriseret adgang til billeder
   Sandsynlighed: Lav (RBAC + TLS) / Konsekvens: Medium
   Behandling: RBAC-adgangskontrol, audit log, TLS 1.3

   Risiko B: Overførsler til USA (Gemini)
   Sandsynlighed: Høj (sker altid) / Konsekvens: Lav-medium
   Behandling: EU-US Data Privacy Framework + SCCs

4. FORANSTALTNINGER
   ✅ Rollebaseret adgangskontrol
   ✅ Kryptering i transit og opbevaring
   ✅ Databehandleraftale med TimeLapse Pro
   ✅ Subprocessor-liste offentliggjort
   [ ] Oplysning til bygningsarbejdere (skiltning på pladsen)
   [ ] Retention policy konfigureret

5. KONKLUSION
   Behandlingen kan [gennemføres / ikke gennemføres] med ovenstående
   foranstaltninger.
   Konsultation af Datatilsynet [påkrævet / ikke påkrævet].

Underskrift Dataansvarlig: __________________ Dato: __________
```

---

# APPENDIKS A — Konvergensanalyse og uoverensstemmelser

## A.1 Enighed mellem Claude og Codex

Begge assessments er **fuldstændigt enige** om følgende:

1. **NO-GO for Internet-facing produktion** pr. 2026-06-23
2. De **3 kritiske blokkere** er identiske: porte, backup/restore, GDPR
3. **Risikovurdering** for R01–R14 er konsistent
4. **Go-live architektur**: Cloudflare Tunnel + `127.0.0.1:18443`
5. **Domain-model**: `www.timelapse-pro.dk` (statisk) + `backend.timelapse-pro.dk` (Tunnel)
6. **Edge must not bruge direkte Internet/GitHub/apt** i produktion
7. **Node-agent** er stoppet og skal genstartes
8. **HMAC cleanup** af stale credentials er åben P1

## A.2 Uoverensstemmelser og diskrepanser

| Emne | Claude-vurdering | Codex-vurdering | Konsolideret beslutning |
|---|---|---|---|
| **JWT-algoritme** | HS256 (implicit) | Nævner RS256 i aeldre docs vs. HS256 i kode | **HS256 er nuværende implementering.** Dokumentér decision: HS256 acceptabel midlertidigt med stærk secret (≥256 bit). Migrer til RS256/asymmetrisk JWT inden multi-admin scale-up |
| **localStorage token** | Ikke eksplicit nævnt | P2 finding (VPEN-CX-008) | **Åben finding** — risikovurder og flyt til auth-cookie som primær inden prod |
| **Frontend lint** | 219 eksisterende fejl (H-02) | P2 finding (VPEN-CX-009) | **Åben finding** — lint gate i CI, triage og ryd op |
| **Estimeret go-live** | 4–6 uger | 2–4 uger (pre-gate) | **Konsolideret: 4–6 uger** til Internet-eksponering |
| **R15 Nikon Z30** | Ikke selvstændig risiko | Selvstændig R15 | **Medtaget som R15** i konsolideret register |
| **R16/R17** | Ikke i Claude-sæt | Implicit i diskrepanstabel | **Tilføjet** i konsolideret register |
| **SFTP-port** | 22222 → 12222 anbefalet | 12222 anbefalet | **Enige: 12222 er target** |
| **SFTP historik** | Nævner 22222 | Nævner 22/2222/22222 historik | Codex-analyse er mere komplet — dokumenteret i port-audit |

## A.3 Unikke Codex-bidrag (supplerer Claude)

- **Detaljeret diskrepanstabel** for 10 historiske uoverensstemmelser i dokumenter
- **localStorage/token posture** som eksplicit P2 finding
- **Frontend lint-gæld** som eksplicit tracking
- **Nikon Z30 config drift** som selvstændig risiko R15
- **Detaljeret roadmap** opdelt i 4 faser med estimater
- **OpenWebUI portmodel** specifik (18081 target)
- **JWT RS256 vs HS256** konflikt identificeret

## A.4 Unikke Claude-bidrag (supplerer Codex)

- **Fuld nginx-konfiguration** for 18443 og backend.timelapse-pro.dk
- **Komplet Cloudflare Tunnel config.yml** med alle hostnames
- **Detaljeret Go-live checkliste** med 44 konkrete kontrolpunkter
- **SABSA-attributter Extensibility og Resilience**
- **Fuld admin-manual** med shell-kommandoer og restore-procedure
- **GPG-specifik guidance** (F75C248F694C097F)
- **Aktuel edge-IP og device-ID** (TL-C87FF9587CA0, 192.168.86.134)
- **Statisk website** `www/index.html` implementeret

---

# APPENDIKS B — Handover og aktuel systemstatus

## B.1 Aktuel systemstatus (2026-06-23)

| Komponent | Status | Detaljer |
|---|---|---|
| Headend | ✅ Kørende | LaunchAgent gui/<uid>; health OK |
| PostgreSQL | ✅ Kørende | `timelapse_db` |
| nginx | ⚠️ Lab-konfiguration | Lytter på *:80 og *:443 — skal migreres |
| Aktiv Edge | ✅ Aktiv | TL-C87FF9587CA0, 192.168.86.134, Nikon Z30 |
| Node-agent | 🔴 Stoppet | Stoppet 2026-06-22 07:46 — genstart nødvendig |
| GitHub CI | ✅ Grøn | OK efter commit 79581ac (3dd7d4d, 38beca3, ae1c135) |
| GPG-nøgle | ✅ OK | F75C248F694C097F i peter's keyring |
| Ollama | 🟡 | Kørende; OpenWebUI nede (8080) |

## B.2 Aktuelle åbne opgaver (prioriteret)

| Prioritet | Opgave | Type |
|---|---|---|
| P0 | Cloudflare Tunnel + port-migration (nginx 18443) | Infrastruktur |
| P0 | Backup-verifikation + restore-test | Sikkerhed |
| P0 | DPIA-template + retention policy + DPA | GDPR |
| P1 | Node-agent genstart | Drift |
| P1 | Stale credentials (TL-DCA63234D813) revokér/migrer | Sikkerhed |
| P1 | OS update E2E på aktiv edge | Update-flow |
| P1 | MFA/WebAuthn implementering | Sikkerhed |
| P1 | Nikon Z30 LAB — fokus/video/accepted labels | Hardware |
| P2 | `slowapi` tilføj til requirements.txt | CI |
| P2 | deploy/launchd plist non-secret version i repo | CI |
| P2 | CMDB dirty worktree — kirurgisk commit | Git |
| P2 | LAB/Nikon Z30 — lokale ændringer commit | Git |
| P2 | Frontend lint gate + triage af 219 fejl | Quality |
| P2 | localStorage token posture risikovurdering | Sikkerhed |
| P2 | OpenWebUI rolle-beslutning (lab-only vs. prod) | Arkitektur |

## B.3 Nøglereferencer

| Ressource | Reference |
|---|---|
| Aktiv edge | TL-C87FF9587CA0 / 192.168.86.134 |
| GPG-nøgle | F75C248F694C097F |
| Lab-URL | https://timelapse.froekjaer.dk |
| Prod-URL (planlagt) | https://backend.timelapse-pro.dk |
| Artifact-dir | /Volumes/data-fast/peter-home/timelapse-artifacts/edge-images/ |
| Storage | /Volumes/data-fast |
| Backup | /Volumes/Backup |
| GCP project | gen-lang-client-0580464840 |

## B.4 Dokumentoversigt — dette dokument's kilder

| Kilde | Forfatter | Dato | Størrelse |
|---|---|---|---|
| Claude_RISK_ASSESSMENT_v7 | Claude | 2026-06-23 | 20K |
| Claude_KRAVREGISTER_og_STATUS | Claude | 2026-06-23 | 12K |
| Claude_GO_LIVE_CHECKLIST | Claude | 2026-06-23 | 8K |
| Claude_BRUGERMANUAL | Claude | 2026-06-23 | 3,4K |
| Claude_ADMIN_MANUAL | Claude | 2026-06-23 | 12K |
| Claude_PORT_AUDIT_og_WEBSITE | Claude | 2026-06-23 | 9,7K |
| Claude_HANDOVER-2026-06-23 | Claude | 2026-06-23 | 9,7K |
| Codex_RISK_ASSESSMENT_v7 | Codex | 2026-06-23 | 7K |
| Codex_KRAVREGISTER_og_STATUS | Codex | 2026-06-23 | 5,7K |
| Codex_GO_LIVE_CHECKLIST | Codex | 2026-06-23 | 4,1K |
| Codex_BRUGERMANUAL | Codex | 2026-06-23 | 2,4K |
| Codex_ADMINISTRATORMANUAL | Codex | 2026-06-23 | 5,1K |
| Codex_PORT_AUDIT_og_WEBSITE | Codex | 2026-06-23 | 4,3K |
| Codex_DOKUMENTPAKKE_OVERSIGT | Codex | 2026-06-23 | 4,1K |

---

*Dokument slut — Version 1.0 — 23. juni 2026*  
*Næste revision anbefalet ved: go-live gate, ved væsentlige arkitekturændringer, eller senest 90 dage*
